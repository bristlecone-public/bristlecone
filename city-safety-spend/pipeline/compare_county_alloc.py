"""Validation of the county jail and courts allocation against the Lincoln Institute Fiscally Standardized
Cities county components (corrections_cnty, admin_judicial_cnty), which FiSC builds from the same Census
county records with its own GIS-based apportionment. Agreement tests our population-share method and
county matching; it is not independent of the Census source.

FiSC workbook values are real per-capita 2023 dollars; nominal total = value / cpi * city_population.
Output: validation/county_alloc_vs_fisc.csv
"""
import csv, os, sys, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build
from compare_vera import norm


def fisc_rows():
    import openpyxl
    ws = openpyxl.load_workbook(os.path.join(build.RAW_ROOT, "fisc", "raw", "FiSC-Full-Dataset-2023-Update.xlsx"), read_only=True)["Data"]
    it = ws.iter_rows(values_only=True); hdr = next(it); ix = {h: i for i, h in enumerate(hdr)}
    out = {}
    for row in it:
        y = row[ix["year"]]
        if y not in (2012, 2017, 2022):
            continue
        if ": " not in (row[ix["city_name"]] or ""):      # the workbook's aggregate rows (e.g. national averages)
            continue
        st, name = row[ix["city_name"]].split(": ", 1)
        cpi, pop = row[ix["cpi"]], row[ix["city_population"]]
        tot = lambda k: (row[ix[k]] / cpi * pop) if row[ix[k]] is not None else None
        out[(norm(name), st, y)] = dict(corr=tot("corrections_cnty"), jud=tot("admin_judicial_cnty"), pol=tot("police_cnty"), fisc_name=row[ix["city_name"]])
    return out


def main():
    fisc = fisc_rows()
    out = []
    for r in csv.DictReader(open(os.path.join(build.OUT, "city_county_allocation.csv"))):
        f = fisc.get((norm(r["city"]), r["state"], int(r["fiscal_year"])))
        if not f:
            continue
        ours_c, ours_j = float(r["county_corrections_alloc_usd"]), float(r["county_judicial_alloc_usd"])
        out.append(dict(city=r["city"], state=r["state"], year=int(r["fiscal_year"]), has_county_government=r["has_county_government"],
                        ours_corrections=round(ours_c), fisc_corrections=round(f["corr"]) if f["corr"] is not None else "",
                        ratio_corrections=round(ours_c / f["corr"], 3) if f["corr"] else "",
                        ours_judicial=round(ours_j), fisc_judicial=round(f["jud"]) if f["jud"] is not None else "",
                        ratio_judicial=round(ours_j / f["jud"], 3) if f["jud"] else "",
                        fisc_county_police=round(f["pol"]) if f["pol"] is not None else ""))
    with open(os.path.join(build.ROOT, "validation", "county_alloc_vs_fisc.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    for y in (2012, 2017, 2022):
        yr = [r for r in out if r["year"] == y]
        both_zero = sum(1 for r in yr if not r["ours_corrections"] and not r["fisc_corrections"] and not r["ours_judicial"] and not r["fisc_judicial"])
        for k in ("corrections", "judicial"):
            xs = sorted(r[f"ratio_{k}"] for r in yr if r[f"ratio_{k}"] != "")
            if not xs:
                continue
            q = statistics.quantiles(xs, n=4)
            one_sided = sum(1 for r in yr if (r[f"ours_{k}"] == 0) != (not r[f"fisc_{k}"]))
            print(f"{y} {k:<12} n={len(xs):3d} median {statistics.median(xs):.3f} IQR {q[0]:.3f}-{q[2]:.3f} within 5% {sum(1 for x in xs if abs(x-1)<=.05)} within 25% {sum(1 for x in xs if abs(x-1)<=.25)}  zero on one side only: {one_sided}", file=sys.stderr)
        print(f"{y} cities with no county corrections or courts on either side: {both_zero}", file=sys.stderr)
    worst = sorted((r for r in out if r["year"] == 2022 and r["ratio_corrections"] != ""), key=lambda r: -abs(r["ratio_corrections"] - 1))[:8]
    print("largest 2022 corrections gaps: " + "; ".join(f"{r['city']} {r['state']} {r['ratio_corrections']}" for r in worst), file=sys.stderr)


if __name__ == "__main__":
    main()
