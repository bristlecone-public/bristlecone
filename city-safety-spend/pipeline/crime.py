"""Reported crime beside police spending (Phase 2, item 2A).

Source: FBI Uniform Crime Reporting agency-level offense counts (data/fbi/fbi_offenses.csv, see
data/fbi/NOTES.md), joined to the 332-city universe by city and state, 2012-2024.

Published per city-year: violent and property crime counts and rates per 1,000 residents, where residents
are the Census population used everywhere else in this dataset (not the FBI's covered population, which
can differ for agencies that police more than the city).

Deliberately NOT published, per docs/ADVERSARIAL_AUDIT_RESPONSE.md: any spending-versus-crime quadrant or
"efficiency" label. Crime per resident overstates risk in commuter and tourist hubs, and reported crime
depends on reporting practice; the numbers are context, not a verdict.

Coverage flag per row:
  full        12 months reported
  partial     1-11 months reported (counts are not annualized; the rate is left blank)
  unknown     the source does not say how many months were reported
  missing     no FBI row for that agency-year (2021 NIBRS transition, non-participation)
  not_city    the reporting agency polices far more than the city (FBI covered population over 1.5 times
              the Census population, e.g. Las Vegas Metro) or far less; the rate is left blank

Consistency flag per row (2020 onward), because the 2021 switch to incident-based reporting left some agencies
filing incomplete years that still say 12 months (Chicago's violent crime reads 25,553 in 2019, 7,766 in 2021):
  break_low / break_high   violent crime under 0.6 or over 1.8 times the city's own 2015-2019 median, or property
                           crime under 0.5 or over 2 times, where the baseline is large enough to judge (200+ violent)
Flagged rates are still published; treat them as suspect. A real change can trip the flag too.

Output: data/census_out/city_crime.csv
"""
import csv, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
from compare_vera import norm

YEARS = range(2012, 2025)


def num(v):
    v = (v or "").strip()
    return int(float(v)) if v not in ("",) else None


def main():
    src = os.path.join(build.ROOT, "data", "fbi", "fbi_offenses.csv")
    fbi = {}
    for r in csv.DictReader(open(src, encoding="utf-8-sig")):
        fbi[(norm(r["city"]), r["state"], int(r["year"]))] = r
    pops = {}
    for r in csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_all_years.csv"))):
        pops[(r["pid"], int(r["fiscal_year"]))] = int(r["population"])
    cities = {}
    for r in csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_2022.csv"))):
        cities[r["pid"]] = r
    rows, cov = [], collections.Counter()
    for pid, c in cities.items():
        for y in YEARS:
            pop = pops.get((pid, y)) or pops.get((pid, y - 1)) or pops.get((pid, y + 1)) or int(c["population"])
            f = fbi.get((norm(c["city"]), c["state"], y))
            row = dict(pid=pid, city=c["city"], state=c["state"], year=y, census_population=pop)
            if not f:
                row.update(coverage="missing"); rows.append(row); cov["missing"] += 1; continue
            months = num(f.get("months_reported"))
            fpop = num(f.get("population_covered"))
            vc, pc = num(f.get("violent_crime")), num(f.get("property_crime"))
            if vc is None and pc is None:
                row.update(ori=f.get("ori", ""), agency=f.get("agency_name", ""), coverage="missing"); rows.append(row); cov["missing"] += 1; continue
            ratio = (fpop / pop) if (fpop and pop) else None
            if ratio is not None and (ratio > 1.5 or ratio < 0.67):
                coverage = "not_city"
            elif months is None:
                coverage = "unknown"
            elif months >= 12:
                coverage = "full"
            else:
                coverage = "partial"
            rate_ok = coverage in ("full", "unknown")
            row.update(ori=f.get("ori", ""), agency=f.get("agency_name", ""), fbi_population_covered=fpop,
                       population_ratio=round(ratio, 3) if ratio else "", months_reported=months if months is not None else "",
                       reporting_system=f.get("reporting_system", ""), coverage=coverage,
                       violent_crime=vc if vc is not None else "", property_crime=pc if pc is not None else "",
                       murder=num(f.get("murder")) if num(f.get("murder")) is not None else "",
                       violent_per_1k=round(1000 * vc / pop, 3) if (rate_ok and vc is not None and pop) else "",
                       property_per_1k=round(1000 * pc / pop, 3) if (rate_ok and pc is not None and pop) else "",
                       murder_per_100k=round(100000 * num(f.get("murder")) / pop, 2) if (rate_ok and num(f.get("murder")) is not None and pop) else "")
            rows.append(row); cov[coverage] += 1
    import statistics
    base = collections.defaultdict(list)
    for r in rows:
        if r.get("coverage") == "full" and 2015 <= r["year"] <= 2019 and r.get("violent_crime") != "":
            base[r["pid"]].append((r["violent_crime"], r["property_crime"] or 0))
    nflag = collections.Counter()
    for r in rows:
        r["consistency"] = ""
        b = base.get(r["pid"])
        if r["year"] < 2020 or not b or len(b) < 3 or r.get("violent_crime") in ("", None):
            continue
        mv, mp = statistics.median(x[0] for x in b), statistics.median(x[1] for x in b)
        v, pr = r["violent_crime"], r["property_crime"] or 0
        if mv >= 200 and (v < 0.6 * mv or (mp >= 1000 and pr < 0.5 * mp)):
            r["consistency"] = "break_low"
        elif mv >= 200 and (v > 1.8 * mv or (mp >= 1000 and pr > 2 * mp)):
            r["consistency"] = "break_high"
        if r["consistency"]:
            nflag[(r["year"], r["consistency"])] += 1
    print("consistency flags: " + ", ".join(f"{y} {k} {n}" for (y, k), n in sorted(nflag.items())), file=sys.stderr)
    cols = ["pid", "city", "state", "year", "census_population", "ori", "agency", "fbi_population_covered", "population_ratio",
            "months_reported", "reporting_system", "coverage", "violent_crime", "property_crime", "murder",
            "violent_per_1k", "property_per_1k", "murder_per_100k", "consistency"]
    rows.sort(key=lambda r: (r["state"], r["city"], r["year"]))
    with open(os.path.join(build.OUT, "city_crime.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    print(f"{len(rows)} city-years; coverage {dict(cov)}", file=sys.stderr)
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r["year"]][r["coverage"]] += 1
    for y in YEARS:
        print(f"  {y}: " + ", ".join(f"{k} {v}" for k, v in sorted(by[y].items())), file=sys.stderr)


if __name__ == "__main__":
    main()
