#!/usr/bin/env python3
"""P4 — revision ghosts: how much seasonally-adjusted CPI history gets rewritten, and how
noisy a single monthly print is.

  p4_vintages.py [--backfill] [--force] [--no-fetch] [--help]

    --backfill   re-pull every vintage from scratch (default: only vintages newer than the
                 newest one already stored for that series)
    --force      ignore the HTTP cache when re-reading the ALFRED series pages
    --no-fetch   skip all downloads; rebuild the analysis tables + JSON from what is stored

WHAT THIS IS
------------
BLS publishes seasonally-adjusted (SA) CPI, then rewrites it. Every February the seasonal
factors are re-estimated and the previous FIVE years of SA history are restated. So the
"0.4% in March" you read on release day is not the 0.4% that sits in the database two years
later. This pipeline reconstructs the real-time record from ALFRED (St. Louis Fed's archive
of FRED vintages) and measures the rewriting.

Nothing here is causal and nothing here says BLS is wrong. Seasonal adjustment is an
estimate; re-estimating it with more data is the correct thing to do. The point is that a
one-month SA print is a noisy, provisional statistic and should be read as one.

DATA SOURCE (no API key needed)
-------------------------------
ALFRED's own download form is a plain POST:
    GET  https://alfred.stlouisfed.org/series/downloaddata?seid=<SERIES_ID>
         -> HTML; <select id="form_selected_vintage_dates"> lists every vintage date
    POST same URL, form[file_type]=2 ("Observations by Vintage Date, All Observations"),
         form[file_format]=csv, form[selected_vintage_dates][]=<date> repeated
         -> application/zip containing README.txt + vintages_starting_<d>.csv, a wide CSV
            with one column per vintage (`<SID>_YYYYMMDD`).
This returns ALL vintages in ONE request (~6 s for 668 vintages of CPIAUCSL), so we never
hammer the per-vintage endpoint. form[obs_end_date] must be <= the page's own obs end date
or the form re-renders with "Data is not available after ...".
The keyless single-vintage alternative is
    https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=<SID>&vintage_date=<d>
but it only honours the LAST vintage_date given, so it is one HTTP request per vintage.
The FRED API (realtime_start=1776-07-04) would also work but needs a free api_key; not used.

RETENTION (why we do not store every cell)
------------------------------------------
Measured on CPIAUCSL, comparing each obs month's SA MoM as of vintage (obs + L years)
against its final value, over vintages since 2000:
    L=1..4 yr : 71-81% of months still differ (max 0.27 pp)
    L=5 yr    :  6.9% differ (max 0.17 pp)
    L=6 yr    :  1.3% differ (max 0.066 pp)
    L=7 yr    :  0.0% differ (max 0.0002 pp)
    L=8 yr    :  0.0% differ (max 0.0000 pp)
i.e. the 5-year seasonal revision window is real and SA history is frozen after ~7 years.
We therefore store, for each vintage, only observations within RETAIN_MONTHS (98 = 8y+2m)
of the vintage date. This is lossless for revision analysis and cuts ~2.4 M rows to ~350 k.

TABLES (idempotent; p4_vintage/p4_mom append, the rest are rebuilt each run)
---------------------------------------------------------------------------
  p4_series(series_id, label, title, se_item, se_exact, n_vintages, first_vintage,
            last_vintage, n_obs_months, pulled_at)
  p4_vintage(series_id, vintage_date, obs_date, value)
        every stored vintage x observation of the SA index. obs_date = 'YYYY-MM-01'.
  p4_mom(series_id, obs_month, vintage_date, mom)
        SA month-over-month % as seen in that vintage. Calendar-aligned: mom(m) needs both
        m and m-1 in that vintage, so 2025-10 and 2025-11 are absent for every series
        (October 2025 CPI was never published). NULL moms are not stored.
  p4_revision(series_id, obs_month, first_print, first_vintage, after_1y, latest,
              rev_1y, rev_latest, n_vintages, true_first)
        first_print = mom in the earliest vintage that contains obs_month
        after_1y    = mom in the earliest vintage >= first_vintage + 365 d
        latest      = mom in the newest vintage that contains obs_month
        rev_1y = after_1y - first_print ; rev_latest = latest - first_print
        n_vintages  = number of STORED vintages carrying this obs_month (capped by
                      RETAIN_MONTHS, so ~98 for old months -- see docs/P4.md)
        true_first  = 1 when first_print really is an original release. A series' OLDEST
                      archived vintage also carries back-history; for those older obs months
                      the "first" value we can see is already a revised one, which would bias
                      revisions toward zero. true_first=0 marks them and every statistic in
                      the JSON is computed on true_first=1 only.
  p4_transition(series_id, first_bin, latest_bin, n)
        first_print and latest both rounded to 0.1 (half away from zero, BLS style)
  p4_seflag(series_id, obs_month, first_print, trail12, n_trail, se, se_year, gap,
            within_1p5se)
        gap = |first_print - real-time trailing 12-month mean of mom in the same vintage|
        within_1p5se = 1 when gap < 1.5 * se  ("not distinguishable from trend")

JSON  $CPI_ROOT/out/p4_vintages.json
-----------------------------------
{ "generated_at": ISO-8601 UTC,
  "summary": {headline_CPIAUCSL, core_CPILFESL},   # the few numbers a reader actually needs
  "source": {name, series_page, method, retain_months, note},
  "windows": ["full","2011+","2019+"],
  "series": [ { "series_id", "label", "title", "first_vintage", "last_vintage",
                "n_vintages", "n_obs_months", "se_item", "se_exact",
                "stats": { "<window>": {n, mean_rev, mean_abs_rev, sd_rev, p10, p50, p90,
                                        mean_abs_rev_1y, share_abs_ge_0_1,
                                        share_abs_ge_0_2, share_sign_flip} },
                "by_month_of_year": [ {m, n, mean_rev, mean_abs_rev, p90_abs} x12 ],
                "by_year":          [ {year, n, mean_rev, mean_abs_rev} ],
                "se_flag": {since, n, n_within, share_within, se_1m, se_year} } ],
  "transitions": { "<series_id>": { "n", "share_changed",
                                    "rows": [ {first, n, to: {"<bin>": count}, share_changed} ] } },
  "fan":  { "<series_id>": { "obs_months": [...], "vintages": [...],
                             "mom": [[per-vintage row of len(obs_months), null-padded]] } },
  "se_series": { "<series_id>": [ {obs_month, first_print, trail12, se, within} ] },  # 2015+
  "validation": {check, n, max_abs_diff, ok, detail:[{ym, alfred, p0, diff}]},
  "caveats": [ ... ] }

VALIDATION
----------
The newest CPIAUCSL vintage's SA MoM is compared with p0's cpi_item_month.mom_sa for item
SA0 over the last 24 available months; max |diff| is logged and written to `validation`.
"""
import sys, io, re, json, zipfile, datetime as dt
import numpy as np
import pandas as pd
from common import *
from common import _s          # shared requests.Session (star-import skips _names)

ALFRED = "https://alfred.stlouisfed.org/series/downloaddata?seid=%s"
RAWP4 = RAW / "alfred"
RETAIN_MONTHS = 98          # 8y + 2m; see docstring
FAN_MONTHS = 36
SE_SINCE = "2019-01"        # share-within-1.5SE reporting window
SE_SERIES_SINCE = "2015-01"

# series_id -> (short label, p5_se item, se_exact)
#   se_exact=1 : the series IS that published major group, so the BLS median 1-month SE
#                applies directly. se_exact=0 : the series is a component of (or is spread
#                across) that group; the group SE is a proxy and generally a LOWER bound,
#                because narrower cells have fewer quotes and larger sampling error.
SERIES = {
    "CPIAUCSL":       ("Headline (all items)",        "all items",                      1),
    "CPILFESL":       ("Core (ex food & energy)",     "all items less food and energy", 1),
    "CPIUFDSL":       ("Food",                        "food and beverages",             0),
    "CPIENGSL":       ("Energy",                      "energy",                         1),
    "CUSR0000SAH1":   ("Shelter",                     "housing",                        0),
    "CUSR0000SEHA":   ("Rent of primary residence",   "housing",                        0),
    "CUSR0000SEHC01": ("Owners' equivalent rent",     "housing",                        0),
    "CUSR0000SAF11":  ("Food at home",                "food and beverages",             0),
    "CUSR0000SETA01": ("New vehicles",                "transportation",                 0),
    "CUSR0000SETA02": ("Used cars and trucks",        "transportation",                 0),
    "CUSR0000SAS":    ("Services",                    "all items",                      0),
    "CUSR0000SACL1E": ("Core goods",                  "all items less food and energy", 0),
    "CUSR0000SASLE":  ("Services less energy svcs",   "all items less food and energy", 0),
}

SCHEMA_P4 = """
CREATE TABLE IF NOT EXISTS p4_series(series_id TEXT PRIMARY KEY, label TEXT, title TEXT,
  se_item TEXT, se_exact INT, n_vintages INT, first_vintage TEXT, last_vintage TEXT,
  n_obs_months INT, pulled_at TEXT);
CREATE TABLE IF NOT EXISTS p4_vintage(series_id TEXT, vintage_date TEXT, obs_date TEXT, value REAL,
  PRIMARY KEY(series_id, vintage_date, obs_date)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS p4_mom(series_id TEXT, obs_month TEXT, vintage_date TEXT, mom REAL,
  PRIMARY KEY(series_id, obs_month, vintage_date)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS p4_mom_sv ON p4_mom(series_id, vintage_date);
CREATE TABLE IF NOT EXISTS p4_revision(series_id TEXT, obs_month TEXT, first_print REAL,
  first_vintage TEXT, after_1y REAL, latest REAL, rev_1y REAL, rev_latest REAL, n_vintages INT,
  true_first INT, PRIMARY KEY(series_id, obs_month));
CREATE TABLE IF NOT EXISTS p4_transition(series_id TEXT, first_bin TEXT, latest_bin TEXT, n INT,
  PRIMARY KEY(series_id, first_bin, latest_bin));
CREATE TABLE IF NOT EXISTS p4_seflag(series_id TEXT, obs_month TEXT, first_print REAL,
  trail12 REAL, n_trail INT, se REAL, se_year INT, gap REAL, within_1p5se INT,
  PRIMARY KEY(series_id, obs_month));
"""

def migrate(con):
    """Add columns introduced after a table was first created (CREATE IF NOT EXISTS won't)."""
    for table, col, decl in [("p4_revision", "true_first", "INT")]:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        if cols and col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
            log.info("migrated: %s += %s", table, col)
    con.commit()


CAVEATS = [
    "Seasonal-adjustment revisions are not errors. BLS re-estimates seasonal factors every "
    "January (published with the January CPI in February) and restates the previous five years "
    "of SA history. Revising an estimate as more data arrives is correct practice.",
    "NSA (not seasonally adjusted) CPI is essentially never revised. Everything measured here "
    "is a property of the seasonal adjustment, not of the underlying price collection.",
    "October 2025 CPI was never published (shutdown), so SA MoM does not exist for 2025-10 or "
    "2025-11 in any vintage of the aggregates. Those months are absent from p4_mom / "
    "p4_revision by design; they are not treated as zeros and never enter a mean. Two "
    "exceptions, confirmed against BLS's own files in p0: new vehicles (CUSR0000SETA01) and "
    "used cars and trucks (CUSR0000SETA02) DO have an October 2025 value, because those "
    "indexes are built from transaction data rather than field collection. MoM is computed "
    "per series by calendar alignment, so this is handled automatically rather than hardcoded.",
    "The oldest archived vintage of a series also contains back-history, and that history had "
    "already been revised before ALFRED first captured it. Those obs months are stored with "
    "true_first=0 and excluded from every statistic; including them would bias revisions "
    "toward zero (for core CPI it would add 97 months of pre-1996 back-history).",
    "CPIAUCSL vintages before 1981-02-25 carry CPI-W, not CPI-U (ALFRED keeps the FRED series "
    "id stable across a definition change), and the index base changed from 1967=100 to "
    "1982-84=100 on 1988-02-26. MoM percent changes are invariant to the rebasing, but "
    "pre-1981 CPIAUCSL revision statistics describe CPI-W. Use the 2011+ window for "
    "cross-series comparison; only CPIAUCSL has vintages before 1996.",
    "n_vintages is capped by the 98-month retention window, so an obs month older than ~8 years "
    "reports ~98 rather than 'every vintage ever'. This is lossless for revision statistics "
    "because SA values are frozen after ~7 years (measured, see docs/P4.md).",
    "BLS median standard errors are ANNUAL and published by major group only (Table 1V of the "
    "variance workbooks, via P5's p5_se). A component series is matched to its parent group "
    "with se_exact=0; the group SE is then a lower bound on that component's sampling error, "
    "so the 'within 1.5 SE of trend' share for those series is conservative (too low).",
    "The SE covers SAMPLING error only. It says nothing about seasonal-adjustment uncertainty, "
    "imputation, or nonresponse -- the revision statistics on this page are a separate and "
    "largely additional source of uncertainty in a single print.",
    "'Not distinguishable from trend' is a descriptive flag (gap < 1.5 x median SE), not a "
    "hypothesis test: the trailing mean is itself estimated, and the SE is a median across "
    "cells rather than a standard error of this particular month's change.",
]


# ---------------------------------------------------------------- fetching

def alfred_page(sid, force=False):
    """Return (vintage dates 'YYYY-MM-DD', obs_start_date, obs_end_date, series title).
    The form validates obs_start/obs_end against the series' own span and silently re-renders
    the HTML page (HTTP 200) with an <li> error instead of returning the zip, so we must echo
    the page's own defaults back rather than passing a generous range."""
    path, _ = fetch(ALFRED % sid, RAWP4 / f"{sid}.page.html", force=force)
    h = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'id="form_selected_vintage_dates".*?</select>', h, re.S)
    if not m:
        raise RuntimeError(f"{sid}: no vintage-date select on the ALFRED page")
    dates = re.findall(r'value="(\d{4}-\d\d-\d\d)"', m.group(0))
    os_ = re.search(r'id="form_obs_start_date"[^>]*value="(\d{4}-\d\d-\d\d)"', h)
    oe = re.search(r'id="form_obs_end_date"[^>]*value="(\d{4}-\d\d-\d\d)"', h)
    t = re.search(r"<title>\s*Download Data for\s*(.*?)\s*\|", h, re.S)
    title = re.sub(r"\s+", " ", t.group(1)) if t else sid
    if not dates or not os_ or not oe:
        raise RuntimeError(f"{sid}: could not read vintage dates / obs date range")
    return sorted(dates), os_.group(1), oe.group(1), title


def alfred_bulk(sid, dates, obs_start, obs_end):
    """POST the download form; return a wide DataFrame indexed by obs month PeriodIndex,
    one column per vintage date (string 'YYYY-MM-DD')."""
    url = ALFRED % sid
    body = [("form[units]", "lin"), ("form[obs_start_date]", obs_start),
            ("form[obs_end_date]", obs_end), ("form[file_type]", "2"),
            ("form[file_format]", "csv"), ("form[download_data]", "Download data")]
    body += [("form[selected_vintage_dates][]", d) for d in dates]
    errs = []
    for attempt in range(3):
        r = _s.post(url, data=body, timeout=900, headers={"Referer": url})
        if r.status_code == 200 and r.content[:2] == b"PK":
            break
        errs = re.findall(r"<li>([^<]{5,140})</li>", r.text)[:3] if r.content[:2] != b"PK" else []
        log.warning("%s: ALFRED POST attempt %d gave %s %s %s", sid, attempt + 1, r.status_code,
                    r.headers.get("Content-Type"), errs)
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"{sid}: ALFRED download form did not return a zip {errs}")
    (RAWP4 / f"{sid}.{dates[-1]}.zip").write_bytes(r.content)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    csvname = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
    df = pd.read_csv(io.BytesIO(z.read(csvname)))
    df["observation_date"] = pd.to_datetime(df.observation_date)
    df = df.set_index("observation_date").sort_index()
    # complete monthly index so shift(1) is a true calendar lag even if a month is skipped
    df.index = pd.PeriodIndex(df.index, freq="M")
    df = df.reindex(pd.period_range(df.index.min(), df.index.max(), freq="M"))
    ren = {}
    for c in df.columns:
        m = re.search(r"_(\d{8})$", c)
        if m:
            ren[c] = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
    df = df[list(ren)].rename(columns=ren)
    return df.apply(pd.to_numeric, errors="coerce")


def ingest(con, sid, backfill, force):
    """Download the vintages we do not have yet and store levels + MoM. Returns n new vintages."""
    have = con.execute("SELECT MAX(vintage_date) FROM p4_vintage WHERE series_id=?", (sid,)).fetchone()[0]
    dates, obs_start, obs_end, title = alfred_page(sid, force=force)
    want = dates if (backfill or not have) else [d for d in dates if d > have]
    if not want:
        log.info("%-15s up to date (%d vintages, latest %s)", sid, len(dates), have)
        return 0, dates, title
    log.info("%-15s pulling %d vintage(s) %s..%s (page lists %d, obs %s..%s)",
             sid, len(want), want[0], want[-1], len(dates), obs_start, obs_end)
    wide = alfred_bulk(sid, want, obs_start, obs_end)
    mom = (wide / wide.shift(1) - 1) * 100          # calendar-aligned; Oct-2025 gap -> NaN

    lv, lm = [], []
    for vd in wide.columns:
        cutoff = pd.Period(vd[:7], freq="M") - RETAIN_MONTHS
        col, mcol = wide[vd], mom[vd]
        keep = col.index >= cutoff
        for p, v in col[keep].dropna().items():
            lv.append((sid, vd, f"{p}-01", float(v)))
        for p, v in mcol[keep].dropna().items():
            lm.append((sid, str(p), vd, float(v)))
    con.executemany("INSERT OR REPLACE INTO p4_vintage VALUES(?,?,?,?)", lv)
    con.executemany("INSERT OR REPLACE INTO p4_mom VALUES(?,?,?,?)", lm)
    con.commit()
    log.info("%-15s stored %d level rows, %d mom rows", sid, len(lv), len(lm))
    return len(want), dates, title


# ---------------------------------------------------------------- analysis

def r1(x):
    """Round to 0.1, half away from zero (BLS prints 0.35 as 0.4, not 0.4-banker's-0.4)."""
    return np.sign(x) * np.floor(np.abs(x) * 10 + 0.5) / 10


def build_revisions(con, sid):
    m = pd.read_sql("SELECT obs_month, vintage_date, mom FROM p4_mom WHERE series_id=? "
                    "ORDER BY obs_month, vintage_date", con, params=(sid,))
    if m.empty:
        return pd.DataFrame()
    m["vd"] = pd.to_datetime(m.vintage_date)
    # the oldest archived vintage also carries back-history; only its newest obs month is a
    # genuine first print, everything older was already revised before ALFRED saw it
    v0 = m.vintage_date.min()
    m0 = m.loc[m.vintage_date == v0, "obs_month"].max()
    recs = []
    for om, g in m.groupby("obs_month", sort=True):
        g = g.sort_values("vd")
        first, fv = g.mom.iloc[0], g.vd.iloc[0]
        latest = g.mom.iloc[-1]
        later = g[g.vd >= fv + pd.Timedelta(days=365)]
        a1 = float(later.mom.iloc[0]) if len(later) else None
        recs.append((sid, om, float(first), g.vintage_date.iloc[0], a1, float(latest),
                     None if a1 is None else a1 - float(first), float(latest) - float(first),
                     len(g), int(om >= m0)))
    con.execute("DELETE FROM p4_revision WHERE series_id=?", (sid,))
    con.executemany("INSERT INTO p4_revision(series_id, obs_month, first_print, first_vintage, "
                    "after_1y, latest, rev_1y, rev_latest, n_vintages, true_first) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)", recs)
    con.commit()
    df = pd.DataFrame(recs, columns=["series_id", "obs_month", "first_print", "first_vintage",
                                     "after_1y", "latest", "rev_1y", "rev_latest", "n_vintages",
                                     "true_first"])
    n_cens = int((df.true_first == 0).sum())
    if n_cens:
        log.info("%-15s %d obs months before the first archived vintage (%s, through %s) "
                 "excluded from stats", sid, n_cens, v0, m0)
    return df[df.true_first == 1].reset_index(drop=True)


def build_transitions(con, sid, rev):
    if rev.empty:
        return {}
    d = rev.dropna(subset=["first_print", "latest"]).copy()
    d["fb"] = r1(d.first_print.values)
    d["lb"] = r1(d.latest.values)
    tab = d.groupby(["fb", "lb"]).size().reset_index(name="n")
    con.execute("DELETE FROM p4_transition WHERE series_id=?", (sid,))
    con.executemany("INSERT INTO p4_transition VALUES(?,?,?,?)",
                    [(sid, f"{r.fb:.1f}", f"{r.lb:.1f}", int(r.n)) for r in tab.itertuples()])
    con.commit()
    rows = []
    for fb, g in tab.groupby("fb"):
        n = int(g.n.sum())
        same = int(g[np.isclose(g.lb, fb)].n.sum())
        rows.append({"first": f"{fb:.1f}", "n": n,
                     "to": {f"{r.lb:.1f}": int(r.n) for r in g.sort_values("lb").itertuples()},
                     "share_changed": round(1 - same / n, 4)})
    rows.sort(key=lambda r: float(r["first"]))
    tot = int(tab.n.sum())
    same_tot = int(tab[np.isclose(tab.fb, tab.lb)].n.sum())
    return {"n": tot, "share_changed": round(1 - same_tot / tot, 4), "rows": rows}


def se_lookup(con):
    """(year, item) -> median SE of the 1-month change, from P5's p5_se (annual, Table 1V)."""
    se = pd.read_sql("SELECT month, item, se FROM p5_se WHERE horizon='1 Month' "
                     "AND period_type='annual' AND se IS NOT NULL", con)
    if se.empty:
        log.warning("p5_se is empty or has no '1 Month' rows -- SE flags will be skipped")
        return {}, []
    se["year"] = se.month.str[:4].astype(int)
    d = {(r.year, r.item): float(r.se) for r in se.itertuples()}
    return d, sorted(se.year.unique())


def build_seflag(con, sid, rev, setab, seyears):
    """Real-time comparison: first-print MoM vs the trailing 12-month mean of MoM *in that same
    vintage*, against the BLS median 1-month SE for the matching major group."""
    item = SERIES[sid][1]
    if not setab or not any((y, item) in setab for y in seyears):
        return None, pd.DataFrame()
    mom = pd.read_sql("SELECT obs_month, vintage_date, mom FROM p4_mom WHERE series_id=?",
                      con, params=(sid,))
    by_v = {vd: g.set_index("obs_month").mom for vd, g in mom.groupby("vintage_date")}
    recs = []
    for r in rev.itertuples():
        s = by_v.get(r.first_vintage)
        if s is None:
            continue
        p = pd.Period(r.obs_month, freq="M")
        prev = [str(p - k) for k in range(1, 13)]
        vals = s.reindex(prev).dropna()
        if len(vals) < 9:                     # Oct-2025 costs at most 2 of the 12
            continue
        y = int(r.obs_month[:4])
        sy = y if (y, item) in setab else max([q for q in seyears if (q, item) in setab and q <= y]
                                              or [min(q for q in seyears if (q, item) in setab)])
        se = setab[(sy, item)]
        gap = abs(r.first_print - vals.mean())
        recs.append((sid, r.obs_month, float(r.first_print), float(vals.mean()), int(len(vals)),
                     se, sy, float(gap), int(gap < 1.5 * se)))
    con.execute("DELETE FROM p4_seflag WHERE series_id=?", (sid,))
    con.executemany("INSERT INTO p4_seflag VALUES(?,?,?,?,?,?,?,?,?)", recs)
    con.commit()
    df = pd.DataFrame(recs, columns=["series_id", "obs_month", "first_print", "trail12", "n_trail",
                                     "se", "se_year", "gap", "within"])
    w = df[df.obs_month >= SE_SINCE]
    summary = None
    if len(w):
        latest_se = setab.get((max(q for q in seyears if (q, item) in setab), item))
        summary = {"since": SE_SINCE, "n": int(len(w)), "n_within": int(w.within.sum()),
                   "share_within": round(float(w.within.mean()), 4),
                   "se_1m": latest_se, "se_year": int(max(q for q in seyears if (q, item) in setab)),
                   "se_item": item, "se_exact": SERIES[sid][2]}
    return summary, df


WINDOWS = {"full": "0000-00", "2011+": "2011-01", "2019+": "2019-01"}


def stats_block(d):
    x = d.rev_latest.dropna().values
    if len(x) < 3:
        return None
    a1 = d.rev_1y.dropna().values
    fp, lt = d.first_print.values, d.latest.values
    return {"n": int(len(x)),
            "mean_rev": round(float(x.mean()), 4),
            "mean_abs_rev": round(float(np.abs(x).mean()), 4),
            "sd_rev": round(float(x.std(ddof=1)), 4),
            "p10": round(float(np.percentile(x, 10)), 4),
            "p50": round(float(np.percentile(x, 50)), 4),
            "p90": round(float(np.percentile(x, 90)), 4),
            "p90_abs": round(float(np.percentile(np.abs(x), 90)), 4),
            "mean_abs_rev_1y": round(float(np.abs(a1).mean()), 4) if len(a1) else None,
            "share_abs_ge_0_1": round(float((np.abs(x) >= 0.1).mean()), 4),
            "share_abs_ge_0_2": round(float((np.abs(x) >= 0.2).mean()), 4),
            "share_sign_flip": round(float(((fp > 0) != (lt > 0)).mean()), 4)}


def fan_block(con, sid):
    om = [r[0] for r in con.execute(
        "SELECT DISTINCT obs_month FROM p4_mom WHERE series_id=? ORDER BY obs_month DESC LIMIT ?",
        (sid, FAN_MONTHS))][::-1]
    if not om:
        return None
    q = ",".join("?" * len(om))
    d = pd.read_sql(f"SELECT obs_month, vintage_date, mom FROM p4_mom WHERE series_id=? "
                    f"AND obs_month IN ({q})", con, params=[sid] + om)
    piv = d.pivot(index="vintage_date", columns="obs_month", values="mom").reindex(columns=om).sort_index()
    return {"obs_months": om, "vintages": list(piv.index),
            "mom": [[None if pd.isna(v) else round(float(v), 3) for v in row] for row in piv.values]}


def validate(con):
    """Newest CPIAUCSL vintage MoM vs p0's cpi_item_month.mom_sa for SA0, last 24 months."""
    vd = con.execute("SELECT MAX(vintage_date) FROM p4_mom WHERE series_id='CPIAUCSL'").fetchone()[0]
    a = pd.read_sql("SELECT obs_month ym, mom FROM p4_mom WHERE series_id='CPIAUCSL' AND vintage_date=?",
                    con, params=(vd,))
    p0 = pd.read_sql("SELECT ym, mom_sa FROM cpi_item_month WHERE item_code='SA0' AND mom_sa IS NOT NULL", con)
    j = a.merge(p0, on="ym").sort_values("ym").tail(24)
    if j.empty:
        log.warning("validation: no overlap between ALFRED CPIAUCSL and p0 SA0")
        return {"check": "p4_alfred_vs_p0_mom_sa", "n": 0, "max_abs_diff": None, "ok": False, "detail": []}
    j["diff"] = j.mom - j.mom_sa
    mx = float(j["diff"].abs().max())
    ok = mx < 0.01
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    con.executemany("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    [(now, "p4_alfred_vs_p0_mom_sa", r.ym, float(r.mom), float(r.mom_sa),
                      float(r.diff), int(abs(r.diff) < 0.01)) for r in j.itertuples()])
    con.commit()
    log.info("validate: ALFRED %s vs p0 SA0 mom_sa over %d months -- max |diff| = %.5f pp %s",
             vd, len(j), mx, "OK" if ok else "MISMATCH")
    for r in j[j["diff"].abs() > 0.005].itertuples():
        log.info("  %s alfred %+.3f vs p0 %+.3f (%+.3f)", r.ym, r.mom, r.mom_sa, r.diff)
    return {"check": "p4_alfred_vs_p0_mom_sa", "vintage": vd, "n": int(len(j)),
            "max_abs_diff": round(mx, 5), "ok": bool(ok),
            "detail": [{"ym": r.ym, "alfred": round(float(r.mom), 3), "p0": round(float(r.mom_sa), 3),
                        "diff": round(float(r.diff), 4)} for r in j.itertuples()]}


def main(argv):
    args = set(argv)
    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    con = init_db()
    con.executescript(SCHEMA_P4)
    con.commit()
    migrate(con)
    RAWP4.mkdir(parents=True, exist_ok=True)
    setab, seyears = se_lookup(con)
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")

    out_series, transitions, fans, se_series = [], {}, {}, {}
    for sid, (label, se_item, se_exact) in SERIES.items():
        title = sid
        if "--no-fetch" not in args:
            try:
                _, dates, title = ingest(con, sid, "--backfill" in args, "--force" in args)
            except Exception as e:
                log.warning("%-15s ingest failed (%s: %s) -- using stored vintages", sid, type(e).__name__, e)
            time.sleep(2)
        rev = build_revisions(con, sid)
        if rev.empty:
            log.warning("%-15s no vintages stored, skipped", sid)
            continue
        nv = con.execute("SELECT COUNT(DISTINCT vintage_date), MIN(vintage_date), MAX(vintage_date) "
                         "FROM p4_vintage WHERE series_id=?", (sid,)).fetchone()
        con.execute("INSERT OR REPLACE INTO p4_series VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (sid, label, title, se_item, se_exact, nv[0], nv[1], nv[2], len(rev), now))
        con.commit()

        rev["moy"] = rev.obs_month.str[5:7].astype(int)
        rev["yr"] = rev.obs_month.str[:4].astype(int)
        stats = {}
        for w, lo in WINDOWS.items():
            b = stats_block(rev[rev.obs_month >= lo])
            if b:
                stats[w] = b
        moy = []
        for m in range(1, 13):
            g = rev[(rev.moy == m) & rev.rev_latest.notna()]
            moy.append({"m": m, "n": int(len(g)),
                        "mean_rev": round(float(g.rev_latest.mean()), 4) if len(g) else None,
                        "mean_abs_rev": round(float(g.rev_latest.abs().mean()), 4) if len(g) else None,
                        "p90_abs": round(float(np.percentile(g.rev_latest.abs(), 90)), 4) if len(g) >= 3 else None})
        by_year = [{"year": int(y), "n": int(len(g)),
                    "mean_rev": round(float(g.rev_latest.mean()), 4),
                    "mean_abs_rev": round(float(g.rev_latest.abs().mean()), 4)}
                   for y, g in rev[rev.rev_latest.notna()].groupby("yr")]

        sesum, sedf = build_seflag(con, sid, rev, setab, seyears)
        if len(sedf):
            se_series[sid] = [{"obs_month": r.obs_month, "first_print": round(r.first_print, 3),
                               "trail12": round(r.trail12, 3), "se": r.se, "within": int(r.within)}
                              for r in sedf[sedf.obs_month >= SE_SERIES_SINCE].itertuples()]
        transitions[sid] = build_transitions(con, sid, rev)
        f = fan_block(con, sid)
        if f:
            fans[sid] = f
        out_series.append({"series_id": sid, "label": label, "title": title,
                           "first_vintage": nv[1], "last_vintage": nv[2], "n_vintages": nv[0],
                           "n_obs_months": int(len(rev)),
                           "first_obs_month": rev.obs_month.min(), "last_obs_month": rev.obs_month.max(),
                           "se_item": se_item, "se_exact": se_exact,
                           "stats": stats, "by_month_of_year": moy, "by_year": by_year,
                           "se_flag": sesum})
        s = stats.get("2011+") or stats.get("full")
        log.info("%-15s %-28s n=%4d  mean|rev|=%.3f  p90|rev|=%.3f  sign flips %.1f%%  within1.5SE %s",
                 sid, label, s["n"], s["mean_abs_rev"], s["p90_abs"], 100 * s["share_sign_flip"],
                 f"{100*sesum['share_within']:.0f}%" if sesum else "n/a")

    val = validate(con)
    S = {s["series_id"]: s for s in out_series}

    def headline(sid, w="full"):
        s = S.get(sid)
        if not s:
            return None
        b = s["stats"].get(w) or s["stats"].get("full")
        t = next((r for r in transitions.get(sid, {}).get("rows", []) if r["first"] == "0.4"), None)
        return {"window": w, "n": b["n"], "mean_abs_rev": b["mean_abs_rev"], "p90_abs_rev": b["p90_abs"],
                "sd_rev": b["sd_rev"], "share_abs_ge_0_1": b["share_abs_ge_0_1"],
                "first_print_0_4": {"n": t["n"], "share_changed": t["share_changed"], "to": t["to"]} if t else None,
                "se_1m": (s["se_flag"] or {}).get("se_1m"),
                "share_within_1p5se_2019plus": (s["se_flag"] or {}).get("share_within")}

    summary = {"headline_CPIAUCSL": headline("CPIAUCSL"), "core_CPILFESL": headline("CPILFESL"),
               "note": "stats over all genuine first prints (true_first=1); see series[].stats for "
                       "the 2011+ / 2019+ windows, which are the comparable ones across series"}
    doc = {"generated_at": now, "summary": summary,
           "source": {"name": "ALFRED (Federal Reserve Bank of St. Louis) vintage archive",
                      "series_page": "https://alfred.stlouisfed.org/series/downloaddata?seid=<SERIES_ID>",
                      "method": "download form POST, file_type=2 (observations by vintage date), zipped CSV; no API key",
                      "retain_months": RETAIN_MONTHS,
                      "se_source": "P5 p5_se — BLS annual variance tables, Table 1V median SE of the 1-month change"},
           "windows": list(WINDOWS),
           "series": out_series, "transitions": transitions, "fan": fans,
           "se_series": se_series, "validation": val, "caveats": CAVEATS}
    p = OUT / "p4_vintages.json"
    p.write_text(json.dumps(doc, allow_nan=False), encoding="utf-8")
    log.info("wrote %s (%.0f KB)", p, p.stat().st_size / 1024)
    return 0 if val["ok"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
