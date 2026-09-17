"""Cohort residual tracing via the census survival ratio method.

For each cohort (a 5-year age-sex group observed at census t0), the national
ratio of its size at t1 to its size at t0 captures survival plus net
international migration. Applying that ratio to each analysis unit's t0 count
gives the count expected if the unit tracked the nation; the deviation of the
actual t1 count from that expectation is the unit's net migration residual
relative to the national average.

This needs no external life tables, and international migration is absorbed
into the national ratio, so residuals are primarily net domestic migration.
"""

from __future__ import annotations

import pandas as pd

from .bins import STD_BINS


def cohort_specs() -> list[tuple[str, list[str], str]]:
    """The full-resolution specs, when both endpoints publish every bin."""
    return specs_for(set(STD_BINS), set(STD_BINS))


def specs_for(bins0: set[str], bins1: set[str]
              ) -> list[tuple[str, list[str], str]]:
    """(label, source bins at t0, destination bin at t0+10) per cohort,
    adapted to the bins each endpoint actually publishes.

    A decade moves every cohort up two 5-year bins. Historical censuses
    publish coarser top bins: 1950 merges 75-84, and 1980's county data
    splits no finer than 75-84/85+ — when the destination lacks the fine
    split, 65-69 and 70-74 are traced as one combined 65-74 cohort. The
    two oldest closed bins both flow into the open 85+ bin and are traced
    as one cohort; people already 85+ at t0 cannot be separated from that
    inflow and are not traced.
    """
    specs: list[tuple[str, list[str], str]] = []
    for i in range(15):  # source bins 0-4 ... 70-74
        src, dst = STD_BINS[i], STD_BINS[i + 2]
        if src in bins0 and dst in bins1:
            specs.append((src, [src], dst))
    if ("75-84" in bins1 and not {"75-79", "80-84"} & bins1
            and {"65-69", "70-74"} <= bins0):
        specs.append(("65-74", ["65-69", "70-74"], "75-84"))
    if "85+" in bins1:
        if {"75-79", "80-84"} <= bins0:
            specs.append(("75-84", ["75-79", "80-84"], "85+"))
        elif "75-84" in bins0:
            specs.append(("75-84", ["75-84"], "85+"))
    return specs


def _birth_years(label: str, t0: int) -> str:
    lo, hi = label.replace("+", "").split("-")
    return f"{t0 - int(hi) - 1}-{t0 - int(lo)}"


def trace(df: pd.DataFrame, t0: int, t1: int,
          basis: str = "total") -> pd.DataFrame:
    """Trace all cohorts from census t0 to census t1.

    Input columns: year, unit, sex, age_bin, count (crosswalked), plus
    gq_count when basis="household". Returns one row per (unit, cohort, sex)
    with expected and residual counts.

    basis="household" subtracts the group-quarters population at both ends,
    so college dorms, prisons, and bases don't register as migration.
    """
    if basis not in ("total", "household"):
        raise ValueError(f"unknown basis: {basis}")
    work = df
    if basis == "household":
        if "gq_count" not in df.columns:
            raise ValueError("household basis requires a gq_count column")
        work = df.copy()
        work["count"] = (work["count"] - work["gq_count"]).clip(lower=0)

    d0 = work[work["year"] == t0]
    d1 = work[work["year"] == t1]
    if d0.empty or d1.empty:
        raise ValueError(f"missing data for {t0} or {t1}")

    # Trace only units present at both endpoints: a unit missing from one
    # year's source (e.g. a geography the older file doesn't cover) would
    # otherwise masquerade as a 100% migration flow.
    u0, u1 = set(d0["unit"]), set(d1["unit"])
    common = u0 & u1
    dropped = (u0 | u1) - common
    if dropped:
        print(f"  {t0}-{t1}: dropping {len(dropped)} unit(s) absent from "
              f"one endpoint: {sorted(dropped)[:6]}"
              f"{'...' if len(dropped) > 6 else ''}")
        d0 = d0[d0["unit"].isin(common)]
        d1 = d1[d1["unit"].isin(common)]

    parts = []
    specs = specs_for(set(d0["age_bin"]), set(d1["age_bin"]))
    for label, src_bins, dst_bin in specs:
        for sex in ("M", "F"):
            s0 = (
                d0[(d0["sex"] == sex) & (d0["age_bin"].isin(src_bins))]
                .groupby("unit")["count"].sum()
            )
            s1 = (
                d1[(d1["sex"] == sex) & (d1["age_bin"] == dst_bin)]
                .groupby("unit")["count"].sum()
            )
            nat0, nat1 = s0.sum(), s1.sum()
            if nat0 == 0:
                continue
            ratio = nat1 / nat0

            units = s0.index.union(s1.index)
            c0 = s0.reindex(units, fill_value=0).astype(float)
            c1 = s1.reindex(units, fill_value=0).astype(float)
            expected = c0 * ratio
            residual = c1 - expected

            part = pd.DataFrame({
                "unit": units,
                "cohort_age_at_t0": label,
                "birth_years": _birth_years(label, t0),
                "sex": sex,
                "count_t0": c0.values,
                "count_t1": c1.values,
                "national_ratio": ratio,
                "expected_t1": expected.values,
                "net_residual": residual.values,
            })
            parts.append(part)

    out = pd.concat(parts, ignore_index=True)
    out["net_migration_rate"] = out["net_residual"].where(
        out["expected_t1"] > 0
    ) / out["expected_t1"].where(out["expected_t1"] > 0)
    # Small expected counts are noise-dominated (sampling error in 2000/2010
    # tabulations is nil, but 2020 carries differential-privacy noise, and
    # tiny cohorts swing wildly on real idiosyncratic events too).
    out["reliability"] = "ok"
    out.loc[out["expected_t1"] < 100, "reliability"] = "low"
    out["period"] = f"{t0}-{t1}"
    out["basis"] = basis
    return out
