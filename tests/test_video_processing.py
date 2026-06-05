import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from meme_bot.reel_source import ReelCandidate
from meme_bot.video_processing import VideoProcessingError, download_video


def candidate(media_url=None):
    return ReelCandidate(
        reddit_id="abc",
        title="title",
        source_url="https://v.redd.it/abc",
        reddit_permalink="https://www.reddit.com/r/memes/comments/abc/title/",
        subreddit="memes",
        score=100,
        duration_seconds=12,
        saved=False,
        media_url=media_url,
    )


class VideoProcessingTest(unittest.TestCase):
    def test_download_video_prefers_direct_media_url_over_yt_dlp(self):
        commands = []

        def fake_run(command):
            commands.append(command)
            Path(command[-1]).write_bytes(b"normalized-video")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp, \
            patch("meme_bot.video_processing._run_command", side_effect=fake_run), \
            patch("meme_bot.video_processing.probe_video_duration", return_value=12.5):
            processed = download_video(
                candidate(media_url="https://v.redd.it/abc/HLSPlaylist.m3u8"),
                Path(tmp),
                max_bytes=1000,
                max_duration_seconds=90,
            )

        self.assertEqual(processed.size_bytes, len(b"normalized-video"))
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][0], "ffmpeg")
        self.assertIn("https://v.redd.it/abc/HLSPlaylist.m3u8", commands[0])
        self.assertNotIn("yt-dlp", commands[0])

    def test_download_video_downloads_normalizes_and_hashes(self):
        commands = []

        def fake_run(command):
            commands.append(command)
            if command[0] == "yt-dlp":
                Path(command[command.index("--output") + 1]).write_bytes(b"raw-video")
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"normalized-video")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp, \
            patch("meme_bot.video_processing._run_command", side_effect=fake_run), \
            patch("meme_bot.video_processing.probe_video_duration", return_value=12.5):
            processed = download_video(
                candidate(),
                Path(tmp),
                max_bytes=1000,
                max_duration_seconds=90,
            )

        self.assertEqual(processed.size_bytes, len(b"normalized-video"))
        self.assertEqual(processed.duration_seconds, 12.5)
        self.assertEqual(commands[0][0], "yt-dlp")
        self.assertEqual(commands[0][-1], "https://www.reddit.com/r/memes/comments/abc/title/")
        self.assertEqual(commands[1][0], "ffmpeg")
        self.assertIn("libx264", commands[1])
        self.assertIn("+faststart", commands[1])

    def test_download_failure_raises_processing_error(self):
        with tempfile.TemporaryDirectory() as tmp, \
            patch("meme_bot.video_processing._run_command", side_effect=VideoProcessingError("download failed")):
            with self.assertRaises(VideoProcessingError):
                download_video(candidate(), Path(tmp), max_bytes=1000, max_duration_seconds=90)

    def test_oversized_download_raises_before_normalization(self):
        commands = []

        def fake_run(command):
            commands.append(command)
            Path(command[command.index("--output") + 1]).write_bytes(b"x" * 20)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp, \
            patch("meme_bot.video_processing._run_command", side_effect=fake_run):
            with self.assertRaises(VideoProcessingError):
                download_video(candidate(), Path(tmp), max_bytes=10, max_duration_seconds=90)

        self.assertEqual(len(commands), 1)

    def test_invalid_duration_raises_after_probe(self):
        def fake_run(command):
            if command[0] == "yt-dlp":
                Path(command[command.index("--output") + 1]).write_bytes(b"raw-video")
            if command[0] == "ffmpeg":
                Path(command[-1]).write_bytes(b"normalized-video")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp, \
            patch("meme_bot.video_processing._run_command", side_effect=fake_run), \
            patch("meme_bot.video_processing.probe_video_duration", return_value=2.5):
            with self.assertRaises(VideoProcessingError):
                download_video(candidate(), Path(tmp), max_bytes=1000, max_duration_seconds=90)


if __name__ == "__main__":
    unittest.main()
