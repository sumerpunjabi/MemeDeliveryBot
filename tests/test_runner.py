import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from meme_bot.config import BotConfig
from meme_bot.reddit_source import ImageCandidate
from meme_bot.runner import run


def config(path, dry_run=False):
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
        tracker_path=path,
        graph_domain="https://graph.facebook.com",
        graph_version="v22.0",
        request_timeout_seconds=1,
        max_retry_attempts=1,
        retry_base_seconds=0,
        refresh_threshold_days=21,
        dry_run=dry_run,
        use_reddit_saved_guard=False,
        mark_reddit_saved=False,
    )


class FakeInstagramClient:
    def __init__(self, config, session=None):
        self.config = config

    def post_image(self, image_url, caption):
        return "ig-media"


class FailingInstagramClient(FakeInstagramClient):
    def post_image(self, image_url, caption):
        raise RuntimeError("publish failed")


def candidate(reddit_id="abc", image_url="https://i.redd.it/a.jpg"):
    return ImageCandidate(
        reddit_id=reddit_id,
        title="title",
        image_url=image_url,
        subreddit="memes",
        score=100,
        saved=False,
    )


class RunnerTest(unittest.TestCase):
    def test_successful_publish_appends_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker_path = Path(tmp) / "state" / "posted.jsonl"
            cfg = config(tracker_path)
            with patch("meme_bot.runner.create_reddit", return_value=object()), \
                patch("meme_bot.runner.fetch_image_candidates", return_value=[candidate()]), \
                patch("meme_bot.runner.calculate_image_hash", return_value="hash"), \
                patch("meme_bot.runner.InstagramClient", FakeInstagramClient):
                self.assertEqual(run(cfg), 0)

            content = tracker_path.read_text(encoding="utf-8")

        self.assertIn('"reddit_id":"abc"', content)
        self.assertIn('"instagram_media_id":"ig-media"', content)

    def test_publish_failure_does_not_append_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker_path = Path(tmp) / "state" / "posted.jsonl"
            cfg = config(tracker_path)
            with patch("meme_bot.runner.create_reddit", return_value=object()), \
                patch("meme_bot.runner.fetch_image_candidates", return_value=[candidate()]), \
                patch("meme_bot.runner.calculate_image_hash", return_value="hash"), \
                patch("meme_bot.runner.InstagramClient", FailingInstagramClient):
                with self.assertRaises(RuntimeError):
                    run(cfg)

            self.assertFalse(tracker_path.exists())

    def test_dry_run_does_not_append_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker_path = Path(tmp) / "state" / "posted.jsonl"
            cfg = config(tracker_path, dry_run=True)
            with patch("meme_bot.runner.create_reddit", return_value=object()), \
                patch("meme_bot.runner.fetch_image_candidates", return_value=[candidate()]), \
                patch("meme_bot.runner.calculate_image_hash", return_value="hash"), \
                patch("meme_bot.runner.InstagramClient", FakeInstagramClient):
                self.assertEqual(run(cfg), 0)

            self.assertFalse(tracker_path.exists())

    def test_duplicate_candidate_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker_path = Path(tmp) / "state" / "posted.jsonl"
            tracker_path.parent.mkdir(parents=True)
            tracker_path.write_text(
                '{"reddit_id":"abc","image_url":"https://i.redd.it/a.jpg","image_hash":"hash","title":"title","subreddit":"memes","instagram_media_id":"ig","posted_at":"2026-06-02T00:00:00Z"}\n',
                encoding="utf-8",
            )
            cfg = config(tracker_path)
            with patch("meme_bot.runner.create_reddit", return_value=object()), \
                patch("meme_bot.runner.fetch_image_candidates", return_value=[candidate()]), \
                patch("meme_bot.runner.calculate_image_hash") as hash_image, \
                patch("meme_bot.runner.InstagramClient", FakeInstagramClient):
                self.assertEqual(run(cfg), 0)

            hash_image.assert_not_called()

    def test_no_candidate_exits_successfully(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config(Path(tmp) / "state" / "posted.jsonl")
            with patch("meme_bot.runner.create_reddit", return_value=object()), \
                patch("meme_bot.runner.fetch_image_candidates", return_value=[]):
                self.assertEqual(run(cfg), 0)


if __name__ == "__main__":
    unittest.main()
