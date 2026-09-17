#!/usr/bin/env python3
"""P3 - item-level inflation persistence (Tier 1 descriptive; Tier-2 appendix labelled).

  p3_persistence.py [--since YYYY-MM] [--quarterly] [--no-fred] [--help]

How long does a price shock to an individual CPI item stay in that item's inflation
rate?  For every leaf item we estimate, on a rolling 10-year window ending each month,
how much of this month's inflation rate is still there next month (AR(1) rho), after
three months (sum of AR(3) coefficients) and at horizons 1/3/6/12 months (local
projections).  From those we build a "sticky" and a "flexible" CPI: the same
December-chained Laspeyres as the headline replica, but with each item's expenditure
weight multiplied by how persistent that item is (or by 1 - that, for the flexible one).

Everything here is a description of published BLS index series.  A high rho means the
item's monthly rate is serially correlated in the sample; it does NOT mean the item
causes inflation, that its prices are "sticky" in the menu-cost sense, or that a shock
to it will propagate.  See the caveats block below and docs/P3.md.

--------------------------------------------------------------------------------
UNIVERSE AND THE MONTHLY RATE
--------------------------------------------------------------------------------
Leaves = cpi_weight WHERE is_leaf=1 AND matched=1, per weight_year (December relative
importance of year Y applies to the months of Y+1).  Weight years in the DB are
2017..2025; the union over years is ~182 item codes.

Each item gets ONE monthly-rate definition, fixed for its whole history, recorded in
p3_persist.source:

  source='sa'     mom_sa, the published seasonally adjusted month-over-month percent
                  change.  144 of 179 current leaves, ~88.8% of the CPI-U basket.
  source='nsa12'  no SA series is published, so the rate is the crude deseasonalised
                  monthly rate  100 * (ln P_t - ln P_{t-12}) / 12  -- the 12-month log
                  change spread evenly over the 12 months.  35 leaves, ~11.0% of weight.

  *** The nsa12 filter is a 12-month moving average of monthly log changes, so it
  *** manufactures serial correlation.  For i.i.d. monthly changes it produces
  *** rho = 11/12 = 0.917 and a half-life of ~8.0 months out of pure noise (the
  *** pipeline re-derives this by simulation and logs it as `nsa12_null`).  nsa12
  *** half-lives are therefore NOT comparable with sa half-lives, and every ranking,
  *** normalisation and bucket in this pipeline is computed WITHIN source group.
  *** Treat nsa12 rows as a coverage device, not as a persistence estimate.

Lags are calendar-aligned throughout (October 2025 has no CPI; it is a hole in the
grid, never a row shift).  An item enters a window only if it has >= 96 monthly rates
(8 years) inside the 120-month window.

universe = 'raw'       the item's own monthly rate.
universe = 'relative'  item rate minus the headline (SA0) rate put through the *same*
                       filter (SA0 mom_sa for source='sa', SA0's nsa12 rate for
                       source='nsa12').  Univariate persistence confounds an item's own
                       persistence with persistence in the aggregate shocks hitting
                       every item; the relative universe strips the common component
                       out.  Both are stored; the Spearman correlation of the two
                       half-life rankings is reported every run.

--------------------------------------------------------------------------------
ESTIMATES (rolling 120-month window ending at `ym`, re-estimated every month)
--------------------------------------------------------------------------------
  rho        OLS slope of x_t on x_{t-1} with a constant (== demeaned AR(1)).
  halflife   ln(0.5)/ln(rho) months, 0 if rho <= 0, capped at 60 (rho >= 1 -> 60).
  ar3sum     sum of b1..b3 from x_t = a + b1 x_{t-1} + b2 x_{t-2} + b3 x_{t-3} + e.
             > 1 means the fitted process is non-stationary in that window.
  lp1/3/6/12 local projections: OLS slope of x_{s+h} on x_s over the window, only
             pairs with s+h <= ym so the estimate is real-time.  Read as "of a 1 pp
             move in this month's rate, this much is still in the rate h months later".
  lp12_se    Newey-West (Bartlett) HAC standard error of lp12, bandwidth h+1 = 13,
             with an n/(n-2) small-sample correction.  Overlapping horizons make the
             LP residuals MA(h-1); without HAC the SEs are far too small.
  pctile     percentile of this month's halflife within the item's OWN history of
             halflives up to and including this month (expanding, no look-ahead).
             Needs >= 12 prior windows.
  n_obs      usable AR(1) pairs in the window.

--------------------------------------------------------------------------------
STICKY / FLEXIBLE CPI
--------------------------------------------------------------------------------
December-chained Laspeyres over leaves (function `dec_chained` below is a verbatim copy
of p1_salience.dec_chained / Chainer - it is the comparison standard and
forbids cross-file imports), with the item weight replaced by

  s_i  = within-source rank percentile of rho_i, (rank - 0.5)/n, in (0,1)
  sticky_cpi   w_i * s_i          flexible_cpi   w_i * (1 - s_i)

rho_i is the *raw*-universe rho estimated on the window ending in **December of the
weight year**, i.e. the classification for the months of year Y+1 uses only data
published before those months existed.  The classification is refreshed every December.

Also written, all on exactly the same item set so they are comparable:
  official_replica          w_i (this p3 subset; p1_index's own official_replica is
                            untouched - different table, this one is p3_index)
  sticky_cpi_binary /       hard split at the within-source weighted median of rho
  flexible_cpi_binary       (closer in spirit to the Atlanta Fed's binary split)
  sticky_cpi_pooled /       s_i = clip(rho_i, 0, 0.99) pooled across sources, i.e. no
  flexible_cpi_pooled       correction for the nsa12 artefact - a sensitivity run that
                            shows how much the artefact matters

Months where less than 90% of the weight year's leaf weight is priced are dropped, not
extrapolated (MIN_COV, same rule as p1/p2).

Cross-check: Atlanta Fed sticky-price CPI via FRED (no key):
  STICKCPIM159SFRBATL / FLEXCPIM159SFRBATL  (12-month percent change)
  STICKCPIM157SFRBATL / FLEXCPIM157SFRBATL  (1-month percent change, SA)
Their split is *frequency of price change* (Bils-Klenow micro data: sticky = repriced
less often than every 4.3 months); ours is *time-series persistence of the published
index*.  They are different constructs and the levels differ by percentage points.
The comparison is a sanity band, not a validation.

--------------------------------------------------------------------------------
TABLES
--------------------------------------------------------------------------------
p3_persist(ym, item_code, universe, rho, halflife, ar3sum, lp1, lp3, lp6, lp12,
           lp12_se, pctile, n_obs, source)      PK (ym, item_code, universe)
p3_index(scheme, ym, idx, yoy)                  PK (scheme, ym)
validation rows: p3_official_replica_yoy, p3_sticky_vs_atlfed_yoy,
                 p3_flexible_vs_atlfed_yoy

--------------------------------------------------------------------------------
out/p3_persistence.json
--------------------------------------------------------------------------------
{ "generated_at", "latest_month", "window_months", "min_obs", "halflife_cap",
  "schema": {...}                       # this block, machine-readable
  "treemap": [ {"item_code","item_name","source","weight",
                "yoy",                                  # NSA 12-month % change
                "rho_raw","halflife_raw","pctile_raw","lp12_raw",
                "rho_relative","halflife_relative","pctile_relative"} ],   # latest month
  "series":  { "<scheme>": {"ym":[...], "idx":[...], "yoy":[...]} },
  "atlanta_fed": { "source", "note",
                   "series": {"sticky_yoy": {"ym":[],"v":[]}, ...},
                   "last12": [ {"ym","ours_sticky_logdiff","af_sticky_logdiff","diff",
                                "ours_flexible_logdiff","af_flexible_logdiff","diff_flex"} ],
                   "corr": {"sticky":..,"flexible":..,"n":..} },
  "summary": { "buckets": {"raw": {"lt3":..,"3to12":..,"gt12":..,"capped":..},
                           "by_source": {...}},        # % of covered basket weight
               "spearman_raw_vs_relative": {"rho":..,"n":..},
               "spearman_hl_vs_weight": ...,
               "stickiest": [...], "most_flexible": [...],   # 10 each, latest month
               "coverage": {"ym": [...], "pct": [...]},
               "nsa12_null": {"rho_mean","halflife_mean","note"},
               "nsa12_robustness": {"spearman_hl_nsa12_vs_demeaned","n","note"} },
  "notes": [ ... ] }

--------------------------------------------------------------------------------
CAVEATS (repeated in docs/P3.md; do not strip them from any front-end)
--------------------------------------------------------------------------------
1. Univariate persistence != own persistence.  A common shock that fades slowly makes
   every item look sticky.  Compare universe='raw' with universe='relative'.
2. Rolling-window instability: rho estimated on 120 monthly observations has a standard
   error of roughly 0.09, so a half-life of 6 months and one of 12 are often not
   statistically distinguishable.  lp12_se is the only uncertainty number we publish;
   treat the half-life league table as indicative.
3. SA and NSA-derived rates are mixed (see the nsa12 warning above).  Never rank an sa
   item against an nsa12 item.
4. Half-life is a summary of an AR(1) fitted to a possibly non-AR(1) process; where
   ar3sum differs a lot from rho the AR(1) summary is poor.
5. No causal claim.  "Sticky" here is a property of the published index series in a
   sample, not a statement about price-setting behaviour or about what policy does.
"""
import sys, json, math, datetime as dt
import numpy as np, pandas as pd
from common import *

# ---------------------------------------------------------------------------- config
WINDOW = 120                 # rolling window, months
MIN_OBS = 96                 # >= 8 years of monthly rates inside the window
HL_CAP = 60.0                # half-life cap, months
HORIZONS = (1, 3, 6, 12)
MIN_PCT_HIST = 12            # windows needed before pctile is meaningful
MIN_COV_MONTH = 0.90         # coverage gate for p3_persist months
MIN_COV = 0.90               # coverage gate inside the chainer (same value as p1)
GRID_START = "1995-01"       # enough history for a 120m window ending 2010-01 (+12 for nsa12)
DEFAULT_SINCE = "2010-01"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
AF_SERIES = {"sticky_yoy": "STICKCPIM159SFRBATL", "flexible_yoy": "FLEXCPIM159SFRBATL",
             "sticky_mom": "STICKCPIM157SFRBATL", "flexible_mom": "FLEXCPIM157SFRBATL"}

SCHEMA3 = """
CREATE TABLE IF NOT EXISTS p3_persist(ym TEXT, item_code TEXT, universe TEXT, rho REAL,
  halflife REAL, ar3sum REAL, lp1 REAL, lp3 REAL, lp6 REAL, lp12 REAL, lp12_se REAL,
  pctile REAL, n_obs INT, source TEXT, PRIMARY KEY(ym, item_code, universe));
CREATE INDEX IF NOT EXISTS p3_persist_i ON p3_persist(item_code, universe, ym);
CREATE TABLE IF NOT EXISTS p3_index(scheme TEXT, ym TEXT, idx REAL, yoy REAL, PRIMARY KEY(scheme, ym));
"""


# ---------------------------------------------------------------------------- little OLS
def _bivariate(y, x):
    """Slope/intercept of y on x with a constant. Returns (b, xd, resid, sxx) or None."""
    n = len(y)
    if n < 3:
        return None
    xb = x.mean()
    xd = x - xb
    sxx = float(xd @ xd)
    if sxx <= 0:
        return None
    yd = y - y.mean()
    b = float(xd @ yd) / sxx
    return b, xd, yd - b * xd, sxx


def _hac_se(xd, u, sxx, pos, T, lags):
    """Newey-West (Bartlett) SE of the slope. `pos` are the window positions of the used
    observations, so gaps (Oct-2025) kill the cross-products that span them instead of
    silently pretending the series is contiguous."""
    n = len(u)
    if n <= 2 or sxx <= 0:
        return None
    z = np.zeros(T)
    z[pos] = xd * u
    s = float(z @ z)
    for j in range(1, lags + 1):
        s += 2.0 * (1.0 - j / (lags + 1.0)) * float(z[j:] @ z[:-j])
    if not np.isfinite(s) or s <= 0:
        return None
    return math.sqrt(s * n / (n - 2)) / sxx


def _ar3sum(y, L1, L2, L3):
    if len(y) < 10:
        return None
    A = np.column_stack([np.ones(len(y)), L1, L2, L3])
    try:
        beta = np.linalg.solve(A.T @ A, A.T @ y)
    except np.linalg.LinAlgError:
        return None
    return float(beta[1:].sum())


def halflife(rho):
    if rho is None or not np.isfinite(rho):
        return None
    if rho <= 0:
        return 0.0
    if rho >= 1:
        return HL_CAP
    return float(min(HL_CAP, math.log(0.5) / math.log(rho)))


# ---------------------------------------------------------------------------- panel
def build_rates(con, last):
    """Returns (grid, rate_raw, rate_rel, source, leaves_by_year, weights, names).

    rate_* are DataFrames indexed by the complete monthly grid (missing months are NaN
    rows, so pandas .shift() IS calendar-aligned here) with one column per leaf item."""
    w = pd.read_sql("SELECT weight_year, item_code, weight_u FROM cpi_weight "
                    "WHERE is_leaf=1 AND matched=1", con)
    leaves_by_year = {int(y): g.set_index("item_code").weight_u.astype(float)
                      for y, g in w.groupby("weight_year")}
    universe = sorted(set(w.item_code))
    names = dict(pd.read_sql("SELECT item_code, item_name FROM cu_item", con).values)

    im = pd.read_sql("SELECT item_code, ym, idx_nsa, mom_sa, mom_nsa FROM cpi_item_month "
                     "WHERE ym >= ?", con, params=(GRID_START,))
    grid = [str(p) for p in pd.period_range(GRID_START, last, freq="M")]
    keep = im[im.item_code.isin(universe + ["SA0"])]
    piv_sa = keep.pivot_table(index="ym", columns="item_code", values="mom_sa").reindex(grid)
    piv_nsa = keep.pivot_table(index="ym", columns="item_code", values="idx_nsa").reindex(grid)
    piv_mn = keep.pivot_table(index="ym", columns="item_code", values="mom_nsa").reindex(grid)
    with np.errstate(divide="ignore", invalid="ignore"):
        lnp = np.log(piv_nsa.where(piv_nsa > 0))
    piv_n12 = (lnp - lnp.shift(12)) / 12.0 * 100.0     # calendar-aligned: grid has every month

    source, raw = {}, {}
    for c in universe:
        n_sa = int(piv_sa[c].notna().sum()) if c in piv_sa.columns else 0
        if n_sa >= MIN_OBS:
            source[c] = "sa"
            raw[c] = piv_sa[c]
        elif c in piv_n12.columns and int(piv_n12[c].notna().sum()) >= MIN_OBS:
            source[c] = "nsa12"
            raw[c] = piv_n12[c]
        else:
            log.info("dropping %s (%s): too little history (sa %d, nsa12 %d)", c, names.get(c, ""),
                     n_sa, int(piv_n12[c].notna().sum()) if c in piv_n12.columns else 0)
    rate_raw = pd.DataFrame(raw, index=grid)
    head = {"sa": piv_sa["SA0"], "nsa12": piv_n12["SA0"]}
    rate_rel = pd.DataFrame({c: rate_raw[c] - head[source[c]] for c in rate_raw.columns}, index=grid)
    ns = pd.Series(source)
    log.info("panel: %d leaf items on %s..%s | source sa %d, nsa12 %d",
             len(rate_raw.columns), grid[0], grid[-1], (ns == "sa").sum(), (ns == "nsa12").sum())
    return grid, rate_raw, rate_rel, source, leaves_by_year, names, piv_mn, piv_nsa


# ---------------------------------------------------------------------------- estimates
def window_stats(x, it, T_grid):
    """All persistence statistics for the 120-month window of `x` ending at grid pos `it`."""
    start = it - WINDOW + 1
    if start < 0:
        return None
    T = it - start + 1

    # AR(1): pairs fully inside the window
    y = x[start + 1:it + 1]
    x1 = x[start:it]
    m = np.isfinite(y) & np.isfinite(x1)
    n = int(m.sum())
    if n < MIN_OBS:
        return None
    fit = _bivariate(y[m], x1[m])
    if fit is None:
        return None
    rho = fit[0]
    out = {"rho": rho, "halflife": halflife(rho), "n_obs": n}

    # AR(3)
    y3 = x[start + 3:it + 1]
    l1, l2, l3 = x[start + 2:it], x[start + 1:it - 1], x[start:it - 2]
    m3 = np.isfinite(y3) & np.isfinite(l1) & np.isfinite(l2) & np.isfinite(l3)
    out["ar3sum"] = _ar3sum(y3[m3], l1[m3], l2[m3], l3[m3]) if m3.sum() >= MIN_OBS - 12 else None

    # local projections, real-time (s + h <= it)
    for h in HORIZONS:
        xs = x[start:it - h + 1]
        yh = x[start + h:it + 1]
        mh = np.isfinite(xs) & np.isfinite(yh)
        if mh.sum() < MIN_OBS - h:
            out[f"lp{h}"] = None
            if h == 12:
                out["lp12_se"] = None
            continue
        f = _bivariate(yh[mh], xs[mh])
        if f is None:
            out[f"lp{h}"] = None
            if h == 12:
                out["lp12_se"] = None
            continue
        out[f"lp{h}"] = f[0]
        if h == 12:
            pos = np.nonzero(mh)[0]                     # positions within the window
            out["lp12_se"] = _hac_se(f[1], f[2], f[3], pos, T, h + 1)
    return out


def expanding_pct(v):
    """Percentile of v[i] within v[:i+1] (finite entries only), no look-ahead."""
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if not np.isfinite(v[i]):
            continue
        h = v[:i + 1]
        h = h[np.isfinite(h)]
        if len(h) >= MIN_PCT_HIST:
            out[i] = 100.0 * float((h <= v[i]).mean())
    return out


def estimate(rate, grid, months, source, universe_name):
    pos = {m: i for i, m in enumerate(grid)}
    T_grid = len(grid)
    mpos = [(m, pos[m]) for m in months if m in pos]
    rows = []
    for c in rate.columns:
        x = rate[c].to_numpy(float)
        per_item = []
        for ym, it in mpos:
            r = window_stats(x, it, T_grid)
            if r is None:
                continue
            per_item.append((ym, r))
        if not per_item:
            continue
        hl = np.array([r["halflife"] if r["halflife"] is not None else np.nan for _, r in per_item])
        pc = expanding_pct(hl)
        for (ym, r), p in zip(per_item, pc):
            rows.append((ym, c, universe_name, r["rho"], r["halflife"], r["ar3sum"],
                         r.get("lp1"), r.get("lp3"), r.get("lp6"), r.get("lp12"),
                         r.get("lp12_se"), None if not np.isfinite(p) else float(p),
                         r["n_obs"], source[c]))
    return rows


def nsa12_null(n_sims=400, seed=20260819):
    """What the nsa12 filter alone produces out of i.i.d. monthly changes.
    Analytic answer for the lag-1 autocorrelation of a 12-term moving average is 11/12."""
    rng = np.random.default_rng(seed)
    rhos = []
    for _ in range(n_sims):
        e = rng.standard_normal(WINDOW + 12)
        f = np.convolve(e, np.ones(12) / 12.0, mode="valid")     # the (1/12)*sum filter
        fit = _bivariate(f[1:], f[:-1])
        if fit:
            rhos.append(fit[0])
    r = float(np.mean(rhos))
    return {"rho_mean": round(r, 4), "halflife_mean": round(halflife(r), 2),
            "analytic_rho": round(11 / 12, 4), "analytic_halflife": round(halflife(11 / 12), 2),
            "n_sims": n_sims,
            "note": "AR(1) rho of the 12-month moving-average filter applied to i.i.d. noise. "
                    "Any nsa12 item at or below this is indistinguishable from white noise."}


# ---------------------------------------------------------------------------- December-chained Laspeyres
# --- verbatim copy of p1_salience.Chainer / dec_chained (copy, do not import) ---
class Chainer:
    """Vectorised December-chained Laspeyres; arithmetic identical to dec_chained().

    A month is skipped unless leaves carrying at least MIN_COV of the scheme's total weight
    have both a December base index and a current index.  Without this, October 2025 (no CPI
    release - government shutdown) was priced off the ~11 leaf items that happen to carry an
    Oct-2025 observation, which produced a spurious index level and YoY.
    """

    def __init__(self, im, leaves_by_year, pub_sa0):
        self.pub = pub_sa0
        self.skipped = {}
        self.years = sorted(leaves_by_year)
        piv = im.pivot_table(index="item_code", columns="ym", values="idx_nsa")
        self.items, self.months, self.R, self.M = {}, {}, {}, {}
        for y in self.years:
            items = list(leaves_by_year[y])
            self.items[y] = items
            bym = f"{y}-12"
            b = piv[bym].reindex(items).values if bym in piv.columns else np.full(len(items), np.nan)
            ms, rows = [], []
            for mo in range(1, 13):
                ym = f"{y+1}-{mo:02d}"
                if ym not in piv.columns:
                    continue
                ms.append(ym)
                rows.append(piv[ym].reindex(items).values / b)
            R = np.array(rows) if rows else np.zeros((0, len(items)))
            self.months[y] = ms
            self.M[y] = np.isfinite(R).astype(float)
            self.R[y] = np.where(np.isfinite(R), R, 0.0)

    def run(self, weights_by_year, note=None):
        out, skipped = {}, []
        for y in self.years:
            if y not in weights_by_year or not self.months[y]:
                continue
            w = pd.Series(weights_by_year[y]).reindex(self.items[y]).fillna(0.0).values.astype(float)
            tot = w.sum()
            if tot <= 0:
                continue
            den = self.M[y] @ w
            num = self.R[y] @ w
            for k, ym in enumerate(self.months[y]):
                if den[k] >= MIN_COV * tot:
                    out[ym] = num[k] / den[k]
                elif den[k] > 0:
                    skipped.append((ym, den[k] / tot))
        for ym, c in skipped:
            self.skipped[ym] = max(self.skipped.get(ym, 0.0), c)
        if note and skipped:
            log.info("%s: dropped %d month(s) with leaf coverage < %.0f%%: %s", note, len(skipped), MIN_COV * 100,
                     [(ym, f"{100*c:.1f}%") for ym, c in skipped])
        s = pd.Series(out).sort_index()
        level, last_dec = {}, None
        for ym, rel in s.items():
            y = int(ym[:4]) - 1
            if last_dec is None or last_dec[0] != y:
                last_dec = (y, level.get(f"{y}-12", self.pub.get(f"{y}-12")))
            level[ym] = last_dec[1] * rel
        lv = pd.Series(level).sort_index()
        p = pd.PeriodIndex(lv.index, freq="M")
        prev = pd.Series(lv.values, index=(p + 12).astype(str))
        yoy = (lv / prev.reindex(lv.index) - 1) * 100
        return lv, yoy


def dec_chained(im, weights_by_year, pub_sa0):
    """Dec-chained Laspeyres over leaves. weights_by_year: {weight_year: Series(item_code -> weight)}.
    Months with less than MIN_COV of the leaf weight priced are dropped, not extrapolated."""
    return Chainer(im, {y: list(w.index) for y, w in weights_by_year.items()}, pub_sa0).run(weights_by_year)
# --- end copied block ------------------------------------------------------------------


def wmedian(v, w):
    o = np.argsort(v)
    v, w = np.asarray(v)[o], np.asarray(w)[o]
    cw = np.cumsum(w) / w.sum()
    return float(v[int(np.searchsorted(cw, 0.5, side="left"))])


def classify(persist_raw, leaves_by_year, source):
    """{scheme: {weight_year: Series(item->weight)}} using the December-of-weight-year window.
    Returns also a diagnostics frame of the December classifications."""
    schemes = {k: {} for k in ("official_replica", "sticky_cpi", "flexible_cpi",
                               "sticky_cpi_binary", "flexible_cpi_binary",
                               "sticky_cpi_pooled", "flexible_cpi_pooled")}
    diag = []
    idx = persist_raw.set_index(["ym", "item_code"])
    for y, wts in sorted(leaves_by_year.items()):
        dec = f"{y}-12"
        if dec not in set(persist_raw.ym):
            log.info("no persistence estimates for %s - weight year %d not classified", dec, y)
            continue
        d = persist_raw[persist_raw.ym == dec].set_index("item_code")
        common = [c for c in wts.index if c in d.index and np.isfinite(d.rho.get(c, np.nan))]
        if not common:
            continue
        w = wts.reindex(common).astype(float)
        rho = d.rho.reindex(common).astype(float)
        src = pd.Series({c: source[c] for c in common})
        # within-source rank percentile, (rank - 0.5) / n, in (0,1)
        s = pd.Series(index=common, dtype=float)
        binary = pd.Series(index=common, dtype=float)
        for grp, g in src.groupby(src):
            cc = list(g.index)
            r = rho[cc].rank(method="average")
            s[cc] = (r - 0.5) / len(cc)
            med = wmedian(rho[cc].values, w[cc].values)
            binary[cc] = (rho[cc] >= med).astype(float)
        pooled = rho.clip(0.0, 0.99)
        schemes["official_replica"][y] = w
        schemes["sticky_cpi"][y] = w * s
        schemes["flexible_cpi"][y] = w * (1 - s)
        schemes["sticky_cpi_binary"][y] = w * binary
        schemes["flexible_cpi_binary"][y] = w * (1 - binary)
        schemes["sticky_cpi_pooled"][y] = w * pooled
        schemes["flexible_cpi_pooled"][y] = w * (1 - pooled)
        cov = 100 * w.sum() / wts.sum()
        diag.append({"weight_year": y, "classified_at": dec, "n_items": len(common),
                     "coverage_pct": round(float(cov), 2),
                     "sticky_weight_share": round(float((w * s).sum() / w.sum() * 100), 2),
                     "binary_sticky_weight_share": round(float((w * binary).sum() / w.sum() * 100), 2)})
        log.info("classify %d from %s: %d items, %.1f%% of leaf weight, sticky weight share %.1f%% "
                 "(binary %.1f%%)", y, dec, len(common), cov, diag[-1]["sticky_weight_share"],
                 diag[-1]["binary_sticky_weight_share"])
    return schemes, diag


# ---------------------------------------------------------------------------- Atlanta Fed
def atlanta_fed():
    out = {}
    for k, sid in AF_SERIES.items():
        try:
            path, _ = fetch(FRED.format(sid), RAW / "atlantafed" / f"{sid}.csv", retries=2)
            df = pd.read_csv(path)
            dcol, vcol = df.columns[0], df.columns[1]
            df["ym"] = pd.to_datetime(df[dcol]).dt.strftime("%Y-%m")
            s = pd.to_numeric(df[vcol], errors="coerce").set_axis(df.ym).dropna()
            out[k] = s
            log.info("Atlanta Fed %s (%s): %d months %s..%s, latest %.3f",
                     k, sid, len(s), s.index[0], s.index[-1], s.iloc[-1])
        except Exception as e:  # noqa
            log.warning("could not fetch %s (%s): %s", k, sid, e)
    return out


def spearman(a, b):
    d = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(d) < 5:
        return None, len(d)
    r = d.a.rank()
    s = d.b.rank()
    return float(np.corrcoef(r, s)[0, 1]), len(d)


# ---------------------------------------------------------------------------- main
def main(since=DEFAULT_SINCE, quarterly=False, do_fred=True):
    con = init_db()
    con.executescript(SCHEMA3)
    con.commit()

    last = con.execute("SELECT MAX(ym) FROM cpi_item_month").fetchone()[0]
    grid, rate_raw, rate_rel, source, leaves_by_year, names, piv_mn, piv_nsa = build_rates(con, last)
    months = [m for m in grid if m >= since]
    if quarterly:
        months = [m for m in months if int(m[5:]) % 3 == 0]
    log.info("estimating persistence on %d months (%s..%s), window %dm, min %d obs",
             len(months), months[0], months[-1], WINDOW, MIN_OBS)

    t0 = dt.datetime.now()
    rows = estimate(rate_raw, grid, months, source, "raw") + \
        estimate(rate_rel, grid, months, source, "relative")
    log.info("estimated %d item-month-universe rows in %.1fs", len(rows), (dt.datetime.now() - t0).total_seconds())

    P = pd.DataFrame(rows, columns=["ym", "item_code", "universe", "rho", "halflife", "ar3sum",
                                    "lp1", "lp3", "lp6", "lp12", "lp12_se", "pctile", "n_obs", "source"])
    NUMCOLS = ["rho", "halflife", "ar3sum", "lp1", "lp3", "lp6", "lp12", "lp12_se", "pctile"]
    for cn in NUMCOLS:
        P[cn] = pd.to_numeric(P[cn], errors="coerce")
    P["n_obs"] = pd.to_numeric(P["n_obs"], errors="coerce").fillna(0).astype(int)

    # ---- coverage gate: drop months where < 90% of that weight year's leaf weight is estimated
    wys = sorted(leaves_by_year)
    cov_rows, drop = [], set()
    for ym in sorted(set(P.ym)):
        wy = min(max(int(ym[:4]) - 1, wys[0]), wys[-1])
        wts = leaves_by_year[wy]
        got = set(P[(P.ym == ym) & (P.universe == "raw") & P.rho.notna()].item_code)
        pct = 100.0 * wts.reindex([c for c in wts.index if c in got]).sum() / wts.sum()
        cov_rows.append((ym, round(float(pct), 2), int(len(got)), wy))
        if pct < MIN_COV_MONTH * 100:
            drop.add(ym)
    if drop:
        log.info("coverage gate: dropping %d month(s) below %.0f%% of leaf weight: %s",
                 len(drop), MIN_COV_MONTH * 100, sorted(drop)[:8])
        P = P[~P.ym.isin(drop)]
    cov_rows = [c for c in cov_rows if c[0] not in drop]
    log.info("p3_persist coverage %s..%s: min %.1f%%, median %.1f%%, latest %.1f%%",
             cov_rows[0][0], cov_rows[-1][0], min(c[1] for c in cov_rows),
             float(np.median([c[1] for c in cov_rows])), cov_rows[-1][1])

    def _f(v):
        return None if v is None or not np.isfinite(v) else float(v)
    recs = [(r.ym, r.item_code, r.universe, _f(r.rho), _f(r.halflife), _f(r.ar3sum), _f(r.lp1),
             _f(r.lp3), _f(r.lp6), _f(r.lp12), _f(r.lp12_se), _f(r.pctile), int(r.n_obs), r.source)
            for r in P.itertuples(index=False)]
    con.execute("DELETE FROM p3_persist")
    con.executemany("INSERT INTO p3_persist VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", recs)
    con.commit()
    log.info("p3_persist: %d rows, %d months, %d items x 2 universes",
             len(P), P.ym.nunique(), P.item_code.nunique())

    # ---- indexes
    im = pd.read_sql("SELECT item_code, ym, idx_nsa FROM cpi_item_month", con)
    pub = pd.read_sql("SELECT ym, idx_nsa, yoy FROM cpi_item_month WHERE item_code='SA0'", con).set_index("ym")
    praw = P[P.universe == "raw"]
    schemes, cls_diag = classify(praw, leaves_by_year, source)

    series = {}
    for name, wby in schemes.items():
        if not wby:
            continue
        lv, yoy = dec_chained(im, wby, pub.idx_nsa)
        series[name] = pd.DataFrame({"idx": lv, "yoy": yoy})
        con.execute("DELETE FROM p3_index WHERE scheme=?", (name,))
        con.executemany("INSERT INTO p3_index VALUES(?,?,?,?)",
                        [(name, ym, float(r.idx), None if not np.isfinite(r.yoy) else float(r.yoy))
                         for ym, r in series[name].iterrows()])
        log.info("%-22s %s..%s  latest idx %.3f  YoY %.2f%%", name, lv.index[0], lv.index[-1],
                 lv.iloc[-1], series[name].yoy.iloc[-1])
    con.commit()

    # who actually is the sticky index? (the answer is "mostly shelter" - say so out loud)
    comp = {}
    wy_last = max(schemes["sticky_cpi"])
    for nm in ("sticky_cpi", "flexible_cpi"):
        sw = schemes[nm][wy_last]
        sh = (sw / sw.sum() * 100).sort_values(ascending=False).head(8)
        comp[nm] = [{"item_code": c, "item_name": names.get(c, c), "share_of_scheme_weight": round(float(v), 2)}
                    for c, v in sh.items()]
        log.info("%s composition (weight year %d, %% of scheme weight): %s", nm, wy_last,
                 ", ".join(f"{names.get(c, c)[:26]} {v:.1f}" for c, v in sh.items()))

    # ---- validation: our official_replica against the published headline
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    ok_all = True
    rep = series["official_replica"]
    for ym in rep.dropna(subset=["yoy"]).index[-6:]:
        ours, p = float(rep.yoy[ym]), float(pub.yoy.get(ym, np.nan))
        diff = ours - p
        ok = abs(diff) < 0.15
        ok_all &= bool(ok)
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    (now, "p3_official_replica_yoy", ym, ours, p, diff, int(ok)))
        log.info("validate %s: p3 replica YoY %.3f vs published %.3f (diff %+.3f) %s",
                 ym, ours, p, diff, "OK" if ok else "MISMATCH")

    # ---- Atlanta Fed cross-check (log differences, last 12 months)
    af = atlanta_fed() if do_fred else {}
    af_block = {"source": "FRED " + ", ".join(AF_SERIES.values()),
                "note": "Atlanta Fed splits the basket by frequency of price change (Bils-Klenow: "
                        "sticky = repriced less often than every 4.3 months) and publishes an SA "
                        "index; P3 splits by time-series persistence of the published NSA index and "
                        "weights continuously. Levels are not expected to match - this is a sanity "
                        "band, not a validation.",
                "series": {k: {"ym": list(v.index), "v": [round(float(x), 4) for x in v.values]}
                           for k, v in af.items()},
                "last12": [], "corr": {}}
    if af:
        def logdiff(s):
            p = pd.PeriodIndex(s.index, freq="M")
            prev = pd.Series(s.values, index=(p + 12).astype(str))
            return 100.0 * np.log(s / prev.reindex(s.index))
        ours_s, ours_f = logdiff(series["sticky_cpi"].idx), logdiff(series["flexible_cpi"].idx)
        af_s = 100.0 * np.log1p(af["sticky_yoy"] / 100.0) if "sticky_yoy" in af else None
        af_f = 100.0 * np.log1p(af["flexible_yoy"] / 100.0) if "flexible_yoy" in af else None
        tail = [m for m in ours_s.dropna().index][-12:]
        log.info("Atlanta Fed cross-check (12-month log differences, percent):")
        log.info("  month     ours_sticky  AF_sticky   diff | ours_flex  AF_flex    diff")
        for ym in tail:
            a, b = float(ours_s.get(ym, np.nan)), float(af_s.get(ym, np.nan)) if af_s is not None else np.nan
            c, d = float(ours_f.get(ym, np.nan)), float(af_f.get(ym, np.nan)) if af_f is not None else np.nan
            af_block["last12"].append({
                "ym": ym, "ours_sticky_logdiff": None if not np.isfinite(a) else round(a, 3),
                "af_sticky_logdiff": None if not np.isfinite(b) else round(b, 3),
                "diff_sticky": None if not (np.isfinite(a) and np.isfinite(b)) else round(a - b, 3),
                "ours_flexible_logdiff": None if not np.isfinite(c) else round(c, 3),
                "af_flexible_logdiff": None if not np.isfinite(d) else round(d, 3),
                "diff_flexible": None if not (np.isfinite(c) and np.isfinite(d)) else round(c - d, 3)})
            log.info("  %s   %8.2f   %8.2f  %+6.2f | %8.2f  %8.2f  %+6.2f", ym, a, b, a - b, c, d, c - d)
            for tag, o, x in (("p3_sticky_vs_atlfed_yoy", a, b), ("p3_flexible_vs_atlfed_yoy", c, d)):
                if np.isfinite(o) and np.isfinite(x):
                    con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                                (now, tag, ym, o, x, o - x, int(abs(o - x) < 2.0)))
        for key, o, x in (("sticky", ours_s, af_s), ("flexible", ours_f, af_f)):
            if x is None:
                continue
            j = pd.concat([o.rename("o"), x.rename("x")], axis=1).dropna()
            af_block["corr"][key] = {"corr": round(float(np.corrcoef(j.o, j.x)[0, 1]), 4),
                                     "mean_diff": round(float((j.o - j.x).mean()), 3),
                                     "mae": round(float((j.o - j.x).abs().mean()), 3), "n": int(len(j))}
            log.info("  %-9s corr %.3f, mean diff %+.2f pp, MAE %.2f pp over %d overlapping months",
                     key, af_block["corr"][key]["corr"], af_block["corr"][key]["mean_diff"],
                     af_block["corr"][key]["mae"], len(j))
    con.commit()

    # ---- latest-month cross section
    lm = P.ym.max()
    cur = P[P.ym == lm].pivot(index="item_code", columns="universe")
    wy = min(max(int(lm[:4]) - 1, wys[0]), wys[-1])
    wts = leaves_by_year[wy]
    yoy_now = pd.read_sql("SELECT item_code, yoy FROM cpi_item_month WHERE ym=?", con,
                          params=(lm,)).set_index("item_code").yoy

    tm = []
    for c in cur.index:
        if c not in wts.index:
            continue
        g = lambda f, u: (None if (f, u) not in cur.columns or not np.isfinite(cur.loc[c, (f, u)])  # noqa
                          else round(float(cur.loc[c, (f, u)]), 4))
        tm.append({"item_code": c, "item_name": names.get(c, c), "source": source[c],
                   "weight": round(float(wts[c]), 4),
                   "yoy": None if c not in yoy_now.index or not np.isfinite(yoy_now[c]) else round(float(yoy_now[c]), 3),
                   "rho_raw": g("rho", "raw"), "halflife_raw": g("halflife", "raw"),
                   "pctile_raw": g("pctile", "raw"), "lp12_raw": g("lp12", "raw"),
                   "lp12_se_raw": g("lp12_se", "raw"), "ar3sum_raw": g("ar3sum", "raw"),
                   "rho_relative": g("rho", "relative"), "halflife_relative": g("halflife", "relative"),
                   "pctile_relative": g("pctile", "relative")})
    tmdf = pd.DataFrame(tm)

    # buckets (% of the covered basket weight, by half-life of the raw universe)
    def buckets(d):
        w = d.weight.sum()
        if w <= 0:
            return {}
        h = d.halflife_raw
        return {"lt3": round(float(d.weight[h < 3].sum() / w * 100), 2),
                "3to12": round(float(d.weight[(h >= 3) & (h <= 12)].sum() / w * 100), 2),
                "gt12": round(float(d.weight[h > 12].sum() / w * 100), 2),
                "capped60": round(float(d.weight[h >= HL_CAP].sum() / w * 100), 2),
                "covered_weight": round(float(w), 3), "n_items": int(len(d))}
    bk = {"all": buckets(tmdf.dropna(subset=["halflife_raw"])),
          "by_source": {s: buckets(g.dropna(subset=["halflife_raw"]))
                        for s, g in tmdf.groupby("source")}}

    sp_rho, sp_n = spearman(tmdf.halflife_raw, tmdf.halflife_relative)
    sp_sa, sp_sa_n = spearman(tmdf[tmdf.source == "sa"].halflife_raw,
                              tmdf[tmdf.source == "sa"].halflife_relative)

    # League tables are WITHIN source group. The nsa12 filter inflates half-lives (see
    # nsa12_null), so a pooled ranking is just a list of NSA-only items and is meaningless.
    ranked = tmdf.dropna(subset=["halflife_raw"])
    rk_sa = ranked[ranked.source == "sa"]
    rk_n12 = ranked[ranked.source == "nsa12"]
    stickiest = rk_sa.sort_values(["halflife_raw", "weight"], ascending=[False, False]).head(10)
    flexible = rk_sa.sort_values(["halflife_raw", "weight"], ascending=[True, False]).head(10)
    stickiest_n12 = rk_n12.sort_values(["halflife_raw", "weight"], ascending=[False, False]).head(10)
    flexible_n12 = rk_n12.sort_values(["halflife_raw", "weight"], ascending=[True, False]).head(10)

    # nsa12 robustness: month-of-year demeaned NSA MoM vs the nsa12 filter, latest window
    it = grid.index(lm)
    alt = {}
    for c in [c for c in rate_raw.columns if source[c] == "nsa12"]:
        s = piv_mn[c].reindex(grid) if c in piv_mn.columns else None
        if s is None:
            continue
        v = s.to_numpy(float).copy()
        seg = slice(max(0, it - WINDOW + 1), it + 1)
        mo = np.array([int(m[5:]) for m in grid])
        for k in range(1, 13):                       # month-of-year demeaning inside the window
            sel = (mo == k)
            sel[:seg.start] = False
            sel[it + 1:] = False
            vals = v[sel]
            vals = vals[np.isfinite(vals)]
            if len(vals) >= 5:
                v[sel] = v[sel] - vals.mean()
        r = window_stats(v, it, len(grid))
        if r:
            alt[c] = r["halflife"]
    a = pd.Series(alt)
    b = tmdf.set_index("item_code").halflife_raw.reindex(a.index)
    rob_rho, rob_n = spearman(a, b)

    null = nsa12_null()
    log.info("nsa12 null benchmark: rho %.3f -> half-life %.1f months out of pure noise "
             "(analytic 11/12 = %.3f, %.1f months)", null["rho_mean"], null["halflife_mean"],
             null["analytic_rho"], null["analytic_halflife"])
    log.info("nsa12 robustness: Spearman(half-life via 12m-MA filter, half-life via month-of-year "
             "demeaned NSA MoM) = %s over %d items", "n/a" if rob_rho is None else f"{rob_rho:.3f}", rob_n)

    # ---- report
    def league(title, d, se=True):
        log.info("=== %s %s", lm, title)
        for r in d.itertuples():
            log.info("   %-7s %-42s w=%5.2f  hl=%5.1f  rho=%+.3f  lp12=%+.3f%s  pctile=%s  yoy=%s",
                     r.item_code, r.item_name[:42], r.weight, r.halflife_raw, r.rho_raw,
                     r.lp12_raw if r.lp12_raw is not None else float("nan"),
                     "" if not se else (" (se n/a)" if r.lp12_se_raw is None else f" (se {r.lp12_se_raw:.3f})"),
                     "n/a" if r.pctile_raw is None else f"{r.pctile_raw:4.0f}",
                     "n/a" if r.yoy is None else f"{r.yoy:+.2f}")
    league("stickiest 10 of the SA-measured items (%.1f%% of the basket) - half-life in months"
           % rk_sa.weight.sum(), stickiest)
    league("most flexible 10 of the SA-measured items", flexible)
    league("stickiest 10 of the nsa12 items -- NOT comparable with the SA list: the 12-month "
           "moving-average filter alone yields hl ~ %.1fm from white noise" % null["halflife_mean"],
           stickiest_n12)
    log.info("=== %s half-life buckets (%% of covered leaf weight): <3m %.1f | 3-12m %.1f | >12m %.1f "
             "(capped at 60m: %.1f) over %d items / %.1f weight",
             lm, bk["all"]["lt3"], bk["all"]["3to12"], bk["all"]["gt12"], bk["all"]["capped60"],
             bk["all"]["n_items"], bk["all"]["covered_weight"])
    for s, v in bk["by_source"].items():
        log.info("      source %-5s: <3m %.1f | 3-12m %.1f | >12m %.1f  (%d items, %.1f weight)",
                 s, v["lt3"], v["3to12"], v["gt12"], v["n_items"], v["covered_weight"])
    log.info("=== Spearman(half-life raw, half-life relative) at %s = %s over %d items "
             "(sa-only items: %s over %d)", lm, "n/a" if sp_rho is None else f"{sp_rho:.3f}", sp_n,
             "n/a" if sp_sa is None else f"{sp_sa:.3f}", sp_sa_n)
    log.info("=== sticky vs flexible CPI, 12-month percent change, last 12 months")
    log.info("    month    sticky  flexible  spread | binary stk/flx | p3 replica  published SA0")
    for ym in list(series["official_replica"].index)[-12:]:
        s_, f_ = float(series["sticky_cpi"].yoy.get(ym, np.nan)), float(series["flexible_cpi"].yoy.get(ym, np.nan))
        log.info("    %s  %6.2f   %6.2f   %+6.2f | %6.2f %6.2f | %6.2f      %6.2f", ym, s_, f_, s_ - f_,
                 float(series["sticky_cpi_binary"].yoy.get(ym, np.nan)),
                 float(series["flexible_cpi_binary"].yoy.get(ym, np.nan)),
                 float(series["official_replica"].yoy.get(ym, np.nan)), float(pub.yoy.get(ym, np.nan)))

    # ---- JSON
    def ser(df):
        return {"ym": list(df.index),
                "idx": [round(float(v), 4) for v in df.idx],
                "yoy": [None if not np.isfinite(v) else round(float(v), 4) for v in df.yoy]}

    def slim(d):
        # d.to_dict("records") turns a missing yoy (stored as None in tm) back into float('nan');
        # scrub non-finite floats to None so json.dumps does not emit a literal NaN (invalid JSON).
        keys = ("item_code", "item_name", "source", "weight", "halflife_raw",
                "rho_raw", "lp12_raw", "pctile_raw", "yoy")
        def clean(v):
            return None if isinstance(v, float) and not np.isfinite(v) else v
        return [{k: clean(r[k]) for k in keys} for r in d.to_dict("records")]

    out = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "latest_month": lm,
        "window_months": WINDOW, "min_obs": MIN_OBS, "halflife_cap": HL_CAP,
        "horizons": list(HORIZONS),
        "schema": {
            "treemap": "latest-month cross section, one object per leaf item: item_code, item_name, "
                       "source (sa|nsa12), weight (Dec relative importance, % of CPI-U), yoy (NSA "
                       "12-month % change), and rho/halflife/pctile/lp12 for universe raw and relative",
            "series": "one object per scheme: official_replica, sticky_cpi, flexible_cpi, "
                      "*_binary (hard median split), *_pooled (no within-source normalisation). "
                      "idx = December-chained Laspeyres level on the published SA0 NSA scale; "
                      "yoy = 12-month % change, calendar-aligned",
            "atlanta_fed": "FRED STICKCPIM159/FLEXCPIM159 (12-month % change) and 157 (1-month), "
                           "plus a last-12-month comparison of 12-month LOG differences and the "
                           "correlation over the whole overlap",
            "summary": "buckets = % of covered leaf weight by half-life (raw universe); "
                       "spearman_raw_vs_relative = rank correlation of the two half-life columns "
                       "at the latest month; nsa12_null = what the nsa12 filter yields from white "
                       "noise; nsa12_robustness = rank correlation against a month-of-year demeaned "
                       "NSA MoM alternative; coverage = % of leaf weight estimated each month",
            "units": "rho, ar3sum, lp* are dimensionless regression coefficients; halflife is in "
                     "months; weight, yoy, idx-derived rates are percent",
        },
        "treemap": tm,
        "series": {k: ser(v) for k, v in series.items()},
        "classification": cls_diag,
        "atlanta_fed": af_block,
        "summary": {
            "buckets": bk,
            "spearman_raw_vs_relative": {"rho": None if sp_rho is None else round(sp_rho, 4), "n": sp_n,
                                         "sa_only_rho": None if sp_sa is None else round(sp_sa, 4),
                                         "sa_only_n": sp_sa_n},
            "stickiest": slim(stickiest), "most_flexible": slim(flexible),
            "stickiest_nsa12": slim(stickiest_n12), "most_flexible_nsa12": slim(flexible_n12),
            "league_table_note": "stickiest / most_flexible cover source='sa' only "
                                 f"({rk_sa.weight.sum():.1f}% of the basket). The *_nsa12 lists are "
                                 "kept apart on purpose: their filter inflates half-lives, so the two "
                                 "groups must never be ranked against each other.",
            "scheme_composition": comp,
            "coverage": {"ym": [c[0] for c in cov_rows], "pct": [c[1] for c in cov_rows],
                         "n_items": [c[2] for c in cov_rows]},
            "nsa12_null": null,
            "nsa12_robustness": {"spearman": None if rob_rho is None else round(rob_rho, 4), "n": rob_n,
                                 "note": "half-life from the 12-month-MA filter vs half-life from "
                                         "month-of-year demeaned NSA MoM, NSA-only items, latest window"},
            "source_shares": {s: round(float(g.weight.sum()), 3) for s, g in tmdf.groupby("source")},
        },
        "notes": [
            "Descriptive statistics of published BLS index series. Persistence here is serial "
            "correlation in a sample, not a claim about price-setting behaviour or causation.",
            "Univariate persistence confounds an item's own persistence with persistence in the "
            "common shocks hitting every item; universe='relative' (item rate minus headline) is "
            "the check, and both are published.",
            "Items with no published SA series use 100*(ln P_t - ln P_t-12)/12, a 12-month moving "
            f"average that manufactures rho ~ {null['analytic_rho']} and a half-life of about "
            f"{null['analytic_halflife']} months out of pure noise. All rankings, normalisations and "
            "buckets are computed within source group; never compare an sa item with an nsa12 item.",
            "Rolling AR(1) rho on 120 observations has a standard error of roughly 0.09, so "
            "neighbouring half-lives are usually not distinguishable. lp12_se is the published "
            "uncertainty number.",
            "October 2025 has no CPI (shutdown). All lags are calendar-aligned, so that month is a "
            "hole in every window rather than a row shift.",
            "The Atlanta Fed sticky-price CPI classifies by frequency of price change (Bils-Klenow) "
            "on an SA basis; P3 classifies by time-series persistence on the published NSA indexes. "
            "The two disagree by construction and the comparison is a sanity band only.",
            "The sticky/flexible classification for the months of year Y+1 uses the window ending in "
            "December of year Y, so it never uses data from the months it is applied to.",
        ],
    }
    # allow_nan=False: emit strict JSON (browsers reject NaN/Infinity). Fail loudly if any
    # non-finite value slips through instead of writing a file that JSON.parse cannot read.
    (OUT / "p3_persistence.json").write_text(json.dumps(out, indent=1, allow_nan=False))
    log.info("wrote %s (%d KB)", OUT / "p3_persistence.json",
             (OUT / "p3_persistence.json").stat().st_size // 1024)
    return 0 if ok_all else 2


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)
    kw = {}
    for a in sys.argv[1:]:
        if a.startswith("--since"):
            kw["since"] = a.split("=")[1]
        elif a == "--quarterly":
            kw["quarterly"] = True
        elif a == "--no-fred":
            kw["do_fred"] = False
    sys.exit(main(**kw))
