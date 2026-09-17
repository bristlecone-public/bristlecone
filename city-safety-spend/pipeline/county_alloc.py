"""County jails and courts allocated to cities (Phase 2, item 3C, narrowed by the adversarial audit).

Every resident of a city also pays, through the county, for jails and courts the city does not run. This
adds a population share of the overlying county government's

  corrections   E/F/G 04 (institutions) + 05 (other: probation, parole, alternatives)
  judicial      E/F/G 25 (courts, prosecutors, public defenders, sheriff court security and civil process)

and deliberately does NOT allocate county police (62), because county sheriff patrol covers unincorporated
areas and contract towns, not cities with their own departments. The one exception is cities flagged
`police_contracted` (the county force is their police): for them a population share of county police is
reported in its own column.

Consolidated city-counties and independent cities have no separate county government in the Census
records (verified for Philadelphia, San Francisco, Nashville, Jacksonville, Louisville, Indianapolis,
St. Louis, Virginia Beach, Washington), so nothing is allocated to them; their own corrections and
judicial spending is already on the city's books and is counted as "own".

Shares: for each county the city lies in, city population in that county / county population, from the
Census Bureau population estimates (place-within-county, summary level 157), same year as the finance data.
Census years 2012, 2017, 2022 only, because only census years include every county.
State-funded courts and state prisons are not on any local record and are not included.

Output: data/census_out/city_county_allocation.csv
"""
import csv, glob, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, cpi

RAW = os.path.join(build.RAW_ROOT, "county_alloc", "raw")
YEARS = (2012, 2017, 2022)
CORR, JUD, POL = ("04", "05"), ("25",), ("62",)


def pep_parts(year):
    """{state+place: {state+county: pop}}, {state+county: county pop}"""
    f = os.path.join(RAW, "sub-est2024.csv" if year >= 2020 else "sub-est2019_all.csv")
    parts, county = collections.defaultdict(dict), {}
    col = f"POPESTIMATE{year}"
    for r in csv.DictReader(open(f, encoding="latin-1")):
        if r["SUMLEV"] == "050":
            county[r["STATE"] + r["COUNTY"]] = int(r[col])
        elif r["SUMLEV"] == "157":
            parts[r["STATE"] + r["PLACE"]][r["STATE"] + r["COUNTY"]] = int(r[col])
    return parts, county


def county_spending(year):
    """{state fips + county fips: {'corr','jud','pol','name'}} for every county government (type 1)."""
    gid_era = year <= 2015
    base = os.path.join(build.RAW, str(year))
    dirf = glob.glob(os.path.join(base, "**", "Fin_GID_*.txt" if gid_era else "Fin_PID_*.txt"), recursive=True)[0]
    datf = glob.glob(os.path.join(base, "**", "*FinEstDAT*.txt"), recursive=True)[0]
    idlen = 14 if gid_era else 12
    key = {}
    for l in open(dirf, encoding="latin-1"):
        if l[2] != "1":
            continue
        if gid_era:
            key[l[:14]] = (l[113:115] + l[115:118], l[14:78].strip())
        else:
            key[l[:12]] = (l[:2] + l[3:6], l[12:76].strip())
    out = collections.defaultdict(lambda: dict(corr=0, jud=0, pol=0, name=""))
    for l in open(datf, encoding="latin-1"):
        k = key.get(l[:idlen])
        if not k:
            continue
        code = l[idlen:idlen + 3]
        if code[0] not in "EFG":
            continue
        amt = int(l[idlen + 3:idlen + 15]) * 1000
        fn = code[1:]
        rec = out[k[0]]; rec["name"] = k[1]
        if fn in CORR: rec["corr"] += amt
        elif fn in JUD: rec["jud"] += amt
        elif fn in POL: rec["pol"] += amt
    return out


def main():
    inv = {v: k for k, v in build.FIPS_STATE.items()}
    flags = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_flags.csv")))}
    xw = build.load_crosswalk()
    rows, notfound = [], collections.defaultdict(list)
    for year in YEARS:
        parts, cpop = pep_parts(year)
        counties = county_spending(year)
        d, data = build.load_year(year, xw)
        fin = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_all_years.csv"))) if int(r["fiscal_year"]) == year}
        for pid, r in fin.items():
            items = data.get(pid, {})
            own = lambda fns: sum(items.get(c + fn, (0, ""))[0] for c in "EFG" for fn in fns) * 1000
            geoid = inv[r["state"]] + r["fips_place"].zfill(5)
            p = parts.get(geoid)
            if not p:
                # fall back to the county in the unit ID with the city's full population
                cid = r["census_raw_id"][:2] + r["census_raw_id"][3:6] if len(r["census_raw_id"]) == 12 else ""
                p = {cid: int(r["population"])} if cid else {}
                notfound[year].append(f"{r['city']} {r['state']}")
            alloc = dict(corr=0.0, jud=0.0, pol=0.0)
            used = []
            for c, part_pop in p.items():
                if c in counties and cpop.get(c) and part_pop > 0:
                    share = min(part_pop / cpop[c], 1.0)
                    for k in alloc:
                        alloc[k] += counties[c][k] * share
                    used.append(f"{counties[c]['name']} {share:.3f}")
            contracted = flags.get(pid, {}).get("police_contracted") == "True"
            pop = int(r["population"])
            police, fire = int(r["police_usd"]), int(r["fire_usd"])
            own_corr, own_jud = own(CORR), own(JUD)
            total = police + fire + own_corr + own_jud + alloc["corr"] + alloc["jud"] + (alloc["pol"] if contracted else 0)
            row = dict(pid=pid, city=r["city"], state=r["state"], fiscal_year=year, population=pop,
                       overlying_counties="; ".join(used), has_county_government=bool(used),
                       police_usd=police, fire_usd=fire, own_corrections_usd=own_corr, own_judicial_usd=own_jud,
                       county_corrections_alloc_usd=round(alloc["corr"]), county_judicial_alloc_usd=round(alloc["jud"]),
                       county_police_contract_alloc_usd=round(alloc["pol"]) if contracted else "",
                       public_safety_and_justice_usd=round(total),
                       public_safety_and_justice_real_per_resident=round(cpi.to_real(total, census_year=year) / pop, 2) if pop else "",
                       record_complete=r["record_complete"])
            rows.append(row)
    rows.sort(key=lambda r: (r["state"], r["city"], r["fiscal_year"]))
    with open(os.path.join(build.OUT, "city_county_allocation.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    for y in YEARS:
        yr = [r for r in rows if r["fiscal_year"] == y]
        print(f"{y}: {len(yr)} cities, {sum(1 for r in yr if r['has_county_government'])} with an overlying county government; "
              f"place not in population estimates (unit-ID county used): {notfound[y]}", file=sys.stderr)


if __name__ == "__main__":
    main()
