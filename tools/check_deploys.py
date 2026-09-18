#!/usr/bin/env python3
"""Compare what each Worker is SERVING against what the repository says it should serve.

    python tools/check_deploys.py [--quiet]

WHY: ten Workers deploy from this repo, and only cpi-lab redeploys itself. For
the other nine, editing a file and forgetting to run `wrangler deploy` leaves the
live site quietly behind the source, with nothing to notice it. That has already
happened twice here — a cpi-lab site fix that reached the public repo but not the
deployed page, and the pipeline host's nginx copy drifting from the repo — so this makes the
question answerable instead of a memory exercise.

WHAT IT DOES NOT CHECK:

  - Data. cpi-lab serves JSON staged from the pipeline host, which is normally
    *fresher* than the copy on this machine; comparing it would fail every day
    for the wrong reason. Only code and markup are compared.
  - The Pulse Worker scripts (src/index.js). Those run server-side and are not
    fetchable, so only their static assets are compared. A framework change with
    no asset change is invisible here.

Two things would otherwise produce false alarms, and are handled:

  - Line endings. This working tree is Windows and checks out CRLF, while the
    deployed bytes are LF (wrangler on Windows, or a Linux clone on the pipeline
    host). Everything is normalised to LF before hashing.
  - cpi-lab is transformed before deploy: publish.py removes the ZORI shelter
    panel and neuters its renderer. Comparing the raw source would always differ,
    so the same transform is applied to a scratch copy first — reusing
    publish.py's implementation rather than restating it.

Exit status: 0 when every Worker matches, 2 when something is behind, 1 on a
fetch or setup error.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (label, origin, {served path: repo path}, transform)
TARGETS: list[tuple[str, str, dict[str, str], str | None]] = [
    ("masthead", "https://bristleconeanalytics.com",
     {"index.html": "web/public/index.html"}, None),
    # publish.py copies output/explorer.html to .site/index.html unchanged.
    ("census", "https://census.bristleconeanalytics.com",
     {"index.html": "census/output/explorer.html"}, None),
    ("cpi-lab", "https://cpi.bristleconeanalytics.com",
     {"index.html": "cpi-lab/site/index.html",
      "app.js": "cpi-lab/site/app.js",
      "charts.js": "cpi-lab/site/charts.js",
      "styles.css": "cpi-lab/site/styles.css"}, "cpi"),
    ("safetyspend", "https://safetyspend.bristleconeanalytics.com",
     {"index.html": "city-safety-spend/site/index.html",
      "findings.html": "city-safety-spend/site/findings.html"}, None),
]
for app in ("gridpulse", "econpulse", "healthpulse", "skypulse", "netpulse", "computepulse"):
    TARGETS.append((app, f"https://{app}.bristleconeanalytics.com",
                    {"index.html": f"pulse/{app}/public/index.html",
                     "app.js": f"pulse/{app}/public/app.js",
                     "style.css": f"pulse/{app}/public/style.css"}, None))


# Cloudflare Web Analytics injects its beacon immediately before </body> on every
# HTML response — 367 bytes that are in none of the source files. Left in, every
# page reports as drifted forever, which would train us to ignore this check.
BEACON = re.compile(
    rb'<script[^>]*static\.cloudflareinsights\.com[^>]*>\s*</script>\s*')


def norm(b: bytes) -> str:
    """Hash after removing the two differences that are never real: the platform's
    injected beacon, and CRLF from a Windows checkout."""
    return hashlib.sha256(BEACON.sub(b"", b).replace(b"\r\n", b"\n")).hexdigest()


def cpi_expected(tmp: Path) -> dict[str, Path]:
    """Apply publish.py's shelter-panel removal to a scratch copy of the source."""
    sys.path.insert(0, str(ROOT / "cpi-lab"))
    import publish  # noqa: E402  reuse the one implementation

    for name in ("index.html", "app.js", "charts.js", "styles.css"):
        shutil.copyfile(ROOT / "cpi-lab" / "site" / name, tmp / name)
    publish.omit_shelter_panel(tmp)
    return {n: tmp / n for n in ("index.html", "app.js", "charts.js", "styles.css")}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "bristlecone-deploy-check"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true", help="print only drift and errors")
    a = ap.parse_args()

    behind, errors, matched = [], 0, 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        try:
            cpi_files = cpi_expected(tmp)
        except Exception as e:                       # noqa: BLE001
            print(f"  ERROR  cpi-lab transform failed: {type(e).__name__}: {e}")
            cpi_files, errors = {}, errors + 1

        for label, origin, files, transform in TARGETS:
            diffs = []
            for served, repo_rel in files.items():
                local = (cpi_files.get(served) if transform == "cpi"
                         else ROOT / repo_rel)
                if local is None or not Path(local).exists():
                    print(f"  ERROR  {label}/{served}: no local file ({repo_rel})")
                    errors += 1
                    continue
                try:
                    got = fetch(f"{origin}/{served}")
                except urllib.error.HTTPError as e:
                    if e.code in (301, 302, 307, 308, 404) and served == "index.html":
                        try:
                            got = fetch(origin)       # some serve the root instead
                        except Exception as e2:       # noqa: BLE001
                            print(f"  ERROR  {label}/{served}: {type(e2).__name__}")
                            errors += 1
                            continue
                    else:
                        print(f"  ERROR  {label}/{served}: HTTP {e.code}")
                        errors += 1
                        continue
                except Exception as e:                # noqa: BLE001
                    print(f"  ERROR  {label}/{served}: {type(e).__name__}")
                    errors += 1
                    continue

                if norm(got) == norm(Path(local).read_bytes()):
                    matched += 1
                else:
                    diffs.append(f"{served} (served {len(got)}B, repo "
                                 f"{Path(local).stat().st_size}B)")
            if diffs:
                behind.append(label)
                print(f"  BEHIND {label}: {', '.join(diffs)}")
            elif not a.quiet:
                print(f"  ok     {label}: {len(files)} asset(s) match")

    print(f"deploys: {matched} assets match, {len(behind)} worker(s) behind, "
          f"{errors} error(s)")
    if behind:
        print("         run `npx wrangler deploy` in the directory for each one above")
    if errors:
        return 1
    return 2 if behind else 0


if __name__ == "__main__":
    sys.exit(main())
