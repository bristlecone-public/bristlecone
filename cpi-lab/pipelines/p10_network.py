#!/usr/bin/env python3
"""P10 - lead-lag network among CPI items (Tier 1, descriptive; explicitly NOT causal).

  p10_network.py [--since=YYYY-MM] [--universe=hybrid|fine|coarse] [--rho-min=0.25]
                 [--fdr=0.05] [--min-windows=3] [--max-lag=12] [--granger-lags=6]
                 [--factor-lags=0] [--no-loo]

Every month ~180 published CPI item indexes move in different directions.  P10 asks a
narrow, purely statistical question about that panel: **when one item's seasonally
adjusted monthly rate moves, does another item's rate tend to move a few months later?**
It draws the answer as a directed graph.

This is a *lead-lag correlation map*.  It is not pass-through, it is not causal, and an
arrow i -> j does not mean i's prices feed into j's costs.  Two items can lead/lag each
other because they share a common driver, because BLS collects them on staggered
schedules, because one is smoothed and the other is not, or by chance.  The whole design
below - multiple-comparison control, four overlapping windows, sign/lag stability,
common-factor removal - exists only to keep the picture from being a swamp of spurious
edges; it does not upgrade correlation into causation.

A word on what "controls" the graph: the per-window screen is a *disjunction* -
a pair is kept if |rho| > 0.25 OR its Granger FDR q < 0.05 - so most displayed edges
qualify on correlation strength alone and have NOT passed the FDR test.  The primary
false-positive control is the cross-window stability rule, not FDR.  Per-edge q is
reported next to rho precisely so you can see which edges are also Granger-significant;
many are not (e.g. rent -> OER, rho 0.80, q 0.78).  Do not describe this as an
"FDR-controlled network".

--------------------------------------------------------------------------------
UNIVERSE  (--universe, default `hybrid`)
--------------------------------------------------------------------------------
Nodes are *mid-level published items* under the eight CPI major groups
(SAF food & beverages, SAH housing, SAA apparel, SAT transportation, SAM medical care,
SAR recreation, SAE education & communication, SAG other goods & services), taken from
`cu_item` display levels 2 and 3, restricted to items with a seasonally adjusted index.

A node must have `mom_sa` for >= 80% of the months in the analysis window and data
through 2026-01 or later.  The three selection rules produce a **non-overlapping** set -
no node is an ancestor of another - so no edge is a mechanical parent/child identity:

  coarse  every usable display-level-2 item; descend to level 3 only where the level-2
          item has no usable SA series.                                   (53 nodes)
  hybrid  `coarse`, then split a node into its usable level-3 children **only when those
          children reproduce >= 90% of the parent's relative importance**, so the split
          never silently drops part of the parent.                        (74 nodes, DEFAULT)
  fine    finest available among levels 2-3 (level 3 wherever it exists). Gives 84 nodes
          but only ~80% of the basket, because many level-2 items have a single small
          published level-3 child (and 9 of them have no relative importance at all).

`hybrid` is the default: 74 nodes covering ~89% of the CPI-U basket, with rent, OER,
gasoline, energy services, food-away-from-home and airline fares all present as their own
nodes.  It is 74 rather than the ~100 a finer cut would give because being *exhaustive*
(the nodes nearly tile the basket) matters more for reading a network than node count,
and because aggregating to expenditure-class level also raises the signal-to-noise of
each series - a graph of noisier leaves is a graph of more spurious edges.

Series: `cpi_item_month.mom_sa` (seasonally adjusted 1-month percent change) from --since
(default 2000-01).  Panel is reindexed to a complete monthly calendar so that a k-row
shift IS a k-calendar-month lag (2025-10 has no CPI; row-offset lags would silently
mis-align across it).  A month is dropped entirely if items covering < 60% of the
universe's weight have a value - this removes 2025-10 (no CPI) and 2025-11 (MoM
undefined), exactly as P2's coverage gate does.

--------------------------------------------------------------------------------
VARIANTS
--------------------------------------------------------------------------------
raw              each series demeaned over the estimation window.
common_removed   each series regressed on headline SA MoM over the estimation window; the
                 residual is used.  **This is the main variant.**  Without it the graph is
                 an energy graph: gasoline moves the aggregate, the aggregate is inside
                 every series, and everything lights up around motor fuel.

                 The headline is taken **leave-one-out** - for item i,
                     h_{-i,t} = (h_t - w_it x_it / 100) / (1 - w_it / 100)
                 with w_it the item's relative importance that month (`cpi_item_month.
                 weight`; weights exist from 2018 and are back-filled before that).  This
                 is not cosmetic and it is the single most consequential choice in P10.
                 Gasoline's SA MoM has sd 5.70 against the headline's 0.30, and most of
                 cov(gasoline, headline) is gasoline regressing on *itself* through its own
                 2.9% weight: its coefficient on the raw headline is **+16.4**, so the
                 residual becomes essentially -16.4 x headline.  Every sticky service item
                 is positively correlated with the lagged headline, so the raw-headline
                 version hands gasoline a **flat** rho = -0.4..-0.5 arrow into rent, food
                 away from home and vehicle maintenance **at every lag 1..12** - the
                 signature of a level artifact, not of a lead-lag relation.

                 Leaving the item out fixes it almost exactly, and costs nothing real:

                   pairs |rho_best| > 0.25          181 -> 170
                   energy items as source            12 ->   3
                   gasoline -> rent            -0.51 @4 -> -0.24 @4   (artifact)
                   gasoline -> vehicle maint.  -0.36 @4 -> -0.18 @4   (artifact)
                   rent -> OER                 +0.796   -> +0.797     (kept)
                   other food at home -> food away  +0.416 -> +0.427  (kept)
                   used cars -> new vehicles        +0.291 -> +0.315  (kept)

                 `--no-loo` reproduces the plain-headline version, and `--factor-lags=K`
                 additionally projects off h_{-i,t-1..t-K}, which removes the remaining
                 energy artifacts at the cost of attenuating real edges by ~30% (K=6) and
                 ~40% (K=12).  Default is K=0: leave-one-out alone does the job.

                 Residual caveat: three weak negative gasoline/energy edges survive the
                 |rho| > 0.25 screen even after leave-one-out.  Each stable edge therefore
                 carries `rho_other`, the same pair and lag in the other variant, so an
                 edge created by the factor step is visible as such.

--------------------------------------------------------------------------------
STATISTICS  (per ordered pair i -> j, per variant, per window)
--------------------------------------------------------------------------------
1. Cross-correlation  rho_k = corr(x_i,t-k , x_j,t)  for k = 1..12, pairwise-complete,
   computed in closed form as 6 matrix products per lag (no per-pair loop).
   best lag = argmax_k |rho_k|;  rho = rho at the best lag.
2. Granger-style F test: regress x_j,t on a constant + its own lags 1..6 + x_i lags 1..6,
   and Wald-test the six x_i coefficients jointly, with a Newey-West HAC covariance
   (Bartlett kernel, L = floor(4 (n/100)^(2/9)), small-sample factor n/(n-k)).
   Implemented as batched numpy (one (N, T, 13) design tensor per source), not per-pair
   statsmodels - 5,256 ordered pairs x 5 windows x 2 variants is 52,560 regressions.
   F ~ F(6, n-13).  Pairs with fewer than 60 usable observations are not tested.
3. Multiple comparisons: Benjamini-Hochberg FDR over all tested ordered pairs, applied
   **within each variant and window** (that is the family: every pair is tested once).

--------------------------------------------------------------------------------
STABILITY FILTER
--------------------------------------------------------------------------------
Everything is recomputed on four overlapping ~15-year windows
  2000-01..2014-12, 2004-01..2018-12, 2008-01..2022-12, 2011-01..latest
and on the full sample (--since..latest, which is what the reported rho / q / best lag
refer to).  A pair *passes* a window if  |rho_best| > 0.25  OR  FDR q < 0.05  there.
An edge is **stable** iff it passes in >= 3 of the 4 windows AND, across the passing
windows, the sign of rho is identical AND every best lag is within +/-2 months of their
median.  Windows are demeaned / residualised separately; lags are taken inside the window
slab, so each window loses its first 12 months of dependent-variable observations.

--------------------------------------------------------------------------------
TABLES
--------------------------------------------------------------------------------
p10_edges(variant, src, dst, best_lag, rho, fdr_q, n_windows_pass, stable)
    ALL ordered pairs (N*(N-1) per variant), so the filtering-stage counts are
    reproducible from SQL.  best_lag/rho/fdr_q are full-sample; n_windows_pass and stable
    come from the four windows.  `stable = 1` is the graph.
p10_nodes(variant, item_code, name, weight, in_deg, out_deg, upstreamness)
    in_deg/out_deg = count of stable edges into/out of the node;
    upstreamness = sum |rho| over stable out-edges - sum |rho| over stable in-edges.
    Positive = the node tends to move before its neighbours in this map.
p10_lagprofile(variant, src, dst, lag, rho)
    full-sample rho at every lag 1..12, for the stable edges only.
p10_meta(key, value)  run parameters and stage counts, JSON-encoded values.

--------------------------------------------------------------------------------
out/p10_network.json
--------------------------------------------------------------------------------
{ "generated_at", "latest_month", "since", "caveat",
  "params":   {"rho_min","fdr","min_windows","max_lag","granger_lags","min_obs",
               "universe","month_coverage_min"},
  "windows":  [{"name","start","end","n_months"}],            # 4 windows + "full"
  "groups":   {"SAF": {"name","color"}, ...},                 # 8 major groups
  "universe": {"rule","n_nodes","weight_covered","weight_year"},
  "variants": { "<variant>": {
      "nodes":  [{"code","name","major","color","weight","in_deg","out_deg","upstreamness"}],
      "edges":  [{"src","dst","lag","rho","q","n_windows_pass"}],      # stable only
      "stages": {"pairs","tested","rho_screen","fdr_pass","screen_any","stable",
                 "per_window":{"<win>":{"tested","rho_screen","fdr_pass","screen_any"}}},
      "top_edges": [ ... 15 strongest stable edges ... ],
      "cascade":  {"<code>": {"l1":[{"dst","lag","rho"}], "l2":[{"via","dst","lag","cum_lag","rho"}]}},
      "lagprofile": {"<src>|<dst>": [rho_1 .. rho_12]} } },            # stable edges
  "sanity":  [{"name","src","dst","variant","lag","rho","q","stable","found"}],
  "notes":   [ ... ] }

Exit code 0 normally; 2 if a stability/sanity expectation fails badly enough to be worth
a look (the tables and JSON are still written).
"""
import sys, json, warnings
import numpy as np, pandas as pd
from scipy import stats
from common import *

warnings.filterwarnings("ignore", category=RuntimeWarning)   # all-NaN slices are expected here

SCHEMA10 = """
CREATE TABLE IF NOT EXISTS p10_edges(variant TEXT, src TEXT, dst TEXT, best_lag INT, rho REAL,
  fdr_q REAL, n_windows_pass INT, stable INT, PRIMARY KEY(variant, src, dst));
CREATE INDEX IF NOT EXISTS p10_edges_stable ON p10_edges(variant, stable);
CREATE TABLE IF NOT EXISTS p10_nodes(variant TEXT, item_code TEXT, name TEXT, weight REAL,
  in_deg INT, out_deg INT, upstreamness REAL, PRIMARY KEY(variant, item_code));
CREATE TABLE IF NOT EXISTS p10_lagprofile(variant TEXT, src TEXT, dst TEXT, lag INT, rho REAL,
  PRIMARY KEY(variant, src, dst, lag));
CREATE TABLE IF NOT EXISTS p10_meta(key TEXT PRIMARY KEY, value TEXT);
"""

MAJORS = {
    "SAF": ("Food and beverages", "#e07b39"),
    "SAH": ("Housing", "#3b7dd8"),
    "SAA": ("Apparel", "#c94f7c"),
    "SAT": ("Transportation", "#2f9e6b"),
    "SAM": ("Medical care", "#8b5cf6"),
    "SAR": ("Recreation", "#0ea5b7"),
    "SAE": ("Education and communication", "#eab308"),
    "SAG": ("Other goods and services", "#64748b"),
}
VARIANTS = ["raw", "common_removed"]
MIN_NODE_COV = 0.80      # share of months a node needs, in the full sample and per window
MONTH_COVW = 0.60        # share of universe weight that must have a value for a month to count
MIN_OBS = 60             # minimum usable observations for a correlation / F test
SPLIT_FRAC = 0.90        # `hybrid`: split a node only if its children hold >= this of its weight
CASCADE_TOP = 6          # edges kept per cascade level in the JSON

# expectations that should show up if the method works at all (see docs/P10.md)
SANITY = [
    ("gasoline -> airline fares", "SETB01", "SETG01"),
    ("fuel oil and other fuels -> airline fares", "SEHE", "SETG01"),
    ("fuel oil and other fuels -> gasoline", "SEHE", "SETB01"),
    ("gasoline -> motor vehicle maintenance", "SETB01", "SETD"),
    ("energy services -> owners' equivalent rent", "SEHF", "SEHC01"),
    ("cereals and bakery -> food away from home", "SAF111", "SEFV"),
    ("meats/poultry/fish/eggs -> food away from home", "SAF112", "SEFV"),
    ("other food at home -> food away from home", "SAF115", "SEFV"),
    ("rent -> owners' equivalent rent", "SEHA", "SEHC01"),
    ("owners' equivalent rent -> rent", "SEHC01", "SEHA"),
]


# ---------------------------------------------------------------- universe
def pick_universe(con, rule, since, last):
    items = pd.read_sql("SELECT item_code,item_name,display_level,sort_sequence,parent_code FROM cu_item", con)
    par = dict(zip(items.item_code, items.parent_code))
    lvl = dict(zip(items.item_code, items.display_level))
    name = dict(zip(items.item_code, items.item_name))
    seq = dict(zip(items.item_code, items.sort_sequence))

    def ancestors(c):
        out, p = [], par.get(c)
        while p:
            out.append(p)
            p = par.get(p)
        return out

    major = {c: (c if c in MAJORS else next((a for a in ancestors(c) if a in MAJORS), None))
             for c in items.item_code}

    im = pd.read_sql("SELECT item_code, ym, mom_sa FROM cpi_item_month WHERE mom_sa IS NOT NULL", con)
    im = im[(im.ym >= since) & (im.ym <= last)]
    months = [str(p) for p in pd.period_range(since, last, freq="M")]
    cnt = im.groupby("item_code").size()
    lastm = im.groupby("item_code").ym.max()
    cov = {c: cnt.get(c, 0) / len(months) for c in items.item_code}
    usable = {c: (cov[c] >= MIN_NODE_COV and str(lastm.get(c, "")) >= "2026-01") for c in items.item_code}

    # weight = most recent non-null relative importance available for the code
    w = pd.read_sql("SELECT weight_year,item_code,weight_u FROM cpi_weight WHERE matched=1", con)
    w = w.sort_values("weight_year").drop_duplicates("item_code", keep="last")
    wm = dict(zip(w.item_code, w.weight_u))
    wyear = int(w.weight_year.max())

    kids = {}
    for c, p in par.items():
        kids.setdefault(p, []).append(c)

    # coarse: level 2 preferred, descend to 3 only where level 2 is unusable
    coarse = []
    for c in items.item_code:
        if major[c] is None or c in MAJORS:
            continue
        if lvl[c] == 2 and usable[c]:
            coarse.append(c)
        elif lvl[c] == 3 and usable[c] and not usable.get(par.get(c), False):
            coarse.append(c)
    sc = set(coarse)
    coarse = [c for c in coarse if par.get(c) not in sc]

    if rule == "coarse":
        sel = coarse
    elif rule == "fine":
        cand = [c for c in items.item_code
                if major[c] and c not in MAJORS and lvl[c] in (2, 3) and usable[c]]
        s = set(cand)
        sel = [c for c in cand if not any(par.get(k) == c for k in s)]
    elif rule == "hybrid":
        sel = []
        for c in coarse:
            ch = [k for k in kids.get(c, []) if lvl.get(k) == 3 and usable[k]]
            pw, cw = wm.get(c), sum(wm.get(k, 0.0) for k in ch)
            if ch and pw and cw / pw >= SPLIT_FRAC:
                sel.extend(ch)
            else:
                sel.append(c)
    else:
        raise SystemExit(f"unknown --universe {rule}")

    sel = sorted(set(sel), key=lambda c: seq.get(c, 0))
    meta = pd.DataFrame({
        "item_code": sel,
        "name": [name[c] for c in sel],
        "major": [major[c] for c in sel],
        "level": [lvl[c] for c in sel],
        "weight": [wm.get(c, float("nan")) for c in sel],
        "cov": [round(cov[c], 3) for c in sel],
    })
    log.info("universe '%s': %d nodes, %d majors, %s weight sum %.1f%% of CPI-U (%d nodes without a weight)",
             rule, len(meta), meta.major.nunique(), wyear, meta.weight.sum(), int(meta.weight.isna().sum()))
    for g, n in meta.groupby("major").size().items():
        log.info("   %-4s %-30s %2d nodes, weight %5.1f%%", g, MAJORS[g][0], n,
                 meta[meta.major == g].weight.sum())
    return meta, wyear


def build_panel(con, meta, since, last, flags):
    """(T x N) calendar-complete matrix of mom_sa, plus the (T x flags+1) design matrix of
    headline SA MoM at lags 0..flags used for common-factor removal."""
    codes = list(meta.item_code)
    q = "SELECT item_code, ym, mom_sa FROM cpi_item_month WHERE mom_sa IS NOT NULL AND item_code IN (%s)" \
        % ",".join("?" * len(codes))
    d = pd.read_sql(q, con, params=codes)
    d = d[(d.ym >= since) & (d.ym <= last)]
    idx = [str(p) for p in pd.period_range(since, last, freq="M")]
    X = d.pivot(index="ym", columns="item_code", values="mom_sa").reindex(index=idx, columns=codes)

    wv = meta.weight.fillna(0.0).to_numpy(float)
    covw = (X.notna().to_numpy(float) * wv).sum(1) / wv.sum()
    thin = [m for m, c in zip(idx, covw) if c < MONTH_COVW]
    if thin:
        log.info("dropping %d months with node-weight coverage < %.0f%%: %s",
                 len(thin), 100 * MONTH_COVW, thin)
        X.loc[thin] = np.nan

    # headline reaches `flags` months before `since` so the first window keeps every row
    hidx = [str(p) for p in pd.period_range(str(pd.Period(since, "M") - max(flags, 1)), last, freq="M")]
    h = pd.read_sql("SELECT ym, mom_sa FROM cpi_item_month WHERE item_code='SA0'", con)
    h = h.set_index("ym").mom_sa.reindex(hidx).astype(float)
    h[[m for m in thin if m in h.index]] = np.nan
    hc = h - h.mean()                      # centred, so "missing" == "no shock information"
    nmiss = int(hc.isna().sum())
    H = np.column_stack([hc.reindex([str(pd.Period(m, "M") - k) for m in idx]).to_numpy(float)
                         for k in range(flags + 1)])
    H = np.nan_to_num(H)                   # gap months (2025-10/11) -> the sample mean

    # per-month relative importance of each node, for the leave-one-out headline. Weight
    # vintages only start in Dec-2017, so earlier months reuse the oldest available one.
    wq = "SELECT item_code, ym, weight FROM cpi_item_month WHERE weight IS NOT NULL AND item_code IN (%s)" \
         % ",".join("?" * len(codes))
    W = pd.read_sql(wq, con, params=codes).pivot(index="ym", columns="item_code", values="weight")
    W = W.reindex(index=idx, columns=codes).ffill().bfill()
    W = np.nan_to_num(W.to_numpy(float))
    log.info("panel %s..%s: %d calendar months, %d nodes, %d/%d cells present; headline design "
             "%d lag(s), %d gap month(s) mean-imputed; node weights %.2f..%.2f%% (mean %.2f%%)",
             idx[0], idx[-1], len(idx), X.shape[1], int(X.notna().sum().sum()), X.size,
             flags, nmiss, W[W > 0].min(), W.max(), W[W > 0].mean())
    return X, H, W, idx


# ---------------------------------------------------------------- transforms
def shift_rows(A, k):
    out = np.full_like(A, np.nan)
    if k:
        out[k:] = A[:-k]
    else:
        out[:] = A
    return out


def prepare(A, H, W, variant, loo=True):
    """Demean (raw), or project off [1, h_{-j,t} .. h_{-j,t-flags}] (common_removed),
    fitted within this window slab.  h_{-j} is the headline with node j's own contribution
    removed and rescaled; see the module docstring for why that matters."""
    A = A.astype(float).copy()
    if variant == "raw":
        return A - np.nanmean(A, axis=0, keepdims=True)
    T = len(H)
    one = np.ones((T, 1))
    R = np.full_like(A, np.nan)
    for j in range(A.shape[1]):
        m = np.isfinite(A[:, j])
        if m.sum() < MIN_OBS:
            continue
        if loo:
            # h_{-j} at every lag: subtract j's own contribution from the same-dated headline
            xj = np.nan_to_num(A[:, j])
            share = W[:, j] / 100.0
            Hj = np.column_stack([(H[:, k] - shift_rows(share[:, None] * xj[:, None], k)[:, 0])
                                  / np.maximum(1.0 - shift_rows(share[:, None], k)[:, 0], 1e-6)
                                  for k in range(H.shape[1])])
            Hj = np.nan_to_num(Hj)
            Hj = Hj - Hj[m].mean(axis=0, keepdims=True)
        else:
            Hj = H
        Z = np.column_stack([one, Hj])
        b, *_ = np.linalg.lstsq(Z[m], A[m, j], rcond=None)
        R[m, j] = A[m, j] - Z[m] @ b
    return R


# ---------------------------------------------------------------- cross-correlation
def xcorr(A, max_lag):
    """rho[k][i, j] = corr(x_i,t-k , x_j,t), pairwise-complete, closed form."""
    M = np.isfinite(A)
    Z = np.where(M, A, 0.0)
    Mf = M.astype(float)
    Z2 = Z * Z
    out = np.full((max_lag, A.shape[1], A.shape[1]), np.nan)
    nout = np.zeros_like(out)
    for k in range(1, max_lag + 1):
        Zq, Mq, Q2 = shift_rows(Z, k), shift_rows(Mf, k), shift_rows(Z2, k)
        Zq = np.nan_to_num(Zq); Mq = np.nan_to_num(Mq); Q2 = np.nan_to_num(Q2)
        n = Mq.T @ Mf
        Si, Sj = Zq.T @ Mf, Mq.T @ Z
        Sii, Sjj = Q2.T @ Mf, Mq.T @ Z2
        Sij = Zq.T @ Z
        num = n * Sij - Si * Sj
        den = np.sqrt(np.clip(n * Sii - Si ** 2, 0, None) * np.clip(n * Sjj - Sj ** 2, 0, None))
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.where((den > 0) & (n >= MIN_OBS), num / den, np.nan)
        out[k - 1], nout[k - 1] = r, n
    return out, nout


def best_lag(rho):
    """argmax_k |rho_k| over the lag axis; returns (lag 1-based, rho at that lag)."""
    a = np.abs(rho)
    a = np.where(np.isfinite(a), a, -1.0)
    k = a.argmax(axis=0)
    r = np.take_along_axis(rho, k[None], axis=0)[0]
    return (k + 1).astype(int), r


# ---------------------------------------------------------------- Granger (batched, HAC)
def granger(A, p=6):
    """F and p-value for 'x_i lags 1..p add to a model of x_j on its own lags 1..p',
    Newey-West HAC.  Batched over j for each source i.  Returns (F, pval, n) (N x N)."""
    T, N = A.shape
    k = 1 + 2 * p
    Lg = np.stack([shift_rows(A, q) for q in range(1, p + 1)], axis=-1)   # (T, N, p)
    y_all = A.T                                                          # (N, T)
    Yl = np.transpose(Lg, (1, 0, 2))                                     # (N, T, p)
    ones = np.ones((N, T, 1))
    F = np.full((N, N), np.nan)
    P = np.full((N, N), np.nan)
    NN = np.zeros((N, N))
    for i in range(N):
        Xi = np.broadcast_to(Lg[:, i, :], (N, T, p))
        Z = np.concatenate([ones, Yl, Xi], axis=2)                       # (N, T, k)
        m = np.isfinite(y_all) & np.isfinite(Z).all(axis=2)
        m[i] = False                                                     # skip i -> i
        n = m.sum(1)
        mf = m.astype(float)
        Zf = np.nan_to_num(Z) * mf[:, :, None]
        yf = np.nan_to_num(y_all) * mf
        XtX = np.transpose(Zf, (0, 2, 1)) @ Zf
        Xty = (np.transpose(Zf, (0, 2, 1)) @ yf[:, :, None])[:, :, 0]
        XtXi = np.linalg.pinv(XtX)
        b = (XtXi @ Xty[:, :, None])[:, :, 0]
        u = (yf - (Zf @ b[:, :, None])[:, :, 0]) * mf
        g = u[:, :, None] * Zf                                           # (N, T, k)
        L = max(1, int(np.floor(4 * (np.nanmax(n) / 100.0) ** (2 / 9))) if n.max() > 0 else 1)
        S = np.transpose(g, (0, 2, 1)) @ g
        for l in range(1, L + 1):
            G = np.transpose(g[:, l:, :], (0, 2, 1)) @ g[:, :-l, :]
            S = S + (1.0 - l / (L + 1.0)) * (G + np.transpose(G, (0, 2, 1)))
        corr = np.where(n > k, n / np.maximum(n - k, 1), 1.0)[:, None, None]   # small-sample factor
        V = XtXi @ (S * corr) @ XtXi
        Rb = b[:, 1 + p:]
        RVR = V[:, 1 + p:, 1 + p:]
        W = np.einsum("ja,jab,jb->j", Rb, np.linalg.pinv(RVR), Rb)
        df2 = n - k
        ok = (n >= MIN_OBS) & (df2 > 0) & np.isfinite(W) & (W >= 0)
        f = np.where(ok, W / p, np.nan)
        F[i] = f
        NN[i] = n
        with np.errstate(invalid="ignore"):
            P[i] = np.where(ok, stats.f.sf(np.where(ok, f, 1.0), p, np.maximum(df2, 1)), np.nan)
    return F, P, NN


def bh_fdr(p):
    """Benjamini-Hochberg q-values over the finite entries of an array (same shape out)."""
    q = np.full(p.shape, np.nan)
    f = np.isfinite(p)
    v = p[f]
    if v.size == 0:
        return q
    o = np.argsort(v, kind="stable")
    m = v.size
    adj = v[o] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[o] = np.clip(adj, 0.0, 1.0)
    q[f] = out
    return q


# ---------------------------------------------------------------- one window
def window_stats(A, H, W, variant, max_lag, glags, loo=True):
    R = prepare(A, H, W, variant, loo)
    rho, n = xcorr(R, max_lag)
    for k in range(rho.shape[0]):                       # i -> i is autocorrelation, not an edge
        np.fill_diagonal(rho[k], np.nan)
    lag, r = best_lag(rho)
    _, pv, gn = granger(R, glags)                       # granger already skips i -> i
    q = bh_fdr(pv)
    tested = np.isfinite(r) | np.isfinite(q)
    np.fill_diagonal(tested, False)
    return {"rho_all": rho, "lag": lag, "rho": r, "q": q, "p": pv, "n": n, "gn": gn, "tested": tested}


def screen(w, rho_min, fdr):
    s = ((np.abs(w["rho"]) > rho_min) & np.isfinite(w["rho"])) | ((w["q"] < fdr) & np.isfinite(w["q"]))
    s = s & w["tested"]
    np.fill_diagonal(s, False)
    return s


# ---------------------------------------------------------------- main
def main(since="2000-01", rule="hybrid", rho_min=0.25, fdr=0.05, min_windows=3,
         max_lag=12, glags=6, flags=0, loo=True):
    con = init_db()
    con.executescript(SCHEMA10)
    con.commit()
    last = con.execute("SELECT MAX(ym) FROM cpi_item_month WHERE mom_sa IS NOT NULL").fetchone()[0]
    meta, wyear = pick_universe(con, rule, since, last)
    X, H, Wm, idx = build_panel(con, meta, since, last, flags)
    codes = list(meta.item_code)
    names = dict(zip(meta.item_code, meta.name))
    majors = dict(zip(meta.item_code, meta.major))
    weights = dict(zip(meta.item_code, meta.weight))
    N = len(codes)
    pos = {m: i for i, m in enumerate(idx)}

    wins = [("w1", "2000-01", "2014-12"), ("w2", "2004-01", "2018-12"),
            ("w3", "2008-01", "2022-12"), ("w4", "2011-01", last)]
    wins = [(nm, max(a, since), b) for nm, a, b in wins if b > since]
    Aall = X.to_numpy(float)

    def slab(a, b):
        i0, i1 = pos.get(a, 0), pos.get(b, len(idx) - 1)
        return Aall[i0:i1 + 1], H[i0:i1 + 1], Wm[i0:i1 + 1], i1 - i0 + 1

    stages_all, edges_all, nodes_all, lagprof_all, sanity_rows = {}, {}, {}, {}, []
    json_variants = {}
    ok_all = True

    A0, H0, W0, _ = slab(since, last)
    full_by = {v: window_stats(A0, H0, W0, v, max_lag, glags, loo) for v in VARIANTS}

    for variant in VARIANTS:
        log.info("=== variant %s ===", variant)
        full = full_by[variant]
        other = full_by["raw" if variant == "common_removed" else "common_removed"]
        full_screen = screen(full, rho_min, fdr)

        per_window, passes, signs, lags = {}, [], [], []
        for nm, a, b in wins:
            Aw, Hw, Ww, nmth = slab(a, b)
            # a node needs MIN_NODE_COV of the window's months, else it sits this one out
            cov = np.isfinite(Aw).mean(axis=0)
            Aw = np.where(cov[None, :] >= MIN_NODE_COV, Aw, np.nan)
            w = window_stats(Aw, Hw, Ww, variant, max_lag, glags, loo)
            s = screen(w, rho_min, fdr)
            passes.append(s)
            signs.append(np.sign(w["rho"]))
            lags.append(w["lag"].astype(float))
            per_window[nm] = {
                "start": a, "end": b, "n_months": int(nmth), "n_nodes": int((cov >= MIN_NODE_COV).sum()),
                "tested": int(w["tested"].sum()),
                "rho_screen": int((np.abs(w["rho"]) > rho_min).sum()),
                "fdr_pass": int((w["q"] < fdr).sum()),
                "screen_any": int(s.sum()),
            }
            log.info("  %s %s..%s (%d months, %d nodes): tested %d, |rho|>%.2f %d, q<%.2f %d, either %d",
                     nm, a, b, nmth, per_window[nm]["n_nodes"], per_window[nm]["tested"],
                     rho_min, per_window[nm]["rho_screen"], fdr, per_window[nm]["fdr_pass"],
                     per_window[nm]["screen_any"])

        Pmask = np.stack(passes)                      # (W, N, N)
        Sg = np.where(Pmask, np.stack(signs), np.nan)
        Lg_ = np.where(Pmask, np.stack(lags), np.nan)
        npass = Pmask.sum(0)
        with np.errstate(invalid="ignore"):
            sign_ok = np.nanmax(Sg, axis=0) == np.nanmin(Sg, axis=0)      # NaN == NaN is False
            med = np.nanmedian(Lg_, axis=0)
            lag_ok = np.nanmax(np.abs(Lg_ - med[None]), axis=0) <= 2
        stable = (npass >= min_windows) & sign_ok & lag_ok
        np.fill_diagonal(stable, False)

        stages = {
            "pairs": N * (N - 1),
            "tested": int(full["tested"].sum()),
            "rho_screen": int((np.abs(full["rho"]) > rho_min).sum()),
            "fdr_pass": int((full["q"] < fdr).sum()),
            "screen_any": int(full_screen.sum()),
            "stable": int(stable.sum()),
            "stable_and_full_screen": int((stable & full_screen).sum()),
            "per_window": per_window,
        }
        log.info("  FULL %s..%s: pairs %d -> tested %d -> |rho|>%.2f %d / FDR q<%.2f %d "
                 "-> either %d -> STABLE (>=%d of %d windows, same sign, lag +/-2) %d",
                 since, last, stages["pairs"], stages["tested"], rho_min, stages["rho_screen"],
                 fdr, stages["fdr_pass"], stages["screen_any"], min_windows, len(wins), stages["stable"])

        # ---- tables
        ii, jj = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
        off = ii != jj
        erows = []
        for i, j in zip(ii[off], jj[off]):
            r, qv = full["rho"][i, j], full["q"][i, j]
            erows.append((variant, codes[i], codes[j], int(full["lag"][i, j]),
                          None if not np.isfinite(r) else round(float(r), 5),
                          None if not np.isfinite(qv) else round(float(qv), 6),
                          int(npass[i, j]), int(stable[i, j])))
        edges_all[variant] = erows

        si, sj = np.where(stable)
        rr = full["rho"][si, sj]
        order = np.argsort(-np.abs(np.where(np.isfinite(rr), rr, 0)))
        def _r(v):
            return None if not np.isfinite(v) else round(float(v), 4)

        # rho_other = the same (pair, lag) correlation in the other variant. A stable edge
        # whose rho_other is near zero or of the opposite sign exists only because of (or
        # only survives) the common-factor step - see docs/P10.md.
        stable_edges = [{"src": codes[si[t]], "dst": codes[sj[t]],
                         "lag": int(full["lag"][si[t], sj[t]]),
                         "rho": _r(full["rho"][si[t], sj[t]]),
                         "rho_other": _r(other["rho_all"][int(full["lag"][si[t], sj[t]]) - 1, si[t], sj[t]]),
                         "q": None if not np.isfinite(full["q"][si[t], sj[t]]) else round(float(full["q"][si[t], sj[t]]), 5),
                         "n_windows_pass": int(npass[si[t], sj[t]])} for t in order]

        absr = np.where(stable & np.isfinite(full["rho"]), np.abs(full["rho"]), 0.0)
        outd, ind = stable.sum(1), stable.sum(0)
        ups = absr.sum(1) - absr.sum(0)
        nrows = [(variant, codes[i], names[codes[i]],
                  None if not np.isfinite(weights.get(codes[i], np.nan)) else float(weights[codes[i]]),
                  int(ind[i]), int(outd[i]), round(float(ups[i]), 4)) for i in range(N)]
        nodes_all[variant] = nrows

        lrows = []
        for t in range(len(si)):
            i, j = si[t], sj[t]
            for k in range(max_lag):
                v = full["rho_all"][k, i, j]
                if np.isfinite(v):
                    lrows.append((variant, codes[i], codes[j], k + 1, round(float(v), 5)))
        lagprof_all[variant] = lrows

        # ---- cascade (BFS 2 levels over stable edges)
        adj = {}
        for e in stable_edges:
            adj.setdefault(e["src"], []).append(e)
        cascade = {}
        for c in codes:
            l1 = sorted(adj.get(c, []), key=lambda e: -abs(e["rho"] or 0))[:CASCADE_TOP]
            if not l1:
                continue
            seen = {c} | {e["dst"] for e in l1}
            l2 = []
            for e in l1:
                for f in sorted(adj.get(e["dst"], []), key=lambda x: -abs(x["rho"] or 0)):
                    if f["dst"] in seen:
                        continue
                    l2.append({"via": e["dst"], "dst": f["dst"], "lag": f["lag"],
                               "cum_lag": e["lag"] + f["lag"], "rho": f["rho"]})
                    if len(l2) >= CASCADE_TOP * 2:
                        break
            cascade[c] = {"l1": [{"dst": e["dst"], "lag": e["lag"], "rho": e["rho"]} for e in l1],
                          "l2": l2[:CASCADE_TOP * 2]}

        lp = {}
        for t in range(len(si)):
            i, j = si[t], sj[t]
            lp[f"{codes[i]}|{codes[j]}"] = [None if not np.isfinite(full["rho_all"][k, i, j])
                                            else round(float(full["rho_all"][k, i, j]), 4) for k in range(max_lag)]

        json_variants[variant] = {
            "nodes": [{"code": codes[i], "name": names[codes[i]], "major": majors[codes[i]],
                       "major_name": MAJORS[majors[codes[i]]][0], "color": MAJORS[majors[codes[i]]][1],
                       "weight": None if not np.isfinite(weights.get(codes[i], np.nan)) else round(float(weights[codes[i]]), 4),
                       "in_deg": int(ind[i]), "out_deg": int(outd[i]),
                       "upstreamness": round(float(ups[i]), 4)} for i in range(N)],
            "edges": stable_edges,
            "stages": stages,
            "top_edges": stable_edges[:15],
            "cascade": cascade,
            "lagprofile": lp,
        }
        stages_all[variant] = stages

        log.info("  top 15 stable edges (%s):", variant)
        for e in stable_edges[:15]:
            log.info("    %-9s %-32s -> %-9s %-32s lag %2d  rho %+.3f (other %+.3f)  q %s  (%d/%d windows)",
                     e["src"], names.get(e["src"], "")[:32], e["dst"], names.get(e["dst"], "")[:32],
                     e["lag"], e["rho"], e["rho_other"] if e["rho_other"] is not None else float("nan"),
                     "n/a" if e["q"] is None else f"{e['q']:.4f}", e["n_windows_pass"], len(wins))
        srcdeg = pd.Series([e["src"] for e in stable_edges]).value_counts()
        log.info("  most connected sources: %s",
                 [(c, int(v), names.get(c, "")[:22]) for c, v in srcdeg.head(6).items()])

        # ---- sanity expectations
        ci = {c: i for i, c in enumerate(codes)}
        for nm, s, d in SANITY:
            if s not in ci or d not in ci:
                sanity_rows.append({"name": nm, "src": s, "dst": d, "variant": variant, "found": False,
                                    "note": "not in universe"})
                continue
            i, j = ci[s], ci[d]
            sanity_rows.append({"name": nm, "src": s, "dst": d, "variant": variant,
                                "lag": int(full["lag"][i, j]),
                                "rho": None if not np.isfinite(full["rho"][i, j]) else round(float(full["rho"][i, j]), 4),
                                "q": None if not np.isfinite(full["q"][i, j]) else round(float(full["q"][i, j]), 5),
                                "n_windows_pass": int(npass[i, j]), "stable": bool(stable[i, j]), "found": True})

    # ---------------------------------------------------------- persist
    con.execute("DELETE FROM p10_edges")
    con.execute("DELETE FROM p10_nodes")
    con.execute("DELETE FROM p10_lagprofile")
    for v in VARIANTS:
        con.executemany("INSERT OR REPLACE INTO p10_edges VALUES(?,?,?,?,?,?,?,?)", edges_all[v])
        con.executemany("INSERT OR REPLACE INTO p10_nodes VALUES(?,?,?,?,?,?,?)", nodes_all[v])
        con.executemany("INSERT OR REPLACE INTO p10_lagprofile VALUES(?,?,?,?,?)", lagprof_all[v])
    params = {"since": since, "last": last, "universe": rule, "n_nodes": N, "rho_min": rho_min,
              "fdr": fdr, "min_windows": min_windows, "max_lag": max_lag, "granger_lags": glags,
              "factor_lags": flags, "leave_one_out_headline": bool(loo), "min_obs": MIN_OBS,
              "month_coverage_min": MONTH_COVW, "node_coverage_min": MIN_NODE_COV,
              "weight_year": wyear}
    con.executemany("INSERT OR REPLACE INTO p10_meta VALUES(?,?)",
                    [("params", json.dumps(params)), ("stages", json.dumps(stages_all)),
                     ("sanity", json.dumps(sanity_rows)),
                     ("run_at", pd.Timestamp.now("UTC").isoformat())])
    con.commit()
    log.info("p10_edges %d rows, p10_nodes %d rows, p10_lagprofile %d rows",
             sum(len(edges_all[v]) for v in VARIANTS), sum(len(nodes_all[v]) for v in VARIANTS),
             sum(len(lagprof_all[v]) for v in VARIANTS))

    now = pd.Timestamp.now("UTC").isoformat(timespec="seconds")
    for r in sanity_rows:
        if r["variant"] != "common_removed" or not r.get("found"):
            continue
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    (now, "p10_sanity_" + r["src"] + "_" + r["dst"], last,
                     r.get("rho"), None, None, int(bool(r.get("stable")))))
    con.commit()

    log.info("sanity expectations (edges the method should find if it works at all):")
    for v in VARIANTS:
        log.info("  --- %s ---", v)
        for r in sanity_rows:
            if r["variant"] != v:
                continue
            if not r.get("found"):
                log.info("    %-44s NOT IN UNIVERSE", r["name"])
                continue
            log.info("    %-44s lag %2d rho %+.3f q %s  %d/%d windows  %s", r["name"], r["lag"],
                     r["rho"] if r["rho"] is not None else float("nan"),
                     "n/a" if r["q"] is None else f"{r['q']:.4f}", r["n_windows_pass"], len(wins),
                     "STABLE" if r["stable"] else "not stable")
    hit = sum(1 for r in sanity_rows if r["variant"] == "common_removed" and r.get("stable"))
    if hit < 2:
        log.warning("only %d of %d sanity expectations are stable edges - check the method", hit, len(SANITY))
        ok_all = False

    out = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "latest_month": last,
        "since": since,
        "caveat": "lead-lag correlation, not pass-through, not causal",
        "params": params,
        "windows": [{"name": nm, "start": a, "end": b,
                     "n_months": len([m for m in idx if a <= m <= b])} for nm, a, b in wins]
                   + [{"name": "full", "start": since, "end": last, "n_months": len(idx)}],
        "groups": {g: {"name": v[0], "color": v[1]} for g, v in MAJORS.items()},
        "universe": {"rule": rule, "n_nodes": N,
                     "weight_covered": round(float(meta.weight.sum()), 2), "weight_year": wyear,
                     "levels": {str(k): int(v) for k, v in meta.level.value_counts().items()}},
        "variants": json_variants,
        "sanity": sanity_rows,
        "notes": [
            "lead-lag correlation, not pass-through, not causal. An arrow i -> j means the "
            "seasonally adjusted monthly rate of i moved before that of j, on average, over "
            "the sample. It does not mean i's prices feed into j's costs.",
            "Common drivers are the obvious alternative explanation: in the `raw` variant "
            "almost everything correlates with almost everything through the aggregate, which "
            "is why `common_removed` is the variant to read. There each series is regressed on "
            "the headline SA MoM *with its own contribution removed* (leave-one-out). Using the "
            "plain headline is not safe: gasoline is 2.9% of the basket but its monthly rate has "
            "19x the headline's standard deviation, so it largely regresses on itself, gets a "
            "coefficient of +16, and its residual becomes roughly minus-the-headline - which "
            "then shows up as a flat -0.5 arrow from gasoline into every persistent service "
            "item at every lag from 1 to 12.",
            "Each edge carries `rho_other`, the same pair and lag measured in the other "
            "variant. An edge whose rho_other is near zero or of the opposite sign is a "
            "creature of the common-factor step, not a robust feature of the data.",
            "The headline used for common-factor removal contains the item itself, so for very "
            "heavy nodes (owners' equivalent rent is ~25% of the basket) some of the item's own "
            "variation is removed along with the factor. Read those nodes' degrees with care.",
            "Edges are screened with Benjamini-Hochberg FDR across all ordered pairs within a "
            "window, then required to reappear in at least 3 of 4 overlapping 15-year windows "
            "with the same sign and the same best lag (+/-2 months). Surviving edges are "
            "reproducible features of the sample, not evidence of a mechanism.",
            "The best lag is the argmax of |rho| over 1..12 months and is not sharply "
            "identified: neighbouring lags usually have similar correlations, which is what "
            "p10_lagprofile is for.",
            "Nodes are non-overlapping mid-level items (no node is an ancestor of another), so "
            "no edge is a mechanical aggregation identity. Items inside the same major group "
            "can still share collection samples and seasonal factors.",
            "October 2025 has no CPI and November 2025 has no SA monthly change; the panel is "
            "reindexed to a complete calendar so every lag is a calendar lag, and both months "
            "are dropped by the 60%-of-weight coverage gate rather than shifted away.",
        ],
    }
    (OUT / "p10_network.json").write_text(json.dumps(out, indent=1))
    log.info("wrote %s (%.1f KB)", OUT / "p10_network.json",
             (OUT / "p10_network.json").stat().st_size / 1024)
    return 0 if ok_all else 2


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)
    kw = {}
    for a in sys.argv[1:]:
        if a.startswith("--since="):
            kw["since"] = a.split("=")[1]
        elif a.startswith("--universe="):
            kw["rule"] = a.split("=")[1]
        elif a.startswith("--rho-min="):
            kw["rho_min"] = float(a.split("=")[1])
        elif a.startswith("--fdr="):
            kw["fdr"] = float(a.split("=")[1])
        elif a.startswith("--min-windows="):
            kw["min_windows"] = int(a.split("=")[1])
        elif a.startswith("--max-lag="):
            kw["max_lag"] = int(a.split("=")[1])
        elif a.startswith("--granger-lags="):
            kw["glags"] = int(a.split("=")[1])
        elif a.startswith("--factor-lags="):
            kw["flags"] = int(a.split("=")[1])
        elif a == "--no-loo":
            kw["loo"] = False
        else:
            raise SystemExit(f"unknown arg {a}")
    sys.exit(main(**kw))
