import unittest
from types import SimpleNamespace

from meme_bot.reddit_source import is_image_submission, rejection_reason, to_candidate


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
            ({"url": "https://i.redd.it/a.gif"}, "unsupported_extension"),
            ({"url": "https://v.redd.it/video"}, "unsupported_domain"),
            ({"stickied": True}, "stickied"),
            ({"over_18": True}, "nsfw"),
            ({"spoiler": True}, "spoiler"),
            ({"is_video": True}, "video"),
            ({"is_gallery": True}, "gallery"),
            ({"url": "https://www.reddit.com/gallery/abc"}, "gallery_url"),
            ({"post_hint": "hosted:video"}, "post_hint_hosted:video"),
            ({"score": 1}, "low_score"),
        ]
        for case, reason in reject_cases:
            with self.subTest(case=case):
                item = submission(**case)
                self.assertFalse(is_image_submission(item, min_score=10))
                self.assertEqual(rejection_reason(item, min_score=10), reason)

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
