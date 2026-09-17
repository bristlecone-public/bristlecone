#!/usr/bin/env python3
"""P2 - cross-sectional distribution of item inflation (Tier 1, descriptive only).

  p2_distribution.py [--since YYYY-MM] [--no-cleveland] [--varshare-since YYYY-MM]

Headline inflation is one number produced by ~180 leaf items moving in very different
directions. P2 describes that cross-section every month - where the middle of the
distribution sits, how fat/skewed the tails are, how much of the basket is running hot -
and which items actually drive the month-to-month variance of the aggregate.
Nothing here is causal: these are descriptive statistics of published BLS series.

--------------------------------------------------------------------------------
UNIVERSE
--------------------------------------------------------------------------------
Leaves = cpi_weight WHERE is_leaf=1 AND matched=1 for weight_year = calendar_year - 1
(December relative importance of year Y applies to the months of Y+1).  Weight years
present in the DB are 2020..2025 (=> months 2021-01..2026-12).  For months outside that
range the nearest available weight year is carried back/forward and the row
`weight_exact` = 0 flags it - those months are a *fixed-weight* cross-section, not the
weights BLS actually used at the time.

  universe = 'all'        all matched leaves with a value for the variable that month
  universe = 'exshelter'  drops SEHA, SEHC01 and every leaf whose cu_item ancestry
                          contains SAH1 (i.e. also SEHB02 lodging away from home and
                          SEHD tenants'/household insurance).  ~34% of the basket, and
                          OER alone is ~26%, so it dominates every weighted moment.

Weights are renormalised to sum to 1 over the items that actually have a value for that
variable in that month (mom_sa exists for ~142 of 179 leaves, yoy for ~175).

--------------------------------------------------------------------------------
TABLES
--------------------------------------------------------------------------------
p2_dist(month, universe, stat, value)     one row per statistic
    stat = "<var>_<name>" for var in yoy | ann3m | mom_sa
      _wmean  weight-weighted mean            _median  weighted median (step definition)
      _p10 _p25 _p75 _p90                     weighted percentiles (step definition)
      _trim08 _trim16                         trimmed means, 8% / 16% of *weight* off
                                              each tail, Cleveland-Fed style
      _skew                                   weighted skewness  m3 / m2^1.5
      _exkurt                                 weighted excess kurtosis  m4 / m2^2 - 3
      _n                                      number of items with a value
      _covw                                   raw basket weight covered (% of CPI-U)
    yoy / ann3m only:
      _share_gt2 _share_gt4 _share_gt6        % of covered weight above 2 / 4 / 6%
      _share_lt0                              % of covered weight falling outright
    plus  weight_year, weight_exact (1 = BLS weights of the right vintage)

p2_varshare(month, "window", item_code, share, level_contrib)
    Rolling variance decomposition of X_t, our replica of headline SA MoM, over the
    trailing `window` months (24 or 60), calendar-aligned (a missing month - Oct-2025 -
    is skipped, never shifted).  With c_it = w_it * x_it (renormalised weight x item SA
    MoM, in percentage points) we have X_t = sum_i c_it exactly, hence
        Var(X) = sum_i Cov(c_i, X)   =>   share_i = Cov(c_i, X) / Var(X),  sum_i = 1.
    That is the spec's  w_i Cov(x_i, X)/Var(X)  with the weight folded into c_i.
    share_i > 0: the item's swings amplified the headline; < 0: they damped it.
    level_contrib = w_i * x_i / 100 for `month` itself (pp of that month's headline MoM).

--------------------------------------------------------------------------------
out/p2_distribution.json
--------------------------------------------------------------------------------
{ "generated_at", "latest_month", "weight_years", "notes": [...],
  "stats": { "all": {"ym": [...], "<stat>": [...]},        # columnar, aligned to "ym"
             "exshelter": {...} },                          # since --since (default 2000-01)
  "ridgeline": [ {"ym", "codes": [...], "yoy": [...], "w": [...]} ],   # last 60 months
  "varshare": { "24": [ {"item_code","item_name","share","level_contrib"} x15 ],
                "60": [ ... ] },                            # latest month, top 15 by share
  "validation": { "wmean_vs_sa0": [ {"ym","ours","published","diff","ok"} ],   # last 6 m
                  "share_sum":    [ {"window","month","sum","ok"} ],
                  "replica_mom":  {"corr","mae","n"},        # X_t vs published SA0 mom_sa
                  "cleveland":    {"source","rows": [ {"ym","cle_12m","ours_yoy_trim16",
                                     "diff_yoy","ours_compound_trim16","diff_compound"} ]} } }

Cross-check: Cleveland Fed 16% trimmed-mean CPI (trim_revised.csv from
clevelandfed.org/indicators-and-data/median-cpi).  Their series is a trimmed mean of ~45
*seasonally adjusted monthly* component changes; ours is over ~179 leaves.  We compare
their 12-month compounded rate with (a) our trimmed mean of the yoy cross-section and
(b) our monthly SA trimmed means compounded over 12 months - (b) is the like-for-like
construction, (a) is the number the site shows.  Differences of a few tenths are expected.
"""
import sys, json, datetime as dt
import numpy as np, pandas as pd
from common import *

CLE_URL = "https://www.clevelandfed.org/-/media/files/webcharts/mediancpi/trim_revised.csv?sc_lang=en"

SCHEMA2 = """
CREATE TABLE IF NOT EXISTS p2_dist(month TEXT, universe TEXT, stat TEXT, value REAL, PRIMARY KEY(month, universe, stat));
CREATE TABLE IF NOT EXISTS p2_varshare(month TEXT, "window" INT, item_code TEXT, share REAL, level_contrib REAL, PRIMARY KEY(month, "window", item_code));
CREATE INDEX IF NOT EXISTS p2_varshare_m ON p2_varshare(month, "window");
"""

VARS = ["yoy", "ann3m", "mom_sa"]
SHARE_VARS = ["yoy", "ann3m"]
PCTS = [10, 25, 75, 90]
TRIMS = [("trim08", 0.08), ("trim16", 0.16)]
# a month/variable is only described if the items with a value cover this much of the
# basket (% of CPI-U). Oct/Nov-2025 have SA indexes for a handful of items only.
MIN_COVW = 60.0


# ---------------------------------------------------------------- weighted statistics
def wpercentile(xs, ws, p):
    """Step-definition weighted percentile: value of the first item at which the
    cumulative weight reaches p (xs sorted ascending, ws sums to 1). This is how the
    Cleveland Fed defines the weighted median of the CPI cross-section."""
    cw = np.cumsum(ws)
    i = int(np.searchsorted(cw, p, side="left"))
    return float(xs[min(i, len(xs) - 1)])


def trimmed_mean(xs, ws, alpha):
    """Weighted mean after cutting `alpha` of the *weight* off each tail. Boundary items
    are split (their retained weight is the overlap of their weight interval with
    [alpha, 1-alpha]) so the estimator is continuous in alpha."""
    cw = np.cumsum(ws)
    lo = np.maximum(cw - ws, alpha)
    hi = np.minimum(cw, 1.0 - alpha)
    keep = np.clip(hi - lo, 0.0, None)
    s = keep.sum()
    if s <= 0:
        return float("nan")
    return float((xs * keep).sum() / s)


def wstats(x, w, var, raw_weight_sum):
    """All statistics for one variable in one month/universe. x,w are 1-D arrays of the
    items that have a value; w is renormalised here to sum to 1."""
    o = np.argsort(x, kind="stable")
    xs, ws = x[o], w[o] / w.sum()
    mu = float((xs * ws).sum())
    d = xs - mu
    m2 = float((ws * d ** 2).sum())
    sd = m2 ** 0.5
    out = {
        f"{var}_wmean": mu,
        f"{var}_median": wpercentile(xs, ws, 0.5),
        f"{var}_sd": sd,
        f"{var}_skew": float((ws * d ** 3).sum() / m2 ** 1.5) if m2 > 0 else float("nan"),
        f"{var}_exkurt": float((ws * d ** 4).sum() / m2 ** 2 - 3.0) if m2 > 0 else float("nan"),
        f"{var}_n": float(len(xs)),
        f"{var}_covw": float(raw_weight_sum),
    }
    for p in PCTS:
        out[f"{var}_p{p}"] = wpercentile(xs, ws, p / 100.0)
    for name, a in TRIMS:
        out[f"{var}_{name}"] = trimmed_mean(xs, ws, a)
    if var in SHARE_VARS:
        for t in (2, 4, 6):
            out[f"{var}_share_gt{t}"] = float(100 * ws[xs > t].sum())
        out[f"{var}_share_lt0"] = float(100 * ws[xs < 0].sum())
    return out


# ---------------------------------------------------------------- universe assembly
def ancestors(par, code):
    out, p = [], par.get(code)
    while p:
        out.append(p)
        p = par.get(p)
    return out


def load_frame(con):
    """Leaf-universe panel: one row per (ym, item) with the weight vintage that applies."""
    im = pd.read_sql("SELECT item_code, ym, mom_sa, yoy, ann3m FROM cpi_item_month", con)
    w = pd.read_sql("SELECT weight_year, item_code, weight_u FROM cpi_weight WHERE is_leaf=1 AND matched=1", con)
    items = pd.read_sql("SELECT item_code, item_name, parent_code FROM cu_item", con)
    par = dict(zip(items.item_code, items.parent_code))
    names = dict(zip(items.item_code, items.item_name))
    wys = sorted(w.weight_year.unique())
    lo, hi = wys[0], wys[-1]
    im["yr"] = im.ym.str[:4].astype(int)
    im["weight_year"] = (im.yr - 1).clip(lo, hi)
    im["weight_exact"] = ((im.yr - 1) >= lo) & ((im.yr - 1) <= hi)
    df = im.merge(w, on=["weight_year", "item_code"], how="inner")
    shelter = {c for c in set(df.item_code) if c in ("SEHA", "SEHC01") or "SAH1" in ancestors(par, c)}
    df["shelter"] = df.item_code.isin(shelter)
    log.info("panel: %d rows, %d items, ym %s..%s; weight years %s; shelter leaves %s",
             len(df), df.item_code.nunique(), df.ym.min(), df.ym.max(), wys, sorted(shelter))
    return df, names, wys


def month_range(a, b):
    return [str(p) for p in pd.period_range(a, b, freq="M")]


# ---------------------------------------------------------------- (1) distributions
def distributions(df, months):
    rows = []
    for ym, g in df[df.ym.isin(months)].groupby("ym", sort=True):
        for uni, gu in (("all", g), ("exshelter", g[~g.shelter])):
            if gu.empty:
                continue
            rec = {"weight_year": float(gu.weight_year.iloc[0]), "weight_exact": float(gu.weight_exact.iloc[0])}
            for var in VARS:
                v = gu[["item_code", var, "weight_u"]].dropna()
                v = v[v.weight_u > 0]
                if len(v) < 20 or v.weight_u.sum() < MIN_COVW * (0.6 if uni == "exshelter" else 1.0):
                    continue
                rec.update(wstats(v[var].to_numpy(float), v.weight_u.to_numpy(float), var, v.weight_u.sum()))
            for k, val in rec.items():
                if val is not None and np.isfinite(val):
                    rows.append((ym, uni, k, float(val)))
    return rows


# ---------------------------------------------------------------- (3) variance shares
def contribution_matrix(df):
    """Wide matrix C (months x items) of c_it = w_it * x_it, x = SA MoM, weights
    renormalised each month over the items that have an SA index. Missing items are 0:
    they genuinely contribute nothing to that month's aggregate, so X = C.sum(axis=1)
    holds exactly and the variance shares sum to 1."""
    d = df[["ym", "item_code", "mom_sa", "weight_u"]].dropna()
    d = d[d.weight_u > 0]
    covw = d.groupby("ym").weight_u.sum()
    thin = covw[covw < MIN_COVW]
    if len(thin):
        log.info("dropping %d months with SA MoM coverage < %.0f%% of the basket: %s",
                 len(thin), MIN_COVW, [(m, round(v, 1)) for m, v in thin.items()][-6:])
    d = d[~d.ym.isin(set(thin.index))]
    tot = d.groupby("ym").weight_u.transform("sum")
    d = d.assign(c=d.weight_u / tot * d.mom_sa)
    C = d.pivot_table(index="ym", columns="item_code", values="c", aggfunc="sum")
    C = C.reindex(month_range(C.index.min(), C.index.max()))  # calendar-aligned; gap months all-NaN
    return C


def varshares(C, months, windows=(24, 60), min_frac=0.9):
    idx = list(C.index)
    pos = {m: i for i, m in enumerate(idx)}
    rows, sums = [], []
    for ym in months:
        if ym not in pos:
            continue
        for L in windows:
            i = pos[ym]
            if i - L + 1 < 0:
                continue
            win = C.iloc[i - L + 1: i + 1]
            win = win.dropna(how="all")            # drop months with no CPI at all (Oct-2025)
            if len(win) < min_frac * L:
                continue
            M = win.fillna(0.0).to_numpy(float)
            X = M.sum(axis=1)
            Xc = X - X.mean()
            var = float((Xc ** 2).sum())
            if var <= 0:
                continue
            cov = ((M - M.mean(axis=0)) * Xc[:, None]).sum(axis=0)
            share = cov / var
            lc = C.loc[ym]
            keep = np.abs(share) > 1e-12
            for code, s in zip(win.columns[keep], share[keep]):
                v = lc.get(code)
                rows.append((ym, L, code, float(s), None if v is None or not np.isfinite(v) else float(v)))
            sums.append((ym, L, float(share.sum()), len(win)))
    return rows, sums


# ---------------------------------------------------------------- (5) Cleveland Fed
def cleveland(dist, months12):
    """Compare our 16% trimmed mean with the Cleveland Fed's published 16% trimmed-mean CPI.
    Returns (source, rows) or (None, []) if the file cannot be fetched."""
    try:
        path, _ = fetch(CLE_URL, RAW / "clevelandfed" / "trim_revised.csv", retries=2)
        cle = pd.read_csv(path)
    except Exception as e:  # noqa
        log.warning("Cleveland Fed trimmed-mean CSV unreachable (%s) - cross-check skipped", e)
        return None, []
    cle.columns = [c.strip() for c in cle.columns]
    cle["ym"] = pd.to_datetime(cle["date"].astype(str).str.strip(), format="%m/%d/%Y").dt.strftime("%Y-%m")
    m = cle.set_index("ym")["trim_monthly_chg"].astype(float)      # fractional SA monthly change
    ours_mom = dist.get("mom_sa_trim16", pd.Series(dtype=float))   # % per month, SA
    ours_yoy = dist.get("yoy_trim16", pd.Series(dtype=float))
    def compound(v):
        """12-month rate from monthly fractional changes; if the window has a hole
        (Oct-2025), geometrically annualise the months that do exist."""
        n = len(v)
        return (float(np.prod(1.0 + v)) ** (12.0 / n) - 1.0) * 100 if n else float("nan")

    rows = []
    for ym in months12:
        win = month_range(str(pd.Period(ym, "M") - 11), ym)
        cw = m.reindex(win).dropna()
        ow = ours_mom.reindex(win).dropna()
        if len(cw) < 10:
            continue
        cle12 = compound(cw.to_numpy())
        ours12 = compound(ow.to_numpy() / 100) if len(ow) >= 10 else float("nan")
        oy = float(ours_yoy.get(ym, float("nan")))
        rows.append({"ym": ym, "n_months_cle": int(len(cw)), "n_months_ours": int(len(ow)),
                     "cle_12m": round(cle12, 3),
                     "ours_yoy_trim16": None if not np.isfinite(oy) else round(oy, 3),
                     "diff_yoy": None if not np.isfinite(oy) else round(oy - cle12, 3),
                     "ours_compound_trim16": None if not np.isfinite(ours12) else round(ours12, 3),
                     "diff_compound": None if not np.isfinite(ours12) else round(ours12 - cle12, 3)})
    return "clevelandfed.org trim_revised.csv (16% trimmed-mean CPI, SA monthly)", rows


# ---------------------------------------------------------------- main
def main(since="2000-01", vs_since="2000-01", do_cle=True):
    con = init_db()
    con.executescript(SCHEMA2)
    con.commit()
    df, names, wys = load_frame(con)
    last = df.ym.max()
    months = [m for m in month_range(since, last) if m in set(df.ym)]
    log.info("computing distributions for %d months (%s..%s)", len(months), months[0], months[-1])

    rows = distributions(df, months)
    con.execute("DELETE FROM p2_dist")
    con.executemany("INSERT OR REPLACE INTO p2_dist VALUES(?,?,?,?)", rows)
    con.commit()
    log.info("p2_dist: %d rows", len(rows))

    d = pd.DataFrame(rows, columns=["ym", "universe", "stat", "value"])
    wide = {u: g.pivot(index="ym", columns="stat", values="value").sort_index()
            for u, g in d.groupby("universe")}
    dist_all = wide["all"]

    # ---- variance decomposition
    C = contribution_matrix(df)
    vs_months = [m for m in month_range(vs_since, last) if m in set(C.index)]
    vrows, vsums = varshares(C, vs_months)
    con.execute("DELETE FROM p2_varshare")
    con.executemany('INSERT OR REPLACE INTO p2_varshare VALUES(?,?,?,?,?)', vrows)
    con.commit()
    log.info("p2_varshare: %d rows over %d months x {24,60}m", len(vrows), len(vs_months))

    # ---- validation
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    pub = pd.read_sql("SELECT ym, yoy, mom_sa FROM cpi_item_month WHERE item_code='SA0'", con).set_index("ym")
    val_rows, ok_all = [], True
    for ym in [m for m in months if np.isfinite(dist_all["yoy_wmean"].get(m, np.nan))][-6:]:
        ours = float(dist_all.loc[ym, "yoy_wmean"])
        p = float(pub.yoy.get(ym, np.nan))
        diff = ours - p
        ok = abs(diff) < 0.2
        ok_all &= bool(ok)
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    (now, "p2_leaf_wmean_yoy_vs_sa0", ym, ours, p, diff, int(ok)))
        val_rows.append({"ym": ym, "ours": round(ours, 3), "published": round(p, 3),
                         "diff": round(diff, 3), "ok": bool(ok)})
        log.info("validate %s: weighted-mean leaf YoY %.3f vs published SA0 %.3f (diff %+.3f pp) %s",
                 ym, ours, p, diff, "OK" if ok else "OUT OF TOLERANCE")
    share_rows = []
    for ym, L, s, n in vsums[-6:]:
        ok = abs(s - 1) < 1e-6
        ok_all &= bool(ok)
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    (now, f"p2_varshare_sum_{L}m", ym, s, 1.0, s - 1, int(ok)))
        share_rows.append({"window": L, "month": ym, "sum": round(s, 9), "n_months": n, "ok": bool(ok)})
    for r in share_rows[-2:]:
        log.info("validate varshare %s %dm: sum of shares = %.9f over %d months %s",
                 r["month"], r["window"], r["sum"], r["n_months"], "OK" if r["ok"] else "BAD")
    # our replica of headline SA MoM (X_t, the quantity being decomposed) vs published SA0
    X = C.sum(axis=1, min_count=1).dropna()
    X = X[X.index >= since]
    j = pub.mom_sa.reindex(X.index).dropna()
    both = X.reindex(j.index)
    rep = {"corr": round(float(np.corrcoef(both, j)[0, 1]), 4),
           "mae": round(float((both - j).abs().mean()), 4),
           "bias": round(float((both - j).mean()), 4), "n": int(len(j)), "since": since}
    log.info("replica SA MoM vs published SA0 since %s: corr %.4f, mean abs diff %.4f pp, bias %+.4f pp, n=%d",
             since, rep["corr"], rep["mae"], rep["bias"], rep["n"])

    cle_src, cle_rows = cleveland(dist_all, months[-12:]) if do_cle else (None, [])
    for r in cle_rows:
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    (now, "p2_trim16_vs_clevelandfed", r["ym"], r["ours_yoy_trim16"], r["cle_12m"],
                     r["diff_yoy"], int(r["diff_yoy"] is not None and abs(r["diff_yoy"]) < 1.0)))
    if cle_rows:
        log.info("Cleveland Fed 16%% trimmed mean (12m) vs ours - last 12 months:")
        for r in cle_rows:
            f = lambda k, d=2: "  n/a" if r[k] is None else f"{r[k]:{d + 4}.{d}f}"  # noqa
            log.info("  %s  cle %5.2f (%dm) | ours yoy-dist %s (diff %s) | ours compounded-SA %s (diff %s, %dm)",
                     r["ym"], r["cle_12m"], r["n_months_cle"], f("ours_yoy_trim16"), f("diff_yoy"),
                     f("ours_compound_trim16"), f("diff_compound"), r["n_months_ours"])
    con.commit()

    # ---- JSON
    def cols(w):
        o = {"ym": list(w.index)}
        for c in w.columns:
            o[c] = [None if not np.isfinite(v) else round(float(v), 4) for v in w[c].to_numpy(float)]
        return o

    ridge = []
    for ym in months[-60:]:
        g = df[(df.ym == ym) & df.yoy.notna()].sort_values("weight_u", ascending=False)
        ridge.append({"ym": ym, "codes": g.item_code.tolist(),
                      "yoy": [round(float(v), 3) for v in g.yoy], "w": [round(float(v), 4) for v in g.weight_u]})

    vdf = pd.DataFrame(vrows, columns=["ym", "window", "item_code", "share", "level_contrib"])
    top = {}
    if len(vdf):
        lm = vdf.ym.max()
        for L in (24, 60):
            g = vdf[(vdf["ym"] == lm) & (vdf["window"] == L)].sort_values("share", ascending=False).head(15)
            top[str(L)] = [{"item_code": r.item_code, "item_name": names.get(r.item_code, r.item_code),
                            "share": round(r.share, 4),
                            "level_contrib": None if r.level_contrib is None or not np.isfinite(r.level_contrib)
                            else round(r.level_contrib, 4)} for r in g.itertuples()]
        top["month"] = lm

    out = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "latest_month": last,
        "weight_years": [int(y) for y in wys],
        "stats": {u: cols(w) for u, w in wide.items()},
        "ridgeline": ridge,
        "varshare": top,
        "validation": {"wmean_vs_sa0": val_rows, "share_sum": share_rows, "replica_mom": rep,
                       "cleveland": {"source": cle_src, "rows": cle_rows}},
        "notes": [
            "Descriptive statistics of published BLS item indexes. No causal interpretation is implied: "
            "a large variance share means an item's swings moved with the aggregate, not that it caused it.",
            "Weighted moments are dominated by shelter (~34% of the basket, OER alone ~26%); the "
            "'exshelter' universe drops SEHA, SEHB02, SEHC01, SEHD.",
            "Weights are December relative importance held fixed through the following year, renormalised "
            "over the items with data; months before 2021 reuse the oldest available weight vintage "
            "(weight_exact=0) and are therefore a fixed-weight cross-section.",
            "October 2025 has no CPI (shutdown); all lags are calendar-aligned, so Nov-2025 MoM and "
            "Jan-2026 3-month-annualised are missing by design rather than shifted.",
            "Median/percentiles use the step definition (value of the item at which cumulative weight "
            "crosses p), the same convention as the Cleveland Fed median CPI.",
        ],
    }
    (OUT / "p2_distribution.json").write_text(json.dumps(out, indent=1, allow_nan=False))

    a = dist_all.loc[last]
    log.info("=== %s all-items leaf distribution: mean %.2f median %.2f trim8 %.2f trim16 %.2f "
             "p10 %.2f p25 %.2f p75 %.2f p90 %.2f skew %.2f exkurt %.2f | >2%% %.1f%% >4%% %.1f%% >6%% %.1f%% <0 %.1f%% of weight",
             last, a.yoy_wmean, a.yoy_median, a.yoy_trim08, a.yoy_trim16, a.yoy_p10, a.yoy_p25, a.yoy_p75,
             a.yoy_p90, a.yoy_skew, a.yoy_exkurt, a.yoy_share_gt2, a.yoy_share_gt4, a.yoy_share_gt6, a.yoy_share_lt0)
    e = wide["exshelter"].loc[last]
    log.info("=== %s ex-shelter: mean %.2f median %.2f trim16 %.2f skew %.2f | >4%% %.1f%% of weight",
             last, e.yoy_wmean, e.yoy_median, e.yoy_trim16, e.yoy_skew, e.yoy_share_gt4)
    for L in (24, 60):
        if str(L) in top:
            log.info("top variance contributors %s (%dm): %s", top["month"], L,
                     [(t["item_name"][:28], round(t["share"], 3)) for t in top[str(L)][:8]])
    return 0 if ok_all else 2


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)
    kw = {}
    for a in sys.argv[1:]:
        if a.startswith("--since"):
            kw["since"] = a.split("=")[1]
        elif a.startswith("--varshare-since"):
            kw["vs_since"] = a.split("=")[1]
        elif a == "--no-cleveland":
            kw["do_cle"] = False
    sys.exit(main(**kw))
