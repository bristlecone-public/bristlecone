"""Command-line entry point: fetch -> build -> report."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import engine, fetch, normalize, report
from .crosswalk import apply_crosswalk

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "county_age_sex.csv"

DEFAULT_YEARS = [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]


def cmd_fetch(years: list[int], force: bool) -> None:
    print("Fetching county P12 tables from api.census.gov...")
    for year in years:
        fetch.fetch_year(year, force=force)
    print("Fetching group-quarters sex-by-age tables (discovered per year)...")
    missing_plain_gq = []
    for year in years:
        if fetch.fetch_gq_year(year, force=force) is None:
            missing_plain_gq.append(year)
    # Years without a plain 5-year GQ sex-by-age table (2000 SF1) may still
    # carry a GQ table with a group-quarters-type dimension; collapse it to
    # recover GQ by sex by age (coarse bands only for 2000) for validation.
    if missing_plain_gq:
        print("Recovering group quarters from the by-group-quarters-type "
              "table where no plain GQ sex-by-age table exists...")
        for year in missing_plain_gq:
            fetch.fetch_gq_by_type_year(year, force=force)
    if 2000 in years and 2010 in years:
        print("Fetching the intercensal 4/1/2000 base for the Broomfield "
              "reconstruction...")
        fetch.fetch_broomfield_base(force=force)


def cmd_build(years: list[int]) -> None:
    frames = [normalize.normalize_year(fetch.load_raw(y), y) for y in years]
    df = pd.concat(frames, ignore_index=True)

    gq_frames = []
    for year in years:
        payload = fetch.load_gq_raw(year)
        if payload is not None:
            gq_frames.append(normalize.normalize_gq(payload, year))
    if gq_frames:
        gq = pd.concat(gq_frames, ignore_index=True)
        df = df.merge(gq, on=["year", "geoid", "sex", "age_bin"], how="left")
        df["gq_count"] = df["gq_count"].fillna(0).astype(int)
    else:
        df["gq_count"] = 0

    df = apply_crosswalk(df)
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED, index=False)
    gq_years = sorted(
        int(y) for y in df.loc[df["gq_count"] > 0, "year"].unique()
    )
    print(f"Built {PROCESSED}: {df['unit'].nunique()} units, years "
          f"{sorted(int(y) for y in df['year'].unique())}, "
          f"5-year GQ data (household basis) for {gq_years or 'no years'}")

    # Report any coarse-age GQ recoveries: kept for validation, but the
    # survival-ratio engine needs 5-year bins, so these years stay on the
    # total-population basis (they are not merged into the traced table).
    for year in years:
        payload = fetch.load_gq_bytype_raw(year)
        if payload is None:
            continue
        total, by_sex = fetch.gq_bytype_total(payload)
        note = ("usable for household basis"
                if payload.get("resolution") == "fine"
                else "coarse age bands only -> stays on TOTAL basis "
                     "(cannot subtract at 5-year resolution)")
        print(f"  {year}: recovered GQ (over group-quarters type) = "
              f"{total:,} (M {by_sex.get('M', 0):,} / F {by_sex.get('F', 0):,})"
              f"; {note}")


def cmd_report(years: list[int]) -> None:
    df = pd.read_csv(PROCESSED, dtype={"unit": str})
    if "gq_count" not in df.columns:
        df["gq_count"] = 0
    gq_years = set(df.loc[df["gq_count"] > 0, "year"].unique())

    broomfield_base = fetch.load_broomfield_base()

    flow_parts = []
    for t0, t1 in zip(years, years[1:]):
        basis = "household" if {t0, t1} <= gq_years else "total"
        if basis == "total":
            print(f"  {t0}-{t1}: no GQ data for both ends; using total "
                  f"population (young-adult flows will include dorms/prisons)")
        # Broomfield (08014) exists only from 2000. For the 2000->2010 trace,
        # splice in its reconstructed standalone 4/1/2000 baseline and the
        # parents reduced to match; every other decade uses df as built (so
        # 1990->2000 keeps the parents' full pre-Broomfield territory).
        dfx = df
        if t0 == 2000 and broomfield_base is not None:
            from . import broomfield
            dfx = broomfield.splice_2000(df, broomfield_base)
        flow_parts.append(engine.trace(dfx, t0, t1, basis=basis))
    flows = pd.concat(flow_parts, ignore_index=True)
    names = (
        df.sort_values("year", ascending=False)
        .drop_duplicates("unit")
        .set_index("unit")["name"]
    )
    path = report.write_reports(flows, names)
    print(f"Wrote {path} and CSVs in {report.OUTPUT_DIR}/")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cohort_trace")
    parser.add_argument("command", choices=["fetch", "build", "report", "all"])
    parser.add_argument("--years", type=int, nargs="+", default=DEFAULT_YEARS,
                        help="census years, ascending "
                             "(default: 1950 through 2020)")
    parser.add_argument("--force", action="store_true",
                        help="re-download even if cached")
    args = parser.parse_args(argv)

    years = sorted(args.years)
    if args.command in ("fetch", "all"):
        cmd_fetch(years, args.force)
    if args.command in ("build", "all"):
        cmd_build(years)
    if args.command in ("report", "all"):
        cmd_report(years)
