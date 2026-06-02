import unittest
from types import SimpleNamespace

from meme_bot.reddit_source import is_image_submission, to_candidate


def submission(**overrides):
    defaults = {
        "id": "abc",
        "title": "title",
        "url": "https://i.redd.it/a.jpg",
        "subreddit": SimpleNamespace(display_name="memes"),
        "score": 100,
        "stickied": False,
        "over_18": False,
        "spoiler": False,
        "is_video": False,
        "is_gallery": False,
        "post_hint": "image",
        "saved": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class RedditSourceTest(unittest.TestCase):
    def test_accepts_supported_image_submission(self):
        self.assertTrue(is_image_submission(submission()))

    def test_rejects_non_image_and_unsafe_content(self):
        reject_cases = [
            {"url": "https://i.redd.it/a.gif"},
            {"url": "https://v.redd.it/video"},
            {"stickied": True},
            {"over_18": True},
            {"spoiler": True},
            {"is_video": True},
            {"is_gallery": True},
            {"url": "https://www.reddit.com/gallery/abc"},
            {"post_hint": "hosted:video"},
            {"score": 1},
        ]
        for case in reject_cases:
            with self.subTest(case=case):
                self.assertFalse(is_image_submission(submission(**case), min_score=10))

    def test_saved_guard_is_optional(self):
        saved = submission(saved=True)
        self.assertTrue(is_image_submission(saved, use_saved_guard=False))
        self.assertFalse(is_image_submission(saved, use_saved_guard=True))

    def test_to_candidate_maps_submission(self):
        candidate = to_candidate(submission(id="xyz", title="hello", score=42))

        self.assertEqual(candidate.reddit_id, "xyz")
        self.assertEqual(candidate.title, "hello")
        self.assertEqual(candidate.subreddit, "memes")
        self.assertEqual(candidate.score, 42)


if __name__ == "__main__":
    unittest.main()
