from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlsplit

from .config import BotConfig

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


def _reddit_permalink(submission: Any) -> str:
    permalink = str(getattr(submission, "permalink", "") or "")
    if permalink.startswith("http://") or permalink.startswith("https://"):
        return permalink
    if permalink:
        return f"https://www.reddit.com{permalink}"
    return str(getattr(submission, "url", "") or "")


def reel_rejection_reason(
    submission: Any,
    *,
    min_score: int = 0,
    max_duration_seconds: int = 90,
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

    duration_seconds = _duration_seconds(submission)
    if duration_seconds is not None and duration_seconds < MIN_REEL_DURATION_SECONDS:
        return "too_short"
    if duration_seconds is not None and duration_seconds > max_duration_seconds:
        return "too_long"

    return None


def is_reel_submission(
    submission: Any,
    *,
    min_score: int = 0,
    max_duration_seconds: int = 90,
    use_saved_guard: bool = False,
) -> bool:
    return (
        reel_rejection_reason(
            submission,
            min_score=min_score,
            max_duration_seconds=max_duration_seconds,
            use_saved_guard=use_saved_guard,
        )
        is None
    )


def to_reel_candidate(submission: Any) -> ReelCandidate:
    return ReelCandidate(
        reddit_id=str(getattr(submission, "id")),
        title=str(getattr(submission, "title", "")),
        source_url=str(getattr(submission, "url", "")),
        reddit_permalink=_reddit_permalink(submission),
        subreddit=str(getattr(getattr(submission, "subreddit", ""), "display_name", getattr(submission, "subreddit", ""))),
        score=int(getattr(submission, "score", 0) or 0),
        duration_seconds=_duration_seconds(submission),
        saved=bool(getattr(submission, "saved", False)),
        submission=submission,
    )


def fetch_reel_candidates(reddit: Any, config: BotConfig) -> list[ReelCandidate]:
    candidates: list[ReelCandidate] = []
    for subreddit_name in config.reel_subreddits:
        LOGGER.info("Scanning subreddit for reels: subreddit=%s", subreddit_name)
        seen_count = 0
        accepted_count = 0
        rejection_counts: dict[str, int] = {}
        try:
            subreddit = reddit.subreddit(subreddit_name)
            submissions: Iterable[Any] = subreddit.top(config.reel_post_time_filter, limit=config.reel_post_limit)
            for submission in submissions:
                seen_count += 1
                reason = reel_rejection_reason(
                    submission,
                    min_score=config.reel_min_score,
                    max_duration_seconds=config.reel_max_duration_seconds,
                    use_saved_guard=config.use_reddit_saved_guard,
                )
                if reason is None:
                    accepted_count += 1
                    candidates.append(to_reel_candidate(submission))
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
