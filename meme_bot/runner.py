from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import requests

from .config import BotConfig
from .captions import CaptionResult, generate_caption
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
from .reddit_source import ImageCandidate, create_reddit, fetch_image_candidates, mark_submission_saved
from .scoring import ScoreResult, score_candidate
from .tracker import PostedRecord, append_record, calculate_image_hash, load_index, normalize_image_url, utc_now_iso
from .tuning import TuningConfig

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoredImageCandidate:
    candidate: ImageCandidate
    score: ScoreResult


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def rank_image_candidates(
    candidates: list[ImageCandidate],
    *,
    performance_index: PerformanceIndex,
    tuning: TuningConfig,
) -> list[ScoredImageCandidate]:
    ranked: list[ScoredImageCandidate] = []
    rejection_counts: dict[str, int] = {}
    for candidate in candidates:
        score = score_candidate(
            candidate,
            media_type="image",
            tuning=tuning.scoring,
            performance_index=performance_index,
        )
        if score.accepted:
            ranked.append(ScoredImageCandidate(candidate=candidate, score=score))
            LOGGER.info(
                "Accepted image candidate score: reddit_id=%s total=%s breakdown=%s",
                candidate.reddit_id,
                score.total,
                score.breakdown,
            )
        else:
            for reason in score.rejection_reasons:
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
            LOGGER.info(
                "Rejected image candidate score: reddit_id=%s total=%s reasons=%s breakdown=%s",
                candidate.reddit_id,
                score.total,
                score.rejection_reasons,
                score.breakdown,
            )
    ranked.sort(key=lambda item: item.score.total, reverse=True)
    LOGGER.info(
        "Image scoring summary: candidates=%s accepted=%s rejected=%s rejection_counts=%s",
        len(candidates),
        len(ranked),
        len(candidates) - len(ranked),
        rejection_counts,
    )
    return ranked


def select_unposted_candidate(
    scored_candidates: list[ScoredImageCandidate],
    index: Any,
    performance_index: PerformanceIndex,
    config: BotConfig,
    session: requests.Session,
) -> tuple[ScoredImageCandidate, str] | None:
    duplicate_count = 0
    performance_duplicate_count = 0
    hash_error_count = 0
    hash_duplicate_count = 0

    for scored in scored_candidates:
        candidate = scored.candidate
        normalized_url = normalize_image_url(candidate.image_url)
        if index.contains(candidate.reddit_id, normalized_url):
            duplicate_count += 1
            LOGGER.info("Skipping duplicate candidate: reddit_id=%s", candidate.reddit_id)
            continue
        performance_reasons = performance_index.duplicate_reasons(
            reddit_id=candidate.reddit_id,
            reddit_url=candidate.reddit_permalink,
            source_url=candidate.image_url,
            media_url=candidate.image_url,
            title=candidate.title,
        )
        exact_reasons = [reason for reason in performance_reasons if reason != "normalized_title"]
        if exact_reasons:
            performance_duplicate_count += 1
            LOGGER.info(
                "Skipping performance-store duplicate candidate: reddit_id=%s reasons=%s",
                candidate.reddit_id,
                exact_reasons,
            )
            continue

        try:
            image_hash = calculate_image_hash(
                candidate.image_url,
                session,
                timeout=config.request_timeout_seconds,
                max_attempts=config.max_retry_attempts,
                base_delay_seconds=config.retry_base_seconds,
                user_agent=config.reddit_user_agent,
            )
        except Exception as exc:
            hash_error_count += 1
            LOGGER.warning(
                "Skipping candidate whose image could not be hashed: reddit_id=%s url=%s error_class=%s error=%s",
                candidate.reddit_id,
                candidate.image_url,
                type(exc).__name__,
                exc,
            )
            continue

        if index.contains(candidate.reddit_id, normalized_url, image_hash):
            hash_duplicate_count += 1
            LOGGER.info("Skipping duplicate image hash: reddit_id=%s", candidate.reddit_id)
            continue
        if performance_index.contains(
            reddit_id=candidate.reddit_id,
            reddit_url=candidate.reddit_permalink,
            source_url=candidate.image_url,
            media_url=candidate.image_url,
            title=candidate.title,
            media_hash=image_hash,
        ):
            hash_duplicate_count += 1
            LOGGER.info("Skipping duplicate image hash in performance store: reddit_id=%s", candidate.reddit_id)
            continue

        return scored, image_hash

    LOGGER.warning(
        "Candidate selection exhausted: total=%s tracker_duplicate=%s performance_duplicate=%s hash_error=%s hash_duplicate=%s",
        len(scored_candidates),
        duplicate_count,
        performance_duplicate_count,
        hash_error_count,
        hash_duplicate_count,
    )
    return None


def _instagram_permalink(client: InstagramClient, media_id: str) -> str | None:
    try:
        details = client.get_media_details(media_id)
    except Exception as exc:
        LOGGER.warning(
            "Could not fetch Instagram permalink after publish: instagram_media_id=%s error_class=%s",
            media_id,
            type(exc).__name__,
        )
        return None
    return str(details.get("permalink")) if details.get("permalink") else None


def _performance_record(
    *,
    candidate: ImageCandidate,
    instagram_media_id: str,
    instagram_permalink: str | None,
    image_hash: str,
    posted_at: str,
    score: ScoreResult,
    caption: CaptionResult,
) -> PerformanceRecord:
    posting_hour, posting_weekday = posting_parts(posted_at)
    return PerformanceRecord(
        reddit_id=candidate.reddit_id,
        reddit_url=candidate.reddit_permalink,
        source_url=candidate.image_url,
        media_url=candidate.image_url,
        media_hash=image_hash,
        title=candidate.title,
        normalized_title=normalize_title(candidate.title),
        subreddit=candidate.subreddit,
        media_type="image",
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
    )


def run(config: BotConfig | None = None) -> int:
    setup_logging()
    config = config or BotConfig.from_env()
    config.validate_for_reddit()
    config.validate_for_instagram()

    session = requests.Session()
    index = load_index(config.tracker_path)
    performance_store = load_performance_store(config.performance_store_path)
    performance_index = build_performance_index(performance_store.posts)
    tuning = TuningConfig.from_path(config.optimization_config_path)
    reddit = create_reddit(config)
    candidates = fetch_image_candidates(reddit, config)
    LOGGER.info("Fetched image candidates: count=%s", len(candidates))
    ranked = rank_image_candidates(candidates, performance_index=performance_index, tuning=tuning)

    selected = select_unposted_candidate(ranked, index, performance_index, config, session)
    if selected is None:
        LOGGER.warning("No unposted image candidate found")
        if not config.dry_run:
            append_run_history(
                config.run_history_path,
                {
                    "media_type": "image",
                    "status": "no_candidate",
                    "candidates_fetched": len(candidates),
                    "candidates_ranked": len(ranked),
                },
            )
        return 0

    scored, image_hash = selected
    candidate = scored.candidate
    caption = generate_caption(
        candidate,
        media_type="image",
        score_result=scored.score,
        recent_records=performance_store.posts,
        caption_tuning=tuning.captions,
        scoring_tuning=tuning.scoring,
    )
    domain = urlsplit(candidate.image_url).netloc.lower()
    LOGGER.info(
        "Selected image candidate: reddit_id=%s subreddit=%s domain=%s reddit_score=%s instagram_score=%s caption_template=%s",
        candidate.reddit_id,
        candidate.subreddit,
        domain,
        candidate.score,
        scored.score.total,
        caption.template_id,
    )
    LOGGER.info("Selected image score breakdown: reddit_id=%s breakdown=%s", candidate.reddit_id, scored.score.breakdown)

    if config.dry_run:
        LOGGER.info("Dry run enabled; not publishing or updating persistent state")
        return 0

    client = InstagramClient(config, session=session)
    instagram_media_id = client.post_image(candidate.image_url, caption.caption)
    instagram_permalink = _instagram_permalink(client, instagram_media_id)

    if config.mark_reddit_saved:
        mark_submission_saved(candidate)

    posted_at = utc_now_iso()
    record = PostedRecord(
        reddit_id=candidate.reddit_id,
        image_url=candidate.image_url,
        image_hash=image_hash,
        title=candidate.title,
        subreddit=candidate.subreddit,
        instagram_media_id=instagram_media_id,
        posted_at=posted_at,
    )
    append_record(config.tracker_path, record)
    append_or_replace_record(
        performance_store,
        _performance_record(
            candidate=candidate,
            instagram_media_id=instagram_media_id,
            instagram_permalink=instagram_permalink,
            image_hash=image_hash,
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
            "media_type": "image",
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
        "Published image and updated tracker/performance store: reddit_id=%s instagram_media_id=%s permalink=%s",
        candidate.reddit_id,
        instagram_media_id,
        instagram_permalink,
    )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
