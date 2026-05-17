from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

from .utils import dedupe_preserve, ensure_http_url, same_site, strip_fragment


@dataclass(frozen=True)
class DiscoveredURL:
    url: str
    source: str
    origin: str


class _LinkCollector(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        href = href.strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            return
        self.links.append(urljoin(self.base_url, href))


def fetch_text(url: str, timeout: float, user_agent: str) -> str:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "text/plain,text/xml,text/html,*/*"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def _safe_robot_parser(seed_url: str, timeout: float, user_agent: str) -> RobotFileParser:
    parsed = urlparse(seed_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        text = fetch_text(robots_url, timeout=timeout, user_agent=user_agent)
    except (HTTPError, URLError, TimeoutError, OSError):
        parser.parse([])
        return parser
    parser.parse(text.splitlines())
    return parser


def sitemap_candidates(seed_url: str, timeout: float, user_agent: str) -> list[str]:
    parser = _safe_robot_parser(seed_url, timeout, user_agent)
    candidates = list(parser.site_maps() or [])
    root = ensure_http_url(seed_url)
    fallback = urljoin(root, "/sitemap.xml")
    if fallback not in candidates:
        candidates.append(fallback)
    robots_fallback = urljoin(root, "/robots.txt")
    robots_text = ""
    try:
        robots_text = fetch_text(robots_fallback, timeout=timeout, user_agent=user_agent)
    except (HTTPError, URLError, TimeoutError, OSError):
        pass
    for line in robots_text.splitlines():
        if line.lower().startswith("sitemap:"):
            candidate = line.split(":", 1)[1].strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)
    return dedupe_preserve(candidates)


def _extract_sitemap_urls(xml_text: str) -> tuple[str, list[str]]:
    root = ET.fromstring(xml_text)
    root_tag = root.tag.rsplit("}", 1)[-1].lower()
    urls: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() == "loc" and element.text:
            urls.append(element.text.strip())
    return root_tag, urls


def discover_from_sitemaps(seed_url: str, timeout: float, user_agent: str, limit: int) -> list[DiscoveredURL]:
    discovered: list[DiscoveredURL] = []
    visited_sitemaps: set[str] = set()
    queue = sitemap_candidates(seed_url, timeout, user_agent)
    origin = ensure_http_url(seed_url)

    while queue and len(discovered) < limit:
        sitemap_url = strip_fragment(queue.pop(0))
        if sitemap_url in visited_sitemaps:
            continue
        visited_sitemaps.add(sitemap_url)
        try:
            xml_text = fetch_text(sitemap_url, timeout=timeout, user_agent=user_agent)
            kind, urls = _extract_sitemap_urls(xml_text)
        except (HTTPError, URLError, TimeoutError, OSError, ET.ParseError):
            continue
        if kind == "sitemapindex":
            for nested in urls:
                nested = strip_fragment(nested)
                if nested not in visited_sitemaps and nested not in queue:
                    queue.append(nested)
            continue
        for page_url in urls:
            candidate = strip_fragment(page_url)
            if not same_site(candidate, origin):
                continue
            discovered.append(DiscoveredURL(candidate, "sitemap", sitemap_url))
            if len(discovered) >= limit:
                break
    return discovered


def discover_from_links(seed_url: str, timeout: float, user_agent: str, limit: int, allow_external: bool = False) -> list[DiscoveredURL]:
    origin = ensure_http_url(seed_url)
    parsed = urlparse(origin)
    homepage = f"{parsed.scheme}://{parsed.netloc}/"
    collector = _LinkCollector(homepage)
    try:
        html_text = fetch_text(homepage, timeout=timeout, user_agent=user_agent)
    except (HTTPError, URLError, TimeoutError, OSError):
        return []
    collector.feed(html_text)
    discovered: list[DiscoveredURL] = []
    for raw_link in collector.links:
        candidate = strip_fragment(raw_link)
        if not allow_external and not same_site(candidate, origin):
            continue
        if candidate == origin:
            continue
        discovered.append(DiscoveredURL(candidate, "links", homepage))
        if len(discovered) >= limit:
            break
    return discovered


def discover_targets(seed_urls: Iterable[str], mode: str, timeout: float, user_agent: str, limit: int, allow_external: bool = False) -> list[DiscoveredURL]:
    discovered: list[DiscoveredURL] = []
    for seed in seed_urls:
        if mode in {"sitemap", "both"}:
            discovered.extend(discover_from_sitemaps(seed, timeout=timeout, user_agent=user_agent, limit=limit))
        if mode in {"links", "both"}:
            discovered.extend(discover_from_links(seed, timeout=timeout, user_agent=user_agent, limit=limit, allow_external=allow_external))
    seen: set[str] = set()
    unique: list[DiscoveredURL] = []
    for item in discovered:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return unique[:limit]
