import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from meme_bot.facebook_cleanup import CleanupConfig, FacebookPageCleanupClient, parse_cutoff, run_cleanup


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}
        self.text = str(payload)

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, timeout, **kwargs):
        self.requests.append({"method": method, "url": url, "timeout": timeout, **kwargs})
        return self.responses.pop(0)


def config(**overrides):
    values = {
        "page_id": "page",
        "access_token": "token",
        "before": datetime(2026, 6, 1, tzinfo=UTC),
        "resources": ("posts",),
        "limit": 50,
        "max_scan_pages": 5,
        "max_deletes_per_run": 25,
        "request_delay_seconds": 0,
        "delete_delay_seconds": 0,
        "timeout_seconds": 1,
        "max_retry_attempts": 1,
        "retry_base_seconds": 0,
    }
    values.update(overrides)
    return CleanupConfig(**values)


class FacebookCleanupTest(unittest.TestCase):
    def test_parse_cutoff_treats_date_as_utc_midnight(self):
        self.assertEqual(parse_cutoff("2026-06-01"), datetime(2026, 6, 1, tzinfo=UTC))

    def test_dry_run_lists_only_items_before_cutoff(self):
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "data": [
                            {"id": "old", "created_time": "2026-05-31T23:59:59+0000"},
                            {"id": "new", "created_time": "2026-06-01T00:00:00+0000"},
                        ]
                    },
                )
            ]
        )

        result = run_cleanup(config(), session=session)

        self.assertEqual(result.scanned, 2)
        self.assertEqual([item.id for item in result.matched], ["old"])
        self.assertEqual(len(result.deleted), 0)
        self.assertEqual(session.requests[0]["method"], "GET")
        self.assertEqual(session.requests[0]["params"]["until"], "1780272000")

    def test_execute_deletes_with_cap_and_audit_log(self):
        with TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            cfg = config(execute=True, max_deletes_per_run=1, audit_path=audit_path)
            session = FakeSession(
                [
                    FakeResponse(
                        200,
                        {
                            "data": [
                                {"id": "old-1", "created_time": "2026-05-30T00:00:00+0000"},
                            ]
                        },
                    ),
                    FakeResponse(200, {"success": True}),
                ]
            )

            with patch("meme_bot.facebook_cleanup.time.sleep"):
                result = run_cleanup(cfg, session=session)

            self.assertEqual([item.id for item in result.deleted], ["old-1"])
            self.assertEqual(session.requests[1]["method"], "DELETE")
            self.assertIn("old-1", audit_path.read_text(encoding="utf-8"))

    def test_photos_request_uses_uploaded_type(self):
        session = FakeSession([FakeResponse(200, {"data": []})])
        client = FacebookPageCleanupClient(config(resources=("photos",)), session=session)

        self.assertEqual(list(client.list_page_content("photos")), [])

        self.assertEqual(session.requests[0]["params"]["type"], "uploaded")


if __name__ == "__main__":
    unittest.main()
