from __future__ import annotations

import unittest

from sitewarmer.discovery import _LinkCollector, _extract_sitemap_urls
from sitewarmer.utils import ensure_http_url, matches_any, path_and_query, same_site


class UtilsTests(unittest.TestCase):
    def test_ensure_http_url_normalizes_scheme_and_path(self) -> None:
        self.assertEqual(ensure_http_url("example.com"), "https://example.com/")

    def test_same_site_handles_www_alias(self) -> None:
        self.assertTrue(same_site("https://www.example.com/blog", "https://example.com/"))

    def test_matches_any_uses_fnmatch(self) -> None:
        self.assertTrue(matches_any("/admin/users", ["*/admin*", "*users"]))
        self.assertFalse(matches_any("/blog", ["*/admin*"]))

    def test_path_and_query_preserves_query(self) -> None:
        self.assertEqual(path_and_query("https://example.com/a/b?x=1"), "/a/b?x=1")

    def test_link_collector_extracts_a_tags(self) -> None:
        parser = _LinkCollector("https://example.com/")
        parser.feed(
            """
            <html><body>
              <a href="/about">About</a>
              <a href="https://example.com/contact">Contact</a>
              <a href="https://evil.test/">External</a>
            </body></html>
            """
        )
        self.assertIn("https://example.com/about", parser.links)
        self.assertIn("https://example.com/contact", parser.links)

    def test_extract_sitemap_urls_returns_locs(self) -> None:
        root, urls = _extract_sitemap_urls(
            """<?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://example.com/</loc></url>
              <url><loc>https://example.com/blog</loc></url>
            </urlset>
            """
        )
        self.assertEqual(root, "urlset")
        self.assertEqual(urls, ["https://example.com/", "https://example.com/blog"])


if __name__ == "__main__":
    unittest.main()

