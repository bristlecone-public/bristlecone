"""Regional Price Parities for the 332-city universe (Phase 2, item 1B(ii)).

Source: BEA Regional Price Parities by metropolitan statistical area, 2008-2024 (MARPP, released
2026-02-19, OMB bulletin 23-01 delineations). U.S. = 100. Line 1 all items; line 3 housing services
(rents) is kept too because it drives most of the regional variation.

Geography: primary key is the county in each city's 2022 Census unit ID (positions 4-6, "county where the
government is located"), matched to the July 2023 OMB county-to-CBSA delineation (list1_2023), the same
vintage BEA uses. The 2022 IDs already use Connecticut's planning regions, which the 2023 delineation also
uses. As a cross-check, the city's Census place code is run through the 2020 place-by-county file and the
majority CBSA of its counties is compared; disagreements are listed.

What RPP is and is not: an index of consumer prices, dominated by rents. It is a reasonable proxy for how
far a dollar goes in a region and loosely tracks the wages a city must pay, but it does not measure
public-sector compensation. Adjusted figures are labelled "regional-price-adjusted", never "labor-cost-adjusted".

Inputs:  data/rpp/raw/MARPP.zip, data/rpp/raw/national_place_by_county2020.txt, data/rpp/raw/list1_2023.xlsx
Outputs: data/rpp/rpp_msa.csv (all-items and housing lines, committed)
         data/census_out/city_rpp.csv
"""
import csv, io, os, sys, zipfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

RAW = os.path.join(build.RAW_ROOT, "rpp", "raw")
YEARS = list(range(2008, 2025))
INV = {v: k for k, v in build.FIPS_STATE.items()}


def load_rpp():
    z = zipfile.ZipFile(os.path.join(RAW, "MARPP.zip"))
    name = [n for n in z.namelist() if n.startswith("MARPP_MSA") and n.endswith(".csv")][0]
    out = {}
    for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="latin-1")):
        code = (r.get("GeoFIPS") or "").strip().strip('"')
        line = (r.get("LineCode") or "").strip()
        if not code.isdigit() or line not in ("1", "3"):
            continue
        vals = {y: (float(r[str(y)]) if r.get(str(y)) not in (None, "", "(NA)") else None) for y in YEARS}
        out.setdefault(code, {"name": r["GeoName"].strip().strip('"')})["all" if line == "1" else "housing"] = vals
    return out


def load_delineation():
    import openpyxl
    ws = openpyxl.load_workbook(os.path.join(RAW, "list1_2023.xlsx"), read_only=True).worksheets[0]
    county = {}
    for row in ws.iter_rows(min_row=4, values_only=True):
        if row[0] and row[9] and row[10] and row[4] == "Metropolitan Statistical Area":
            county[str(row[9]).zfill(2) + str(row[10]).zfill(3)] = (str(row[0]), row[3])
    return county


def main():
    rpp = load_rpp()
    with open(os.path.join(build.ROOT, "data", "rpp", "rpp_msa.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["cbsa", "name", "line"] + YEARS)
        for code, d in sorted(rpp.items()):
            for line in ("all", "housing"):
                if line in d:
                    w.writerow([code, d["name"], line] + [d[line][y] for y in YEARS])
    county_cbsa = load_delineation()
    place_counties = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(RAW, "national_place_by_county2020.txt"), encoding="latin-1"), delimiter="|"):
        place_counties[r["STATEFP"] + r["PLACEFP"]].append(r["STATEFP"] + r["COUNTYFP"])
    cities = {}
    for r in csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_all_years.csv"))):
        if r["pid"] not in cities or int(r["fiscal_year"]) == 2022:
            cities[r["pid"]] = r
    out, unmapped, ties = [], [], []
    for pid, r in sorted(cities.items(), key=lambda kv: (kv[1]["state"], kv[1]["city"])):
        geoid = INV[r["state"]] + r["fips_place"].zfill(5)
        id_county = r["census_raw_id"][:2] + r["census_raw_id"][3:6] if len(r["census_raw_id"]) == 12 else ""
        primary = county_cbsa.get(id_county)
        cb = collections.Counter(county_cbsa[c] for c in place_counties.get(geoid, []) if c in county_cbsa)
        check = cb.most_common(1)[0][0] if cb else None
        if not primary:
            unmapped.append(f"{r['city']} {r['state']} (county {id_county})"); continue
        if check and check != primary:
            ties.append(f"{r['city']} {r['state']}: unit-ID county gives {primary[1]}, place file majority gives {check[1]}")
        code, title = primary
        d = rpp.get(code)
        row = dict(pid=pid, city=r["city"], state=r["state"], place_geoid=geoid, cbsa=code, cbsa_title=title,
                   bea_name=d["name"] if d else "", counties=len(place_counties[geoid]))
        for y in YEARS:
            row[f"rpp_{y}"] = d["all"][y] if d and "all" in d else None
        row["rpp_housing_2022"] = d["housing"][2022] if d and "housing" in d else None
        out.append(row)
    with open(os.path.join(build.OUT, "city_rpp.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    missing = [f"{r['city']} {r['state']} ({r['cbsa']})" for r in out if r["rpp_2022"] is None]
    print(f"{len(out)} of {len(cities)} cities mapped to a metro area; unmapped: {unmapped}", file=sys.stderr)
    print(f"unit-ID county and place-file cross-check disagree: {ties}", file=sys.stderr)
    print(f"mapped but no BEA RPP for 2022: {missing}", file=sys.stderr)
    v = sorted(r["rpp_2022"] for r in out if r["rpp_2022"])
    print(f"2022 RPP across cities: min {v[0]:.1f}, quartiles {v[len(v)//4]:.1f} / {v[len(v)//2]:.1f} / {v[3*len(v)//4]:.1f}, max {v[-1]:.1f}", file=sys.stderr)


if __name__ == "__main__":
    main()
