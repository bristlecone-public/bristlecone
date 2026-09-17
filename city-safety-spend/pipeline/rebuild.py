"""Re-run the whole pipeline and report what changed. Mechanical only: it never decides whether a
change is acceptable, it measures and writes the evidence down for a person to read.

    python pipeline/rebuild.py                 # rebuild from the raw files already on disk
    python pipeline/rebuild.py --refresh-cpi    # also re-fetch CPI-U from BLS first
    python pipeline/rebuild.py --only build,export_site

Writes validation/REFRESH_REPORT.md and exits:
    0   everything ran and nothing looks wrong
    2   a step failed
    3   steps ran but something needs a human: history moved, or a validation headline got worse

"History moved" is the check that matters. Re-running with a new year of data should add rows and
leave past years alone. Census does revise, so a handful of small moves are normal and the report
lists them; a wave of them means a parser or classification change, not a revision.

Downloading new raw files is deliberately NOT automated: a new Census year has, twice in this
project's history, arrived with a changed file name or record layout, and that needs eyes.
docs/METHODOLOGY.md section 1 holds the URLs.
"""
import argparse, csv, io, os, subprocess, sys, datetime, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
OUT = os.path.join(ROOT, "data", "census_out")
REPORT = os.path.join(ROOT, "validation", "REFRESH_REPORT.md")

STEPS = [
    ("build", "pipeline/build.py"),
    ("rpp", "pipeline/rpp.py"),
    ("long_series", "pipeline/compare_willamette.py"),
    ("peers", "pipeline/peers.py"),
    ("employment", "pipeline/employment.py"),
    ("employment_checks", "pipeline/employment_checks.py"),
    ("crime", "pipeline/crime.py"),
    ("county_alloc", "pipeline/county_alloc.py"),
    ("checks", "pipeline/checks.py"),
    ("compare_fisc", "pipeline/compare_fisc.py"),
    ("compare_vera", "pipeline/compare_vera.py"),
    ("compare_spotcheck", "pipeline/compare_spotcheck.py"),
    ("compare_bjs", "pipeline/compare_bjs.py"),
    ("compare_fbi", "pipeline/compare_fbi.py"),
    ("compare_county_alloc", "pipeline/compare_county_alloc.py"),
    ("factsheets", "pipeline/factsheets.py"),
    ("export_site", "pipeline/export_site.py"),
    ("findings", "pipeline/findings.py"),
    ("findings_page", "pipeline/findings_page.py"),
]

# headline numbers re-derived after the run and compared with the committed baseline
def headline_stats(read):
    s = {}
    rows = read("validation/aggregate_check_all_codes.csv")
    if rows:
        for r in rows:
            s[f"census {r['year']} item codes matching published totals"] = float(r["pct_exact"])
    rows = read("validation/fbi_vs_census.csv")
    if rows:
        xs = [float(r["ratio_sworn"]) for r in rows if r["ratio_sworn"] and r["contracted_or_joint"] != "True"
              and r["census_flag_class"] == "reported"]
        if xs:
            s["FBI sworn counts within 10% (reported years)"] = round(100 * sum(1 for x in xs if abs(x - 1) <= .1) / len(xs), 1)
    rows = read("validation/county_alloc_vs_fisc.csv")
    if rows:
        xs = [float(r["ratio_corrections"]) for r in rows if r["ratio_corrections"] and r["year"] == "2022"]
        if xs:
            s["county jail allocation vs FiSC, median ratio"] = round(statistics.median(xs), 3)
    rows = read("data/census_out/city_police_fire_2022.csv")
    if rows:
        xs = [float(r["police_fire_pct_general"]) for r in rows if r["police_fire_pct_general"]]
        s["2022 median police+fire share of general expenditure"] = round(statistics.median(xs), 2)
        s["2022 cities with a complete record"] = sum(1 for r in rows if r["record_complete"] == "True")
    return s


def git_read(path):
    """The committed version of a CSV, as a list of dicts; None if there is no baseline."""
    try:
        blob = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return list(csv.DictReader(io.StringIO(blob.decode("utf-8-sig", "replace"))))


def disk_read(path):
    p = os.path.join(ROOT, path)
    return list(csv.DictReader(open(p, encoding="utf-8-sig"))) if os.path.exists(p) else None


def drift(before, after, key, value, label):
    """Rows present both before and after whose value moved. Returns (n_compared, [(key, old, new, delta)])."""
    if not before or not after:
        return 0, []
    b = {tuple(r[k] for k in key): r for r in before}
    moved = []
    for r in after:
        k = tuple(r[x] for x in key)
        if k in b and b[k][value] and r[value]:
            o, n = float(b[k][value]), float(r[value])
            if abs(n - o) > 0.5:
                moved.append((" ".join(k), o, n, n - o))
    moved.sort(key=lambda x: -abs(x[3]))
    return len(b), moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-cpi", action="store_true")
    ap.add_argument("--only", help="comma-separated step names")
    args = ap.parse_args()

    baseline_stats = headline_stats(git_read)
    before_long = git_read("data/census_out/city_police_fire_all_years.csv")
    before_emp = git_read("data/census_out/city_employment_all_years.csv")

    steps = list(STEPS)
    if args.refresh_cpi:
        steps.insert(0, ("cpi", "pipeline/cpi.py"))
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        steps = [s for s in steps if s[0] in want]

    started = datetime.datetime.now()
    log, failed = [], None
    for name, script in steps:
        t0 = datetime.datetime.now()
        p = subprocess.run([PY, script], cwd=ROOT, capture_output=True, text=True)
        secs = (datetime.datetime.now() - t0).total_seconds()
        tail = (p.stderr or p.stdout or "").strip().splitlines()
        log.append(dict(step=name, ok=p.returncode == 0, seconds=round(secs, 1),
                        tail=tail[-6:], error=(p.stderr or "").strip()[-1500:] if p.returncode else ""))
        print(f"{'ok ' if p.returncode == 0 else 'FAIL'} {name:<22}{secs:6.1f}s", file=sys.stderr)
        if p.returncode:
            failed = name
            break

    after_stats = headline_stats(disk_read)
    n_long, long_moved = drift(before_long, disk_read("data/census_out/city_police_fire_all_years.csv"),
                               ("pid", "fiscal_year"), "police_fire_pct_general", "share")
    n_emp, emp_moved = drift(before_emp, disk_read("data/census_out/city_employment_all_years.csv"),
                             ("pid", "year"), "sworn_per_1k", "officers per 1,000")
    now = disk_read("data/census_out/city_police_fire_all_years.csv") or []
    new_years = sorted({r["fiscal_year"] for r in now} - {r["fiscal_year"] for r in (before_long or [])})

    worse = []
    for k, v in after_stats.items():
        if k in baseline_stats and isinstance(v, (int, float)):
            if v < baseline_stats[k] - (0.5 if "within" in k or "matching" in k else 0):
                worse.append((k, baseline_stats[k], v))

    lines = [f"# Refresh report {started:%Y-%m-%d %H:%M}", ""]
    if failed:
        lines += [f"**Step `{failed}` failed - the rebuild stopped there. Nothing below is complete.**", "",
                  "```", next(x["error"] for x in log if x["step"] == failed), "```", ""]
    lines += ["## Steps", "", "| step | ok | seconds | last line |", "|---|---|---|---|"]
    for x in log:
        last = (x["tail"][-1][:110].replace("|", "\\|") if x["tail"] else "")
        lines.append(f"| {x['step']} | {'yes' if x['ok'] else 'NO'} | {x['seconds']} | {last} |")

    lines += ["", "## New data", ""]
    lines.append(f"- Fiscal years added to the long series: {', '.join(new_years) if new_years else 'none'}")
    lines.append(f"- City-years now / before: {len(now)} / {len(before_long) if before_long is not None else 'no baseline'}")

    lines += ["", "## Did history move?", "",
              f"Comparing every city-year present both before and after ({n_long} compared), "
              f"**{len(long_moved)}** moved by more than half a point of the general-expenditure share; "
              f"staffing: **{len(emp_moved)}** of {n_emp} moved by more than 0.5 officers per 1,000.", ""]
    if long_moved:
        lines += ["| city-year | was | now | change |", "|---|---|---|---|"]
        lines += [f"| {k} | {o:.2f} | {n:.2f} | {d:+.2f} |" for k, o, n, d in long_moved[:15]]
        if len(long_moved) > 15:
            lines.append(f"| ... {len(long_moved)-15} more | | | |")
        lines += ["", "A handful is normal (Census revises). A wave is not: check whether a file layout or an "
                  "item-code list changed before accepting the rebuild.", ""]

    lines += ["## Validation headlines", "", "| measure | before | after |", "|---|---|---|"]
    for k in sorted(set(baseline_stats) | set(after_stats)):
        lines.append(f"| {k} | {baseline_stats.get(k, '-')} | {after_stats.get(k, '-')} |")
    if worse:
        lines += ["", "**Worse than the committed baseline:**", ""] + [f"- {k}: {b} -> {a}" for k, b, a in worse]

    lines += ["", "## Then what", "",
              "1. Read the moves above. If they are explained (a Census revision, a city reorganised), note them in "
              "`data/known_issues.csv` or `validation/REPORT.md`.",
              "2. If a new year arrived, check the new year's flags: imputed cities, incomplete records, and any city "
              "whose share moved more than a couple of points.",
              "3. Commit the rebuilt outputs, run `python pipeline/factsheets.py` if it was skipped, deploy with "
              "`scripts/deploy_site.ps1`, and republish the dashboard artifact.", ""]
    open(REPORT, "w", encoding="utf-8").write("\n".join(lines))
    print(f"\nwrote {os.path.relpath(REPORT, ROOT)}", file=sys.stderr)

    if failed:
        sys.exit(2)
    if worse or len(long_moved) > 25:
        sys.exit(3)
    sys.exit(0)


if __name__ == "__main__":
    main()
