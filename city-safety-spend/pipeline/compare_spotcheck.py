"""Cross-validation against the cities' own FY2022 financial documents (data/spotcheck/, all
spotcheck_fy2022*.csv files: round 1 = 15 cities incl. six in Texas, round 2 = 14 non-Texas cities). Census fiscal year 2022 = the fiscal year ending Jul 2021 - Jun 2022; the
spotcheck rows already use the matching city document (a Sept-30 city's "FY2021").

For each city and framing that splits police and fire, report Census / document ratios. The
department-level budgetary framing is usually the like-for-like comparator for Census code 62/24;
whether pension contributions sit inside it, and whether Census counts them, is city-specific
(see METHODOLOGY section 2 and the pensions_in_line column).
Output: validation/spotcheck_vs_census.csv
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
from compare_vera import norm

def main():
    import glob
    sc = []
    for f in sorted(glob.glob(os.path.join(build.ROOT, "data", "spotcheck", "spotcheck_fy2022*.csv"))):
        sc += list(csv.DictReader(open(f, encoding="utf-8-sig")))
    cen = {(norm(r["city"]), r["state"]): r for r in csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_2022.csv")))}
    out = []
    for s in sc:
        c = cen.get((norm(s["city"]), s["state"]))
        if not c:
            print("no census row for", s["city"], s["state"]); continue
        cp, cf = int(c["police_usd"]), int(c["fire_usd"])
        dp = int(s["police_usd"]) if s["police_usd"] else None
        df = int(s["fire_usd"]) if s["fire_usd"] else None
        dps = int(s["public_safety_usd"]) if s["public_safety_usd"] else None
        out.append(dict(city=s["city"], state=s["state"], fy_end_date=s["fy_end_date"], framing=s["framing"], actual_or_adopted=s["actual_or_adopted"],
                        pensions_in_line=s["pensions_in_line"], fire_includes_ems=s["fire_includes_ems"],
                        census_police_usd=cp, doc_police_usd=dp, ratio_police=round(cp / dp, 3) if dp else None,
                        census_fire_usd=cf, doc_fire_usd=df, ratio_fire=round(cf / df, 3) if df else None,
                        census_police_fire_usd=cp + cf, doc_public_safety_usd=dps, ratio_police_fire_to_public_safety=round((cp + cf) / dps, 3) if dps else None,
                        census_flags=c["police_flags"] + "/" + c["fire_flags"],
                        doc_denominator_usd=s["denominator_usd"], doc_denominator_label=s["denominator_label"],
                        doc_police_fire_pct_of_its_denominator=round(100 * (dp + df) / int(s["denominator_usd"]), 1) if (dp and df and s["denominator_usd"]) else None,
                        census_police_fire_pct_general=c["police_fire_pct_general"], census_police_fire_pct_core=c["police_fire_pct_core"],
                        source_url=s["source_url"], page=s["page"]))
    with open(os.path.join(build.ROOT, "validation", "spotcheck_vs_census.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print(f"{'city':<16}{'framing':<42}{'pens':<5}{'Cpol':>8}{'Dpol':>8}{'r':>6}{'Cfire':>8}{'Dfire':>8}{'r':>6}  docP+F%  censG%  censCore%")
    for r in out:
        if r["doc_police_usd"]:
            print(f"{r['city']:<16}{r['framing'][:41]:<42}{r['pensions_in_line'][:4]:<5}{r['census_police_usd']/1e6:8.0f}{r['doc_police_usd']/1e6:8.0f}{r['ratio_police']:6.2f}{r['census_fire_usd']/1e6:8.0f}{(r['doc_fire_usd'] or 0)/1e6:8.0f}{(r['ratio_fire'] or 0):6.2f}  {str(r['doc_police_fire_pct_of_its_denominator']):>6}  {r['census_police_fire_pct_general']:>6}  {r['census_police_fire_pct_core']:>6}  [{r['census_flags']}]")

if __name__ == "__main__":
    main()
