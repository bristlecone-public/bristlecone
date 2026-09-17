"""Parser check for the employment unit files: sum every LOCAL government (types 1-5) by state for the
police and fire item codes and compare with the Census Bureau's published local-government table for the
same year (<year>_local.xlsx). In a Census of Governments year (2017, 2022) every unit is in the file,
so the sums should equal the published totals.

Output: validation/employment_aggregate_check.csv
"""
import csv, glob, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

ALPHA = ["AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]
FUNC = {"Police Protection - Persons with Power of Arrest": "062", "Police Protection - Other": "162",
        "Fire Protection - Firefighters": "024", "Fire Protection - Other": "124"}


def published(year):
    import openpyxl
    p = os.path.join(build.RAW, "apes", f"{year}_local.xlsx")
    if not os.path.exists(p):
        return None
    out = {}
    for row in openpyxl.load_workbook(p, read_only=True).worksheets[0].iter_rows(values_only=True):
        if row and isinstance(row[1], str) and row[1].strip() in FUNC and isinstance(row[2], (int, float)):
            out[(row[0], FUNC[row[1].strip()])] = (int(row[2]), int(row[3]))   # full-time employees, full-time payroll
    return out


def main():
    rows = []
    for year in (2022,):
        pub = published(year)
        st = glob.glob(os.path.join(build.RAW, "apes", str(year), "**", "*empst*"), recursive=True)[0]
        mine = collections.defaultdict(lambda: [0, 0])
        for l in open(st, encoding="latin-1"):
            if l[2] not in "12345" or l[17:20] not in FUNC.values():
                continue
            k = (ALPHA[int(l[:2]) - 1], l[17:20])
            mine[k][0] += int(l[20:30].strip() or 0)
            mine[k][1] += int(l[32:44].strip() or 0)
        exact_e = exact_p = 0
        for k in sorted(pub):
            m = mine.get(k, [0, 0]); p = pub[k]
            exact_e += m[0] == p[0]; exact_p += m[1] == p[1]
            rows.append(dict(year=year, state=k[0], item=k[1], my_ft_employees=m[0], census_ft_employees=p[0], diff_employees=m[0] - p[0],
                             my_ft_payroll=m[1], census_ft_payroll=p[1], diff_payroll=m[1] - p[1]))
        print(f"{year}: {len(pub)} state-by-item cells; full-time employees exact {exact_e}, full-time payroll exact {exact_p}", file=sys.stderr)
        bad = [r for r in rows if r["year"] == year and (r["diff_employees"] or r["diff_payroll"])]
        for r in sorted(bad, key=lambda r: -abs(r["diff_employees"]))[:8]:
            print(f"   {r['state']} {r['item']}: employees {r['my_ft_employees']} vs {r['census_ft_employees']}, payroll diff {r['diff_payroll']:,}", file=sys.stderr)
    with open(os.path.join(build.ROOT, "validation", "employment_aggregate_check.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
