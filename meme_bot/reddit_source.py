from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlsplit

from .config import BotConfig

LOGGER = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
REJECTED_DOMAINS = {"v.redd.it", "redgifs.com", "www.redgifs.com", "gfycat.com", "www.gfycat.com"}


@dataclass(frozen=True)
class RedditComment:
    body: str
    score: int = 0


@dataclass(frozen=True)
class ImageCandidate:
    reddit_id: str
    title: str
    image_url: str
    subreddit: str
    score: int
    saved: bool
    created_utc: float | None = None
    upvote_ratio: float | None = None
    num_comments: int = 0
    reddit_permalink: str = ""
    top_comments: tuple[RedditComment, ...] = field(default_factory=tuple)
    submission: Any = None


def create_reddit(config: BotConfig) -> Any:
    config.validate_for_reddit()
    import praw

    kwargs: dict[str, str] = {
        "client_id": config.reddit_client_id or "",
        "client_secret": config.reddit_client_secret or "",
        "user_agent": config.reddit_user_agent or "",
    }
    if config.reddit_username and config.reddit_password:
        kwargs["username"] = config.reddit_username
        kwargs["password"] = config.reddit_password
    return praw.Reddit(**kwargs)


def _has_supported_extension(url: str) -> bool:
    parsed = urlsplit(url)
    suffix = PurePosixPath(parsed.path).suffix.lower()
    return suffix in SUPPORTED_IMAGE_EXTENSIONS


def reddit_permalink(submission: Any) -> str:
    permalink = str(getattr(submission, "permalink", "") or "")
    if permalink.startswith("http://") or permalink.startswith("https://"):
        return permalink
    if permalink:
        return f"https://www.reddit.com{permalink}"
    return str(getattr(submission, "url", "") or "")


def fetch_top_comments(submission: Any, limit: int = 5) -> tuple[RedditComment, ...]:
    if limit <= 0:
        return ()
    comments = getattr(submission, "comments", None)
    if comments is None:
        return ()
    try:
        if hasattr(comments, "replace_more"):
            comments.replace_more(limit=0)
        iterable = comments.list() if hasattr(comments, "list") else comments
        parsed: list[RedditComment] = []
        for comment in iterable:
            body = str(getattr(comment, "body", "") or "").strip()
            if not body or body in {"[deleted]", "[removed]"}:
                continue
            parsed.append(RedditComment(body=body[:300], score=int(getattr(comment, "score", 0) or 0)))
        parsed.sort(key=lambda item: item.score, reverse=True)
        return tuple(parsed[:limit])
    except Exception as exc:
        LOGGER.debug(
            "Could not fetch top comments for Reddit submission",
            extra={"reddit_id": getattr(submission, "id", ""), "error_class": type(exc).__name__},
        )
        return ()


def is_image_submission(submission: Any, min_score: int = 0, use_saved_guard: bool = False) -> bool:
    return rejection_reason(submission, min_score=min_score, use_saved_guard=use_saved_guard) is None


def rejection_reason(submission: Any, min_score: int = 0, use_saved_guard: bool = False) -> str | None:
    url = str(getattr(submission, "url", "") or "")
    parsed = urlsplit(url)
    domain = parsed.netloc.lower()

    if not url or domain in REJECTED_DOMAINS:
        return "unsupported_domain"
    if getattr(submission, "stickied", False):
        return "stickied"
    if getattr(submission, "over_18", False):
        return "nsfw"
    if getattr(submission, "spoiler", False):
        return "spoiler"
    if getattr(submission, "is_video", False):
        return "video"
    if getattr(submission, "is_gallery", False):
        return "gallery"
    if "/gallery/" in url:
        return "gallery_url"
    if int(getattr(submission, "score", 0) or 0) < min_score:
        return "low_score"
    if use_saved_guard and bool(getattr(submission, "saved", False)):
        return "saved"

    post_hint = getattr(submission, "post_hint", None)
    if post_hint and post_hint != "image":
        return f"post_hint_{post_hint}"

    if not _has_supported_extension(url):
        return "unsupported_extension"

    return None


def to_candidate(submission: Any, comments_limit: int = 5) -> ImageCandidate:
    return ImageCandidate(
        reddit_id=str(getattr(submission, "id")),
        title=str(getattr(submission, "title", "")),
        image_url=str(getattr(submission, "url", "")),
        subreddit=str(getattr(getattr(submission, "subreddit", ""), "display_name", getattr(submission, "subreddit", ""))),
        score=int(getattr(submission, "score", 0) or 0),
        saved=bool(getattr(submission, "saved", False)),
        created_utc=float(getattr(submission, "created_utc", 0) or 0) or None,
        upvote_ratio=(
            float(getattr(submission, "upvote_ratio")) if getattr(submission, "upvote_ratio", None) is not None else None
        ),
        num_comments=int(getattr(submission, "num_comments", 0) or 0),
        reddit_permalink=reddit_permalink(submission),
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
    LOGGER.warning("Skipping unknown Reddit listing mode: mode=%s", mode)
    return ()


def fetch_image_candidates(reddit: Any, config: BotConfig) -> list[ImageCandidate]:
    candidates: list[ImageCandidate] = []
    seen_ids: set[str] = set()
    listing_modes = list(getattr(config, "image_listing_modes", None) or ["top"])
    comments_limit = int(getattr(config, "top_comments_limit", 5) or 0)
    for subreddit_name in config.subreddits:
        LOGGER.info("Scanning subreddit: subreddit=%s", subreddit_name)
        seen_count = 0
        accepted_count = 0
        rejection_counts: dict[str, int] = {}
        try:
            subreddit = reddit.subreddit(subreddit_name)
            for mode in listing_modes:
                submissions = _listing(subreddit, mode, time_filter=config.post_time_filter, limit=config.post_limit)
                for submission in submissions:
                    seen_count += 1
                    reddit_id = str(getattr(submission, "id", "") or "")
                    if reddit_id and reddit_id in seen_ids:
                        rejection_counts["duplicate_listing"] = rejection_counts.get("duplicate_listing", 0) + 1
                        continue
                    reason = rejection_reason(
                        submission,
                        min_score=config.min_score,
                        use_saved_guard=config.use_reddit_saved_guard,
                    )
                    if reason is None:
                        seen_ids.add(reddit_id)
                        accepted_count += 1
                        candidates.append(to_candidate(submission, comments_limit=comments_limit))
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
                "Subreddit scan result: subreddit=%s seen=%s accepted=%s rejections=%s",
                subreddit_name,
                seen_count,
                accepted_count,
                rejection_counts,
            )

    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates


def mark_submission_saved(candidate: ImageCandidate) -> None:
    if candidate.submission is None:
        return
    try:
        candidate.submission.save()
        LOGGER.info("Marked Reddit submission as saved", extra={"reddit_id": candidate.reddit_id})
    except Exception as exc:
        LOGGER.warning(
            "Failed to mark Reddit submission as saved",
            extra={"reddit_id": candidate.reddit_id, "error_class": type(exc).__name__},
        )
