from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from .discovery import DiscoveredURL, discover_targets, fetch_text
from .logging_utils import JsonlLogger
from .utils import (
    DEFAULT_INTERVAL,
    DEFAULT_LIMIT,
    DEFAULT_READ_LIMIT,
    DEFAULT_REQUEST_DELAY,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    MIN_SAFE_INTERVAL,
    dedupe_preserve,
    ensure_http_url,
    matches_any,
    path_and_query,
    pretty_bytes,
    pretty_ms,
    same_site,
    strip_fragment,
    url_host_key,
)


@dataclass
class SiteWarmerConfig:
    urls: list[str]
    interval: int = DEFAULT_INTERVAL
    timeout: float = DEFAULT_TIMEOUT
    retries: int = DEFAULT_RETRIES
    user_agent: str = "sitewarmer/0.1"
    discover: str = "none"
    limit: int = DEFAULT_LIMIT
    max_depth: int = 0
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    allow_external: bool = False
    dry_run: bool = False
    once: bool = False
    continuous: bool = False
    json_output: bool = False
    log_file: str | None = None
    request_delay: float = DEFAULT_REQUEST_DELAY
    read_limit: int = DEFAULT_READ_LIMIT
    verbose: bool = False


@dataclass
class WarmResult:
    url: str
    source: str
    origin: str
    ok: bool
    skipped: bool
    status_code: int | None = None
    elapsed_ms: float | None = None
    bytes_read: int | None = None
    error: str | None = None
    final_url: str | None = None
    attempts: int = 0


@dataclass
class CycleSummary:
    total: int = 0
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    bytes_read: int = 0


@dataclass
class CycleReport:
    started_at_utc: str
    finished_at_utc: str
    results: list[WarmResult]
    summary: CycleSummary
    targets: list[str]
    mode: str
    interval_seconds: int


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def parse_robot_delay(url: str, timeout: float, user_agent: str) -> float | None:
    parser = RobotFileParser()
    parsed = ensure_http_url(url)
    host = parsed.split("://", 1)[0] + "://" + parsed.split("://", 1)[1].split("/", 1)[0]
    try:
        text = fetch_text(f"{host}/robots.txt", timeout=timeout, user_agent=user_agent)
    except (HTTPError, URLError, TimeoutError, OSError):
        parser.parse([])
        return None
    parser.parse(text.splitlines())
    delay = parser.crawl_delay(user_agent) or parser.crawl_delay("*")
    return float(delay) if delay else None


def discover_plan(config: SiteWarmerConfig) -> tuple[list[DiscoveredURL], int]:
    seeds = [ensure_http_url(url) for url in config.urls]
    discovered = discover_targets(
        seeds,
        mode=config.discover,
        timeout=config.timeout,
        user_agent=config.user_agent,
        limit=config.limit,
        allow_external=config.allow_external,
        max_depth=config.max_depth,
    )
    delay_candidates = [config.interval]
    for seed in seeds:
        robot_delay = parse_robot_delay(seed, timeout=config.timeout, user_agent=config.user_agent)
        if robot_delay is not None:
            delay_candidates.append(int(robot_delay))
    effective_interval = max(delay_candidates)
    return discovered, effective_interval


def _should_include(url: str, include: list[str], exclude: list[str]) -> bool:
    candidate = path_and_query(url)
    if include and not (matches_any(candidate, include) or matches_any(url, include)):
        return False
    if exclude and (matches_any(candidate, exclude) or matches_any(url, exclude)):
        return False
    return True


def _retry_sleep(attempt: int) -> float:
    return min(0.5 * (2**attempt), 3.0)


def fetch_url(url: str, *, timeout: float, retries: int, user_agent: str, read_limit: int) -> WarmResult:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        method="GET",
    )
    last_error: str | None = None
    for attempt in range(retries + 1):
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read(read_limit)
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                status_code = response.getcode()
                ok = status_code is not None and status_code < 400
                return WarmResult(
                    url=url,
                    source="seed",
                    origin=url,
                    ok=ok,
                    skipped=False,
                    status_code=status_code,
                    elapsed_ms=elapsed_ms,
                    bytes_read=len(body),
                    error=None if ok else f"HTTP {status_code}",
                    final_url=response.geturl(),
                    attempts=attempt + 1,
                )
        except HTTPError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            body = exc.read(read_limit) if hasattr(exc, "read") else b""
            status_code = exc.code
            if status_code in {429} or status_code >= 500:
                last_error = f"HTTP {status_code}"
                if attempt < retries:
                    time.sleep(_retry_sleep(attempt))
                    continue
            return WarmResult(
                url=url,
                source="seed",
                origin=url,
                ok=status_code < 400,
                skipped=False,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                bytes_read=len(body),
                error=f"HTTP {status_code}",
                final_url=exc.geturl() if hasattr(exc, "geturl") else url,
                attempts=attempt + 1,
            )
        except (URLError, TimeoutError, OSError) as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            last_error = str(exc)
            if attempt < retries:
                time.sleep(_retry_sleep(attempt))
                continue
            return WarmResult(
                url=url,
                source="seed",
                origin=url,
                ok=False,
                skipped=False,
                status_code=None,
                elapsed_ms=elapsed_ms,
                bytes_read=0,
                error=last_error,
                final_url=url,
                attempts=attempt + 1,
            )
    return WarmResult(
        url=url,
        source="seed",
        origin=url,
        ok=False,
        skipped=False,
        status_code=None,
        elapsed_ms=None,
        bytes_read=0,
        error=last_error or "request failed",
        final_url=url,
        attempts=retries + 1,
    )


def warm_once(config: SiteWarmerConfig, fetcher: Callable[..., WarmResult] = fetch_url, logger=None, jsonl: JsonlLogger | None = None) -> CycleReport:
    started = utc_now()
    seeds = [ensure_http_url(url) for url in config.urls]
    if config.dry_run:
        discovered: list[DiscoveredURL] = []
        effective_interval = config.interval
    else:
        discovered, effective_interval = discover_plan(config)
    planned: list[DiscoveredURL] = [DiscoveredURL(url, "seed", url) for url in seeds] + discovered
    ordered_urls = dedupe_preserve([item.url for item in planned])

    results: list[WarmResult] = []
    summary = CycleSummary()
    host_last_request: dict[tuple[str, int | None], float] = {}

    for index, url in enumerate(ordered_urls):
        source = next((item.source for item in planned if item.url == url), "seed")
        origin = next((item.origin for item in planned if item.url == url), url)
        if not _should_include(url, config.include, config.exclude):
            result = WarmResult(url, source, origin, ok=False, skipped=True, error="filtered by include/exclude", attempts=0)
        elif not config.allow_external and not any(same_site(url, seed) for seed in seeds):
            result = WarmResult(url, source, origin, ok=False, skipped=True, error="external domain blocked", attempts=0)
        elif config.dry_run:
            result = WarmResult(url, source, origin, ok=True, skipped=True, error="dry-run", attempts=0)
        else:
            host_key = url_host_key(url)
            last_seen = host_last_request.get(host_key)
            if last_seen is not None:
                elapsed = time.time() - last_seen
                if elapsed < config.request_delay:
                    time.sleep(config.request_delay - elapsed)
            result = fetcher(
                url,
                timeout=config.timeout,
                retries=config.retries,
                user_agent=config.user_agent,
                read_limit=config.read_limit,
            )
            result.source = source
            result.origin = origin
            host_last_request[host_key] = time.time()
        results.append(result)
        summary.total += 1
        summary.bytes_read += result.bytes_read or 0
        if result.skipped:
            summary.skipped += 1
        elif result.ok:
            summary.ok += 1
        else:
            summary.failed += 1
        event = {"timestamp_utc": utc_now(), "result": asdict(result)}
        if jsonl:
            jsonl.write(event)
        if logger and not config.json_output:
            state = "SKIP" if result.skipped else ("OK" if result.ok else "FAIL")
            message = f"{state} {result.url} ({result.source})"
            if result.status_code is not None:
                message += f" status={result.status_code}"
            if result.elapsed_ms is not None:
                message += f" time={pretty_ms(result.elapsed_ms)}"
            if result.bytes_read is not None and result.bytes_read:
                message += f" bytes={pretty_bytes(result.bytes_read)}"
            if result.error:
                message += f" error={result.error}"
            logger.info(message)

    finished = utc_now()
    return CycleReport(
        started_at_utc=started,
        finished_at_utc=finished,
        results=results,
        summary=summary,
        targets=ordered_urls,
        mode="dry-run" if config.dry_run else ("continuous" if config.continuous or not config.once and config.interval > 0 else "once"),
        interval_seconds=effective_interval,
    )


def report_as_dict(report: CycleReport) -> dict[str, object]:
    return {
        "started_at_utc": report.started_at_utc,
        "finished_at_utc": report.finished_at_utc,
        "mode": report.mode,
        "interval_seconds": report.interval_seconds,
        "targets": report.targets,
        "summary": asdict(report.summary),
        "results": [asdict(item) for item in report.results],
    }


def format_plain_report(report: CycleReport) -> str:
    lines = [
        f"[{report.finished_at_utc}] mode={report.mode} targets={report.summary.total} ok={report.summary.ok} failed={report.summary.failed} skipped={report.summary.skipped}",
    ]
    for item in report.results:
        state = "SKIP" if item.skipped else ("OK" if item.ok else "FAIL")
        bits = [state, item.url]
        if item.status_code is not None:
            bits.append(f"status={item.status_code}")
        if item.elapsed_ms is not None:
            bits.append(f"time={pretty_ms(item.elapsed_ms)}")
        if item.error:
            bits.append(f"error={item.error}")
        lines.append("  " + " ".join(bits))
    return "\n".join(lines)


def run(config: SiteWarmerConfig, fetcher: Callable[..., WarmResult] = fetch_url, logger=None) -> int:
    with JsonlLogger(config.log_file) as jsonl:
        continuous = config.continuous or (not config.once and config.interval > 0)
        if config.interval < MIN_SAFE_INTERVAL and continuous and not config.dry_run:
            if logger:
                logger.warning(f"Warning: interval {config.interval}s is below the recommended minimum of {MIN_SAFE_INTERVAL}s.")
        try:
            while True:
                report = warm_once(config, fetcher=fetcher, logger=logger, jsonl=jsonl)
                if config.json_output:
                    print(json.dumps(report_as_dict(report), sort_keys=True, ensure_ascii=False))
                else:
                    print(format_plain_report(report))
                if config.once or config.dry_run or not continuous:
                    return 0 if report.summary.failed == 0 else 1
                time.sleep(report.interval_seconds)
        except KeyboardInterrupt:
            if logger:
                logger.info("Interrupted by user; shutting down cleanly.")
            return 130
