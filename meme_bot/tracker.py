from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

import requests

from .retry import request_with_retries

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PostedRecord:
    reddit_id: str
    image_url: str
    image_hash: str
    title: str
    subreddit: str
    instagram_media_id: str
    posted_at: str


@dataclass(frozen=True)
class TrackerIndex:
    reddit_ids: set[str]
    image_urls: set[str]
    image_hashes: set[str]

    def contains(self, reddit_id: str, image_url: str, image_hash: str | None = None) -> bool:
        if reddit_id in self.reddit_ids:
            return True
        if normalize_image_url(image_url) in self.image_urls:
            return True
        return bool(image_hash and image_hash in self.image_hashes)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_image_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") if parsed.path.endswith("/") else parsed.path
    return urlunsplit((scheme, netloc, path, "", ""))


def load_records(path: Path) -> list[PostedRecord]:
    records: list[PostedRecord] = []
    if not path.exists():
        return records

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
                records.append(
                    PostedRecord(
                        reddit_id=str(data["reddit_id"]),
                        image_url=str(data["image_url"]),
                        image_hash=str(data["image_hash"]),
                        title=str(data["title"]),
                        subreddit=str(data["subreddit"]),
                        instagram_media_id=str(data["instagram_media_id"]),
                        posted_at=str(data["posted_at"]),
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                LOGGER.warning(
                    "Ignoring malformed tracker line",
                    extra={"path": str(path), "line": line_number, "error_class": type(exc).__name__},
                )
    return records


def build_index(records: Iterable[PostedRecord]) -> TrackerIndex:
    reddit_ids: set[str] = set()
    image_urls: set[str] = set()
    image_hashes: set[str] = set()

    for record in records:
        reddit_ids.add(record.reddit_id)
        image_urls.add(normalize_image_url(record.image_url))
        if record.image_hash:
            image_hashes.add(record.image_hash)

    return TrackerIndex(reddit_ids=reddit_ids, image_urls=image_urls, image_hashes=image_hashes)


def load_index(path: Path) -> TrackerIndex:
    return build_index(load_records(path))


def append_record(path: Path, record: PostedRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(record)
    payload["image_url"] = normalize_image_url(payload["image_url"])
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def calculate_image_hash(
    url: str,
    session: requests.Session,
    *,
    timeout: float,
    max_attempts: int,
    base_delay_seconds: float,
    user_agent: str | None = None,
    max_bytes: int = 25 * 1024 * 1024,
) -> str:
    headers = {"Accept": "image/*"}
    if user_agent:
        headers["User-Agent"] = user_agent

    response = request_with_retries(
        session,
        "GET",
        url,
        timeout=timeout,
        max_attempts=max_attempts,
        base_delay_seconds=base_delay_seconds,
        stream=True,
        headers=headers,
    )
    if response.status_code >= 400:
        response.close()
        raise ValueError(f"Image fetch failed with status {response.status_code}")

    content_type = response.headers.get("Content-Type", "")
    if content_type and not content_type.lower().startswith("image/"):
        response.close()
        raise ValueError(f"URL did not return image content: {content_type}")

    digest = hashlib.sha256()
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Image exceeds maximum hash size")
            digest.update(chunk)
    finally:
        response.close()

    if total == 0:
        raise ValueError("Image response was empty")
    return digest.hexdigest()
