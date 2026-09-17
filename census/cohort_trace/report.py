"""Summaries of cohort flows: full CSVs plus a readable markdown report."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"

# Cohorts aged 10-19 at t0 are aged 20-29 at t1: the young-adult flows that
# answer "where did the children of t0 go?"
YOUNG_ADULT_COHORTS = ["10-14", "15-19"]
MIN_EXPECTED_FOR_RANKING = 1000


def _both_sexes(flows: pd.DataFrame) -> pd.DataFrame:
    combined = (
        flows.groupby(["period", "unit", "cohort_age_at_t0", "birth_years"],
                      as_index=False)
        .agg(count_t0=("count_t0", "sum"),
             count_t1=("count_t1", "sum"),
             expected_t1=("expected_t1", "sum"),
             net_residual=("net_residual", "sum"))
    )
    combined["net_migration_rate"] = combined["net_residual"].where(
        combined["expected_t1"] > 0
    ) / combined["expected_t1"].where(combined["expected_t1"] > 0)
    return combined


def _young_adult_table(flows: pd.DataFrame, names: pd.Series) -> pd.DataFrame:
    ya = flows[flows["cohort_age_at_t0"].isin(YOUNG_ADULT_COHORTS)]
    grouped = (
        ya.groupby(["period", "unit"], as_index=False)
        .agg(expected_t1=("expected_t1", "sum"),
             count_t1=("count_t1", "sum"),
             net_residual=("net_residual", "sum"))
    )
    grouped["net_migration_rate"] = grouped["net_residual"] / grouped["expected_t1"]
    grouped["name"] = grouped["unit"].map(names)
    return grouped[grouped["expected_t1"] >= MIN_EXPECTED_FOR_RANKING]


def _ranking_caveat(period: str, basis: str) -> str:
    """The per-decade note above each ranking, matched to what actually drives
    the top of *that* decade. The old text asserted 'college towns dominate on
    every basis' verbatim on all seven decades -- false for 1950-1980, where the
    gains are military/training installations and resource/resort boomtowns and
    where, on the total-population basis, group quarters are not subtracted at
    all (so the off-campus-student mechanism it described does not even apply)."""
    start = int(period[:4])
    if basis == "household":
        # 2010->2020: group quarters ARE subtracted, so college towns rise on
        # the off-campus-student channel described in caveat 1 -- the sharp case.
        return (
            "*College towns dominate the top of this ranking even on the "
            "household basis: off-campus students are counted as household "
            "population, so subtracting group quarters does not remove them "
            "(caveat 1 above).*"
        )
    if start >= 1990:
        # Total basis, modern: dorms/prisons/barracks all register, and growing
        # university enrollment still tops the gains alongside Sunbelt growth.
        return (
            "*On this total-population basis group quarters are not subtracted, "
            "so college dorms, prisons, and military barracks register directly "
            "in these flows. University counties still top the gains (dorm plus "
            "off-campus enrollment), alongside institutional and Sunbelt-growth "
            "counties -- read the top ranks as enrollment and base population, "
            "not purely economic in-migration.*"
        )
    # Total basis, 1950-1980: the auditor's core correction.
    return (
        "*On this total-population basis group quarters are not subtracted, so "
        "whole installation and institutional populations register directly. "
        "The top of this ranking is dominated by military and training bases "
        "and by resource/resort boomtowns -- not by universities. In the "
        "1950s-60s these are Cold War and Vietnam-era mobilizations (Fort "
        "Leonard Wood, Fort Polk, Fort Benning) and aerospace/proving grounds "
        "(Cape Canaveral); in the 1970s, energy and ski-resort booms (the "
        "Powder River and Wyoming trona fields; Aspen, Vail). The largest net "
        "losses reflect farm and coal-mine mechanization and the Second Great "
        "Migration out of the Deep South, not the modern undercount and "
        "young-adult mortality of caveat 3.*"
    )


def _fmt_ranking(df: pd.DataFrame, top: bool, n: int = 20) -> str:
    ordered = df.sort_values("net_migration_rate", ascending=not top).head(n)
    lines = ["| Unit | Expected | Actual | Net | Rate |",
             "|---|---:|---:|---:|---:|"]
    for _, r in ordered.iterrows():
        label = r["name"] if r["name"] == r["unit"] else f"{r['name']} ({r['unit']})"
        lines.append(
            f"| {label} | {r['expected_t1']:,.0f} "
            f"| {r['count_t1']:,.0f} | {r['net_residual']:+,.0f} "
            f"| {r['net_migration_rate']:+.1%} |"
        )
    return "\n".join(lines)


def write_reports(flows: pd.DataFrame, names: pd.Series) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for period, chunk in flows.groupby("period"):
        out = chunk.copy()
        out["name"] = out["unit"].map(names)
        out.to_csv(OUTPUT_DIR / f"cohort_flows_{period}.csv", index=False)

    combined = _both_sexes(flows)
    combined["name"] = combined["unit"].map(names)
    combined.to_csv(OUTPUT_DIR / "cohort_flows_both_sexes.csv", index=False)

    period_bases = {
        period: (chunk["basis"].iloc[0] if "basis" in chunk.columns
                 else "total")
        for period, chunk in flows.groupby("period")
    }
    hh = [p for p, b in sorted(period_bases.items()) if b == "household"]
    tot = [p for p, b in sorted(period_bases.items()) if b != "household"]

    sections = [
        "# Cohort residual tracing report",
        "",
        "Net migration residuals by cohort, relative to national survival. "
        "A negative residual means the unit kept fewer members of that cohort "
        "than national survival predicts (net out-migration); positive means "
        "net in-migration.",
        "",
        "## Population basis (read before comparing decades)",
        "",
        "Each decade is traced on one of two bases, labelled below:",
        "",
        f"- **Household population** (group quarters subtracted): "
        f"{', '.join(hh) if hh else 'none'}.",
        f"- **Total population** (group quarters included): "
        f"{', '.join(tot) if tot else 'none'}.",
        "",
        "**Decades on different bases are NOT level-comparable.** Subtracting "
        "group quarters (college dorms, prisons, military barracks, nursing "
        "homes) moves a college or prison county's young-adult retention rate "
        "by tens of percentage points, so a household-basis decade sitting "
        "next to a total-basis decade will look like a migration surge or "
        "collapse that is really just the basis switch. Compare same-basis "
        "decades, or compare a county against its peers within one decade.",
        "",
        "Why the split: 2010 and 2020 publish group quarters by sex by 5-year "
        "age (the Census PCO1 / DHC tables), so 2010->2020 runs on the "
        "household basis. 2000 SF1 tabulates group quarters by sex by age "
        "only in three coarse bands (Under 18 / 18-64 / 65+; tables "
        "P038 / PCT017) -- enough to confirm the ~7.78M national total, but "
        "too coarse to subtract at 5-year resolution -- and the 1990 STF1A "
        "county files carry no group-quarters age detail at all. So any "
        "decade touching 1990 or 2000 stays on the total-population basis.",
        "",
        "## Known caveats and directional biases",
        "",
        "The residual is net migration *relative to the national average*, but "
        "several other signals ride inside it and bias specific, identifiable "
        "county types. Read the rankings with these in mind:",
        "",
        "1. **Off-campus students inflate college-town young-adult 'growth' -- "
        "even on the household basis.** The Census counts only dormitories and "
        "recognized fraternity/sorority houses as group quarters; roughly "
        "65-80% of undergraduates and over 95% of graduate students live "
        "off-campus and are tabulated as *household* population. So subtracting "
        "group quarters removes dorm residents but NOT the far larger "
        "off-campus student influx. The top young-adult-gaining counties on "
        "the 2010->2020 household basis are therefore still dominated by "
        "university towns -- Charlottesville (UVA), Clarke GA (UGA), "
        "Harrisonburg (JMU), Riley KS (KSU), Whitman WA (WSU), Story IA (ISU), "
        "Montgomery VA (Virginia Tech) -- and that ranking largely measures "
        "off-campus university enrollment, not economic in-migration.",
        "",
        "2. **International immigration inflates gateway metros and penalizes "
        "rural counties.** The survival ratio is a single national number, and "
        "it absorbs net international migration, which concentrates in a "
        "handful of gateway metros (Miami, New York, Houston, Los Angeles, "
        "Chicago, Dallas). Those counties post positive residuals that are "
        "really foreign arrivals, not domestic attraction. The same "
        "immigration-boosted national ratio inflates the *expected* count "
        "everywhere, so low-immigration rural and Midwestern counties are "
        "penalized and can be mislabeled as domestic out-migration when they "
        "are merely not receiving immigrants.",
        "",
        "3. **Undercount and young-adult mortality masquerade as "
        "out-migration.** The method treats every uncounted person AND every "
        "death as an out-migrant. The biggest 'out-migration' counties are "
        "disproportionately tribal (Rolette, Benson ND), high-poverty "
        "Mississippi Delta (Phillips, Lee AR), border (Presidio TX), and "
        "Puerto Rican (Guanica). The 2020 Post-Enumeration Survey found large "
        "net undercounts for exactly these populations (on-reservation "
        "American Indian -5.6%, Black -3.3%, Hispanic -5.0%), and 2010-2020 "
        "brought historic rural young-adult mortality (opioids, motor-vehicle "
        "deaths, suicide). Both channels appear here as negative residuals "
        "indistinguishable from out-migration. These two channels are largest "
        "in the recent decades; the heavy out-migration of 1950-1980 instead "
        "reflects farm and coal-mine mechanization (the Oklahoma/Arkansas and "
        "Appalachian losses) and the Second Great Migration of African "
        "Americans out of the Deep South Black Belt, so read the pre-1990 loss "
        "rankings against that history rather than this caveat's modern one.",
        "",
        "4. **A few Virginia independent-city annexations inflate their "
        "apparent gains.** Virginia's independent cities are county-equivalents "
        "that annexed populated territory from their neighbouring counties "
        "through the 1950s-70s. `crosswalk.py` folds the major cases into "
        "constant-territory merged units (Richmond, Roanoke, the Tidewater and "
        "Hampton Roads cities, Fairfax city + county, and others), but three "
        "fast-growing cities are deliberately left standalone and their "
        "annexations therefore register as migration: **Alexandria** (annexed "
        "7.5 sq mi from Fairfax County on 1 Jan 1952), **Charlottesville** "
        "(from Albemarle in 1963 and 1968), and **Harrisonburg** (from "
        "Rockingham in 1953, 1962 and 1982). Each posts triple-digit "
        "young-adult 'gains' in the decades bracketing its annexations that are "
        "partly a boundary transfer, not cohort migration -- all three appear "
        "in the national top ranks for the 1950s-70s. They are not merged "
        "because Charlottesville (UVA) and Harrisonburg (JMU) are also the "
        "clearest modern college-town cases, which the 2010-2020 household "
        "basis shows standalone on purpose; read their pre-1980 ranks as "
        "boundary-inflated and their post-2000 ranks as enrollment-driven.",
        "",
        "Other caveats: 2020 counts carry differential-privacy noise, so treat "
        "small units cautiously. Broomfield CO (08014), created in 2001 from "
        "parts of four counties, is traced standalone from 2000 onward -- its "
        "4/1/2000 baseline reconstructed from the Census Bureau's intercensal "
        "estimates base (2010 boundaries, parents already reduced), which sums "
        "to the parents' raw 2000 total within ~140 people -- so Adams, "
        "Boulder, Jefferson and Weld keep their own signals instead of being "
        "bundled into one ~2M-person merged unit; the 1990-2000 decade still "
        "uses the parents' full pre-Broomfield territory. The 1980 "
        "county age data splices single-year counts (ages up to 74) with a "
        "coarser table for the 75-84 and 85+ split, so a small seam can appear "
        "at age 75 in the oldest cohorts; the national totals are anchor-"
        "checked, the mismatch is logged at build time, and the young-adult "
        "rankings above are unaffected. The oldest traced cohort (75-84 -> "
        "85+) is contaminated at the destination, because the open-ended 85+ "
        "bin at t1 also holds people already 85+ at t0 -- counties with large "
        "elderly-institution populations get spuriously positive residuals, so "
        "read the 85+ cohort in the CSVs and explorer as indicative only. And "
        "Alaska is excluded from 1950, 1960 and 1970 (its pre-borough judicial "
        "divisions and election districts are not county-comparable) and "
        "therefore from every decade that traces into those years (1950-60, "
        "1960-70, 1970-80): Alaskan counties carry no residual there and the "
        "1970s Trans-Alaska Pipeline boom does not appear. Those decades' "
        "national ratios are computed on the Lower 48 plus Hawaii -- Alaska is "
        "cleanly dropped from both endpoints of the ratio, not misattributed "
        "to the other states.",
    ]
    for period, chunk in flows.groupby("period"):
        ya = _young_adult_table(chunk, names)
        basis = chunk["basis"].iloc[0] if "basis" in chunk.columns else "total"
        basis_note = (
            "**Basis: household population** (group quarters subtracted)."
            if basis == "household"
            else "**Basis: total population** — no 5-year group-quarters age "
                 "table for both endpoints, so college, prison, and military "
                 "counties inflate these flows. Not level-comparable with "
                 "household-basis decades (see the population-basis note "
                 "above)."
        )
        sections += [
            "",
            f"## {period}: where the 10-19-year-olds of {period[:4]} went",
            "",
            basis_note,
            "",
            f"Units with expected young-adult cohort >= "
            f"{MIN_EXPECTED_FOR_RANKING:,}. "
            f"({len(ya):,} units qualify.)",
            "",
            _ranking_caveat(period, basis),
            "",
            "### Largest net gains (importing 20-somethings)",
            "",
            _fmt_ranking(ya, top=True),
            "",
            "### Largest net losses (exporting 20-somethings)",
            "",
            _fmt_ranking(ya, top=False),
        ]

    report_path = OUTPUT_DIR / "report.md"
    report_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return report_path
