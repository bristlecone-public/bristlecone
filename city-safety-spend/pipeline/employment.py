"""Police and fire employment for the 332-city universe from the Census Bureau Annual Survey of Public
Employment & Payroll (ASPEP) and Census of Governments: Employment individual unit files, 2012-2025.

Inputs: data/census_raw/apes/<year>/ (unzipped), data/census_raw/PID_GID_Crosswalk.txt
Output: data/census_out/city_employment_all_years.csv

Record layout, identical in positions 1-72 in every year 2012-2025 (verified against each era's tech doc):
  1-14 legacy unit ID (Census alphabetical state code, type, county, unit, supplement, sub)
  18-20 item code: 000 total, 062 police persons with power of arrest, 162 police other,
        024 fire protection firefighters, 124 fire protection other
  21-30 full-time employees, 32 flag; 33-44 full-time March payroll, 46 flag
  47-56 part-time employees, 58 flag; 59-70 part-time March payroll, 72 flag
  2021+: 75-80 new 6-digit unit ID (the same PID the finance pipeline keys on)
Payroll is gross pay for March, 31-day monthly equivalent. It does NOT include employer pension or
benefit costs, which is why it is comparable across cities where finance dollars are not.

Flags (tech doc section 2.4): reported R C K U V Z; T = reported unit total prorated across functions by
last year's distribution (so the sworn/civilian split is estimated); anything else = imputed.

Deliberately not produced: finance expenditure divided by employees (see docs/ADVERSARIAL_AUDIT_RESPONSE.md).
"""
import csv, glob, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build, cpi

RAW = os.path.join(build.RAW, "apes")
REPORTED, PRORATED = set("RCKUVZ"), set("T")
CODES = {"000": "total", "062": "police_sworn", "162": "police_other", "024": "fire_firefighters", "124": "fire_other"}


def flag_class(flags):
    fl = {f for f in flags if f.strip()}
    if not fl:
        return ""
    if fl <= REPORTED:
        return "reported"
    if fl <= REPORTED | PRORATED:
        return "prorated"
    return "imputed"


def num(s):
    s = s.strip()
    return int(s) if s.lstrip("-").isdigit() else 0


def main():
    xw = build.load_crosswalk()
    fin = {}
    for r in csv.DictReader(open(os.path.join(build.OUT, "city_police_fire_all_years.csv"))):
        fin.setdefault(r["pid"], r)
    names = {pid: (r["city"], r["state"]) for pid, r in fin.items()}
    rows, mismatch = [], 0
    for year in range(2012, 2026):
        st = glob.glob(os.path.join(RAW, str(year), "**", "*empst*"), recursive=True)
        idf = glob.glob(os.path.join(RAW, str(year), "**", "*empid*"), recursive=True)
        if not st:
            print(f"{year}: no employment file", file=sys.stderr); continue
        pop = {}
        for l in open(idf[0], encoding="latin-1"):
            if l[2] == "2":
                pop[l[:14]] = (num(l[125:134]), l[134:136].strip())
        data = collections.defaultdict(dict)
        for l in open(st[0], encoding="latin-1"):
            if l[2] != "2":
                continue
            code = l[17:20]
            if code not in CODES:
                continue
            gid = l[:14]
            legacy_pid = xw.get(gid)
            new_pid = l[74:80].strip() if year >= 2021 else ""
            if new_pid and legacy_pid and new_pid != legacy_pid:
                mismatch += 1
            pid = new_pid or legacy_pid
            if pid not in names:
                continue
            data[pid]["_gid"] = gid
            data[pid][CODES[code]] = dict(ft=num(l[20:30]), ft_flag=l[31], ft_pay=num(l[32:44]), ft_pay_flag=l[45],
                                          pt=num(l[46:56]), pt_flag=l[57], pt_pay=num(l[58:70]), pt_pay_flag=l[71])
        for pid, d in data.items():
            g = lambda k, f: d.get(k, {}).get(f, 0)
            p, pyear = pop.get(d["_gid"], (0, ""))
            sworn, civ, ff, fo = g("police_sworn", "ft"), g("police_other", "ft"), g("fire_firefighters", "ft"), g("fire_other", "ft")
            pol_fl = [d.get(k, {}).get(x, " ") for k in ("police_sworn", "police_other") for x in ("ft_flag", "ft_pay_flag")]
            fire_fl = [d.get(k, {}).get(x, " ") for k in ("fire_firefighters", "fire_other") for x in ("ft_flag", "ft_pay_flag")]
            def per_ft_annual(k):
                ft, pay = g(k, "ft"), g(k, "ft_pay")
                return round(12 * pay / ft) if ft else None
            row = dict(pid=pid, city=names[pid][0], state=names[pid][1], year=year, full_census_year=(year % 5 == 2),
                       population=p, population_year=("20" + pyear) if pyear else "",
                       police_sworn_ft=sworn, police_sworn_pt=g("police_sworn", "pt"),
                       police_other_ft=civ, police_other_pt=g("police_other", "pt"),
                       fire_firefighters_ft=ff, fire_firefighters_pt=g("fire_firefighters", "pt"),
                       fire_other_ft=fo, fire_other_pt=g("fire_other", "pt"),
                       city_total_ft=g("total", "ft"), city_total_pt=g("total", "pt"),
                       police_sworn_march_payroll_usd=g("police_sworn", "ft_pay"), police_other_march_payroll_usd=g("police_other", "ft_pay"),
                       fire_firefighters_march_payroll_usd=g("fire_firefighters", "ft_pay"), fire_other_march_payroll_usd=g("fire_other", "ft_pay"),
                       police_flag_class=flag_class(pol_fl), fire_flag_class=flag_class(fire_fl),
                       police_flags="".join(sorted({f for f in pol_fl if f.strip()})), fire_flags="".join(sorted({f for f in fire_fl if f.strip()})),
                       sworn_per_1k=round(1000 * sworn / p, 3) if p else None,
                       firefighters_per_1k=round(1000 * ff / p, 3) if p else None,
                       police_civilian_share=round(civ / (sworn + civ), 4) if (sworn + civ) else None,
                       police_fire_share_of_city_ft=round((sworn + civ + ff + fo) / g("total", "ft"), 4) if g("total", "ft") else None,
                       sworn_pay_annualized_usd=per_ft_annual("police_sworn"),
                       firefighter_pay_annualized_usd=per_ft_annual("fire_firefighters"))
            row["sworn_pay_annualized_real_usd"] = cpi.to_real(row["sworn_pay_annualized_usd"], calendar_year=year)
            row["firefighter_pay_annualized_real_usd"] = cpi.to_real(row["firefighter_pay_annualized_usd"], calendar_year=year)
            row["real_dollar_base_year"] = cpi.base_year()
            rows.append(row)
        print(f"{year}: {len(data)} cities", file=sys.stderr)
    if mismatch:
        raise SystemExit(f"new unit ID and legacy crosswalk disagree on {mismatch} records")
    rows.sort(key=lambda r: (r["state"], r["city"], r["year"]))
    with open(os.path.join(build.OUT, "city_employment_all_years.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} city-years; new-ID/legacy agreement checked on 2021-2025 records", file=sys.stderr)


if __name__ == "__main__":
    main()
