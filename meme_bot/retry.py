from __future__ import annotations

import logging
import time
from email.utils import parsedate_to_datetime
from typing import Iterable

import requests

LOGGER = logging.getLogger(__name__)


class HTTPRequestError(RuntimeError):
    pass


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, parsed.timestamp() - time.time())


def request_with_retries(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout: float,
    max_attempts: int = 3,
    base_delay_seconds: float = 2.0,
    retry_statuses: Iterable[int] = (429, 500, 502, 503, 504),
    **kwargs,
) -> requests.Response:
    retry_status_set = set(retry_statuses)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
            if response.status_code not in retry_status_set or attempt == max_attempts:
                return response

            retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
            delay = retry_after if retry_after is not None else base_delay_seconds * (2 ** (attempt - 1))
            LOGGER.warning(
                "Retrying HTTP request after retryable response",
                extra={"status_code": response.status_code, "attempt": attempt},
            )
            time.sleep(delay)
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            LOGGER.warning(
                "Retrying HTTP request after transport error",
                extra={"attempt": attempt, "error_class": type(exc).__name__},
            )
            time.sleep(delay)

    raise HTTPRequestError(f"HTTP request failed after {max_attempts} attempts: {last_error}")
