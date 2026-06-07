from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Literal

import requests

from .retry import request_with_retries

LOGGER = logging.getLogger(__name__)

ResourceType = Literal["posts", "photos"]
RATE_LIMIT_ERROR_CODES = {4, 17, 32, 613}


class FacebookCleanupError(RuntimeError):
    pass


class FacebookRateLimitError(FacebookCleanupError):
    pass


class FacebookGraphAPIError(FacebookCleanupError):
    def __init__(self, message: str, *, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class PageContentItem:
    id: str
    resource: ResourceType
    created_time: datetime
    permalink_url: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class CleanupConfig:
    page_id: str
    access_token: str
    before: datetime
    resources: tuple[ResourceType, ...] = ("posts",)
    graph_domain: str = "https://graph.facebook.com"
    graph_version: str = "v24.0"
    limit: int = 50
    max_scan_pages: int = 20
    max_deletes_per_run: int = 25
    request_delay_seconds: float = 5.0
    delete_delay_seconds: float = 8.0
    timeout_seconds: float = 20.0
    max_retry_attempts: int = 3
    retry_base_seconds: float = 5.0
    execute: bool = False
    audit_path: Path = Path("cleanup-state/facebook-page-cleanup.jsonl")

    @property
    def endpoint_base(self) -> str:
        return f"{self.graph_domain.rstrip('/')}/{self.graph_version}"


@dataclass
class CleanupResult:
    scanned: int = 0
    matched: list[PageContentItem] = field(default_factory=list)
    deleted: list[PageContentItem] = field(default_factory=list)
    failed: list[tuple[PageContentItem, str]] = field(default_factory=list)
    scan_page_limit_reached: bool = False


class FacebookPageCleanupClient:
    def __init__(self, config: CleanupConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.scan_page_limit_reached = False

    def _url(self, path: str) -> str:
        return f"{self.config.endpoint_base}/{path.lstrip('/')}"

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = request_with_retries(
            self.session,
            method,
            url,
            timeout=self.config.timeout_seconds,
            max_attempts=self.config.max_retry_attempts,
            base_delay_seconds=self.config.retry_base_seconds,
            params=params,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise FacebookGraphAPIError(
                "Meta Graph API returned a non-JSON response",
                status_code=response.status_code,
                payload=response.text,
            ) from exc

        if response.status_code >= 400 or "error" in payload:
            error = payload.get("error", payload)
            if isinstance(error, dict):
                message = str(error.get("message", "Meta Graph API error"))
                code = error.get("code")
            else:
                message = "Meta Graph API error"
                code = None
            if response.status_code == 429 or code in RATE_LIMIT_ERROR_CODES or "limit" in message.lower():
                raise FacebookRateLimitError(message)
            raise FacebookGraphAPIError(message, status_code=response.status_code, payload=payload)

        return payload

    def list_page_content(self, resource: ResourceType) -> Iterable[PageContentItem]:
        if resource == "posts":
            path = f"{self.config.page_id}/posts"
            params: dict[str, Any] | None = {
                "fields": "id,created_time,permalink_url,message",
                "limit": str(self.config.limit),
                "until": str(int(self.config.before.timestamp())),
                "access_token": self.config.access_token,
            }
        else:
            path = f"{self.config.page_id}/photos"
            params = {
                "fields": "id,created_time,link,name",
                "type": "uploaded",
                "limit": str(self.config.limit),
                "until": str(int(self.config.before.timestamp())),
                "access_token": self.config.access_token,
            }

        url = self._url(path)
        pages_read = 0
        while url:
            if pages_read >= self.config.max_scan_pages:
                self.scan_page_limit_reached = True
                return
            payload = self._request_json("GET", url, params=params)
            pages_read += 1
            params = None

            data = payload.get("data", [])
            if not isinstance(data, list):
                data = []
            for entry in data:
                item = _parse_item(entry, resource)
                if item is not None:
                    yield item

            paging = payload.get("paging") if isinstance(payload.get("paging"), dict) else {}
            next_url = paging.get("next")
            url = str(next_url) if next_url else ""
            if url:
                time.sleep(self.config.request_delay_seconds)

    def delete_item(self, item: PageContentItem) -> None:
        self._request_json(
            "DELETE",
            self._url(item.id),
            params={"access_token": self.config.access_token},
        )


def parse_cutoff(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_created_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    clean = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None
    return parsed.astimezone(UTC)


def _parse_item(entry: Any, resource: ResourceType) -> PageContentItem | None:
    if not isinstance(entry, dict):
        return None
    item_id = entry.get("id")
    created_time = _parse_created_time(entry.get("created_time"))
    if not item_id or created_time is None:
        return None
    permalink_url = entry.get("permalink_url") or entry.get("link")
    message = entry.get("message") or entry.get("name")
    return PageContentItem(
        id=str(item_id),
        resource=resource,
        created_time=created_time,
        permalink_url=str(permalink_url) if permalink_url else None,
        message=str(message) if message else None,
    )


def _append_audit(path: Path, action: str, item: PageContentItem, *, error: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "action": action,
        "id": item.id,
        "resource": item.resource,
        "created_time": item.created_time.isoformat(),
        "permalink_url": item.permalink_url,
        "error": error,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def find_delete_candidates(config: CleanupConfig, client: FacebookPageCleanupClient) -> CleanupResult:
    result = CleanupResult()
    seen: set[str] = set()
    for resource in config.resources:
        for item in client.list_page_content(resource):
            result.scanned += 1
            if item.id in seen:
                continue
            seen.add(item.id)
            if item.created_time >= config.before:
                continue
            result.matched.append(item)
            if config.execute and len(result.matched) >= config.max_deletes_per_run:
                result.matched.sort(key=lambda matched: matched.created_time)
                return result
        if client.scan_page_limit_reached:
            result.scan_page_limit_reached = True
    result.matched.sort(key=lambda item: item.created_time)
    return result


def run_cleanup(config: CleanupConfig, session: requests.Session | None = None) -> CleanupResult:
    client = FacebookPageCleanupClient(config, session=session)
    result = find_delete_candidates(config, client)
    if not config.execute:
        return result

    for item in result.matched[: config.max_deletes_per_run]:
        try:
            client.delete_item(item)
            result.deleted.append(item)
            _append_audit(config.audit_path, "deleted", item)
            LOGGER.info("Deleted Facebook Page content: resource=%s id=%s", item.resource, item.id)
        except FacebookRateLimitError:
            raise
        except FacebookCleanupError as exc:
            result.failed.append((item, str(exc)))
            _append_audit(config.audit_path, "failed", item, error=str(exc))
            LOGGER.error("Failed to delete Facebook Page content: id=%s error=%s", item.id, exc)
        time.sleep(config.delete_delay_seconds)
    return result
