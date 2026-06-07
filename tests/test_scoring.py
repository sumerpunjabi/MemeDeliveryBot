import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from meme_bot.performance_store import PerformanceRecord, build_performance_index
from meme_bot.reddit_source import RedditComment
from meme_bot.scoring import score_candidate
from meme_bot.tuning import ScoringTuning


def candidate(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "reddit_id": "abc",
        "title": "When your friend says this is fine",
        "image_url": "https://i.redd.it/a.jpg",
        "source_url": "https://i.redd.it/a.jpg",
        "reddit_permalink": "https://www.reddit.com/r/memes/comments/abc/title/",
        "subreddit": "memes",
        "score": 250,
        "num_comments": 42,
        "upvote_ratio": 0.94,
        "created_utc": (now - timedelta(hours=3)).timestamp(),
        "top_comments": (RedditComment("lol this is too real", 20),),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def performance_record(**overrides):
    defaults = {
        "reddit_id": "abc",
        "reddit_url": "https://www.reddit.com/r/memes/comments/abc/title/",
        "source_url": "https://i.redd.it/a.jpg",
        "media_url": "https://i.redd.it/a.jpg",
        "media_hash": "hash",
        "title": "When your friend says this is fine",
        "normalized_title": "when your friend says this is fine",
        "subreddit": "memes",
        "media_type": "image",
        "instagram_media_id": "ig",
        "instagram_permalink": None,
        "posted_at": "2026-06-02T00:00:00Z",
        "posting_hour_utc": 0,
        "posting_weekday_utc": "tuesday",
        "generated_score": 70,
        "score_breakdown": {},
        "score_rejections": [],
        "caption_template_id": "send_to_friend",
        "hashtag_pool_id": "memes",
        "hashtags": ["#memes"],
    }
    defaults.update(overrides)
    return PerformanceRecord(**defaults)


class ScoringTest(unittest.TestCase):
    def test_scores_instagram_candidate_with_breakdown(self):
        result = score_candidate(candidate(), media_type="image", tuning=ScoringTuning())

        self.assertTrue(result.accepted)
        self.assertGreater(result.total, 35)
        self.assertIn("reddit_comments", result.breakdown)
        self.assertIn("shareability", result.breakdown)

    def test_rejects_stale_posts(self):
        old = candidate(created_utc=(datetime.now(timezone.utc) - timedelta(days=4)).timestamp())

        result = score_candidate(old, media_type="image", tuning=ScoringTuning())

        self.assertIn("stale", result.rejection_reasons)

    def test_rejects_existing_performance_duplicate(self):
        index = build_performance_index([performance_record()])

        result = score_candidate(candidate(), media_type="image", tuning=ScoringTuning(), performance_index=index)

        self.assertIn("already_published", result.rejection_reasons)

    def test_downranks_long_reels(self):
        reel = candidate(
            source_url="https://v.redd.it/abc",
            media_url="https://v.redd.it/abc/HLSPlaylist.m3u8",
            duration_seconds=70,
            width=720,
            height=1280,
        )

        result = score_candidate(reel, media_type="reel", tuning=ScoringTuning())

        self.assertLess(result.breakdown["quick_payoff"], 0)


if __name__ == "__main__":
    unittest.main()
