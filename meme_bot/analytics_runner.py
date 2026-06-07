from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .config import BotConfig
from .instagram import InstagramClient
from .performance_store import (
    calculate_performance_score,
    load_performance_store,
    parse_utc,
    prune_performance_store,
    save_performance_store,
    utc_now_iso,
)
from .runner import setup_logging
from .tuning import TuningConfig

LOGGER = logging.getLogger(__name__)


def _eligible_records(config: BotConfig, tuning: TuningConfig):
    store = load_performance_store(config.performance_store_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=tuning.analytics.lookback_days)
    records = []
    for record in sorted(store.posts, key=lambda item: item.posted_at, reverse=True):
        if not record.instagram_media_id:
            continue
        posted_at = parse_utc(record.posted_at)
        if posted_at is not None and posted_at < cutoff:
            continue
        records.append(record)
        if len(records) >= tuning.analytics.max_media_per_run:
            break
    return store, records


def run(config: BotConfig | None = None) -> int:
    setup_logging()
    config = config or BotConfig.from_env()
    tuning = TuningConfig.from_path(config.optimization_config_path)
    try:
        config.validate_for_instagram()
    except ValueError as exc:
        LOGGER.warning("Skipping analytics collection because Instagram config is incomplete: %s", exc)
        return 0

    store, records = _eligible_records(config, tuning)
    if not records:
        LOGGER.info("No recent Instagram media found for analytics update")
        return 0

    client = InstagramClient(config)
    updated = 0
    unavailable_counts: dict[str, int] = {}
    for record in records:
        try:
            insights = client.get_media_insights(record.instagram_media_id or "", tuning.analytics.metrics)
        except Exception as exc:
            LOGGER.warning(
                "Skipping media analytics after Instagram error: instagram_media_id=%s error_class=%s error=%s",
                record.instagram_media_id,
                type(exc).__name__,
                exc,
            )
            continue

        performance_score = calculate_performance_score(insights.metrics)
        fetched_at = utc_now_iso()
        record.latest_metrics = insights.metrics
        record.unavailable_metrics = insights.unavailable_metrics
        record.metric_snapshots.append(
            {
                "fetched_at": fetched_at,
                "metrics": insights.metrics,
                "unavailable_metrics": insights.unavailable_metrics,
                "performance_score": performance_score,
            }
        )
        record.final_performance_score = performance_score
        record.last_metrics_at = fetched_at
        for metric in insights.unavailable_metrics:
            unavailable_counts[metric] = unavailable_counts.get(metric, 0) + 1
        updated += 1
        LOGGER.info(
            "Updated Instagram analytics: instagram_media_id=%s performance_score=%s metrics=%s unavailable=%s",
            record.instagram_media_id,
            performance_score,
            sorted(insights.metrics),
            insights.unavailable_metrics,
        )

    if updated:
        pruned = prune_performance_store(
            store,
            max_posts=tuning.storage.max_posts,
            max_age_days=tuning.storage.max_age_days,
            max_snapshots_per_post=tuning.storage.max_snapshots_per_post,
        )
        save_performance_store(config.performance_store_path, pruned)

    LOGGER.info(
        "Analytics collection complete: considered=%s updated=%s unavailable_counts=%s",
        len(records),
        updated,
        unavailable_counts,
    )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
