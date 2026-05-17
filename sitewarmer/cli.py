from __future__ import annotations

import argparse
import textwrap
from typing import Sequence

from . import __version__
from .core import SiteWarmerConfig, run
from .logging_utils import build_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sitewarmer",
        description="Lightweight website warmer and uptime checker for small/shared-hosted sites.",
        epilog=textwrap.dedent(
            """\
            examples:
              sitewarmer https://example.com --once
              sitewarmer https://example.com --discover both --limit 25
              sitewarmer https://example.com --discover links --max-depth 1 --exclude "/admin"
              sitewarmer https://example.com --once --json --log-file warmer.jsonl
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("urls", nargs="+", help="One or more target URLs to warm or check.")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between cycles when running continuously (default: 300).")
    parser.add_argument("--timeout", type=float, default=10.0, help="Network timeout in seconds (default: 10).")
    parser.add_argument("--retries", type=int, default=2, help="Retry count for transient network failures (default: 2).")
    parser.add_argument("--user-agent", default=f"sitewarmer/{__version__}", help=f"Custom User-Agent header (default: sitewarmer/{__version__}).")
    parser.add_argument("--discover", choices=["none", "sitemap", "links", "both"], default="none", help="Add URLs from sitemap, homepage links, or both (default: none).")
    parser.add_argument("--limit", type=int, default=10, help="Maximum discovered URLs to add per run, after de-duplication (default: 10).")
    parser.add_argument("--max-depth", type=int, default=0, help="Same-site link hops beyond the homepage for links/both discovery (default: 0).")
    parser.add_argument("--include", action="append", default=[], help="Include pattern matched against path/query or full URL.")
    parser.add_argument("--exclude", action="append", default=[], help="Exclude pattern matched against path/query or full URL.")
    parser.add_argument("--allow-external", action="store_true", help="Allow discovered external URLs; disabled by default.")
    parser.add_argument("--dry-run", action="store_true", help="Plan the run without making requests.")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit.")
    parser.add_argument("--continuous", action="store_true", help="Keep running until interrupted; this is the default when --once is not used.")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Emit JSON output.")
    parser.add_argument("--log-file", help="Append JSONL event logs to this file.")
    parser.add_argument("--read-limit", type=int, default=256 * 1024, help="Maximum bytes to read per response (default: 256 KiB).")
    parser.add_argument("--request-delay", type=float, default=1.0, help="Minimum delay between requests to the same host in a cycle (default: 1s).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose plain-text logging.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logger = build_logger(verbose=args.verbose)
    config = SiteWarmerConfig(
        urls=args.urls,
        interval=args.interval,
        timeout=args.timeout,
        retries=args.retries,
        user_agent=args.user_agent,
        discover=args.discover,
        limit=args.limit,
        max_depth=args.max_depth,
        include=args.include,
        exclude=args.exclude,
        allow_external=args.allow_external,
        dry_run=args.dry_run,
        once=args.once,
        continuous=args.continuous,
        json_output=args.json_output,
        log_file=args.log_file,
        request_delay=args.request_delay,
        read_limit=args.read_limit,
        verbose=args.verbose,
    )
    return run(config, logger=logger)
