import unittest
from types import SimpleNamespace

from meme_bot.captions import CAPTION_TEMPLATES, generate_caption, sanitize_subreddit_hashtag
from meme_bot.performance_store import PerformanceRecord
from meme_bot.scoring import ScoreResult
from meme_bot.tuning import CaptionTuning, ScoringTuning


def record(template_id, index):
    return PerformanceRecord(
        reddit_id=f"old-{index}",
        reddit_url="",
        source_url="",
        media_url=None,
        media_hash=None,
        title="old",
        normalized_title="old",
        subreddit="memes",
        media_type="image",
        instagram_media_id="ig",
        instagram_permalink=None,
        posted_at=f"2026-06-0{index + 1}T00:00:00Z",
        posting_hour_utc=0,
        posting_weekday_utc="monday",
        generated_score=50,
        score_breakdown={},
        score_rejections=[],
        caption_template_id=template_id,
        hashtag_pool_id="memes",
        hashtags=["#memes"],
    )


class CaptionsTest(unittest.TestCase):
    def test_sanitizes_subreddit_hashtag(self):
        self.assertEqual(sanitize_subreddit_hashtag("funny-videos"), "#funnyvideos")

    def test_rotates_away_from_recent_templates_and_keeps_attribution(self):
        recent_ids = [template.template_id for template in CAPTION_TEMPLATES[:-1]]
        recent = [record(template_id, index) for index, template_id in enumerate(recent_ids)]
        candidate = SimpleNamespace(reddit_id="abc", title="This is way too specific", subreddit="funny-videos")
        score = ScoreResult(total=70, breakdown={"shareability": 10, "reddit_comments": 9}, rejection_reasons=[])

        result = generate_caption(
            candidate,
            media_type="image",
            score_result=score,
            recent_records=recent,
            caption_tuning=CaptionTuning(recent_template_window=len(recent)),
            scoring_tuning=ScoringTuning(),
        )

        self.assertEqual(result.template_id, CAPTION_TEMPLATES[-1].template_id)
        self.assertIn("via r/funny-videos on Reddit", result.caption)
        self.assertLessEqual(len(result.hashtags), 4)
        self.assertIn("#funnyvideos", result.hashtags)


if __name__ == "__main__":
    unittest.main()
