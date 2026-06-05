from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .config import BotConfig
from .instagram import InstagramClient
from .reddit_source import create_reddit, mark_submission_saved
from .reel_source import ReelCandidate, fetch_reel_candidates
from .tracker import (
    PostedReelRecord,
    append_reel_record,
    load_reel_index,
    normalize_image_url,
    utc_now_iso,
)
from .video_processing import ProcessedVideo, VideoProcessingError, download_video

LOGGER = logging.getLogger(__name__)
DEFAULT_REEL_HASHTAGS = (
    "#memes",
    "#funny",
    "#reels",
    "#instareels",
    "#viralreels",
    "#redditmemes",
    "#dailymemes",
)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def build_reel_caption(candidate: ReelCandidate) -> str:
    title = candidate.title.strip() or "Reddit reel"
    engagement_prompt = "Follow for more daily memes. Share this with someone who needs a laugh."
    attribution = f"via r/{candidate.subreddit} on Reddit"
    subreddit_hashtag = re.sub(r"[^A-Za-z0-9_]", "", candidate.subreddit)
    hashtags = list(DEFAULT_REEL_HASHTAGS)
    if subreddit_hashtag:
        subreddit_tag = f"#{subreddit_hashtag}"
        if subreddit_tag.lower() not in {tag.lower() for tag in hashtags}:
            hashtags.append(subreddit_tag)
    return "\n\n".join([title, engagement_prompt, attribution, " ".join(hashtags)])[:2200]


def select_unposted_reel_candidate(
    candidates: list[ReelCandidate],
    index: Any,
    config: BotConfig,
    output_dir: Path,
) -> tuple[ReelCandidate, ProcessedVideo] | None:
    duplicate_count = 0
    processing_error_count = 0
    hash_duplicate_count = 0

    for candidate in candidates:
        normalized_url = normalize_image_url(candidate.source_url)
        if index.contains(candidate.reddit_id, normalized_url):
            duplicate_count += 1
            LOGGER.info("Skipping duplicate reel candidate: reddit_id=%s", candidate.reddit_id)
            continue

        try:
            processed_video = download_video(
                candidate,
                output_dir=output_dir,
                max_bytes=config.reel_max_bytes,
                max_duration_seconds=config.reel_max_duration_seconds,
            )
        except VideoProcessingError as exc:
            processing_error_count += 1
            LOGGER.warning(
                "Skipping reel candidate after video processing error: reddit_id=%s error_class=%s error=%s",
                candidate.reddit_id,
                type(exc).__name__,
                exc,
            )
            continue

        if index.contains(candidate.reddit_id, normalized_url, processed_video.video_hash):
            hash_duplicate_count += 1
            LOGGER.info("Skipping duplicate reel video hash: reddit_id=%s", candidate.reddit_id)
            continue

        return candidate, processed_video

    LOGGER.warning(
        "Reel candidate selection exhausted: total=%s duplicate=%s processing_error=%s hash_duplicate=%s",
        len(candidates),
        duplicate_count,
        processing_error_count,
        hash_duplicate_count,
    )
    return None


def run(config: BotConfig | None = None) -> int:
    setup_logging()
    config = config or BotConfig.from_env()
    config.validate_for_reddit()
    config.validate_for_instagram(dry_run=config.reels_dry_run)

    index = load_reel_index(config.reel_tracker_path)
    reddit = create_reddit(config)
    candidates = fetch_reel_candidates(reddit, config)
    LOGGER.info("Fetched reel candidates: count=%s", len(candidates))

    with tempfile.TemporaryDirectory(prefix="meme-bot-reel-") as tmp:
        selected = select_unposted_reel_candidate(candidates, index, config, Path(tmp))
        if selected is None:
            LOGGER.warning("No unposted reel candidate found")
            return 0

        candidate, processed_video = selected
        domain = urlsplit(candidate.source_url).netloc.lower()
        LOGGER.info(
            "Selected reel candidate: reddit_id=%s subreddit=%s domain=%s score=%s duration=%s size=%s",
            candidate.reddit_id,
            candidate.subreddit,
            domain,
            candidate.score,
            processed_video.duration_seconds,
            processed_video.size_bytes,
        )

        if config.reels_dry_run:
            LOGGER.info("Reels dry run enabled; not publishing or appending tracker")
            return 0

        instagram_media_id = InstagramClient(config).post_reel(
            processed_video.path,
            build_reel_caption(candidate),
            share_to_feed=config.reel_share_to_feed,
        )

        if config.mark_reddit_saved:
            mark_submission_saved(candidate)

        record = PostedReelRecord(
            reddit_id=candidate.reddit_id,
            source_url=candidate.source_url,
            video_hash=processed_video.video_hash,
            title=candidate.title,
            subreddit=candidate.subreddit,
            instagram_media_id=instagram_media_id,
            posted_at=utc_now_iso(),
        )
        append_reel_record(config.reel_tracker_path, record)
        LOGGER.info(
            "Published reel and updated tracker: reddit_id=%s instagram_media_id=%s",
            candidate.reddit_id,
            instagram_media_id,
        )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
