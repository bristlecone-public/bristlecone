"""Cross-validation against the Lincoln Institute Fiscally Standardized Cities database (212 cities,
2012/2017/2022/2023, two views).

city_only view  = the Census municipal record as FiSC republishes it (nominal dollars, unrounded).
fisc view       = city + allocated share of overlying county, school district, special districts.

Outputs
  validation/fisc_vs_census.csv     city_only police/fire/direct-general vs our parse, relative differences
  data/census_out/fisc_share.csv    for the 212 FiSC cities: police+fire share on the city's own books vs
                                    on the FiSC basis (residents' whole local-government bill). The FiSC
                                    basis is the fair cross-city comparison when some cities carry county
                                    functions and others do not.
FiSC "general expenditure" is DIRECT general (excludes intergovernmental expenditure), per
data/fisc/NOTES.md, so it is compared to our direct_general_expenditure_usd.
"""
import csv, os, sys, collections, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
from compare_vera import norm

def main():
    fisc = list(csv.DictReader(open(os.path.join(build.ROOT, "data", "fisc", "fisc_police_fire.csv"), encoding="utf-8-sig")))
    mine = list(csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_all_years.csv"))))
    my = {(norm(r["city"]), r["state"], int(r["fiscal_year"])): r for r in mine}
    out, unmatched = [], set()
    fisc_view = {(norm(r["city"]), r["state"], int(r["fiscal_year"])): r for r in fisc if r["view"] == "fisc"}
    for f in fisc:
        if f["view"] != "city_only":
            continue
        k = (norm(f["city"]), f["state"], int(f["fiscal_year"]))
        m = my.get(k)
        if not m:
            unmatched.add((f["city"], f["state"])); continue
        row = dict(city=f["city"], state=f["state"], fiscal_year=k[2])
        for col, mcol in (("police_usd", "police_usd"), ("fire_usd", "fire_usd"), ("general_expenditure_usd", "direct_general_expenditure_usd")):
            a, b = int(m[mcol]), int(float(f[col] or 0))
            row[f"census_{col}"], row[f"fisc_cityonly_{col}"] = a, b
            row[f"reldiff_{col}"] = round(abs(a - b) / b, 6) if b else None
        row["census_flags"] = m["police_flags"] + "/" + m["fire_flags"]
        v = fisc_view.get(k)
        if v and float(v["general_expenditure_usd"]) and float(f["general_expenditure_usd"]):
            row["cityonly_police_fire_pct_general"] = round(100 * (float(f["police_usd"]) + float(f["fire_usd"])) / float(f["general_expenditure_usd"]), 2)
            row["fisc_police_fire_pct_general"] = round(100 * (float(v["police_usd"]) + float(v["fire_usd"])) / float(v["general_expenditure_usd"]), 2)
            row["fisc_police_usd"], row["fisc_fire_usd"], row["fisc_general_expenditure_usd"] = int(float(v["police_usd"])), int(float(v["fire_usd"])), int(float(v["general_expenditure_usd"]))
        out.append(row)
    cols = list(out[0].keys())
    for r in out:
        for c in cols: r.setdefault(c, None)
    with open(os.path.join(build.ROOT, "validation", "fisc_vs_census.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(sorted(out, key=lambda r: -(r["reldiff_police_usd"] or 0)))
    with open(os.path.join(build.OUT, "fisc_share.csv"), "w", newline="") as fh:
        keep = ["city", "state", "fiscal_year", "cityonly_police_fire_pct_general", "fisc_police_fire_pct_general", "fisc_police_usd", "fisc_fire_usd", "fisc_general_expenditure_usd", "census_flags"]
        w = csv.DictWriter(fh, fieldnames=keep, extrasaction="ignore"); w.writeheader(); w.writerows(sorted(out, key=lambda r: (r["state"], r["city"], r["fiscal_year"])))
    print(f"matched {len(out)} city-years; unmatched FiSC cities: {sorted(unmatched)}")
    for col in ("police_usd", "fire_usd", "general_expenditure_usd"):
        d = [r[f"reldiff_{col}"] for r in out if r[f"reldiff_{col}"] is not None]
        print(f"  {col}: median reldiff {statistics.median(d):.2e}, within 0.5%: {sum(1 for x in d if x <= 0.005)}/{len(d)}, over 5%: {sum(1 for x in d if x > 0.05)}")
    print("  police disagreements > 0.5%:")
    for r in sorted(out, key=lambda r: -(r["reldiff_police_usd"] or 0)):
        if (r["reldiff_police_usd"] or 0) > 0.005:
            print(f"    {r['city']} {r['state']} {r['fiscal_year']}: census {r['census_police_usd']:,} fisc {r['fisc_cityonly_police_usd']:,} [{r['census_flags']}]")
    s = [r for r in out if r["fiscal_year"] == 2022 and r["fisc_police_fire_pct_general"]]
    print(f"  2022 FiSC-basis share: median {statistics.median(r['fisc_police_fire_pct_general'] for r in s):.1f}% vs city-only median {statistics.median(r['cityonly_police_fire_pct_general'] for r in s):.1f}% (n={len(s)})")

if __name__ == "__main__":
    main()
