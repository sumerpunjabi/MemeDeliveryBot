from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .captions import CaptionResult, generate_caption
from .config import BotConfig
from .instagram import InstagramClient
from .performance_store import (
    PerformanceIndex,
    PerformanceRecord,
    append_or_replace_record,
    append_run_history,
    build_performance_index,
    load_performance_store,
    normalize_title,
    posting_parts,
    prune_performance_store,
    save_performance_store,
)
from .reddit_source import create_reddit, mark_submission_saved
from .reel_source import ReelCandidate, fetch_reel_candidates
from .scoring import ScoreResult, score_candidate
from .tracker import (
    PostedReelRecord,
    append_reel_record,
    load_reel_index,
    normalize_image_url,
    utc_now_iso,
)
from .tuning import TuningConfig
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


@dataclass(frozen=True)
class ScoredReelCandidate:
    candidate: ReelCandidate
    score: ScoreResult


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


def rank_reel_candidates(
    candidates: list[ReelCandidate],
    *,
    performance_index: PerformanceIndex,
    tuning: TuningConfig,
) -> list[ScoredReelCandidate]:
    ranked: list[ScoredReelCandidate] = []
    rejection_counts: dict[str, int] = {}
    for candidate in candidates:
        score = score_candidate(
            candidate,
            media_type="reel",
            tuning=tuning.scoring,
            performance_index=performance_index,
        )
        if score.accepted:
            ranked.append(ScoredReelCandidate(candidate=candidate, score=score))
            LOGGER.info(
                "Accepted reel candidate score: reddit_id=%s total=%s duration=%s breakdown=%s",
                candidate.reddit_id,
                score.total,
                candidate.duration_seconds,
                score.breakdown,
            )
        else:
            for reason in score.rejection_reasons:
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
            LOGGER.info(
                "Rejected reel candidate score: reddit_id=%s total=%s duration=%s reasons=%s breakdown=%s",
                candidate.reddit_id,
                score.total,
                candidate.duration_seconds,
                score.rejection_reasons,
                score.breakdown,
            )
    ranked.sort(key=lambda item: item.score.total, reverse=True)
    LOGGER.info(
        "Reel scoring summary: candidates=%s accepted=%s rejected=%s rejection_counts=%s",
        len(candidates),
        len(ranked),
        len(candidates) - len(ranked),
        rejection_counts,
    )
    return ranked


def select_unposted_reel_candidate(
    scored_candidates: list[ScoredReelCandidate],
    index: Any,
    performance_index: PerformanceIndex,
    config: BotConfig,
    output_dir: Path,
) -> tuple[ScoredReelCandidate, ProcessedVideo] | None:
    duplicate_count = 0
    performance_duplicate_count = 0
    processing_error_count = 0
    hash_duplicate_count = 0

    for scored in scored_candidates:
        candidate = scored.candidate
        normalized_url = normalize_image_url(candidate.source_url)
        if index.contains(candidate.reddit_id, normalized_url):
            duplicate_count += 1
            LOGGER.info("Skipping duplicate reel candidate: reddit_id=%s", candidate.reddit_id)
            continue
        performance_reasons = performance_index.duplicate_reasons(
            reddit_id=candidate.reddit_id,
            reddit_url=candidate.reddit_permalink,
            source_url=candidate.source_url,
            media_url=candidate.media_url,
            title=candidate.title,
        )
        exact_reasons = [reason for reason in performance_reasons if reason != "normalized_title"]
        if exact_reasons:
            performance_duplicate_count += 1
            LOGGER.info(
                "Skipping performance-store duplicate reel candidate: reddit_id=%s reasons=%s",
                candidate.reddit_id,
                exact_reasons,
            )
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
        if performance_index.contains(
            reddit_id=candidate.reddit_id,
            reddit_url=candidate.reddit_permalink,
            source_url=candidate.source_url,
            media_url=candidate.media_url,
            title=candidate.title,
            media_hash=processed_video.video_hash,
        ):
            hash_duplicate_count += 1
            LOGGER.info("Skipping duplicate reel video hash in performance store: reddit_id=%s", candidate.reddit_id)
            continue

        return scored, processed_video

    LOGGER.warning(
        "Reel candidate selection exhausted: total=%s tracker_duplicate=%s performance_duplicate=%s processing_error=%s hash_duplicate=%s",
        len(scored_candidates),
        duplicate_count,
        performance_duplicate_count,
        processing_error_count,
        hash_duplicate_count,
    )
    return None


def _instagram_permalink(client: InstagramClient, media_id: str) -> str | None:
    try:
        details = client.get_media_details(media_id)
    except Exception as exc:
        LOGGER.warning(
            "Could not fetch Instagram permalink after Reel publish: instagram_media_id=%s error_class=%s",
            media_id,
            type(exc).__name__,
        )
        return None
    return str(details.get("permalink")) if details.get("permalink") else None


def _performance_record(
    *,
    candidate: ReelCandidate,
    instagram_media_id: str,
    instagram_permalink: str | None,
    processed_video: ProcessedVideo,
    posted_at: str,
    score: ScoreResult,
    caption: CaptionResult,
) -> PerformanceRecord:
    posting_hour, posting_weekday = posting_parts(posted_at)
    return PerformanceRecord(
        reddit_id=candidate.reddit_id,
        reddit_url=candidate.reddit_permalink,
        source_url=candidate.source_url,
        media_url=candidate.media_url,
        media_hash=processed_video.video_hash,
        title=candidate.title,
        normalized_title=normalize_title(candidate.title),
        subreddit=candidate.subreddit,
        media_type="reel",
        instagram_media_id=instagram_media_id,
        instagram_permalink=instagram_permalink,
        posted_at=posted_at,
        posting_hour_utc=posting_hour,
        posting_weekday_utc=posting_weekday,
        generated_score=score.total,
        score_breakdown=score.breakdown,
        score_rejections=score.rejection_reasons,
        caption_template_id=caption.template_id,
        hashtag_pool_id=caption.hashtag_pool_id,
        hashtags=caption.hashtags,
        video_duration_seconds=processed_video.duration_seconds,
    )


def run(config: BotConfig | None = None) -> int:
    setup_logging()
    config = config or BotConfig.from_env()
    config.validate_for_reddit()
    config.validate_for_instagram(dry_run=config.reels_dry_run)

    index = load_reel_index(config.reel_tracker_path)
    performance_store = load_performance_store(config.performance_store_path)
    performance_index = build_performance_index(performance_store.posts)
    tuning = TuningConfig.from_path(config.optimization_config_path)
    reddit = create_reddit(config)
    candidates = fetch_reel_candidates(reddit, config)
    LOGGER.info("Fetched reel candidates: count=%s", len(candidates))
    ranked = rank_reel_candidates(candidates, performance_index=performance_index, tuning=tuning)

    with tempfile.TemporaryDirectory(prefix="meme-bot-reel-") as tmp:
        selected = select_unposted_reel_candidate(ranked, index, performance_index, config, Path(tmp))
        if selected is None:
            LOGGER.warning("No unposted reel candidate found")
            if not config.reels_dry_run:
                append_run_history(
                    config.run_history_path,
                    {
                        "media_type": "reel",
                        "status": "no_candidate",
                        "candidates_fetched": len(candidates),
                        "candidates_ranked": len(ranked),
                    },
                )
            return 0

        scored, processed_video = selected
        candidate = scored.candidate
        caption = generate_caption(
            candidate,
            media_type="reel",
            score_result=scored.score,
            recent_records=performance_store.posts,
            caption_tuning=tuning.captions,
            scoring_tuning=tuning.scoring,
        )
        domain = urlsplit(candidate.source_url).netloc.lower()
        LOGGER.info(
            "Selected reel candidate: reddit_id=%s subreddit=%s domain=%s reddit_score=%s instagram_score=%s duration=%s size=%s caption_template=%s",
            candidate.reddit_id,
            candidate.subreddit,
            domain,
            candidate.score,
            scored.score.total,
            processed_video.duration_seconds,
            processed_video.size_bytes,
            caption.template_id,
        )
        LOGGER.info("Selected reel score breakdown: reddit_id=%s breakdown=%s", candidate.reddit_id, scored.score.breakdown)

        if config.reels_dry_run:
            LOGGER.info("Reels dry run enabled; not publishing or updating persistent state")
            return 0

        client = InstagramClient(config)
        instagram_media_id = client.post_reel(
            processed_video.path,
            caption.caption,
            share_to_feed=config.reel_share_to_feed,
        )
        instagram_permalink = _instagram_permalink(client, instagram_media_id)

        if config.mark_reddit_saved:
            mark_submission_saved(candidate)

        posted_at = utc_now_iso()
        record = PostedReelRecord(
            reddit_id=candidate.reddit_id,
            source_url=candidate.source_url,
            video_hash=processed_video.video_hash,
            title=candidate.title,
            subreddit=candidate.subreddit,
            instagram_media_id=instagram_media_id,
            posted_at=posted_at,
        )
        append_reel_record(config.reel_tracker_path, record)
        append_or_replace_record(
            performance_store,
            _performance_record(
                candidate=candidate,
                instagram_media_id=instagram_media_id,
                instagram_permalink=instagram_permalink,
                processed_video=processed_video,
                posted_at=posted_at,
                score=scored.score,
                caption=caption,
            ),
        )
        performance_store = prune_performance_store(
            performance_store,
            max_posts=tuning.storage.max_posts,
            max_age_days=tuning.storage.max_age_days,
            max_snapshots_per_post=tuning.storage.max_snapshots_per_post,
        )
        save_performance_store(config.performance_store_path, performance_store)
        append_run_history(
            config.run_history_path,
            {
                "media_type": "reel",
                "status": "published",
                "reddit_id": candidate.reddit_id,
                "instagram_media_id": instagram_media_id,
                "generated_score": scored.score.total,
                "caption_template_id": caption.template_id,
                "candidates_fetched": len(candidates),
                "candidates_ranked": len(ranked),
            },
        )
        LOGGER.info(
            "Published reel and updated tracker/performance store: reddit_id=%s instagram_media_id=%s permalink=%s",
            candidate.reddit_id,
            instagram_media_id,
            instagram_permalink,
        )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
