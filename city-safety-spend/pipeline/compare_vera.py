"""Cross-validation: Vera Institute FY2020 adopted police budgets (72 cities) vs Census actual
police expenditure (item code 62, E+F+G) for Census fiscal years 2020 and 2021.

Why two Census years: Census year Y covers fiscal years ending 1 Jul Y-1 to 30 Jun Y. A city
whose FY2020 ends 30 Sep 2020 (Dallas, San Antonio, Austin, Fort Worth, El Paso, Phoenix ...)
lands in Census 2021; a 30 Jun 2020 close (Houston, Los Angeles, most others) lands in Census 2020.
We report both and the closer one.

Vera's headline figure adds pension, debt-service, and sheriff agencies in 24 cities; their
police_dept_only_usd is the like-for-like comparator for code 62.
Output: validation/vera_vs_census.csv
"""
import csv, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

ALIASES = {
    "batonrougeeastbatonrougeparish": "batonrouge", "wyandotteandkansasunifiedgovernment": "kansas", "wyandotteandkansas": "kansas",
    "sanfranciscoand": "sanfrancisco", "denverand": "denver", "augustaconsolidatedgovernment": "augusta", "columbusconsolidatedgovernment": "columbus",
    "athensunifiedgovernment": "athens", "maconbibb": "macon", "honoluluand": "honolulu", "washingtondc": "washington",
    "anchoragemunicipality": "anchorage", "lexingtonurbangovernment": "lexington", "louisvillemetrogovernment": "louisville",
}

def norm(s):
    s = s.lower().replace("ft.", "fort").replace("ft ", "fort ")
    s = re.sub(r"\b(city|and county|county|metropolitan government|metro government|consolidated government|urban county government|unified government|municipality|-davidson|-jefferson|-fayette|-richmond|-bibb|-clarke|dc)\b", " ", s)
    s = s.replace("st.", "st").replace("saint", "st").replace("-", " ")
    s = re.sub(r"[^a-z]", "", s)
    return ALIASES.get(s, s)

def main():
    vera = list(csv.DictReader(open(os.path.join(build.ROOT, "data", "vera", "vera_fy2020.csv"), encoding="utf-8-sig")))
    cen = list(csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_all_years.csv"))))
    by = {}
    for r in cen:
        by[(norm(r["city"]), r["state"], int(r["fiscal_year"]))] = r
    out = []
    for v in vera:
        k = (norm(v["city"]), v["state"])
        c20, c21 = by.get(k + (2020,)), by.get(k + (2021,))
        dept = float(v.get("police_dept_only_usd") or v["police_budget_usd"])
        row = dict(city=v["city"], state=v["state"], vera_police_headline_usd=v["police_budget_usd"], vera_police_dept_only_usd=int(dept),
                   vera_pct_of_city_funds=v["police_pct"], vera_source=v["source_url"])
        for lab, c in (("2020", c20), ("2021", c21)):
            row[f"census{lab}_police_usd"] = int(c["police_usd"]) if c else None
            row[f"census{lab}_flags"] = c["police_flags"] if c else None
            row[f"ratio_census{lab}_to_vera_dept"] = round(int(c["police_usd"]) / dept, 3) if c and dept else None
            row[f"census{lab}_police_pct_general"] = c["police_pct_general"] if c else None
        ratios = [row[f"ratio_census{l}_to_vera_dept"] for l in ("2020", "2021") if row[f"ratio_census{l}_to_vera_dept"]]
        row["closest_ratio"] = min(ratios, key=lambda x: abs(x - 1)) if ratios else None
        row["matched"] = bool(c20 or c21)
        out.append(row)
    out.sort(key=lambda r: (r["closest_ratio"] is None, abs((r["closest_ratio"] or 1) - 1)), reverse=True)
    p = os.path.join(build.ROOT, "validation", "vera_vs_census.csv")
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    m = [r for r in out if r["closest_ratio"]]
    import statistics
    print(f"matched {len(m)}/{len(out)} cities; unmatched: {[r['city']+' '+r['state'] for r in out if not r['matched']]}")
    print(f"closest-year ratio Census/Vera-dept: median {statistics.median(r['closest_ratio'] for r in m):.3f}, "
          f"within 10%: {sum(1 for r in m if abs(r['closest_ratio']-1)<=0.10)}, within 20%: {sum(1 for r in m if abs(r['closest_ratio']-1)<=0.20)}")
    print("largest gaps:")
    for r in m[:12]:
        print(f"  {r['city']:<18}{r['state']} vera_dept {r['vera_police_dept_only_usd']/1e6:8.1f}M  census20 {(r['census2020_police_usd'] or 0)/1e6:8.1f}M [{r['census2020_flags']}]  census21 {(r['census2021_police_usd'] or 0)/1e6:8.1f}M [{r['census2021_flags']}]  closest {r['closest_ratio']}")

if __name__ == "__main__":
    main()
