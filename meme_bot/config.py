from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
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


@dataclass(frozen=True)
class BotConfig:
    access_token: str | None
    instagram_account_id: str | None
    reddit_client_id: str | None
    reddit_client_secret: str | None
    reddit_user_agent: str | None
    reddit_username: str | None
    reddit_password: str | None
    fb_app_id: str | None
    fb_app_secret: str | None
    subreddits: list[str]
    post_time_filter: str
    post_limit: int
    min_score: int
    tracker_path: Path
    graph_domain: str
    graph_version: str
    request_timeout_seconds: float
    max_retry_attempts: int
    retry_base_seconds: float
    refresh_threshold_days: int
    dry_run: bool
    use_reddit_saved_guard: bool
    mark_reddit_saved: bool
    reel_subreddits: list[str] = field(default_factory=lambda: ["memes"])
    reel_post_time_filter: str = "day"
    reel_post_limit: int = 100
    reel_min_score: int = 0
    reel_tracker_path: Path = Path("state/reels-posted.jsonl")
    reel_max_duration_seconds: int = 90
    reel_max_bytes: int = 100_000_000
    reel_share_to_feed: bool = True
    reels_dry_run: bool = False

    @classmethod
    def from_env(cls) -> "BotConfig":
        subreddits = _split_csv(os.getenv("SUBREDDITS"), ["memes"])
        post_time_filter = os.getenv("POST_TIME_FILTER", "day")
        post_limit = _get_int("POST_LIMIT", 100)
        min_score = _get_int("MIN_SCORE", 0)
        dry_run = _get_bool("DRY_RUN", False)
        return cls(
            access_token=os.getenv("ACCESS_TOKEN"),
            instagram_account_id=os.getenv("INSTAGRAM_ACCOUNT_ID"),
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            reddit_user_agent=os.getenv("REDDIT_USER_AGENT"),
            reddit_username=os.getenv("REDDIT_USERNAME"),
            reddit_password=os.getenv("REDDIT_PASSWORD"),
            fb_app_id=os.getenv("FB_APP_ID"),
            fb_app_secret=os.getenv("FB_APP_SECRET"),
            subreddits=subreddits,
            post_time_filter=post_time_filter,
            post_limit=post_limit,
            min_score=min_score,
            tracker_path=Path(os.getenv("TRACKER_PATH", "state/posted.jsonl")),
            graph_domain=os.getenv("GRAPH_DOMAIN", "https://graph.facebook.com"),
            graph_version=os.getenv("GRAPH_VERSION", "v22.0"),
            request_timeout_seconds=_get_float("REQUEST_TIMEOUT_SECONDS", 20.0),
            max_retry_attempts=_get_int("MAX_RETRY_ATTEMPTS", 3),
            retry_base_seconds=_get_float("RETRY_BASE_SECONDS", 2.0),
            refresh_threshold_days=_get_int("REFRESH_THRESHOLD_DAYS", 21),
            dry_run=dry_run,
            use_reddit_saved_guard=_get_bool("USE_REDDIT_SAVED_GUARD", False),
            mark_reddit_saved=_get_bool("MARK_REDDIT_SAVED", False),
            reel_subreddits=_split_csv(os.getenv("REEL_SUBREDDITS"), subreddits),
            reel_post_time_filter=os.getenv("REEL_POST_TIME_FILTER", "day"),
            reel_post_limit=_get_int("REEL_POST_LIMIT", 100),
            reel_min_score=_get_int("REEL_MIN_SCORE", min_score),
            reel_tracker_path=Path(os.getenv("REEL_TRACKER_PATH", "state/reels-posted.jsonl")),
            reel_max_duration_seconds=_get_int("REEL_MAX_DURATION_SECONDS", 90),
            reel_max_bytes=_get_int("REEL_MAX_BYTES", 100_000_000),
            reel_share_to_feed=_get_bool("REEL_SHARE_TO_FEED", False),
            reels_dry_run=_get_bool("REELS_DRY_RUN", dry_run),
        )

    @property
    def endpoint_base(self) -> str:
        return f"{self.graph_domain.rstrip('/')}/{self.graph_version}"

    def validate_for_reddit(self) -> None:
        missing = [
            name
            for name, value in {
                "REDDIT_CLIENT_ID": self.reddit_client_id,
                "REDDIT_CLIENT_SECRET": self.reddit_client_secret,
                "REDDIT_USER_AGENT": self.reddit_user_agent,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required Reddit configuration: {', '.join(missing)}")

    def validate_for_instagram(self, dry_run: bool | None = None) -> None:
        effective_dry_run = self.dry_run if dry_run is None else dry_run
        if effective_dry_run:
            return
        missing = [
            name
            for name, value in {
                "ACCESS_TOKEN": self.access_token,
                "INSTAGRAM_ACCOUNT_ID": self.instagram_account_id,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required Instagram configuration: {', '.join(missing)}")

    def validate_for_token_refresh(self) -> None:
        missing = [
            name
            for name, value in {
                "ACCESS_TOKEN": self.access_token,
                "FB_APP_ID": self.fb_app_id,
                "FB_APP_SECRET": self.fb_app_secret,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required token refresh configuration: {', '.join(missing)}")
