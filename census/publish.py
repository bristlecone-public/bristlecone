#!/usr/bin/env python3
"""Stage census/.site/ for the Cloudflare deploy, then `npx wrangler deploy`.

output/ holds ~158 MB of cohort-flow CSVs alongside the two published
artifacts, and one of them is over Cloudflare's 25 MB per-asset limit, so the
assets directory cannot point at output/ directly. This copies just what should
be served into .site/ (gitignored).

    python census/publish.py && cd census && npx wrangler deploy

explorer.html is self-contained — the county topology and every flow figure are
embedded — so it is served as the front page with no other assets needed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
SITE = ROOT / ".site"


def main() -> None:
    explorer = OUT / "explorer.html"
    report = OUT / "report.md"
    if not explorer.exists():
        raise SystemExit(f"missing {explorer} — run `make explorer` first")

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()

    # The explorer is the deliverable for a browser, so it is the front page.
    shutil.copyfile(explorer, SITE / "index.html")
    # Keep the canonical name working for anyone who links it.
    shutil.copyfile(explorer, SITE / "explorer.html")
    if report.exists():
        shutil.copyfile(report, SITE / "report.md")

    total = sum(f.stat().st_size for f in SITE.iterdir())
    print(f"staged {len(list(SITE.iterdir()))} files, {total/1e6:.1f} MB -> {SITE}")
    print("now: cd census && npx wrangler deploy")


if __name__ == "__main__":
    main()
