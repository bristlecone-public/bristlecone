#!/usr/bin/env python3
"""Stage cpi-lab/.site/ for the Cloudflare deploy, then `npx wrangler deploy`.

    python tools/public-mirror/prepare_data.py    # once, to refresh + strip ZORI
    python cpi-lab/publish.py
    cd cpi-lab && npx wrangler deploy

The dashboard fetches `/data/<pipeline>.json` at runtime, so the assets tree has
to carry the pipeline outputs next to the page. They are taken from
.mirror-data/cpi-lab/, which is the same staging directory the public repo
mirror publishes from — deliberately, so the ZORI strip has exactly one
implementation (tools/public-mirror/prepare_data.py) and the website and the
repo cannot drift apart on it.

Zillow's Terms of Use §4(C) prohibit *displaying* their data as well as
redistributing it, so the p9_metro.json served here is the stripped copy, same
as the one in the repo.

NOTE ON FRESHNESS: this publishes a snapshot. The pipeline host keeps running on
its own cron and its nginx copy stays live; nothing here updates Cloudflare
automatically. Re-run this after a pipeline refresh, or add a deploy step to the
host's cron.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

# P9's shelter panel is the CPI-rent vs ZORI comparison. With ZORI stripped it
# renders "gap — pp · best lag — (r —)" placeholders under a legend still
# advertising a Zillow series, and ZORI runs through the surrounding prose and
# the provenance table too. Zillow's terms prohibit displaying their data, so
# the public build removes the panel outright and says why. The rest of P9 —
# metro real wages and cross-metro dispersion — is not ZORI-derived and stays.
OMITTED_PANEL = '''<div class="panel">
    <h3>CPI rent vs the asking-rent market &mdash; omitted here</h3>
    <p class="isnt">This panel compares each metro&rsquo;s CPI rent of primary residence against the
       Zillow Observed Rent Index. Zillow&rsquo;s terms of use do not permit republishing or displaying
       values derived from ZORI, so it is not part of this public copy. The pipeline
       (<code>pipelines/p9_metro.py</code>) is unchanged and records the exact source file, so you can
       download ZORI from Zillow under their own terms and reproduce this panel in full.</p>
  </div>

  '''

# Absent from the built files, or the build fails. Each is a thing that would
# otherwise render a broken chart or point at data we do not ship.
FORBIDDEN = [
    ('index.html', 'id="p9Shelter"'),
    ('index.html', 'p9ShelterNote'),
    ('index.html', 'zillow.com/research'),
    ('app.js', 'p9Shelter(p9);'),
    ('app.js', "'p9Shelter'"),
    ('app.js', 'shelter vs ZORI small multiples'),
]


def omit_shelter_panel(site: Path) -> None:
    """Remove the ZORI panel, its prose, its render call and its source entry."""
    html = (site / "index.html").read_text(encoding="utf-8")
    html, n = re.subn(
        r'<div class="panel">\s*<h3>CPI rent vs the asking-rent market.*?(?=<div class="panel">)',
        OMITTED_PANEL, html, flags=re.S)
    if n != 1:
        raise SystemExit(f"shelter panel: expected 1 match, got {n} — markup changed")
    # The ZORI entry in the sources list.
    html, n = re.subn(
        r'[ \t]*<li><a href="https://www\.zillow\.com/research/data/".*?</li>\n',
        "", html, flags=re.S)
    if n != 1:
        raise SystemExit(f"ZORI source entry: expected 1 match, got {n}")
    (site / "index.html").write_text(html, encoding="utf-8", newline="\n")

    js = (site / "app.js").read_text(encoding="utf-8")
    # $('p9ShelterNote').innerHTML is unguarded, so the renderer must not run.
    js, a = re.subn(r"^(\s*)p9Shelter\(p9\);",
                    r"\1/* shelter panel omitted in the public build - Zillow ToU */",
                    js, flags=re.M)
    js, b = re.subn(r"'p9Real', 'p9Shelter', 'p9Disp'", "'p9Real', 'p9Disp'", js)
    js, c = re.subn(r"shelter vs ZORI small multiples, ", "", js)
    # Drop the renderer itself, so no dead code references the removed DOM.
    js, d = re.subn(r"^function p9Shelter\(p9\) \{.*?(?=^function )", "",
                    js, flags=re.S | re.M)
    if (a, b, c, d) != (1, 1, 1, 1):
        raise SystemExit(f"app.js edits: expected (1,1,1,1), got {(a, b, c, d)}")
    (site / "app.js").write_text(js, encoding="utf-8", newline="\n")

    for name, marker in FORBIDDEN:
        if marker in (site / name).read_text(encoding="utf-8"):
            raise SystemExit(f"{name} still contains {marker!r}")
    print("  shelter panel omitted; app.js render call neutered; checks passed")

ROOT = Path(__file__).resolve().parent
SITE_SRC = ROOT / "site"
DATA_SRC = ROOT.parent / ".mirror-data" / "cpi-lab"
SITE = ROOT / ".site"

# The page loads exactly these; see site/app.js FILES.
FILES = [
    "p1_salience.json", "p2_distribution.json", "p3_persistence.json",
    "p4_vintages.json", "p5_quality.json", "p6_pipeline.json",
    "p7_tariff.json", "p8_chained.json", "p9_metro.json",
    "p10_network.json", "r1_expectations.json",
]
ASSETS = ["index.html", "app.js", "charts.js", "styles.css"]


def main() -> None:
    if not DATA_SRC.exists():
        raise SystemExit(
            f"missing {DATA_SRC}\n"
            "run: python tools/public-mirror/prepare_data.py (fetches the "
            "pipeline outputs and strips ZORI)")

    # Clear the contents rather than the directory itself: on Windows a preview
    # server whose cwd is .site/ blocks removing the directory, but not the
    # files inside it.
    if SITE.exists():
        for child in SITE.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    (SITE / "data").mkdir(parents=True, exist_ok=True)

    for name in ASSETS:
        src = SITE_SRC / name
        if not src.exists():
            raise SystemExit(f"missing {src}")
        shutil.copyfile(src, SITE / name)

    for name in FILES:
        src = DATA_SRC / name
        if not src.exists():
            raise SystemExit(f"missing {src} — re-run prepare_data.py")
        shutil.copyfile(src, SITE / "data" / name)

    # Fail loudly rather than publish Zillow-derived values by accident.
    p9 = json.loads((SITE / "data" / "p9_metro.json").read_text(encoding="utf-8"))
    if "best_lag_table" in p9 or any(
            "zori_yoy_l12" in (m.get("latest_shelter") or {}) for m in p9.get("metros", [])):
        raise SystemExit("p9_metro.json still carries ZORI-derived values — "
                         "re-run tools/public-mirror/prepare_data.py")

    omit_shelter_panel(SITE)

    n = len(list(SITE.rglob("*")))
    total = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"staged {n} files, {total/1e6:.1f} MB -> {SITE}  (ZORI strip verified)")
    print("now: cd cpi-lab && npx wrangler deploy")


if __name__ == "__main__":
    main()
