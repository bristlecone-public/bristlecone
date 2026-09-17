"""Turn raw Census API JSON into a tidy long table of standard 5-year bins.

Output columns: year, geoid, name, sex, age_bin, count
"""

from __future__ import annotations

import pandas as pd

from .bins import std_bin
from .fetch import var_map


def normalize_year(raw: list[list[str]], year: int) -> pd.DataFrame:
    header, *rows = raw
    idx = {col: i for i, col in enumerate(header)}
    vm = var_map(year)

    records = []
    for row in rows:
        geoid = row[idx["state"]] + row[idx["county"]]
        name = row[idx["NAME"]]
        for var, (sex, api_bin) in vm.items():
            records.append((year, geoid, name, sex, std_bin(api_bin),
                            int(row[idx[var]])))

    df = pd.DataFrame(
        records, columns=["year", "geoid", "name", "sex", "age_bin", "count"]
    )
    # Collapse the published sub-bins (15-17 + 18-19, etc.) into standard bins.
    return (
        df.groupby(["year", "geoid", "sex", "age_bin"], as_index=False)
        .agg(count=("count", "sum"), name=("name", "first"))
    )


def normalize_gq(payload: dict, year: int) -> pd.DataFrame:
    """Tidy a discovered group-quarters table.

    Output columns: year, geoid, sex, age_bin, gq_count.
    The variable map was derived from labels at fetch time and travels with
    the raw payload.
    """
    header, *rows = payload["data"]
    idx = {col: i for i, col in enumerate(header)}
    vm = {var: tuple(sb) for var, sb in payload["var_map"].items()}

    records = []
    for row in rows:
        geoid = row[idx["state"]] + row[idx["county"]]
        for var, (sex, bin_) in vm.items():
            records.append((year, geoid, sex, bin_, int(row[idx[var]])))

    df = pd.DataFrame(
        records, columns=["year", "geoid", "sex", "age_bin", "gq_count"]
    )
    return (
        df.groupby(["year", "geoid", "sex", "age_bin"], as_index=False)
        .agg(gq_count=("gq_count", "sum"))
    )
