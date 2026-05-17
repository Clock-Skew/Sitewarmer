# Local Docs Used

This project was built with the local Python documentation index first.

Useful local docs and what they informed:

- `/home/smith/codex/agent/docs/python-3.14-docs-text/library/argparse.txt`
  - used for CLI design, option parsing, choices, defaults, and help text
- `/home/smith/codex/agent/docs/python-3.14-docs-text/library/urllib.request.txt`
  - used for `Request` headers, custom `User-Agent`, timeouts, and `urlopen`
- `/home/smith/codex/agent/docs/python-3.14-docs-text/library/urllib.robotparser.txt`
  - used for `RobotFileParser`, robots.txt handling, and `site_maps()`
- `/home/smith/codex/agent/docs/python-3.14-docs-text/library/html.parser.txt`
  - used for safe homepage link extraction with `HTMLParser`
- `/home/smith/codex/agent/docs/python-3.14-docs-text/library/xml.etree.elementtree.txt`
  - used for sitemap XML parsing
- `/home/smith/codex/agent/docs/python-3.14-docs-text/library/json.txt`
  - used for JSON output and JSONL event logging
- `/home/smith/codex/agent/docs/python-3.14-docs-text/howto/logging-cookbook.txt`
  - used for practical CLI logging shape and command-line-controlled verbosity

Fallback rule:

1. Use the local docs index first.
2. Use repo-local source when the answer depends on this project.
3. Use official online docs or live web browsing when the local docs are missing, stale, or incomplete.

