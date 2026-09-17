"""Cross-validation against BJS-published police operating budgets (LEMAS 1993/1997/2000 agency
volumes and Police Departments in Large Cities 1990-2000), data/bjs/bjs_police_budgets.csv.

Different instrument (police chief answers form CJ-44) and different definition: BJS INCLUDES employer
pension contributions and agency-run jails; Census code 62 excludes contributions to a city's own
pension fund and sends jails to corrections. So Census/BJS should sit near 1 for cities in state-run
plans and well below 1 for cities with their own police pension funds. Census fiscal-year alignment as
in compare_vera.py: BJS FY Y compared to Census Y and Y+1, closest kept.
Output: validation/bjs_vs_census.csv
"""
import csv, os, sys, statistics, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
from compare_vera import norm

def main():
    bjs = list(csv.DictReader(open(os.path.join(build.ROOT, "data", "bjs", "bjs_police_budgets.csv"), encoding="utf-8-sig")))
    longs = {(norm(r["city"]), r["state"], int(r["fiscal_year"])): r for r in csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_1967_2024_long.csv")))}
    out = []
    for b in bjs:
        y = int(b["fiscal_year"]); k = (norm(b["city"]), b["state"])
        bud = float(b["operating_budget_usd"] or 0)
        if not bud: continue
        row = dict(city=b["city"], state=b["state"], agency=b["agency_name"], bjs_fy=y, bjs_operating_budget_usd=int(bud), sworn=b.get("sworn_officers"), bjs_source=b["source"])
        ratios = []
        for lab, yy in (("same", y), ("next", y + 1)):
            c = longs.get(k + (yy,))
            row[f"census_{lab}_year"] = yy if c else None
            row[f"census_{lab}_police_usd"] = int(c["police_usd"]) if c else None
            r = round(int(c["police_usd"]) / bud, 3) if c and int(c["police_usd"]) else None
            row[f"ratio_{lab}"] = r
            if r: ratios.append(r)
        row["closest_ratio"] = min(ratios, key=lambda x: abs(x - 1)) if ratios else None
        out.append(row)
    with open(os.path.join(build.ROOT, "validation", "bjs_vs_census.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(sorted(out, key=lambda r: (r["bjs_fy"], r["city"])))
    m = [r for r in out if r["closest_ratio"]]
    print(f"BJS rows {len(out)}, matched to a Census year {len(m)}")
    for y in sorted(set(r["bjs_fy"] for r in m)):
        s = [r["closest_ratio"] for r in m if r["bjs_fy"] == y]
        print(f"  FY{y}: n={len(s)} median Census/BJS {statistics.median(s):.3f}, within 10%: {sum(1 for x in s if abs(x-1)<=.1)}, within 20%: {sum(1 for x in s if abs(x-1)<=.2)}")
    own = {"Houston","Dallas","Austin","San Antonio","Fort Worth","El Paso","Chicago","New York","Los Angeles","Philadelphia","Boston","Detroit","Baltimore","San Francisco","Seattle","Denver","Milwaukee","Pittsburgh","St. Louis","Kansas City","Omaha","Minneapolis","Atlanta","Nashville","Memphis","New Orleans","Oklahoma City","Tulsa","Cincinnati","Columbus","Cleveland"}
    print("  FY2000 cities with their own police pension funds (expect ratio < 1):")
    for r in sorted((r for r in m if r["bjs_fy"] == 2000 and r["city"] in own), key=lambda r: r["closest_ratio"]):
        print(f"    {r['city']:<16}{r['state']} BJS {r['bjs_operating_budget_usd']/1e6:7.1f}M  Census {r['closest_ratio']:.2f}x")

if __name__ == "__main__":
    main()
