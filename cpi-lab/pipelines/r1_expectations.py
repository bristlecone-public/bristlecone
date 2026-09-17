#!/usr/bin/env python3
"""R1 (Tier-2 research) — do frequency-weighted CPI gaps explain household inflation expectations?

Builds a monthly panel joining
  * p1_index  (official_replica / salience / blend50 / any newer scheme) YoY,
  * published CPI-U NSA YoY (FRED CPIAUCNS),
  * University of Michigan median expected price change next 1 yr (table 32) and next 5 yrs (table 33),
  * NY Fed Survey of Consumer Expectations median 1-yr and 3-yr expected inflation,
  * gasoline (SETB01) and food-at-home (SAF11) YoY from cpi_item_month,
and runs Newey-West OLS of the *expectations gap* on the *frequency-weighting gap*, with and
without the gas/food controls that the literature says drive perceptions.

  r1_expectations.py [--maxlags=12] [--force-fetch]

`--force-fetch` re-downloads every source even if the cached copy under raw/expect is current
(common.fetch already does Last-Modified caching; the Michigan POST tables are cached by file).

Outputs
  table  r1_panel(ym, <panel columns...>)          -- tidy-ish wide monthly panel
  file   $CPI_ROOT/out/r1_expectations.json         -- {panel:[...], regressions:{...}, meta:{...}}
  files  $CPI_ROOT/out/r1_fig/*.png                 -- figures for research/R1_expectations.md
  raw    $CPI_ROOT/raw/expect/*                     -- every downloaded source, unmodified

JSON schema
  meta      : generated_at, sample (first/last ym, n), schemes, dropped_months, sources{name:url}
  panel     : list of {ym, ...columns...} (nulls preserved)
  regressions: {model_key: {dep, sample, n, r2, adj_r2, maxlags, params:{name:{coef,se,t,p}}}}
  rolling   : {window, points:[{ym_end, beta, se, t}]}

No causal language is claimed anywhere: these are contemporaneous correlations in ~55 highly
autocorrelated monthly observations.
"""
import sys, json, io, re
import pandas as pd, numpy as np
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.api as sm
from common import *

EXPECT = RAW / "expect"
FIGDIR = OUT / "r1_fig"

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
UMICH = "https://data.sca.isr.umich.edu/data-archive/mine.php"
SCE = "https://www.newyorkfed.org/medialibrary/interactives/sce/sce/downloads/data/FRBNY-SCE-Data.xlsx"

SOURCES = {
    "fred_CPIAUCNS": FRED.format(sid="CPIAUCNS"),
    "fred_MICH": FRED.format(sid="MICH"),
    "umich_table32_1yr": UMICH + " [POST table=32]",
    "umich_table33_5yr": UMICH + " [POST table=33]",
    "nyfed_sce": SCE,
}

SCHEMA_R1 = "CREATE TABLE IF NOT EXISTS r1_panel(ym TEXT PRIMARY KEY, payload TEXT);"


# ---------------------------------------------------------------- fetching
def fred(sid, force=False):
    p, _ = fetch(FRED.format(sid=sid), EXPECT / f"fred_{sid}.csv", force=force)
    df = pd.read_csv(p)
    df.columns = ["date", sid]
    df["ym"] = pd.to_datetime(df.date).dt.strftime("%Y-%m")
    return df.set_index("ym")[sid].apply(pd.to_numeric, errors="coerce").dropna()


def umich_table(n, year=2005, force=False):
    """POST the ISR data archive form; returns the raw CSV text (cached under raw/expect)."""
    dest = EXPECT / f"umich_table{n}.csv"
    if dest.exists() and not force:
        return dest.read_text()
    r = requests.post(UMICH, data={"table": str(n), "year": str(year), "qorm": "M",
                                   "order": "asc", "format": "Comma-Separated (CSV)"},
                      headers={"User-Agent": UA}, timeout=120)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(r.text)
    log.info("fetched umich table %d (%d bytes)", n, len(r.text))
    return r.text


def umich_median(n, force=False):
    txt = umich_table(n, force=force)
    lines = [l for l in txt.splitlines() if l.strip()]
    hdr = next(i for i, l in enumerate(lines) if l.startswith("Month,Year"))
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr:])))
    df.columns = [c.strip() for c in df.columns]
    df = df[pd.to_numeric(df.Month, errors="coerce").notna()]
    df["ym"] = df.Year.astype(int).astype(str) + "-" + df.Month.astype(int).map("{:02d}".format)
    return pd.to_numeric(df.set_index("ym")["Median"], errors="coerce").dropna()


def sce_medians(force=False):
    """NY Fed SCE: median 1-yr and 3-yr ahead expected inflation (and 5-yr where published)."""
    p, _ = fetch(SCE, EXPECT / "FRBNY-SCE-Data.xlsx", force=force)
    out = {}
    d = pd.read_excel(p, sheet_name="Inflation expectations", header=3)
    d = d.rename(columns={d.columns[0]: "ym"})
    d = d[pd.to_numeric(d.ym, errors="coerce").notna()]
    d["ym"] = d.ym.astype(int).astype(str).str.slice(0, 4) + "-" + d.ym.astype(int).astype(str).str.slice(4, 6)
    c1 = [c for c in d.columns if str(c).startswith("Median one-year ahead expected inflation")]
    c3 = [c for c in d.columns if str(c).startswith("Median three-year ahead expected inflation")]
    out["sce1"] = pd.to_numeric(d.set_index("ym")[c1[0]], errors="coerce").dropna()
    out["sce3"] = pd.to_numeric(d.set_index("ym")[c3[0]], errors="coerce").dropna()
    try:
        f = pd.read_excel(p, sheet_name="Five-year ahead Infl Exp", header=3)
        f = f.rename(columns={f.columns[0]: "ym"})
        f = f[pd.to_numeric(f.ym, errors="coerce").notna()]
        f["ym"] = f.ym.astype(int).astype(str).str.slice(0, 4) + "-" + f.ym.astype(int).astype(str).str.slice(4, 6)
        c5 = [c for c in f.columns if "edian" in str(c)][0]
        out["sce5"] = pd.to_numeric(f.set_index("ym")[c5], errors="coerce").dropna()
    except Exception as e:
        log.warning("SCE 5-yr sheet unusable: %s", e)
    return out


# ---------------------------------------------------------------- helpers
def yoy_cal(s):
    """Calendar-aligned 12-month percent change (never a row offset -- Oct 2025 is missing)."""
    p = pd.PeriodIndex(s.index, freq="M")
    prev = pd.Series(s.values, index=(p + 12).astype(str))
    return (s / prev.reindex(s.index) - 1) * 100


def lag_cal(s, k):
    p = pd.PeriodIndex(s.index, freq="M")
    return pd.Series(s.values, index=(p + k).astype(str)).reindex(s.index)


def ols(df, dep, regs, maxlags=12, label=""):
    d = df[[dep] + regs].dropna()
    if len(d) < len(regs) + 6:
        return None
    X = sm.add_constant(d[regs])
    m = sm.OLS(d[dep], X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return {
        "label": label, "dep": dep, "regressors": regs, "maxlags": maxlags,
        "sample": [d.index.min(), d.index.max()], "n": int(len(d)),
        "r2": round(float(m.rsquared), 4), "adj_r2": round(float(m.rsquared_adj), 4),
        "params": {k: {"coef": round(float(m.params[k]), 4), "se": round(float(m.bse[k]), 4),
                       "t": round(float(m.tvalues[k]), 3), "p": round(float(m.pvalues[k]), 4)}
                   for k in m.params.index},
        "_fit": m,
    }


def fmt(r):
    if r is None:
        return "  (insufficient obs)"
    ps = "  ".join(f"{k}={v['coef']:+.3f}(t={v['t']:+.2f})" for k, v in r["params"].items() if k != "const")
    return (f"  {r['label']:<34s} n={r['n']:3d} R2={r['r2']:.3f} adjR2={r['adj_r2']:.3f}  "
            f"const={r['params']['const']['coef']:+.3f}  {ps}")


# ---------------------------------------------------------------- main
def main(maxlags=12, force=False):
    con = init_db(); con.executescript(SCHEMA_R1); con.commit()
    EXPECT.mkdir(parents=True, exist_ok=True); FIGDIR.mkdir(parents=True, exist_ok=True)

    # ---- index schemes (re-query so any scheme the P1 agent added shows up)
    pi = pd.read_sql("SELECT scheme, ym, idx, yoy FROM p1_index", con)
    schemes = sorted(pi.scheme.unique())
    log.info("p1_index schemes present: %s", schemes)
    wide = pi.pivot(index="ym", columns="scheme", values="yoy").sort_index()

    # ---- month quality: p1_index computes a value for any month with *some* leaves; Oct-2025
    #      only has 11 of ~380 published items, so its index level is not comparable. Drop it.
    cov = pd.read_sql("SELECT ym, COUNT(*) n FROM cpi_item_month GROUP BY ym", con).set_index("ym").n
    med = cov.reindex(wide.index).median()
    bad = [ym for ym in wide.index if cov.get(ym, 0) < 0.5 * med]
    log.info("dropping thin months (<50%% of %d items): %s", int(med), bad)

    # ---- item YoY controls
    it = pd.read_sql("SELECT item_code, ym, yoy FROM cpi_item_month WHERE item_code IN ('SETB01','SAF11','SA0')", con)
    it = it.pivot(index="ym", columns="item_code", values="yoy")

    # ---- external series
    cpi = fred("CPIAUCNS", force=force)
    cpi_yoy = yoy_cal(cpi)
    mich_fred = fred("MICH", force=force)
    mich1 = umich_median(32, force=force)
    mich5 = umich_median(33, force=force)
    sce = sce_medians(force=force)

    # cross-check the ISR table against FRED's MICH
    j = pd.concat([mich1.rename("isr"), mich_fred.rename("fred")], axis=1).dropna()
    log.info("MICH cross-check vs ISR table 32: n=%d max|diff|=%.3f corr=%.4f",
             len(j), (j.isr - j.fred).abs().max(), j.isr.corr(j.fred))

    df = pd.DataFrame(index=[ym for ym in wide.index if ym not in bad])
    for s in schemes:
        df[f"yoy_{s}"] = wide[s]
    base = "official_replica"
    for s in schemes:
        if s != base:
            df[f"gap_{s}"] = wide[s] - wide[base]
    df["cpi_yoy_pub"] = cpi_yoy.reindex(df.index)
    df["cpi_yoy_pub_l1"] = lag_cal(cpi_yoy, 1).reindex(df.index)
    df["cpi_yoy_pub_l12"] = lag_cal(cpi_yoy, 12).reindex(df.index)
    df["sa0_yoy_ours"] = it["SA0"].reindex(df.index)
    df["gas_yoy"] = it["SETB01"].reindex(df.index)
    df["fah_yoy"] = it["SAF11"].reindex(df.index)
    df["mich1"] = mich1.reindex(df.index)
    df["mich5"] = mich5.reindex(df.index)
    for k, v in sce.items():
        df[k] = v.reindex(df.index)

    df["gap_expect"] = df.mich1 - df.cpi_yoy_pub                 # contemporaneous
    df["gap_expect_l1"] = df.mich1 - df.cpi_yoy_pub_l1           # vs. the print households had seen
    df["gap_expect_l12"] = df.mich1 - df.cpi_yoy_pub_l12         # vs. the rate a year earlier
    df["gap_expect5"] = df.mich5 - df.cpi_yoy_pub
    if "sce1" in df:
        df["gap_sce"] = df.sce1 - df.cpi_yoy_pub
        df["gap_sce_l12"] = df.sce1 - df.cpi_yoy_pub_l12
    if "sce3" in df:
        df["gap_sce3"] = df.sce3 - df.cpi_yoy_pub

    df = df.dropna(subset=[f"yoy_{base}"])
    log.info("panel %s..%s, %d months; columns %s", df.index.min(), df.index.max(), len(df), list(df.columns))

    # ---------------------------------------------------------------- regressions
    R, sub2223, sub2426 = {}, df[df.index < "2024-01"], df[df.index >= "2024-01"]
    gapcols = [c for c in df.columns if c.startswith("gap_") and c.split("gap_")[1] in schemes]
    primary = "gap_salience" if "gap_salience" in df else (gapcols[0] if gapcols else None)

    specs = []
    for dep, dl in (("gap_expect", "MICH1-CPIyoy"), ("gap_expect_l12", "MICH1-CPIyoy(t-12)")):
        specs += [
            (f"{dl}~freq", dep, [primary], df),
            (f"{dl}~gas+food", dep, ["gas_yoy", "fah_yoy"], df),
            (f"{dl}~freq+gas+food", dep, [primary, "gas_yoy", "fah_yoy"], df),
        ]
    specs += [
        ("MICH1-CPIyoy~officialYoY", "gap_expect", ["cpi_yoy_pub"], df),
        ("MICH1-CPIyoy~officialYoY+freq", "gap_expect", ["cpi_yoy_pub", primary], df),
        ("MICH1-CPIyoy~offYoY+freq+gas+food", "gap_expect", ["cpi_yoy_pub", primary, "gas_yoy", "fah_yoy"], df),
        ("MICH1-CPIyoy(t-1)~freq", "gap_expect_l1", [primary], df),
        ("MICH1 level~officialYoY", "mich1", [f"yoy_{base}"], df),
        ("MICH1 level~salienceYoY", "mich1", [f"yoy_salience"], df) if "yoy_salience" in df else None,
        ("MICH1 level~off+freq", "mich1", [f"yoy_{base}", primary], df),
        ("MICH5-CPIyoy~freq", "gap_expect5", [primary], df),
        ("[2022-23] gap~freq", "gap_expect", [primary], sub2223),
        ("[2022-23] gap~freq+gas+food", "gap_expect", [primary, "gas_yoy", "fah_yoy"], sub2223),
        ("[2024-26] gap~freq", "gap_expect", [primary], sub2426),
        ("[2024-26] gap~freq+gas+food", "gap_expect", [primary, "gas_yoy", "fah_yoy"], sub2426),
    ]
    if "gap_sce" in df:
        specs += [
            ("SCE1-CPIyoy~freq", "gap_sce", [primary], df),
            ("SCE1-CPIyoy~gas+food", "gap_sce", ["gas_yoy", "fah_yoy"], df),
            ("SCE1-CPIyoy~freq+gas+food", "gap_sce", [primary, "gas_yoy", "fah_yoy"], df),
            ("SCE1-CPIyoy(t-12)~freq", "gap_sce_l12", [primary], df),
        ]
    # every alternative scheme, one-variable form, so new schemes are covered automatically
    for g in gapcols:
        if g != primary:
            specs.append((f"MICH1-CPIyoy~{g}", "gap_expect", [g], df))
            specs.append((f"MICH1-CPIyoy~{g}+gas+food", "gap_expect", [g, "gas_yoy", "fah_yoy"], df))

    for sp in specs:
        if sp is None:
            continue
        lab, dep, regs, data = sp
        if dep not in data or any(r not in data for r in regs):
            continue
        ml = min(maxlags, max(1, len(data) // 4))
        r = ols(data, dep, regs, maxlags=ml, label=lab)
        if r:
            R[lab] = r

    print("\n=== R1 regressions (Newey-West HAC SEs) " + "=" * 40)
    for lab in R:
        print(fmt(R[lab]))

    # robustness: same models at maxlags=4
    R4 = {}
    for lab in ("MICH1-CPIyoy~freq", "MICH1-CPIyoy~freq+gas+food"):
        if lab in R:
            r = ols(df, R[lab]["dep"], R[lab]["regressors"], maxlags=4, label=lab + " [NW4]")
            if r:
                R4[r["label"]] = r
    print("\n--- HAC lag robustness")
    for lab in R4:
        print(fmt(R4[lab]))
    R.update(R4)

    # ---------------------------------------------------------------- size / incremental tests
    desc_cols = [c for c in ["gap_expect", "gap_expect_l12", "gap_sce", primary, "gap_blend50",
                             "cpi_yoy_pub", "mich1", "sce1", "gas_yoy", "fah_yoy"] if c in df]
    desc = df[desc_cols].describe().T[["count", "mean", "std", "min", "max"]].round(3)
    print("\n--- descriptives (pp)\n" + desc.to_string())
    scale = {}
    if primary in df and "gap_expect" in df:
        g, f = df.gap_expect.dropna(), df[primary].dropna()
        scale = {"mean_gap_expect": round(float(g.mean()), 3), "sd_gap_expect": round(float(g.std()), 3),
                 "mean_gap_freq": round(float(f.mean()), 3), "sd_gap_freq": round(float(f.std()), 3),
                 "sd_ratio": round(float(g.std() / f.std()), 2),
                 "share_of_mean_gap_closed_by_freq": round(float(f.mean() / g.mean()), 4)}
        print(f"\n--- scale check: mean gap_expect {scale['mean_gap_expect']:+.2f}pp vs mean gap_freq "
              f"{scale['mean_gap_freq']:+.2f}pp  -> frequency weighting closes "
              f"{100*scale['share_of_mean_gap_closed_by_freq']:.1f}% of the average level gap; "
              f"sd ratio {scale['sd_ratio']}x")

    ftests = {}
    for lab, dep, restricted, full, data in [
        ("freq | gas+food", "gap_expect", ["gas_yoy", "fah_yoy"], [primary, "gas_yoy", "fah_yoy"], df),
        ("freq | officialYoY", "gap_expect", ["cpi_yoy_pub"], ["cpi_yoy_pub", primary], df),
        ("freq | offYoY+gas+food", "gap_expect", ["cpi_yoy_pub", "gas_yoy", "fah_yoy"],
         ["cpi_yoy_pub", primary, "gas_yoy", "fah_yoy"], df),
        ("freq | gas+food (SCE)", "gap_sce", ["gas_yoy", "fah_yoy"], [primary, "gas_yoy", "fah_yoy"], df),
    ]:
        if dep not in data:
            continue
        d = data[[dep] + full].dropna()
        m0 = sm.OLS(d[dep], sm.add_constant(d[restricted])).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
        m1 = sm.OLS(d[dep], sm.add_constant(d[full])).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
        w = float(m1.wald_test(np.eye(len(m1.params))[[list(m1.params.index).index(primary)]], scalar=True).statistic)
        ftests[lab] = {"dep": dep, "n": int(len(d)), "r2_restricted": round(float(m0.rsquared), 4),
                       "r2_full": round(float(m1.rsquared), 4),
                       "delta_r2": round(float(m1.rsquared - m0.rsquared), 4),
                       "hac_wald_chi2_on_freq": round(w, 3)}
        print(f"    incremental {lab:<26s} R2 {m0.rsquared:.3f} -> {m1.rsquared:.3f} "
              f"(dR2={m1.rsquared-m0.rsquared:+.4f}, HAC Wald chi2={w:.2f})")

    # ---------------------------------------------------------------- rolling beta
    roll, W = [], 24
    d = df[["gap_expect", primary]].dropna()
    for i in range(W, len(d) + 1):
        w = d.iloc[i - W:i]
        m = sm.OLS(w.gap_expect, sm.add_constant(w[primary])).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
        roll.append({"ym_end": w.index[-1], "beta": round(float(m.params[primary]), 4),
                     "se": round(float(m.bse[primary]), 4), "t": round(float(m.tvalues[primary]), 3),
                     "r2": round(float(m.rsquared), 4)})
    if roll:
        print(f"\n--- rolling {W}m beta of gap_expect on {primary}: "
              f"{roll[0]['ym_end']} {roll[0]['beta']:+.2f} ... {roll[-1]['ym_end']} {roll[-1]['beta']:+.2f} "
              f"(min {min(r['beta'] for r in roll):+.2f}, max {max(r['beta'] for r in roll):+.2f})")

    # ---------------------------------------------------------------- correlations
    cc = df[[c for c in ["gap_expect", "gap_expect_l12", "gap_sce", primary, "gas_yoy", "fah_yoy",
                         "cpi_yoy_pub", "mich1"] if c in df]].corr().round(3)
    print("\n--- correlation matrix\n" + cc.to_string())

    # ---------------------------------------------------------------- figures
    _figures(df, primary, roll, schemes, base)

    # ---------------------------------------------------------------- persist
    panel = [{"ym": ym, **{c: (None if pd.isna(v) else round(float(v), 4)) for c, v in row.items()}}
             for ym, row in df.iterrows()]
    con.execute("DELETE FROM r1_panel")
    con.executemany("INSERT INTO r1_panel VALUES(?,?)", [(p["ym"], json.dumps(p)) for p in panel])
    con.commit()

    out = {
        "meta": {
            "generated_at": pd.Timestamp.now("UTC").isoformat(),
            "sample": {"first": df.index.min(), "last": df.index.max(), "n": int(len(df))},
            "schemes": schemes, "primary_gap": primary, "dropped_months": bad,
            "maxlags": maxlags, "sources": SOURCES,
            "caveat": "~55 overlapping monthly observations, heavily autocorrelated. Correlational only.",
        },
        "panel": panel,
        "regressions": {k: {kk: vv for kk, vv in v.items() if kk != "_fit"} for k, v in R.items()},
        "rolling": {"window": W, "dep": "gap_expect", "reg": primary, "points": roll},
        "correlations": json.loads(cc.to_json()),
        "descriptives": json.loads(desc.to_json(orient="index")),
        "scale_check": scale,
        "incremental_tests": ftests,
    }
    (OUT / "r1_expectations.json").write_text(json.dumps(out, indent=1))
    log.info("wrote %s (%d panel rows, %d regressions)", OUT / "r1_expectations.json", len(panel), len(R))
    return df, R


def _figures(df, primary, roll, schemes, base):
    x = pd.PeriodIndex(df.index, freq="M").to_timestamp()

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(x, df.mich1, lw=2, color="#c0392b", label="Michigan median expected inflation, 1-yr")
    if "sce1" in df:
        ax.plot(x, df.sce1, lw=2, color="#e67e22", label="NY Fed SCE median, 1-yr")
    ax.plot(x, df.cpi_yoy_pub, lw=2, color="#2c3e50", label="Published CPI-U YoY (NSA)")
    ax.plot(x, df[f"yoy_{base}"], lw=1.2, ls="--", color="#7f8c8d", label="Dec-chained replica YoY")
    if "yoy_salience" in df:
        ax.plot(x, df.yoy_salience, lw=1.6, color="#2980b9", label="Frequency-weighted (salience) YoY")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_ylabel("percent"); ax.set_title("Expectations vs. measured inflation")
    ax.legend(fontsize=8); ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(FIGDIR / "fig1_series.png", dpi=140); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(x, df.gap_expect, lw=2, color="#c0392b", label="gap_expect = MICH 1-yr − CPI YoY (left)")
    ax.set_ylabel("percentage points"); ax.axhline(0, color="k", lw=0.6)
    a2 = ax.twinx()
    a2.plot(x, df[primary], lw=2, color="#2980b9", label=f"{primary} = salience − replica YoY (right)")
    a2.set_ylabel("percentage points")
    ax.set_title("Expectations gap vs. frequency-weighting gap")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = a2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper right"); ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(FIGDIR / "fig2_gaps.png", dpi=140); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    d = df[[primary, "gap_expect"]].dropna()
    early = d.index < "2024-01"
    ax.scatter(d[primary][early], d.gap_expect[early], s=34, color="#c0392b", label="2022–23")
    ax.scatter(d[primary][~early], d.gap_expect[~early], s=34, color="#2980b9", label="2024–26")
    if len(d) > 2:
        b = np.polyfit(d[primary], d.gap_expect, 1)
        xs = np.linspace(d[primary].min(), d[primary].max(), 20)
        ax.plot(xs, np.polyval(b, xs), color="k", lw=1.2, ls="--", label=f"OLS slope {b[0]:+.2f}")
    ax.set_xlabel(primary + "  (pp)"); ax.set_ylabel("gap_expect  (pp)")
    ax.set_title("Does the frequency gap track the expectations gap?")
    ax.legend(fontsize=8); ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(FIGDIR / "fig3_scatter.png", dpi=140); plt.close(fig)

    if roll:
        r = pd.DataFrame(roll).set_index("ym_end")
        xr = pd.PeriodIndex(r.index, freq="M").to_timestamp()
        fig, ax = plt.subplots(figsize=(9, 4.0))
        ax.plot(xr, r.beta, lw=2, color="#2980b9")
        ax.fill_between(xr, r.beta - 1.96 * r.se, r.beta + 1.96 * r.se, color="#2980b9", alpha=.2)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_title("24-month rolling slope of gap_expect on " + primary + " (±1.96 HAC SE)")
        ax.set_ylabel("slope"); ax.grid(alpha=.25); fig.tight_layout()
        fig.savefig(FIGDIR / "fig4_rolling.png", dpi=140); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(x, df.gap_expect, lw=2, color="#c0392b", label="gap_expect")
    ax.plot(x, df.gas_yoy / 10, lw=1.6, color="#8e44ad", label="gasoline YoY ÷10")
    ax.plot(x, df.fah_yoy, lw=1.6, color="#27ae60", label="food-at-home YoY")
    ax.axhline(0, color="k", lw=0.6); ax.grid(alpha=.25)
    ax.set_title("The usual suspects: gasoline and food at home"); ax.set_ylabel("pp")
    ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(FIGDIR / "fig5_controls.png", dpi=140); plt.close(fig)
    log.info("wrote figures to %s", FIGDIR)


if __name__ == "__main__":
    ml, force = 12, False
    for a in sys.argv[1:]:
        if a.startswith("--maxlags"):
            ml = int(a.split("=")[1])
        if a == "--force-fetch":
            force = True
        if a in ("-h", "--help"):
            print(__doc__); sys.exit(0)
    main(maxlags=ml, force=force)
