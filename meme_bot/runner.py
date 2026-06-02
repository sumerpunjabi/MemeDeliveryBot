from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

import requests

from .config import BotConfig
from .instagram import InstagramClient
from .reddit_source import ImageCandidate, create_reddit, fetch_image_candidates, mark_submission_saved
from .tracker import PostedRecord, append_record, calculate_image_hash, load_index, normalize_image_url, utc_now_iso

LOGGER = logging.getLogger(__name__)


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def select_unposted_candidate(
    candidates: list[ImageCandidate],
    index: Any,
    config: BotConfig,
    session: requests.Session,
) -> tuple[ImageCandidate, str] | None:
    for candidate in candidates:
        normalized_url = normalize_image_url(candidate.image_url)
        if index.contains(candidate.reddit_id, normalized_url):
            LOGGER.info("Skipping duplicate candidate", extra={"reddit_id": candidate.reddit_id})
            continue

        try:
            image_hash = calculate_image_hash(
                candidate.image_url,
                session,
                timeout=config.request_timeout_seconds,
                max_attempts=config.max_retry_attempts,
                base_delay_seconds=config.retry_base_seconds,
            )
        except Exception as exc:
            LOGGER.warning(
                "Skipping candidate whose image could not be hashed",
                extra={"reddit_id": candidate.reddit_id, "error_class": type(exc).__name__},
            )
            continue

        if index.contains(candidate.reddit_id, normalized_url, image_hash):
            LOGGER.info("Skipping duplicate image hash", extra={"reddit_id": candidate.reddit_id})
            continue

        return candidate, image_hash
    return None


def run(config: BotConfig | None = None) -> int:
    setup_logging()
    config = config or BotConfig.from_env()
    config.validate_for_reddit()
    config.validate_for_instagram()

    session = requests.Session()
    index = load_index(config.tracker_path)
    reddit = create_reddit(config)
    candidates = fetch_image_candidates(reddit, config)
    LOGGER.info("Fetched image candidates", extra={"candidate_count": len(candidates)})

    selected = select_unposted_candidate(candidates, index, config, session)
    if selected is None:
        LOGGER.warning("No unposted image candidate found")
        return 0

    candidate, image_hash = selected
    domain = urlsplit(candidate.image_url).netloc.lower()
    LOGGER.info(
        "Selected image candidate",
        extra={"reddit_id": candidate.reddit_id, "subreddit": candidate.subreddit, "domain": domain},
    )

    if config.dry_run:
        LOGGER.info("Dry run enabled; not publishing or appending tracker")
        return 0

    instagram_media_id = InstagramClient(config, session=session).post_image(candidate.image_url, candidate.title)

    if config.mark_reddit_saved:
        mark_submission_saved(candidate)

    record = PostedRecord(
        reddit_id=candidate.reddit_id,
        image_url=candidate.image_url,
        image_hash=image_hash,
        title=candidate.title,
        subreddit=candidate.subreddit,
        instagram_media_id=instagram_media_id,
        posted_at=utc_now_iso(),
    )
    append_record(config.tracker_path, record)
    LOGGER.info(
        "Published image and updated tracker",
        extra={"reddit_id": candidate.reddit_id, "instagram_media_id": instagram_media_id},
    )
    return 0


def main() -> None:
    raise SystemExit(run())
