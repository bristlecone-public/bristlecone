#!/usr/bin/env python3
"""P9 - metro CPI vs local wages and rents.

  p9_metro.py [--history] [--force] [--no-qcew] [--no-zori] [--qcew-from YYYY]

--history      also load the deep metro CPI history (cu.data.7..10, ~46 MB, back to 1914)
               on top of cu.data.0.Current (which carries metro rows from 1997).  Opt-in, not
               implied on a fresh database: nothing this pipeline publishes uses pre-1997 data
               (see DISP_FROM below), and the pre-1998 metro areas are different geographies
               under the same codes.
--force        re-download every source and rebuild, ignoring Last-Modified / cache hits.
--no-qcew      skip the QCEW wage step (keeps whatever is already in p9_wage).
--no-zori      skip the Zillow step (keeps whatever is already in p9_zori).
--qcew-from    first year of the QCEW backfill (default 2015).

WHAT THIS IS
------------
The published CPI has 23 "self-representing" metropolitan areas - places big enough that BLS
prices them as their own index rather than folding them into a region/size-class cell.  P0
loads only the U.S. city average (area 0000), so this pipeline loads the metro rows itself
into its own tables and joins them to two local, non-CPI series:

  * QCEW average weekly wages by MSA  (BLS, quarterly, administrative payroll records)
  * Zillow Observed Rent Index (ZORI) by metro (asking rents on new leases, monthly)

and produces three views:

  1. real wages     wage growth minus local inflation, per metro per quarter
  2. shelter        the CPI's rent/shelter measure against market asking rent lagged 12 months
  3. dispersion     how far apart metro inflation rates are, over time

THREE THINGS THAT MAKE THIS HARDER THAN IT LOOKS
------------------------------------------------
1. BIMONTHLY PUBLICATION - BUT ONLY FOR SOME ITEMS.  Only New York (S12A), Chicago (S23A)
   and Los Angeles (S49A) publish an all-items index every month.  The other 20 publish it
   every OTHER month, on two staggered schedules ("odd" = Jan/Mar/May/Jul/Sep/Nov, "even" =
   Feb/Apr/.../Dec).  The schedule is DERIVED from the data in derive_schedule(), never
   hard-coded, because circulating reference lists disagree (a list checked 2026-08 put
   Detroit S23B on the odd schedule; the flat file says even - see docs/P9.md).
   The bimonthly restriction applies to ALL ITEMS (SA0) and FOOD (SAF) only.  Verified in the
   flat file: shelter (SAH1), rent (SEHA), owners' equivalent rent (SEHC01) and energy (SA0E)
   carry a value EVERY month for all 23 metros, because the housing survey and the fuel/
   utility pricing run monthly everywhere while the general commodity/service pricing that
   feeds all-items does not.  So the shelter-vs-ZORI view (build_shelter) is monthly for every
   metro, while the real-wage and dispersion views (both built on SA0) are staggered.
   Consequences of the stagger:
     - a metro's 12-month change is only computable in months it publishes (its own-parity
       months), and the 12-months-ago observation is always the same parity, so YoY is
       computable in every published month.  Missing months stay NULL.  Nothing is
       interpolated in any stored table.
     - the cross-metro mean in an odd month is a mean over a DIFFERENT set of metros than in
       an even month, so a "rise" from one month to the next can be pure composition.
       p9_disp flags that (comp_flag / comp_delta).
2. THE OCTOBER 2025 HOLE.  No CPI was published for 2025-10 (shutdown).  For odd-schedule
   metros that month was not theirs anyway; for even-schedule metros it removes a scheduled
   observation, leaving a four-month gap (2025-08 -> 2025-12) and making their 2026-10 YoY
   uncomputable.  All lags here are calendar-aligned merges, never row offsets.
3. QCEW MSA PRIVATE-OWNERSHIP SUPPRESSION.  own_code 5 (private) at MSA aggregation
   (agglvl 41) is published through 2025Q2 and carries disclosure_code '-' with zeros from
   2025Q3 onward, for every MSA.  We therefore load BOTH own_code 5 (private) and own_code 0
   (total covered) and compute each ownership basis's YoY separately; p9_real prefers the
   private YoY and falls back to total covered, recording which in wage_own.  A YoY is never
   computed across ownership bases.

DATA SOURCES
------------
  metro CPI   https://download.bls.gov/pub/time.series/cu/cu.data.0.Current   (metro rows 1997+)
              cu.data.7.OtherNorthEast / 8.OtherNorthCentral / 9.OtherSouth / 10.OtherWest
              hold the same series back to 1914 (--history).  The Asize files (3..6) hold the
              size-class aggregates, NOT the metros - checked, 0 metro rows.
              Series are CUUR<area><item>, periodicity R, seasonal U.  There is no seasonally
              adjusted metro CPI at all (0 CUSR metro series in cu.series).
  QCEW        https://data.bls.gov/cew/data/api/{year}/{qtr}/industry/10.csv
              One 3.7 MB file per quarter covering every area, rather than 23 per-area slices
              (https://data.bls.gov/cew/data/api/{year}/{qtr}/area/C3562.csv would also work -
              same numbers, 23x the requests).  MSA rows are area_fips 'C' + first four digits
              of the CBSA code; agglvl 40 = MSA total (own 0), 41 = MSA by ownership (own 5).
              avg_wkly_wage is total quarterly wages / (13 x average monthly employment).
  ZORI        https://files.zillowstatic.com/research/public_csvs/zori/
              Metro_zori_uc_sfrcondomfr_sm_month.csv  (smoothed, all home types, NOT sa)
              Zillow renames/reshuffles these files roughly annually, so load_zori() walks a
              candidate list, validates the shape, keeps the last good copy in raw/zori/ and
              logs which URL resolved.  A failed refresh is a warning, never a crash.
  population  2020 CBSA population, hard-coded in CROSSWALK below, cross-checked at run time
              against the Census population-estimates file (fail-soft).

TABLES
------
p9_area(area_code, area_name, cbsa, cbsa_name, qcew_area, zori_region, pop2020, schedule,
        approx_geo, first_ym, last_ym)
        the crosswalk, materialised.  schedule = 'monthly' | 'odd' | 'even' (derived).
        approx_geo=1 where the CPI pricing area is wider than the CBSA joined to (Urban Hawaii,
        Urban Alaska) - their wage/rent joins are approximations, see docs/P9.md.
p9_cpi(area_code, area_name, item_code, ym, idx, yoy)
        idx = published NSA index level (each metro keeps its own reference base - Tampa is
        1987=100, Phoenix DEC 2001=100, Riverside DEC 2017=100, the rest 1982-84=100; YoY is
        base-invariant so levels are never compared across metros).
        yoy = 100 * (idx[ym] / idx[ym - 12 calendar months] - 1), NULL when either is missing.
        items: SA0 all items, SAH1 shelter, SEHA rent of primary residence, SEHC01 owners'
        equivalent rent, SAF food, SA0E energy.  SA0 and SAF follow the metro's bimonthly
        schedule; SAH1/SEHA/SEHC01/SA0E are present every month for every metro.
        2025-10 is absent everywhere: BLS ships the row with value '-' and footnote 'X'
        (not available), which numeric coercion turns into NULL and the loader drops.
p9_wage(cbsa, yq, own_code, avg_wkly_wage, emp, disclosed, yoy)
        yq = 'YYYYQn'.  own_code '0' = total covered, '5' = private.  disclosed = 0 when BLS
        suppressed the cell (wage stored as NULL).  yoy computed within own_code.
p9_real(cbsa, yq, wage_yoy, cpi_yoy, real_yoy, cpi_month_used, wage_own)
        real_yoy = wage_yoy - cpi_yoy (percentage points; the exact ratio form differs by
        <0.1 pp at these rates).  cpi_month_used = the LAST month inside the quarter that the
        metro actually published an all-items index for (monthly metros: Mar/Jun/Sep/Dec;
        odd metros: Mar/May/Sep/Nov; even metros: Feb/Jun/Aug/Dec).  See docs/P9.md.
p9_zori(region, cbsa, ym, zori, yoy)
p9_shelter(cbsa, ym, cpi_rent_yoy, cpi_shelter_yoy, zori_yoy_l12, gap)
        gap = cpi_rent_yoy - zori_yoy_l12 (pp).  zori_yoy_l12 is ZORI's own 12-month change
        as of ym-12, i.e. market rent growth a year earlier.
p9_lag(cbsa, lag, corr, n)          correlation of cpi_rent_yoy[t] with zori_yoy[t-lag], 0..18
p9_disp(ym, n_metros, mean, sd, min_metro, min_yoy, max_metro, max_yoy, range, comp_flag,
        comp_delta)
        population-weighted across the metros that published that month; n>=8 required, and
        nothing before DISP_FROM (1998-01) is reported even when --history loaded it, because
        BLS redefined the metro pricing areas in 1998 (and again in 2018, when Tampa, Phoenix
        and Riverside were added) - a longer series would silently change geography.
        comp_delta = mean[t] - avg(mean[t-1], mean[t], mean[t+1]); comp_flag = |delta| > 0.3.

OUTPUT
------
$CPI_ROOT/out/p9_metro.json  - schema block at the top of the document, then per-metro latest
values, a map-ready array, the dispersion series, shelter small multiples (last 8 years), the
best-lag table and the validation results.

NOT CAUSAL.  "Real wage growth" here is an arithmetic difference between two independently
measured growth rates for the same geography, not a measure of purchasing power for any
individual; QCEW wages are per covered job (composition shifts move it), CPI is per urban
consumer basket.  The shelter/ZORI gap is a lead-lag description of two different rent
concepts (all leases in place vs new asking rents), not evidence that one causes the other.
"""
import sys, io, re, json, time, datetime as dt
import numpy as np
import pandas as pd
from common import *

# ---------------------------------------------------------------------------------------
# CROSSWALK: CPI area_code -> CBSA / QCEW area_fips / Zillow RegionName / 2020 population.
# Hand-checked 2026-08-24 against cu.area (CPI names), the QCEW area-titles file
# (https://data.bls.gov/cew/doc/titles/area/area_titles.csv), the ZORI metro CSV RegionName
# column, and the Census CBSA population-estimates file (ESTIMATESBASE2020 = the April 1 2020
# census count as used for the estimates series).  QCEW area_fips = 'C' + CBSA[:4].
# The CPI area name is frozen at the vintage BLS defined the pricing area; QCEW and Census use
# the current OMB title, which is why several names differ (Phoenix-Mesa-Scottsdale vs
# Phoenix-Mesa-Chandler, etc.).  Geography is the same CBSA in every case except the two noted.
# ---------------------------------------------------------------------------------------
CROSSWALK = [
    # area  CPI area name                                   CBSA    QCEW   ZORI RegionName        pop2020
    ("S11A", "Boston-Cambridge-Newton, MA-NH",              "14460", "C1446", "Boston, MA",          4941657),  # same CBSA; Census title identical
    ("S12A", "New York-Newark-Jersey City, NY-NJ-PA",       "35620", "C3562", "New York, NY",       20140535),  # CPI title keeps the pre-2023 "-PA"; CBSA 35620 is now NY-NJ only
    ("S12B", "Philadelphia-Camden-Wilmington, PA-NJ-DE-MD", "37980", "C3798", "Philadelphia, PA",    6245049),  # same CBSA
    ("S23A", "Chicago-Naperville-Elgin, IL-IN-WI",          "16980", "C1698", "Chicago, IL",         9618494),  # CPI title keeps "-WI"; CBSA 16980 is now IL-IN
    ("S23B", "Detroit-Warren-Dearborn, MI",                 "19820", "C1982", "Detroit, MI",         4392029),  # same CBSA
    ("S24A", "Minneapolis-St.Paul-Bloomington, MN-WI",      "33460", "C3346", "Minneapolis, MN",     3690272),  # same CBSA (CPI drops the space in "St.Paul")
    ("S24B", "St. Louis, MO-IL",                            "41180", "C4118", "St. Louis, MO",       2820292),  # same CBSA
    ("S35A", "Washington-Arlington-Alexandria, DC-VA-MD-WV","47900", "C4790", "Washington, DC",      6385198),  # same CBSA
    ("S35B", "Miami-Fort Lauderdale-West Palm Beach, FL",   "33100", "C3310", "Miami, FL",           6138336),  # same CBSA; current OMB title is "-Pompano Beach"
    ("S35C", "Atlanta-Sandy Springs-Roswell, GA",           "12060", "C1206", "Atlanta, GA",         6089755),  # same CBSA; current OMB title is "-Alpharetta"
    ("S35D", "Tampa-St. Petersburg-Clearwater, FL",         "45300", "C4530", "Tampa, FL",           3175288),  # same CBSA; CPI index starts 2017-12 (1987=100 base)
    ("S35E", "Baltimore-Columbia-Towson, MD",               "12580", "C1258", "Baltimore, MD",       2844513),  # same CBSA
    ("S37A", "Dallas-Fort Worth-Arlington, TX",             "19100", "C1910", "Dallas, TX",          7637361),  # same CBSA
    ("S37B", "Houston-The Woodlands-Sugar Land, TX",        "26420", "C2642", "Houston, TX",         7122206),  # same CBSA; current OMB title is "Houston-Pasadena-The Woodlands"
    ("S48A", "Phoenix-Mesa-Scottsdale, AZ",                 "38060", "C3806", "Phoenix, AZ",         4845831),  # same CBSA; current OMB title is "-Chandler". CPI starts 2017-12 (DEC 2001=100)
    ("S48B", "Denver-Aurora-Lakewood, CO",                  "19740", "C1974", "Denver, CO",          2963831),  # same CBSA; current OMB title is "-Centennial"
    ("S49A", "Los Angeles-Long Beach-Anaheim, CA",          "31080", "C3108", "Los Angeles, CA",    13201021),  # same CBSA (QCEW also lists the retired C3110 "-Santa Ana"; not used)
    ("S49B", "San Francisco-Oakland-Hayward, CA",           "41860", "C4186", "San Francisco, CA",   4748967),  # same CBSA; current OMB title is "-Fremont"
    ("S49C", "Riverside-San Bernardino-Ontario, CA",        "40140", "C4014", "Riverside, CA",       4599839),  # same CBSA; CPI starts 2017-12 (DEC 2017=100)
    ("S49D", "Seattle-Tacoma-Bellevue, WA",                 "42660", "C4266", "Seattle, WA",         4018751),  # same CBSA
    ("S49E", "San Diego-Carlsbad, CA",                      "41740", "C4174", "San Diego, CA",       3298635),  # same CBSA; current OMB title is "San Diego-Chula Vista-Carlsbad"
    # --- the two areas where CPI geography is WIDER than the CBSA we join to: ---
    ("S49F", "Urban Hawaii",                                "46520", "C4652", "Urban Honolulu, HI",  1016506),  # CPI prices urban Hawaii statewide; Honolulu MSA (Oahu) is ~70% of state pop and all of its urban pop
    ("S49G", "Urban Alaska",                                "11260", "C1126", "Anchorage, AK",        398326),  # CPI prices urban Alaska (Anchorage + Fairbanks urban); Anchorage MSA is the dominant piece
]
APPROX_GEO = {"S49F", "S49G"}   # CPI area not coextensive with the CBSA - flagged in output
DISP_FROM = "1998-01"           # earliest month reported in p9_disp (see docstring)

ITEMS = {"SA0": "All items", "SAH1": "Shelter", "SEHA": "Rent of primary residence",
         "SEHC01": "Owners' equivalent rent of residences", "SAF": "Food", "SA0E": "Energy"}

HISTORY_FILES = ["cu.data.7.OtherNorthEast", "cu.data.8.OtherNorthCentral",
                 "cu.data.9.OtherSouth", "cu.data.10.OtherWest"]

QCEW_URL = "https://data.bls.gov/cew/data/api/{y}/{q}/industry/10.csv"
CENSUS_POP = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2022/metro/totals/cbsa-est2022.csv"

# Zillow reshuffles file names/columns roughly annually. Order = preference.
ZORI_URLS = [
    "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv",
    "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_sa_month.csv",
    "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfr_sm_month.csv",
    "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_sm_month.csv",
    "https://files.zillowstatic.com/research/public_csvs/zori/Metro_ZORI_AllHomesPlusMultifamily_Smoothed.csv",
]

# BLS regional news releases used for the published-number spot check (fail-soft).
NEWS = {
    "S12A": "https://www.bls.gov/regions/northeast/news-release/consumerpriceindex_newyork.htm",
    "S23A": "https://www.bls.gov/regions/midwest/news-release/consumerpriceindex_chicago.htm",
    "S49A": "https://www.bls.gov/regions/west/news-release/consumerpriceindex_losangeles.htm",
    "S11A": "https://www.bls.gov/regions/new-england/news-release/consumerpriceindex_boston.htm",
    "S37A": "https://www.bls.gov/regions/southwest/news-release/consumerpriceindex_dallasfortworth.htm",
    "S49D": "https://www.bls.gov/regions/west/news-release/consumerpriceindex_seattle.htm",
}

SCHEMA9 = """
CREATE TABLE IF NOT EXISTS p9_area(area_code TEXT PRIMARY KEY, area_name TEXT, cbsa TEXT, cbsa_name TEXT,
    qcew_area TEXT, zori_region TEXT, pop2020 INT, schedule TEXT, approx_geo INT, first_ym TEXT, last_ym TEXT);
CREATE TABLE IF NOT EXISTS p9_cpi(area_code TEXT, area_name TEXT, item_code TEXT, ym TEXT, idx REAL, yoy REAL,
    PRIMARY KEY(area_code, item_code, ym));
CREATE INDEX IF NOT EXISTS p9_cpi_ym ON p9_cpi(item_code, ym);
CREATE TABLE IF NOT EXISTS p9_wage(cbsa TEXT, yq TEXT, own_code TEXT, avg_wkly_wage REAL, emp REAL,
    disclosed INT, yoy REAL, PRIMARY KEY(cbsa, yq, own_code));
CREATE TABLE IF NOT EXISTS p9_real(cbsa TEXT, yq TEXT, wage_yoy REAL, cpi_yoy REAL, real_yoy REAL,
    cpi_month_used TEXT, wage_own TEXT, PRIMARY KEY(cbsa, yq));
CREATE TABLE IF NOT EXISTS p9_zori(region TEXT, cbsa TEXT, ym TEXT, zori REAL, yoy REAL, PRIMARY KEY(cbsa, ym));
CREATE TABLE IF NOT EXISTS p9_shelter(cbsa TEXT, ym TEXT, cpi_rent_yoy REAL, cpi_shelter_yoy REAL,
    zori_yoy_l12 REAL, gap REAL, PRIMARY KEY(cbsa, ym));
CREATE TABLE IF NOT EXISTS p9_lag(cbsa TEXT, lag INT, corr REAL, n INT, PRIMARY KEY(cbsa, lag));
CREATE TABLE IF NOT EXISTS p9_disp(ym TEXT PRIMARY KEY, n_metros INT, mean REAL, sd REAL,
    min_metro TEXT, min_yoy REAL, max_metro TEXT, max_yoy REAL, range REAL, comp_flag INT, comp_delta REAL);
"""

AREAS = [r[0] for r in CROSSWALK]
CBSA_OF = {r[0]: r[2] for r in CROSSWALK}
NAME_OF = {r[0]: r[1] for r in CROSSWALK}
POP_OF = {r[2]: r[5] for r in CROSSWALK}
AREA_OF_CBSA = {r[2]: r[0] for r in CROSSWALK}


# --------------------------------------------------------------------------- helpers
def read_tsv(path, usecols=None):
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, usecols=usecols)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


def lag_merge(df, keys, val, k, per="ym", freq="M"):
    """Value of `val` from k calendar periods earlier, aligned to df's rows.

    Row-offset shifts are wrong here twice over: metro series skip every other month by
    design, and 2025-10 is missing for everyone.  Merging on a shifted PeriodIndex is the
    only safe way to say "12 calendar months ago"."""
    left = df[keys + [per]].copy()
    right = df[keys + [per, val]].copy()
    right[per] = (pd.PeriodIndex(right[per], freq=freq) + k).astype(str)
    out = left.merge(right, on=keys + [per], how="left")[val]
    out.index = df.index
    return out


def wmean_wsd(x, w):
    """Population-weighted mean and (population-weighted) standard deviation."""
    w = np.asarray(w, float); x = np.asarray(x, float)
    m = np.isfinite(x) & np.isfinite(w) & (w > 0)
    x, w = x[m], w[m]
    if len(x) == 0:
        return np.nan, np.nan
    mu = float((w * x).sum() / w.sum())
    sd = float(np.sqrt((w * (x - mu) ** 2).sum() / w.sum()))
    return mu, sd


# --------------------------------------------------------------------------- 1. metro CPI
def load_cpi(con, history=False, force=False):
    """Load the 23 metro areas x 6 items from the cu flat files into p9_cpi.

    Everything comes out of the same files P0 already caches, so the loader is deliberately
    the same shape as p0_fetch.read_tsv/load_data: filter by series_id, keep monthly periods,
    numeric-coerce.  We do NOT widen cpi_obs - metro rows would multiply that table by ~20x
    and every downstream pipeline assumes cpi_obs is US-city-average only."""
    d = RAW / "cu"
    keep = {f"CUUR{a}{i}" for a in AREAS for i in ITEMS}
    files = ["cu.data.0.Current"] + (HISTORY_FILES if history else [])
    frames, changed_any = [], False
    for f in files:
        path, changed = fetch(BLS_TS + "cu/" + f, d / f, force=force)
        changed_any |= changed
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, usecols=[0, 1, 2, 3])
        df.columns = [c.strip() for c in df.columns]
        df["series_id"] = df.series_id.str.strip()
        df = df[df.series_id.isin(keep)]
        df = df[df.period.str.strip().str.startswith("M") & (df.period.str.strip() != "M13")]
        log.info("p9 cpi: %s -> %d metro rows (%s)", f, len(df), "changed" if changed else "cached")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["value"] = pd.to_numeric(df.value.str.strip(), errors="coerce")
    df["ym"] = df.year.str.strip() + "-" + df.period.str.strip().str[1:]
    df["area_code"] = df.series_id.str[4:8]
    df["item_code"] = df.series_id.str[8:]
    df = df.dropna(subset=["value"])
    # de-duplicate: Current and the history files overlap on recent years; keep one row per cell
    df = df.sort_values("ym").drop_duplicates(["area_code", "item_code", "ym"], keep="last")
    df = df.rename(columns={"value": "idx"})[["area_code", "item_code", "ym", "idx"]]
    df = df.sort_values(["area_code", "item_code", "ym"]).reset_index(drop=True)
    prev = lag_merge(df, ["area_code", "item_code"], "idx", 12)
    df["yoy"] = (df.idx / prev - 1) * 100          # NULL wherever the 12-months-ago cell is absent
    df["area_name"] = df.area_code.map(NAME_OF)
    con.execute("DELETE FROM p9_cpi")
    con.executemany("INSERT INTO p9_cpi VALUES(?,?,?,?,?,?)",
                    df[["area_code", "area_name", "item_code", "ym", "idx", "yoy"]]
                    .astype(object).where(df[["area_code", "area_name", "item_code", "ym", "idx", "yoy"]].notna(), None)
                    .values.tolist())
    con.commit()
    n_yoy = int(df.yoy.notna().sum())
    log.info("p9_cpi: %d rows, %d with YoY, %d areas, items %s, %s..%s",
             len(df), n_yoy, df.area_code.nunique(), sorted(df.item_code.unique()), df.ym.min(), df.ym.max())
    return df, changed_any


def derive_schedule(con):
    """Classify each metro monthly / odd / even from the published all-items months.

    Derived, not hard-coded: this is the one fact about the metro CPI that circulating
    reference lists get wrong.  Uses the last five complete years of SA0 and excludes
    2025-10 (no CPI at all that month)."""
    df = pd.read_sql("SELECT area_code, ym FROM p9_cpi WHERE item_code='SA0'", con)
    last = df.ym.max()
    start = (pd.Period(last, freq="M") - 59).strftime("%Y-%m")
    df = df[(df.ym >= start) & (df.ym != "2025-10")]
    df["mo"] = df.ym.str[5:7].astype(int)
    out = {}
    for a, g in df.groupby("area_code"):
        n = len(g)
        months_possible = len(pd.period_range(max(start, g.ym.min()), last, freq="M")) - 1  # -1 for 2025-10
        odd = int((g.mo % 2 == 1).sum())
        if n >= 0.9 * months_possible:
            out[a] = "monthly"
        else:
            out[a] = "odd" if odd > n - odd else "even"
    log.info("schedule: monthly=%s", sorted(k for k, v in out.items() if v == "monthly"))
    log.info("schedule: odd=%s", sorted(k for k, v in out.items() if v == "odd"))
    log.info("schedule: even=%s", sorted(k for k, v in out.items() if v == "even"))
    return out


def load_area(con, sched):
    rng = pd.read_sql("SELECT area_code, MIN(ym) f, MAX(ym) l FROM p9_cpi WHERE item_code='SA0' GROUP BY 1", con)
    rng = dict(zip(rng.area_code, zip(rng.f, rng.l)))
    rows = []
    for a, name, cbsa, qcew, zori, pop in CROSSWALK:
        f, l = rng.get(a, (None, None))
        rows.append((a, name, cbsa, name, qcew, zori, pop, sched.get(a), int(a in APPROX_GEO), f, l))
    con.execute("DELETE FROM p9_area")
    con.executemany("INSERT INTO p9_area VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    log.info("p9_area: %d metros", len(rows))


def check_population():
    """Cross-check the hard-coded 2020 populations against the Census estimates file."""
    try:
        path, _ = fetch(CENSUS_POP, RAW / "p9" / "cbsa-est2022.csv", retries=1)
        d = pd.read_csv(path, dtype=str, encoding_errors="ignore")
        d = d[d.LSAD == "Metropolitan Statistical Area"].set_index("CBSA")
        bad = []
        for r in CROSSWALK:
            if r[2] in d.index:
                ref = float(d.loc[r[2], "ESTIMATESBASE2020"])
                if abs(ref - r[5]) / ref > 0.02:
                    bad.append((r[0], r[5], ref))
            else:
                bad.append((r[0], r[5], None))
        log.info("population cross-check vs Census: %d/%d within 2%%%s",
                 len(CROSSWALK) - len(bad), len(CROSSWALK), "" if not bad else f" MISMATCH {bad}")
        return len(bad) == 0, bad
    except Exception as e:
        log.warning("population cross-check unavailable (%s) - using hard-coded values", e)
        return None, []


# --------------------------------------------------------------------------- 2. QCEW wages
def qcew_quarters(start_year):
    today = dt.date.today()
    end = (today.year, (today.month - 1) // 3 + 1)
    out = []
    y, q = start_year, 1
    while (y, q) <= end:
        out.append((y, q))
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return out


def load_qcew(con, start_year=2015, force=False):
    """Fetch one industry-10 slice per quarter, keep our 23 MSAs x own_code {0,5}.

    Cache holds the FILTERED rows (a few hundred bytes) rather than the 3.7 MB source file:
    the slice covers every county/state/CSA in the country and we need 46 rows of it.
    Existing quarters are skipped; the two most recent cached quarters are re-fetched every
    run because QCEW revises back."""
    d = RAW / "qcew"
    d.mkdir(parents=True, exist_ok=True)
    want = set(r[3] for r in CROSSWALK)
    qs = qcew_quarters(start_year)
    cached = sorted(p.stem for p in d.glob("ind10_*.csv"))
    refresh = set(cached[-2:]) if cached and not force else set()
    frames, misses, fetched = [], 0, 0
    for y, q in qs:
        stem = f"ind10_{y}q{q}"
        p = d / f"{stem}.csv"
        if p.exists() and not force and stem not in refresh:
            frames.append(pd.read_csv(p, dtype=str))
            continue
        url = QCEW_URL.format(y=y, q=q)
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=300)
        except Exception as e:
            log.warning("qcew %sQ%s fetch failed (%s)", y, q, e)
            misses += 1
            if misses >= 2 and not p.exists():
                break
            continue
        if not r.ok or len(r.content) < 50000:
            log.info("qcew %sQ%s not published yet (HTTP %s)", y, q, r.status_code)
            misses += 1
            if misses >= 2:
                break
            continue
        misses = 0
        fetched += 1
        df = pd.read_csv(io.StringIO(r.text), dtype=str)
        df = df[df.area_fips.isin(want) & df.own_code.isin(["0", "5"]) & (df.industry_code == "10")]
        df = df[["area_fips", "own_code", "agglvl_code", "year", "qtr", "disclosure_code",
                 "avg_wkly_wage", "month3_emplvl"]]
        df.to_csv(p, index=False)
        frames.append(df.astype(str))
        time.sleep(0.4)
    if not frames:
        log.warning("qcew: nothing loaded")
        return pd.DataFrame()
    w = pd.concat(frames, ignore_index=True)
    w["cbsa"] = w.area_fips.map({r[3]: r[2] for r in CROSSWALK})
    w["yq"] = w.year.astype(str) + "Q" + w.qtr.astype(str)
    w["avg_wkly_wage"] = pd.to_numeric(w.avg_wkly_wage, errors="coerce")
    w["emp"] = pd.to_numeric(w.month3_emplvl, errors="coerce")
    # BLS writes a suppressed cell as disclosure_code '-' with zeros, not as a blank
    w["disclosed"] = ((w.avg_wkly_wage > 0) & (w.disclosure_code.fillna("") != "-")).astype(int)
    w.loc[w.disclosed == 0, ["avg_wkly_wage", "emp"]] = np.nan
    w = w.drop_duplicates(["cbsa", "yq", "own_code"]).sort_values(["cbsa", "own_code", "yq"]).reset_index(drop=True)
    w["yoy"] = (w.avg_wkly_wage / lag_merge(w, ["cbsa", "own_code"], "avg_wkly_wage", 4, per="yq", freq="Q") - 1) * 100
    cols = ["cbsa", "yq", "own_code", "avg_wkly_wage", "emp", "disclosed", "yoy"]
    con.execute("DELETE FROM p9_wage")
    con.executemany("INSERT INTO p9_wage VALUES(?,?,?,?,?,?,?)",
                    w[cols].astype(object).where(w[cols].notna(), None).values.tolist())
    con.commit()
    priv = w[(w.own_code == "5") & (w.disclosed == 1)]
    log.info("p9_wage: %d rows, %d fetched quarters, %s..%s; private disclosed through %s, total-covered through %s",
             len(w), fetched, w.yq.min(), w.yq.max(),
             priv.yq.max() if len(priv) else "-", w[w.own_code == "0"].yq.max())
    return w


# --------------------------------------------------------------------------- 3. ZORI
def load_zori(con, force=False):
    """Zillow ZORI metro CSV -> p9_zori, fail-soft.

    Zillow renames these files and reorders columns roughly once a year, and the CSV is wide
    (one column per month).  So: walk the candidate URLs, accept the first that parses into
    the expected shape (a RegionName column plus >=60 YYYY-MM-DD columns), keep it in
    raw/zori/ as the last known good copy, and fall back to that copy when every URL fails.
    A stale ZORI degrades p9_shelter; it must never take the run down."""
    d = RAW / "zori"
    d.mkdir(parents=True, exist_ok=True)
    good = d / "Metro_zori_last_good.csv"
    z, used = None, None
    for u in ZORI_URLS:
        try:
            r = requests.get(u, headers={"User-Agent": UA}, timeout=300)
            if not r.ok or len(r.content) < 100000:
                log.info("zori: %s -> HTTP %s (%d bytes), next candidate", u.rsplit("/", 1)[-1], r.status_code, len(r.content))
                continue
            cand = pd.read_csv(io.StringIO(r.text), dtype={"RegionID": str, "SizeRank": str})
            months = [c for c in cand.columns if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(c))]
            if "RegionName" not in cand.columns or len(months) < 60:
                log.warning("zori: %s parsed but shape unexpected (RegionName=%s, %d month cols) - rejecting",
                            u, "RegionName" in cand.columns, len(months))
                continue
            z, used = cand, u
            good.write_text(r.text)
            (d / "last_good.url").write_text(f"{u}\n{dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}\n")
            log.info("zori: resolved %s (%d regions, %d months, %s..%s)", u, len(cand), len(months), months[0], months[-1])
            break
        except Exception as e:
            log.warning("zori: %s failed (%s)", u, e)
    if z is None:
        if good.exists():
            z = pd.read_csv(good, dtype={"RegionID": str, "SizeRank": str})
            used = "CACHED " + (d / "last_good.url").read_text().splitlines()[0] if (d / "last_good.url").exists() else "CACHED"
            log.warning("zori: EVERY candidate URL failed - using last good copy from %s. "
                        "Zillow has probably renamed the file again; check %s",
                        time.strftime("%Y-%m-%d", time.localtime(good.stat().st_mtime)),
                        "https://www.zillow.com/research/data/")
        else:
            log.error("zori: no source and no cache - p9_zori/p9_shelter left untouched")
            return pd.DataFrame(), None
    months = [c for c in z.columns if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(c))]
    want = {r[4]: r[2] for r in CROSSWALK}
    hit = z[z.RegionName.isin(want)].copy()
    missing = sorted(set(want) - set(hit.RegionName))
    log.info("zori crosswalk: matched %d/%d metros%s", len(hit), len(CROSSWALK),
             "" if not missing else f"; MISSED {missing}")
    long = hit.melt(id_vars=["RegionName"], value_vars=months, var_name="date", value_name="zori")
    long["ym"] = long.date.str[:7]
    long["cbsa"] = long.RegionName.map(want)
    long["zori"] = pd.to_numeric(long.zori, errors="coerce")
    long = long.dropna(subset=["zori"]).rename(columns={"RegionName": "region"})
    long = long.sort_values(["cbsa", "ym"]).reset_index(drop=True)
    long["yoy"] = (long.zori / lag_merge(long, ["cbsa"], "zori", 12) - 1) * 100
    cols = ["region", "cbsa", "ym", "zori", "yoy"]
    con.execute("DELETE FROM p9_zori")
    con.executemany("INSERT INTO p9_zori VALUES(?,?,?,?,?)",
                    long[cols].astype(object).where(long[cols].notna(), None).values.tolist())
    con.commit()
    log.info("p9_zori: %d rows, %d metros, %s..%s", len(long), long.cbsa.nunique(), long.ym.min(), long.ym.max())
    return long, (used, len(hit), missing)


# --------------------------------------------------------------------------- 4. real wages
def build_real(con, sched):
    """wage YoY (quarterly) - all-items CPI YoY (calendar-matched month) per metro-quarter.

    QUARTER-MATCHING RULE.  A quarter's CPI reading is the LAST month inside that quarter for
    which the metro published an all-items index:
        monthly metros   Mar / Jun / Sep / Dec
        odd-month metros Mar / May / Sep / Nov
        even-month metros Feb / Jun / Aug / Dec
    Always inside the quarter (never borrowing the next quarter's month, which would leak
    future information), always the freshest available reading, and stable over time so the
    quarterly real-wage series is not spliced from different months of the quarter.  The month
    actually used is recorded per row in cpi_month_used.  For Q4-2025 the even-month metros
    would normally use October; October 2025 has no CPI, so the rule falls back to the next
    published month inside the quarter and December is used - visible in cpi_month_used."""
    cpi = pd.read_sql("SELECT area_code, ym, yoy FROM p9_cpi WHERE item_code='SA0' AND yoy IS NOT NULL", con)
    cpi["cbsa"] = cpi.area_code.map(CBSA_OF)
    cpi["yq"] = pd.PeriodIndex(cpi.ym, freq="M").asfreq("Q").astype(str)
    # last published month inside each quarter
    cpi = cpi.sort_values("ym").groupby(["cbsa", "yq"], as_index=False).last()
    cpi = cpi.rename(columns={"yoy": "cpi_yoy", "ym": "cpi_month_used"})

    w = pd.read_sql("SELECT cbsa, yq, own_code, yoy FROM p9_wage WHERE yoy IS NOT NULL", con)
    piv = w.pivot_table(index=["cbsa", "yq"], columns="own_code", values="yoy").reset_index()
    for c in ("0", "5"):
        if c not in piv:
            piv[c] = np.nan
    piv["wage_yoy"] = piv["5"].where(piv["5"].notna(), piv["0"])
    piv["wage_own"] = np.where(piv["5"].notna(), "5", np.where(piv["0"].notna(), "0", None))
    piv = piv[piv.wage_yoy.notna()]

    r = piv.merge(cpi[["cbsa", "yq", "cpi_yoy", "cpi_month_used"]], on=["cbsa", "yq"], how="inner")
    r["real_yoy"] = r.wage_yoy - r.cpi_yoy
    cols = ["cbsa", "yq", "wage_yoy", "cpi_yoy", "real_yoy", "cpi_month_used", "wage_own"]
    con.execute("DELETE FROM p9_real")
    con.executemany("INSERT INTO p9_real VALUES(?,?,?,?,?,?,?)",
                    r[cols].astype(object).where(r[cols].notna(), None).values.tolist())
    con.commit()
    # how much does the ownership basis matter, where both exist?
    both = piv[piv["5"].notna() & piv["0"].notna()]
    log.info("p9_real: %d metro-quarters, %s..%s; %d rows use total-covered wages (private suppressed); "
             "private-vs-total wage YoY differ by %.2f pp on average where both exist",
             len(r), r.yq.min(), r.yq.max(), int((r.wage_own == "0").sum()),
             float((both["5"] - both["0"]).abs().mean()) if len(both) else float("nan"))
    return r


# --------------------------------------------------------------------------- 5. shelter
def build_shelter(con):
    """CPI rent/shelter YoY vs ZORI YoY lagged 12 months, plus the lag 0..18 correlation profile."""
    cpi = pd.read_sql("SELECT area_code, item_code, ym, yoy FROM p9_cpi "
                      "WHERE item_code IN ('SEHA','SAH1') AND yoy IS NOT NULL", con)
    cpi["cbsa"] = cpi.area_code.map(CBSA_OF)
    piv = cpi.pivot_table(index=["cbsa", "ym"], columns="item_code", values="yoy").reset_index()
    piv = piv.rename(columns={"SEHA": "cpi_rent_yoy", "SAH1": "cpi_shelter_yoy"})
    for c in ("cpi_rent_yoy", "cpi_shelter_yoy"):
        if c not in piv:
            piv[c] = np.nan

    z = pd.read_sql("SELECT cbsa, ym, yoy FROM p9_zori WHERE yoy IS NOT NULL", con)
    z12 = z.copy()
    z12["ym"] = (pd.PeriodIndex(z12.ym, freq="M") + 12).astype(str)
    z12 = z12.rename(columns={"yoy": "zori_yoy_l12"})
    s = piv.merge(z12, on=["cbsa", "ym"], how="inner")
    s["gap"] = s.cpi_rent_yoy - s.zori_yoy_l12
    cols = ["cbsa", "ym", "cpi_rent_yoy", "cpi_shelter_yoy", "zori_yoy_l12", "gap"]
    s = s[cols].dropna(subset=["cpi_rent_yoy", "zori_yoy_l12"]).sort_values(["cbsa", "ym"])
    con.execute("DELETE FROM p9_shelter")
    con.executemany("INSERT INTO p9_shelter VALUES(?,?,?,?,?,?)",
                    s.astype(object).where(s.notna(), None).values.tolist())

    # lag profile: corr(cpi_rent_yoy[t], zori_yoy[t-L]) for L = 0..18
    zi = z.set_index(["cbsa", "ym"]).yoy
    rows = []
    for cbsa, g in piv.dropna(subset=["cpi_rent_yoy"]).groupby("cbsa"):
        for L in range(0, 19):
            shifted = (pd.PeriodIndex(g.ym, freq="M") - L).astype(str)
            zz = pd.Series([zi.get((cbsa, m), np.nan) for m in shifted], index=g.index)
            d = pd.concat([g.cpi_rent_yoy, zz.rename("z")], axis=1).dropna()
            rows.append((cbsa, L, float(d.cpi_rent_yoy.corr(d.z)) if len(d) >= 24 else None, len(d)))
    con.execute("DELETE FROM p9_lag")
    con.executemany("INSERT INTO p9_lag VALUES(?,?,?,?)", rows)
    con.commit()
    lg = pd.DataFrame(rows, columns=["cbsa", "lag", "corr", "n"]).dropna(subset=["corr"])
    best = lg.loc[lg.groupby("cbsa")["corr"].idxmax()] if len(lg) else pd.DataFrame()
    log.info("p9_shelter: %d rows, %d metros; lag profile over %d metros, median best lag %s months",
             len(s), s.cbsa.nunique(), best.cbsa.nunique() if len(best) else 0,
             float(best["lag"].median()) if len(best) else float("nan"))
    return s, lg, best


# --------------------------------------------------------------------------- 6. dispersion
def build_disp(con):
    """Population-weighted cross-metro spread of all-items YoY, month by month.

    Only metros that actually published that month are in that month's cross-section, and a
    month needs n>=8 to be reported at all.  Because the odd and even panels are different
    sets of cities, the level of the mean jumps between adjacent months for reasons that have
    nothing to do with inflation; comp_delta measures exactly that jump against a 3-month
    centered average of the same statistic and comp_flag marks it when it exceeds 0.3 pp."""
    df = pd.read_sql("SELECT area_code, ym, yoy FROM p9_cpi WHERE item_code='SA0' AND yoy IS NOT NULL "
                     "AND ym >= ?", con, params=(DISP_FROM,))
    df["cbsa"] = df.area_code.map(CBSA_OF)
    df["pop"] = df.cbsa.map(POP_OF)
    df["name"] = df.area_code.map(NAME_OF)
    rows = []
    for ym, g in df.groupby("ym"):
        if len(g) < 8:
            continue
        mu, sd = wmean_wsd(g.yoy, g["pop"])
        lo = g.loc[g.yoy.idxmin()]; hi = g.loc[g.yoy.idxmax()]
        rows.append(dict(ym=ym, n_metros=len(g), mean=mu, sd=sd,
                         min_metro=lo["name"], min_yoy=float(lo.yoy),
                         max_metro=hi["name"], max_yoy=float(hi.yoy),
                         range=float(hi.yoy - lo.yoy)))
    d = pd.DataFrame(rows).sort_values("ym").reset_index(drop=True)
    if d.empty:
        log.warning("p9_disp: no month reaches n>=8")
        return d
    idx = d.set_index("ym")["mean"]
    prev = [(pd.Period(m, freq="M") - 1).strftime("%Y-%m") for m in d.ym]
    nxt = [(pd.Period(m, freq="M") + 1).strftime("%Y-%m") for m in d.ym]
    p_ = np.array([idx.get(m, np.nan) for m in prev])
    n_ = np.array([idx.get(m, np.nan) for m in nxt])
    mean3 = (p_ + d["mean"].values + n_) / 3.0
    d["comp_delta"] = d["mean"].values - mean3
    d["comp_flag"] = (d.comp_delta.abs() > 0.3).astype("Int64")
    d.loc[d.comp_delta.isna(), "comp_flag"] = pd.NA
    cols = ["ym", "n_metros", "mean", "sd", "min_metro", "min_yoy", "max_metro", "max_yoy",
            "range", "comp_flag", "comp_delta"]
    con.execute("DELETE FROM p9_disp")
    con.executemany("INSERT INTO p9_disp VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    d[cols].astype(object).where(d[cols].notna(), None).values.tolist())
    con.commit()
    flagged = int(d.comp_flag.fillna(0).sum())
    log.info("p9_disp: %d months (%s..%s), %d flagged for odd/even composition shift >0.3 pp",
             len(d), d.ym.min(), d.ym.max(), flagged)
    return d


# --------------------------------------------------------------------------- 7. validation
def validate(con, zori_info, pop_ok, pop_bad):
    """(a) our loader reproduces P0's U.S.-city-average SA0 exactly (same source file);
       (b) spot-check metro 12-month changes against the BLS regional news releases;
       (c) crosswalk: ZORI matched for >=20 of 23 metros."""
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    out, ok_all = [], True

    # (a) identical-source check: reload area 0000 SA0 with THIS loader and diff against p0
    path = RAW / "cu" / "cu.data.0.Current"
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, usecols=[0, 1, 2, 3])
    df.columns = [c.strip() for c in df.columns]
    df["series_id"] = df.series_id.str.strip()
    us = df[df.series_id == "CUUR0000SA0"].copy()
    us = us[us.period.str.strip().str.startswith("M") & (us.period.str.strip() != "M13")]
    us["ours"] = pd.to_numeric(us.value.str.strip(), errors="coerce")
    us["ym"] = us.year.str.strip() + "-" + us.period.str.strip().str[1:]
    p0 = pd.read_sql("SELECT ym, idx_nsa FROM cpi_item_month WHERE item_code='SA0'", con)
    j = us[["ym", "ours"]].merge(p0, on="ym", how="inner")
    diff = float((j.ours - j.idx_nsa).abs().max()) if len(j) else float("nan")
    ok = len(j) > 0 and diff < 1e-9
    ok_all &= ok
    con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                (now, "p9_us_sa0_matches_p0", j.ym.max() if len(j) else None, diff, 0.0, diff, int(ok)))
    log.info("validate US SA0 vs P0: %d common months, max |diff| = %.6f  %s", len(j), diff, "OK" if ok else "MISMATCH")
    out.append(dict(check="us_sa0_matches_p0", n_months=len(j), max_abs_diff=diff, ok=bool(ok),
                    note="same cu.data.0.Current file read by this loader and by P0; must be bit-identical"))

    # (b) published spot check against the BLS regional news releases
    pat12 = re.compile(r"all items CPI-U\s+((?:\w+\s+){0,3}?)([\d.]+)\s+percent for the 12 months ending in\s+([A-Za-z]+)", re.I)
    pat_sub = re.compile(r"(up|down)\s+([\d.]+)\s+percent (?:over the year|from a year ago)", re.I)
    # the dash between area and month is an en-dash that survives the round trip badly, so key
    # on the month name instead of the punctuation
    MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
    pat_title = re.compile(r"Consumer Price Index,.{0,90}?(" + MONTHS + r")\s+(\d{4})")
    NEG = ("declin", "fell", "decreas", "down", "dropp", "lower")
    cpi = pd.read_sql("SELECT area_code, ym, yoy FROM p9_cpi WHERE item_code='SA0' AND yoy IS NOT NULL", con)
    cpi = cpi.set_index(["area_code", "ym"]).yoy
    spot = []
    for a, url in NEWS.items():
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
            if not r.ok:
                spot.append(dict(area=a, ok=None, note=f"HTTP {r.status_code}")); continue
            t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
            ttl = pat_title.search(t)
            if not ttl:
                spot.append(dict(area=a, ok=None, note="could not date the release")); continue
            m = pat12.search(t)
            if m:
                verb, val = m.group(1).lower(), float(m.group(2))
            else:
                m = pat_sub.search(t)
                if not m:
                    spot.append(dict(area=a, ok=None, note="no parseable 12-month sentence")); continue
                verb, val = m.group(1).lower(), float(m.group(2))
            if any(k in verb for k in NEG):
                val = -val
            ym = f"{ttl.group(2)}-{dt.datetime.strptime(ttl.group(1)[:3], '%b').month:02d}"
            ours = cpi.get((a, ym))
            if ours is None or not np.isfinite(ours):
                spot.append(dict(area=a, ym=ym, ok=None, note="no computed YoY for that month")); continue
            dd = float(ours) - val
            k = abs(dd) <= 0.06        # releases are rounded to 0.1 pp
            ok_all &= k
            con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                        (now, f"p9_newsrelease_{a}", ym, float(ours), val, dd, int(k)))
            log.info("validate %s (%s) %s: ours %+.2f%% vs published %+.1f%% (diff %+.2f) %s",
                     a, NAME_OF[a].split(",")[0], ym, ours, val, dd, "OK" if k else "MISMATCH")
            spot.append(dict(area=a, name=NAME_OF[a], ym=ym, ours=round(float(ours), 2),
                             published=val, diff=round(dd, 3), ok=bool(k)))
        except Exception as e:
            spot.append(dict(area=a, ok=None, note=f"fetch/parse failed: {e}"))
    out.append(dict(check="news_release_spot_check", results=spot,
                    note="BLS regional news releases print the 12-month change rounded to 0.1 pp; "
                         "tolerance 0.06 pp"))

    # (c) crosswalk coverage
    n_hit = zori_info[1] if zori_info else 0
    missed = zori_info[2] if zori_info else [r[4] for r in CROSSWALK]
    ok = n_hit >= 20
    ok_all &= ok
    con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                (now, "p9_zori_crosswalk", None, n_hit, 23, n_hit - 23, int(ok)))
    log.info("validate ZORI crosswalk: %d/23 matched (need >=20) %s%s", n_hit, "OK" if ok else "FAIL",
             "" if not missed else f" missing {missed}")
    out.append(dict(check="zori_crosswalk", matched=n_hit, of=23, required=20, ok=bool(ok), missing=missed))
    out.append(dict(check="population_vs_census", ok=pop_ok, mismatches=pop_bad,
                    note="hard-coded 2020 CBSA populations vs the Census cbsa-est2022 ESTIMATESBASE2020 column"))
    con.commit()
    return out, ok_all


# --------------------------------------------------------------------------- 8. JSON
def json_out(con, sched, lg, best, zori_info, val):
    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if o is pd.NA or o is None:
            return None
        if isinstance(o, (float, np.floating)):
            return round(float(o), 4) if np.isfinite(o) else None
        return o

    area = pd.read_sql("SELECT * FROM p9_area", con)
    cpi = pd.read_sql("SELECT * FROM p9_cpi WHERE yoy IS NOT NULL", con)
    real = pd.read_sql("SELECT * FROM p9_real", con)
    shel = pd.read_sql("SELECT * FROM p9_shelter", con)
    disp = pd.read_sql("SELECT * FROM p9_disp ORDER BY ym", con)
    zori = pd.read_sql("SELECT * FROM p9_zori WHERE yoy IS NOT NULL", con)
    latest_cpi = cpi.ym.max()
    latest_q = real.yq.max() if len(real) else None
    cutoff = (pd.Period(latest_cpi, freq="M") - 95).strftime("%Y-%m")

    bestmap = {r["cbsa"]: (int(r["lag"]), float(r["corr"])) for _, r in best.iterrows()} if len(best) else {}
    metros = []
    for a in area.itertuples():
        c = cpi[cpi.area_code == a.area_code]
        latest_row = {}
        for it in ITEMS:
            g = c[c.item_code == it]
            if len(g):
                g = g.sort_values("ym").iloc[-1]
                latest_row[it] = dict(ym=g.ym, yoy=g.yoy)
        rr = real[real.cbsa == a.cbsa]
        rr = rr.sort_values("yq").iloc[-1].to_dict() if len(rr) else None
        ss = shel[shel.cbsa == a.cbsa]
        ss = ss.sort_values("ym").iloc[-1].to_dict() if len(ss) else None
        bl = bestmap.get(a.cbsa)
        metros.append(dict(
            area_code=a.area_code, area_name=a.area_name, cbsa=a.cbsa, qcew_area=a.qcew_area,
            zori_region=a.zori_region, pop2020=a.pop2020, schedule=a.schedule,
            approx_geo=bool(a.approx_geo), cpi_first_ym=a.first_ym, cpi_last_ym=a.last_ym,
            latest_cpi=latest_row,
            latest_real=None if rr is None else dict(
                yq=rr["yq"], wage_yoy=rr["wage_yoy"], cpi_yoy=rr["cpi_yoy"], real_yoy=rr["real_yoy"],
                cpi_month_used=rr["cpi_month_used"], wage_own=rr["wage_own"]),
            latest_shelter=None if ss is None else dict(
                ym=ss["ym"], cpi_rent_yoy=ss["cpi_rent_yoy"], cpi_shelter_yoy=ss["cpi_shelter_yoy"],
                zori_yoy_l12=ss["zori_yoy_l12"], gap=ss["gap"]),
            best_lag=None if bl is None else dict(lag=bl[0], corr=bl[1])))

    map_arr = []
    for a in area.itertuples():
        rr = real[real.cbsa == a.cbsa].sort_values("yq")
        map_arr.append(dict(cbsa=a.cbsa, area_code=a.area_code, name=a.area_name.split(",")[0],
                            pop2020=a.pop2020, approx_geo=bool(a.approx_geo),
                            real_yoy=[[r.yq, r.real_yoy] for r in rr.itertuples()]))

    sm = []
    for a in area.itertuples():
        g = shel[(shel.cbsa == a.cbsa) & (shel.ym >= cutoff)].sort_values("ym")
        if len(g):
            sm.append(dict(cbsa=a.cbsa, name=a.area_name.split(",")[0], schedule=a.schedule,
                           series=[[r.ym, r.cpi_rent_yoy, r.zori_yoy_l12] for r in g.itertuples()]))

    lagtab = []
    for a in area.itertuples():
        g = lg[lg.cbsa == a.cbsa].sort_values("lag") if len(lg) else pd.DataFrame()
        if len(g):
            bl = bestmap.get(a.cbsa)
            lagtab.append(dict(cbsa=a.cbsa, name=a.area_name.split(",")[0],
                               best_lag=None if bl is None else bl[0],
                               best_corr=None if bl is None else bl[1],
                               n=int(g.n.max()),
                               corr_by_lag=[[int(r["lag"]), r["corr"]] for _, r in g.iterrows()]))

    doc = dict(
        schema={
            "generated_at": "UTC ISO timestamp of this run",
            "coverage": "latest CPI month / wage quarter / ZORI month actually present",
            "metros[]": "one per CPI self-representing metro: crosswalk fields, publication schedule "
                        "('monthly'|'odd'|'even'), latest_cpi{item:{ym,yoy}} for SA0/SAH1/SEHA/SEHC01/SAF/SA0E, "
                        "latest_real{yq,wage_yoy,cpi_yoy,real_yoy,cpi_month_used,wage_own}, "
                        "latest_shelter{ym,cpi_rent_yoy,cpi_shelter_yoy,zori_yoy_l12,gap}, best_lag{lag,corr}. "
                        "approx_geo=true means the CPI pricing area is wider than the CBSA joined to "
                        "(Urban Hawaii, Urban Alaska).",
            "map[]": "map-ready: {cbsa, area_code, name, pop2020, real_yoy:[[yq, pp], ...]}",
            "dispersion[]": "{ym, n_metros, mean, sd, min_metro, min_yoy, max_metro, max_yoy, range, "
                            "comp_flag, comp_delta} - population-weighted across metros publishing that "
                            "month, n>=8 only. comp_delta = mean[t] - mean of (t-1,t,t+1); comp_flag=1 when "
                            "|comp_delta| > 0.3 pp, i.e. the odd/even panel swap is moving the mean.",
            "shelter_small_multiples[]": "last 8 years of {ym, cpi_rent_yoy, zori_yoy_l12} per metro",
            "best_lag_table[]": "corr(cpi_rent_yoy[t], zori_yoy[t-lag]) for lag 0..18 plus the argmax",
            "validation[]": "checks run this pass",
            "units": "all *_yoy and gap are percent / percentage points; real_yoy = wage_yoy - cpi_yoy",
            "caveats": "NSA only (there is no seasonally adjusted metro CPI). 20 of 23 metros publish "
                       "every other month. QCEW private wages are suppressed at MSA level from 2025Q3; "
                       "wage_own says which ownership basis a row used. Nothing is interpolated.",
        },
        generated_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        coverage=dict(latest_cpi_month=latest_cpi, latest_wage_quarter=latest_q,
                      latest_zori_month=zori.ym.max() if len(zori) else None,
                      n_metros=len(area), zori_source=(zori_info[0] if zori_info else None)),
        metros=metros, map=map_arr,
        dispersion=disp.to_dict("records"),
        shelter_small_multiples=sm, best_lag_table=lagtab, validation=val)

    p = OUT / "p9_metro.json"
    p.write_text(json.dumps(clean(doc), indent=1, allow_nan=False))
    log.info("wrote %s (%.0f KB)", p, p.stat().st_size / 1024)
    return doc


# --------------------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__); return 0
    force = "--force" in args
    qfrom = 2015
    if "--qcew-from" in args:
        qfrom = int(args[args.index("--qcew-from") + 1])
    con = init_db()
    con.executescript(SCHEMA9); con.commit()

    load_cpi(con, history=("--history" in args), force=force)
    sched = derive_schedule(con)
    load_area(con, sched)
    pop_ok, pop_bad = check_population()

    if "--no-qcew" not in args:
        load_qcew(con, start_year=qfrom, force=force)
    zori_info = None
    if "--no-zori" not in args:
        _, zori_info = load_zori(con, force=force)

    build_real(con, sched)
    _, lg, best = build_shelter(con)
    build_disp(con)
    val, ok = validate(con, zori_info, pop_ok, pop_bad)
    json_out(con, sched, lg, best, zori_info, val)
    log.info("P9 done (validation %s)", "OK" if ok else "CHECK FAILED")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
