#!/usr/bin/env python3
"""P6 - producer-price "pressure in the pipe" (Tier 1 descriptive + Tier 2 honest numbers).

  p6_pipeline.py [--since=YYYY-MM] [--max-lag=18] [--pressure-months=36]
                 [--roll-years=10] [--force] [--no-ei] [--help]

Some CPI items sit downstream of a producer price that BLS measures separately.  P6 takes a
*hand-built* concordance of PPI commodity series to CPI item codes, measures how the two have
co-moved historically (cross-correlogram + local-projection pass-through with HAC standard
errors), and then does one piece of arithmetic: "if the last few months of producer-price
surprises pass through the way they have on average since ~1990, how many basis points of
CPI would that be?".

**That number is not a forecast.**  It is historical-relationship arithmetic: a recent
producer-price deviation multiplied by a regression coefficient estimated on the past.  The
coefficients are regime-dependent - the rolling 10-year range printed next to every point
estimate is usually a factor of two or more wide - and nothing here models demand, margins,
inventories, exchange rates, or the retailer's decision to eat a cost increase.  A pass-through
beta is a conditional correlation, not a causal elasticity.

--------------------------------------------------------------------------------
DATA
--------------------------------------------------------------------------------
PPI commodity flat files  download.bls.gov/pub/time.series/wp/
  wp.series / wp.item / wp.group are the dimension files.  PPI keys on group_code + item_code
  and the series id is  'WP' + seasonal(S|U) + group_code + item_code.  Only the group data
  files that the concordance actually needs are downloaded (see GROUP_FILES); each holds the
  full history for its group, so wp.data.0.Current is never needed.
  Seasonally adjusted (WPS...) is used when a live SA series exists; a great many WPS series
  were discontinued years ago (dairy 2018, household furniture 2012, pharmaceutical
  preparations 2020, ...) in which case P6 falls back to the NSA (WPU...) twin *and* switches
  the CPI side of that pair to NSA too, so the two sides are always on the same footing.
  For an NSA pair both series have their calendar-month means removed over the estimation
  sample before anything is computed (sa_mode='NSA-dm') - a crude X-11 substitute that stops
  shared seasonality from masquerading as pass-through.

  **PPI is revised.**  Every PPI index is preliminary for four months after first publication
  and is recalculated with late reports each month.  p6_obs is therefore vintaged exactly like
  cpi_obs: one row per (series, month, value) with the pull_id that first carried that value,
  and the view p6_obs_latest picks max(pull_id).  Check `p6_prelim_revision` in `validation`
  for how much the last four months moved at this run.

  FD-ID aggregates (the headline "PPI final demand" family, plus intermediate demand by
  production flow / commodity type) live in the same file set under group codes FD / ID5 / ID6
  and are loaded and published as context series.  They are *not* paired with a CPI item -
  they are a different weighting universe (they include exports, government purchases and
  capital equipment, and exclude imports), so lining them up against the CPI headline would be
  an apples-to-oranges comparison.

Import price indexes  download.bls.gov/pub/time.series/ei/  (ei.data.01.BEAImport)
  Included, but only as an *overlay*: six BEA end-use import categories whose mapping to a CPI
  item is unambiguous (passenger cars, footwear, furniture/household items, household and
  kitchen appliances, TV/video receivers, automotive tires).  Everything else in `ei` is
  either a country-of-origin or a NAICS/Harmonized cut whose relation to a consumer item is
  not clean, so it is skipped.  Import pairs never enter the pressure sum (in_sum=0): they
  measure the border price of a subset of the same goods and would double-count the PPI pair
  on the same CPI item.  They are all NSA (the whole ei programme is), so they run in NSA-dm
  mode.

CPI side  cpi_item_month from P0 (mom_sa / mom_nsa, weight = December relative importance).

--------------------------------------------------------------------------------
CONCORDANCE
--------------------------------------------------------------------------------
P6_PAIRS below is written by hand, one row per CPI item, each carrying a confidence label:

  high  the PPI series covers essentially the same physical good at the stage just before
        retail (gasoline, beef, new passenger cars, physician care, ...)
  med   the PPI series covers the right goods but at a different level of aggregation, or a
        meaningful part of the CPI item is imported / is a service margin the PPI misses
  low   plausible cost input only; expect a weak and unstable relationship

Every PPI series id is verified against wp.series at run time and dropped, with a logged
reason, if it does not exist, has fewer than MIN_YEARS years of monthly observations, or has
stopped being published (its last month must be within LAG_TOL months of the CPI's).  CPI
items whose index has been discontinued are dropped the same way.

Because the concordance mixes levels (both "Meats" and "Beef and veal" are paired), a pair is
only allowed into the pressure *sum* when no other pair's CPI item is a descendant of it in
the cu_item hierarchy - the finer pair wins, the broader one keeps its row but gets in_sum=0.

--------------------------------------------------------------------------------
METHOD
--------------------------------------------------------------------------------
1. Cross-correlogram.  rho_k = corr(PPI MoM at t-k, CPI MoM at t) for k = 0..18, computed
   pairwise-complete on a calendar-complete monthly index (2025-10 has no CPI, so it is a hole,
   never a row offset - see the calendar-complete index rule.  best_lag = argmax_k rho_k over the *signed*
   correlation, not |rho| as P10 does: a negative correlation is not evidence of a slow
   pass-through, it is evidence of no pass-through.

2. Local-projection pass-through (Jorda 2005).  For h in {3, 6, 12},

       sum_{j=0..h} cpi_mom_{t+j}  =  a + beta_h * ppi_mom_t
                                        + g1 cpi_mom_{t-1} + g2 cpi_mom_{t-2} + g3 cpi_mom_{t-3} + e_t

   beta_h is the cumulative percentage-point response of the CPI item over h+1 months to a
   1 pp PPI move in month t.  Overlapping horizons make e_t an MA(h) process, so the standard
   errors are Newey-West (Bartlett kernel) with truncation L = h + floor(4 (n/100)^(2/9)) and a
   n/(n-k) small-sample correction.  Estimated on the full sample (window_end='full') and on
   rolling ROLL_YEARS-year windows ending each June and December plus the latest month; in a
   rolling window t is restricted to the window while the outcome is allowed to run past its
   end, the usual convention.

3. "Pressure in the pipe".  For pair i with best_lag L_i, at month m, each past PPI innovation
   is discounted by the pass-through it has ALREADY delivered, so only what is still to come is
   counted (a raw sum * beta_12 double-counts pass-through that has landed, and scales long-lag
   pairs up mechanically).  An innovation k months old has realised beta_k of its cumulative
   response; the remaining fraction is (beta_12 - beta_k)/beta_12.  Writing that as an effective
   shock lets beta_12 and its SE flow through exactly as before:

       dev_{m-k}   = ppi_mom_{m-k} - mean_5y(ppi_mom)_m
       s_eff_i,m   = sum_{k=0..L_i-1} dev_{m-k} * max(beta_12 - beta_k, 0) / beta_12
       contrib_bp  = s_eff_i,m * beta_12,i * weight_i,m          [bp of headline CPI]
                   = sum_{k} dev_{m-k} * max(beta_12 - beta_k, 0) * weight_i,m
       contrib_se  = |s_eff_i,m| * se(beta_12,i) * weight_i,m

   beta_k is the full-sample local projection at horizon k (k = 0..12).  This assumes pass-
   through is essentially complete within 12 months: k >= 12 counts as fully realised (weight 0),
   so an innovation older than a year adds nothing.  Using se(beta_12) for every term is a
   deliberate, conservative approximation - the true SE of (beta_12 - beta_k) is smaller because
   beta_12 and beta_k are estimated on the same sample and move together.
   (weight is the CPI relative importance in %, so pp * pp^-1 * % lands directly in bp.)
   Pairs with best_lag = 0 contribute exactly zero by construction - there is no pipe if the
   move shows up the same month.  A pair whose pass-through is entirely contemporaneous
   (beta_0 ~= beta_12) likewise contributes ~0: its moves have already hit the CPI.
   The band shown is +/-1 SE aggregated as
   sqrt(sum contrib_se^2), i.e. treating the beta errors as independent across pairs; because
   the pairs share macro shocks that is a *lower* bound, so the comonotone bound
   sum |contrib_se| is reported alongside.  Neither band contains any allowance for the betas
   being wrong in a regime sense - that is what the rolling range is for.

--------------------------------------------------------------------------------
TABLES
--------------------------------------------------------------------------------
p6_series(series_id, source wp|ei, group_code, item_code, seasonal, series_title,
          begin_year, begin_period, end_year, end_period)
p6_obs(series_id, year, period 'M01'..'M12', value, footnote, pull_id)   -- vintaged
p6_obs_latest                                                            -- view, max(pull_id)
p6_pair(pair_id, ppi_series, cpi_item, confidence, best_lag, rho_best,
        source, sa_mode, note, ppi_title, cpi_item_name, n_obs, first_ym, last_ym,
        weight, beta12, se12, beta12_lo, beta12_hi, weak, in_sum, lead_ok, sum_excl)
        lead_ok=0 flags a pair whose correlation is HIGHER at a negative lag (the CPI leading
        the PPI) than at lag 0 - the pipeline story is not supported for that pair
        beta12_lo/hi = min/max of beta_12 across the rolling windows (the regime range)
p6_xcorr(pair_id, lag, rho, n)                                           -- lags 0..MAX_LAG
p6_passthru(pair_id, h, window_end, beta, se, n)                         -- window_end='full' or 'YYYY-MM'
p6_pressure(ym, pair_id, contrib_bp, contrib_se)

validation (shared table) gets: p6_ppi_recency, p6_gasoline_lag, p6_gasoline_beta3,
p6_weak_pair, p6_prelim_revision, p6_pressure_total.

--------------------------------------------------------------------------------
out/p6_pipeline.json
--------------------------------------------------------------------------------
{ "schema": {...}, "generated_at", "latest_cpi_month", "latest_ppi_month", "params": {...},
  "notes": [...],
  "pairs":   [ {pair_id, ppi_series, ppi_title, cpi_item, cpi_item_name, confidence, source,
                sa_mode, note, best_lag, rho_best, n_obs, first_ym, last_ym, weight, weak,
                in_sum, xcorr:[rho_0..rho_18],
                beta: {"3":{beta,se,n}, "6":{...}, "12":{...}}, disc_beta:[beta_0..beta_12],
                beta12_rolling: {window_end:[...], beta:[...], se:[...]},
                small_multiple: {ym:[...], ppi_shifted:[...], cpi:[...]} } ],   # last 8 years
  "pressure": {"ym":[...], "total_bp":[...], "se_bp":[...], "se_bp_comonotone":[...],
               "by_pair": {pair_id: [...]}, "latest": {"ym", "total_bp", "se_bp",
               "top": [{pair_id, contrib_bp, contrib_se}]}},
  "fd_id":   [ {series_id, title, seasonal, ym:[...], index:[...], mom:[...], yoy:[...]} ],
  "weak_pairs": [...], "dropped": [{pair, reason}],
  "validation": [{check_name, ym, ours, published, diff, ok}] }
"""
import sys, json, math, datetime as dt
import numpy as np, pandas as pd
from common import *

MAX_LAG = 18
MIN_YEARS = 15          # a pair needs this many years of monthly PPI data
MIN_XCORR_N = 60        # minimum overlapping months for a correlogram point
MIN_LP_N = 60           # minimum usable rows for a local projection
LAG_TOL = 2             # PPI (or CPI) latest month must be within this many months of CPI latest
ROLL_YEARS = 10
PRESSURE_MONTHS = 36
CPI_LAGS = 3            # own-CPI control lags in the local projection
HORIZONS = (3, 6, 12)
LEAD_LAGS = 3           # negative correlogram lags (CPI leading PPI), alignment diagnostic only
# Acceptance band for the gasoline sanity check's beta_3.  The refinery-gate PPI excludes the
# ~50-60c/gal of fixed federal+state excise tax and the retail margin that the pump price
# carries, so a 1% refinery move is arithmetically ~0.6-0.8% at the pump; the pass-through is
# also nearly complete within a month.  Anything far outside this means the two MoM series are
# not lined up on the same calendar month.  (The build brief's prior of 0.2-0.4 corresponds to
# a same-month-only coefficient or a crude-oil upstream, not to a cumulative 4-month response
# to the gasoline PPI - see docs/P6.md.)
GAS_BETA3_BAND = (0.35, 1.00)
SINCE = "1990-01"       # estimation sample start (PPI service groups only begin 2008-2011)

# ---------------------------------------------------------------- wp data files by group
GROUP_FILES = {
    "00": ["wp.data.1.AllCommodities"], "01": ["wp.data.2.FarmProducts"],
    "02": ["wp.data.3.ProcessedFoods"], "03": ["wp.data.4.Textile"],
    "04": ["wp.data.5.Leather"], "05": ["wp.data.6.Fuels"], "06": ["wp.data.7.Chemicals"],
    "07": ["wp.data.8.Rubber"], "08": ["wp.data.9.Lumber"], "09": ["wp.data.10.Pulp"],
    "10": ["wp.data.11a.Metals10-103", "wp.data.11b.Metals104-109"],
    "11": ["wp.data.12a.Machinery11-113", "wp.data.12b.Machinery114-116", "wp.data.12c.Machinery117-119"],
    "12": ["wp.data.13.Furniture"], "13": ["wp.data.14.Minerals"],
    "14": ["wp.data.15.Transportation"], "15": ["wp.data.16.Miscellaneous"],
    "80": ["wp.data.80.Construction"], "SI": ["wp.data.18.SpecialIndexes"],
    "FD": ["wp.data.22.FD-ID"], "ID5": ["wp.data.22.FD-ID"], "ID6": ["wp.data.22.FD-ID"],
}
for _g in [str(i) for i in range(30, 62)]:      # every service group lives in one file
    GROUP_FILES[_g] = ["wp.data.30.Services"]
EI_FILE = "ei.data.01.BEAImport"

# ---------------------------------------------------------------- the concordance
# (ppi_series_id, cpi_item_code, confidence, note)
# series ids are 'WP' + S|U + group_code + item_code; WPS is preferred where a live SA series
# exists, WPU where BLS discontinued the SA twin (the run-time check reports which was used).
P6_PAIRS = [
    # ---- food, farm-to-shelf -------------------------------------------------------------
    # NB the group-level commodity aggregate WPS02/WPU02 "Processed foods and feeds" is in
    # wp.series but has no observations after 1974, so the FD-ID consumer-foods slice is used
    # instead: it is the same goods measured at the stage that actually feeds a grocery shelf.
    ("WPSFD41112",   "SAF11",    "high", "Finished consumer foods, processed (FD-ID) -> Food at home; "
                                         "the classic aggregate pair"),
    ("WPS022",       "SAF1121",  "high", "Meats, poultry and fish, processed"),
    ("WPS0221",      "SAF11211", "high", "Meats (processed) -> CPI Meats"),
    ("WPS022101",    "SEFC",     "high", "Beef and veal products, fresh or frozen"),
    ("WPS022104",    "SEFD",     "high", "Pork products, fresh/frozen/processed"),
    ("WPS022105",    "SEFE",     "med",  "Other meats, fresh/frozen/canned -> CPI other meats (sausage, lunchmeat)"),
    ("WPS0222",      "SEFF",     "high", "Processed poultry"),
    ("WPS0223",      "SEFG",     "med",  "Unprocessed and prepared seafood; CPI fish is heavily imported"),
    ("WPU023",       "SEFJ",     "high", "Dairy products (SA twin discontinued 2018)"),
    ("WPU0231",      "SEFJ01",   "high", "Fluid milk products -> CPI milk"),
    ("WPU0233",      "SEFJ02",   "high", "Natural, processed and imitation cheese"),
    ("WPS0234",      "SEFJ04",   "med",  "Ice cream and frozen desserts -> other dairy"),
    ("WPS021",       "SAF111",   "high", "Cereal and bakery products"),
    ("WPS0214",      "SEFA",     "med",  "Cereal and pasta products -> cereals and cereal products"),
    ("WPU0211",      "SEFB",     "med",  "Bakery products (SA twin discontinued 2010)"),
    ("WPU017",       "SEFH",     "high", "Chicken eggs, farm gate (SA twin discontinued 2012)"),
    ("WPS0111",      "SEFK",     "med",  "Fresh fruits and melons, farm gate"),
    ("WPS011302",    "SEFL",     "med",  "Fresh vegetables except potatoes, farm gate"),
    ("WPS024101",    "SEFM01",   "med",  "Canned fruits, excluding baby foods -> canned fruits and vegetables"),
    ("WPU026301",    "SEFP01",   "med",  "Coffee (whole bean, ground, instant)"),
    ("WPU0262",      "SEFN",     "med",  "Soft drinks -> juices and nonalcoholic drinks"),
    ("WPU025",       "SEFR",     "med",  "Sugar and confectionery -> sugar and sweets"),
    ("WPU027",       "SEFS",     "med",  "Fats and oils (edible)"),
    ("WPS0261",      "SEFW",     "med",  "Alcoholic beverages, producer -> alcohol at home"),
    ("WPU029402",    "SERB01",   "low",  "Pet food is only part of CPI pets and pet products"),
    # ---- energy ---------------------------------------------------------------------------
    ("WPS0571",      "SETB01",   "high", "Gasoline, refinery gate -> CPI gasoline. SANITY-CHECK PAIR"),
    ("WPS0573",      "SEHE01",   "high", "Light fuel oils -> CPI fuel oil"),
    ("WPS0541",      "SEHF01",   "high", "Residential electric power (a utility tariff, not a factory gate)"),
    ("WPU0531",      "SEHF02",   "high", "Natural gas at the wellhead -> piped gas service (no SA twin)"),
    # ---- transportation --------------------------------------------------------------------
    ("WPS141101",    "SETA01",   "high", "Passenger cars and chassis -> new vehicles"),
    ("WPU071201",    "SETC01",   "high", "Tires (SA twin discontinued 1989)"),
    ("WPS3022",      "SETG01",   "high", "Airline passenger services -> airline fares"),
    ("WPS441",       "SETA04",   "high", "Passenger car rental -> car and truck rental"),
    ("WPU552",       "SETD",     "med",  "Motor vehicle repair and maintenance, partial coverage (SA twin ended 2018)"),
    ("WPU14120508",  "SETC",     "low",  "Other motor vehicle parts; CPI item is retail parts and equipment"),
    # ---- medical ----------------------------------------------------------------------------
    ("WPU0638",      "SEMF01",   "high", "Pharmaceutical preparations -> prescription drugs (SA twin ended 2020). "
                                         "PPI is net of rebates in a way CPI is not"),
    ("WPS511101",    "SEMC01",   "high", "Physician care -> physicians' services"),
    ("WPS511105",    "SEMC02",   "high", "Dental care -> dental services"),
    ("WPS512101",    "SEMD01",   "med",  "Hospital inpatient care -> CPI hospital services (in+outpatient)"),
    ("WPS512102",    "SEMD02",   "med",  "Nursing home care -> nursing homes and adult day services"),
    # ---- apparel ------------------------------------------------------------------------------
    ("WPU0381",      "SAA",      "med",  "Domestic apparel producers only; most CPI apparel is imported"),
    ("WPU159F2",     "SEAE",     "med",  "Footwear, domestic producers; same import caveat"),
    ("WPU1594",      "SEAG02",   "low",  "Jewelry and jewelry products -> CPI jewelry"),
    # ---- household ----------------------------------------------------------------------------
    ("WPU121",       "SEHJ",     "high", "Household furniture (SA twin discontinued 2012)"),
    ("WPU124",       "SEHK",     "high", "Household appliances (SA twin discontinued 2008)"),
    ("WPU123",       "SEHH01",   "med",  "Floor coverings"),
    ("WPU06710402",  "SEHN01",   "med",  "Household detergents -> household cleaning products"),
    ("WPU09150123",  "SEHN02",   "med",  "Sanitary paper products -> household paper products"),
    ("WPU0675",      "SEGB",     "med",  "Cosmetics and other toilet preparations -> personal care products"),
    ("WPU1512",      "SERC",     "low",  "Sporting and athletic goods; CPI sporting goods includes bicycles/boats"),
    # ---- other goods and services -------------------------------------------------------------
    ("WPU1521",      "SEGA01",   "high", "Cigarettes, excluding electronic (SA twin ended 1992). Excise-tax driven"),
    ("WPS531",       "SEHB02",   "med",  "Traveler accommodation services -> hotels and motels"),
    ("WPS451",       "SEGD01",   "med",  "Legal services (CPI legal services index was discontinued in 2024)"),
    ("WPS501",       "SEHG02",   "med",  "Waste collection -> garbage and trash collection"),
    ("WPS372",       "SEED03",   "med",  "Wireless telecommunication services -> wireless telephone services"),
    ("WPU154",       "SERD01",   "low",  "Photographic equipment and supplies; tiny CPI weight"),
]

# import-price overlays: never enter the pressure sum
P6_EI_PAIRS = [
    ("EIUIR300",   "SETA01", "med", "BEA end-use import price, passenger cars new and used"),
    ("EIUIR40040", "SEAE",   "med", "BEA end-use import price, footwear of leather/rubber/other"),
    ("EIUIR41000", "SEHJ",   "med", "BEA end-use import price, furniture and household items"),
    ("EIUIR41030", "SEHK",   "med", "BEA end-use import price, household and kitchen appliances"),
    ("EIUIR41200", "SERA01", "med", "BEA end-use import price, television and video receivers"),
    ("EIUIR30220", "SETC01", "med", "BEA end-use import price, automotive tires and tubes"),
]

# FD-ID context aggregates: (group_code, item_code, short label)
FD_ID_KEEP = [
    ("FD", "4",     "Final demand"),
    ("FD", "41",    "Final demand goods"),
    ("FD", "42",    "Final demand services"),
    ("FD", "411",   "Final demand foods"),
    ("FD", "412",   "Final demand energy"),
    ("FD", "413",   "Final demand goods less foods and energy"),
    ("FD", "49104", "Final demand less foods and energy"),
    ("FD", "49116", "Final demand less foods, energy, and trade services"),
    ("FD", "49207", "Finished goods"),
    ("FD", "49501", "Personal consumption"),
    ("FD", "49502", "Personal consumption goods"),
    ("FD", "49505", "Personal consumption services"),
    ("ID5", "1",    "Stage 1 intermediate demand"),
    ("ID5", "2",    "Stage 2 intermediate demand"),
    ("ID5", "3",    "Stage 3 intermediate demand"),
    ("ID5", "4",    "Stage 4 intermediate demand"),
    ("ID6", "1",    "Intermediate demand, processed goods"),
    ("ID6", "2",    "Intermediate demand, unprocessed goods"),
    ("ID6", "3",    "Intermediate demand, services"),
]

SCHEMA6 = """
CREATE TABLE IF NOT EXISTS p6_series(series_id TEXT PRIMARY KEY, source TEXT, group_code TEXT,
  item_code TEXT, seasonal TEXT, series_title TEXT, begin_year INT, begin_period TEXT,
  end_year INT, end_period TEXT);
CREATE TABLE IF NOT EXISTS p6_obs(series_id TEXT, year INT, period TEXT, value REAL,
  footnote TEXT, pull_id INT, PRIMARY KEY(series_id, year, period, pull_id));
CREATE INDEX IF NOT EXISTS p6_obs_sp ON p6_obs(series_id, year, period);
CREATE VIEW IF NOT EXISTS p6_obs_latest AS
  SELECT o.series_id, o.year, o.period, o.value, o.footnote, o.pull_id FROM p6_obs o
  JOIN (SELECT series_id, year, period, MAX(pull_id) pull_id FROM p6_obs GROUP BY 1,2,3) m
  USING(series_id, year, period, pull_id);
-- the four derived tables are rebuilt from scratch on every run, so they are dropped rather
-- than migrated when their columns change.  p6_obs / p6_series accumulate and are never dropped.
DROP TABLE IF EXISTS p6_pair;
DROP TABLE IF EXISTS p6_xcorr;
DROP TABLE IF EXISTS p6_passthru;
DROP TABLE IF EXISTS p6_pressure;
CREATE TABLE IF NOT EXISTS p6_pair(pair_id TEXT PRIMARY KEY, ppi_series TEXT, cpi_item TEXT,
  confidence TEXT, best_lag INT, rho_best REAL, source TEXT, sa_mode TEXT, note TEXT,
  ppi_title TEXT, cpi_item_name TEXT, n_obs INT, first_ym TEXT, last_ym TEXT, weight REAL,
  beta12 REAL, se12 REAL, beta12_lo REAL, beta12_hi REAL, weak INT, in_sum INT, lead_ok INT,
  sum_excl TEXT);
CREATE TABLE IF NOT EXISTS p6_xcorr(pair_id TEXT, lag INT, rho REAL, n INT,
  PRIMARY KEY(pair_id, lag));
CREATE TABLE IF NOT EXISTS p6_passthru(pair_id TEXT, h INT, window_end TEXT, beta REAL, se REAL,
  n INT, PRIMARY KEY(pair_id, h, window_end));
CREATE TABLE IF NOT EXISTS p6_pressure(ym TEXT, pair_id TEXT, contrib_bp REAL, contrib_se REAL,
  PRIMARY KEY(ym, pair_id));
"""


# ================================================================= small helpers
def read_tsv(path):
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


def month_range(a, b):
    return [str(p) for p in pd.period_range(a, b, freq="M")]


def shift_back(v, k):
    """x_{t-k} placed at position t (k >= 0)."""
    out = np.full_like(v, np.nan)
    if k == 0:
        out[:] = v
    else:
        out[k:] = v[:-k]
    return out


def shift_fwd(v, k):
    """x_{t+k} placed at position t (k >= 0)."""
    out = np.full_like(v, np.nan)
    if k == 0:
        out[:] = v
    else:
        out[:-k] = v[k:]
    return out


def nw_ols(y, X, L):
    """OLS with a Newey-West (Bartlett) HAC covariance; X must already contain the constant.
    Returns (b, se, n).  L is the truncation lag."""
    n, k = X.shape
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ (X.T @ y)
    u = y - X @ b
    g = u[:, None] * X
    S = g.T @ g
    for l in range(1, L + 1):
        G = g[l:].T @ g[:-l]
        S = S + (1.0 - l / (L + 1.0)) * (G + G.T)
    V = XtXi @ S @ XtXi * (n / max(n - k, 1))
    return b, np.sqrt(np.clip(np.diag(V), 0.0, None)), n


def deseason(v, months):
    """Subtract the calendar-month mean.  `months` is the 1..12 month number of every row of
    the calendar-complete index, so this is exact regardless of where the index starts."""
    out = v.astype(float).copy()
    for m in range(1, 13):
        sl = out[months == m]
        if np.isfinite(sl).any():
            out[months == m] = sl - np.nanmean(sl)
    return out


# ================================================================= fetch + load
def load_dims(con, need_groups, use_ei):
    """Load wp.series/wp.item/wp.group (+ ei.series) into p6_series for the series we care about."""
    d = RAW / "wp"
    item = read_tsv(fetch(BLS_TS + "wp/wp.item", d / "wp.item")[0])
    grp = read_tsv(fetch(BLS_TS + "wp/wp.group", d / "wp.group")[0])
    ser = read_tsv(fetch(BLS_TS + "wp/wp.series", d / "wp.series")[0])
    ser["begin_year"] = ser.begin_year.astype(int)
    ser["end_year"] = ser.end_year.astype(int)
    log.info("wp dims: %d groups, %d items, %d series (%s SA / %s NSA)", len(grp), len(item),
             len(ser), (ser.seasonal == "S").sum(), (ser.seasonal == "U").sum())
    log.info("wp groups present: %s", ", ".join(sorted(set(grp.group_code))))
    fd = ser[ser.group_code.isin(["FD", "ID5", "ID6"])]
    log.info("FD-ID family in wp.series: %d series (FD %d, ID5 %d, ID6 %d); SA available for %d",
             len(fd), (fd.group_code == "FD").sum(), (fd.group_code == "ID5").sum(),
             (fd.group_code == "ID6").sum(), (fd.seasonal == "S").sum())
    rows = [(r.series_id, "wp", r.group_code, r.item_code, r.seasonal, r.series_title,
             int(r.begin_year), r.begin_period, int(r.end_year), r.end_period)
            for r in ser.itertuples()]
    eis = None
    if use_ei:
        try:
            eis = read_tsv(fetch(BLS_TS + "ei/ei.series", RAW / "ei" / "ei.series")[0])
            eis["begin_year"] = eis.begin_year.astype(int)
            eis["end_year"] = eis.end_year.astype(int)
            log.info("ei dims: %d series, index codes %s", len(eis),
                     sorted(set(eis.index_code)) if "index_code" in eis else "?")
            rows += [(r.series_id, "ei", getattr(r, "index_code", ""), "", r.seasonal,
                      r.series_title, int(r.begin_year), r.begin_period, int(r.end_year),
                      r.end_period) for r in eis.itertuples()]
        except Exception as e:  # noqa
            log.warning("ei.series unavailable (%s) - import overlays skipped", e)
            eis = None
    con.execute("DELETE FROM p6_series")
    con.executemany("INSERT OR REPLACE INTO p6_series VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return ser, item, grp, eis


def load_data(con, keep, groups, use_ei, force=False):
    """Download the wp group data files (and the BEA import file) and store the observations of
    `keep` vintaged into p6_obs."""
    # The top row of every group (item_code '-', e.g. WPU02 "Processed foods and feeds") is
    # listed in wp.series but carries NO observations in any wp.data file - BLS stopped
    # publishing the group-level commodity aggregates.  Use an FD-ID or SI series instead.
    # wp.data.1.AllCommodities (WP?00000000) and wp.data.21.Aggregates (groups IND/ILF/PFF/IP)
    # are always taken because they are tiny and hold the only other cross-group indexes.
    files = ["wp/wp.data.1.AllCommodities", "wp/wp.data.21.Aggregates"]
    for g in sorted(groups):
        for f in GROUP_FILES.get(g, []):
            if ("wp/" + f) not in files:
                files.append("wp/" + f)
    if use_ei:
        files.append("ei/" + EI_FILE)
    changed_any = False
    latest = pd.read_sql("SELECT series_id, year, period, value AS old FROM p6_obs_latest", con)
    # The cached copy is always re-parsed, not just when Last-Modified moved: adding a series to
    # the concordance must load its history even though the file on bls.gov did not change.
    # Parsing the cached TSVs costs a few seconds; the download is what fetch() caches.
    for f in files:
        sub, name = f.split("/")
        path, changed = fetch(BLS_TS + f, RAW / sub / name, force=force)
        changed_any = changed_any or changed
        df = read_tsv(path)
        df = df[df.series_id.isin(keep) & df.period.str.startswith("M") & (df.period != "M13")]
        if df.empty:
            log.info("%s: no series of interest", name)
            continue
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df[df.value.notna()]
        df["year"] = df["year"].astype(int)
        m = df.merge(latest, on=["series_id", "year", "period"], how="left")
        new = m[m.old.isna() | ((m.value - m.old).abs() > 1e-9)]
        if new.empty:
            log.info("%s (%s): %d rows for %d kept series, nothing new", name,
                     "re-downloaded" if changed else "cached", len(df), df.series_id.nunique())
            continue
        pull = new_pull(con, name, "p6")
        con.executemany("INSERT OR REPLACE INTO p6_obs VALUES(?,?,?,?,?,?)",
                        [(r.series_id, int(r.year), r.period, float(r.value),
                          getattr(r, "footnote_codes", ""), pull) for r in new.itertuples()])
        con.commit()
        log.info("%s (%s): %d rows for %d kept series, %d new/changed stored (pull %d)",
                 name, "re-downloaded" if changed else "cached", len(df),
                 df.series_id.nunique(), len(new), pull)
    return changed_any


# ================================================================= panels
def ppi_panel(con, idx):
    """Wide (T x series) matrix of PPI index levels on the calendar index `idx`."""
    o = pd.read_sql("SELECT series_id, year, period, value FROM p6_obs_latest", con)
    if o.empty:
        return pd.DataFrame(index=idx)
    o["ym"] = o.year.astype(str) + "-" + o.period.str[1:]
    P = o.pivot_table(index="ym", columns="series_id", values="value", aggfunc="last")
    return P.reindex(idx)


def mom(series_levels):
    """Calendar-aligned month-over-month % change of an index level array (NaN-safe)."""
    v = series_levels.astype(float)
    prev = shift_back(v, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.isfinite(v) & np.isfinite(prev) & (prev > 0), (v / prev - 1.0) * 100.0, np.nan)


# ================================================================= per-pair estimation
def correlogram(x, y, max_lag, min_lag=0):
    """rho_k = corr(x_{t-k}, y_t) for k = min_lag..max_lag.  Negative k means the CPI leads the
    PPI, which is only computed as an alignment diagnostic (best_lag is chosen over k >= 0).
    Returns list of (lag, rho, n)."""
    out = []
    for k in range(min_lag, max_lag + 1):
        xs = shift_back(x, k) if k >= 0 else shift_fwd(x, -k)
        m = np.isfinite(xs) & np.isfinite(y)
        n = int(m.sum())
        if n < MIN_XCORR_N:
            out.append((k, float("nan"), n))
            continue
        a, b = xs[m], y[m]
        if a.std() == 0 or b.std() == 0:
            out.append((k, float("nan"), n))
            continue
        out.append((k, float(np.corrcoef(a, b)[0, 1]), n))
    return out


def lp(x, y, h, rows=None):
    """Local projection: cum_{t..t+h} y  on  [1, x_t, y_{t-1..t-CPI_LAGS}].
    `rows` is an optional boolean mask restricting which t are used.  Returns (beta, se, n)."""
    cum = np.zeros_like(y)
    for j in range(h + 1):
        cum = cum + shift_fwd(y, j)
    cols = [np.ones_like(y), x] + [shift_back(y, l) for l in range(1, CPI_LAGS + 1)]
    X = np.column_stack(cols)
    m = np.isfinite(cum) & np.isfinite(X).all(axis=1)
    if rows is not None:
        m = m & rows
    n = int(m.sum())
    if n < MIN_LP_N:
        return float("nan"), float("nan"), n
    L = h + int(math.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    try:
        b, se, n = nw_ols(cum[m], X[m], L)
    except Exception as e:  # noqa
        log.warning("lp failed (h=%d, n=%d): %s", h, n, e)
        return float("nan"), float("nan"), n
    return float(b[1]), float(se[1]), n


def rolling_ends(idx, first_ok, roll_years):
    """Window end months: every June and December that admits a full window, plus the last month."""
    L = roll_years * 12
    ends = []
    for i, m in enumerate(idx):
        if i < L - 1 or i < first_ok:
            continue
        if m[5:] in ("06", "12") or m == idx[-1]:
            ends.append(m)
    return ends


# ================================================================= main
def main(since=SINCE, max_lag=MAX_LAG, pressure_months=PRESSURE_MONTHS, roll_years=ROLL_YEARS,
         force=False, use_ei=True):
    con = init_db()
    con.executescript(SCHEMA6)
    con.commit()

    # ---- CPI side -------------------------------------------------------------------------
    cpi = pd.read_sql("SELECT item_code, ym, mom_sa, mom_nsa, weight FROM cpi_item_month", con)
    names = dict(pd.read_sql("SELECT item_code, item_name FROM cu_item", con).values)
    parent = dict(pd.read_sql("SELECT item_code, parent_code FROM cu_item", con).values)
    cpi_last = cpi.ym.max()
    idx = month_range(since, cpi_last)
    pos = {m: i for i, m in enumerate(idx)}
    mnum = np.array([int(m[5:]) for m in idx])
    log.info("CPI panel through %s; estimation calendar %s..%s (%d months)", cpi_last,
             idx[0], idx[-1], len(idx))

    all_pairs = [(p[0], p[1], p[2], p[3], "wp") for p in P6_PAIRS]
    if use_ei:
        all_pairs += [(p[0], p[1], p[2], p[3], "ei") for p in P6_EI_PAIRS]

    # ---- dims + which groups we need ------------------------------------------------------
    ser, item, grp, eis = load_dims(con, None, use_ei)
    sid2row = ser.set_index("series_id")
    gc_ic = {r.series_id: (r.group_code, r.item_code) for r in ser.itertuples()}
    item_name = {(r.group_code, r.item_code): r.item_name for r in item.itertuples()}

    dropped = []
    # resolve FD-ID context series
    fd_ids = []
    for g, ic, label in FD_ID_KEEP:
        cand = ser[(ser.group_code == g) & (ser.item_code == ic)]
        s = cand[cand.seasonal == "S"]
        r = (s if len(s) else cand)
        if not len(r):
            dropped.append({"pair": f"FD-ID {g}/{ic}", "reason": "no such (group,item) in wp.series"})
            log.warning("FD-ID %s/%s (%s): not in wp.series", g, ic, label)
            continue
        r = r.iloc[0]
        fd_ids.append((r.series_id, label, r.seasonal, r.series_title))
    log.info("FD-ID context series resolved: %d of %d -> %s", len(fd_ids), len(FD_ID_KEEP),
             [f"{s}({sa})" for s, _, sa, _ in fd_ids])

    # ---- verify every pair's PPI series ----------------------------------------------------
    resolved, groups = [], set()
    for sid, cpi_item, conf, note, src in all_pairs:
        if cpi_item not in set(cpi.item_code):
            dropped.append({"pair": f"{sid}->{cpi_item}", "reason": "CPI item not in cpi_item_month"})
            continue
        if src == "wp":
            if sid not in sid2row.index:
                dropped.append({"pair": f"{sid}->{cpi_item}", "reason": "PPI series id not in wp.series"})
                log.warning("DROP %s -> %s: not in wp.series", sid, cpi_item)
                continue
            g, ic = gc_ic[sid]
            # the SA/NSA twin is the same id with the 3rd character flipped. Do NOT rebuild it
            # as 'WPU'+group+item: for a group's own top-level row item_code is '-' and the
            # series id is just 'WP?'+group (e.g. WPS02 / WPU02, group 02, item '-').
            twin = ("WPU" if sid[2] == "S" else "WPS") + sid[3:]
            resolved.append(dict(sid=sid, twin=twin if twin in sid2row.index else None, gc=g, ic=ic,
                                 cpi=cpi_item, conf=conf, note=note, src=src,
                                 title=item_name.get((g, ic), sid2row.loc[sid, "series_title"])))
            groups.add(g)
        else:
            if eis is None or sid not in set(eis.series_id):
                dropped.append({"pair": f"{sid}->{cpi_item}", "reason": "import series id not in ei.series"})
                log.warning("DROP %s -> %s: not in ei.series", sid, cpi_item)
                continue
            row = eis[eis.series_id == sid].iloc[0]
            resolved.append(dict(sid=sid, twin=None, gc="", ic="", cpi=cpi_item, conf=conf,
                                 note=note, src=src, title=row.series_name))
    groups |= {"FD", "ID5", "ID6"}
    keep_ids = {r["sid"] for r in resolved} | {r["twin"] for r in resolved if r["twin"]} \
               | {s for s, _, _, _ in fd_ids}
    log.info("concordance: %d rows requested, %d resolved to a real series, %d dropped up front",
             len(all_pairs), len(resolved), len(all_pairs) - len(resolved))
    log.info("wp group data files needed for groups %s", sorted(groups))

    # ---- download + store ------------------------------------------------------------------
    load_data(con, keep_ids, groups, use_ei, force=force)

    P = ppi_panel(con, idx)
    ppi_last_by_sid = {}
    for c in P.columns:
        v = P[c]
        nz = v[v.notna()]
        if len(nz):
            ppi_last_by_sid[c] = nz.index[-1]
    ppi_last = max(ppi_last_by_sid.values()) if ppi_last_by_sid else None
    log.info("p6_obs: %d series stored, latest PPI month %s (CPI latest %s)",
             len(ppi_last_by_sid), ppi_last, cpi_last)

    # ---- CPI wide -------------------------------------------------------------------------
    C_sa = cpi.pivot_table(index="ym", columns="item_code", values="mom_sa").reindex(idx)
    C_ns = cpi.pivot_table(index="ym", columns="item_code", values="mom_nsa").reindex(idx)
    W = cpi.pivot_table(index="ym", columns="item_code", values="weight").reindex(idx).ffill()

    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    val_rows = []

    def add_val(check, ym, ours, published, ok, log_it=True):
        diff = None if (ours is None or published is None) else ours - published
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    (now, check, ym, ours, published, diff, int(bool(ok))))
        val_rows.append({"check_name": check, "ym": ym, "ours": ours, "published": published,
                         "diff": diff, "ok": bool(ok)})
        if log_it and not ok:
            log.warning("validation %s %s: ours=%s published=%s NOT OK", check, ym, ours, published)

    # ---- build every pair ------------------------------------------------------------------
    pairs, xrows = [], []
    for r in resolved:
        sid, cpi_item = r["sid"], r["cpi"]
        # Choose the SA/NSA mode.  A candidate is usable only if BOTH sides exist, both have
        # >= MIN_YEARS of monthly data and the PPI series is still being published.  SA is
        # tried first when the concordance asked for it; the NSA twin is the fallback (very
        # many WPS series were discontinued, and several CPI items have no SA index at all).
        def usable(cand, want_mode):
            if cand is None or cand not in P.columns:
                return None
            v = P[cand]
            if v.notna().sum() < MIN_YEARS * 12:
                return None
            lastm = v[v.notna()].index[-1]
            if ppi_last and (pd.Period(ppi_last, "M") - pd.Period(lastm, "M")).n > LAG_TOL:
                return None
            cser = C_sa if want_mode == "SA" else C_ns
            if cpi_item not in cser.columns:
                return None
            yv = cser[cpi_item].to_numpy(float)
            if np.isfinite(yv).sum() < MIN_YEARS * 12:
                return None
            return cand, want_mode, yv

        order = [(sid, "SA" if sid[2] == "S" else "NSA-dm"), (r["twin"], "NSA-dm" if sid[2] == "S" else "SA")]
        if r["src"] == "ei":
            order = [(sid, "NSA-dm")]                        # the whole ei programme is NSA
        pick = next((u for u in (usable(c, m) for c, m in order) if u), None)
        if pick is None:
            bits = []
            for cand, m in order:
                if cand is None:
                    continue
                nn = int(P[cand].notna().sum()) if cand in P.columns else 0
                lm = P[cand][P[cand].notna()].index[-1] if nn else "-"
                cs = C_sa if m == "SA" else C_ns
                cn = int(np.isfinite(cs[cpi_item].to_numpy(float)).sum()) if cpi_item in cs.columns else 0
                bits.append(f"{cand}[{m}] ppi {nn} obs last {lm}, cpi {cn} obs")
            why = f"no usable side (need >= {MIN_YEARS*12} monthly obs each and PPI last within " \
                  f"{LAG_TOL}m of {ppi_last}): " + " | ".join(bits)
            dropped.append({"pair": f"{sid}->{cpi_item}", "reason": why})
            log.warning("DROP %s -> %s: %s", sid, cpi_item, why)
            continue
        use_sid, mode, y_raw = pick

        # CPI item still published?
        yfin = np.where(np.isfinite(y_raw))[0]
        if not len(yfin):
            dropped.append({"pair": f"{use_sid}->{cpi_item}", "reason": "CPI item has no MoM data"})
            continue
        cpi_item_last = idx[yfin[-1]]
        if (pd.Period(cpi_last, "M") - pd.Period(cpi_item_last, "M")).n > LAG_TOL + 1:
            dropped.append({"pair": f"{use_sid}->{cpi_item}",
                            "reason": f"CPI item discontinued (last MoM {cpi_item_last}, panel {cpi_last})"})
            log.warning("DROP %s -> %s: CPI item index ends %s (panel ends %s)",
                        use_sid, cpi_item, cpi_item_last, cpi_last)
            continue

        x_raw = mom(P[use_sid].to_numpy(float))
        x, y = (deseason(x_raw, mnum), deseason(y_raw, mnum)) if mode == "NSA-dm" else (x_raw, y_raw)
        both = np.isfinite(x) & np.isfinite(y)
        n_obs = int(both.sum())
        if n_obs < MIN_YEARS * 12:
            dropped.append({"pair": f"{use_sid}->{cpi_item}",
                            "reason": f"only {n_obs} overlapping months (need {MIN_YEARS*12})"})
            log.warning("DROP %s -> %s: only %d overlapping months", use_sid, cpi_item, n_obs)
            continue
        wh = np.where(both)[0]
        first_ym, last_ym = idx[wh[0]], idx[wh[-1]]

        pair_id = f"{use_sid}|{cpi_item}"
        xc = correlogram(x, y, max_lag, min_lag=-LEAD_LAGS)
        fin = [(k, rho) for k, rho, _ in xc if np.isfinite(rho) and k >= 0]
        if not fin:
            dropped.append({"pair": pair_id, "reason": "no correlogram point had enough overlap"})
            continue
        best_lag, rho_best = max(fin, key=lambda t: t[1])       # signed argmax over k >= 0
        leads = [rho for k, rho, _ in xc if np.isfinite(rho) and k < 0]
        rho0 = next((rho for k, rho, _ in xc if k == 0), float("nan"))
        lead_ok = (not leads) or not np.isfinite(rho0) or rho0 >= max(leads)
        for k, rho, n in xc:
            xrows.append((pair_id, k, None if not np.isfinite(rho) else float(rho), n))

        # Full-sample betas at every horizon 0..12. HORIZONS (3/6/12) drive the
        # display and the rolling regime range; beta_0..beta_12 feed the
        # pass-through discount in the pressure step (see section 3).
        allh = {h: lp(x, y, h) for h in range(13)}
        betas = {h: allh[h] for h in HORIZONS}
        disc_beta = {h: allh[h][0] for h in range(13)}  # point estimates only

        # rolling windows
        roll = []
        L = roll_years * 12
        for end in rolling_ends(idx, wh[0] + L - 1, roll_years):
            i = pos[end]
            rows = np.zeros(len(idx), bool)
            rows[max(0, i - L + 1): i + 1] = True
            for h in HORIZONS:
                b, se, n = lp(x, y, h, rows)
                if np.isfinite(b):
                    roll.append((h, end, b, se, n))

        b12 = [t for t in roll if t[0] == 12]
        lo = min((t[2] for t in b12), default=float("nan"))
        hi = max((t[2] for t in b12), default=float("nan"))
        beta12, se12, n12 = betas[12]
        weak = int(not np.isfinite(beta12) or beta12 <= 0 or not np.isfinite(se12)
                   or se12 <= 0 or abs(beta12 / se12) < 1.96)

        pairs.append(dict(pair_id=pair_id, ppi_series=use_sid, cpi_item=cpi_item,
                          confidence=r["conf"], best_lag=best_lag, rho_best=rho_best,
                          source=r["src"], sa_mode=mode, note=r["note"], ppi_title=r["title"],
                          cpi_item_name=names.get(cpi_item, cpi_item), n_obs=n_obs,
                          first_ym=first_ym, last_ym=last_ym,
                          weight=float(W[cpi_item].dropna().iloc[-1]) if cpi_item in W and W[cpi_item].notna().any() else float("nan"),
                          beta12=beta12, se12=se12, beta12_lo=lo, beta12_hi=hi, weak=weak,
                          betas=betas, disc_beta=disc_beta, roll=roll, xc=xc, x=x, y=y,
                          lead_ok=lead_ok, rho0=rho0,
                          lead_max=max(leads) if leads else float("nan"),
                          ppi_last=ppi_last_by_sid.get(use_sid)))

    log.info("%d pairs kept, %d dropped", len(pairs), len(dropped))

    # ---- in_sum: drop a pair from the SUM if a finer pair covers part of it -----------------
    def ancestors(code):
        out, p = [], parent.get(code)
        while p:
            out.append(p)
            p = parent.get(p)
        return out

    sum_items = {p["cpi_item"] for p in pairs if p["source"] == "wp"}
    excl = {"import overlay": 0, "weak": 0, "covered by a finer pair": 0,
            "best_lag=0 (nothing in the pipe)": 0, "no CPI weight": 0}
    for p in pairs:
        covered = any(p["cpi_item"] in ancestors(o) for o in sum_items if o != p["cpi_item"])
        p["covered"] = covered
        reason = ("import overlay" if p["source"] == "ei" else
                  "weak" if p["weak"] else
                  "covered by a finer pair" if covered else
                  "best_lag=0 (nothing in the pipe)" if p["best_lag"] == 0 else
                  "no CPI weight" if not np.isfinite(p["weight"]) else None)
        p["sum_excl"] = reason
        p["in_sum"] = int(reason is None)
        if reason:
            excl[reason] += 1
    cov = sum(p["weight"] for p in pairs if p["in_sum"] and np.isfinite(p["weight"]))
    cov_all = sum(p["weight"] for p in pairs
                  if p["source"] == "wp" and not p["covered"] and np.isfinite(p["weight"]))
    log.info("pressure sum uses %d of %d pairs; first-reason exclusions: %s",
             sum(p["in_sum"] for p in pairs), len(pairs),
             ", ".join(f"{v} {k}" for k, v in excl.items() if v))
    log.info("basket coverage: the summed pairs carry %.2f%% of CPI-U weight; the whole "
             "non-overlapping PPI concordance carries %.2f%%. The rest of the basket (shelter, "
             "most services, used cars) has no producer-price counterpart at all, so the "
             "pressure figure is a partial total, not a decomposition of the CPI.", cov, cov_all)
    lagdist = {}
    for p in pairs:
        lagdist[p["best_lag"]] = lagdist.get(p["best_lag"], 0) + 1
    log.info("best-lag distribution over %d pairs: %s", len(pairs),
             " ".join(f"{k}m:{v}" for k, v in sorted(lagdist.items())))
    bad_align = [p["pair_id"] for p in pairs if not p["lead_ok"]]
    log.info("alignment diagnostic: %d of %d pairs have a higher correlation at a NEGATIVE lag "
             "(CPI leading PPI) than at lag 0%s", len(bad_align), len(pairs),
             "" if not bad_align else " -> " + ", ".join(bad_align[:8]))
    log.info("--- surviving pairs -------------------------------------------------------------")
    for p in sorted(pairs, key=lambda q: (q["source"], -abs(q["weight"]) if np.isfinite(q["weight"]) else 0)):
        log.info("  %-4s %-13s -> %-8s %-30s %-6s %-6s lag %2d rho %+0.3f  b12 %7.3f (se %6.3f) "
                 "[%6.3f..%6.3f] w %5.2f%% n %3d %s%s",
                 p["source"], p["ppi_series"], p["cpi_item"], p["cpi_item_name"][:30],
                 p["confidence"], p["sa_mode"], p["best_lag"], p["rho_best"], p["beta12"],
                 p["se12"], p["beta12_lo"], p["beta12_hi"], p["weight"], p["n_obs"],
                 "SUM" if p["in_sum"] else "---", "" if p["in_sum"] else " (%s)" % p["sum_excl"])
    big = sorted([p for p in pairs if np.isfinite(p["beta12"]) and p["beta12"] > 1.5],
                 key=lambda q: -q["beta12"])
    if big:
        log.info("pairs whose CPI item moves MORE than one-for-one with its PPI (beta_12 > 1.5). "
                 "Not necessarily an error: the PPI usually covers only part of the CPI item's "
                 "cost basis, so a 1pp move in the measured slice can accompany a larger move in "
                 "the whole item. It does mean the 'pass-through' label is loose for these:")
        for q in big:
            log.info("   beta12 %6.3f (se %5.3f) %-13s -> %-8s %-30s %s",
                     q["beta12"], q["se12"], q["ppi_series"], q["cpi_item"],
                     q["cpi_item_name"][:30], "IN SUM" if q["in_sum"] else "")
    log.info("---------------------------------------------------------------------------------")

    # ---- pressure --------------------------------------------------------------------------
    months = idx[-pressure_months:]
    prows, by_pair, tot, tse, tse_co = [], {}, [], [], []
    for m in months:
        i = pos[m]
        s, s2, sco = 0.0, 0.0, 0.0
        for p in pairs:
            if not p["in_sum"]:
                continue
            x = p["x"]
            lo5 = max(0, i - 59)
            base = np.nanmean(x[lo5:i + 1]) if np.isfinite(x[lo5:i + 1]).any() else np.nan
            b12 = p["beta12"]
            db = p["disc_beta"]
            # Distributed-lag discount: an innovation k months old has already
            # passed through beta_k of its cumulative response, so only the
            # REMAINING fraction (beta_12 - beta_k)/beta_12 is still "in the
            # pipe". k=0 keeps (beta_12-beta_0)/beta_12; k>=12 is treated as
            # fully realised (0) under the horizon-12 completeness assumption.
            # Expressed as an effective shock so beta_12 and se_12 flow through
            # exactly as before.
            s_eff = 0.0
            for k in range(p["best_lag"]):
                j = i - k
                if j < 0:
                    break
                dv = x[j] - base
                if not np.isfinite(dv):
                    continue
                bk = db.get(k) if k < 12 else b12  # k>=12 -> remaining 0
                if bk is None or not np.isfinite(bk):
                    bk = 0.0  # horizon not estimable: treat as fully un-realised
                rem = max(b12 - bk, 0.0)
                frac = rem / b12 if np.isfinite(b12) and abs(b12) > 1e-9 else 0.0
                s_eff += dv * frac
            w = W[p["cpi_item"]].iloc[i]
            if not np.isfinite(w):
                w = p["weight"]
            cb = s_eff * b12 * w
            cs = abs(s_eff) * p["se12"] * w
            if not (np.isfinite(cb) and np.isfinite(cs)):
                continue
            prows.append((m, p["pair_id"], float(cb), float(cs)))
            by_pair.setdefault(p["pair_id"], {})[m] = float(cb)
            s += cb
            s2 += cs * cs
            sco += cs
        tot.append(s)
        tse.append(math.sqrt(s2))
        tse_co.append(sco)

    # ---- write tables ----------------------------------------------------------------------
    con.execute("DELETE FROM p6_pair")
    con.executemany("INSERT OR REPLACE INTO p6_pair VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(p["pair_id"], p["ppi_series"], p["cpi_item"], p["confidence"],
                      int(p["best_lag"]), float(p["rho_best"]), p["source"], p["sa_mode"],
                      p["note"], p["ppi_title"], p["cpi_item_name"], int(p["n_obs"]),
                      p["first_ym"], p["last_ym"],
                      None if not np.isfinite(p["weight"]) else float(p["weight"]),
                      None if not np.isfinite(p["beta12"]) else float(p["beta12"]),
                      None if not np.isfinite(p["se12"]) else float(p["se12"]),
                      None if not np.isfinite(p["beta12_lo"]) else float(p["beta12_lo"]),
                      None if not np.isfinite(p["beta12_hi"]) else float(p["beta12_hi"]),
                      int(p["weak"]), int(p["in_sum"]), int(p["lead_ok"]),
                      p["sum_excl"]) for p in pairs])
    con.execute("DELETE FROM p6_xcorr")
    con.executemany("INSERT OR REPLACE INTO p6_xcorr VALUES(?,?,?,?)", xrows)
    con.execute("DELETE FROM p6_passthru")
    ptrows = []
    for p in pairs:
        for h, (b, se, n) in p["betas"].items():
            if np.isfinite(b):
                ptrows.append((p["pair_id"], int(h), "full", float(b), float(se), int(n)))
        for h, end, b, se, n in p["roll"]:
            ptrows.append((p["pair_id"], int(h), end, float(b), float(se), int(n)))
    con.executemany("INSERT OR REPLACE INTO p6_passthru VALUES(?,?,?,?,?,?)", ptrows)
    con.execute("DELETE FROM p6_pressure")
    con.executemany("INSERT OR REPLACE INTO p6_pressure VALUES(?,?,?,?)", prows)
    con.commit()
    log.info("p6_pair %d rows, p6_xcorr %d, p6_passthru %d, p6_pressure %d",
             len(pairs), len(xrows), len(ptrows), len(prows))

    # ---- validation ------------------------------------------------------------------------
    ok_all = True
    # (a) every PPI series recent enough
    stale = []
    for p in pairs:
        lm = p["ppi_last"]
        gap = None if lm is None else (pd.Period(cpi_last, "M") - pd.Period(lm, "M")).n
        ok = gap is not None and gap <= LAG_TOL
        ok_all &= ok
        if not ok:
            stale.append((p["pair_id"], lm))
        add_val("p6_ppi_recency", lm or "-", float(gap) if gap is not None else None,
                float(LAG_TOL), ok, log_it=False)
    log.info("validate ppi recency: %d/%d pairs have a PPI series within %d months of CPI %s%s",
             len(pairs) - len(stale), len(pairs), LAG_TOL, cpi_last,
             "" if not stale else "; STALE: %s" % stale)

    # (b) gasoline sanity
    gas = next((p for p in pairs if p["cpi_item"] == "SETB01"), None)
    if gas is None:
        log.error("SANITY: the gasoline pair is missing entirely")
        add_val("p6_gasoline_lag", cpi_last, None, 1.0, False)
        ok_all = False
    else:
        lag_ok = gas["best_lag"] in (0, 1)
        b3, se3, n3 = gas["betas"][3]
        b3_ok = np.isfinite(b3) and GAS_BETA3_BAND[0] <= b3 <= GAS_BETA3_BAND[1]
        add_val("p6_gasoline_lag", cpi_last, float(gas["best_lag"]), 1.0, lag_ok, log_it=False)
        add_val("p6_gasoline_beta3", cpi_last, float(b3) if np.isfinite(b3) else None, 0.65, b3_ok, log_it=False)
        add_val("p6_gasoline_leadcheck", cpi_last, float(gas["rho0"]),
                float(gas["lead_max"]) if np.isfinite(gas["lead_max"]) else None,
                gas["lead_ok"], log_it=False)
        ok_all &= (lag_ok and b3_ok and gas["lead_ok"])
        log.info("SANITY gasoline %s -> SETB01: best lag %d (rho %.3f) %s | beta_3 = %.3f "
                 "(se %.3f, n %d) %s [band %.2f-%.2f] | alignment: rho at lag 0 = %.3f vs best "
                 "CPI-leads-PPI lag %.3f %s", gas["ppi_series"], gas["best_lag"], gas["rho_best"],
                 "OK" if lag_ok else "*** BAD ***", b3, se3, n3, "OK" if b3_ok else "*** OUT OF BAND ***",
                 GAS_BETA3_BAND[0], GAS_BETA3_BAND[1], gas["rho0"], gas["lead_max"],
                 "OK" if gas["lead_ok"] else "*** BAD: the CPI leads the PPI, the series are misaligned ***")

    # (c) weak pairs
    weak_list = [p for p in pairs if p["weak"]]
    for p in weak_list:
        add_val("p6_weak_pair", p["last_ym"], float(p["beta12"]) if np.isfinite(p["beta12"]) else None,
                0.0, False, log_it=False)
    log.info("weak pairs (full-sample beta_12 <= 0 or |t| < 1.96) - kept in the tables, flagged "
             "weak=1, excluded from the pressure sum: %d of %d", len(weak_list), len(pairs))
    for p in sorted(weak_list, key=lambda q: q["cpi_item"]):
        log.info("   weak  %-28s %-8s %-24s beta12 %7.3f (se %6.3f) rho_best %+0.3f lag %2d %s",
                 p["ppi_series"], p["cpi_item"], p["cpi_item_name"][:24], p["beta12"], p["se12"],
                 p["rho_best"], p["best_lag"], p["confidence"])

    # (d) how much did the preliminary months move at this pull?
    rev = pd.read_sql("""
        SELECT series_id, year, period, COUNT(*) nv, MAX(value)-MIN(value) spread
        FROM p6_obs GROUP BY 1,2,3 HAVING nv > 1""", con)
    if len(rev):
        rev["ym"] = rev.year.astype(str) + "-" + rev.period.str[1:]
        recent = rev[rev.ym >= str(pd.Period(cpi_last, "M") - 5)]
        log.info("preliminary-PPI revisions: %d (series, month) cells now hold >1 vintage; "
                 "%d of them are in the last 6 months, max spread %.3f index points",
                 len(rev), len(recent), float(recent.spread.max()) if len(recent) else 0.0)
        add_val("p6_prelim_revision", cpi_last, float(len(recent)), 0.0, True, log_it=False)
    else:
        log.info("preliminary-PPI revisions: first pull, nothing to compare yet")
        add_val("p6_prelim_revision", cpi_last, 0.0, 0.0, True, log_it=False)

    # ---- report ----------------------------------------------------------------------------
    if tot:
        latest_m = months[-1]
        add_val("p6_pressure_total", latest_m, float(tot[-1]), 0.0, True, log_it=False)
        lat = sorted([(pid, d.get(latest_m)) for pid, d in by_pair.items() if d.get(latest_m) is not None],
                     key=lambda t: -abs(t[1]))
        log.info("=== pressure in the pipe, %s: %+.1f bp of CPI still to pass through over the "
                 "coming ~12 months (each PPI innovation discounted by the pass-through already "
                 "realised) (+/-%.1f bp, 1 SE, independent betas; comonotone bound +/-%.1f bp) "
                 "from %d pairs",
                 latest_m, tot[-1], tse[-1], tse_co[-1], sum(p["in_sum"] for p in pairs))
        byid = {p["pair_id"]: p for p in pairs}
        for pid, v in lat[:8]:
            p = byid[pid]
            log.info("   %+7.2f bp  %-28s -> %-8s %-26s lag %2d  beta12 %6.3f [%.3f..%.3f] w %5.2f%%",
                     v, p["ppi_series"], p["cpi_item"], p["cpi_item_name"][:26], p["best_lag"],
                     p["beta12"], p["beta12_lo"], p["beta12_hi"], p["weight"])
    con.commit()

    # ---- FD-ID context series ---------------------------------------------------------------
    fd_out = []
    for sid, label, sa, title in fd_ids:
        if sid not in P.columns:
            continue
        v = P[sid]
        if v.notna().sum() < 24:
            continue
        mm = mom(v.to_numpy(float))
        lv = v.to_numpy(float)
        yy = np.full(len(lv), np.nan)
        for i in range(len(lv)):
            j = i - 12
            if j >= 0 and np.isfinite(lv[i]) and np.isfinite(lv[j]) and lv[j] > 0:
                yy[i] = (lv[i] / lv[j] - 1) * 100
        keep = [i for i, m in enumerate(idx) if np.isfinite(lv[i])]
        if not keep:
            continue
        k0 = max(keep[0], len(idx) - 12 * 20)
        fd_out.append({"series_id": sid, "label": label, "seasonal": sa, "title": title,
                       "ym": idx[k0:],
                       "index": [None if not np.isfinite(x) else round(float(x), 3) for x in lv[k0:]],
                       "mom": [None if not np.isfinite(x) else round(float(x), 3) for x in mm[k0:]],
                       "yoy": [None if not np.isfinite(x) else round(float(x), 3) for x in yy[k0:]]})
    for f in fd_out[:6]:
        have = [i for i, v in enumerate(f["yoy"]) if v is not None]
        if have:
            log.info("FD-ID %-12s %-42s %s: YoY %+6.2f%%  MoM %+5.2f%%", f["series_id"],
                     f["label"][:42], f["ym"][have[-1]], f["yoy"][have[-1]],
                     f["mom"][have[-1]] if f["mom"][have[-1]] is not None else float("nan"))
    log.info("FD-ID: %d aggregate series published as context", len(fd_out))

    # ---- JSON --------------------------------------------------------------------------------
    def rnd(v, d=4):
        return None if v is None or not np.isfinite(v) else round(float(v), d)

    sm_from = max(0, len(idx) - 96)         # 8 years of small multiples
    pjson = []
    for p in sorted(pairs, key=lambda q: (q["source"], q["cpi_item"])):
        rollm = {}
        for h, end, b, se, n in p["roll"]:
            rollm.setdefault(str(h), {"window_end": [], "beta": [], "se": [], "n": []})
            rollm[str(h)]["window_end"].append(end)
            rollm[str(h)]["beta"].append(rnd(b))
            rollm[str(h)]["se"].append(rnd(se))
            rollm[str(h)]["n"].append(int(n))
        xs = shift_back(p["x"], p["best_lag"])
        pjson.append({
            "pair_id": p["pair_id"], "ppi_series": p["ppi_series"], "ppi_title": p["ppi_title"],
            "cpi_item": p["cpi_item"], "cpi_item_name": p["cpi_item_name"],
            "confidence": p["confidence"], "source": p["source"], "sa_mode": p["sa_mode"],
            "note": p["note"], "best_lag": int(p["best_lag"]), "rho_best": rnd(p["rho_best"]),
            "n_obs": int(p["n_obs"]), "first_ym": p["first_ym"], "last_ym": p["last_ym"],
            "weight": rnd(p["weight"], 3), "weak": int(p["weak"]), "in_sum": int(p["in_sum"]),
            "xcorr_lags": [int(k) for k, _, _ in p["xc"]],
            "xcorr": [rnd(rho) for _, rho, _ in p["xc"]],
            "xcorr_n": [int(n) for _, _, n in p["xc"]],
            "lead_ok": bool(p["lead_ok"]),
            "beta": {str(h): {"beta": rnd(b), "se": rnd(se), "n": int(n)}
                     for h, (b, se, n) in p["betas"].items()},
            "disc_beta": [rnd(p["disc_beta"][h]) for h in range(13)],
            "beta12_range": [rnd(p["beta12_lo"]), rnd(p["beta12_hi"])],
            "rolling": rollm,
            "small_multiple": {"ym": idx[sm_from:],
                               "ppi_shifted": [rnd(v, 3) for v in xs[sm_from:]],
                               "cpi": [rnd(v, 3) for v in p["y"][sm_from:]]},
        })

    latest_top = []
    if tot:
        byid = {p["pair_id"]: p for p in pairs}
        se_latest = {pid: cs for m2, pid, _, cs in prows if m2 == months[-1]}
        for pid, v in sorted([(k, d.get(months[-1])) for k, d in by_pair.items()
                              if d.get(months[-1]) is not None], key=lambda t: -abs(t[1]))[:10]:
            p = byid[pid]
            latest_top.append({"pair_id": pid, "cpi_item": p["cpi_item"],
                               "cpi_item_name": p["cpi_item_name"], "contrib_bp": rnd(v, 3),
                               "contrib_se": rnd(se_latest.get(pid), 3),
                               "best_lag": int(p["best_lag"]), "beta12": rnd(p["beta12"]),
                               "beta12_range": [rnd(p["beta12_lo"]), rnd(p["beta12_hi"])],
                               "weight": rnd(p["weight"], 3)})

    out = {
        "schema": {
            "pairs": "one object per surviving concordance row; xcorr[i] = corr(PPI MoM at "
                     "t-xcorr_lags[i], CPI MoM at t), lags -%d..%d (negative = CPI leads, an "
                     "alignment diagnostic only; best_lag is chosen over lags >= 0); beta[h] = "
                     "cumulative pp response of the CPI item "
                     "over h+1 months to a 1pp PPI move, Newey-West SE; beta12_range = "
                     "[min, max] of beta_12 over the rolling %d-year windows; small_multiple "
                     "carries the PPI MoM already shifted by best_lag over the CPI MoM, last 8 years"
                     % (LEAD_LAGS, MAX_LAG, ROLL_YEARS),
            "pressure": "total_bp[t] = sum over in_sum pairs of (each recent PPI deviation from "
                        "its 5-year mean, over the pair's best_lag months, weighted by the pass-"
                        "through STILL TO COME: (beta_12 - beta_k)/beta_12 for an innovation k "
                        "months old) x beta_12 x CPI weight. So total_bp is the bp still to reach "
                        "headline CPI over the coming ~year - already-realised pass-through is "
                        "discounted out and innovations older than 12 months count as done. "
                        "disc_beta[k] on each pair is beta_k. Historical-relationship arithmetic, "
                        "NOT a forecast.",
            "fd_id": "PPI final-demand / intermediate-demand aggregates, context only - a "
                     "different weighting universe from the CPI, never paired with a CPI item.",
        },
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "latest_cpi_month": cpi_last, "latest_ppi_month": ppi_last,
        "params": {"since": since, "max_lag": max_lag, "min_years": MIN_YEARS,
                   "roll_years": roll_years, "horizons": list(HORIZONS),
                   "cpi_control_lags": CPI_LAGS, "pressure_months": pressure_months,
                   "min_xcorr_n": MIN_XCORR_N, "min_lp_n": MIN_LP_N, "lag_tol": LAG_TOL},
        "pairs": pjson,
        "pressure": {"ym": months, "total_bp": [rnd(v, 3) for v in tot],
                     "se_bp": [rnd(v, 3) for v in tse],
                     "se_bp_comonotone": [rnd(v, 3) for v in tse_co],
                     "by_pair": {k: [rnd(v.get(m), 3) for m in months] for k, v in by_pair.items()},
                     "latest": {"ym": months[-1] if months else None,
                                "total_bp": rnd(tot[-1], 3) if tot else None,
                                "se_bp": rnd(tse[-1], 3) if tse else None,
                                "se_bp_comonotone": rnd(tse_co[-1], 3) if tse_co else None,
                                "n_pairs": sum(p["in_sum"] for p in pairs),
                                "weight_covered_pct": rnd(cov, 3),
                                "weight_concordance_pct": rnd(cov_all, 3),
                                "top": latest_top}},
        "fd_id": fd_out,
        "weak_pairs": [{"pair_id": p["pair_id"], "cpi_item": p["cpi_item"],
                        "cpi_item_name": p["cpi_item_name"], "ppi_series": p["ppi_series"],
                        "beta12": rnd(p["beta12"]), "se12": rnd(p["se12"]),
                        "rho_best": rnd(p["rho_best"]), "best_lag": int(p["best_lag"]),
                        "confidence": p["confidence"]} for p in weak_list],
        "dropped": dropped,
        "validation": [{**v, "ours": rnd(v["ours"], 4), "published": rnd(v["published"], 4),
                        "diff": rnd(v["diff"], 4)} for v in val_rows],
        "notes": [
            "Pressure still to come, not a next-month reading and not dated to a particular future "
            "month. Each recent PPI innovation is discounted by the pass-through it has ALREADY "
            "delivered: an innovation k months old keeps only (beta_12 - beta_k)/beta_12 of its "
            "cumulative effect, where beta_k is the local projection at horizon k (k=0..12). This "
            "removes the earlier double-count (a raw accumulated shock times the full beta_12) and "
            "the mechanical up-weighting of longer-lag pairs; it assumes pass-through is essentially "
            "complete within 12 months, so an innovation older than a year adds nothing. The +/-1 SE "
            "band uses se(beta_12) per pair, a deliberately conservative choice (the true SE of "
            "beta_12 - beta_k is smaller). Historical-relationship arithmetic, NOT a forecast.",
            "Not a forecast. The pressure figure is historical-relationship arithmetic: a recent "
            "producer-price deviation multiplied by a pass-through coefficient estimated on the "
            "past. It carries no view on demand, margins, inventories or the exchange rate.",
            "Pass-through betas are regime-dependent. Read beta12_range (the min and max over "
            "rolling %d-year windows) next to every point estimate; for most pairs it is at "
            "least twice as wide as the +/-1 SE band." % ROLL_YEARS,
            "PPI is preliminary for four months and is revised every release. p6_obs is vintaged; "
            "the last four months of any PPI series in this file can and will move.",
            "A pass-through beta is a conditional correlation, not a causal elasticity: the PPI "
            "and the CPI item share demand shocks, and part of any measured 'pass-through' is "
            "simply both prices responding to the same thing.",
            "Pairs whose full-sample beta_12 is negative or statistically insignificant are kept "
            "in the tables with weak=1 and excluded from the pressure sum. So are import "
            "overlays (they would double-count the PPI pair on the same CPI item) and pairs "
            "whose best lag is 0 (nothing is in the pipe if it lands the same month).",
            "October 2025 has no CPI (shutdown). Every lag here is calendar-aligned, so any "
            "regression row whose window spans that hole is dropped rather than shifted.",
            "NSA pairs (sa_mode='NSA-dm') have the calendar-month means removed from both sides "
            "over the estimation sample. This is a crude substitute for X-11 and it is used only "
            "where BLS has discontinued the seasonally adjusted PPI twin.",
            "PPI covers domestic producers' net revenue. For heavily imported CPI items (apparel, "
            "footwear, consumer electronics, much of the furniture basket) the domestic PPI is "
            "the wrong upstream price, which is why those pairs are labelled 'med' or 'low' and "
            "why the BEA import-price overlays are shown next to them.",
        ],
    }
    (OUT / "p6_pipeline.json").write_text(json.dumps(out, indent=1))
    log.info("wrote %s (%d pairs, %d FD-ID series, %d pressure months)",
             OUT / "p6_pipeline.json", len(pjson), len(fd_out), len(months))
    return 0 if ok_all else 2


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)
    kw = {}
    for a in sys.argv[1:]:
        if a.startswith("--since="):
            kw["since"] = a.split("=", 1)[1]
        elif a.startswith("--max-lag="):
            kw["max_lag"] = int(a.split("=", 1)[1])
        elif a.startswith("--pressure-months="):
            kw["pressure_months"] = int(a.split("=", 1)[1])
        elif a.startswith("--roll-years="):
            kw["roll_years"] = int(a.split("=", 1)[1])
        elif a == "--force":
            kw["force"] = True
        elif a == "--no-ei":
            kw["use_ei"] = False
        else:
            print("unknown argument", a); sys.exit(64)
    sys.exit(main(**kw))
