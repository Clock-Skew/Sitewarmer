from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from sitewarmer.core import CycleSummary, SiteWarmerConfig, WarmResult, report_as_dict, warm_once


class CoreTests(TestCase):
    def test_warm_once_with_fake_fetcher(self) -> None:
        config = SiteWarmerConfig(urls=["https://example.com"], once=True)

        def fake_fetcher(url: str, **kwargs):
            return WarmResult(
                url=url,
                source="seed",
                origin=url,
                ok=True,
                skipped=False,
                status_code=200,
                elapsed_ms=12.5,
                bytes_read=128,
                final_url=url,
                attempts=1,
            )

        with patch("sitewarmer.core.discover_plan", return_value=([], 300)):
            report = warm_once(config, fetcher=fake_fetcher)

        self.assertEqual(report.summary, CycleSummary(total=1, ok=1, failed=0, skipped=0, bytes_read=128))
        self.assertEqual(report.results[0].status_code, 200)
        self.assertTrue(report.results[0].ok)

    def test_dry_run_skips_fetch(self) -> None:
        config = SiteWarmerConfig(urls=["https://example.com"], once=True, dry_run=True)

        def fail_fetcher(*args, **kwargs):
            raise AssertionError("fetcher should not be called in dry-run mode")

        with patch("sitewarmer.core.discover_plan", return_value=([], 300)):
            report = warm_once(config, fetcher=fail_fetcher)

        self.assertEqual(report.summary.total, 1)
        self.assertEqual(report.summary.skipped, 1)
        self.assertEqual(report.results[0].error, "dry-run")

    def test_report_as_dict_is_json_ready(self) -> None:
        config = SiteWarmerConfig(urls=["https://example.com"], once=True)

        def fake_fetcher(url: str, **kwargs):
            return WarmResult(
                url=url,
                source="seed",
                origin=url,
                ok=True,
                skipped=False,
                status_code=200,
                elapsed_ms=9.0,
                bytes_read=64,
                final_url=url,
                attempts=1,
            )

        with patch("sitewarmer.core.discover_plan", return_value=([], 300)):
            report = warm_once(config, fetcher=fake_fetcher)

        payload = report_as_dict(report)
        self.assertEqual(payload["summary"]["ok"], 1)
        self.assertEqual(payload["results"][0]["url"], "https://example.com/")

