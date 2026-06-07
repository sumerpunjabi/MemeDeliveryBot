from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from meme_bot.facebook_cleanup import (  # noqa: E402
    CleanupConfig,
    FacebookCleanupError,
    FacebookRateLimitError,
    parse_cutoff,
    resolve_page_id,
    run_cleanup,
)

DELETE_ACK = "DELETE_OLD_PAGE_CONTENT"


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _resources(value: str) -> tuple[str, ...]:
    if value == "all":
        return ("posts", "photos")
    return (value,)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run or delete Facebook Page posts/photos created before a cutoff date."
    )
    parser.add_argument("--page-id", default=os.getenv("FACEBOOK_PAGE_ID") or os.getenv("PAGE_ID"))
    parser.add_argument(
        "--instagram-account-id",
        default=os.getenv("INSTAGRAM_ACCOUNT_ID"),
        help="Used to resolve the connected Facebook Page when --page-id is omitted.",
    )
    parser.add_argument(
        "--access-token",
        default=os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN") or os.getenv("PAGE_ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN"),
        help="Use a Page-capable access token. Falls back to ACCESS_TOKEN.",
    )
    parser.add_argument("--before", default="2026-06-01", help="Delete content strictly before this UTC date/time.")
    parser.add_argument("--resource", choices=("posts", "photos", "all"), default="posts")
    parser.add_argument("--graph-domain", default=os.getenv("GRAPH_DOMAIN", "https://graph.facebook.com"))
    parser.add_argument("--graph-version", default=os.getenv("GRAPH_VERSION", "v24.0"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--max-scan-pages", type=int, default=20)
    parser.add_argument("--max-deletes-per-run", type=int, default=25)
    parser.add_argument("--request-delay-seconds", type=float, default=5.0)
    parser.add_argument("--delete-delay-seconds", type=float, default=8.0)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--max-retry-attempts", type=int, default=3)
    parser.add_argument("--retry-base-seconds", type=float, default=5.0)
    parser.add_argument("--audit-path", type=Path, default=Path("cleanup-state/facebook-page-cleanup.jsonl"))
    parser.add_argument("--execute", action="store_true", help="Actually delete matched content.")
    parser.add_argument(
        "--confirm-permanent-delete",
        default="",
        help=f"Required with --execute. Must equal {DELETE_ACK}.",
    )
    return parser


def config_from_args(args: argparse.Namespace) -> CleanupConfig:
    if not args.access_token:
        raise ValueError("Missing access token. Set ACCESS_TOKEN, FACEBOOK_PAGE_ACCESS_TOKEN, or pass --access-token.")
    if args.execute and args.confirm_permanent_delete != DELETE_ACK:
        raise ValueError(f"Live deletion requires --confirm-permanent-delete {DELETE_ACK}")
    if args.max_deletes_per_run < 1:
        raise ValueError("--max-deletes-per-run must be at least 1")
    if args.limit < 1:
        raise ValueError("--limit must be at least 1")
    if args.max_scan_pages < 1:
        raise ValueError("--max-scan-pages must be at least 1")

    page_id = args.page_id
    if not page_id:
        page_id = resolve_page_id(
            access_token=args.access_token,
            instagram_account_id=args.instagram_account_id,
            graph_domain=args.graph_domain,
            graph_version=args.graph_version,
            timeout_seconds=args.timeout_seconds,
            max_retry_attempts=args.max_retry_attempts,
            retry_base_seconds=args.retry_base_seconds,
        )

    return CleanupConfig(
        page_id=page_id,
        access_token=args.access_token,
        before=parse_cutoff(args.before),
        resources=_resources(args.resource),  # type: ignore[arg-type]
        graph_domain=args.graph_domain,
        graph_version=args.graph_version,
        limit=args.limit,
        max_scan_pages=args.max_scan_pages,
        max_deletes_per_run=args.max_deletes_per_run,
        request_delay_seconds=args.request_delay_seconds,
        delete_delay_seconds=args.delete_delay_seconds,
        timeout_seconds=args.timeout_seconds,
        max_retry_attempts=args.max_retry_attempts,
        retry_base_seconds=args.retry_base_seconds,
        execute=args.execute,
        audit_path=args.audit_path,
    )


def main() -> int:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = config_from_args(args)
        result = run_cleanup(config)
    except FacebookRateLimitError as exc:
        logging.error("Stopping after Meta rate-limit response. Retry later; no further deletes were attempted. %s", exc)
        return 75
    except (FacebookCleanupError, ValueError) as exc:
        logging.error("%s", exc)
        return 2

    mode = "LIVE DELETE" if config.execute else "DRY RUN"
    print(f"Mode: {mode}")
    print(f"Cutoff: before {config.before.isoformat()}")
    print(f"Scanned: {result.scanned}")
    print(f"Matched: {len(result.matched)}")
    print(f"Deleted: {len(result.deleted)}")
    print(f"Failed: {len(result.failed)}")
    if result.scan_page_limit_reached:
        print("Scan stopped at --max-scan-pages; rerun with a higher limit if needed.")
    if config.execute and len(result.matched) >= config.max_deletes_per_run:
        print("Delete cap reached; rerun later to continue without increasing request pressure.")
    if not config.execute and result.matched:
        print("First matches:")
        for item in result.matched[:10]:
            target = item.permalink_url or item.id
            print(f"- {item.resource} {item.id} {item.created_time.isoformat()} {target}")
    if config.execute:
        print(f"Audit log: {config.audit_path}")
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
