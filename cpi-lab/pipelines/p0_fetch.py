#!/usr/bin/env python3
"""P0 — item-level CPI foundation.

  p0_fetch.py [--full] [--weights] [--force]

--full     also pull the full-history data files (once; ~300 MB) instead of only cu.data.0.Current
--weights  refresh relative-importance (annual) tables
Only U.S. city average (area 0000), monthly (periodicity R), CPI-U (CUUR/CUSR) is loaded.
"""
import sys, re, io, html, datetime as dt
import pandas as pd
from common import *

FULL_FILES = ["cu.data.1.AllItems", "cu.data.2.Summaries", "cu.data.11.USFoodBeverage", "cu.data.12.USHousing",
              "cu.data.13.USApparel", "cu.data.14.USTransportation", "cu.data.15.USMedical", "cu.data.16.USRecreation",
              "cu.data.17.USEducationAndCommunication", "cu.data.18.USOtherGoodsAndServices",
              "cu.data.20.USCommoditiesServicesSpecial"]


def read_tsv(path):
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


def load_dims(con):
    d = RAW / "cu"
    item = read_tsv(fetch(BLS_TS + "cu/cu.item", d / "cu.item")[0])
    series = read_tsv(fetch(BLS_TS + "cu/cu.series", d / "cu.series")[0])
    item["display_level"] = item["display_level"].astype(int)
    item["sort_sequence"] = item["sort_sequence"].astype(int)
    item = item.sort_values("sort_sequence").reset_index(drop=True)
    # parent = nearest previous row with display_level - 1
    parents, stack = [], {}
    for _, r in item.iterrows():
        lvl = r.display_level
        parents.append(stack.get(lvl - 1) if lvl > 0 else None)
        stack[lvl] = r.item_code
        for k in [k for k in stack if k > lvl]:
            del stack[k]
    item["parent_code"] = parents
    con.execute("DELETE FROM cu_item")
    con.executemany("INSERT INTO cu_item VALUES(?,?,?,?,?,?)",
                    item[["item_code", "item_name", "display_level", "selectable", "sort_sequence", "parent_code"]].values.tolist())
    s = series[(series.area_code == "0000") & (series.periodicity_code == "R") & series.series_id.str.startswith("CU")]
    con.execute("DELETE FROM cu_series")
    con.executemany("INSERT INTO cu_series VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    s[["series_id", "area_code", "item_code", "seasonal", "periodicity_code", "base_code", "base_period",
                       "series_title", "begin_year", "begin_period", "end_year", "end_period"]].values.tolist())
    con.commit()
    log.info("dims: %d items, %d US-city-avg monthly series", len(item), len(s))
    return set(s.series_id)


def load_data(con, files, keep, force=False):
    d = RAW / "cu"
    changed_any = False
    for f in files:
        path, changed = fetch(BLS_TS + "cu/" + f, d / f, force=force)
        if not changed and not force:
            log.info("%s unchanged", f)
            continue
        changed_any = True
        df = read_tsv(path)
        df = df[df.series_id.isin(keep) & df.period.str.startswith("M") & (df.period != "M13")]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["year"] = df["year"].astype(int)
        pull = new_pull(con, f)
        # only insert rows whose value differs from the latest stored vintage
        latest = pd.read_sql("SELECT series_id, year, period, value AS old FROM cpi_obs_latest", con)
        m = df.merge(latest, on=["series_id", "year", "period"], how="left")
        new = m[m.old.isna() | ((m.value - m.old).abs() > 1e-9)]
        con.executemany("INSERT OR REPLACE INTO cpi_obs VALUES(?,?,?,?,?,?)",
                        [(r.series_id, int(r.year), r.period, float(r.value), r.footnote_codes, pull) for r in new.itertuples()])
        con.commit()
        log.info("%s: %d rows read, %d new/changed stored (pull %d)", f, len(df), len(new), pull)
    return changed_any


def norm(s):
    s = html.unescape(s).lower()
    s = re.sub(r"\(\d+\)", "", s)  # footnote markers
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_weights(con, years=None):
    """Parse relative-importance HTML tables (December weights of `year`, used from Jan year+1).
    Hierarchy comes from cu_item (the HTML markup varies by year); rows after the
    'Special aggregate indexes' marker are tagged section='special'."""
    items = pd.read_sql("SELECT item_code, item_name, display_level, parent_code FROM cu_item", con)
    items["n"] = items.item_name.map(norm)
    by_name = items.groupby("n").item_code.apply(list).to_dict()
    parent_of = dict(zip(items.item_code, items.parent_code))
    this_year = dt.date.today().year
    years = years or list(range(2020, this_year + 1))
    for y in years:
        url = f"https://www.bls.gov/cpi/tables/relative-importance/{y}.htm"
        try:
            path, _ = fetch(url, RAW / "weights" / f"{y}.htm", retries=1)
        except Exception:
            log.info("no relative-importance page for %d", y)
            continue
        t = path.read_text(encoding="utf-8", errors="ignore")
        i = t.find("<table"); j = t.find("</table>", i)
        rows = re.findall(r"<tr.*?</tr>", t[i:j], flags=re.S)
        recs, unmatched, ambiguous, section = [], [], 0, "main"
        for r in rows:
            plain = norm(re.sub(r"<[^>]+>", " ", r))
            if "special aggregate" in plain:
                section = "special"; continue
            th = re.search(r"<th[^>]*>(.*?)</th>", r, flags=re.S)
            if not th:
                continue
            name = norm(re.sub(r"<[^>]+>", " ", th.group(1)))
            vals = [re.sub(r"<[^>]+>", "", v).strip() for v in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S)]
            try:
                wu, ww = float(vals[0]), float(vals[1])
            except Exception:
                continue
            cands = by_name.get(name, [])
            if len(cands) == 1:
                code = cands[0]
            elif len(cands) > 1:
                ambiguous += 1
                # prefer a candidate whose parent is already matched in this section
                seen = {rec[1] for rec in recs}
                code = next((c for c in cands if parent_of.get(c) in seen), cands[0])
            else:
                unmatched.append(name); code = "?" + name[:40]
            recs.append([y, code, name, wu, ww, 0 if code.startswith("?") else 1, section, None, 0])
        # levels + leaves from cu_item hierarchy: leaf = matched main row that is nobody's parent among matched main rows
        main_codes = {rec[1] for rec in recs if rec[6] == "main" and rec[5]}
        parents_used = {parent_of.get(c) for c in main_codes}
        lvl = dict(zip(items.item_code, items.display_level))
        for rec in recs:
            rec[7] = lvl.get(rec[1])
            rec[8] = int(rec[6] == "main" and rec[5] == 1 and rec[1] not in parents_used)
        con.execute("DELETE FROM cpi_weight WHERE weight_year=?", (y,))
        con.executemany("INSERT OR REPLACE INTO cpi_weight VALUES(?,?,?,?,?,?,?,?,?)", recs)
        con.commit()
        leafsum = sum(r[3] for r in {rec[1]: rec for rec in recs}.values() if r[8])  # dedupe on item_code (RI lists "All items" twice)
        log.info("weights %d: %d rows, leaf weight sum %.2f, %d ambiguous, %d unmatched: %s", y, len(recs), leafsum, ambiguous, len(unmatched), unmatched[:6])


def build_item_month(con):
    """Derived table: per item × month NSA/SA index, MoM, YoY, 3m annualized, weight, contribution to YoY."""
    obs = pd.read_sql("""SELECT s.item_code, s.seasonal, o.year, o.period, o.value
                         FROM cpi_obs_latest o JOIN cu_series s USING(series_id)""", con)
    obs["ym"] = obs.year.astype(str) + "-" + obs.period.str[1:]
    piv = obs.pivot_table(index=["item_code", "ym"], columns="seasonal", values="value").reset_index()
    piv = piv.rename(columns={"U": "idx_nsa", "S": "idx_sa"})
    if "idx_sa" not in piv: piv["idx_sa"] = float("nan")
    piv = piv.sort_values(["item_code", "ym"])
    # calendar-aligned lags (row offsets break across the Oct-2025 shutdown gap)
    def lag(col, k):
        l = piv[["item_code", "ym", col]].copy()
        p = pd.PeriodIndex(l.ym, freq="M") + k
        l["ym"] = p.astype(str)
        return piv[["item_code", "ym"]].merge(l, on=["item_code", "ym"], how="left")[col].values
    piv["mom_sa"] = (piv.idx_sa / lag("idx_sa", 1) - 1) * 100
    piv["mom_nsa"] = (piv.idx_nsa / lag("idx_nsa", 1) - 1) * 100
    piv["yoy"] = (piv.idx_nsa / lag("idx_nsa", 12) - 1) * 100
    piv["ann3m"] = ((piv.idx_sa / lag("idx_sa", 3)) ** 4 - 1) * 100
    w = pd.read_sql("SELECT weight_year, item_code, weight_u FROM cpi_weight WHERE matched=1", con)
    # December weights of year Y apply to months of Y+1
    w["yr"] = w.weight_year + 1
    piv["yr"] = piv.ym.str[:4].astype(int)
    piv = piv.merge(w[["yr", "item_code", "weight_u"]], on=["yr", "item_code"], how="left").rename(columns={"weight_u": "weight"})
    # approx contribution to headline YoY: weight × item YoY / 100 (proper BLS method uses relative importance updated by relative price change; this is close for a spec table)
    piv["contrib_yoy"] = piv.weight * piv.yoy / 100
    con.execute("DELETE FROM cpi_item_month")
    cols = ["item_code", "ym", "idx_nsa", "idx_sa", "mom_sa", "mom_nsa", "yoy", "ann3m", "weight", "contrib_yoy"]
    con.executemany("INSERT INTO cpi_item_month VALUES(?,?,?,?,?,?,?,?,?,?)",
                    piv[cols].astype(object).where(piv[cols].notna(), None).values.tolist())
    con.commit()
    piv[cols].to_parquet(OUT / "cpi_item_month.parquet", index=False)
    log.info("cpi_item_month: %d rows", len(piv))


def validate(con):
    """Replicate the published all-items NSA index as a December-chained Laspeyres over leaf items
    (I_t = I_Dec * sum_i w_i * P_it / P_iDec, weights = Dec relative importance) and compare YoY."""
    im = pd.read_sql("SELECT item_code, ym, idx_nsa FROM cpi_item_month", con)
    w = pd.read_sql("SELECT weight_year, item_code, weight_u FROM cpi_weight WHERE is_leaf=1 AND matched=1", con)
    pub = im[im.item_code == "SA0"].set_index("ym").idx_nsa
    ours = {}
    for y in sorted(w.weight_year.unique()):
        wy = w[w.weight_year == y]
        base_ym = f"{y}-12"
        base = im[im.ym == base_ym].set_index("item_code").idx_nsa
        for m in range(1, 13):
            ym = f"{y+1}-{m:02d}"
            cur = im[im.ym == ym].set_index("item_code").idx_nsa
            d = wy.set_index("item_code").weight_u.to_frame().join(base.rename("b")).join(cur.rename("c")).dropna()
            if d.empty or ym not in pub.index:
                continue
            rel = (d.weight_u * d.c / d.b).sum() / d.weight_u.sum()
            ours[ym] = (pub.get(base_ym) * rel, d.weight_u.sum())
    o = pd.Series({k: v[0] for k, v in ours.items()}).sort_index()
    cov = pd.Series({k: v[1] for k, v in ours.items()})
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    ok_all = True
    for ym in o.index[-8:]:
        prev = f"{int(ym[:4])-1}{ym[4:]}"
        if prev not in o.index and prev not in pub.index:
            continue
        ours_yoy = (o[ym] / (o.get(prev) if prev in o.index else pub[prev]) - 1) * 100
        pub_yoy = (pub[ym] / pub[prev] - 1) * 100
        diff = ours_yoy - pub_yoy
        ok = abs(diff) < 0.15
        ok_all &= ok
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)", (now, "dec_chained_laspeyres_yoy", ym, ours_yoy, pub_yoy, diff, int(ok)))
        log.info("validate %s: replicated YoY %.2f vs published %.2f (diff %+.2f, leaf coverage %.1f%%) %s",
                 ym, ours_yoy, pub_yoy, diff, cov[ym], "OK" if ok else "MISMATCH")
    con.commit()
    return ok_all


if __name__ == "__main__":
    args = set(sys.argv[1:])
    con = init_db()
    keep = load_dims(con)
    files = FULL_FILES + ["cu.data.0.Current"] if "--full" in args else ["cu.data.0.Current"]
    changed = load_data(con, files, keep, force="--force" in args)
    if "--weights" in args or not con.execute("SELECT 1 FROM cpi_weight LIMIT 1").fetchone():
        load_weights(con)
    if changed or "--force" in args or "--weights" in args:
        build_item_month(con)
        ok = validate(con)
        sys.exit(0 if ok else 2)
    log.info("nothing new")
