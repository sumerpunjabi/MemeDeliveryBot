from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


DEFAULT_IMAGE_LISTING_MODES = ("hot", "rising", "new")
DEFAULT_REEL_LISTING_MODES = ("hot", "rising", "new")
LOGGER = logging.getLogger(__name__)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def _split_csv(value: str | None, default: Iterable[str]) -> list[str]:
    if not value:
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning(
            "Ignoring unreadable optimized config: path=%s error_class=%s",
            path,
            type(exc).__name__,
        )
        return {}
    return data if isinstance(data, dict) else {}


def _nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _number_map(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, raw in value.items():
        try:
            result[str(key)] = float(raw)
        except (TypeError, ValueError):
            continue
    return result


@dataclass(frozen=True)
class ScoringTuning:
    minimum_total_score: float = 35.0
    preferred_age_hours: float = 12.0
    max_age_hours: float = 48.0
    hot_age_hours: float = 6.0
    old_post_penalty: float = 30.0
    reddit_comment_weight: float = 1.0
    upvote_ratio_weight: float = 1.0
    title_weight: float = 1.0
    shareability_weight: float = 1.0
    quick_payoff_weight: float = 1.0
    discussion_weight: float = 1.0
    duplicate_risk_penalty: float = 20.0
    reel_soft_max_duration_seconds: int = 45
    reel_hard_max_duration_seconds: int = 90
    reel_preferred_duration_seconds: int = 20
    reel_min_width: int = 240
    reel_min_height: int = 240
    reel_min_aspect_ratio: float = 0.35
    reel_max_aspect_ratio: float = 3.0
    subreddit_weights: dict[str, float] = field(default_factory=dict)
    posting_hour_weights: dict[str, float] = field(default_factory=dict)
    caption_template_weights: dict[str, float] = field(default_factory=dict)
    hashtag_pool_weights: dict[str, float] = field(default_factory=dict)
    media_type_weights: dict[str, float] = field(default_factory=dict)
    duration_bucket_weights: dict[str, float] = field(default_factory=dict)
    paused_subreddits: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class CaptionTuning:
    recent_template_window: int = 5
    max_hashtags: int = 4


@dataclass(frozen=True)
class StorageTuning:
    max_posts: int = 1000
    max_age_days: int = 365
    max_snapshots_per_post: int = 8


@dataclass(frozen=True)
class AnalyticsTuning:
    lookback_days: int = 14
    max_media_per_run: int = 50
    metrics: list[str] = field(
        default_factory=lambda: [
            "likes",
            "comments",
            "saved",
            "shares",
            "reach",
            "views",
            "plays",
            "total_interactions",
            "follows",
        ]
    )


@dataclass(frozen=True)
class OptimizerTuning:
    enabled: bool = True
    min_total_samples: int = 20
    min_group_samples: int = 5
    max_weight_change: float = 0.15
    min_weight: float = 0.5
    max_weight: float = 1.5
    threshold_step: float = 3.0
    min_threshold: float = 20.0
    max_threshold: float = 85.0
    recent_run_window: int = 20


@dataclass(frozen=True)
class TuningConfig:
    scoring: ScoringTuning
    captions: CaptionTuning
    storage: StorageTuning
    analytics: AnalyticsTuning
    optimizer: OptimizerTuning
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_path(cls, path: Path) -> "TuningConfig":
        raw = _load_json(path)
        scoring = ScoringTuning(
            minimum_total_score=_get_float(
                "SCORING_MINIMUM_TOTAL_SCORE",
                float(_nested(raw, "scoring", "minimum_total_score") or 35.0),
            ),
            preferred_age_hours=_get_float(
                "SCORING_PREFERRED_AGE_HOURS",
                float(_nested(raw, "scoring", "preferred_age_hours") or 12.0),
            ),
            max_age_hours=_get_float(
                "SCORING_MAX_AGE_HOURS",
                float(_nested(raw, "scoring", "max_age_hours") or 48.0),
            ),
            hot_age_hours=_get_float(
                "SCORING_HOT_AGE_HOURS",
                float(_nested(raw, "scoring", "hot_age_hours") or 6.0),
            ),
            old_post_penalty=_get_float(
                "SCORING_OLD_POST_PENALTY",
                float(_nested(raw, "scoring", "old_post_penalty") or 30.0),
            ),
            reddit_comment_weight=_get_float(
                "SCORING_REDDIT_COMMENT_WEIGHT",
                float(_nested(raw, "scoring", "reddit_comment_weight") or 1.0),
            ),
            upvote_ratio_weight=_get_float(
                "SCORING_UPVOTE_RATIO_WEIGHT",
                float(_nested(raw, "scoring", "upvote_ratio_weight") or 1.0),
            ),
            title_weight=_get_float(
                "SCORING_TITLE_WEIGHT",
                float(_nested(raw, "scoring", "title_weight") or 1.0),
            ),
            shareability_weight=_get_float(
                "SCORING_SHAREABILITY_WEIGHT",
                float(_nested(raw, "scoring", "shareability_weight") or 1.0),
            ),
            quick_payoff_weight=_get_float(
                "SCORING_QUICK_PAYOFF_WEIGHT",
                float(_nested(raw, "scoring", "quick_payoff_weight") or 1.0),
            ),
            discussion_weight=_get_float(
                "SCORING_DISCUSSION_WEIGHT",
                float(_nested(raw, "scoring", "discussion_weight") or 1.0),
            ),
            duplicate_risk_penalty=_get_float(
                "SCORING_DUPLICATE_RISK_PENALTY",
                float(_nested(raw, "scoring", "duplicate_risk_penalty") or 20.0),
            ),
            reel_soft_max_duration_seconds=_get_int(
                "REEL_SOFT_MAX_DURATION_SECONDS",
                int(_nested(raw, "scoring", "reel_soft_max_duration_seconds") or 45),
            ),
            reel_hard_max_duration_seconds=_get_int(
                "REEL_HARD_MAX_DURATION_SECONDS",
                int(_nested(raw, "scoring", "reel_hard_max_duration_seconds") or 90),
            ),
            reel_preferred_duration_seconds=_get_int(
                "REEL_PREFERRED_DURATION_SECONDS",
                int(_nested(raw, "scoring", "reel_preferred_duration_seconds") or 20),
            ),
            reel_min_width=_get_int(
                "REEL_MIN_WIDTH",
                int(_nested(raw, "scoring", "reel_min_width") or 240),
            ),
            reel_min_height=_get_int(
                "REEL_MIN_HEIGHT",
                int(_nested(raw, "scoring", "reel_min_height") or 240),
            ),
            reel_min_aspect_ratio=_get_float(
                "REEL_MIN_ASPECT_RATIO",
                float(_nested(raw, "scoring", "reel_min_aspect_ratio") or 0.35),
            ),
            reel_max_aspect_ratio=_get_float(
                "REEL_MAX_ASPECT_RATIO",
                float(_nested(raw, "scoring", "reel_max_aspect_ratio") or 3.0),
            ),
            subreddit_weights=_number_map(_nested(raw, "scoring", "subreddit_weights")),
            posting_hour_weights=_number_map(_nested(raw, "scoring", "posting_hour_weights")),
            caption_template_weights=_number_map(_nested(raw, "scoring", "caption_template_weights")),
            hashtag_pool_weights=_number_map(_nested(raw, "scoring", "hashtag_pool_weights")),
            media_type_weights=_number_map(_nested(raw, "scoring", "media_type_weights")),
            duration_bucket_weights=_number_map(_nested(raw, "scoring", "duration_bucket_weights")),
            paused_subreddits={str(item).lower() for item in (_nested(raw, "scoring", "paused_subreddits") or [])},
        )
        captions = CaptionTuning(
            recent_template_window=_get_int(
                "CAPTION_RECENT_TEMPLATE_WINDOW",
                int(_nested(raw, "captions", "recent_template_window") or 5),
            ),
            max_hashtags=_get_int("CAPTION_MAX_HASHTAGS", int(_nested(raw, "captions", "max_hashtags") or 4)),
        )
        storage = StorageTuning(
            max_posts=_get_int("PERFORMANCE_MAX_POSTS", int(_nested(raw, "storage", "max_posts") or 1000)),
            max_age_days=_get_int("PERFORMANCE_MAX_AGE_DAYS", int(_nested(raw, "storage", "max_age_days") or 365)),
            max_snapshots_per_post=_get_int(
                "PERFORMANCE_MAX_SNAPSHOTS_PER_POST",
                int(_nested(raw, "storage", "max_snapshots_per_post") or 8),
            ),
        )
        analytics = AnalyticsTuning(
            lookback_days=_get_int("ANALYTICS_LOOKBACK_DAYS", int(_nested(raw, "analytics", "lookback_days") or 14)),
            max_media_per_run=_get_int(
                "ANALYTICS_MAX_MEDIA_PER_RUN",
                int(_nested(raw, "analytics", "max_media_per_run") or 50),
            ),
            metrics=_split_csv(
                os.getenv("INSTAGRAM_INSIGHT_METRICS"),
                _nested(raw, "analytics", "metrics")
                or [
                    "likes",
                    "comments",
                    "saved",
                    "shares",
                    "reach",
                    "views",
                    "plays",
                    "total_interactions",
                    "follows",
                ],
            ),
        )
        optimizer = OptimizerTuning(
            enabled=_get_bool("SELF_OPTIMIZATION_ENABLED", bool(_nested(raw, "optimizer", "enabled") is not False)),
            min_total_samples=_get_int(
                "OPTIMIZER_MIN_TOTAL_SAMPLES",
                int(_nested(raw, "optimizer", "min_total_samples") or 20),
            ),
            min_group_samples=_get_int(
                "OPTIMIZER_MIN_GROUP_SAMPLES",
                int(_nested(raw, "optimizer", "min_group_samples") or 5),
            ),
            max_weight_change=_get_float(
                "OPTIMIZER_MAX_WEIGHT_CHANGE",
                float(_nested(raw, "optimizer", "max_weight_change") or 0.15),
            ),
            min_weight=_get_float("OPTIMIZER_MIN_WEIGHT", float(_nested(raw, "optimizer", "min_weight") or 0.5)),
            max_weight=_get_float("OPTIMIZER_MAX_WEIGHT", float(_nested(raw, "optimizer", "max_weight") or 1.5)),
            threshold_step=_get_float(
                "OPTIMIZER_THRESHOLD_STEP",
                float(_nested(raw, "optimizer", "threshold_step") or 3.0),
            ),
            min_threshold=_get_float(
                "OPTIMIZER_MIN_THRESHOLD",
                float(_nested(raw, "optimizer", "min_threshold") or 20.0),
            ),
            max_threshold=_get_float(
                "OPTIMIZER_MAX_THRESHOLD",
                float(_nested(raw, "optimizer", "max_threshold") or 85.0),
            ),
            recent_run_window=_get_int(
                "OPTIMIZER_RECENT_RUN_WINDOW",
                int(_nested(raw, "optimizer", "recent_run_window") or 20),
            ),
        )
        return cls(scoring=scoring, captions=captions, storage=storage, analytics=analytics, optimizer=optimizer, raw=raw)


def default_optimized_config() -> dict[str, Any]:
    return {
        "version": 1,
        "generated_by": "meme_bot.optimizer",
        "scoring": {
            "minimum_total_score": 35.0,
            "preferred_age_hours": 12.0,
            "max_age_hours": 48.0,
            "reel_soft_max_duration_seconds": 45,
            "subreddit_weights": {},
            "posting_hour_weights": {},
            "caption_template_weights": {},
            "hashtag_pool_weights": {},
            "media_type_weights": {},
            "duration_bucket_weights": {},
            "paused_subreddits": [],
        },
        "captions": {"recent_template_window": 5, "max_hashtags": 4},
        "storage": {"max_posts": 1000, "max_age_days": 365, "max_snapshots_per_post": 8},
        "analytics": {
            "lookback_days": 14,
            "max_media_per_run": 50,
            "metrics": ["likes", "comments", "saved", "shares", "reach", "views", "plays", "total_interactions", "follows"],
        },
        "optimizer": {
            "enabled": True,
            "min_total_samples": 20,
            "min_group_samples": 5,
            "max_weight_change": 0.15,
            "min_weight": 0.5,
            "max_weight": 1.5,
            "threshold_step": 3.0,
            "min_threshold": 20.0,
            "max_threshold": 85.0,
            "recent_run_window": 20,
        },
    }
