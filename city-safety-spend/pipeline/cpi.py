"""CPI-U (BLS series CUUR0000SA0, U.S. city average, all items, not seasonally adjusted), annual averages.

Fetched from the BLS Public Data API v2 without a key (10 years per request, 25 requests per day) and
cross-checked against FRED CPIAUCNS, which republishes the same series monthly. The result is written
to data/cpi/cpi_u_annual.csv and committed, so the build does not depend on the API.

Alignment rule (METHODOLOGY section 7): Census fiscal year Y covers fiscal years ending 1 July Y-1 to
30 June Y, whose midpoints all fall in calendar year Y-1. Finance dollars for Census year Y are
therefore deflated with the calendar Y-1 annual average. Employment payroll is a March Y snapshot and
is deflated with the calendar Y annual average.

Run:  python pipeline/cpi.py          (refresh from BLS)
Use:  from cpi import to_real, BASE_YEAR
"""
import csv, json, os, sys, time, urllib.request, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "cpi", "cpi_u_annual.csv")
SERIES = "CUUR0000SA0"


def fetch(first=1966, last=2025):
    out = {}
    for start in range(first, last + 1, 10):
        end = min(start + 9, last)
        body = json.dumps({"seriesid": [SERIES], "startyear": str(start), "endyear": str(end), "annualaverage": True}).encode()
        req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/", data=body,
                                     headers={"Content-Type": "application/json", "User-Agent": "city-safety-spend research"})
        res = json.load(urllib.request.urlopen(req, timeout=60))
        if res.get("status") != "REQUEST_SUCCEEDED":
            raise SystemExit(f"BLS API: {res.get('status')} {res.get('message')}")
        months = {}
        for d in res["Results"]["series"][0]["data"]:
            y = int(d["year"])
            if d["value"].strip() in ("-", ""):       # BLS marks uncollected months with "-" (October 2025 shutdown gap)
                continue
            if d["period"] == "M13":
                out[y] = float(d["value"])
            elif d["period"].startswith("M"):
                months.setdefault(y, []).append(float(d["value"]))
        for y, v in months.items():           # older years can lack an M13 row; compute it
            if y not in out and len(v) == 12:
                out[y] = round(statistics.mean(v), 3)
        time.sleep(1)
    return out


def check_against_fred(bls, local=None):
    """Largest |BLS annual - mean of FRED monthly| over complete years. `local` = a curl-downloaded
    fredgraph.csv, used when FRED times out for Python clients."""
    if local and os.path.exists(local):
        raw = open(local).read()
    else:
        try:
            raw = urllib.request.urlopen(urllib.request.Request("https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS",
                                                                headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode()
        except Exception as e:
            print(f"FRED cross-check skipped: {e}", file=sys.stderr)
            return None
    months = {}
    for row in list(csv.reader(raw.splitlines()))[1:]:
        if row[1] in (".", ""):
            continue
        y = int(row[0][:4]); months.setdefault(y, []).append(float(row[1]))
    worst = max(abs(bls[y] - statistics.mean(months[y])) for y in bls if len(months.get(y, [])) == 12)
    return worst


def main():
    bls = fetch()
    worst = check_against_fred(bls, local=sys.argv[1] if len(sys.argv) > 1 else None)
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["calendar_year", "cpi_u_annual_avg", "series", "source"])
        for y in sorted(bls):
            w.writerow([y, bls[y], SERIES, "BLS Public Data API v2"])
    msg = f"{worst:.3f} index points" if worst is not None else "not run"
    print(f"{len(bls)} years {min(bls)}-{max(bls)}; largest difference from FRED monthly mean: {msg}", file=sys.stderr)


_cache = None
def table():
    global _cache
    if _cache is None:
        _cache = {int(r["calendar_year"]): float(r["cpi_u_annual_avg"]) for r in csv.DictReader(open(PATH))}
    return _cache

def base_year():
    return max(table())

def to_real(nominal, census_year=None, calendar_year=None):
    """Convert nominal dollars to base-year dollars. Pass census_year for finance data (uses Y-1),
    calendar_year for March payroll snapshots."""
    t = table()
    y = census_year - 1 if census_year is not None else calendar_year
    if nominal in (None, "") or y not in t:
        return None
    return round(float(nominal) * t[base_year()] / t[y])


if __name__ == "__main__":
    main()
