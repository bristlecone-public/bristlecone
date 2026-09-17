"""Reconstruct Broomfield County, CO (08014) as a standalone unit for 2000.

Broomfield was created 15 Nov 2001 from parts of Adams (08001), Boulder
(08013), Jefferson (08059) and Weld (08123), so the 2000 census has no 08014
and the four parents still contain its territory. The crosswalk used to merge
all five into one constant-territory unit; that bundled ~2 million people and
erased four distinct Denver-metro signals across all seven decades.

Instead we splice in the Census Bureau's own reconstruction. The 2000-2010
intercensal county file carries a 4/1/2000 *estimates base* built on 2010
county boundaries -- Broomfield present, the four parents already reduced -- by
clean 5-year age groups (AGEGRP 1=0-4 .. 18=85+, SEX 1=male/2=female). That
base is the Bureau's block-level allocation of the 2000 count and sums to the
four parents' raw SF1-2000 total to within ~140 people (the Count Question
Resolution adjustment in the estimates base).

Continuity across the 2001 split is handled by *when* the splice applies, not
by merging: the reconstructed standalone 2000 is used only where 2000 is the
START of a trace (2000->2010). Where 2000 is the END (1990->2000), the raw SF1
parents are used, so pre-Broomfield decades keep the territory the parents
actually had then. See crosswalk.py (the removed MG-CO-BROOMFIELD note) and
report.py (the Broomfield caveat).
"""

from __future__ import annotations

import pandas as pd

from .bins import STD_BINS

# Broomfield + its four parent counties.
BROOMFIELD = "08014"
PARENTS = ("08001", "08013", "08059", "08123")
UNITS = (BROOMFIELD,) + PARENTS

_SEX = {"1": "M", "2": "F"}


def _frame(payload: dict, names: dict[str, str]) -> pd.DataFrame:
    """Build the year-2000 standalone rows for the five units from the cached
    intercensal payload (see fetch.fetch_broomfield_base).

    Columns match the processed table: year, unit, sex, age_bin, count, name,
    gq_count. AGEGRP i maps to STD_BINS[i-1]; the 2000->2010 trace runs on the
    total-population basis, so gq_count is zero here.
    """
    records = []
    for r in payload["rows"]:
        unit = r["geoid"]
        sex = _SEX[str(r["sex"])]
        age_bin = STD_BINS[int(r["agegrp"]) - 1]
        records.append((2000, unit, sex, age_bin, int(r["base2000"]),
                        names.get(unit, unit), 0))
    df = pd.DataFrame(records, columns=["year", "unit", "sex", "age_bin",
                                        "count", "name", "gq_count"])
    # AGEGRP is already one row per standard bin, but group defensively so the
    # schema matches the processed table exactly.
    return (df.groupby(["year", "unit", "sex", "age_bin"], as_index=False)
              .agg(count=("count", "sum"), name=("name", "first"),
                   gq_count=("gq_count", "first")))


def splice_2000(df: pd.DataFrame, payload: dict) -> pd.DataFrame:
    """Return `df` with the five units' year-2000 rows replaced by the
    reconstructed standalone baseline. Apply this only for the 2000->2010
    trace; every other decade uses `df` unchanged.
    """
    names = df.drop_duplicates("unit").set_index("unit")["name"].to_dict()
    frame = _frame(payload, names)
    if "gq_count" not in df.columns:
        frame = frame.drop(columns=["gq_count"])
    keep = ~((df["year"] == 2000) & (df["unit"].isin(UNITS)))
    return pd.concat([df[keep], frame], ignore_index=True)
