#!/usr/bin/env python3
"""Check the prose figures on the CPI Lab page against the live pipeline JSON.

    python3 cpi-lab/drift_check.py [--site <index.html>] [--data-dir <out/>]

WHY: the charts on that page re-read their JSON on every load, so they cannot go
stale. The prose can, and silently — it is full of figures that were measured
once and typed in. The replica correlation, the number of months in a comparison
window, the share of the basket a pipeline covers: each was right the day it was
written and has no way to announce the month it stops being.

So a figure that has a machine-readable counterpart carries it in the markup:

    <span data-check="p2:validation.replica_mom.n" data-round="0">318</span>

`data-check` is `<pipeline>:<dotted.path>`, where a list index is `[0]`.
`data-round` is the number of decimal places to compare at — the prose rounds,
the JSON does not, so 0.9715 and "0.972" agree at 3 places. `data-tol` allows an
absolute tolerance instead, for a figure quoted as approximate.

Binding the number where it is written, rather than in a separate manifest, is
deliberate: editing the sentence puts the binding directly in front of whoever
is editing it. A manifest would be one more thing to forget.

This REPORTS; it does not block. Publishing month-old prose alongside fresh data
is bad, but refusing to publish fresh data because a sentence drifted is worse.
Exit status is 0 when everything agrees, 2 when something has drifted, and 1 on
a real error (a missing file, a path that does not resolve) — the last of which
means the check itself is broken and should be fixed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# <span data-check="..." data-round="..." data-tol="...">TEXT</span>, attributes
# in any order. Deliberately narrow: only a span, only a plain-number body.
TAG = re.compile(
    r'<span\b(?P<attrs>[^>]*\bdata-check="(?P<path>[^"]+)"[^>]*)>(?P<text>[^<]*)</span>')
ATTR = re.compile(r'\bdata-(round|tol)="([^"]*)"')


def resolve(doc: dict, path: str):
    """Walk a dotted path with [i] list indices. Raises KeyError with context."""
    cur = doc
    for part in path.split("."):
        m = re.fullmatch(r"(\w*)\[(\d+)\]", part)
        if m:
            if m.group(1):
                cur = cur[m.group(1)]
            cur = cur[int(m.group(2))]
        else:
            if not isinstance(cur, dict) or part not in cur:
                raise KeyError(f"{path!r}: no {part!r}")
            cur = cur[part]
    return cur


def load(data_dir: Path, pipeline: str) -> dict:
    hits = sorted(data_dir.glob(f"{pipeline}_*.json"))
    if not hits:
        raise SystemExit(f"drift: no {pipeline}_*.json in {data_dir}")
    return json.loads(hits[0].read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", type=Path, default=ROOT / "site" / "index.html")
    ap.add_argument("--data-dir", type=Path, default=ROOT / ".site" / "data")
    ap.add_argument("--quiet", action="store_true",
                    help="print only drift and errors, not the agreeing figures")
    a = ap.parse_args()

    html = a.site.read_text(encoding="utf-8")
    cache: dict[str, dict] = {}
    checked = drifted = errors = 0

    for m in TAG.finditer(html):
        spec, shown = m.group("path"), m.group("text").strip()
        opts = dict((k, v) for k, v in ATTR.findall(m.group("attrs")))
        if ":" not in spec:
            print(f"  ERROR  {spec}: expected <pipeline>:<path>")
            errors += 1
            continue
        pipeline, path = spec.split(":", 1)
        try:
            if pipeline not in cache:
                cache[pipeline] = load(a.data_dir, pipeline)
            live = resolve(cache[pipeline], path)
        except (KeyError, IndexError, TypeError) as e:
            print(f"  ERROR  {spec}: {e}")
            errors += 1
            continue

        checked += 1
        # Compare as the prose presents it: the sentence rounds, the JSON does not.
        if "tol" in opts:
            try:
                ok = abs(float(shown) - float(live)) <= float(opts["tol"])
            except ValueError:
                ok = False
            expect = f"{live} (±{opts['tol']})"
        else:
            nd = int(opts.get("round", 2))
            expect = f"{float(live):.{nd}f}"
            ok = shown == expect
        if ok:
            if not a.quiet:
                print(f"  ok     {spec} = {shown}")
        else:
            print(f"  DRIFT  {spec}: page says {shown!r}, data says {expect!r}")
            drifted += 1

    total_figures = len(re.findall(r'(\d+(?:\.\d+)?)\s*(?:pp|%|bp)\b',
                                   re.sub(r"<[^>]+>", "", html)))
    print(f"drift: {checked} bound, {drifted} drifted, {errors} broken "
          f"({total_figures} figures carry a unit; the rest are unbound)")
    if errors:
        return 1
    return 2 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
