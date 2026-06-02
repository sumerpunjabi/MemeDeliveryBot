from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from .config import BotConfig
from .retry import request_with_retries

LOGGER = logging.getLogger(__name__)


class InstagramAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class InstagramClient:
    config: BotConfig
    session: requests.Session | None = None

    def _session(self) -> requests.Session:
        return self.session or requests.Session()

    def _post_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        session = self._session()
        response = request_with_retries(
            session,
            "POST",
            url,
            timeout=self.config.request_timeout_seconds,
            max_attempts=self.config.max_retry_attempts,
            base_delay_seconds=self.config.retry_base_seconds,
            params=params,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise InstagramAPIError(
                "Instagram returned a non-JSON response",
                status_code=response.status_code,
                payload=response.text,
            ) from exc

        if response.status_code >= 400 or "error" in payload:
            error = payload.get("error", payload)
            message = error.get("message", "Instagram API error") if isinstance(error, dict) else "Instagram API error"
            raise InstagramAPIError(message, status_code=response.status_code, payload=payload)
        return payload

    def create_image_container(self, image_url: str, caption: str) -> str:
        self.config.validate_for_instagram()
        url = f"{self.config.endpoint_base}/{self.config.instagram_account_id}/media"
        payload = self._post_json(
            url,
            {
                "image_url": image_url,
                "caption": caption[:2200],
                "access_token": self.config.access_token or "",
            },
        )
        container_id = payload.get("id")
        if not container_id:
            raise InstagramAPIError("Instagram did not return a media container id", payload=payload)
        LOGGER.info("Created Instagram image container", extra={"container_id": container_id})
        return str(container_id)

    def publish_container(self, container_id: str) -> str:
        self.config.validate_for_instagram()
        url = f"{self.config.endpoint_base}/{self.config.instagram_account_id}/media_publish"
        payload = self._post_json(
            url,
            {
                "creation_id": container_id,
                "access_token": self.config.access_token or "",
            },
        )
        media_id = payload.get("id")
        if not media_id:
            raise InstagramAPIError("Instagram did not return a published media id", payload=payload)
        LOGGER.info("Published Instagram media", extra={"instagram_media_id": media_id})
        return str(media_id)

    def post_image(self, image_url: str, caption: str) -> str:
        container_id = self.create_image_container(image_url, caption)
        return self.publish_container(container_id)
