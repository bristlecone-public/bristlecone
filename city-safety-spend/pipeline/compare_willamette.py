"""Replication check against the Willamette Government Finance Database (same Census microdata,
independent aggregation code), and construction of the 1967-2024 long series.

1. validation/willamette_vs_census.csv: for every city-year we both cover (2012-2024), exact
   comparison of police_usd, fire_usd, general_expenditure_usd. Join key is place_geoid
   (FIPS state + FIPS place), which Willamette's notes identify as the only key stable across the
   2017 Connecticut ID break. Willamette's total_expenditure is NOT compared for 2007-2021 because
   their build double-counts regular highways (E44) in those years (see data/willamette/NOTES.md).
2. data/census_out/city_police_fire_1967_2024_long.csv: our rows for 2012+ (with flags) plus
   Willamette rows for 1967-2011 and 2016 (no imputation flags exist in that file; source column
   says so). Only cities in our 100k universe.
"""
import csv, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, cpi

INV = {v: k for k, v in build.FIPS_STATE.items()}

def geoid(state, fips_place):
    return INV.get(state, "") + fips_place.zfill(5) if fips_place else ""

def main():
    mine = list(csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_all_years.csv"))))
    wil = list(csv.DictReader(open(os.path.join(build.ROOT, "data", "willamette", "willamette_municipal_100k.csv"), encoding="utf-8-sig")))
    my = {(geoid(r["state"], r["fips_place"]), int(r["fiscal_year"])): r for r in mine}
    wl = {(r["place_geoid"].zfill(7), int(r["fiscal_year"])): r for r in wil}
    out, stats = [], collections.Counter()
    for k, m in my.items():
        w = wl.get(k)
        if not w:
            stats["no_willamette_row"] += 1; continue
        row = dict(place_geoid=k[0], city=m["city"], state=m["state"], fiscal_year=k[1])
        allsame = True
        # Willamette's police_usd/fire_usd add intergovernmental payments; their *_direct_usd equals our E+F+G.
        for col, wcol in (("police_usd", "police_direct_usd"), ("fire_usd", "fire_direct_usd"), ("general_expenditure_usd", "general_expenditure_usd")):
            a, b = int(m[col]), int(float(w[wcol] or 0))
            row[f"census_{col}"], row[f"willamette_{col}"], row[f"diff_{col}"] = a, b, a - b
            if a != b: allsame = False; stats[f"diff_{col}"] += 1
        row["exact_match"] = allsame
        stats["compared"] += 1; stats["exact"] += allsame
        out.append(row)
    out.sort(key=lambda r: (r["exact_match"], -abs(r["diff_police_usd"]) - abs(r["diff_fire_usd"]) - abs(r["diff_general_expenditure_usd"])))
    with open(os.path.join(build.ROOT, "validation", "willamette_vs_census.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(out[0].keys())); wr.writeheader(); wr.writerows(out)
    print(dict(stats))
    byy = collections.defaultdict(lambda: [0, 0])
    for r in out:
        byy[r["fiscal_year"]][0] += 1; byy[r["fiscal_year"]][1] += (r["diff_general_expenditure_usd"] != 0)
    print("general-expenditure disagreements by year (n, differing):", {y: tuple(v) for y, v in sorted(byy.items())})
    print("non-matching examples:")
    for r in [r for r in out if not r["exact_match"]][:10]:
        print("  ", r["city"], r["state"], r["fiscal_year"], "police", r["diff_police_usd"], "fire", r["diff_fire_usd"], "general", r["diff_general_expenditure_usd"])

    # ---- long series ----
    universe = {geoid(r["state"], r["fips_place"]) for r in mine}
    cols = ["place_geoid", "city", "state", "fiscal_year", "population", "police_usd", "fire_usd", "general_expenditure_usd", "total_expenditure_usd",
            "police_pct_general", "fire_pct_general", "police_fire_pct_general", "police_flags", "fire_flags", "record_complete", "source",
            "police_real_usd", "fire_real_usd", "police_real_per_resident", "fire_real_per_resident", "police_fire_real_per_resident", "police_fire_real_rpp_per_resident", "real_dollar_base_year"]
    rows = []
    for r in mine:
        rows.append(dict(place_geoid=geoid(r["state"], r["fips_place"]), city=r["city"], state=r["state"], fiscal_year=int(r["fiscal_year"]), population=r["population"],
                         police_usd=r["police_usd"], fire_usd=r["fire_usd"], general_expenditure_usd=r["general_expenditure_usd"], total_expenditure_usd=r["total_expenditure_usd"],
                         police_pct_general=r["police_pct_general"], fire_pct_general=r["fire_pct_general"], police_fire_pct_general=r["police_fire_pct_general"],
                         police_flags=r["police_flags"], fire_flags=r["fire_flags"], record_complete=r["record_complete"], source="census_iuf"))
    have = {(r["place_geoid"], r["fiscal_year"]) for r in rows}
    names = {r["place_geoid"]: (r["city"], r["state"]) for r in rows}
    for w in wil:
        g, y = w["place_geoid"].zfill(7), int(w["fiscal_year"])
        if g not in universe or (g, y) in have:
            continue
        pol, fire, gen = (int(float(w[c] or 0)) for c in ("police_direct_usd", "fire_direct_usd", "general_expenditure_usd"))
        complete = pol > 0 and gen > 0
        rows.append(dict(place_geoid=g, city=names[g][0], state=names[g][1], fiscal_year=y, population=w["population"],
                         police_usd=pol, fire_usd=fire, general_expenditure_usd=gen,
                         total_expenditure_usd=int(float(w["total_expenditure_usd"] or 0)) if (y <= 2006 or y >= 2022) else "",
                         police_pct_general=round(100 * pol / gen, 2) if complete else "", fire_pct_general=round(100 * fire / gen, 2) if complete else "",
                         police_fire_pct_general=round(100 * (pol + fire) / gen, 2) if complete else "",
                         police_flags="", fire_flags="", record_complete=complete, source="willamette_gfd (no imputation flags published)"))
    # constant dollars (CPI-U, calendar Y-1 for Census year Y) and per resident
    base = cpi.base_year()
    rpp_by_geoid = {}
    rp = os.path.join(build.OUT, "city_rpp.csv")
    if os.path.exists(rp):
        for x in csv.DictReader(open(rp)):
            rpp_by_geoid[x["place_geoid"]] = {y: float(x[f"rpp_{y}"]) for y in range(2008, 2025) if x.get(f"rpp_{y}")}
    for r in rows:
        y = int(r["fiscal_year"]); pop = int(float(r["population"] or 0))
        pr, fr = cpi.to_real(r["police_usd"], census_year=y), cpi.to_real(r["fire_usd"], census_year=y)
        r["police_real_usd"], r["fire_real_usd"] = pr, fr
        ok = pop > 0 and str(r["record_complete"]) == "True" and pr is not None
        r["police_real_per_resident"] = round(pr / pop, 2) if ok else ""
        r["fire_real_per_resident"] = round(fr / pop, 2) if ok else ""
        r["police_fire_real_per_resident"] = round((pr + fr) / pop, 2) if ok else ""
        rp_y = rpp_by_geoid.get(r["place_geoid"], {}).get(y - 1)      # calendar Y-1 prices for Census year Y, as with CPI
        r["police_fire_real_rpp_per_resident"] = round((pr + fr) / pop / (rp_y / 100), 2) if (ok and rp_y) else ""
        r["real_dollar_base_year"] = base
    rows.sort(key=lambda r: (r["city"], r["state"], r["fiscal_year"]))
    with open(os.path.join(build.OUT, "city_police_fire_1967_2024_long.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader(); wr.writerows(rows)
    yrs = collections.Counter(r["fiscal_year"] for r in rows)
    print(f"long series: {len(rows)} city-years, {min(yrs)}-{max(yrs)}, sources:", collections.Counter(r["source"][:12] for r in rows))

if __name__ == "__main__":
    main()
