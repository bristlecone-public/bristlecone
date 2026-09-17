"""Build police/fire expenditure shares for US municipalities >= 100k population
from Census Bureau Annual Survey of State & Local Government Finances
individual unit files (IUF).

Run:  python pipeline/build.py
Inputs: data/census_raw/<year>/ (unzipped IUF), data/census_raw/PID_GID_Crosswalk.txt
Outputs: data/census_out/*.csv

Two IUF layouts exist:
  GID era (2012-2015): 14-char ID, 34-char data record, Fin_GID_<yr>.txt directory
  PID era (2017+):     12-char ID, 32-char data record, Fin_PID_<yr>.txt directory
Both: amounts in THOUSANDS of dollars; last char = imputation flag
  R reported, I imputed, A analyst correction, S alternative source, M unknown, N n/a
Item codes: first char = character of expenditure, last two = function.
  E current operation, F construction, G other capital outlay, I interest,
  J assistance/subsidies, L/M/Q/S intergovernmental expenditure,
  X/Y insurance trust: NOT counted. Employee-retirement codes (X11 benefit payments etc.) appear in
  the 2012-2015 public files only; from 2017 the unit file omits them (they moved to the Annual
  Survey of Public Pensions). Leaving them out in every year keeps total_expenditure comparable.
Function 62 = police protection, 24 = fire protection.
"""
import csv, glob, os, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _raw_root():
    """Where the raw source files live. They are ~2.8 GB, have never been in git, and now sit in the
    bristlecone monorepo so the provenance for every data project is in one place.

    Resolution order, so a fresh clone still works with nothing configured:
      1. $CSS_RAW_ROOT
      2. the path in data/.raw_root (one line, gitignored, per-machine)
      3. data/ inside this checkout, the original layout
    """
    env = os.environ.get("CSS_RAW_ROOT")
    if env:
        return os.path.expanduser(env.strip())
    marker = os.path.join(ROOT, "data", ".raw_root")
    if os.path.exists(marker):
        for line in open(marker, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                return os.path.expanduser(line)
    return os.path.join(ROOT, "data")


RAW_ROOT = _raw_root()
RAW = os.path.join(RAW_ROOT, "census_raw")
OUT = os.path.join(ROOT, "data", "census_out")


def data_vintage():
    """The last year each source actually contributes, read back out of the built outputs.
    Derived rather than declared: a page can then never claim a vintage the data does not have.
    Returns {source: last_year}; a source that has not been built yet is simply absent."""
    import csv as _csv
    want = (("finance", "city_police_fire_all_years.csv", "fiscal_year"),
            ("employment", "city_employment_all_years.csv", "year"),
            ("crime", "city_crime.csv", "year"))
    out = {}
    for name, fn, field in want:
        p = os.path.join(OUT, fn)
        if not os.path.exists(p):
            continue
        ys = {int(r[field]) for r in _csv.DictReader(open(p, encoding="utf-8-sig")) if r.get(field)}
        if ys:
            out[name] = max(ys)
    return out


def vintage_sentence():
    """One plain sentence naming the data vintage, for a page footer."""
    v = data_vintage()
    bits = [t for t in ((f"Census finance through fiscal year {v['finance']}" if "finance" in v else None),
                        (f"employment through {v['employment']}" if "employment" in v else None),
                        (f"reported crime through {v['crime']}" if "crime" in v else None)) if t]
    return ("Data vintage: " + ", ".join(bits) + ".") if bits else ""
POP_THRESHOLD = 100_000

FIPS_STATE = {
 '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE','11':'DC','12':'FL',
 '13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME',
 '24':'MD','25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE','32':'NV','33':'NH',
 '34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA','44':'RI',
 '45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV','55':'WI','56':'WY'}

EXP_PREFIX = set("EFGIJLMQS")
UTILITY_FN = {"90", "91", "92", "93", "94"}        # liquor stores + water/electric/gas/transit utilities
EDU_FN = {"12", "16", "18", "21", "09"}            # elem-sec, higher ed aux, higher ed, other ed, school bldg
COUNTY_LIKE_FN = {"04", "05", "36", "77", "79"}  # corrections, hospitals, public welfare (functions cities normally do not run)
# Consolidated city-counties, city-parishes, and independent cities. The county-function heuristic
# below misses several (Louisville 2.5%, Jacksonville 0.2%, Baltimore 0.1%, Honolulu 0.6%), so the
# flag is name-based. Every Virginia city is independent of any county by state constitution.
KNOWN_CONSOLIDATED = {
    ("NEW YORK", "NY"), ("PHILADELPHIA", "PA"), ("SAN FRANCISCO", "CA"), ("DENVER", "CO"), ("WASHINGTON", "DC"),
    ("NASHVILLE", "TN"), ("INDIANAPOLIS", "IN"), ("JACKSONVILLE", "FL"), ("LOUISVILLE", "KY"), ("LEXINGTON", "KY"),
    ("BATON ROUGE", "LA"), ("LAFAYETTE", "LA"), ("NEW ORLEANS", "LA"), ("AUGUSTA", "GA"), ("COLUMBUS", "GA"),
    ("MACON", "GA"), ("ATHENS", "GA"), ("WYANDOTTE", "KS"), ("HONOLULU", "HI"), ("ANCHORAGE", "AK"),
    ("BALTIMORE", "MD"), ("ST LOUIS", "MO"),
}
def is_consolidated(name, state):
    n = name.upper().replace(".", "").replace("-", " ")
    return state == "VA" or any(st == state and n.startswith(k) for k, st in KNOWN_CONSOLIDATED)

# Health other than own hospitals (32) is removed from the CORE denominator only, not from the county-like
# flag: it is a county function in most states (median 0.6% of plain municipalities' general expenditure,
# 4.1% of consolidated governments', $2.8B in San Francisco, $2.2B in Philadelphia). Judicial and legal (25)
# stays in: it is 0.8% vs 1.7% and holds municipal courts and city attorneys every city runs.
CORE_EXTRA_FN = {"32"}
ENTERPRISE_FN = {"01", "87"}                     # airports, seaports: self-funded enterprises that swell a few cities' general expenditure


def load_crosswalk():
    """PID(6) -> GID(14). File: PID space GID space name."""
    xw = {}
    with open(os.path.join(RAW, "PID_GID_Crosswalk.txt"), encoding="latin-1") as f:
        for line in f:
            pid, gid = line[0:6], line[7:21]
            if pid.strip() and gid.strip():
                xw[gid] = pid
    return xw


def find(year, pattern):
    hits = glob.glob(os.path.join(RAW, str(year), "**", pattern), recursive=True)
    return hits[0] if hits else None


def load_year(year, xw):
    """Return (directory, data). directory: unit_id -> dict(name, state, fips_place, pop, pop_year).
    data: unit_id -> {item_code: (amount_thousands, flag)}. unit_id is the 6-digit PID."""
    gid_era = year <= 2015
    dirfile = find(year, "Fin_GID_*.txt" if gid_era else "Fin_PID_*.txt")
    datfile = find(year, "*FinEstDAT*.txt")
    if not dirfile or not datfile:
        return None, None
    directory, key_of = {}, {}
    with open(dirfile, encoding="latin-1") as f:
        for l in f:
            if gid_era:
                raw_id = l[0:14]
                if raw_id[2] != "2":
                    continue
                pid = xw.get(raw_id)
                if not pid:
                    continue
                rec = dict(name=l[14:78].strip(), state=FIPS_STATE.get(l[113:115], l[113:115]),
                           fips_place=l[118:123].strip(), pop=int(l[123:132] or 0), pop_year=l[132:134].strip())
            else:
                raw_id = l[0:12]
                if raw_id[2] != "2":
                    continue
                pid = raw_id[6:12]
                rec = dict(name=l[12:76].strip(), state=FIPS_STATE.get(l[0:2], l[0:2]),
                           fips_place=l[111:116].strip(), pop=int(l[116:125] or 0), pop_year=l[125:127].strip())
            rec["raw_id"] = raw_id
            directory[pid] = rec
            key_of[raw_id] = pid
    data = collections.defaultdict(dict)
    idlen = 14 if gid_era else 12
    with open(datfile, encoding="latin-1") as f:
        for l in f:
            pid = key_of.get(l[0:idlen])
            if not pid:
                continue
            code = l[idlen:idlen + 3]
            amt = int(l[idlen + 3:idlen + 15])
            flag = l[idlen + 19:idlen + 20]
            data[pid][code] = (amt, flag)
    return directory, data


def metrics(items):
    """items: {code: (amt_k, flag)} -> dict of metrics in DOLLARS plus flags."""
    def s(pred):
        return sum(a for c, (a, _) in items.items() if pred(c)) * 1000
    def flags(pred):
        fl = sorted(set(f for c, (a, f) in items.items() if pred(c) and a))
        return "".join(fl) or "-"
    def imputed_share(pred):
        tot = sum(a for c, (a, _) in items.items() if pred(c))
        imp = sum(a for c, (a, f) in items.items() if pred(c) and f == "I")
        return round(imp / tot, 3) if tot else None
    is_exp = lambda c: c[0] in EXP_PREFIX
    total = s(is_exp)   # Census total expenditure less insurance-trust expenditure (see module docstring)
    general = s(lambda c: is_exp(c) and c[1:] not in UTILITY_FN)
    direct_general = s(lambda c: c[0] in "EFGIJ" and c[1:] not in UTILITY_FN)
    education = s(lambda c: is_exp(c) and c[1:] in EDU_FN)
    county_like = s(lambda c: is_exp(c) and c[1:] in COUNTY_LIKE_FN)
    pol = lambda c: c[0] in "EFG" and c[1:] == "62"
    fire = lambda c: c[0] in "EFG" and c[1:] == "24"
    m = dict(
        total_expenditure_usd=total,
        general_expenditure_usd=general,
        direct_general_expenditure_usd=direct_general,
        general_ex_education_usd=general - education,
        education_usd=education,
        county_like_functions_usd=county_like,
        police_usd=s(pol), police_current_ops_usd=s(lambda c: c == "E62"), police_capital_usd=s(lambda c: c in ("F62", "G62")),
        fire_usd=s(fire), fire_current_ops_usd=s(lambda c: c == "E24"), fire_capital_usd=s(lambda c: c in ("F24", "G24")),
        police_intergov_usd=s(lambda c: c[0] in "LMQS" and c[1:] == "62"),
        fire_intergov_usd=s(lambda c: c[0] in "LMQS" and c[1:] == "24"),
        enterprise_usd=s(lambda c: is_exp(c) and c[1:] in ENTERPRISE_FN),
        health_usd=s(lambda c: is_exp(c) and c[1:] in CORE_EXTRA_FN),
        core_municipal_expenditure_usd=general - education - county_like - s(lambda c: is_exp(c) and c[1:] in CORE_EXTRA_FN) - s(lambda c: is_exp(c) and c[1:] in ENTERPRISE_FN),
        police_flags=flags(pol), fire_flags=flags(fire),
        unit_imputed_share=imputed_share(is_exp),
        n_items=len(items),
    )
    # A record with zero police spending, or very few item codes, is a partial response, not a city
    # with no police: every 100k+ city has a police department or a police contract. Zero FIRE can be
    # real (independent fire district). Shares are left null on incomplete records so they cannot be
    # averaged in by mistake.
    m["record_complete"] = m["police_usd"] > 0 and len(items) >= 30 and general > 0
    core = m["core_municipal_expenditure_usd"]
    dens = (("general", general), ("total", total), ("general_ex_edu", general - education), ("core", core))
    for k, d in (("police", "police_usd"), ("fire", "fire_usd")):
        for dn, dv in dens:
            m[f"{k}_pct_{dn}"] = round(100 * m[d] / dv, 2) if (dv and m["record_complete"]) else None
    for dn, dv in dens:
        m[f"police_fire_pct_{dn}"] = round(100 * (m["police_usd"] + m["fire_usd"]) / dv, 2) if (dv and m["record_complete"]) else None
    return m


def main():
    os.makedirs(OUT, exist_ok=True)
    xw = load_crosswalk()
    years = sorted(int(os.path.basename(d)) for d in glob.glob(os.path.join(RAW, "2*")) if os.path.isdir(d))
    loaded = {}
    for y in years:
        d, data = load_year(y, xw)
        if d is None:
            print(f"{y}: no unit file found, skipped", file=sys.stderr); continue
        loaded[y] = (d, data)
        print(f"{y}: {len(d):,} municipalities, {sum(len(v) for v in data.values()):,} items", file=sys.stderr)
    # universe: any municipality with pop >= threshold in any loaded year
    universe = set()
    for y, (d, _) in loaded.items():
        universe |= {pid for pid, r in d.items() if r["pop"] >= POP_THRESHOLD}
    # latest known name/state/pop per pid
    latest = {}
    for y in sorted(loaded):
        for pid in universe:
            r = loaded[y][0].get(pid)
            if r:
                latest[pid] = dict(r, year=y)
    rows = []
    for y in sorted(loaded):
        d, data = loaded[y]
        for pid in sorted(universe):
            if pid not in data or not data[pid]:
                continue
            r = d[pid]
            m = metrics(data[pid])
            rows.append(dict(pid=pid, census_raw_id=r["raw_id"], city=r["name"].replace(" CITY", "").replace(" TOWN", "").title(),
                             state=r["state"], fips_place=r["fips_place"], fiscal_year=y,
                             population=r["pop"], population_year="20" + r["pop_year"] if r["pop_year"] else "",
                             full_census_year=(y % 5 == 2), **m))
    cols = list(rows[0].keys())
    with open(os.path.join(OUT, "city_police_fire_all_years.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    # wide summary: latest full-census year
    fc = max(y for y in loaded if y % 5 == 2)
    with open(os.path.join(OUT, f"city_police_fire_{fc}.csv"), "w", newline="") as f:
        sub = sorted((r for r in rows if r["fiscal_year"] == fc), key=lambda r: -r["population"])
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(sub)
    # documented source-data issues found in validation (data/known_issues.csv), appended to that year's notes
    known = collections.defaultdict(list)
    ki = os.path.join(ROOT, "data", "known_issues.csv")
    if os.path.exists(ki):
        for k in csv.DictReader(open(ki, encoding="utf-8")):
            known[(k["pid"], int(k["fiscal_year"]))].append(("verified issue: " if k["status"] == "verified" else "possible issue: ") + k["finding"].split(". ")[0])
    # comparability flags from the data itself (latest full census year)
    with open(os.path.join(OUT, "city_flags.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pid", "city", "state", "fiscal_year", "runs_schools", "county_like_functions", "education_pct_general", "county_like_pct_general", "police_flags", "fire_flags", "unit_imputed_share", "record_complete", "fire_external", "police_contracted", "consolidated_or_independent", "note"])
        for r in sorted((r for r in rows if r["fiscal_year"] == fc), key=lambda r: -r["population"]):
            g = r["general_expenditure_usd"] or 1
            edu = 100 * r["education_usd"] / g; cl = 100 * r["county_like_functions_usd"] / g
            notes = []
            cons = is_consolidated(r["city"], r["state"])
            if cons: notes.append("consolidated city-county, city-parish, or independent city: carries county-type functions")
            if edu > 5: notes.append("dependent school system inside city books")
            if cl > 3 and not cons: notes.append("carries county-type functions (corrections/hospital/welfare) above 3% of general expenditure")
            if r["police_flags"] not in ("R", "-") or r["fire_flags"] not in ("R", "-"): notes.append("police/fire contains imputed or analyst-adjusted items")
            if (r["unit_imputed_share"] or 0) > 0.5: notes.append("majority of unit expenditure imputed (nonrespondent)")
            if not r["record_complete"]: notes.append("incomplete record this year (partial response); shares null")
            if r["fire_usd"] == 0 and r["record_complete"]: notes.append("no fire spending on city books: fire provided by independent district or county")
            if r["police_intergov_usd"] > r["police_usd"] or (r["record_complete"] and r["police_pct_core"] is not None and float(r["police_pct_core"]) < 5): notes.append("police share under 5%: likely contracts with county sheriff (Census books such purchases as unallocated intergovernmental expenditure, invisible in code 62)")
            if r["fire_intergov_usd"] > r["fire_usd"]: notes.append("fire provided by contract with another government")
            notes.extend(known.get((r["pid"], fc), []))
            w.writerow([r["pid"], r["city"], r["state"], fc, edu > 5, cl > 3, round(edu, 1), round(cl, 1), r["police_flags"], r["fire_flags"], r["unit_imputed_share"], r["record_complete"], r["fire_usd"] == 0 and r["record_complete"], r["police_intergov_usd"] > r["police_usd"] or (r["record_complete"] and r["police_pct_core"] is not None and float(r["police_pct_core"]) < 5), cons, "; ".join(notes)])
    print(f"universe {len(universe)} cities, {len(rows)} city-years, years {sorted(loaded)}", file=sys.stderr)


if __name__ == "__main__":
    main()
