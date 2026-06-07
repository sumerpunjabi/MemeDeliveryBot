import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from meme_bot.config import BotConfig
from meme_bot.reel_runner import build_reel_caption, run
from meme_bot.reel_source import ReelCandidate
from meme_bot.video_processing import ProcessedVideo


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
        tracker_path=Path("state/posted.jsonl"),
        graph_domain="https://graph.facebook.com",
        graph_version="v22.0",
        request_timeout_seconds=1,
        max_retry_attempts=1,
        retry_base_seconds=0,
        refresh_threshold_days=21,
        dry_run=False,
        use_reddit_saved_guard=False,
        mark_reddit_saved=False,
        reel_subreddits=["memes"],
        reel_post_time_filter="day",
        reel_post_limit=100,
        reel_min_score=0,
        reel_tracker_path=path,
        reel_max_duration_seconds=90,
        reel_max_bytes=1000,
        reel_share_to_feed=True,
        reels_dry_run=dry_run,
        performance_store_path=path.parent / "performance.json",
        run_history_path=path.parent / "run-history.jsonl",
        optimization_config_path=path.parent / "optimized-config.json",
        optimization_changelog_path=path.parent / "optimization-changelog.jsonl",
    )


class FakeInstagramClient:
    def __init__(self, config):
        self.config = config

    def post_reel(self, video_path, caption, *, share_to_feed=True):
        return "ig-reel"


class FailingInstagramClient(FakeInstagramClient):
    def post_reel(self, video_path, caption, *, share_to_feed=True):
        raise RuntimeError("publish failed")


def candidate(reddit_id="abc", source_url="https://v.redd.it/abc"):
    return ReelCandidate(
        reddit_id=reddit_id,
        title="title",
        source_url=source_url,
        reddit_permalink="https://www.reddit.com/r/memes/comments/abc/title/",
        subreddit="memes",
        score=100,
        duration_seconds=12,
        saved=False,
    )


def processed(path):
    return ProcessedVideo(
        path=path,
        video_hash="hash",
        size_bytes=100,
        duration_seconds=12,
    )


class ReelRunnerTest(unittest.TestCase):
    def test_build_reel_caption_adds_engagement_prompt_attribution_and_hashtags(self):
        caption = build_reel_caption(candidate())

        self.assertIn("title", caption)
        self.assertIn("Follow for more daily memes.", caption)
        self.assertIn("Share this with someone who needs a laugh.", caption)
        self.assertIn("via r/memes on Reddit", caption)
        self.assertIn("#memes", caption)
        self.assertIn("#reels", caption)
        self.assertIn("#redditmemes", caption)

    def test_build_reel_caption_adds_sanitized_subreddit_hashtag(self):
        caption = build_reel_caption(candidate())

        self.assertNotIn("#memes #memes", caption)

        custom = ReelCandidate(
            reddit_id="abc",
            title="title",
            source_url="https://v.redd.it/abc",
            reddit_permalink="https://www.reddit.com/r/funny-videos/comments/abc/title/",
            subreddit="funny-videos",
            score=100,
            duration_seconds=12,
            saved=False,
        )
        self.assertIn("#funnyvideos", build_reel_caption(custom))

    def test_successful_publish_appends_reel_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker_path = Path(tmp) / "state" / "reels-posted.jsonl"
            video_path = Path(tmp) / "reel.mp4"
            video_path.write_bytes(b"video")
            cfg = config(tracker_path)
            with patch("meme_bot.reel_runner.create_reddit", return_value=object()), \
                patch("meme_bot.reel_runner.fetch_reel_candidates", return_value=[candidate()]), \
                patch("meme_bot.reel_runner.download_video", return_value=processed(video_path)), \
                patch("meme_bot.reel_runner.InstagramClient", FakeInstagramClient):
                self.assertEqual(run(cfg), 0)

            content = tracker_path.read_text(encoding="utf-8")
            performance = (tracker_path.parent / "performance.json").read_text(encoding="utf-8")

        self.assertIn('"reddit_id":"abc"', content)
        self.assertIn('"instagram_media_id":"ig-reel"', content)
        self.assertIn('"source_url":"https://v.redd.it/abc"', content)
        self.assertIn('"media_type":"reel"', performance)
        self.assertIn('"caption_template_id"', performance)

    def test_publish_failure_does_not_append_reel_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker_path = Path(tmp) / "state" / "reels-posted.jsonl"
            video_path = Path(tmp) / "reel.mp4"
            video_path.write_bytes(b"video")
            cfg = config(tracker_path)
            with patch("meme_bot.reel_runner.create_reddit", return_value=object()), \
                patch("meme_bot.reel_runner.fetch_reel_candidates", return_value=[candidate()]), \
                patch("meme_bot.reel_runner.download_video", return_value=processed(video_path)), \
                patch("meme_bot.reel_runner.InstagramClient", FailingInstagramClient):
                with self.assertRaises(RuntimeError):
                    run(cfg)

            self.assertFalse(tracker_path.exists())

    def test_dry_run_downloads_but_does_not_append_reel_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker_path = Path(tmp) / "state" / "reels-posted.jsonl"
            video_path = Path(tmp) / "reel.mp4"
            video_path.write_bytes(b"video")
            cfg = config(tracker_path, dry_run=True)
            with patch("meme_bot.reel_runner.create_reddit", return_value=object()), \
                patch("meme_bot.reel_runner.fetch_reel_candidates", return_value=[candidate()]), \
                patch("meme_bot.reel_runner.download_video", return_value=processed(video_path)) as download, \
                patch("meme_bot.reel_runner.InstagramClient", FakeInstagramClient):
                self.assertEqual(run(cfg), 0)

            download.assert_called_once()
            self.assertFalse(tracker_path.exists())

    def test_duplicate_candidate_is_skipped_before_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracker_path = Path(tmp) / "state" / "reels-posted.jsonl"
            tracker_path.parent.mkdir(parents=True)
            tracker_path.write_text(
                '{"reddit_id":"abc","source_url":"https://v.redd.it/abc","video_hash":"hash","title":"title","subreddit":"memes","instagram_media_id":"ig","posted_at":"2026-06-02T00:00:00Z"}\n',
                encoding="utf-8",
            )
            cfg = config(tracker_path)
            with patch("meme_bot.reel_runner.create_reddit", return_value=object()), \
                patch("meme_bot.reel_runner.fetch_reel_candidates", return_value=[candidate()]), \
                patch("meme_bot.reel_runner.download_video") as download:
                self.assertEqual(run(cfg), 0)

            download.assert_not_called()

    def test_no_candidate_exits_successfully(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config(Path(tmp) / "state" / "reels-posted.jsonl")
            with patch("meme_bot.reel_runner.create_reddit", return_value=object()), \
                patch("meme_bot.reel_runner.fetch_reel_candidates", return_value=[]):
                self.assertEqual(run(cfg), 0)


if __name__ == "__main__":
    unittest.main()
