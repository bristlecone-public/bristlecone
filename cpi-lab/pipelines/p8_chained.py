#!/usr/bin/env python3
"""P8 - substitution: C-CPI-U (Toernqvist, superlative) vs CPI-U (Laspeyres-type) at item level.

  p8_chained.py [--history] [--force] [--no-vintages]

--history      (re)build the published-vintage panel from the full BLS supplemental-file
               archive (13 yearly zips, ~45 MB, cached). Implied when p8_vintage is empty.
--force        re-download the su.* flat files and rebuild everything even if unchanged.
--no-vintages  skip the supplemental-file vintage/revision step entirely (flat files only).

WHAT THIS MEASURES
------------------
The CPI-U aggregates item indexes with fixed (lagged) expenditure weights - a modified
Laspeyres.  The C-CPI-U aggregates the *same* item indexes with a Toernqvist formula that
uses expenditure shares in both the base and the current period, so it reflects how
households shifted spending between categories as relative prices moved.  For any published
category the difference

    gap_yoy = CPI-U 12-month % change  -  C-CPI-U 12-month % change      (percentage points)

is positive when the fixed-weight measure rises faster than the superlative one.  Across the
all-items index that difference is conventionally described as *upper-level substitution*
(plus formula and weight-update-timing effects - see docs/P8.md, it is NOT a clean estimate
of consumer substitution alone).

DATA
----
https://download.bls.gov/pub/time.series/su/   (Chained CPI-U, survey "SU")
  su.item       29 item codes, same code scheme as cu.item (SA0, SAF11, SETA01, ...)
  su.series     29 series, all SUUR0000<item>: U.S. city average (0000), monthly (R),
                NSA only (U), base "DECEMBER 1999=100"
  su.data.0.Current / su.data.1.AllItems - byte-identical; the whole survey is one file.
  su.footnote   I = Initial, U = Interim.  A BLANK footnote code = FINAL.
  su.area/su.base/su.periodicity/su.seasonal - single-row mapping files.
There is no fine-grained (SE....) C-CPI-U on the flat file: BLS publishes the chained index
for 29 aggregates only, so "item level" here means those 29, not the ~179 CPI leaf strata.

THREE-STAGE PUBLICATION
-----------------------
The C-CPI-U needs current-period expenditure data, which arrive with a lag, so every month is
published three ways: Initial (with the month itself), Interim (revised each quarter with the
Jan/Apr/Jul/Oct releases), Final (~10-12 months later).  The flat file carries only the
*current* stage of each month, in the footnote_codes column of su.data (I / U / blank).  We
therefore (a) store every pull as a vintage in p8_obs so future revisions become visible, and
(b) reconstruct historical vintages from the BLS monthly supplemental tables
https://www.bls.gov/cpi/tables/supplemental-files/c-cpi-u-YYYYMM.xlsx (Table 1C), which print
the index as it stood at that publication.  xlsx from 2021-11, PDF 2017-07..2021-10, nothing
earlier.  No single consolidated BLS "C-CPI-U revision history" table exists (searched).

TABLES
------
p8_obs(series_id, year, period, value, footnote, pull_id)      vintaged; PK includes pull_id
p8_obs_latest                                                  view, MAX(pull_id) per cell
p8_item(item_code, item_name, display_level, sort_sequence, section, group_code, group_name,
        is_partition, weight, weight_year)
     section: 'expenditure' (the 23 expenditure-category items) | 'special' (the 6 commodity
     and service group aggregates: SAC SAD SAN SAS SA0E SA0L1E).
     is_partition: member of the finest set of su items that still tiles 100% of the index
     (see partition() - 15 items; note SAT1 stays whole because su publishes only one of its
     children, so descending into SETA01 alone would leave a hole).
p8_gap(item_code, ym, cpi_u_yoy, ccpi_u_yoy, gap_yoy, cpi_u_idx_rel, ccpi_u_idx_rel,
       gap_cum, stage)
     *_idx_rel  = index rebased to 100 at 1999-12 (the C-CPI-U reference base)
     gap_cum    = (cpi_u_idx_rel / ccpi_u_idx_rel - 1) * 100, i.e. the cumulative percent by
                  which the fixed-weight index has outrun the superlative one since 1999-12
     stage      = 'initial' | 'interim' | 'final'
p8_vintage(item_code, ym, pub_ym, value, source)   as-published levels from supplemental tables
p8_revision(item_code, ym, initial, initial_pub, latest, latest_stage, rev_idx, rev_pct,
            rev_yoy_pp)
     initial->current revision of the level, and the implied revision to the 12-month change.

OUTPUT  $CPI_ROOT/out/p8_chained.json  (schema in json_out(), also mirrored in docs/P8.md)

Validation written to `validation`:
  p8_longrun_gap_pp_per_yr   our annualised all-items gap since 1999-12 vs the ~0.25pp
                             figure BLS/CBO cite
  p8_cpiu_yoy_matches_p0     our CPI-U all-items YoY vs cpi_item_month (must be 0)
  p8_ccpiu_yoy_vs_published  our C-CPI-U YoY vs the printed % change in the latest Table 1C
"""
import sys, re, io, zipfile, datetime as dt
import pandas as pd
import numpy as np
from common import *
from p0_fetch import read_tsv, norm

SU = BLS_TS + "su/"
SUPP = "https://www.bls.gov/cpi/tables/supplemental-files/"
BASE_YM = "1999-12"                      # C-CPI-U reference base
STAGE = {"": "final", "I": "initial", "U": "interim"}
MAJOR = {"SAF": "Food and beverages", "SAH": "Housing", "SAA": "Apparel",
         "SAT": "Transportation", "SAM": "Medical care", "SAR": "Recreation",
         "SAE": "Education and communication", "SAG": "Other goods and services"}
SPECIAL = {"SAC", "SAD", "SAN", "SAS", "SA0E", "SA0L1E"}

# The su item hierarchy, pinned explicitly.  cu_item cannot supply it: in cu.item every major
# group sits at display_level 0 (so nothing hangs off SA0 and p0's nearest-previous-level rule
# hands SAC/SAD/SAN/SAS/SA0E a spurious SAG parent), and su.item's own display levels flatten
# New vehicles into a sibling of Private transportation.  This mirrors the indent levels printed
# in BLS Table 1C, which are stable and authoritative for these 29 series.
PARENT = {
    "SA0": None,
    "SAF": "SA0", "SAF1": "SAF", "SAF11": "SAF1", "SEFV": "SAF1", "SAF116": "SAF",
    "SAH": "SA0", "SAH1": "SAH", "SAH2": "SAH", "SAH3": "SAH",
    "SAA": "SA0",
    "SAT": "SA0", "SAT1": "SAT", "SETA01": "SAT1", "SETG": "SAT",
    "SAM": "SA0", "SAM1": "SAM", "SAM2": "SAM",
    "SAR": "SA0",
    "SAE": "SA0", "SAE1": "SAE", "SAE2": "SAE",
    "SAG": "SA0",
    # commodity and service group: a second, overlapping partition of the same total
    "SAS": "SA0", "SAC": "SA0", "SAD": "SAC", "SAN": "SAC",
    "SA0L1E": None, "SA0E": None,
}

SCHEMA8 = """
CREATE TABLE IF NOT EXISTS p8_obs(series_id TEXT, year INT, period TEXT, value REAL,
    footnote TEXT, pull_id INT, PRIMARY KEY(series_id, year, period, pull_id));
CREATE INDEX IF NOT EXISTS p8_obs_sp ON p8_obs(series_id, year, period);
CREATE VIEW IF NOT EXISTS p8_obs_latest AS
  SELECT o.series_id, o.year, o.period, o.value, o.footnote, o.pull_id FROM p8_obs o
  JOIN (SELECT series_id, year, period, MAX(pull_id) pull_id FROM p8_obs GROUP BY 1,2,3) m
  USING(series_id, year, period, pull_id);
CREATE TABLE IF NOT EXISTS p8_item(item_code TEXT PRIMARY KEY, item_name TEXT,
    display_level INT, sort_sequence INT, section TEXT, group_code TEXT, group_name TEXT,
    is_partition INT, weight REAL, weight_year INT);
CREATE TABLE IF NOT EXISTS p8_gap(item_code TEXT, ym TEXT, cpi_u_yoy REAL, ccpi_u_yoy REAL,
    gap_yoy REAL, cpi_u_idx_rel REAL, ccpi_u_idx_rel REAL, gap_cum REAL, stage TEXT,
    PRIMARY KEY(item_code, ym));
CREATE TABLE IF NOT EXISTS p8_vintage(item_code TEXT, ym TEXT, pub_ym TEXT, value REAL,
    source TEXT, PRIMARY KEY(item_code, ym, pub_ym));
CREATE TABLE IF NOT EXISTS p8_revision(item_code TEXT, ym TEXT, initial REAL,
    initial_pub TEXT, latest REAL, latest_stage TEXT, rev_idx REAL, rev_pct REAL,
    rev_yoy_pp REAL, PRIMARY KEY(item_code, ym));
"""

MON = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def ym_add(ym, k):
    """Calendar month arithmetic on 'YYYY-MM' strings."""
    y, m = int(ym[:4]), int(ym[5:])
    t = y * 12 + (m - 1) + k
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def lag(df, col, k, key="item_code"):
    """Calendar-aligned k-month lag of df[col] (never row offsets - 2025-10 has no CPI)."""
    l = df[[key, "ym", col]].copy()
    l["ym"] = [ym_add(v, k) for v in l.ym]
    return df[[key, "ym"]].merge(l, on=[key, "ym"], how="left")[col].values


# ---------------------------------------------------------------- flat files

def load_su(con, force=False):
    """Fetch su.* and store one vintage of su.data. Returns (item df, changed)."""
    d = RAW / "su"
    item = read_tsv(fetch(SU + "su.item", d / "su.item", force=force)[0])
    series = read_tsv(fetch(SU + "su.series", d / "su.series", force=force)[0])
    fn = read_tsv(fetch(SU + "su.footnote", d / "su.footnote", force=force)[0])
    log.info("su.footnote map: %s (blank = Final)", dict(zip(fn.footnote_code, fn.footnote_text)))
    series["series_id"] = series.series_id.str.strip()
    keep = set(series[(series.area_code == "0000") & (series.periodicity_code == "R")].series_id)
    # su.data.0.Current and su.data.1.AllItems are byte-identical (checked); take AllItems.
    path, changed = fetch(SU + "su.data.1.AllItems", d / "su.data.1.AllItems", force=force)
    df = read_tsv(path)
    df["series_id"] = df.series_id.str.strip()
    n_all = len(df)
    df = df[df.series_id.isin(keep) & df.period.str.startswith("M") & (df.period != "M13")].copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["year"] = df["year"].astype(int)
    log.info("su.data.1.AllItems: %d rows (%d after dropping M13 annual averages), %d series, %s..%s",
             n_all, len(df), df.series_id.nunique(),
             f"{df.year.min()}", f"{df.year.max()}")
    if not changed and not force and con.execute("SELECT 1 FROM p8_obs LIMIT 1").fetchone():
        log.info("su.data unchanged; keeping existing vintages")
        return item, series, False
    pull = new_pull(con, "su.data.1.AllItems", "P8 C-CPI-U")
    latest = pd.read_sql("SELECT series_id, year, period, value AS old, footnote AS oldfn "
                         "FROM p8_obs_latest", con)
    m = df.merge(latest, on=["series_id", "year", "period"], how="left")
    # NB: unlike p0 we also store a row when only the STAGE changed (interim -> final with an
    # unchanged level is a real event for this pipeline).
    new = m[m.old.isna() | ((m.value - m.old).abs() > 1e-9) | (m.footnote_codes != m.oldfn.fillna(""))]
    con.executemany("INSERT OR REPLACE INTO p8_obs VALUES(?,?,?,?,?,?)",
                    [(r.series_id, int(r.year), r.period, float(r.value), r.footnote_codes, pull)
                     for r in new.itertuples()])
    con.commit()
    log.info("p8_obs: %d rows read, %d new/changed stored (pull %d)", len(df), len(new), pull)
    return item, series, True


def partition(codes, parent_of, weight):
    """Finest subset of `codes` that still tiles the whole index.

    Start at SA0 and replace a node by its `codes` children only when those children account
    for >=99% of the node's relative importance; otherwise keep the node whole.  With the su
    item set this yields 15 items (SAT1 is kept intact because su publishes only one of its
    children, New vehicles, so descending would drop motor fuel, used cars, insurance...)."""
    kids = {}
    for c in codes:
        p = c
        while True:
            p = parent_of.get(p)
            if p is None:
                break
            if p in codes:
                kids.setdefault(p, []).append(c)
                break
    out, stack = [], ["SA0"]
    while stack:
        c = stack.pop()
        ch = kids.get(c, [])
        wc, wch = weight.get(c), sum(weight.get(k, 0) or 0 for k in ch)
        if ch and wc and wch >= 0.99 * wc:
            stack.extend(ch)
        else:
            out.append(c)
    return set(out)


def build_items(con, item):
    """Map the 29 su items onto the hierarchy: major group, section, partition flag, weight."""
    cu = set(x[0] for x in con.execute("SELECT item_code FROM cu_item"))
    codes = set(item.item_code)
    if codes - cu:
        log.warning("su items absent from cu_item: %s", sorted(codes - cu))
    if codes - set(PARENT):
        log.warning("su items missing from the pinned PARENT map: %s", sorted(codes - set(PARENT)))
    parent_of = PARENT
    w = pd.read_sql("SELECT weight_year, item_code, weight_u FROM cpi_weight WHERE matched=1", con)
    wy = int(w.weight_year.max())
    wmap = dict(zip(w[w.weight_year == wy].item_code, w[w.weight_year == wy].weight_u))
    part = partition({c for c in codes if c not in SPECIAL}, parent_of, wmap)
    log.info("weights from cpi_weight weight_year=%d; complete partition = %d items (%.1f%% of "
             "relative importance): %s", wy, len(part), sum(wmap.get(c, 0) for c in part),
             ",".join(sorted(part)))
    rows = []
    for r in item.itertuples():
        c = r.item_code
        if c in SPECIAL:
            sec, gc, gn = "special", None, "Commodity and service group"
        else:
            sec, gc = "expenditure", None
            p = c
            while p is not None and gc is None:
                if p in MAJOR:
                    gc = p
                p = parent_of.get(p)
            gn = MAJOR.get(gc, "All items")
        rows.append((c, r.item_name, int(r.display_level), int(r.sort_sequence), sec, gc, gn,
                     int(c in part), wmap.get(c), wy))
    con.execute("DELETE FROM p8_item")
    con.executemany("INSERT INTO p8_item VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    log.info("p8_item: %d items (%d expenditure, %d special aggregates), all 8 major groups "
             "present: %s", len(rows), sum(r[4] == "expenditure" for r in rows),
             sum(r[4] == "special" for r in rows), sorted(MAJOR) == sorted(c for c in MAJOR if c in codes))
    return pd.DataFrame(rows, columns=["item_code", "item_name", "display_level", "sort_sequence",
                                       "section", "group_code", "group_name", "is_partition",
                                       "weight", "weight_year"])


# ---------------------------------------------------------------- the gap

def build_gap(con):
    su = pd.read_sql("""SELECT substr(series_id,9) AS item_code, year, period, value, footnote
                        FROM p8_obs_latest""", con)
    su["item_code"] = su.item_code.str.strip()
    su["ym"] = su.year.astype(str) + "-" + su.period.str[1:]
    su = su[["item_code", "ym", "value", "footnote"]].rename(columns={"value": "ccpi"})
    cu = pd.read_sql("SELECT item_code, ym, idx_nsa FROM cpi_item_month WHERE idx_nsa IS NOT NULL", con)
    m = su.merge(cu.rename(columns={"idx_nsa": "cpiu"}), on=["item_code", "ym"], how="inner")
    m = m.sort_values(["item_code", "ym"]).reset_index(drop=True)
    lost = sorted(set(su.item_code) - set(m.item_code))
    if lost:
        log.warning("su items with no CPI-U counterpart in cpi_item_month: %s", lost)
    m["cpiu_l12"] = lag(m, "cpiu", 12)
    m["ccpi_l12"] = lag(m, "ccpi", 12)
    m["cpi_u_yoy"] = (m.cpiu / m.cpiu_l12 - 1) * 100
    m["ccpi_u_yoy"] = (m.ccpi / m.ccpi_l12 - 1) * 100
    m["gap_yoy"] = m.cpi_u_yoy - m.ccpi_u_yoy
    base = m[m.ym == BASE_YM].set_index("item_code")
    nobase = sorted(set(m.item_code) - set(base.index))
    if nobase:
        log.warning("no %s observation (cannot rebase, gap_cum null): %s", BASE_YM, nobase)
    m["cpi_u_idx_rel"] = m.cpiu / m.item_code.map(base.cpiu) * 100
    m["ccpi_u_idx_rel"] = m.ccpi / m.item_code.map(base.ccpi) * 100
    m["gap_cum"] = (m.cpi_u_idx_rel / m.ccpi_u_idx_rel - 1) * 100
    m["stage"] = m.footnote.map(lambda f: STAGE.get((f or "").strip(), "unknown"))
    bad = m[m.stage == "unknown"].footnote.unique()
    if len(bad):
        log.warning("unrecognised footnote codes (stage): %s", bad)
    cols = ["item_code", "ym", "cpi_u_yoy", "ccpi_u_yoy", "gap_yoy", "cpi_u_idx_rel",
            "ccpi_u_idx_rel", "gap_cum", "stage"]
    con.execute("DELETE FROM p8_gap")
    con.executemany("INSERT INTO p8_gap VALUES(?,?,?,?,?,?,?,?,?)",
                    m[cols].astype(object).where(m[cols].notna(), None).values.tolist())
    con.commit()
    st = m[m.item_code == "SA0"].groupby("stage").ym.agg(["min", "max", "count"])
    log.info("p8_gap: %d rows, %d items, %s..%s", len(m), m.item_code.nunique(), m.ym.min(), m.ym.max())
    log.info("all-items stages:\n%s", st.to_string())
    return m[cols + ["cpiu", "ccpi"]]


# ------------------------------------------------- published vintages / revisions

def _name_map(item):
    """norm(name) -> item_code, plus a space-free key: pdfplumber loses the inter-word spaces
    in some vintages of Table 1C ('Allitems', 'Foodathome')."""
    m = {}
    for c, n in zip(item.item_code, item.item_name):
        k = norm(n)
        m[k] = c
        m[k.replace(" ", "")] = c
    return m


def _lookup(nm, name):
    n = norm(name)
    return nm.get(n) or nm.get(n.replace(" ", ""))


def _parse_month(s):
    mm = re.search(r"([A-Za-z]{3,9})\.?\s*\n?\s*(\d{4})", str(s))
    if not mm:
        return None
    k = MON.get(mm.group(1)[:3].lower())
    return f"{int(mm.group(2)):04d}-{k:02d}" if k else None


def parse_supp_xlsx(blob, nm, src):
    """Table 1C xlsx -> [(item_code, ym, value)] for both printed index columns."""
    df = pd.read_excel(io.BytesIO(blob), sheet_name=0, header=None)
    h = next((i for i in range(min(12, len(df)))
              if str(df.iat[i, 0]).strip().lower() == "indent level"), None)
    if h is None:
        raise ValueError("no 'Indent Level' header row")
    labs = [(c, _parse_month(df.iat[h + 1, c])) for c in range(2, df.shape[1])]
    cols = [(c, y) for c, y in labs if y][:2]          # first two month labels = the index cols
    if len(cols) != 2:
        raise ValueError(f"could not locate index columns ({labs})")
    out, unmatched = [], []
    for i in range(h + 2, len(df)):
        name = df.iat[i, 1]
        if not isinstance(name, str) or not name.strip():
            continue
        code = _lookup(nm, name)
        if code is None:
            if any(pd.notna(df.iat[i, c]) for c, _ in cols):
                unmatched.append(name.strip())
            continue
        for c, ym in cols:
            v = pd.to_numeric(df.iat[i, c], errors="coerce")
            if pd.notna(v):
                out.append((code, ym, float(v), src))
    return out, unmatched


NUM = re.compile(r"^-?[\d,]*\.\d+$|^-?[\d,]+$")


def parse_supp_pdf(blob, nm, ym, src):
    """Table 1C pdf -> [(item_code, ym, value)] for the CURRENT month column only.

    The two printed columns are (prev month, current month); prev is ambiguous when a month is
    skipped (2025-10), and the header layout is not reliably extractable, so we take only the
    current month, which is the one that matters (the Initial estimate)."""
    import pdfplumber
    out, unmatched = [], []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    for line in text.splitlines():
        toks = line.replace("—", " ").split()
        tail = []
        for t in reversed(toks):
            if NUM.match(t):
                tail.append(t)
            else:
                break
        if len(tail) < 5:
            continue
        tail = list(reversed(tail))[-5:]
        name = " ".join(toks[:len(toks) - 5]).strip(" .")
        code = _lookup(nm, name)
        if code is None:
            if 3 < len(name) < 60:
                unmatched.append(name)
            continue
        try:
            out.append((code, ym, float(tail[2].replace(",", "")), src))   # RI, prev, CURRENT, %, %
        except ValueError:
            pass
    return out, unmatched


def load_vintages(con, item, full=False):
    """Reconstruct as-published C-CPI-U levels from the BLS monthly supplemental tables."""
    nm, d = _name_map(item), RAW / "su" / "supp"
    have = {r[0] for r in con.execute("SELECT DISTINCT source FROM p8_vintage")}
    rows, unmatched, files = [], set(), 0

    idx, _ = fetch(SUPP, d / "index.html", force=True)
    page = idx.read_text(errors="ignore")
    links = re.findall(r'href="([^"]*c-cpi-u-(\d{6})\.(xlsx|pdf))"', page, re.I)
    for href, yyyymm, ext in links:
        src = f"c-cpi-u-{yyyymm}.{ext.lower()}"
        if src in have:
            continue
        url = href if href.startswith("http") else "https://www.bls.gov" + href
        try:
            p, _ = fetch(url, d / src, retries=2)
            blob = p.read_bytes()
            ym = f"{yyyymm[:4]}-{yyyymm[4:]}"
            r, u = (parse_supp_xlsx(blob, nm, src) if ext.lower() == "xlsx"
                    else parse_supp_pdf(blob, nm, ym, src))
            rows += r; unmatched |= set(u); files += 1
        except Exception as e:
            log.warning("supplemental %s failed: %s", src, e)

    if full:
        years = sorted({int(y) for y in re.findall(r'href="[^"]*archive-(\d{4})\.zip"', page)})
        log.info("supplemental archives on the index page: %s", years)
        for y in years:
            try:
                p, _ = fetch(f"{SUPP}archive-{y}.zip", d / f"archive-{y}.zip", retries=2)
            except Exception as e:
                log.warning("archive-%d.zip: %s", y, e); continue
            z = zipfile.ZipFile(p)
            names = [n for n in z.namelist() if re.search(r"c-cpi-u-\d{6}\.(xlsx|pdf)$", n, re.I)]
            if not names:
                log.info("archive-%d.zip: no C-CPI-U tables", y)
                continue
            for n in sorted(names):
                src = n.rsplit("/", 1)[-1].lower()
                if src in have:
                    continue
                yyyymm = re.search(r"(\d{6})", src).group(1)
                ym = f"{yyyymm[:4]}-{yyyymm[4:]}"
                try:
                    blob = z.read(n)
                    r, u = (parse_supp_xlsx(blob, nm, src) if src.endswith("xlsx")
                            else parse_supp_pdf(blob, nm, ym, src))
                    rows += r; unmatched |= set(u); files += 1
                except Exception as e:
                    log.warning("supplemental %s failed: %s", src, e)

    if rows:
        con.executemany("INSERT OR REPLACE INTO p8_vintage(item_code, ym, pub_ym, value, source) "
                        "VALUES(?,?,?,?,?)",
                        [(c, ym, "%s-%s" % (s[8:12], s[12:14]), v, s) for c, ym, v, s in rows])
        con.commit()
    n, mn, mx = con.execute("SELECT COUNT(*), MIN(pub_ym), MAX(pub_ym) FROM p8_vintage").fetchone()
    log.info("p8_vintage: +%d rows from %d new supplemental tables -> %d rows, pubs %s..%s",
             len(rows), files, n, mn, mx)
    if unmatched:
        log.info("supplemental rows with no su item code (expected: none): %s", sorted(unmatched)[:12])


def build_revisions(con):
    """initial (as first published) vs current level, per item x month."""
    v = pd.read_sql("SELECT item_code, ym, pub_ym, value FROM p8_vintage", con)
    cur = pd.read_sql("""SELECT substr(series_id,9) AS item_code, year, period, value, footnote
                         FROM p8_obs_latest""", con)
    cur["item_code"] = cur.item_code.str.strip()
    cur["ym"] = cur.year.astype(str) + "-" + cur.period.str[1:]
    cur["stage"] = cur.footnote.map(lambda f: STAGE.get((f or "").strip(), "unknown"))
    con.execute("DELETE FROM p8_revision")
    if v.empty:
        log.info("p8_revision: no vintages yet, nothing to compute")
        return pd.DataFrame()
    ini = v[v.pub_ym == v.ym]                      # the Initial estimate
    if ini.empty:
        log.info("p8_revision: no initial-vintage rows"); return pd.DataFrame()
    ini = ini.sort_values("pub_ym").groupby(["item_code", "ym"], as_index=False).first()
    m = ini.merge(cur[["item_code", "ym", "value", "stage"]], on=["item_code", "ym"],
                  how="inner", suffixes=("_ini", "_cur"))
    m["rev_idx"] = m.value_cur - m.value_ini
    m["rev_pct"] = (m.value_cur / m.value_ini - 1) * 100
    m = m.sort_values(["item_code", "ym"]).reset_index(drop=True)
    m["rev_yoy_pp"] = m.rev_pct - lag(m, "rev_pct", 12)
    con.executemany("INSERT OR REPLACE INTO p8_revision VALUES(?,?,?,?,?,?,?,?,?)",
                    [(r.item_code, r.ym, r.value_ini, r.pub_ym, r.value_cur, r.stage,
                      r.rev_idx, r.rev_pct, None if pd.isna(r.rev_yoy_pp) else r.rev_yoy_pp)
                     for r in m.itertuples()])
    con.commit()
    a = m[(m.item_code == "SA0")]
    fin = a[a.stage == "final"]
    log.info("p8_revision: %d item-months (%s..%s); all-items: %d months, %d now final",
             len(m), m.ym.min(), m.ym.max(), len(a), len(fin))
    if len(fin):
        log.info("all-items initial->FINAL level revision: mean %+.4f%%, median %+.4f%%, "
                 "mean |rev| %.4f%%, max |rev| %.4f%% (%s)",
                 fin.rev_pct.mean(), fin.rev_pct.median(), fin.rev_pct.abs().mean(),
                 fin.rev_pct.abs().max(), fin.loc[fin.rev_pct.abs().idxmax(), "ym"])
        fy = fin.dropna(subset=["rev_yoy_pp"])
        if len(fy):
            log.info("all-items revision to the 12-month change: mean %+.3f pp, mean |rev| %.3f pp,"
                     " max |rev| %.3f pp", fy.rev_yoy_pp.mean(), fy.rev_yoy_pp.abs().mean(),
                     fy.rev_yoy_pp.abs().max())
    # vintage-to-vintage revisions inside our OWN pull history (empty until BLS revises)
    own = pd.read_sql("""SELECT series_id, year, period, COUNT(*) n, MIN(value) lo, MAX(value) hi
                         FROM p8_obs GROUP BY 1,2,3 HAVING n>1""", con)
    log.info("own-pull vintages differing: %d series-months (%d with a level change)",
             len(own), int((own.hi - own.lo).abs().gt(1e-9).sum()) if len(own) else 0)
    return m


# ---------------------------------------------------------------- validation

def validate(con, g, item):
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    out, ok_all = {}, True

    def rec(name, ym, ours, pub, tol):
        nonlocal ok_all
        d = ours - pub
        ok = abs(d) < tol
        ok_all &= ok
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    (now, name, ym, ours, pub, d, int(ok)))
        log.info("validate %-26s %s ours %.4f published %.4f diff %+.4f %s",
                 name, ym, ours, pub, d, "OK" if ok else "MISMATCH")
        out[name] = dict(ym=ym, ours=ours, published=pub, diff=d, ok=bool(ok))

    a = g[g.item_code == "SA0"].set_index("ym")
    fin = g[(g.item_code == "SA0") & (g.stage == "final")]
    last_fin = fin.ym.max()
    last = a.index.max()
    # 1. long-run annualised gap, 1999-12 -> latest final month
    yrs = (int(last_fin[:4]) * 12 + int(last_fin[5:]) - (1999 * 12 + 12)) / 12
    cpi_a = (a.loc[last_fin, "cpi_u_idx_rel"] / 100) ** (1 / yrs) * 100 - 100
    cc_a = (a.loc[last_fin, "ccpi_u_idx_rel"] / 100) ** (1 / yrs) * 100 - 100
    log.info("annualised since %s (%.2f yr): CPI-U %.3f%%/yr, C-CPI-U %.3f%%/yr, cumulative "
             "gap %.2f%%", BASE_YM, yrs, cpi_a, cc_a, a.loc[last_fin, "gap_cum"])
    rec("p8_longrun_gap_pp_per_yr", last_fin, cpi_a - cc_a, 0.25, 0.10)
    out["longrun"] = dict(years=yrs, cpi_u_annual_pct=cpi_a, ccpi_u_annual_pct=cc_a,
                          gap_pp_per_year=cpi_a - cc_a, cum_gap_pct=a.loc[last_fin, "gap_cum"],
                          through=last_fin)

    # 2. our CPI-U all-items YoY must equal p0's cpi_item_month.yoy exactly (same source)
    p0 = pd.read_sql("SELECT ym, yoy FROM cpi_item_month WHERE item_code='SA0'", con).set_index("ym").yoy
    j = a.cpi_u_yoy.dropna()
    common = j.index.intersection(p0.dropna().index)
    dmax = (j[common] - p0[common]).abs().max()
    worst = (j[common] - p0[common]).abs().idxmax()
    rec("p8_cpiu_yoy_matches_p0", worst, float(dmax), 0.0, 1e-9)

    # 3. our C-CPI-U YoY vs the % change printed in the latest supplemental Table 1C
    try:
        d = RAW / "su" / "supp"
        cand = sorted(d.glob("c-cpi-u-*.xlsx"))
        if cand:
            f = cand[-1]
            df = pd.read_excel(f, sheet_name=0, header=None)
            h = next(i for i in range(12) if str(df.iat[i, 0]).strip().lower() == "indent level")
            labs = [(c, _parse_month(df.iat[h + 1, c])) for c in range(2, df.shape[1])]
            got = [(c, y) for c, y in labs if y]
            cur_ym, pct_col = got[1][1], got[2][0]
            row = next(i for i in range(h + 2, len(df))
                       if isinstance(df.iat[i, 1], str) and norm(df.iat[i, 1]) == "all items")
            pub = float(df.iat[row, pct_col])
            ours = float(g[(g.item_code == "SA0") & (g.ym == cur_ym)].ccpi_u_yoy.iloc[0])
            rec("p8_ccpiu_yoy_vs_published", cur_ym, ours, pub, 0.06)
    except Exception as e:
        log.warning("published-YoY cross-check skipped: %s", e)

    con.commit()
    out["latest_ym"] = last
    out["latest_stage"] = a.loc[last, "stage"]
    out["latest_final_ym"] = last_fin
    return out, ok_all


# ---------------------------------------------------------------- aggregates + json

def json_out(con, g, item, rev, val):
    """Schema of $CPI_ROOT/out/p8_chained.json

    { generated, source, base_ym, coverage:{items,expenditure,special,partition,partition_weight},
      stages:{ym:stage} for the last 24 months,
      items:[{item_code,item_name,group_code,group_name,section,is_partition,weight,weight_year,
              latest_gap_yoy, gap_cum, rank}],
      heatmap:{ months:[ym...120], items:[item_code...], z:[[gap_yoy per month] per item] },
      all_items:{ months:[], cpi_u_yoy:[], ccpi_u_yoy:[], gap_yoy:[], gap_cum:[], stage:[] },
      group_cum:{ group_code:{name, months:[], gap_cum:[], gap_yoy:[]} },
      ranking:{ as_of, stage, top15:[...], bottom15:[...], all:[...] },   # by 12-month gap
      cum_ranking:[ {item_code,item_name,gap_cum} ...],                   # by cumulative gap
      decomposition:{ ym, total_gap, weighted_component_gap, residual, parts:[...] },
      revisions:{ n, first_pub, last_pub, all_items:[{ym,initial,latest,stage,rev_idx,rev_pct,
                  rev_yoy_pp}], summary:{...} },
      validation:{...} }
    """
    it = item.set_index("item_code")
    last = g.ym.max()
    months = [ym_add(last, -k) for k in range(119, -1, -1)]
    piv = g.pivot_table(index="item_code", columns="ym", values="gap_yoy").reindex(columns=months)
    order = it.sort_values("sort_sequence").index.tolist()
    piv = piv.reindex([c for c in order if c in piv.index])
    fin_ym = g[(g.item_code == "SA0") & (g.stage == "final")].ym.max()
    latest_gap = g[g.ym == fin_ym].set_index("item_code")
    cumu = g[g.ym == last].set_index("item_code")

    def nn(x):
        return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else float(x)

    items = []
    for c in piv.index:
        items.append(dict(item_code=c, item_name=it.at[c, "item_name"],
                          group_code=it.at[c, "group_code"], group_name=it.at[c, "group_name"],
                          section=it.at[c, "section"], is_partition=int(it.at[c, "is_partition"]),
                          weight=nn(it.at[c, "weight"]), weight_year=int(it.at[c, "weight_year"]),
                          latest_gap_yoy=nn(latest_gap.gap_yoy.get(c)),
                          gap_cum=nn(cumu.gap_cum.get(c))))
    rank = sorted([i for i in items if i["latest_gap_yoy"] is not None],
                  key=lambda r: -r["latest_gap_yoy"])
    crank = sorted([i for i in items if i["gap_cum"] is not None], key=lambda r: -r["gap_cum"])

    a = g[g.item_code == "SA0"].sort_values("ym")
    allit = dict(months=a.ym.tolist(), cpi_u_yoy=[nn(x) for x in a.cpi_u_yoy],
                 ccpi_u_yoy=[nn(x) for x in a.ccpi_u_yoy], gap_yoy=[nn(x) for x in a.gap_yoy],
                 gap_cum=[nn(x) for x in a.gap_cum], stage=a.stage.tolist())
    groups = {}
    for gc in MAJOR:
        s = g[g.item_code == gc].sort_values("ym")
        if s.empty:
            continue
        groups[gc] = dict(name=MAJOR[gc], weight=nn(it.at[gc, "weight"]), months=s.ym.tolist(),
                          gap_cum=[nn(x) for x in s.gap_cum], gap_yoy=[nn(x) for x in s.gap_yoy])

    # decomposition: all-items gap vs the RI-weighted sum of the 15 partition items' gaps
    part = it[it.is_partition == 1].index
    d = g[(g.ym == fin_ym) & (g.item_code.isin(part))].set_index("item_code")
    wt = pd.to_numeric(it.loc[d.index, "weight"], errors="coerce")
    keep = wt.notna() & d.gap_yoy.notna()
    d, wt = d[keep], wt[keep]
    comp = float((d.gap_yoy * wt).sum() / wt.sum())
    tot = float(g[(g.item_code == "SA0") & (g.ym == fin_ym)].gap_yoy.iloc[0])
    dec = dict(ym=fin_ym, total_gap=tot, weighted_component_gap=comp, residual=tot - comp,
               weight_covered=float(wt.sum()),
               parts=[dict(item_code=c, item_name=it.at[c, "item_name"], weight=nn(wt[c]),
                           gap_yoy=nn(d.gap_yoy[c]), contrib=nn(d.gap_yoy[c] * wt[c] / wt.sum()))
                      for c in d.index])
    log.info("decomposition %s: all-items gap %+.3f pp = weighted component gap %+.3f pp + "
             "residual %+.3f pp (%d partition items, %.1f%% weight)", fin_ym, tot, comp,
             tot - comp, len(d), wt.sum())

    ra = rev[rev.item_code == "SA0"].sort_values("ym") if len(rev) else pd.DataFrame()
    rj = dict(n=int(len(rev)), all_items=[], summary={})
    if len(ra):
        rj["first_pub"], rj["last_pub"] = ra.pub_ym.min(), ra.pub_ym.max()
        rj["all_items"] = [dict(ym=r.ym, initial=nn(r.value_ini), latest=nn(r.value_cur),
                                stage=r.stage, rev_idx=nn(r.rev_idx), rev_pct=nn(r.rev_pct),
                                rev_yoy_pp=nn(r.rev_yoy_pp)) for r in ra.itertuples()]
        f = ra[ra.stage == "final"]
        if len(f):
            rj["summary"] = dict(n_final=int(len(f)), mean_rev_pct=nn(f.rev_pct.mean()),
                                 mean_abs_rev_pct=nn(f.rev_pct.abs().mean()),
                                 max_abs_rev_pct=nn(f.rev_pct.abs().max()),
                                 mean_abs_rev_yoy_pp=nn(f.rev_yoy_pp.abs().mean()),
                                 max_abs_rev_yoy_pp=nn(f.rev_yoy_pp.abs().max()),
                                 pct_revised_up=nn((f.rev_pct > 0).mean() * 100))

    doc = dict(
        generated=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        source="BLS su (C-CPI-U) flat files + CPI-U from p0; supplemental Table 1C vintages",
        base_ym=BASE_YM, note="gap_yoy = CPI-U YoY - C-CPI-U YoY (pp); positive = the "
        "fixed-weight index rose faster. Includes formula and weight-timing effects, not only "
        "consumer substitution.",
        coverage=dict(items=int(len(items)),
                      expenditure=int((item.section == "expenditure").sum()),
                      special=int((item.section == "special").sum()),
                      partition=sorted(part), partition_weight=float(wt.sum())),
        stages={r.ym: r.stage for r in a.tail(24).itertuples()},
        items=items, heatmap=dict(months=months, items=piv.index.tolist(),
                                  z=[[nn(x) for x in row] for row in piv.values]),
        all_items=allit, group_cum=groups,
        ranking=dict(as_of=fin_ym, stage="final", top15=rank[:15], bottom15=rank[-15:], all=rank),
        cum_ranking=crank, decomposition=dec, revisions=rj, validation=val)
    import json

    def clean(o):
        """NaN/Inf -> null, numpy scalars -> python (json is written with allow_nan=False so a
        stray non-finite anywhere in the tree would otherwise abort the write)."""
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, (float, np.floating)):
            return float(o) if np.isfinite(o) else None
        return o

    p = OUT / "p8_chained.json"
    p.write_text(json.dumps(clean(doc), indent=1, allow_nan=False))
    log.info("wrote %s (%.0f KB)", p, p.stat().st_size / 1024)
    return doc


def main():
    args = set(sys.argv[1:])
    if "--help" in args or "-h" in args:
        print(__doc__); return 0
    con = init_db()
    con.executescript(SCHEMA8); con.commit()
    item, series, changed = load_su(con, force="--force" in args)
    it = build_items(con, item)
    if "--no-vintages" not in args:
        empty = not con.execute("SELECT 1 FROM p8_vintage LIMIT 1").fetchone()
        load_vintages(con, item, full=("--history" in args or empty))
    g = build_gap(con)
    rev = build_revisions(con)
    val, ok = validate(con, g, it)
    json_out(con, g, it, rev, val)
    log.info("P8 done (validation %s)", "OK" if ok else "MISMATCH")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
