#!/usr/bin/env python3
"""Remove ZORI-derived values from p9_metro.json.

WHY: Zillow's Terms of Use (2025-10-28) §4(C) grant the right to display and
distribute derivative works only of "Aggregate Data provided on the Zillow
Local-Info Pages", and then state "You are prohibited from displaying any other
Zillow Companies' data without our prior written approval." ZORI comes from the
Research CSVs, not the Local-Info pages, so no ZORI-derived value is published
or displayed. The pipeline (pipelines/p9_metro.py) and the source URL stay
public, so anyone can download ZORI themselves, under Zillow's terms, and
regenerate the complete file.

This is the ONE implementation of the strip. It is used by:

  - cpi-lab/publish.py            (the public website build)
  - tools/public-mirror/prepare_data.py  (the public repo's data package)

Keeping it in one place is deliberate: the site and the repo must not be able to
drift apart on what was removed. It lives here, next to the pipeline that
produces the file, rather than inside the private mirror builder, so that the
removal itself is publicly auditable — a reader can see exactly which fields
went and check that nothing else did.

`strip_zori` is idempotent: running it on an already-stripped file is a no-op
that reports zero removals.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ZORI_NOTE = (
    "ZORI-derived values (zori_yoy_l12, the CPI-shelter/ZORI gap, the best-lag "
    "correlation table, and the third element of each shelter_small_multiples "
    "series) have been REMOVED from this published copy. Zillow's Terms of Use "
    "do not grant redistribution rights for Zillow Observed Rent Index data. "
    "The pipeline (cpi-lab/pipelines/p9_metro.py) and the source URL in "
    "coverage.zori_source are unchanged, so you can download ZORI from Zillow "
    "yourself, under their terms, and regenerate the complete file."
)


def strip_zori(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    removed = {"metro_fields": 0, "series_points": 0, "best_lag_table": 0}

    for m in d.get("metros", []):
        ls = m.get("latest_shelter") or {}
        for k in ("zori_yoy_l12", "gap"):      # gap = cpi - zori, so it leaks zori
            if ls.pop(k, None) is not None:
                removed["metro_fields"] += 1
        if m.pop("best_lag", None) is not None:  # CPI-shelter vs ZORI lag
            removed["metro_fields"] += 1

    if "best_lag_table" in d:                   # entirely ZORI-vs-CPI correlation
        removed["best_lag_table"] = len(d["best_lag_table"])
        del d["best_lag_table"]

    for sm in d.get("shelter_small_multiples", []):
        series = sm.get("series") or []
        # [ym, cpi_rent_yoy, zori_yoy] -> [ym, cpi_rent_yoy]
        trimmed = [row[:2] for row in series]
        if trimmed != series:
            removed["series_points"] += len(series)
        sm["series"] = trimmed

    # Keep coverage.zori_source / latest_zori_month: a URL and a date are
    # provenance, not Zillow data, and they are what makes this reproducible.

    schema = d.get("schema")
    if isinstance(schema, dict):
        schema.pop("best_lag_table[]", None)
        for k, v in list(schema.items()):
            if isinstance(v, str):
                v = v.replace("zori_yoy_l12,", "").replace(",zori_yoy_l12", "")
                v = re.sub(r",?\s*best_lag\{lag,\s*corr\}", "", v)
                v = re.sub(r",?\s*zori_yoy_l12", "", v)
                schema[k] = v
        schema["zori_removed"] = ZORI_NOTE

    d["zori_removed"] = ZORI_NOTE
    path.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return removed


def assert_stripped(path: Path) -> None:
    """Fail closed. Called after staging, before anything is published."""
    d = json.loads(path.read_text(encoding="utf-8"))
    bad = []
    if "best_lag_table" in d:
        bad.append("best_lag_table")
    for m in d.get("metros", []):
        if "best_lag" in m:
            bad.append(f"{m.get('cbsa', '?')}.best_lag")
        ls = m.get("latest_shelter") or {}
        for k in ("zori_yoy_l12", "gap"):
            if k in ls:
                bad.append(f"{m.get('cbsa', '?')}.latest_shelter.{k}")
    for sm in d.get("shelter_small_multiples", []):
        for row in sm.get("series") or []:
            if len(row) > 2:
                bad.append(f"{sm.get('cbsa', '?')}.series has {len(row)} columns")
                break
    if bad:
        raise SystemExit(
            f"ZORI STRIP FAILED — {path} still carries Zillow-derived values: "
            + ", ".join(bad[:8]) + (" ..." if len(bad) > 8 else ""))
