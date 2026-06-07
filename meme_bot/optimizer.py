from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import BotConfig
from .performance_store import (
    PerformanceRecord,
    append_run_history,
    duration_bucket,
    load_performance_store,
    load_run_history,
    utc_now_iso,
)
from .runner import setup_logging
from .tuning import OptimizerTuning, TuningConfig, default_optimized_config

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OptimizationChange:
    path: str
    old_value: float | str | None
    new_value: float | str | None
    reason: str
    samples: int
    average_score: float | None = None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ensure_config(raw: dict) -> dict:
    config = default_optimized_config()
    for key, value in raw.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key] = {**config[key], **value}
        else:
            config[key] = value
    for section, defaults in default_optimized_config().items():
        if isinstance(defaults, dict):
            config.setdefault(section, {})
            for key, value in defaults.items():
                config[section].setdefault(key, value)
    return config


def _records_with_scores(records: list[PerformanceRecord]) -> list[PerformanceRecord]:
    return [record for record in records if record.final_performance_score is not None]


def _average(records: list[PerformanceRecord]) -> float:
    if not records:
        return 0.0
    return sum(float(record.final_performance_score or 0.0) for record in records) / len(records)


def _groups(
    records: list[PerformanceRecord],
    key_func: Callable[[PerformanceRecord], str | None],
) -> dict[str, list[PerformanceRecord]]:
    grouped: dict[str, list[PerformanceRecord]] = {}
    for record in records:
        key = key_func(record)
        if not key:
            continue
        grouped.setdefault(str(key), []).append(record)
    return grouped


def _update_weight_group(
    config: dict,
    *,
    group_name: str,
    records: list[PerformanceRecord],
    key_func: Callable[[PerformanceRecord], str | None],
    global_average: float,
    tuning: OptimizerTuning,
) -> list[OptimizationChange]:
    changes: list[OptimizationChange] = []
    weights = config.setdefault("scoring", {}).setdefault(group_name, {})
    grouped = _groups(records, key_func)
    for key, group_records in sorted(grouped.items()):
        if len(group_records) < tuning.min_group_samples:
            continue
        group_average = _average(group_records)
        shrinkage_average = (
            (group_average * len(group_records)) + (global_average * tuning.min_group_samples)
        ) / (len(group_records) + tuning.min_group_samples)
        relative = shrinkage_average / global_average if global_average else 1.0
        delta = _clamp((relative - 1.0) * 0.4, -tuning.max_weight_change, tuning.max_weight_change)
        if abs(delta) < 0.01:
            continue
        old_weight = float(weights.get(key, 1.0))
        new_weight = round(_clamp(old_weight * (1.0 + delta), tuning.min_weight, tuning.max_weight), 4)
        if abs(new_weight - old_weight) < 0.0001:
            continue
        weights[key] = new_weight
        changes.append(
            OptimizationChange(
                path=f"scoring.{group_name}.{key}",
                old_value=old_weight,
                new_value=new_weight,
                reason="historical_performance_above_baseline" if delta > 0 else "historical_performance_below_baseline",
                samples=len(group_records),
                average_score=round(group_average, 4),
            )
        )
    return changes


def _update_threshold(
    config: dict,
    *,
    records: list[PerformanceRecord],
    run_history: list[dict],
    global_average: float,
    tuning: OptimizerTuning,
) -> list[OptimizationChange]:
    if len(run_history) < max(5, tuning.min_group_samples):
        return []
    scoring = config.setdefault("scoring", {})
    old_threshold = float(scoring.get("minimum_total_score", 50.0))
    recent = run_history[-tuning.recent_run_window :]
    published = [item for item in recent if item.get("status") == "published"]
    publish_rate = len(published) / len(recent) if recent else 0.0
    recent_records = records[-tuning.recent_run_window :]
    recent_average = _average(recent_records) if recent_records else global_average

    direction = 0.0
    reason = ""
    if publish_rate < 0.25:
        direction = -tuning.threshold_step
        reason = "too_few_posts_found"
    elif publish_rate > 0.9 and recent_records and recent_average < (global_average * 0.8):
        direction = tuning.threshold_step
        reason = "many_low_performing_posts"

    if direction == 0.0:
        return []
    new_threshold = round(_clamp(old_threshold + direction, tuning.min_threshold, tuning.max_threshold), 4)
    if new_threshold == old_threshold:
        return []
    scoring["minimum_total_score"] = new_threshold
    return [
        OptimizationChange(
            path="scoring.minimum_total_score",
            old_value=old_threshold,
            new_value=new_threshold,
            reason=reason,
            samples=len(recent),
            average_score=round(recent_average, 4) if recent_average else None,
        )
    ]


def save_optimized_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    config["version"] = 1
    config["generated_by"] = "meme_bot.optimizer"
    config["generated_at"] = utc_now_iso()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(config, handle, sort_keys=True, indent=2)
        handle.write("\n")
    tmp_path.replace(path)


def run(config: BotConfig | None = None) -> int:
    setup_logging()
    config = config or BotConfig.from_env()
    tuning_config = TuningConfig.from_path(config.optimization_config_path)
    if not tuning_config.optimizer.enabled:
        LOGGER.info("Self-optimization disabled; no config changes will be made")
        return 0

    store = load_performance_store(config.performance_store_path)
    scored_records = _records_with_scores(store.posts)
    if len(scored_records) < tuning_config.optimizer.min_total_samples:
        LOGGER.info(
            "Not enough performance samples for self-optimization: samples=%s required=%s",
            len(scored_records),
            tuning_config.optimizer.min_total_samples,
        )
        return 0

    generated = _ensure_config(tuning_config.raw)
    global_average = _average(scored_records)
    changes: list[OptimizationChange] = []
    changes.extend(
        _update_weight_group(
            generated,
            group_name="subreddit_weights",
            records=scored_records,
            key_func=lambda record: record.subreddit.lower(),
            global_average=global_average,
            tuning=tuning_config.optimizer,
        )
    )
    changes.extend(
        _update_weight_group(
            generated,
            group_name="posting_hour_weights",
            records=scored_records,
            key_func=lambda record: str(record.posting_hour_utc) if record.posting_hour_utc is not None else None,
            global_average=global_average,
            tuning=tuning_config.optimizer,
        )
    )
    changes.extend(
        _update_weight_group(
            generated,
            group_name="caption_template_weights",
            records=scored_records,
            key_func=lambda record: record.caption_template_id,
            global_average=global_average,
            tuning=tuning_config.optimizer,
        )
    )
    changes.extend(
        _update_weight_group(
            generated,
            group_name="hashtag_pool_weights",
            records=scored_records,
            key_func=lambda record: record.hashtag_pool_id,
            global_average=global_average,
            tuning=tuning_config.optimizer,
        )
    )
    changes.extend(
        _update_weight_group(
            generated,
            group_name="media_type_weights",
            records=scored_records,
            key_func=lambda record: record.media_type,
            global_average=global_average,
            tuning=tuning_config.optimizer,
        )
    )
    changes.extend(
        _update_weight_group(
            generated,
            group_name="duration_bucket_weights",
            records=scored_records,
            key_func=lambda record: duration_bucket(record.video_duration_seconds),
            global_average=global_average,
            tuning=tuning_config.optimizer,
        )
    )
    changes.extend(
        _update_threshold(
            generated,
            records=scored_records,
            run_history=load_run_history(config.run_history_path),
            global_average=global_average,
            tuning=tuning_config.optimizer,
        )
    )

    if not changes:
        LOGGER.info("Self-optimization complete: no config changes met safeguards")
        return 0

    save_optimized_config(config.optimization_config_path, generated)
    for change in changes:
        append_run_history(
            config.optimization_changelog_path,
            {
                "path": change.path,
                "old_value": change.old_value,
                "new_value": change.new_value,
                "reason": change.reason,
                "samples": change.samples,
                "average_score": change.average_score,
            },
        )
    LOGGER.info("Self-optimization updated config: changes=%s", [change.__dict__ for change in changes])
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
