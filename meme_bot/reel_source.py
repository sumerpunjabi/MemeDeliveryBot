from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urlsplit

from .config import BotConfig
from .reddit_source import RedditComment, fetch_top_comments, reddit_permalink

LOGGER = logging.getLogger(__name__)

MIN_REEL_DURATION_SECONDS = 3
SUPPORTED_VIDEO_DOMAINS = {"v.redd.it"}


@dataclass(frozen=True)
class ReelCandidate:
    reddit_id: str
    title: str
    source_url: str
    reddit_permalink: str
    subreddit: str
    score: int
    duration_seconds: int | None
    saved: bool
    media_url: str | None = None
    created_utc: float | None = None
    upvote_ratio: float | None = None
    num_comments: int = 0
    width: int | None = None
    height: int | None = None
    top_comments: tuple[RedditComment, ...] = field(default_factory=tuple)
    submission: Any = None


def _reddit_video(submission: Any) -> dict[str, Any] | None:
    for media_attr in ("secure_media", "media"):
        media = getattr(submission, media_attr, None)
        if isinstance(media, dict) and isinstance(media.get("reddit_video"), dict):
            return media["reddit_video"]
    return None


def _duration_seconds(submission: Any) -> int | None:
    reddit_video = _reddit_video(submission)
    if not reddit_video:
        return None
    duration = reddit_video.get("duration")
    if duration is None:
        return None
    try:
        return int(duration)
    except (TypeError, ValueError):
        return None


def _video_int(submission: Any, key: str) -> int | None:
    reddit_video = _reddit_video(submission)
    if not reddit_video:
        return None
    value = reddit_video.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _reddit_video_url(submission: Any) -> str | None:
    reddit_video = _reddit_video(submission)
    if not reddit_video:
        return None
    for key in ("hls_url", "dash_url", "fallback_url"):
        value = reddit_video.get(key)
        if value:
            return str(value)
    return None


def _reddit_permalink(submission: Any) -> str:
    return reddit_permalink(submission)


def reel_rejection_reason(
    submission: Any,
    *,
    min_score: int = 0,
    max_duration_seconds: int = 90,
    min_width: int = 240,
    min_height: int = 240,
    min_aspect_ratio: float = 0.35,
    max_aspect_ratio: float = 3.0,
    use_saved_guard: bool = False,
) -> str | None:
    url = str(getattr(submission, "url", "") or "")
    domain = urlsplit(url).netloc.lower()

    if not url or domain not in SUPPORTED_VIDEO_DOMAINS:
        return "unsupported_domain"
    if getattr(submission, "stickied", False):
        return "stickied"
    if getattr(submission, "over_18", False):
        return "nsfw"
    if getattr(submission, "spoiler", False):
        return "spoiler"
    if getattr(submission, "is_gallery", False):
        return "gallery"
    if int(getattr(submission, "score", 0) or 0) < min_score:
        return "low_score"
    if use_saved_guard and bool(getattr(submission, "saved", False)):
        return "saved"

    post_hint = getattr(submission, "post_hint", None)
    is_video = bool(getattr(submission, "is_video", False))
    if post_hint and post_hint != "hosted:video":
        return f"post_hint_{post_hint}"
    if not is_video and post_hint != "hosted:video":
        return "not_video"
    if not _reddit_video_url(submission):
        return "missing_video_url"

    duration_seconds = _duration_seconds(submission)
    if duration_seconds is not None and duration_seconds < MIN_REEL_DURATION_SECONDS:
        return "too_short"
    if duration_seconds is not None and duration_seconds > max_duration_seconds:
        return "too_long"
    width = _video_int(submission, "width")
    height = _video_int(submission, "height")
    if width is not None and height is not None:
        if width < min_width or height < min_height:
            return "low_resolution"
        aspect_ratio = width / height if height else 0
        if aspect_ratio < min_aspect_ratio or aspect_ratio > max_aspect_ratio:
            return "weird_aspect_ratio"

    return None


def is_reel_submission(
    submission: Any,
    *,
    min_score: int = 0,
    max_duration_seconds: int = 90,
    min_width: int = 240,
    min_height: int = 240,
    min_aspect_ratio: float = 0.35,
    max_aspect_ratio: float = 3.0,
    use_saved_guard: bool = False,
) -> bool:
    return (
        reel_rejection_reason(
            submission,
            min_score=min_score,
            max_duration_seconds=max_duration_seconds,
            min_width=min_width,
            min_height=min_height,
            min_aspect_ratio=min_aspect_ratio,
            max_aspect_ratio=max_aspect_ratio,
            use_saved_guard=use_saved_guard,
        )
        is None
    )


def to_reel_candidate(submission: Any, comments_limit: int = 5) -> ReelCandidate:
    return ReelCandidate(
        reddit_id=str(getattr(submission, "id")),
        title=str(getattr(submission, "title", "")),
        source_url=str(getattr(submission, "url", "")),
        reddit_permalink=_reddit_permalink(submission),
        subreddit=str(getattr(getattr(submission, "subreddit", ""), "display_name", getattr(submission, "subreddit", ""))),
        score=int(getattr(submission, "score", 0) or 0),
        duration_seconds=_duration_seconds(submission),
        saved=bool(getattr(submission, "saved", False)),
        media_url=_reddit_video_url(submission),
        created_utc=float(getattr(submission, "created_utc", 0) or 0) or None,
        upvote_ratio=(
            float(getattr(submission, "upvote_ratio")) if getattr(submission, "upvote_ratio", None) is not None else None
        ),
        num_comments=int(getattr(submission, "num_comments", 0) or 0),
        width=_video_int(submission, "width"),
        height=_video_int(submission, "height"),
        top_comments=fetch_top_comments(submission, limit=comments_limit),
        submission=submission,
    )


def _listing(subreddit: Any, mode: str, *, time_filter: str, limit: int) -> Iterable[Any]:
    normalized = mode.strip().lower()
    if normalized == "top" and hasattr(subreddit, "top"):
        return subreddit.top(time_filter, limit=limit)
    if normalized == "hot" and hasattr(subreddit, "hot"):
        return subreddit.hot(limit=limit)
    if normalized == "rising" and hasattr(subreddit, "rising"):
        return subreddit.rising(limit=limit)
    if normalized in {"new", "recent"} and hasattr(subreddit, "new"):
        return subreddit.new(limit=limit)
    LOGGER.warning("Skipping unknown Reddit listing mode for reels: mode=%s", mode)
    return ()


def fetch_reel_candidates(reddit: Any, config: BotConfig) -> list[ReelCandidate]:
    candidates: list[ReelCandidate] = []
    seen_ids: set[str] = set()
    listing_modes = list(getattr(config, "reel_listing_modes", None) or ["top"])
    comments_limit = int(getattr(config, "top_comments_limit", 5) or 0)
    for subreddit_name in config.reel_subreddits:
        LOGGER.info("Scanning subreddit for reels: subreddit=%s", subreddit_name)
        seen_count = 0
        accepted_count = 0
        rejection_counts: dict[str, int] = {}
        try:
            subreddit = reddit.subreddit(subreddit_name)
            for mode in listing_modes:
                submissions = _listing(
                    subreddit,
                    mode,
                    time_filter=config.reel_post_time_filter,
                    limit=config.reel_post_limit,
                )
                for submission in submissions:
                    seen_count += 1
                    reddit_id = str(getattr(submission, "id", "") or "")
                    if reddit_id and reddit_id in seen_ids:
                        rejection_counts["duplicate_listing"] = rejection_counts.get("duplicate_listing", 0) + 1
                        continue
                    reason = reel_rejection_reason(
                        submission,
                        min_score=config.reel_min_score,
                        max_duration_seconds=config.reel_max_duration_seconds,
                        min_width=int(getattr(config, "reel_min_width", 240) or 240),
                        min_height=int(getattr(config, "reel_min_height", 240) or 240),
                        min_aspect_ratio=float(getattr(config, "reel_min_aspect_ratio", 0.35) or 0.35),
                        max_aspect_ratio=float(getattr(config, "reel_max_aspect_ratio", 3.0) or 3.0),
                        use_saved_guard=config.use_reddit_saved_guard,
                    )
                    if reason is None:
                        seen_ids.add(reddit_id)
                        accepted_count += 1
                        candidates.append(to_reel_candidate(submission, comments_limit=comments_limit))
                    else:
                        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        except Exception as exc:
            LOGGER.warning(
                "Skipping subreddit after Reddit API error: subreddit=%s error_class=%s error=%s",
                subreddit_name,
                type(exc).__name__,
                exc,
            )
        finally:
            LOGGER.info(
                "Subreddit reel scan result: subreddit=%s seen=%s accepted=%s rejections=%s",
                subreddit_name,
                seen_count,
                accepted_count,
                rejection_counts,
            )

    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates
