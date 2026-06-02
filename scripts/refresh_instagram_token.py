from __future__ import annotations

import logging
import os
from pathlib import Path

from meme_bot.config import BotConfig
from meme_bot.token_manager import debug_token, refresh_access_token, should_refresh


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _write_github_output(name: str, value: str) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def main() -> int:
    setup_logging()
    config = BotConfig.from_env()
    token_output_path = Path(os.getenv("REFRESHED_TOKEN_PATH", "new_access_token.txt"))

    token_info = debug_token(config)
    expires_at = token_info.expires_at.isoformat() if token_info.expires_at else "none"
    logging.info("Checked Instagram token expiry: valid=%s expires_at=%s", token_info.is_valid, expires_at)

    if not should_refresh(token_info, config.refresh_threshold_days):
        logging.info("Token is not within refresh threshold; no update needed")
        _write_github_output("refreshed", "false")
        return 0

    new_token = refresh_access_token(config)
    token_output_path.write_text(new_token, encoding="utf-8")
    logging.info("Wrote refreshed token to secure workflow-local output file")
    _write_github_output("refreshed", "true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
