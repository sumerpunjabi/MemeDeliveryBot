from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .performance_store import PerformanceRecord
from .scoring import ScoreResult
from .tuning import CaptionTuning, ScoringTuning


MAX_INSTAGRAM_CAPTION_LENGTH = 2200


@dataclass(frozen=True)
class CaptionTemplate:
    template_id: str
    text: str
    preferred_tags: set[str]


@dataclass(frozen=True)
class HashtagPool:
    pool_id: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class CaptionResult:
    caption: str
    template_id: str
    hashtag_pool_id: str
    hashtags: list[str]


CAPTION_TEMPLATES = (
    CaptionTemplate("send_to_friend", "Send this to the friend who needs to see it.", {"shareable"}),
    CaptionTemplate("be_honest", "Be honest - who would you send this to?", {"shareable", "comments"}),
    CaptionTemplate("tag_someone", "Tag someone who does this.", {"shareable"}),
    CaptionTemplate("rate_this", "Rate this 1-10.", {"comments"}),
    CaptionTemplate("too_specific", "This is way too specific.", {"relatable"}),
    CaptionTemplate("comments_ruthless", "The comments were ruthless.", {"comments"}),
    CaptionTemplate("saved_for_later", "Save this for when you need the receipt.", {"saves"}),
)

HASHTAG_POOLS = (
    HashtagPool("memes", ("#memes", "#funny", "#dailymemes", "#redditmemes")),
    HashtagPool("reels", ("#reels", "#funnyreels", "#instareels", "#memes")),
    HashtagPool("relatable", ("#relatable", "#funnymemes", "#mood", "#memes")),
    HashtagPool("comments", ("#memes", "#funnyposts", "#commentsection", "#reddit")),
)


def sanitize_subreddit_hashtag(subreddit: str) -> str | None:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", subreddit)
    if not cleaned:
        return None
    return f"#{cleaned}"


def _seed(candidate: Any, media_type: str) -> int:
    key = f"{getattr(candidate, 'reddit_id', '')}:{getattr(candidate, 'title', '')}:{media_type}"
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def _recent_template_ids(records: Iterable[PerformanceRecord], window: int) -> set[str]:
    recent = sorted(records, key=lambda item: item.posted_at, reverse=True)[:window]
    return {record.caption_template_id for record in recent if record.caption_template_id}


def _score_tags(score_result: ScoreResult) -> set[str]:
    tags: set[str] = set()
    breakdown = score_result.breakdown
    if breakdown.get("shareability", 0.0) >= 5.0:
        tags.add("shareable")
    if breakdown.get("reddit_comments", 0.0) >= 8.0 or breakdown.get("comment_reaction", 0.0) >= 6.0:
        tags.add("comments")
    if breakdown.get("shareability", 0.0) >= 8.0:
        tags.add("relatable")
    if breakdown.get("quick_payoff", 0.0) <= 1.0:
        tags.add("saves")
    return tags


def _pick_template(
    candidate: Any,
    media_type: str,
    score_result: ScoreResult,
    recent_records: Iterable[PerformanceRecord],
    caption_tuning: CaptionTuning,
    scoring_tuning: ScoringTuning,
) -> CaptionTemplate:
    rng = random.Random(_seed(candidate, media_type))
    recent_ids = _recent_template_ids(recent_records, caption_tuning.recent_template_window)
    desired_tags = _score_tags(score_result)
    candidates = [template for template in CAPTION_TEMPLATES if template.template_id not in recent_ids]
    if not candidates:
        candidates = list(CAPTION_TEMPLATES)

    weighted: list[tuple[float, CaptionTemplate]] = []
    for template in candidates:
        weight = scoring_tuning.caption_template_weights.get(template.template_id, 1.0)
        if desired_tags & template.preferred_tags:
            weight += 0.35
        weighted.append((max(0.05, weight), template))

    total = sum(weight for weight, _ in weighted)
    pick = rng.random() * total
    running = 0.0
    for weight, template in weighted:
        running += weight
        if running >= pick:
            return template
    return weighted[-1][1]


def _pick_hashtag_pool(
    candidate: Any,
    media_type: str,
    template: CaptionTemplate,
    scoring_tuning: ScoringTuning,
) -> HashtagPool:
    rng = random.Random(_seed(candidate, media_type) + 7)
    pools = list(HASHTAG_POOLS)
    weighted: list[tuple[float, HashtagPool]] = []
    for pool in pools:
        weight = scoring_tuning.hashtag_pool_weights.get(pool.pool_id, 1.0)
        if media_type == "reel" and pool.pool_id == "reels":
            weight += 0.4
        if "comments" in template.preferred_tags and pool.pool_id == "comments":
            weight += 0.25
        if "relatable" in template.preferred_tags and pool.pool_id == "relatable":
            weight += 0.25
        weighted.append((max(0.05, weight), pool))

    total = sum(weight for weight, _ in weighted)
    pick = rng.random() * total
    running = 0.0
    for weight, pool in weighted:
        running += weight
        if running >= pick:
            return pool
    return weighted[-1][1]


def _hashtags(candidate: Any, pool: HashtagPool, caption_tuning: CaptionTuning) -> list[str]:
    tags: list[str] = []
    subreddit_tag = sanitize_subreddit_hashtag(str(getattr(candidate, "subreddit", "") or ""))
    if subreddit_tag:
        tags.append(subreddit_tag)
    for tag in pool.tags:
        if tag.lower() not in {existing.lower() for existing in tags}:
            tags.append(tag)
    return tags[: max(0, caption_tuning.max_hashtags)]


def generate_caption(
    candidate: Any,
    *,
    media_type: str,
    score_result: ScoreResult,
    recent_records: Iterable[PerformanceRecord],
    caption_tuning: CaptionTuning,
    scoring_tuning: ScoringTuning,
) -> CaptionResult:
    template = _pick_template(candidate, media_type, score_result, recent_records, caption_tuning, scoring_tuning)
    pool = _pick_hashtag_pool(candidate, media_type, template, scoring_tuning)
    hashtags = _hashtags(candidate, pool, caption_tuning)

    title = str(getattr(candidate, "title", "") or "").strip() or "From Reddit"
    attribution = f"via r/{getattr(candidate, 'subreddit', 'reddit')} on Reddit"
    caption = "\n\n".join([title, template.text, attribution, " ".join(hashtags)]).strip()
    return CaptionResult(
        caption=caption[:MAX_INSTAGRAM_CAPTION_LENGTH],
        template_id=template.template_id,
        hashtag_pool_id=pool.pool_id,
        hashtags=hashtags,
    )
