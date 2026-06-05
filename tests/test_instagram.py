import unittest
from dataclasses import replace
from unittest.mock import patch

from meme_bot.config import BotConfig
from meme_bot.instagram import InstagramAPIError, InstagramClient


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


def config():
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
        tracker_path=None,
        graph_domain="https://graph.facebook.com",
        graph_version="v22.0",
        request_timeout_seconds=1,
        max_retry_attempts=3,
        retry_base_seconds=0,
        refresh_threshold_days=21,
        dry_run=False,
        use_reddit_saved_guard=False,
        mark_reddit_saved=False,
    )


class InstagramTest(unittest.TestCase):
    def test_post_image_creates_and_publishes_image_only_container(self):
        session = FakeSession([FakeResponse(200, {"id": "container"}), FakeResponse(200, {"id": "media"})])
        media_id = InstagramClient(config(), session=session).post_image("https://i.redd.it/a.jpg", "caption")

        self.assertEqual(media_id, "media")
        self.assertEqual(session.requests[0]["params"]["image_url"], "https://i.redd.it/a.jpg")
        self.assertNotIn("media_type", session.requests[0]["params"])
        self.assertEqual(session.requests[1]["params"]["creation_id"], "container")

    def test_api_error_raises(self):
        session = FakeSession([FakeResponse(400, {"error": {"message": "bad token"}})])

        with self.assertRaises(InstagramAPIError):
            InstagramClient(config(), session=session).create_image_container("https://i.redd.it/a.jpg", "caption")

    def test_retries_rate_limit_response(self):
        session = FakeSession(
            [
                FakeResponse(429, {"error": {"message": "rate limit"}}, headers={"Retry-After": "0"}),
                FakeResponse(200, {"id": "container"}),
            ]
        )

        with patch("meme_bot.retry.time.sleep") as sleep:
            container_id = InstagramClient(config(), session=session).create_image_container(
                "https://i.redd.it/a.jpg",
                "caption",
            )

        self.assertEqual(container_id, "container")
        self.assertEqual(len(session.requests), 2)
        sleep.assert_called_once()

    def test_retries_publish_when_media_id_is_not_available_yet(self):
        session = FakeSession(
            [
                FakeResponse(400, {"error": {"message": "Media ID is not available"}}),
                FakeResponse(200, {"id": "media"}),
            ]
        )

        with patch("meme_bot.instagram.time.sleep") as sleep:
            media_id = InstagramClient(config(), session=session).publish_container("container")

        self.assertEqual(media_id, "media")
        self.assertEqual(len(session.requests), 2)
        sleep.assert_called_once_with(10)

    def test_does_not_retry_non_readiness_publish_error(self):
        session = FakeSession([FakeResponse(400, {"error": {"message": "bad token"}})])

        with patch("meme_bot.instagram.time.sleep") as sleep:
            with self.assertRaises(InstagramAPIError):
                InstagramClient(config(), session=session).publish_container("container")

        self.assertEqual(len(session.requests), 1)
        sleep.assert_not_called()

    def test_dry_run_skips_instagram_validation(self):
        cfg = replace(config(), access_token=None, instagram_account_id=None, dry_run=True)
        session = FakeSession([FakeResponse(200, {"id": "container"})])

        self.assertEqual(
            InstagramClient(cfg, session=session).create_image_container("https://i.redd.it/a.jpg", "caption"),
            "container",
        )


if __name__ == "__main__":
    unittest.main()
