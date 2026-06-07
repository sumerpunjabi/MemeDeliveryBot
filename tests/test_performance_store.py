import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from meme_bot.performance_store import (
    PerformanceRecord,
    build_performance_index,
    calculate_performance_score,
    load_performance_store,
    prune_performance_store,
    save_performance_store,
)


def record(reddit_id="abc", title="Same title", posted_at="2026-06-02T00:00:00Z"):
    return PerformanceRecord(
        reddit_id=reddit_id,
        reddit_url=f"https://www.reddit.com/r/memes/comments/{reddit_id}/title/",
        source_url=f"https://i.redd.it/{reddit_id}.jpg",
        media_url=f"https://i.redd.it/{reddit_id}.jpg",
        media_hash=f"hash-{reddit_id}",
        title=title,
        normalized_title="same title",
        subreddit="memes",
        media_type="image",
        instagram_media_id=f"ig-{reddit_id}",
        instagram_permalink=None,
        posted_at=posted_at,
        posting_hour_utc=0,
        posting_weekday_utc="tuesday",
        generated_score=60,
        score_breakdown={"age": 12},
        score_rejections=[],
        caption_template_id="send_to_friend",
        hashtag_pool_id="memes",
        hashtags=["#memes"],
    )


class PerformanceStoreTest(unittest.TestCase):
    def test_save_load_and_duplicate_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "performance.json"
            store = load_performance_store(path)
            store.posts.append(record())
            save_performance_store(path, store)
            loaded = load_performance_store(path)

        self.assertEqual(len(loaded.posts), 1)
        index = build_performance_index(loaded.posts)
        self.assertTrue(
            index.contains(
                reddit_id="other",
                source_url="https://i.redd.it/other.jpg",
                title="Same title",
            )
        )

    def test_prunes_old_records_and_snapshots(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=400)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        recent = record(reddit_id="recent")
        recent.metric_snapshots = [{"i": i} for i in range(5)]
        store = load_performance_store(Path("missing.json"))
        store.posts = [record(reddit_id="old", posted_at=old_date), recent]

        pruned = prune_performance_store(store, max_posts=10, max_age_days=365, max_snapshots_per_post=2)

        self.assertEqual([item.reddit_id for item in pruned.posts], ["recent"])
        self.assertEqual(len(pruned.posts[0].metric_snapshots), 2)

    def test_calculates_performance_score_with_missing_metrics(self):
        score = calculate_performance_score({"likes": 10, "comments": 2, "reach": 1000})

        self.assertEqual(score, 22.0)


if __name__ == "__main__":
    unittest.main()
