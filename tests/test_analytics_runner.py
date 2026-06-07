import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from meme_bot.analytics_runner import run
from meme_bot.config import BotConfig
from meme_bot.instagram import InstagramInsights
from meme_bot.performance_store import PerformanceRecord, load_performance_store, save_performance_store


def config(base):
    return BotConfig(
        access_token="token",
        instagram_account_id="ig-user",
        reddit_client_id="rid",
        reddit_client_secret="rsecret",
        reddit_user_agent="ua",
        reddit_username=None,
        reddit_password=None,
        fb_app_id="fbid",
        fb_app_secret="fbsecret",
        subreddits=["memes"],
        post_time_filter="day",
        post_limit=100,
        min_score=0,
        tracker_path=base / "posted.jsonl",
        graph_domain="https://graph.facebook.com",
        graph_version="v22.0",
        request_timeout_seconds=1,
        max_retry_attempts=1,
        retry_base_seconds=0,
        refresh_threshold_days=21,
        dry_run=False,
        use_reddit_saved_guard=False,
        mark_reddit_saved=False,
        performance_store_path=base / "performance.json",
        run_history_path=base / "run-history.jsonl",
        optimization_config_path=base / "optimized-config.json",
        optimization_changelog_path=base / "optimization-changelog.jsonl",
    )


def record():
    return PerformanceRecord(
        reddit_id="abc",
        reddit_url="https://www.reddit.com/r/memes/comments/abc/title/",
        source_url="https://i.redd.it/a.jpg",
        media_url="https://i.redd.it/a.jpg",
        media_hash="hash",
        title="title",
        normalized_title="title",
        subreddit="memes",
        media_type="image",
        instagram_media_id="ig-media",
        instagram_permalink=None,
        posted_at="2026-06-02T00:00:00Z",
        posting_hour_utc=0,
        posting_weekday_utc="tuesday",
        generated_score=60,
        score_breakdown={},
        score_rejections=[],
        caption_template_id="send_to_friend",
        hashtag_pool_id="memes",
        hashtags=["#memes"],
    )


class FakeInstagramClient:
    def __init__(self, config):
        self.config = config

    def get_media_insights(self, media_id, metrics):
        return InstagramInsights(
            metrics={"likes": 10, "comments": 2, "saved": 1, "reach": 1000},
            unavailable_metrics=["shares"],
        )


class AnalyticsRunnerTest(unittest.TestCase):
    def test_updates_metrics_and_performance_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = config(base)
            store = load_performance_store(cfg.performance_store_path)
            store.posts.append(record())
            save_performance_store(cfg.performance_store_path, store)

            with patch("meme_bot.analytics_runner.InstagramClient", FakeInstagramClient):
                self.assertEqual(run(cfg), 0)

            updated = load_performance_store(cfg.performance_store_path).posts[0]

        self.assertEqual(updated.latest_metrics["likes"], 10)
        self.assertIn("shares", updated.unavailable_metrics)
        self.assertEqual(updated.final_performance_score, 30.0)


if __name__ == "__main__":
    unittest.main()
