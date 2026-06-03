import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from meme_bot.tracker import (
    PostedRecord,
    append_record,
    build_index,
    calculate_image_hash,
    load_records,
    normalize_image_url,
)


class FakeImageResponse:
    status_code = 200
    headers = {"Content-Type": "image/jpeg"}

    def __init__(self, body: bytes):
        self.body = body
        self.closed = False

    def iter_content(self, chunk_size=1):
        yield self.body

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.last_request = None

    def request(self, method, url, timeout, **kwargs):
        self.last_request = {"method": method, "url": url, "timeout": timeout, **kwargs}
        return self.response


class TrackerTest(unittest.TestCase):
    def test_normalize_image_url_removes_query_fragment_and_normalizes_host(self):
        self.assertEqual(
            normalize_image_url("HTTPS://I.REDD.IT/example.JPG?width=640#frag"),
            "https://i.redd.it/example.JPG",
        )

    def test_load_records_ignores_malformed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "posted.jsonl"
            path.write_text(
                "\n".join(
                    [
                        "{bad json",
                        json.dumps(
                            {
                                "reddit_id": "abc",
                                "image_url": "https://i.redd.it/a.jpg",
                                "image_hash": "hash",
                                "title": "title",
                                "subreddit": "memes",
                                "instagram_media_id": "ig",
                                "posted_at": "2026-06-02T00:00:00Z",
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            records = load_records(path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].reddit_id, "abc")

    def test_append_record_and_index_duplicate_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "posted.jsonl"
            append_record(
                path,
                PostedRecord(
                    reddit_id="abc",
                    image_url="https://I.REDD.IT/a.jpg?width=640",
                    image_hash="hash",
                    title="title",
                    subreddit="memes",
                    instagram_media_id="ig",
                    posted_at="2026-06-02T00:00:00Z",
                ),
            )
            records = load_records(path)
            index = build_index(records)

        self.assertTrue(index.contains("abc", "https://i.redd.it/other.jpg"))
        self.assertTrue(index.contains("other", "https://i.redd.it/a.jpg"))
        self.assertTrue(index.contains("other", "https://i.redd.it/other.jpg", "hash"))

    def test_calculate_image_hash(self):
        body = b"image bytes"
        response = FakeImageResponse(body)
        session = FakeSession(response)
        digest = calculate_image_hash(
            "https://i.redd.it/a.jpg",
            session,
            timeout=1,
            max_attempts=1,
            base_delay_seconds=0,
            user_agent="test-agent",
        )

        self.assertEqual(digest, hashlib.sha256(body).hexdigest())
        self.assertEqual(session.last_request["headers"]["User-Agent"], "test-agent")
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
