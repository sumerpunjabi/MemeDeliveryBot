from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .config import BotConfig
from .retry import request_with_retries

LOGGER = logging.getLogger(__name__)

PUBLISH_NOT_READY_MESSAGE = "Media ID is not available"
PUBLISH_READY_MAX_ATTEMPTS = 6
PUBLISH_READY_DELAY_SECONDS = 10
REEL_READY_STATUSES = {"FINISHED"}
REEL_FAILED_STATUSES = {"ERROR", "EXPIRED"}
REEL_STATUS_MAX_ATTEMPTS = 30
REEL_STATUS_DELAY_SECONDS = 10


class InstagramAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class InstagramInsights:
    metrics: dict[str, float]
    unavailable_metrics: list[str]


@dataclass(frozen=True)
class InstagramClient:
    config: BotConfig
    session: requests.Session | None = None

    def _session(self) -> requests.Session:
        return self.session or requests.Session()

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
    ) -> dict[str, Any]:
        session = self._session()
        response = request_with_retries(
            session,
            method,
            url,
            timeout=self.config.request_timeout_seconds,
            max_attempts=self.config.max_retry_attempts,
            base_delay_seconds=self.config.retry_base_seconds,
            params=params,
            headers=headers,
            data=data,
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

    def _post_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", url, params=params)

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("GET", url, params=params)

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
        params = {
            "creation_id": container_id,
            "access_token": self.config.access_token or "",
        }

        for attempt in range(1, PUBLISH_READY_MAX_ATTEMPTS + 1):
            try:
                payload = self._post_json(url, params)
                break
            except InstagramAPIError as exc:
                is_not_ready = PUBLISH_NOT_READY_MESSAGE.lower() in str(exc).lower()
                if not is_not_ready or attempt == PUBLISH_READY_MAX_ATTEMPTS:
                    raise
                LOGGER.warning(
                    "Instagram media container is not ready; retrying publish: container_id=%s attempt=%s/%s",
                    container_id,
                    attempt,
                    PUBLISH_READY_MAX_ATTEMPTS,
                )
                time.sleep(PUBLISH_READY_DELAY_SECONDS)

        media_id = payload.get("id")
        if not media_id:
            raise InstagramAPIError("Instagram did not return a published media id", payload=payload)
        LOGGER.info("Published Instagram media", extra={"instagram_media_id": media_id})
        return str(media_id)

    def post_image(self, image_url: str, caption: str) -> str:
        container_id = self.create_image_container(image_url, caption)
        return self.publish_container(container_id)

    def create_reel_container(self, caption: str, *, share_to_feed: bool = False) -> tuple[str, str]:
        self.config.validate_for_instagram()
        url = f"{self.config.endpoint_base}/{self.config.instagram_account_id}/media"
        payload = self._post_json(
            url,
            {
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": caption[:2200],
                "share_to_feed": str(share_to_feed).lower(),
                "access_token": self.config.access_token or "",
            },
        )
        container_id = payload.get("id")
        upload_uri = payload.get("uri")
        if not container_id or not upload_uri:
            raise InstagramAPIError("Instagram did not return a reel upload container", payload=payload)
        LOGGER.info("Created Instagram reel container", extra={"container_id": container_id})
        return str(container_id), str(upload_uri)

    def upload_reel_video(self, upload_uri: str, video_path: Path) -> None:
        self.config.validate_for_instagram()
        file_size = video_path.stat().st_size
        headers = {
            "Authorization": f"OAuth {self.config.access_token or ''}",
            "offset": "0",
            "file_size": str(file_size),
        }
        payload = self._request_json("POST", upload_uri, headers=headers, data=video_path.read_bytes())
        if payload.get("success") is not True and payload.get("message") != "Upload successful.":
            raise InstagramAPIError("Instagram reel upload did not succeed", payload=payload)
        LOGGER.info("Uploaded Instagram reel video", extra={"file_size": file_size})

    def get_container_status(self, container_id: str) -> dict[str, Any]:
        self.config.validate_for_instagram()
        url = f"{self.config.endpoint_base}/{container_id}"
        return self._get_json(
            url,
            {
                "fields": "status_code,status",
                "access_token": self.config.access_token or "",
            },
        )

    def get_media_details(self, media_id: str) -> dict[str, Any]:
        self.config.validate_for_instagram()
        url = f"{self.config.endpoint_base}/{media_id}"
        return self._get_json(
            url,
            {
                "fields": "id,media_type,media_product_type,permalink",
                "access_token": self.config.access_token or "",
            },
        )

    def _parse_insights(self, payload: dict[str, Any]) -> dict[str, float]:
        parsed: dict[str, float] = {}
        data = payload.get("data")
        if not isinstance(data, list):
            return parsed
        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            values = item.get("values")
            if not name or not isinstance(values, list) or not values:
                continue
            value = values[-1].get("value") if isinstance(values[-1], dict) else None
            if isinstance(value, (int, float)):
                parsed[str(name)] = float(value)
        return parsed

    def get_media_insights(self, media_id: str, metrics: list[str]) -> InstagramInsights:
        self.config.validate_for_instagram()
        clean_metrics = [metric.strip() for metric in metrics if metric.strip()]
        if not clean_metrics:
            return InstagramInsights(metrics={}, unavailable_metrics=[])

        url = f"{self.config.endpoint_base}/{media_id}/insights"
        params = {
            "metric": ",".join(clean_metrics),
            "access_token": self.config.access_token or "",
        }
        try:
            payload = self._get_json(url, params)
            parsed = self._parse_insights(payload)
            unavailable = [metric for metric in clean_metrics if metric not in parsed]
            return InstagramInsights(metrics=parsed, unavailable_metrics=unavailable)
        except InstagramAPIError as exc:
            LOGGER.warning(
                "Bulk Instagram insights request failed; retrying metrics individually: media_id=%s error_class=%s error=%s",
                media_id,
                type(exc).__name__,
                exc,
            )

        parsed: dict[str, float] = {}
        unavailable: list[str] = []
        for metric in clean_metrics:
            try:
                payload = self._get_json(
                    url,
                    {
                        "metric": metric,
                        "access_token": self.config.access_token or "",
                    },
                )
                metric_values = self._parse_insights(payload)
                if metric in metric_values:
                    parsed[metric] = metric_values[metric]
                else:
                    unavailable.append(metric)
            except InstagramAPIError as exc:
                unavailable.append(metric)
                LOGGER.info(
                    "Instagram insight metric unavailable: media_id=%s metric=%s error_class=%s",
                    media_id,
                    metric,
                    type(exc).__name__,
                )
        return InstagramInsights(metrics=parsed, unavailable_metrics=sorted(set(unavailable)))

    def verify_published_reel(self, media_id: str) -> None:
        payload = self.get_media_details(media_id)
        media_product_type = str(payload.get("media_product_type", "")).upper()
        media_type = str(payload.get("media_type", "")).upper()
        if media_product_type != "REELS":
            raise InstagramAPIError(
                "Instagram published media is not a Reel",
                payload={
                    "media_id": media_id,
                    "media_product_type": media_product_type,
                    "media_type": media_type,
                    "details": payload,
                },
            )
        LOGGER.info(
            "Verified Instagram media is a Reel",
            extra={"instagram_media_id": media_id, "media_product_type": media_product_type},
        )

    def wait_for_reel_container_ready(self, container_id: str) -> None:
        for attempt in range(1, REEL_STATUS_MAX_ATTEMPTS + 1):
            payload = self.get_container_status(container_id)
            status_code = str(payload.get("status_code", "")).upper()
            if status_code in REEL_READY_STATUSES:
                LOGGER.info("Instagram reel container is ready", extra={"container_id": container_id})
                return
            if status_code in REEL_FAILED_STATUSES:
                raise InstagramAPIError("Instagram reel container failed processing", payload=payload)
            if attempt == REEL_STATUS_MAX_ATTEMPTS:
                raise InstagramAPIError("Instagram reel container was not ready before timeout", payload=payload)
            LOGGER.info(
                "Waiting for Instagram reel container: container_id=%s status=%s attempt=%s/%s",
                container_id,
                status_code or "UNKNOWN",
                attempt,
                REEL_STATUS_MAX_ATTEMPTS,
            )
            time.sleep(REEL_STATUS_DELAY_SECONDS)

    def post_reel(self, video_path: Path, caption: str, *, share_to_feed: bool = False) -> str:
        container_id, upload_uri = self.create_reel_container(caption, share_to_feed=share_to_feed)
        self.upload_reel_video(upload_uri, video_path)
        self.wait_for_reel_container_ready(container_id)
        media_id = self.publish_container(container_id)
        self.verify_published_reel(media_id)
        return media_id
