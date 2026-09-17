"""Internal consistency checks on the Census parse. Run after build.py.

1. aggregate_check.csv: for every state and year, sum of E62/E24 across ALL municipalities we
   parsed (not just 100k+) versus the Census Bureau's own published state-by-type totals
   (<yy>statetypepu.txt, level code for municipalities). Any nonzero difference means our
   parser or ID handling is wrong.
2. yoy_anomalies.csv: city-years where police+fire share of general expenditure moved more
   than 40% relative to the previous available year, with the raw components so a reader can
   see whether the numerator or the denominator moved.
"""
import csv, glob, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

ROOT = build.ROOT
VAL = os.path.join(ROOT, "validation")
os.makedirs(VAL, exist_ok=True)

# Level-of-estimate codes differ between eras. Determined empirically against Texas 2022 (6 = municipal)
# and verified below by picking, per year, the level whose E62 total matches our municipal sum in >= 45 states.
def published_totals(year):
    f = glob.glob(os.path.join(build.RAW, str(year), "**", f"{str(year)[2:]}statetypepu.txt"), recursive=True)
    if not f:
        return None
    out = collections.defaultdict(dict)  # (state, level) -> {code: amt}
    with open(f[0], encoding="latin-1") as fh:
        for l in fh:
            st, lvl, code = l[0:2], l[2], l[4:7]
            try:
                amt = int(l[8:20])
            except ValueError:
                continue
            out[(st, lvl)][code] = amt
    return out


def main():
    xw = build.load_crosswalk()
    years = sorted(int(os.path.basename(d)) for d in glob.glob(os.path.join(build.RAW, "2*")) if os.path.isdir(d))
    agg_rows, allcode_rows = [], []
    for y in years:
        d, data = build.load_year(y, xw)
        if d is None:
            continue
        pub = published_totals(y)
        mine = collections.defaultdict(lambda: collections.Counter())
        for pid, items in data.items():
            st = d[pid]["state"]
            for c, (a, _) in items.items():
                mine[st][c] += a
        if not pub:
            agg_rows.append(dict(year=y, note="no published state-by-type file in this year's zip"))
            continue
        # pick the municipal level code for this year. Published files use FIPS state codes from 2017 on,
        # but the 2012-2015 era files use Census alphabetical state codes (01 AL, 02 AK, 03 AZ, 04 AR ...).
        if y <= 2015:
            alpha = ["AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
            inv = {st: f"{i+1:02d}" for i, st in enumerate(alpha)}
        else:
            inv = {v: k for k, v in build.FIPS_STATE.items()}
        best_lvl, best_hits = None, -1
        for lvl in sorted(set(k[1] for k in pub)):
            hits = sum(1 for st, m in mine.items() if pub.get((inv.get(st, st), lvl), {}).get("E62") == m["E62"])
            if hits > best_hits:
                best_lvl, best_hits = lvl, hits
        for st, m in sorted(mine.items()):
            p = pub.get((inv.get(st, st), best_lvl), {})
            agg_rows.append(dict(year=y, state=st, level_code=best_lvl, full_census_year=(y % 5 == 2), my_E62_k=m["E62"], census_E62_k=p.get("E62"),
                                 diff_E62_k=(m["E62"] - p["E62"]) if "E62" in p else None,
                                 my_E24_k=m["E24"], census_E24_k=p.get("E24"),
                                 diff_E24_k=(m["E24"] - p["E24"]) if "E24" in p else None))
        if y % 5 == 2:
            # every item code, every state: how many (state, code) cells match the published municipal total exactly
            cells = mism = 0
            for st, m in mine.items():
                p = pub.get((inv.get(st, st), best_lvl), {})
                for c, v in m.items():
                    if c[0] in "EFGIJLMQSXY":
                        cells += 1; mism += (p.get(c) != v)
            allcode_rows.append(dict(year=y, expenditure_cells=cells, mismatched_cells=mism, pct_exact=round(100 * (cells - mism) / cells, 3)))
        kind = "FULL CENSUS: sums must match" if y % 5 == 2 else "sample year: published totals are weighted universe estimates, our sum covers sampled units only"
        print(f"{y}: municipal level code {best_lvl}, states matching exactly on E62: {best_hits}/{len(mine)}  [{kind}]", file=sys.stderr)
    cols = ["year", "state", "level_code", "full_census_year", "my_E62_k", "census_E62_k", "diff_E62_k", "my_E24_k", "census_E24_k", "diff_E24_k", "note"]
    with open(os.path.join(VAL, "aggregate_check.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(agg_rows)

    with open(os.path.join(VAL, "aggregate_check_all_codes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["year", "expenditure_cells", "mismatched_cells", "pct_exact"]); w.writeheader(); w.writerows(allcode_rows)
    print("all expenditure item codes vs published municipal totals, census years:", allcode_rows, file=sys.stderr)

    rows = list(csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_all_years.csv"))))
    by = collections.defaultdict(dict)
    for r in rows:
        if r["police_fire_pct_general"]:
            by[(r["city"], r["state"])][int(r["fiscal_year"])] = r
    out = []
    for k, ys in by.items():
        yy = sorted(ys)
        for a, b in zip(yy, yy[1:]):
            pa, pb = float(ys[a]["police_fire_pct_general"]), float(ys[b]["police_fire_pct_general"])
            if pa and abs(pb - pa) / pa > 0.4:
                ra, rb = ys[a], ys[b]
                out.append(dict(city=k[0], state=k[1], year_from=a, year_to=b, share_from=pa, share_to=pb,
                                police_from=ra["police_usd"], police_to=rb["police_usd"], fire_from=ra["fire_usd"], fire_to=rb["fire_usd"],
                                general_from=ra["general_expenditure_usd"], general_to=rb["general_expenditure_usd"],
                                flags_to=rb["police_flags"] + "/" + rb["fire_flags"], n_items_to=rb["n_items"]))
    out.sort(key=lambda r: -abs(r["share_to"] - r["share_from"]))
    with open(os.path.join(VAL, "yoy_anomalies.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print(f"yoy anomalies: {len(out)}", file=sys.stderr)


if __name__ == "__main__":
    main()
