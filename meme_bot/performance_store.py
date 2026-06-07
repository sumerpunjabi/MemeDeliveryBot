from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .tracker import normalize_image_url, utc_now_iso

LOGGER = logging.getLogger(__name__)
STORE_VERSION = 1


def normalize_title(title: str) -> str:
    lowered = title.casefold()
    lowered = re.sub(r"https?://\S+", " ", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def posting_parts(posted_at: str) -> tuple[int | None, str | None]:
    parsed = parse_utc(posted_at)
    if parsed is None:
        return None, None
    return parsed.hour, parsed.strftime("%A").lower()


def duration_bucket(duration_seconds: float | int | None) -> str:
    if duration_seconds is None:
        return "unknown"
    if duration_seconds <= 15:
        return "0-15s"
    if duration_seconds <= 30:
        return "16-30s"
    if duration_seconds <= 45:
        return "31-45s"
    if duration_seconds <= 60:
        return "46-60s"
    return "60s+"


@dataclass
class PerformanceRecord:
    reddit_id: str
    reddit_url: str
    source_url: str
    media_url: str | None
    media_hash: str | None
    title: str
    normalized_title: str
    subreddit: str
    media_type: str
    instagram_media_id: str | None
    instagram_permalink: str | None
    posted_at: str
    posting_hour_utc: int | None
    posting_weekday_utc: str | None
    generated_score: float
    score_breakdown: dict[str, float]
    score_rejections: list[str]
    caption_template_id: str
    hashtag_pool_id: str
    hashtags: list[str]
    video_duration_seconds: float | None = None
    latest_metrics: dict[str, float] = field(default_factory=dict)
    unavailable_metrics: list[str] = field(default_factory=list)
    metric_snapshots: list[dict[str, Any]] = field(default_factory=list)
    final_performance_score: float | None = None
    last_metrics_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PerformanceRecord":
        posted_at = str(data.get("posted_at") or "")
        posting_hour, posting_weekday = posting_parts(posted_at)
        raw_breakdown = data.get("score_breakdown") if isinstance(data.get("score_breakdown"), dict) else {}
        score_breakdown: dict[str, float] = {}
        for key, value in raw_breakdown.items():
            try:
                score_breakdown[str(key)] = float(value)
            except (TypeError, ValueError):
                continue

        return cls(
            reddit_id=str(data.get("reddit_id") or ""),
            reddit_url=str(data.get("reddit_url") or data.get("reddit_permalink") or ""),
            source_url=str(data.get("source_url") or data.get("image_url") or ""),
            media_url=str(data["media_url"]) if data.get("media_url") else None,
            media_hash=str(data["media_hash"]) if data.get("media_hash") else data.get("image_hash") or data.get("video_hash"),
            title=str(data.get("title") or ""),
            normalized_title=str(data.get("normalized_title") or normalize_title(str(data.get("title") or ""))),
            subreddit=str(data.get("subreddit") or ""),
            media_type=str(data.get("media_type") or "image"),
            instagram_media_id=str(data["instagram_media_id"]) if data.get("instagram_media_id") else None,
            instagram_permalink=str(data["instagram_permalink"]) if data.get("instagram_permalink") else None,
            posted_at=posted_at,
            posting_hour_utc=data.get("posting_hour_utc") if isinstance(data.get("posting_hour_utc"), int) else posting_hour,
            posting_weekday_utc=str(data.get("posting_weekday_utc") or posting_weekday or ""),
            generated_score=float(data.get("generated_score") or data.get("score") or 0.0),
            score_breakdown=score_breakdown,
            score_rejections=[str(item) for item in data.get("score_rejections", []) if item],
            caption_template_id=str(data.get("caption_template_id") or ""),
            hashtag_pool_id=str(data.get("hashtag_pool_id") or ""),
            hashtags=[str(item) for item in data.get("hashtags", []) if item],
            video_duration_seconds=(
                float(data["video_duration_seconds"]) if data.get("video_duration_seconds") is not None else None
            ),
            latest_metrics={
                str(key): float(value)
                for key, value in (data.get("latest_metrics") or {}).items()
                if isinstance(value, (int, float))
            },
            unavailable_metrics=[str(item) for item in data.get("unavailable_metrics", []) if item],
            metric_snapshots=list(data.get("metric_snapshots") or []),
            final_performance_score=(
                float(data["final_performance_score"]) if data.get("final_performance_score") is not None else None
            ),
            last_metrics_at=str(data["last_metrics_at"]) if data.get("last_metrics_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "reddit_id": self.reddit_id,
            "reddit_url": self.reddit_url,
            "source_url": normalize_image_url(self.source_url) if self.source_url else "",
            "media_url": normalize_image_url(self.media_url) if self.media_url else None,
            "media_hash": self.media_hash,
            "title": self.title,
            "normalized_title": self.normalized_title,
            "subreddit": self.subreddit,
            "media_type": self.media_type,
            "instagram_media_id": self.instagram_media_id,
            "instagram_permalink": self.instagram_permalink,
            "posted_at": self.posted_at,
            "posting_hour_utc": self.posting_hour_utc,
            "posting_weekday_utc": self.posting_weekday_utc,
            "generated_score": round(self.generated_score, 4),
            "score_breakdown": {key: round(value, 4) for key, value in sorted(self.score_breakdown.items())},
            "score_rejections": list(self.score_rejections),
            "caption_template_id": self.caption_template_id,
            "hashtag_pool_id": self.hashtag_pool_id,
            "hashtags": list(self.hashtags),
            "video_duration_seconds": self.video_duration_seconds,
            "latest_metrics": {key: round(value, 4) for key, value in sorted(self.latest_metrics.items())},
            "unavailable_metrics": sorted(set(self.unavailable_metrics)),
            "metric_snapshots": list(self.metric_snapshots),
            "final_performance_score": (
                round(self.final_performance_score, 4) if self.final_performance_score is not None else None
            ),
            "last_metrics_at": self.last_metrics_at,
        }
        return {key: value for key, value in payload.items() if value not in (None, "", [])}


@dataclass
class PerformanceStore:
    posts: list[PerformanceRecord] = field(default_factory=list)
    version: int = STORE_VERSION
    meta: dict[str, Any] = field(default_factory=dict)

    def by_instagram_id(self) -> dict[str, PerformanceRecord]:
        return {record.instagram_media_id: record for record in self.posts if record.instagram_media_id}


@dataclass(frozen=True)
class DuplicateResult:
    is_duplicate: bool
    reasons: list[str]


@dataclass(frozen=True)
class PerformanceIndex:
    reddit_ids: set[str]
    reddit_urls: set[str]
    source_urls: set[str]
    media_urls: set[str]
    permalinks: set[str]
    normalized_titles: set[str]
    media_hashes: set[str]

    def duplicate_reasons(
        self,
        *,
        reddit_id: str,
        reddit_url: str = "",
        source_url: str = "",
        media_url: str | None = None,
        title: str = "",
        media_hash: str | None = None,
    ) -> list[str]:
        reasons: list[str] = []
        if reddit_id and reddit_id in self.reddit_ids:
            reasons.append("reddit_id")
        if reddit_url and normalize_image_url(reddit_url) in self.reddit_urls:
            reasons.append("reddit_url")
        if source_url and normalize_image_url(source_url) in self.source_urls:
            reasons.append("source_url")
        if media_url and normalize_image_url(media_url) in self.media_urls:
            reasons.append("media_url")
        if reddit_url and normalize_image_url(reddit_url) in self.permalinks:
            reasons.append("permalink")
        normalized = normalize_title(title)
        if normalized and normalized in self.normalized_titles:
            reasons.append("normalized_title")
        if media_hash and media_hash in self.media_hashes:
            reasons.append("media_hash")
        return reasons

    def contains(
        self,
        *,
        reddit_id: str,
        reddit_url: str = "",
        source_url: str = "",
        media_url: str | None = None,
        title: str = "",
        media_hash: str | None = None,
    ) -> bool:
        return bool(
            self.duplicate_reasons(
                reddit_id=reddit_id,
                reddit_url=reddit_url,
                source_url=source_url,
                media_url=media_url,
                title=title,
                media_hash=media_hash,
            )
        )


def build_performance_index(records: Iterable[PerformanceRecord]) -> PerformanceIndex:
    reddit_ids: set[str] = set()
    reddit_urls: set[str] = set()
    source_urls: set[str] = set()
    media_urls: set[str] = set()
    permalinks: set[str] = set()
    normalized_titles: set[str] = set()
    media_hashes: set[str] = set()
    for record in records:
        if record.reddit_id:
            reddit_ids.add(record.reddit_id)
        if record.reddit_url:
            reddit_urls.add(normalize_image_url(record.reddit_url))
            permalinks.add(normalize_image_url(record.reddit_url))
        if record.source_url:
            source_urls.add(normalize_image_url(record.source_url))
        if record.media_url:
            media_urls.add(normalize_image_url(record.media_url))
        if record.normalized_title:
            normalized_titles.add(record.normalized_title)
        if record.media_hash:
            media_hashes.add(record.media_hash)
    return PerformanceIndex(
        reddit_ids=reddit_ids,
        reddit_urls=reddit_urls,
        source_urls=source_urls,
        media_urls=media_urls,
        permalinks=permalinks,
        normalized_titles=normalized_titles,
        media_hashes=media_hashes,
    )


def load_performance_store(path: Path) -> PerformanceStore:
    if not path.exists():
        return PerformanceStore()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Ignoring unreadable performance store: path=%s error_class=%s", path, type(exc).__name__)
        return PerformanceStore()

    if isinstance(data, list):
        return PerformanceStore(posts=[PerformanceRecord.from_dict(item) for item in data if isinstance(item, dict)])
    if not isinstance(data, dict):
        return PerformanceStore()
    posts = [PerformanceRecord.from_dict(item) for item in data.get("posts", []) if isinstance(item, dict)]
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    return PerformanceStore(posts=posts, version=int(data.get("version") or STORE_VERSION), meta=meta)


def save_performance_store(path: Path, store: PerformanceStore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": STORE_VERSION,
        "meta": {**store.meta, "updated_at": utc_now_iso()},
        "posts": [record.to_dict() for record in store.posts],
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    tmp_path.replace(path)


def prune_performance_store(
    store: PerformanceStore,
    *,
    max_posts: int,
    max_age_days: int,
    max_snapshots_per_post: int,
    now: datetime | None = None,
) -> PerformanceStore:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    kept: list[PerformanceRecord] = []
    for record in sorted(store.posts, key=lambda item: item.posted_at, reverse=True):
        posted_at = parse_utc(record.posted_at)
        if posted_at is not None and posted_at < cutoff:
            continue
        if len(record.metric_snapshots) > max_snapshots_per_post:
            record.metric_snapshots = record.metric_snapshots[-max_snapshots_per_post:]
        kept.append(record)
        if len(kept) >= max_posts:
            break
    kept.sort(key=lambda item: item.posted_at)
    return PerformanceStore(posts=kept, version=STORE_VERSION, meta=store.meta)


def append_or_replace_record(store: PerformanceStore, record: PerformanceRecord) -> None:
    for index, existing in enumerate(store.posts):
        if existing.reddit_id == record.reddit_id or (
            existing.instagram_media_id and existing.instagram_media_id == record.instagram_media_id
        ):
            store.posts[index] = record
            return
    store.posts.append(record)


def append_run_history(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    full_payload = {"created_at": utc_now_iso(), **payload}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(full_payload, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def load_run_history(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                records.append(data)
    if limit is not None:
        return records[-limit:]
    return records


def calculate_performance_score(metrics: dict[str, float]) -> float:
    likes = float(metrics.get("likes", 0.0))
    comments = float(metrics.get("comments", 0.0))
    saves = float(metrics.get("saved", metrics.get("saves", 0.0)))
    shares = float(metrics.get("shares", 0.0))
    follows = float(metrics.get("follows", metrics.get("follower_changes", 0.0)))
    denominator = max(
        float(metrics.get("reach", 0.0)),
        float(metrics.get("views", 0.0)),
        float(metrics.get("plays", 0.0)),
        100.0,
    )
    weighted = likes + (6.0 * comments) + (8.0 * saves) + (10.0 * shares) + (15.0 * follows)
    return round((weighted / denominator) * 1000.0, 4)
