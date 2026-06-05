import unittest
from types import SimpleNamespace

from meme_bot.reel_source import fetch_reel_candidates, is_reel_submission, reel_rejection_reason, to_reel_candidate


def submission(**overrides):
    defaults = {
        "id": "abc",
        "title": "title",
        "url": "https://v.redd.it/abc",
        "permalink": "/r/memes/comments/abc/title/",
        "subreddit": SimpleNamespace(display_name="memes"),
        "score": 100,
        "stickied": False,
        "over_18": False,
        "spoiler": False,
        "is_video": True,
        "is_gallery": False,
        "post_hint": "hosted:video",
        "saved": False,
        "secure_media": {"reddit_video": {"duration": 12}},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class FakeListing:
    def __init__(self, submissions):
        self.submissions = submissions

    def top(self, time_filter, limit):
        self.time_filter = time_filter
        self.limit = limit
        return self.submissions


class FakeReddit:
    def __init__(self, mapping):
        self.mapping = mapping

    def subreddit(self, name):
        return FakeListing(self.mapping[name])


class FakeConfig:
    reel_subreddits = ["memes"]
    reel_post_time_filter = "day"
    reel_post_limit = 100
    reel_min_score = 10
    reel_max_duration_seconds = 90
    use_reddit_saved_guard = False


class ReelSourceTest(unittest.TestCase):
    def test_accepts_supported_reddit_video_submission(self):
        self.assertTrue(is_reel_submission(submission()))

    def test_rejects_unsafe_unsupported_and_bad_duration_content(self):
        reject_cases = [
            ({"url": "https://youtube.com/watch?v=abc"}, "unsupported_domain"),
            ({"stickied": True}, "stickied"),
            ({"over_18": True}, "nsfw"),
            ({"spoiler": True}, "spoiler"),
            ({"is_gallery": True}, "gallery"),
            ({"score": 1}, "low_score"),
            ({"saved": True}, "saved"),
            ({"post_hint": "image"}, "post_hint_image"),
            ({"is_video": False, "post_hint": None}, "not_video"),
            ({"secure_media": {"reddit_video": {"duration": 2}}}, "too_short"),
            ({"secure_media": {"reddit_video": {"duration": 120}}}, "too_long"),
        ]
        for case, reason in reject_cases:
            with self.subTest(case=case):
                item = submission(**case)
                self.assertEqual(
                    reel_rejection_reason(
                        item,
                        min_score=10,
                        max_duration_seconds=90,
                        use_saved_guard=True,
                    ),
                    reason,
                )

    def test_to_reel_candidate_maps_submission(self):
        candidate = to_reel_candidate(submission(id="xyz", title="hello", score=42))

        self.assertEqual(candidate.reddit_id, "xyz")
        self.assertEqual(candidate.title, "hello")
        self.assertEqual(candidate.subreddit, "memes")
        self.assertEqual(candidate.score, 42)
        self.assertEqual(candidate.duration_seconds, 12)
        self.assertEqual(candidate.reddit_permalink, "https://www.reddit.com/r/memes/comments/abc/title/")

    def test_fetch_reel_candidates_orders_by_score(self):
        low = submission(id="low", score=20, url="https://v.redd.it/low")
        high = submission(id="high", score=200, url="https://v.redd.it/high")
        image = submission(id="image", url="https://i.redd.it/a.jpg", post_hint="image", is_video=False)
        reddit = FakeReddit({"memes": [low, high, image]})

        candidates = fetch_reel_candidates(reddit, FakeConfig())

        self.assertEqual([candidate.reddit_id for candidate in candidates], ["high", "low"])


if __name__ == "__main__":
    unittest.main()
