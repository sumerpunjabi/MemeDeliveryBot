from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .config import BotConfig
from .retry import request_with_retries

LOGGER = logging.getLogger(__name__)


class TokenRefreshError(RuntimeError):
    pass


@dataclass(frozen=True)
class TokenInfo:
    is_valid: bool
    expires_at: datetime | None


def _parse_graph_json(response: requests.Response, action: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise TokenRefreshError(f"Graph API returned non-JSON during {action}") from exc
    if response.status_code >= 400 or "error" in payload:
        raise TokenRefreshError(f"Graph API error during {action}: {payload.get('error', payload)}")
    return payload


def debug_token(config: BotConfig, session: requests.Session | None = None) -> TokenInfo:
    config.validate_for_token_refresh()
    actual_session = session or requests.Session()
    response = request_with_retries(
        actual_session,
        "GET",
        f"{config.endpoint_base}/debug_token",
        timeout=config.request_timeout_seconds,
        max_attempts=config.max_retry_attempts,
        base_delay_seconds=config.retry_base_seconds,
        params={
            "input_token": config.access_token,
            "access_token": f"{config.fb_app_id}|{config.fb_app_secret}",
        },
    )
    payload = _parse_graph_json(response, "token debug")
    data = payload.get("data", {})
    expires_at_raw = data.get("expires_at")
    expires_at = None
    if isinstance(expires_at_raw, int) and expires_at_raw > 0:
        expires_at = datetime.fromtimestamp(expires_at_raw, tz=timezone.utc)
    return TokenInfo(is_valid=bool(data.get("is_valid", False)), expires_at=expires_at)


def should_refresh(token_info: TokenInfo, threshold_days: int) -> bool:
    if not token_info.is_valid:
        raise TokenRefreshError("Current Instagram access token is invalid")
    if token_info.expires_at is None:
        return False
    return token_info.expires_at <= datetime.now(timezone.utc) + timedelta(days=threshold_days)


def refresh_access_token(config: BotConfig, session: requests.Session | None = None) -> str:
    config.validate_for_token_refresh()
    actual_session = session or requests.Session()
    response = request_with_retries(
        actual_session,
        "GET",
        f"{config.endpoint_base}/oauth/access_token",
        timeout=config.request_timeout_seconds,
        max_attempts=config.max_retry_attempts,
        base_delay_seconds=config.retry_base_seconds,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": config.fb_app_id,
            "client_secret": config.fb_app_secret,
            "fb_exchange_token": config.access_token,
        },
    )
    payload = _parse_graph_json(response, "token refresh")
    new_token = payload.get("access_token")
    if not new_token:
        raise TokenRefreshError("Graph API did not return an access_token during refresh")
    LOGGER.info("Instagram access token refreshed")
    return str(new_token)
