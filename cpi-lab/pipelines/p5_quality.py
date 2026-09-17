#!/usr/bin/env python3
"""P5 — CPI instrument health / data quality.

  p5_quality.py [--force] [--no-se] [--no-events]

Tracks how the CPI is being *collected*, not what it says. Four BLS source families:

  1. Imputation source distribution (monthly, Jan-2019+)   — imputation-source-201901-present.xlsx
  2. Response / collection rates (monthly, Jan-2019+)      — monthly-response-rates-201901-present.xlsx
  3. Median standard errors (ANNUAL, 2019+)                — variance-estimates/<year>.xlsx (2019 = PDF)
  4. CPI notices (event annotations)                       — bls.gov/cpi/notices/

THE ONE THING NOT TO GET WRONG
------------------------------
The imputation tables are a *percent distribution of imputation sources* — of the imputations that
happened, what method was used. BLS says so explicitly on the source page: "They do not represent an
overall imputation rate for each survey."  "different cell = 37%" means 37% OF THE IMPUTATIONS used a
different-cell donor pool. It does NOT mean 37% of the CPI was imputed, and nothing here supports a
sentence of the form "X% of the CPI is guessed".
The *rate* comes from the response-rate tables instead (share of targeted quotes/units not collected),
and even that is an unweighted count share of price quotes, not a share of the index by expenditure
weight, and imputed price *changes* are borrowed from observed price changes of similar items —
not invented.

TABLES (all idempotent, full rebuild each run)
  p5_imputation(month, survey, source, pct)        percent distribution *of imputations*, per survey
  p5_response(month, metric, value, unit, source)  long-format collection/response metrics
  p5_mode(month, survey, mode, pct)                percent distribution of collection modes
  p5_se(month, item, horizon, se, median_change, period_type)
        annual median standard error of published price change; month='<year>-12', period_type='annual'
  p5_events(date, title, url, category, impact)    CPI notices scraped from the notices index
  p5_stress(month, component, z, pp, composite, composite_pp)   instrument-stress indicator (see below)

INSTRUMENT STRESS INDICATOR (an indicator, not a measure)
  Four monthly components, each z-scored against its own Jan–Dec 2019 mean and SD, all oriented so
  that higher = more of the index resting on imputation:
      domain "cs"       cs_different_cell      different-cell share of C&S imputations   (quality of donor pool)
                        cs_imputed_share       % of targeted C&S quotes not collected    (quantity imputed)
      domain "housing"  housing_noninterview   non-interview share of housing imputations
                        housing_imputed_share  (vacant+other)/(reported+vacant+other) of targeted units
  composite = mean over domains of (mean of that domain's available component z's), so C&S and Housing
  each get half the weight regardless of how many of their components survived the fetch.
  It is a unitless stress score with 0 = the 2019 collection environment. It is NOT an error bar on
  the CPI, NOT a bias estimate, and has no units of inflation.
  READ THE MAGNITUDES WITH CARE: 2019 was a very flat year (component SDs ~0.8-1.2 pp, and the
  imputation shares are published as whole percents, so part of that SD is rounding). Dividing a
  ~15 pp move by a ~1 pp baseline SD produces z's in the teens and thirties. Those are NOT "sigmas"
  in any probability sense — the series are trending and autocorrelated. Read the shape and the
  ordering, not the number of standard deviations. Every row therefore also carries `pp`, the plain
  percentage-point deviation from the 2019 mean, and `composite_pp`, the same domain-balanced average
  in percentage points — that is the number to put in front of a human.
  Standard errors are deliberately NOT in the composite: they are published annually, so they cannot be
  z-scored against a 12-month 2019 baseline. SE inflation is reported separately as a ratio vs 2019.

OUTPUT  $CPI_ROOT/out/p5_quality.json
  {
    "generated_at": iso8601, "pipeline": "p5_quality", "baseline": "2019-01..2019-12",
    "sources":     [{"name","url","parsed":bool,"note"}],
    "definitions": {metric: {"label","definition","not":"what it does not mean","source"}},
    "series": {
      "imputation_cs":      [{"month","home_cell","different_cell","carry_forward"}],
      "imputation_housing": [{"month","non_interview","vacancy"}],
      "response":           {metric: [{"month","value"}]},          # percent unless metric ends _count
      "modes_cs" / "modes_housing": [{"month", <mode>: pct}],
      "stress":             [{"month","composite","components":{name:z}}]
    },
    "se": {"baseline_year":2019, "items":[{"item","horizon","by_year":{yr:se},"ratio_vs_2019"}]},
    "latest": {...headline values with plain-English wording...},
    "events": [{"date","title","url","category","impact"}],
    "caveats": [...]
  }
"""
import sys, re, json, datetime as dt
import pandas as pd
from common import *

IMP_XLSX = "https://www.bls.gov/cpi/tables/imputation-source-201901-present.xlsx"
IMP_PAGE = "https://www.bls.gov/cpi/tables/imputation.htm"
RR_XLSX = "https://www.bls.gov/cpi/tables/response-rates/monthly-response-rates-201901-present.xlsx"
RR_PAGE = "https://www.bls.gov/cpi/tables/response-rates/home.htm"
MODE_XLSX = "https://www.bls.gov/cpi/tables/collection-modes-201901-present.xlsx"
VAR_PAGE = "https://www.bls.gov/cpi/tables/variance-estimates/home.htm"
VAR_YEAR = "https://www.bls.gov/cpi/tables/variance-estimates/%d.xlsx"
VAR_CURRENT = "https://www.bls.gov/web/cpi/cpi-variance.xlsx"   # rolling latest year; year read from title
VAR_2019_PDF = "https://www.bls.gov/cpi/tables/variance-estimates/2019.pdf"
NOTICES = "https://www.bls.gov/cpi/notices/"

RAWP5 = RAW / "p5"
BASELINE = [f"2019-{m:02d}" for m in range(1, 13)]
SE_ITEMS = ["all items", "food and beverages", "housing", "apparel", "transportation", "medical care",
            "recreation", "education and communication", "other goods and services",
            "all items less food and energy", "energy"]
# 2019 Table 1V All items, median standard error of the median price change, U.S. city average.
# Fallback only (used if the 2019 PDF cannot be parsed); verified against the published PDF.
SE_2019_FALLBACK = {("all items", "1 Month"): 0.04, ("all items", "2 Month"): 0.05,
                    ("all items", "6 Month"): 0.07, ("all items", "12 Month"): 0.08}

SCHEMA_P5 = """
CREATE TABLE IF NOT EXISTS p5_imputation(month TEXT, survey TEXT, source TEXT, pct REAL, PRIMARY KEY(month, survey, source));
CREATE TABLE IF NOT EXISTS p5_response(month TEXT, metric TEXT, value REAL, unit TEXT, source TEXT, PRIMARY KEY(month, metric));
CREATE TABLE IF NOT EXISTS p5_mode(month TEXT, survey TEXT, mode TEXT, pct REAL, PRIMARY KEY(month, survey, mode));
CREATE TABLE IF NOT EXISTS p5_se(month TEXT, item TEXT, horizon TEXT, se REAL, median_change REAL, period_type TEXT, PRIMARY KEY(month, item, horizon));
CREATE TABLE IF NOT EXISTS p5_events(date TEXT, title TEXT, url TEXT PRIMARY KEY, category TEXT, impact INT);
CREATE TABLE IF NOT EXISTS p5_stress(month TEXT, component TEXT, z REAL, pp REAL, composite REAL, composite_pp REAL, PRIMARY KEY(month, component));
"""

SOURCES = []          # [{name,url,parsed,note}] — filled as we go; every source may fail independently


def note_source(name, url, parsed, note=""):
    SOURCES.append({"name": name, "url": url, "parsed": bool(parsed), "note": note})
    (log.info if parsed else log.warning)("source %s parsed=%s %s", name, parsed, note)


# ---------------------------------------------------------------- parsers

def _ym_from_datelike(v):
    """Excel datetime cell -> 'YYYY-MM'."""
    if isinstance(v, (dt.datetime, dt.date, pd.Timestamp)):
        return f"{v.year:04d}-{v.month:02d}"
    return None


def _ym_from_text(v):
    """'January 2019' -> '2019-01'."""
    if not isinstance(v, str):
        return None
    try:
        d = dt.datetime.strptime(v.strip(), "%B %Y")
    except ValueError:
        return None
    return f"{d.year:04d}-{d.month:02d}"


def pct_dist_sheet(path, sheet, ymfun=_ym_from_datelike, header_row=1):
    """Parse the BLS 'percent distribution' layout: title row(s), a header row, then Month + N columns.

    Returns DataFrame(month, <col>...) with numeric columns; blank months (Oct-2025) dropped."""
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    cols = [str(c).strip() for c in df.iloc[header_row].tolist()]
    out = []
    for _, r in df.iloc[header_row + 1:].iterrows():
        ym = ymfun(r[0])
        if not ym:
            continue
        vals = {}
        for j, name in enumerate(cols[1:], start=1):
            v = pd.to_numeric(r[j], errors="coerce")
            if pd.notna(v):
                vals[name] = float(v)
        if vals:
            out.append({"month": ym, **vals})
    return pd.DataFrame(out)


def load_imputation(con, force):
    p, _ = fetch(IMP_XLSX, RAWP5 / "imputation-source.xlsx", force=force)
    rows, out = [], {}
    for sheet, survey, keymap in [
            ("Commodities and Services", "cs",
             {"Home cell": "home_cell", "Different cell": "different_cell", "Carry forward": "carry_forward"}),
            ("Housing", "housing", {"Non-interview": "non_interview", "Vacancy": "vacancy"})]:
        df = pct_dist_sheet(p, sheet)
        df = df.rename(columns=keymap)
        keep = [c for c in keymap.values() if c in df.columns]
        tot = df[keep].sum(axis=1)
        bad = df[(tot - 100).abs() > 2]
        if len(bad):
            log.warning("imputation %s: %d months whose sources do not sum to ~100 (e.g. %s)",
                        survey, len(bad), bad.iloc[0].to_dict())
        for _, r in df.iterrows():
            for c in keep:
                rows.append((r.month, survey, c, float(r[c])))
        out[survey] = df[["month"] + keep]
    con.executemany("INSERT OR REPLACE INTO p5_imputation VALUES(?,?,?,?)", rows)
    con.commit()
    note_source("imputation source distribution", IMP_XLSX, True,
                f"{len(rows)} rows, {out['cs'].month.min()}..{out['cs'].month.max()}")
    return out


def load_response(con, force):
    """Response-rate workbook -> long p5_response. Percentages stored as 0-100, counts as counts."""
    p, _ = fetch(RR_XLSX, RAWP5 / "monthly-response-rates.xlsx", force=force)
    sheets = {
        "CPI C&S Quote response rates": ("cs_quote", {
            "Targeted quotes": ("cs_quotes_targeted_count", "count", 1),
            "Collected quotes": ("cs_quotes_collected_count", "count", 1),
            "Non-responding quotes": ("cs_quotes_nonresponding_count", "count", 1),
            "Quotes used in estimation": ("cs_quotes_used_count", "count", 1),
            "Percent collected": ("cs_quote_collection_rate", "percent", 100),
            "Percent non-responding": ("cs_imputed_share", "percent", 100),
            "Percent used in estimation": ("cs_quote_estimation_rate", "percent", 100)}),
        "CPI C&S Outlet response rates": ("cs_outlet", {
            "Targeted outlets": ("cs_outlets_targeted_count", "count", 1),
            "Percent Collected": ("cs_outlet_collection_rate", "percent", 100),
            "Percent collected": ("cs_outlet_collection_rate", "percent", 100),
            "Percent non-responding": ("cs_outlet_nonresponse", "percent", 100),
            "Percent used in estimation": ("cs_outlet_estimation_rate", "percent", 100)}),
        "CPI Housing response rates": ("housing", {
            "Units targeted for collection": ("housing_units_targeted_count", "count", 1),
            "Percent data reported": ("housing_reported", "percent", 100),
            "Percent vacant": ("housing_vacant", "percent", 100),
            "Percent other (not interviewed, not vacant)": ("housing_other", "percent", 100),
            "Total percent used in estimation": ("housing_used_in_estimation", "percent", 100)}),
    }
    rows = []
    for sheet, (tag, keymap) in sheets.items():
        df = pct_dist_sheet(p, sheet, ymfun=_ym_from_text, header_row=2)
        for _, r in df.iterrows():
            for col, (metric, unit, scale) in keymap.items():
                if col in df.columns and pd.notna(r.get(col)):
                    rows.append((r.month, metric, float(r[col]) * scale, unit, "response_rates"))
    con.executemany("INSERT OR REPLACE INTO p5_response VALUES(?,?,?,?,?)", rows)
    con.commit()

    # derived: share of targeted housing units in estimation whose rent was imputed (vacant + other)
    w = pd.read_sql("SELECT month, metric, value FROM p5_response WHERE unit='percent'", con)
    w = w.pivot(index="month", columns="metric", values="value")
    if {"housing_reported", "housing_vacant", "housing_other", "housing_used_in_estimation"} <= set(w.columns):
        # BLS: reported + vacant + other = total used in estimation. Check it, then derive.
        chk = (w.housing_reported + w.housing_vacant + w.housing_other - w.housing_used_in_estimation).abs()
        log.info("housing identity reported+vacant+other == used_in_estimation: max |diff| = %.4f pp", chk.max())
        d = (100 * (w.housing_vacant + w.housing_other) / w.housing_used_in_estimation).dropna()
        con.executemany("INSERT OR REPLACE INTO p5_response VALUES(?,?,?,?,?)",
                        [(m, "housing_imputed_share", float(v), "percent", "derived") for m, v in d.items()])
        con.commit()
    months = sorted({r[0] for r in rows})
    note_source("response / collection rates", RR_XLSX, True,
                f"{len(rows)} rows, {months[0]}..{months[-1]}" if months else "no rows")
    return True


def load_modes(con, force):
    p, _ = fetch(MODE_XLSX, RAWP5 / "collection-modes.xlsx", force=force)
    rows = []
    for sheet, survey in [("Commodities and Services", "cs"), ("Housing", "housing")]:
        df = pct_dist_sheet(p, sheet)
        for _, r in df.iterrows():
            for c in df.columns:
                if c != "month" and pd.notna(r[c]):
                    rows.append((r.month, survey, c.strip().lower().replace(" ", "_"), float(r[c])))
    con.executemany("INSERT OR REPLACE INTO p5_mode VALUES(?,?,?,?)", rows)
    con.commit()
    months = sorted({r[0] for r in rows})
    note_source("collection modes", MODE_XLSX, True,
                f"{len(rows)} rows, {months[0]}..{months[-1]} (BLS updates this file less often than the "
                f"others — expect it to lag the imputation series)" if months else "no rows")


# ---------------------------------------------------------------- standard errors (annual)

HORIZONS = ["1 Month", "2 Month", "6 Month", "12 Month"]


def _norm_item(s):
    return re.sub(r"[\s.]+$", "", re.sub(r"\s+", " ", str(s).strip())).lower()


def se_from_xlsx(path, year=None):
    """Table 1V (U.S. city average): col0 indent, col1 item, cols2..9 = change/se x 4 horizons.

    The reference year is taken from the table title ("...intervals, 2025") so that the rolling
    'current year' workbook cannot be filed under the wrong year."""
    df = pd.read_excel(path, sheet_name="Table 1V", header=None)
    m = re.search(r"(20\d\d)\s*$", str(df.iat[0, 1]).strip())
    if m:
        year = int(m.group(1))
    elif year is None:
        raise RuntimeError(f"cannot determine year for {path.name}")
    out = []
    for _, r in df.iterrows():
        name = _norm_item(r[1]) if isinstance(r[1], str) else None
        if name not in SE_ITEMS:
            continue
        for k, h in enumerate(HORIZONS):
            chg, se = pd.to_numeric(r[2 + 2 * k], errors="coerce"), pd.to_numeric(r[3 + 2 * k], errors="coerce")
            if pd.notna(se):
                out.append((f"{year}-12", name, h, float(se), None if pd.isna(chg) else float(chg), "annual"))
    return out


LEADER = re.compile(r"^(?P<name>.+?)\s*\.{3,}\s*(?P<nums>[-\d.\s]+)$")


def se_from_pdf_2019(path):
    """2019 is PDF-only. Text extraction + dot-leader regex, Table 1V pages only."""
    import pdfplumber
    out, in_1v = [], False
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            m = re.search(r"Table (\d+)V\.", txt)
            if m:
                in_1v = m.group(1) == "1"
            if not in_1v:
                continue
            for line in txt.split("\n"):
                mm = LEADER.match(line.strip())
                if not mm:
                    continue
                name = _norm_item(mm.group("name"))
                if name not in SE_ITEMS:
                    continue
                nums = [float(x) for x in mm.group("nums").split()]
                if len(nums) != 8:
                    continue
                for k, h in enumerate(HORIZONS):
                    out.append(("2019-12", name, h, nums[2 * k + 1], nums[2 * k], "annual"))
    return out


def variance_years(force):
    """Which annual variance workbooks exist? Read the links off the page rather than guessing years
    (guessing costs a 30 s retry storm on next January's not-yet-published file)."""
    try:
        from bs4 import BeautifulSoup
        p, _ = fetch(VAR_PAGE, RAWP5 / "variance-home.htm", force=force)
        soup = BeautifulSoup(p.read_text(errors="replace"), "lxml")
        ys = {int(m.group(1)) for a in soup.find_all("a", href=True)
              if (m := re.search(r"variance-estimates/(20\d\d)\.xlsx$", a["href"]))}
        if ys:
            return sorted(ys)
        log.warning("variance page listed no .xlsx years — falling back to a year scan")
    except Exception as e:
        log.warning("variance page unreadable (%s) — falling back to a year scan", e)
    return list(range(2020, dt.date.today().year + 1))


def load_se(con, force):
    rows, years_ok = [], []
    try:
        p, _ = fetch(VAR_2019_PDF, RAWP5 / "variance-2019.pdf", force=force)
        r = se_from_pdf_2019(p)
        if not r:
            raise RuntimeError("no rows matched in PDF")
        rows += r
        years_ok.append(2019)
    except Exception as e:
        log.warning("2019 variance PDF unusable (%s) — using hardcoded All-items baseline", e)
        rows += [("2019-12", i, h, v, None, "annual") for (i, h), v in SE_2019_FALLBACK.items()]
        years_ok.append("2019(fallback)")
    for y in variance_years(force):
        try:
            p, _ = fetch(VAR_YEAR % y, RAWP5 / f"variance-{y}.xlsx", force=force)
            r = se_from_xlsx(p, y)
            if r:
                rows += r
                years_ok.append(int(r[0][0][:4]))
        except Exception as e:
            log.info("variance %d not available (%s)", y, type(e).__name__)
    try:   # rolling "current year" workbook: newest year can appear here before it is archived
        p, _ = fetch(VAR_CURRENT, RAWP5 / "variance-current.xlsx", force=force)
        r = se_from_xlsx(p)
        if r and int(r[0][0][:4]) not in years_ok:
            rows += r
            years_ok.append(int(r[0][0][:4]))
    except Exception as e:
        log.info("current-year variance workbook unavailable (%s)", type(e).__name__)
    if not rows:
        note_source("variance / standard errors", VAR_PAGE, False, "no year parsed")
        return False
    con.executemany("INSERT OR REPLACE INTO p5_se VALUES(?,?,?,?,?,?)", rows)
    con.commit()
    note_source("variance / standard errors", VAR_PAGE, True,
                f"annual, years {years_ok}; {len(rows)} rows")
    return True


# ---------------------------------------------------------------- events

CATS = [("shutdown", r"shutdown|lapse in appropriation"),
        ("collection", r"collection reduction|collection mode|alternative collection|sample"),
        ("covid", r"covid|coronavirus"),
        ("data_quality", r"missing consumer expenditure|cnstat|committee on national statistics|expert panel|variance|response rate"),
        ("correction", r"correction|errata"),
        ("seasonal", r"seasonal factor"),
        ("methodology", r"methodology|weight|rebasing|geographic revision|publication change|title change|"
                        r"titles for .*will change|renaming|supplemental files|discontinu|new vehicles index|imputation"),
        ("research", r"^research |r-cpi|r-hicp|experimental"),
        ("outreach", r"conference|webinar|forum|registration|jsm|presenters|users. conference|duac")]
HIGH = {"shutdown", "collection", "covid", "data_quality"}
LI_DATE = re.compile(r"\((\d{2})/(\d{2})/(\d{4})\)\s*$")


def categorize(title):
    t = title.lower()
    for cat, pat in CATS:
        if re.search(pat, t):
            return cat
    return "other"


def load_events(con, force):
    from bs4 import BeautifulSoup
    p, _ = fetch(NOTICES, RAWP5 / "notices.htm", force=True)   # index page has no useful Last-Modified
    soup = BeautifulSoup(p.read_text(errors="replace"), "lxml")
    rows, seen = [], set()
    for li in soup.find_all("li"):
        a = li.find("a", href=True)
        if not a or "/cpi/notices/" not in a["href"]:
            continue
        text = " ".join(li.get_text().split())
        m = LI_DATE.search(text)
        if not m:
            continue
        date = f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
        title = LI_DATE.sub("", text).strip()
        url = a["href"]
        url = "https://www.bls.gov" + url if url.startswith("/") else url
        if url in seen:
            continue
        seen.add(url)
        cat = categorize(title)
        rows.append((date, title, url, cat, int(cat in HIGH)))
    if not rows:
        note_source("CPI notices", NOTICES, False, "no dated notices found — page layout changed?")
        return False
    con.execute("DELETE FROM p5_events")
    con.executemany("INSERT OR REPLACE INTO p5_events VALUES(?,?,?,?,?)", rows)
    con.commit()
    note_source("CPI notices", NOTICES, True,
                f"{len(rows)} notices, {min(r[0] for r in rows)}..{max(r[0] for r in rows)}")
    return True


# ---------------------------------------------------------------- stress indicator

COMPONENTS = [  # (name, domain, table-expression)
    ("cs_different_cell", "cs"),
    ("cs_imputed_share", "cs"),
    ("housing_noninterview", "housing"),
    ("housing_imputed_share", "housing"),
]


def build_stress(con):
    imp = pd.read_sql("SELECT month, survey, source, pct FROM p5_imputation", con)
    resp = pd.read_sql("SELECT month, metric, value FROM p5_response WHERE unit='percent'", con)
    s = {}
    if len(imp):
        w = imp.pivot_table(index="month", columns=["survey", "source"], values="pct")
        if ("cs", "different_cell") in w:
            s["cs_different_cell"] = w[("cs", "different_cell")]
        if ("housing", "non_interview") in w:
            s["housing_noninterview"] = w[("housing", "non_interview")]
    if len(resp):
        r = resp.pivot(index="month", columns="metric", values="value")
        for m in ("cs_imputed_share", "housing_imputed_share"):
            if m in r.columns:
                s[m] = r[m]
    if not s:
        log.warning("stress: no components available")
        return pd.DataFrame(), {}
    X = pd.DataFrame(s).sort_index()
    Z, P, stats = pd.DataFrame(index=X.index), pd.DataFrame(index=X.index), {}
    for c in X.columns:
        base = X.loc[X.index.isin(BASELINE), c].dropna()
        if len(base) < 6 or base.std(ddof=0) == 0:
            log.warning("stress: component %s has no usable 2019 baseline (n=%d) — dropped", c, len(base))
            continue
        mu, sd = float(base.mean()), float(base.std(ddof=0))
        Z[c], P[c] = (X[c] - mu) / sd, X[c] - mu
        stats[c] = {"mean_2019": round(mu, 2), "sd_2019": round(sd, 2), "n_2019": int(len(base)),
                    "latest": round(float(X[c].dropna().iloc[-1]), 2),
                    "latest_pp": round(float(P[c].dropna().iloc[-1]), 2),
                    "latest_z": round(float(Z[c].dropna().iloc[-1]), 1)}
        log.info("stress component %-24s baseline 2019 mean=%.2f sd=%.2f  latest=%.2f (%+.1f pp, z=%.1f)",
                 c, mu, sd, X[c].dropna().iloc[-1], P[c].dropna().iloc[-1], Z[c].dropna().iloc[-1])
    if Z.empty:
        return pd.DataFrame(), {}
    doms = {}
    for name, dom in COMPONENTS:
        if name in Z.columns:
            doms.setdefault(dom, []).append(name)
    comp = pd.DataFrame({d: Z[cols].mean(axis=1) for d, cols in doms.items()}).mean(axis=1, skipna=True)
    comp_pp = pd.DataFrame({d: P[cols].mean(axis=1) for d, cols in doms.items()}).mean(axis=1, skipna=True)
    rows = []
    for m in Z.index:
        c = None if pd.isna(comp.get(m)) else float(comp[m])
        cpp = None if pd.isna(comp_pp.get(m)) else float(comp_pp[m])
        for name in Z.columns:
            if pd.notna(Z.at[m, name]):
                rows.append((m, name, float(Z.at[m, name]), float(P.at[m, name]), c, cpp))
        if c is not None:
            rows.append((m, "_composite", c, cpp, c, cpp))
    con.execute("DELETE FROM p5_stress")
    con.executemany("INSERT OR REPLACE INTO p5_stress VALUES(?,?,?,?,?,?)", rows)
    con.commit()
    log.info("stress: %d months, components %s", len(Z), list(Z.columns))
    out = pd.DataFrame({"composite": comp, "composite_pp": comp_pp,
                        **{c: Z[c] for c in Z.columns}, **{c + "__pp": P[c] for c in Z.columns}})
    return out, stats


# ---------------------------------------------------------------- output

DEFS = {
    "imputation_source_distribution": {
        "label": "Imputation source mix",
        "definition": "Of the price observations that BLS had to impute in a month, the percent that used "
                      "each imputation method. C&S: home cell (same item category, same area), different "
                      "cell (same item category, wider geography), carry forward (last month's price). "
                      "Housing: non-interview (occupied unit, no data obtained) vs vacancy.",
        "not": "NOT the share of the CPI that is imputed. BLS states on the source page: 'They do not "
               "represent an overall imputation rate for each survey.' A different-cell share of 37% means "
               "37% of the imputations used a wider donor pool, not that 37% of the index was imputed.",
        "source": IMP_PAGE},
    "cs_imputed_share": {
        "label": "C&S quotes not collected (imputed)",
        "definition": "Percent of targeted Commodities & Services price quotes for which no price was "
                      "collected in the month (BLS 'percent non-responding'). These quotes' price changes "
                      "are imputed from observed price changes of similar items.",
        "not": "Not a share of the CPI by expenditure weight — response rates are unweighted counts of "
               "price quotes and exclude items priced from non-survey (transaction/alternative) data. "
               "An imputed quote borrows an observed price change; it is not a guessed price level. "
               "It is also a slight OVER-statement of the imputed share: BLS notes that responding plus "
               "imputed quotes do not sum to 100%, most often because some quotes were initiated but not "
               "yet priced, and those sit in the non-responding count without being imputed.",
        "source": RR_PAGE},
    "cs_quote_collection_rate": {
        "label": "C&S quote collection rate",
        "definition": "Collected quotes / targeted quotes.", "not": "", "source": RR_PAGE},
    "cs_quote_estimation_rate": {
        "label": "C&S quote estimation rate",
        "definition": "Quotes used in estimation / targeted quotes. Per BLS, this numerator adds "
                      "carry-forward-imputed and substitution quotes and removes rejected quotes; home-cell "
                      "and different-cell imputations are NOT counted in it.",
        "not": "Not comparable to the collection rate as a 'data quality' delta without that adjustment.",
        "source": RR_PAGE},
    "cs_outlet_collection_rate": {
        "label": "C&S outlet collection rate",
        "definition": "Percent of targeted outlets (stores/websites) from which any price was collected.",
        "not": "", "source": RR_PAGE},
    "housing_imputed_share": {
        "label": "Rent units with imputed rent",
        "definition": "(vacant + other) / (data reported + vacant + other) of targeted housing units. "
                      "'Other' = occupied unit, no data obtained (refusal/no contact); its rent change is "
                      "imputed from units in the same rent class and area. 'Vacant' units get a separate "
                      "market-rent imputation. Derived by P5 from the BLS response-rate table.",
        "not": "Not the share of the shelter index that is fabricated — imputed units borrow the measured "
               "rent change of comparable units, and shelter also uses the six-month rent-change panel.",
        "source": RR_PAGE},
    "housing_used_in_estimation": {
        "label": "Housing units used in estimation",
        "definition": "Percent of targeted rent units that entered the index (reported + vacant + other).",
        "not": "", "source": RR_PAGE},
    "collection_modes": {
        "label": "Collection mode mix",
        "definition": "Percent distribution of how collected prices were obtained: personal visit, "
                      "telephone, online (C&S); personal visit, telephone (Housing).",
        "not": "Not a quality ranking of modes; BLS treats all collected prices as observations.",
        "source": "https://www.bls.gov/cpi/tables/collection-modes.htm"},
    "se": {
        "label": "Median standard error of price change",
        "definition": "BLS variance tables: the median (across the year's published changes) standard error "
                      "of the CPI price change, by item and horizon, U.S. city average. Published ANNUALLY, "
                      "one value per calendar year (stored at month = '<year>-12').",
        "not": "Not a monthly series, and not a total error — it is sampling error only. It does not cover "
               "nonresponse bias, which is exactly the risk that rising imputation raises.",
        "source": VAR_PAGE},
    "stress_composite": {
        "label": "Instrument stress indicator",
        "definition": "Mean of two domain scores (C&S, Housing); each domain score is the mean of its "
                      "components' z-scores against that component's Jan-Dec 2019 mean and standard "
                      "deviation. Components: C&S different-cell share of imputations, C&S share of targeted "
                      "quotes not collected, housing non-interview share of imputations, housing share of "
                      "units with imputed rent. 0 = the 2019 collection environment. 'composite_pp' is the "
                      "same domain-balanced average expressed in percentage points above the 2019 mean, and "
                      "is the number to show a human.",
        "not": "An INDICATOR, not a measure. It is not an error bar, not a bias estimate, not a correction "
               "to the CPI, and has no units of inflation. A high value means more of the index rests on "
               "imputation than in 2019; it says nothing about the direction of any resulting error. "
               "The z-scores are NOT sigmas in a probability sense: 2019 was nearly flat (component SDs "
               "~0.8-1.2 pp, partly rounding, since the imputation shares are published as whole percents), "
               "so ordinary moves divide out to double-digit z. Read shape and ordering, not sigma counts.",
        "source": "P5 construction (see docs/P5.md)"},
}

CAVEATS = [
    "Imputation-source shares are a distribution AMONG imputations, not the share of the index imputed.",
    "Response rates are unweighted counts of price quotes/units, not expenditure-weighted shares of the CPI.",
    "October 2025 is blank in every monthly source (lapse in appropriations); it is omitted, never interpolated.",
    "Standard errors are annual and cover sampling error only; they are reported separately and are NOT part "
    "of the stress composite (an annual number cannot be z-scored against a 12-month 2019 baseline).",
    "Rising imputation raises the RISK of nonresponse bias; none of these series measures such a bias.",
    "Stress z-scores are large because the 2019 baseline is nearly flat; they are not probability sigmas. "
    "Quote composite_pp (percentage points above 2019) to a general audience.",
    "Part of the fall in collection rates is by design: BLS cut the collection sample in 2025 (see events), "
    "and targeted quote counts fall alongside collected ones. This is a policy change, not only a refusal wave.",
]


def to_json(con, stress, stats):
    q = lambda s, **k: pd.read_sql(s, con, **k)
    imp = q("SELECT month, survey, source, pct FROM p5_imputation ORDER BY month")
    resp = q("SELECT month, metric, value, unit FROM p5_response ORDER BY month")
    modes = q("SELECT month, survey, mode, pct FROM p5_mode ORDER BY month")
    se = q("SELECT month, item, horizon, se, median_change FROM p5_se ORDER BY month")
    ev = q("SELECT date, title, url, category, impact FROM p5_events ORDER BY date DESC")

    def wide(df, survey):
        d = df[df.survey == survey].pivot(index="month", columns="source" if "source" in df else "mode", values="pct")
        return [{"month": m, **{c: (None if pd.isna(v) else v) for c, v in r.items()}} for m, r in d.iterrows()]

    def wide_mode(survey):
        d = modes[modes.survey == survey].pivot(index="month", columns="mode", values="pct")
        return [{"month": m, **{c: (None if pd.isna(v) else v) for c, v in r.items()}} for m, r in d.iterrows()]

    resp_series = {m: [{"month": r.month, "value": r.value} for _, r in g.iterrows()]
                   for m, g in resp.groupby("metric")}
    latest_month = max([m for m in imp.month] or [None])

    # SE by year + inflation vs 2019
    se_out = []
    if len(se):
        for (item, hz), g in se.groupby(["item", "horizon"]):
            by = {int(m[:4]): float(v) for m, v in zip(g.month, g.se)}
            base = by.get(2019)
            se_out.append({"item": item, "horizon": hz, "by_year": by,
                           "ratio_vs_2019": (round(max(by.items())[1] / base, 3) if base else None),
                           "latest_year": max(by), "latest_se": by[max(by)]})

    stress_out, zcols = [], [c for c in stress.columns
                             if c not in ("composite", "composite_pp") and not c.endswith("__pp")]
    if len(stress):
        for m, r in stress.iterrows():
            rnd = lambda v, n=3: (None if pd.isna(v) else round(float(v), n))
            stress_out.append({"month": m, "composite": rnd(r.composite), "composite_pp": rnd(r.composite_pp, 2),
                               "components": {c: rnd(r[c]) for c in zcols},
                               "components_pp": {c: rnd(r[c + "__pp"], 2) for c in zcols},
                               # how many components actually fed this month's composite vs how many
                               # exist: n_components < n_components_total means a source dropped out and
                               # the composite is averaged over fewer inputs (a quiet degradation).
                               "n_components": int(sum(1 for c in zcols if pd.notna(r[c]))),
                               "n_components_total": len(zcols)})

    def lastval(metric):
        g = resp[resp.metric == metric]
        return None if g.empty else {"month": g.iloc[-1].month, "value": round(float(g.iloc[-1].value), 2)}

    def base_mean(metric):
        g = resp[(resp.metric == metric) & resp.month.isin(BASELINE)]
        return None if g.empty else round(float(g.value.mean()), 2)

    def imp_last(survey, source):
        g = imp[(imp.survey == survey) & (imp.source == source)]
        return None if g.empty else {"month": g.iloc[-1].month, "value": float(g.iloc[-1].pct)}

    def imp_base(survey, source):
        g = imp[(imp.survey == survey) & (imp.source == source) & imp.month.isin(BASELINE)]
        return None if g.empty else round(float(g.pct.mean()), 2)

    latest = {
        "month": latest_month,
        "cs_different_cell": {"latest": imp_last("cs", "different_cell"), "mean_2019": imp_base("cs", "different_cell"),
                              "says": "share OF THE IMPUTATIONS that used a different-cell donor pool"},
        "housing_noninterview": {"latest": imp_last("housing", "non_interview"),
                                 "mean_2019": imp_base("housing", "non_interview"),
                                 "says": "share OF THE HOUSING IMPUTATIONS that were non-interviews"},
        "cs_imputed_share": {"latest": lastval("cs_imputed_share"), "mean_2019": base_mean("cs_imputed_share"),
                             "says": "percent of targeted C&S price quotes with no collected price"},
        "housing_imputed_share": {"latest": lastval("housing_imputed_share"),
                                  "mean_2019": base_mean("housing_imputed_share"),
                                  "says": "percent of rent units in estimation whose rent was imputed"},
        "cs_quote_collection_rate": {"latest": lastval("cs_quote_collection_rate"),
                                     "mean_2019": base_mean("cs_quote_collection_rate")},
        "cs_outlet_collection_rate": {"latest": lastval("cs_outlet_collection_rate"),
                                      "mean_2019": base_mean("cs_outlet_collection_rate")},
        "stress_composite": (stress_out[-1] if stress_out else None),
    }
    doc = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "pipeline": "p5_quality", "baseline": "2019-01..2019-12",
           "sources": SOURCES, "definitions": DEFS, "caveats": CAVEATS,
           "series": {"imputation_cs": wide(imp, "cs"), "imputation_housing": wide(imp, "housing"),
                      "response": resp_series, "modes_cs": wide_mode("cs"),
                      "modes_housing": wide_mode("housing"), "stress": stress_out},
           "stress_baseline_stats": stats,
           "se": {"baseline_year": 2019, "period_type": "annual", "items": se_out},
           "latest": latest,
           "events": [{"date": r.date, "title": r.title, "url": r.url, "category": r.category,
                       "impact": int(r.impact)} for _, r in ev.iterrows()]}
    path = OUT / "p5_quality.json"
    path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    log.info("wrote %s (%d KB)", path, path.stat().st_size // 1024)
    return doc


def migrate(con):
    """CREATE TABLE IF NOT EXISTS silently keeps an outdated shape. Every p5_* table is rebuilt from
    source on each run, so if the columns no longer match the schema above, just drop and recreate."""
    for stmt in SCHEMA_P5.strip().split(";"):
        m = re.search(r"CREATE TABLE IF NOT EXISTS (\w+)\((.*)\)", stmt.strip(), re.S)
        if not m:
            continue
        table = m.group(1)
        want = [c.strip().split()[0] for c in re.split(r",\s*(?![^()]*\))", m.group(2))
                if not c.strip().upper().startswith("PRIMARY KEY")]
        have = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        if have and have != want:
            log.warning("migrating %s: columns %s -> %s (table is rebuilt from source)", table, have, want)
            con.execute(f"DROP TABLE {table}")
    con.commit()


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    force = "--force" in argv
    RAWP5.mkdir(parents=True, exist_ok=True)
    con = init_db()
    migrate(con)
    con.executescript(SCHEMA_P5)
    con.commit()
    new_pull(con, "p5_quality", "instrument health")

    ok_primary = False
    try:                                    # 1. imputation source distribution (PRIMARY)
        load_imputation(con, force)
        ok_primary = True
    except Exception as e:
        log.error("imputation XLSX failed: %s", e)
        note_source("imputation source distribution", IMP_XLSX, False, str(e)[:200])
    for fn, name, url in [(load_response, "response / collection rates", RR_XLSX),
                          (load_modes, "collection modes", MODE_XLSX)]:
        try:
            fn(con, force)
        except Exception as e:
            log.error("%s failed: %s", name, e)
            note_source(name, url, False, str(e)[:200])
    if "--no-se" not in argv:
        try:
            load_se(con, force)
        except Exception as e:
            log.error("variance failed: %s", e)
            note_source("variance / standard errors", VAR_PAGE, False, str(e)[:200])
    if "--no-events" not in argv:
        try:
            load_events(con, force)
        except Exception as e:
            log.error("notices failed: %s", e)
            note_source("CPI notices", NOTICES, False, str(e)[:200])

    stress, stats = build_stress(con)
    doc = to_json(con, stress, stats)
    l = doc["latest"]
    log.info("LATEST %s | different-cell %s%% (2019 %s) | C&S quotes not collected %s%% (2019 %s) | "
             "housing imputed %s%% (2019 %s) | stress z=%s (%s pp)",
             l["month"], (l["cs_different_cell"]["latest"] or {}).get("value"), l["cs_different_cell"]["mean_2019"],
             (l["cs_imputed_share"]["latest"] or {}).get("value"), l["cs_imputed_share"]["mean_2019"],
             (l["housing_imputed_share"]["latest"] or {}).get("value"), l["housing_imputed_share"]["mean_2019"],
             (l["stress_composite"] or {}).get("composite"), (l["stress_composite"] or {}).get("composite_pp"))
    if not ok_primary:
        log.error("PRIMARY source (imputation XLSX) failed this run")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
