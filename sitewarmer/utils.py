from __future__ import annotations

from fnmatch import fnmatch
from urllib.parse import urldefrag, urlparse, urlunparse


DEFAULT_PATH = "/"
DEFAULT_INTERVAL = 300
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 2
DEFAULT_LIMIT = 10
DEFAULT_READ_LIMIT = 256 * 1024
DEFAULT_REQUEST_DELAY = 1.0
MIN_SAFE_INTERVAL = 30


def ensure_http_url(raw: str) -> str:
    value = raw.strip()
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"unsupported URL scheme: {parsed.scheme or '<missing>'}")
    if not parsed.netloc:
        raise ValueError(f"invalid URL: {raw!r}")
    cleaned = parsed._replace(fragment="")
    path = cleaned.path or DEFAULT_PATH
    if not path.startswith("/"):
        path = f"/{path}"
    cleaned = cleaned._replace(path=path)
    return urlunparse(cleaned)


def strip_fragment(url: str) -> str:
    return urldefrag(url)[0]


def url_host_key(url: str) -> tuple[str, int | None]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host, parsed.port


def same_site(candidate: str, reference: str) -> bool:
    cand_host, cand_port = url_host_key(candidate)
    ref_host, ref_port = url_host_key(reference)
    if not cand_host or not ref_host:
        return False
    if cand_host != ref_host:
        return False
    if cand_port == ref_port:
        return True
    return cand_port is None and ref_port in {80, 443, None} or ref_port is None and cand_port in {80, 443, None}


def path_and_query(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path


def matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch(value, pattern) for pattern in patterns)


def dedupe_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def pretty_ms(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{int(round(float(value)))}ms"


def pretty_bytes(value: int | None) -> str:
    if value is None:
        return "n/a"
    units = ["B", "KiB", "MiB", "GiB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)}{unit}"
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{value}B"

