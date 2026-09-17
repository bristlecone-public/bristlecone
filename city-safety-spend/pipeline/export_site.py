"""Bundle the outputs into site/data.js for the dashboard artifact."""
import csv, datetime, json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

SITE = os.path.join(build.ROOT, "site")
os.makedirs(SITE, exist_ok=True)

def f(x):
    return float(x) if x not in ("", None) else None

wide = list(csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_2022.csv"))))
flags = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_flags.csv")))}
longs = list(csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_1967_2024_long.csv"))))
fisc = {(r["city"].lower(), r["state"], r["fiscal_year"]): r for r in csv.DictReader(open(os.path.join(build.OUT, "fisc_share.csv")))}
from compare_vera import norm
fisc_n = {(norm(k[0]), k[1]): v for k, v in fisc.items() if k[2] == "2022"}

series = collections.defaultdict(lambda: dict(y=[], pf=[], p=[], fi=[], src=[], pc=[], pcp=[], pcf=[]))
for r in longs:
    s = series[r["place_geoid"]]
    s["y"].append(int(r["fiscal_year"])); s["pf"].append(f(r["police_fire_pct_general"])); s["p"].append(f(r["police_pct_general"])); s["fi"].append(f(r["fire_pct_general"]))
    s["src"].append("c" if r["source"].startswith("census") else "w")
    s["pc"].append(f(r["police_fire_real_per_resident"])); s["pcp"].append(f(r["police_real_per_resident"])); s["pcf"].append(f(r["fire_real_per_resident"]))

INV = {v: k for k, v in build.FIPS_STATE.items()}
import cpi
rpp = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_rpp.csv")))}
peer_rows = collections.defaultdict(list)
for r in csv.DictReader(open(os.path.join(build.OUT, "peer_groups.csv"))):
    peer_rows[r["pid"]].append(r)
long22 = {r["place_geoid"]: r for r in longs if r["fiscal_year"] == "2022"}
crime = collections.defaultdict(dict)
for r in csv.DictReader(open(os.path.join(build.OUT, "city_crime.csv"))):
    crime[r["pid"]][int(r["year"])] = dict(v=f(r["violent_per_1k"]), p=f(r["property_per_1k"]), m=f(r["murder_per_100k"]),
                                           cov=r["coverage"], flag=r["consistency"], agency=r["agency"])
alloc22 = {r["pid"]: r for r in csv.DictReader(open(os.path.join(build.OUT, "city_county_allocation.csv"))) if r["fiscal_year"] == "2022"}
def justice(pid):
    a = alloc22.get(pid)
    if not a:
        return None
    g = lambda k: float(a[k]) if a[k] not in ("", None) else None
    return dict(pf=g("police_usd") + g("fire_usd"), own_corr=g("own_corrections_usd"), own_jud=g("own_judicial_usd"),
                cnty_corr=g("county_corrections_alloc_usd"), cnty_jud=g("county_judicial_alloc_usd"), cnty_pol=g("county_police_contract_alloc_usd"),
                total=g("public_safety_and_justice_usd"), per_res=g("public_safety_and_justice_real_per_resident"),
                counties=a["overlying_counties"], has_county=a["has_county_government"] == "True")
emp = collections.defaultdict(dict)
for r in csv.DictReader(open(os.path.join(build.OUT, "city_employment_all_years.csv"))):
    emp[r["pid"]][int(r["year"])] = dict(year=int(r["year"]), sworn=int(r["police_sworn_ft"]), civ=int(r["police_other_ft"]), ff=int(r["fire_firefighters_ft"]),
        sw1k=f(r["sworn_per_1k"]), ff1k=f(r["firefighters_per_1k"]), civsh=f(r["police_civilian_share"]),
        pay=f(r["sworn_pay_annualized_real_usd"]), ffpay=f(r["firefighter_pay_annualized_real_usd"]),
        pfl=r["police_flag_class"], ffl=r["fire_flag_class"])
cities = []
for r in wide:
    g = INV[r["state"]] + r["fips_place"].zfill(5)
    fl = flags.get(r["pid"], {})
    fs = fisc_n.get((norm(r["city"]), r["state"]))
    cities.append(dict(
        id=g, city=r["city"], state=r["state"], pop=int(r["population"]),
        police=int(r["police_usd"]), fire=int(r["fire_usd"]),
        general=int(r["general_expenditure_usd"]), total=int(r["total_expenditure_usd"]),
        core=int(r["core_municipal_expenditure_usd"]), gen_ex_edu=int(r["general_ex_education_usd"]),
        pflag=r["police_flags"], fflag=r["fire_flags"], complete=r["record_complete"] == "True",
        runs_schools=fl.get("runs_schools") == "True", county=fl.get("county_like_functions") == "True",
        fire_ext=fl.get("fire_external") == "True", contracted=fl.get("police_contracted") == "True",
        note=fl.get("note", ""),
        consolidated=fl.get("consolidated_or_independent") == "True",
        # FiSC republishes bad source zeros (Syracuse 2022, Toledo 2022-23): suppress when the city-only police is 0 or our record is incomplete
        fisc_pf=f(fs["fisc_police_fire_pct_general"]) if (fs and r["record_complete"] == "True" and float(fs["cityonly_police_fire_pct_general"] or 0) > 0) else None,
        fisc_general=int(fs["fisc_general_expenditure_usd"]) if (fs and float(fs["cityonly_police_fire_pct_general"] or 0) > 0) else None,
        fisc_police=int(fs["fisc_police_usd"]) if (fs and float(fs["cityonly_police_fire_pct_general"] or 0) > 0) else None,
        fisc_fire=int(fs["fisc_fire_usd"]) if (fs and float(fs["cityonly_police_fire_pct_general"] or 0) > 0) else None,
        series=series.get(g, {}),
        pf_real=cpi.to_real(int(r["police_usd"]) + int(r["fire_usd"]), census_year=2022),
        rpp21=f(rpp.get(r["pid"], {}).get("rpp_2021")), cbsa=rpp.get(r["pid"], {}).get("cbsa_title", ""),
        pf_rpp_per_res=f(long22.get(INV[r["state"]] + r["fips_place"].zfill(5), {}).get("police_fire_real_rpp_per_resident")),
        peer_pids=[x["peer_pid"] for x in sorted(peer_rows[r["pid"]], key=lambda x: int(x["rank"]))],
        peer_quality=(peer_rows[r["pid"]][0]["group_quality"] if peer_rows[r["pid"]] else ""),
        justice=justice(r["pid"]),
        crime={y: crime[r["pid"]][y] for y in (2019, 2022, 2024) if y in crime[r["pid"]]},
        emp=emp[r["pid"]].get(2022), emp_latest=emp[r["pid"]][max(emp[r["pid"]])] if emp[r["pid"]] else None,
    ))
pid_to_id = {r["pid"]: INV[r["state"]] + r["fips_place"].zfill(5) for r in wide}
for c in cities:
    c["peers"] = [pid_to_id[p] for p in c.pop("peer_pids") if p in pid_to_id]
cities.sort(key=lambda c: -c["pop"])
ann = [r for r in csv.DictReader(open(os.path.join(build.ROOT, "data", "annotations.csv"), encoding="utf-8"))]
meta_ann = [dict(scope=a["scope"], state=a["state"], year=int(a["year"]), end=int(a["end_year"]) if a["end_year"] else None,
                 label=a["label"], note=a["note"], url=a["source_url"]) for a in ann]
meta = dict(annotations=meta_ann, built=datetime.date.today().isoformat(),
            vintage=build.vintage_sentence(), n=len(cities), years=sorted({y for c in cities for y in c["series"].get("y", [])}), real_base=cpi.base_year())
with open(os.path.join(SITE, "data.js"), "w", encoding="utf-8") as fh:
    fh.write("window.CSS_DATA=" + json.dumps(dict(meta=meta, cities=cities), separators=(",", ":")) + ";")
print(len(cities), "cities;", os.path.getsize(os.path.join(SITE, "data.js")) // 1024, "KB")
