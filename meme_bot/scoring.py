from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .performance_store import PerformanceIndex, duration_bucket, normalize_title
from .tuning import ScoringTuning


FUNNY_REACTION_RE = re.compile(r"\b(lol|lmao|lmfao|dead|crying|funny|hilarious|ruthless|accurate|real|same)\b|[😂😭💀]", re.I)
CONFUSED_RE = re.compile(r"\b(context|what does this mean|i don't get|dont get|explain|who is this for)\b", re.I)
SHAREABLE_RE = re.compile(
    r"\b(me|my|friend|friends|roommate|coworker|boss|mom|dad|bro|sister|when|every|pov|nobody|tag|send|specific|relatable)\b",
    re.I,
)
REDDIT_ONLY_RE = re.compile(r"\b(reddit|subreddit|upvote|karma|cake day|op\b|mods?\b|this sub|r/)\b", re.I)
SLOW_START_RE = re.compile(r"\b(wait for it|watch till the end|watch until the end|gets better|slow start)\b", re.I)
PAYOFF_RE = re.compile(r"\b(immediately|instant|first|ending|plot twist|caught|bro|then this happened)\b", re.I)


@dataclass(frozen=True)
class ScoreResult:
    total: float
    breakdown: dict[str, float]
    rejection_reasons: list[str]

    @property
    def accepted(self) -> bool:
        return not self.rejection_reasons


def _get(candidate: Any, name: str, default: Any = None) -> Any:
    return getattr(candidate, name, default)


def _comments_text(candidate: Any) -> str:
    comments = _get(candidate, "top_comments", ()) or ()
    return " ".join(str(getattr(comment, "body", "")) for comment in comments)


def _age_hours(candidate: Any, now: datetime) -> float | None:
    created_utc = _get(candidate, "created_utc")
    if created_utc is None:
        return None
    try:
        created = datetime.fromtimestamp(float(created_utc), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    return max(0.0, (now - created).total_seconds() / 3600.0)


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _log_score(value: int | float, *, scale: float, cap: float) -> float:
    if value <= 0:
        return 0.0
    return min(cap, math.log1p(float(value)) * scale)


def _title_clarity(title: str) -> float:
    words = normalize_title(title).split()
    if not words:
        return -12.0
    length = len(words)
    score = 12.0
    if length < 3:
        score -= 4.0
    if length > 18:
        score -= min(8.0, (length - 18) * 0.8)
    if title.count("?") + title.count("!") > 4:
        score -= 2.0
    if REDDIT_ONLY_RE.search(title):
        score -= 7.0
    return _bounded(score, -12.0, 14.0)


def _shareability(title: str, comments_text: str) -> float:
    text = f"{title} {comments_text}"
    score = 0.0
    score += min(10.0, len(SHAREABLE_RE.findall(text)) * 2.5)
    if FUNNY_REACTION_RE.search(comments_text):
        score += 4.0
    if REDDIT_ONLY_RE.search(title):
        score -= 6.0
    if CONFUSED_RE.search(comments_text):
        score -= 8.0
    return _bounded(score, -12.0, 16.0)


def _quick_payoff(candidate: Any, media_type: str, title: str, comments_text: str, tuning: ScoringTuning) -> float:
    text = f"{title} {comments_text}"
    score = 6.0
    if PAYOFF_RE.search(text):
        score += 4.0
    if SLOW_START_RE.search(text):
        score -= 10.0
    if media_type == "reel":
        duration = _get(candidate, "duration_seconds")
        if duration is None:
            score -= 2.0
        else:
            try:
                duration_value = float(duration)
            except (TypeError, ValueError):
                duration_value = 0.0
            if duration_value <= tuning.reel_preferred_duration_seconds:
                score += 8.0
            elif duration_value <= tuning.reel_soft_max_duration_seconds:
                score += 3.0
            else:
                score -= min(22.0, (duration_value - tuning.reel_soft_max_duration_seconds) * 0.8)
    return _bounded(score, -24.0, 16.0)


def _comment_reaction(candidate: Any, comments_text: str) -> float:
    comments = _get(candidate, "top_comments", ()) or ()
    score = 0.0
    for comment in comments:
        body = str(getattr(comment, "body", ""))
        comment_score = float(getattr(comment, "score", 0) or 0)
        if FUNNY_REACTION_RE.search(body):
            score += 2.5 + min(2.5, math.log1p(max(0.0, comment_score)))
        if CONFUSED_RE.search(body):
            score -= 5.0
    if not comments_text:
        score += 0.0
    return _bounded(score, -12.0, 18.0)


def _video_quality(candidate: Any, tuning: ScoringTuning) -> float:
    width = _get(candidate, "width")
    height = _get(candidate, "height")
    if width is None or height is None:
        return 0.0
    try:
        width_value = float(width)
        height_value = float(height)
    except (TypeError, ValueError):
        return 0.0
    if width_value <= 0 or height_value <= 0:
        return 0.0
    score = 4.0
    if width_value < tuning.reel_min_width or height_value < tuning.reel_min_height:
        score -= 10.0
    aspect_ratio = width_value / height_value
    if aspect_ratio < tuning.reel_min_aspect_ratio or aspect_ratio > tuning.reel_max_aspect_ratio:
        score -= 8.0
    return _bounded(score, -14.0, 5.0)


def _historical_multiplier(candidate: Any, media_type: str, tuning: ScoringTuning, now: datetime) -> float:
    subreddit = str(_get(candidate, "subreddit", "")).lower()
    age_hour = str(now.hour)
    bucket = duration_bucket(_get(candidate, "duration_seconds") if media_type == "reel" else None)
    factors = [
        tuning.subreddit_weights.get(subreddit, 1.0),
        tuning.posting_hour_weights.get(age_hour, 1.0),
        tuning.media_type_weights.get(media_type, 1.0),
        tuning.duration_bucket_weights.get(bucket, 1.0),
    ]
    multiplier = 1.0
    for factor in factors:
        multiplier *= _bounded(float(factor), 0.5, 1.5)
    return _bounded(multiplier, 0.35, 2.25)


def score_candidate(
    candidate: Any,
    *,
    media_type: str,
    tuning: ScoringTuning,
    performance_index: PerformanceIndex | None = None,
    now: datetime | None = None,
) -> ScoreResult:
    now = now or datetime.now(timezone.utc)
    title = str(_get(candidate, "title", "") or "")
    comments_text = _comments_text(candidate)
    num_comments = int(_get(candidate, "num_comments", 0) or 0)
    upvote_ratio = _get(candidate, "upvote_ratio")
    reddit_id = str(_get(candidate, "reddit_id", "") or "")
    reddit_url = str(_get(candidate, "reddit_permalink", "") or "")
    source_url = str(_get(candidate, "source_url", _get(candidate, "image_url", "")) or "")
    media_url = _get(candidate, "media_url", None)

    breakdown: dict[str, float] = {}
    rejection_reasons: list[str] = []

    age_hours = _age_hours(candidate, now)
    if age_hours is None:
        breakdown["age"] = 6.0
    elif age_hours <= tuning.hot_age_hours:
        breakdown["age"] = 16.0
    elif age_hours <= tuning.preferred_age_hours:
        breakdown["age"] = 12.0
    elif age_hours <= tuning.max_age_hours:
        breakdown["age"] = max(0.0, 12.0 - ((age_hours - tuning.preferred_age_hours) * 0.6))
    else:
        breakdown["age"] = -tuning.old_post_penalty
        rejection_reasons.append("stale")

    breakdown["reddit_score"] = _log_score(float(_get(candidate, "score", 0) or 0), scale=2.4, cap=18.0)
    breakdown["reddit_comments"] = _log_score(num_comments, scale=3.2, cap=18.0) * tuning.reddit_comment_weight
    if upvote_ratio is None:
        breakdown["upvote_ratio"] = 0.0
    else:
        try:
            breakdown["upvote_ratio"] = ((float(upvote_ratio) - 0.75) * 40.0) * tuning.upvote_ratio_weight
        except (TypeError, ValueError):
            breakdown["upvote_ratio"] = 0.0
        breakdown["upvote_ratio"] = _bounded(breakdown["upvote_ratio"], -10.0, 10.0)

    breakdown["media_type"] = 6.0 if media_type == "reel" else 4.0
    breakdown["title_clarity"] = _title_clarity(title) * tuning.title_weight
    breakdown["shareability"] = _shareability(title, comments_text) * tuning.shareability_weight
    breakdown["quick_payoff"] = _quick_payoff(candidate, media_type, title, comments_text, tuning) * tuning.quick_payoff_weight
    breakdown["comment_reaction"] = _comment_reaction(candidate, comments_text) * tuning.discussion_weight

    if media_type == "reel":
        duration = _get(candidate, "duration_seconds")
        if duration is not None:
            try:
                if float(duration) > tuning.reel_hard_max_duration_seconds:
                    rejection_reasons.append("video_too_long")
            except (TypeError, ValueError):
                pass
        breakdown["video_quality"] = _video_quality(candidate, tuning)

    subreddit = str(_get(candidate, "subreddit", "") or "").lower()
    if subreddit and subreddit in tuning.paused_subreddits:
        rejection_reasons.append("paused_subreddit")

    duplicate_reasons: list[str] = []
    if performance_index is not None:
        duplicate_reasons = performance_index.duplicate_reasons(
            reddit_id=reddit_id,
            reddit_url=reddit_url,
            source_url=source_url,
            media_url=media_url,
            title=title,
        )
    exact_duplicate_reasons = [reason for reason in duplicate_reasons if reason != "normalized_title"]
    if exact_duplicate_reasons:
        rejection_reasons.append("already_published")
        breakdown["duplicate_risk"] = -100.0
    elif duplicate_reasons:
        breakdown["duplicate_risk"] = -tuning.duplicate_risk_penalty
    else:
        breakdown["duplicate_risk"] = 0.0

    subtotal = sum(breakdown.values())
    multiplier = _historical_multiplier(candidate, media_type, tuning, now)
    breakdown["historical_multiplier"] = multiplier
    total = subtotal * multiplier

    if total < tuning.minimum_total_score:
        rejection_reasons.append("below_instagram_score_threshold")

    return ScoreResult(
        total=round(total, 4),
        breakdown={key: round(value, 4) for key, value in breakdown.items()},
        rejection_reasons=sorted(set(rejection_reasons)),
    )
