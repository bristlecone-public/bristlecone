"""Cross-validation of Census employment counts against FBI Uniform Crime Reporting police employee data
(data/fbi/fbi_police_employees.csv): an independent report, filed by the police agency itself rather than
the city's finance or personnel office.

Definitions differ in known ways, so exact agreement is not expected:
- Timing: Census counts full-time employees in March of year Y; FBI counts as of October 31 of year Y.
- Scope: Census code 062 is every city employee in the police function with power of arrest; FBI counts
  sworn officers of that agency. Census excludes airport, port, park and transit police by function; the
  FBI excludes any sworn staff not in the reporting department.
- Contract and joint forces: the FBI reports Las Vegas Metro as a department; Census records the city's
  own marshals only. Such cities are flagged and left out of the summary.
Output: validation/fbi_vs_census.csv
"""
import csv, os, sys, statistics, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
from compare_vera import norm


def main():
    fbi = {}
    for r in csv.DictReader(open(os.path.join(build.ROOT, "data", "fbi", "fbi_police_employees.csv"), encoding="utf-8-sig")):
        fbi[(norm(r["city"]), r["state"], int(r["year"]))] = r
    flags = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_flags.csv")))}
    out = []
    for r in csv.DictReader(open(os.path.join(build.OUT, "city_employment_all_years.csv"))):
        y = int(r["year"])
        f = fbi.get((norm(r["city"]), r["state"], y))
        if not f:
            continue
        cs, cc = int(r["police_sworn_ft"]), int(r["police_other_ft"])
        fs, fc = int(f["sworn_officers"]), int(f["civilians"])
        contracted = flags.get(r["pid"], {}).get("police_contracted") == "True"
        out.append(dict(city=r["city"], state=r["state"], year=y, census_sworn_ft=cs, fbi_sworn=fs,
                        ratio_sworn=round(cs / fs, 3) if fs else None, census_civilian_ft=cc, fbi_civilians=fc,
                        ratio_civilian=round(cc / fc, 3) if fc else None, census_flag_class=r["police_flag_class"],
                        contracted_or_joint=contracted, fbi_agency=f["agency_name"], fbi_ori=f["ori"]))
    out.sort(key=lambda r: (r["state"], r["city"], r["year"]))
    with open(os.path.join(build.ROOT, "validation", "fbi_vs_census.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)

    def summary(label, rows, key):
        xs = sorted(r[key] for r in rows if r[key])
        if not xs:
            return
        q = statistics.quantiles(xs, n=4)
        print(f"  {label:<42} n={len(xs):5d}  median {statistics.median(xs):.3f}  IQR {q[0]:.3f}-{q[2]:.3f}  "
              f"within 5% {sum(1 for x in xs if abs(x-1)<=.05)/len(xs):.0%}  within 10% {sum(1 for x in xs if abs(x-1)<=.10)/len(xs):.0%}", file=sys.stderr)
        return xs

    base = [r for r in out if not r["contracted_or_joint"]]
    print(f"{len(out)} matched city-years ({len({(r['city'], r['state']) for r in out})} cities)", file=sys.stderr)
    summary("sworn, all non-contract city-years", base, "ratio_sworn")
    summary("sworn, Census reported", [r for r in base if r["census_flag_class"] == "reported"], "ratio_sworn")
    summary("sworn, Census imputed", [r for r in base if r["census_flag_class"] == "imputed"], "ratio_sworn")
    # Prorated is its own class: the unit total was reported, only the split across functions is
    # estimated. Rolling it into "imputed" - or omitting it, as this did - hides both.
    summary("sworn, Census prorated", [r for r in base if r["census_flag_class"] == "prorated"], "ratio_sworn")
    summary("civilian, Census reported", [r for r in base if r["census_flag_class"] == "reported"], "ratio_civilian")
    by_year = collections.defaultdict(list)
    for r in base:
        if r["ratio_sworn"]:
            by_year[r["year"]].append(r["ratio_sworn"])
    print("  sworn median by year: " + ", ".join(f"{y} {statistics.median(v):.3f}" for y, v in sorted(by_year.items())), file=sys.stderr)
    print("  largest sworn gaps, 2022 reported:", file=sys.stderr)
    for r in sorted((r for r in base if r["year"] == 2022 and r["census_flag_class"] == "reported" and r["ratio_sworn"]), key=lambda r: -abs(r["ratio_sworn"] - 1))[:10]:
        print(f"    {r['city']:<18}{r['state']} Census {r['census_sworn_ft']:>6}  FBI {r['fbi_sworn']:>6}  ratio {r['ratio_sworn']}", file=sys.stderr)


if __name__ == "__main__":
    main()
