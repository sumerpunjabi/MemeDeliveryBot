from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlsplit

from .config import BotConfig

LOGGER = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
REJECTED_DOMAINS = {"v.redd.it", "redgifs.com", "www.redgifs.com", "gfycat.com", "www.gfycat.com"}


@dataclass(frozen=True)
class ImageCandidate:
    reddit_id: str
    title: str
    image_url: str
    subreddit: str
    score: int
    saved: bool
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


def to_candidate(submission: Any) -> ImageCandidate:
    return ImageCandidate(
        reddit_id=str(getattr(submission, "id")),
        title=str(getattr(submission, "title", "")),
        image_url=str(getattr(submission, "url", "")),
        subreddit=str(getattr(getattr(submission, "subreddit", ""), "display_name", getattr(submission, "subreddit", ""))),
        score=int(getattr(submission, "score", 0) or 0),
        saved=bool(getattr(submission, "saved", False)),
        submission=submission,
    )


def fetch_image_candidates(reddit: Any, config: BotConfig) -> list[ImageCandidate]:
    candidates: list[ImageCandidate] = []
    for subreddit_name in config.subreddits:
        LOGGER.info("Scanning subreddit: subreddit=%s", subreddit_name)
        seen_count = 0
        accepted_count = 0
        rejection_counts: dict[str, int] = {}
        try:
            subreddit = reddit.subreddit(subreddit_name)
            submissions: Iterable[Any] = subreddit.top(config.post_time_filter, limit=config.post_limit)
            for submission in submissions:
                seen_count += 1
                reason = rejection_reason(
                    submission,
                    min_score=config.min_score,
                    use_saved_guard=config.use_reddit_saved_guard,
                )
                if reason is None:
                    accepted_count += 1
                    candidates.append(to_candidate(submission))
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
