# sitewarmer

Lightweight Python CLI for warming and checking selected website URLs without turning into a load tester.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![setuptools](https://img.shields.io/badge/Build-setuptools-2D9CDB?style=for-the-badge&logo=python&logoColor=white)](https://setuptools.pypa.io/)
[![unittest](https://img.shields.io/badge/Tests-unittest-4CAF50?style=for-the-badge&logo=python&logoColor=white)](https://docs.python.org/3/library/unittest.html)
[![GitHub Actions](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![MIT License](https://img.shields.io/badge/License-MIT-success?style=for-the-badge)](LICENSE)
[![v0.1.0](https://img.shields.io/badge/Release-v0.1.0-0F8B8D?style=for-the-badge)](https://github.com/Clock-Skew/sitewarmer/releases/tag/v0.1.0)

![sitewarmer social preview](assets/sitewarmer-social-preview.jpg)

## What It Does

`sitewarmer` periodically requests one or more URLs on a site to help keep small or shared-hosted sites responsive, confirm uptime, and improve perceived first-load responsiveness for real users.

It can:

- warm explicit URLs
- discover more URLs from `sitemap.xml`
- discover internal links from the homepage
- enforce conservative rate limits
- respect `robots.txt`
- output JSON or readable terminal summaries
- append local JSONL logs

## What It Does Not Do

This is not:

- a load tester
- a stress tester
- a DDoS tool
- a scraper farm
- a bypass tool for robots or access controls

## Ethical Use

Use this only on websites you own, operate, or are explicitly authorized to check. Keep intervals conservative. Do not use it to generate aggressive traffic.

## Features

- One or more target URLs
- One-shot mode
- Continuous mode
- Dry-run mode
- Configurable interval and timeout
- Retry limits
- Custom `User-Agent`
- Sitemap discovery
- Internal homepage link discovery
- Bounded same-site link depth with `--max-depth`
- Discovery result limiting
- Include/exclude patterns
- JSON output
- Plain terminal summaries
- Local JSONL log file support
- Graceful `Ctrl+C` shutdown
- Safe URL validation
- External-domain blocking by default
- Robots-aware fetch decisions

## Installation

```bash
cd /path/to/sitewarmer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

No third-party runtime dependencies are required.

## Quick Start

Warm one URL once:

```bash
sitewarmer https://example.com --once
```

Warm continuously every 5 minutes:

```bash
sitewarmer https://example.com --interval 300
```

`sitewarmer` runs continuously by default. Add `--once` when you want a single cycle.

Discover sitemap URLs first:

```bash
sitewarmer https://example.com --discover sitemap --limit 25
```

Discover sitemap URLs and homepage links together:

```bash
sitewarmer https://example.com --discover both --limit 25
```

Discover internal homepage links:

```bash
sitewarmer https://example.com --discover links --max-depth 1 --exclude "/admin" --exclude "/cart"
```

JSON output:

```bash
sitewarmer https://example.com --once --json
```

Write a log file:

```bash
sitewarmer https://example.com --log-file warmer.log
```

## CLI Reference

| Option | Meaning |
| --- | --- |
| `urls` | One or more target URLs |
| `--interval SECONDS` | Delay between cycles in continuous mode. Default: `300` |
| `--timeout SECONDS` | Request timeout. Default: `10` |
| `--retries N` | Retry count for transient failures. Default: `2` |
| `--user-agent UA` | Custom `User-Agent` string |
| `--discover none|sitemap|links|both` | Optional discovery mode |
| `--limit N` | Maximum discovered URLs to add per run. Default: `10` |
| `--max-depth N` | Maximum same-site link hops beyond the homepage for `links` or `both` discovery. Default: `0` |
| `--include PATTERN` | Include filter. Repeatable |
| `--exclude PATTERN` | Exclude filter. Repeatable |
| `--allow-external` | Allow external discovered URLs |
| `--dry-run` | Plan the run without requests |
| `--once` | Run one cycle and exit |
| `--continuous` | Keep running until interrupted. This is also the default when `--once` is not used |
| `--json` | Emit JSON output |
| `--log-file PATH` | Append JSONL event logs to a file |
| `--read-limit BYTES` | Max bytes read per response. Default: `262144` |
| `--request-delay SECONDS` | Minimum per-host delay inside a cycle. Default: `1.0` |
| `-v, --verbose` | Verbose plain-text logging |

## Example Output

```text
[2026-05-17T00:00:00Z] mode=once targets=2 ok=2 failed=0 skipped=0
  OK https://example.com/ status=200 time=143ms bytes=24.0KiB
  OK https://example.com/blog status=200 time=98ms bytes=18.2KiB
```

JSON example:

```json
{
  "finished_at_utc": "2026-05-17T00:00:00Z",
  "interval_seconds": 300,
  "mode": "once",
  "results": [
    {
      "attempts": 1,
      "bytes_read": 24576,
      "elapsed_ms": 143.2,
      "error": null,
      "final_url": "https://example.com/",
      "ok": true,
      "origin": "https://example.com/",
      "skipped": false,
      "source": "seed",
      "status_code": 200,
      "url": "https://example.com/"
    }
  ],
  "started_at_utc": "2026-05-17T00:00:00Z",
  "summary": {
    "bytes_read": 24576,
    "failed": 0,
    "ok": 1,
    "skipped": 0,
    "total": 1
  },
  "targets": [
    "https://example.com/"
  ]
}
```

## Sitemap Discovery

`--discover sitemap` checks `robots.txt` for sitemap hints, then tries the site’s sitemap candidates, including `site_maps()` support from Python’s `urllib.robotparser`, and finally `/sitemap.xml` as a fallback.

Only same-site URLs are kept unless `--allow-external` is explicitly set.

## Link Discovery

`--discover links` fetches the homepage and extracts internal links from anchor tags. By default it stays one hop wide from the homepage. Raise `--max-depth` to let it follow a bounded number of same-site hops, and keep `--limit` low for small sites.

`--discover both` combines sitemap discovery and link discovery in one pass. This is the most useful mode for small, stable sites that already have a sitemap but also expose a few important internal links from the homepage.

## Safety and Rate Limiting

- Default interval: `300` seconds
- Default request timeout: `10` seconds
- Default retries: `2`
- Default per-host delay inside a cycle: `1` second
- External URLs are blocked unless `--allow-external` is given
- `robots.txt` is checked before warming targets
- `--dry-run` performs no requests

If you need something more aggressive than that, you are outside the intended use case.

## Cron Example

```cron
*/5 * * * * /path/to/sitewarmer/.venv/bin/sitewarmer https://example.com --once --log-file /var/log/sitewarmer.jsonl
```

## systemd Timer Example

`/etc/systemd/system/sitewarmer.service`

```ini
[Unit]
Description=SiteWarmer one-shot check

[Service]
Type=oneshot
ExecStart=/path/to/sitewarmer/.venv/bin/sitewarmer https://example.com --once --log-file /var/log/sitewarmer.jsonl
```

`/etc/systemd/system/sitewarmer.timer`

```ini
[Unit]
Description=Run SiteWarmer every 5 minutes

[Timer]
OnBootSec=1m
OnUnitActiveSec=5m
Unit=sitewarmer.service

[Install]
WantedBy=timers.target
```

## Logging

Use `--log-file` to append JSONL events. Each run records timestamped URL results with status, response time, bytes read, and error reason when present.

## Use Cases

### Shared Hosting

Keep a small site responsive without hammering the host. Use a conservative interval and sitemap discovery only if the site is small and stable.

### Small Business Site

Warm the homepage, contact page, services page, or a short sitemap list so the first real customer visit does not hit a cold start.

### Developer or Staging Site

Confirm uptime during demos, deployments, or maintenance windows without introducing noisy traffic.

## Troubleshooting

- `invalid URL`: include `https://` or a valid host name
- `robots.txt blocks a page`: the tool is respecting the site rules
- `No output in continuous mode`: check `--json`, `--verbose`, or `--log-file`
- `Too many discovered URLs`: lower `--limit` or narrow `--include` / `--exclude`
- `Unexpected external URLs`: remove `--allow-external`

## Testing

```bash
python3 -m unittest discover -s tests
python3 -m compileall sitewarmer tests
python3 -m sitewarmer https://example.com --once
```

## Roadmap

- optional per-host scheduling
- richer status summaries
- package publishing
- release tagging and changelog workflow
- explicit sitemap index reporting

## Contributing

Keep changes small, safe, and readable. Do not add aggressive crawling, scraping, or load generation.

## License

MIT. See [LICENSE](LICENSE).
