import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from meme_bot.config import BotConfig
from meme_bot.optimizer import run
from meme_bot.performance_store import PerformanceRecord, load_performance_store, save_performance_store


def config(base):
    return BotConfig(
        access_token=None,
        instagram_account_id=None,
        reddit_client_id="rid",
        reddit_client_secret="rsecret",
        reddit_user_agent="ua",
        reddit_username=None,
        reddit_password=None,
        fb_app_id=None,
        fb_app_secret=None,
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
        dry_run=True,
        use_reddit_saved_guard=False,
        mark_reddit_saved=False,
        performance_store_path=base / "performance.json",
        run_history_path=base / "run-history.jsonl",
        optimization_config_path=base / "optimized-config.json",
        optimization_changelog_path=base / "optimization-changelog.jsonl",
    )


def record(index, subreddit, score):
    return PerformanceRecord(
        reddit_id=f"id-{index}",
        reddit_url=f"https://www.reddit.com/r/{subreddit}/comments/{index}/title/",
        source_url=f"https://i.redd.it/{index}.jpg",
        media_url=f"https://i.redd.it/{index}.jpg",
        media_hash=f"hash-{index}",
        title="title",
        normalized_title="title",
        subreddit=subreddit,
        media_type="image",
        instagram_media_id=f"ig-{index}",
        instagram_permalink=None,
        posted_at=f"2026-06-{(index % 9) + 1:02d}T00:00:00Z",
        posting_hour_utc=0,
        posting_weekday_utc="tuesday",
        generated_score=60,
        score_breakdown={},
        score_rejections=[],
        caption_template_id="send_to_friend",
        hashtag_pool_id="memes",
        hashtags=["#memes"],
        final_performance_score=score,
    )


class OptimizerTest(unittest.TestCase):
    def test_updates_weights_after_minimum_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = config(base)
            store = load_performance_store(cfg.performance_store_path)
            store.posts = [record(i, "memes", 100) for i in range(10)]
            store.posts.extend(record(i + 10, "dankmemes", 10) for i in range(10))
            save_performance_store(cfg.performance_store_path, store)

            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(run(cfg), 0)

            generated = json.loads(cfg.optimization_config_path.read_text(encoding="utf-8"))
            changelog = cfg.optimization_changelog_path.read_text(encoding="utf-8")

        self.assertGreater(generated["scoring"]["subreddit_weights"]["memes"], 1.0)
        self.assertLess(generated["scoring"]["subreddit_weights"]["dankmemes"], 1.0)
        self.assertIn("scoring.subreddit_weights.memes", changelog)

    def test_noops_without_enough_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = config(base)
            store = load_performance_store(cfg.performance_store_path)
            store.posts = [record(i, "memes", 100) for i in range(3)]
            save_performance_store(cfg.performance_store_path, store)

            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(run(cfg), 0)

            self.assertFalse(cfg.optimization_config_path.exists())


if __name__ == "__main__":
    unittest.main()
