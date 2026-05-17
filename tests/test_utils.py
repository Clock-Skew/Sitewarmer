from __future__ import annotations

import unittest
from urllib.error import URLError

from sitewarmer.discovery import _LinkCollector, _extract_sitemap_urls, discover_from_links, discover_from_sitemaps
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

    @unittest.mock.patch("sitewarmer.discovery.fetch_text")
    def test_discover_from_sitemaps_follows_nested_indexes(self, mock_fetch_text) -> None:
        def fake_fetch(url: str, timeout: float, user_agent: str) -> str:
            pages = {
                "https://example.com/robots.txt": "Sitemap: https://example.com/sitemap-index.xml\n",
                "https://example.com/sitemap-index.xml": """<?xml version="1.0" encoding="UTF-8"?>
                <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <sitemap><loc>https://example.com/blog-sitemap.xml</loc></sitemap>
                </sitemapindex>
                """,
                "https://example.com/blog-sitemap.xml": """<?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <url><loc>https://example.com/blog/post-1</loc></url>
                  <url><loc>https://example.com/blog/post-2</loc></url>
                </urlset>
                """,
            }
            if url not in pages:
                raise URLError(url)
            return pages[url]

        mock_fetch_text.side_effect = fake_fetch
        discovered = discover_from_sitemaps("https://example.com", timeout=1.0, user_agent="sitewarmer/0.1", limit=10)
        self.assertEqual([item.url for item in discovered], ["https://example.com/blog/post-1", "https://example.com/blog/post-2"])

    @unittest.mock.patch("sitewarmer.discovery.fetch_text")
    def test_discover_from_links_honors_max_depth(self, mock_fetch_text) -> None:
        def fake_fetch(url: str, timeout: float, user_agent: str) -> str:
            pages = {
                "https://example.com/": '<a href="/one">One</a>',
                "https://example.com/one": '<a href="/two">Two</a>',
                "https://example.com/two": '<a href="/three">Three</a>',
            }
            if url not in pages:
                raise URLError(url)
            return pages[url]

        mock_fetch_text.side_effect = fake_fetch
        shallow = discover_from_links("https://example.com", timeout=1.0, user_agent="sitewarmer/0.1", limit=10, max_depth=0)
        deeper = discover_from_links("https://example.com", timeout=1.0, user_agent="sitewarmer/0.1", limit=10, max_depth=1)
        self.assertEqual([item.url for item in shallow], ["https://example.com/one"])
        self.assertEqual([item.url for item in deeper], ["https://example.com/one", "https://example.com/two"])


if __name__ == "__main__":
    unittest.main()
