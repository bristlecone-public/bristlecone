"""Build the self-contained interactive flow explorer.

Reads the per-sex cohort flow CSVs from output/, packs them into a compact
JSON payload, and injects payload + county topology into template.html to
produce a single-file output/explorer.html (no external requests at view
time). Both-sexes values are reconstructed client-side as M + F.

Run after `make report`:  .venv/bin/python explorer/build_explorer.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cohort_trace.crosswalk import MERGE_GROUPS, RENAMES  # noqa: E402

OUTPUT = ROOT / "output"
# Whatever per-sex flow CSVs the pipeline produced, oldest decade first.
PERIODS = sorted(
    m.group(1)
    for f in OUTPUT.glob("cohort_flows_*.csv")
    if (m := re.match(r"cohort_flows_(\d{4}-\d{4})\.csv$", f.name))
)


def _cohort_sort_key(label: str) -> int:
    return int(label.replace("+", "").split("-")[0])


def pack() -> dict:
    """Historical censuses publish coarser top bins, so each period carries
    its own cohort list; unit arrays are sized to that period's list."""
    units: dict[str, dict] = {}
    basis: dict[str, str] = {}
    period_cohorts: list[list[str]] = []

    frames = [pd.read_csv(OUTPUT / f"cohort_flows_{p}.csv",
                          dtype={"unit": str}) for p in PERIODS]
    for period, df in zip(PERIODS, frames):
        basis[period] = df["basis"].iloc[0]
        period_cohorts.append(
            sorted(df["cohort_age_at_t0"].unique(), key=_cohort_sort_key))

    for p_i, df in enumerate(frames):
        cohort_idx = {c: i for i, c in enumerate(period_cohorts[p_i])}
        n = len(cohort_idx)
        for row in df.itertuples(index=False):
            u = units.setdefault(row.unit, {
                "n": row.name if isinstance(row.name, str) else row.unit,
                # per period, per sex: flat [e0, a0, e1, a1, ...] over cohorts
                "d": [{"M": [0] * (2 * len(period_cohorts[i])),
                       "F": [0] * (2 * len(period_cohorts[i]))}
                      for i in range(len(PERIODS))],
            })
            arr = u["d"][p_i][row.sex]
            ci = cohort_idx[row.cohort_age_at_t0]
            arr[2 * ci] = int(round(row.expected_t1))
            arr[2 * ci + 1] = int(round(row.count_t1))

    xwalk = dict(RENAMES)
    for group, members in MERGE_GROUPS.items():
        for fips in sorted(members):  # sets iterate nondeterministically
            xwalk[fips] = group

    return {
        "periods": PERIODS,
        "basis": basis,
        "period_cohorts": period_cohorts,
        "xwalk": xwalk,
        "units": units,
    }


def main() -> None:
    payload = pack()
    topo = (ROOT / "explorer" / "counties-albers-10m.json").read_text(encoding="utf-8")
    template = (ROOT / "explorer" / "template.html").read_text(encoding="utf-8")

    html = (template
            .replace("__DATA__", json.dumps(payload, separators=(",", ":")))
            .replace("__TOPO__", topo))
    out = OUTPUT / "explorer.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, "
          f"{len(payload['units'])} units)")


if __name__ == "__main__":
    main()
