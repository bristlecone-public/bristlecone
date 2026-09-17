"""Check whether any upstream source has published something new. No model, no judgement: it records
what each source looks like today, compares with last time, and says what changed.

    python pipeline/poll_sources.py            # report, update state
    python pipeline/poll_sources.py --dry-run  # report only

Exit codes so cron can branch on them:
    0   nothing changed
    10  something changed (a rebuild is warranted)
    1   a source could not be checked (network, layout change) - look at the report

State lives in data/source_state.json and is committed, so the first run after a clone is quiet
rather than reporting everything as new.

The five sources refresh on different cadences: Census finance and employment around mid-year, FBI in
the autumn, BEA regional prices in winter, CPI each January. Poll monthly; only the Census finance file
forces a full rebuild.
"""
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The committed copy is the baseline. A deployed checkout must point this somewhere outside the
# working tree (SOURCE_STATE=/srv/...), or every run dirties the repo and the next pull fails.
STATE = os.environ.get("SOURCE_STATE") or os.path.join(ROOT, "data", "source_state.json")
UA = {"User-Agent": "city-safety-spend source poller (research; contact via repo)"}
TIMEOUT = 45


def head(url, method="HEAD"):
    req = urllib.request.Request(url, headers=UA, method=method)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return dict(status=r.status, size=r.headers.get("Content-Length"), modified=r.headers.get("Last-Modified"))


def census_years(kind):
    """First year whose individual unit file is published, looking ahead from what we already parsed.
    finance:    .../gov-finances/tables/<y>/<y>_Individual_Unit_File(s).zip
    employment: .../apes/datasets/<y>/<y>_individual_unit_files.zip
    """
    raw = os.path.join(build.RAW_ROOT, "census_raw", "apes" if kind == "employment" else "")
    have = sorted(int(d) for d in os.listdir(raw) if d.isdigit()) if os.path.isdir(raw) else []
    if not have:
        # A deployed checkout has no raw files (gitignored, ~2.8 GB), so fall back to what the
        # committed outputs actually contain. Falling back to the calendar instead would slide
        # the probe window forward every year and step over the file we are waiting for.
        v = build.data_vintage().get("employment" if kind == "employment" else "finance")
        have = [int(v)] if v else []
    start = (max(have) if have else datetime.date.today().year - 2) + 1
    found = {}
    for y in range(start, datetime.date.today().year + 1):
        if kind == "finance":
            cands = [f"https://www2.census.gov/programs-surveys/gov-finances/tables/{y}/{y}_Individual_Unit_Files.zip",
                     f"https://www2.census.gov/programs-surveys/gov-finances/tables/{y}/{y}_Individual_Unit_File.zip"]
        else:
            cands = [f"https://www2.census.gov/programs-surveys/apes/datasets/{y}/{y}_individual_unit_files.zip",
                     f"https://www2.census.gov/programs-surveys/apes/datasets/{y}/{y}%20COG-E%20Individual%20Unit%20Files.zip"]
        for u in cands:
            try:
                h = head(u)
            except urllib.error.HTTPError:
                continue
            if h["status"] == 200:
                found[str(y)] = dict(url=u, size=h["size"], modified=h["modified"])
                break
    return dict(latest_published=max(found) if found else None, files=found, already_parsed=str(max(have)) if have else None)


def bea_rpp():
    h = head("https://apps.bea.gov/regional/zip/MARPP.zip")
    return dict(size=h["size"], modified=h["modified"])


def bls_cpi():
    """Latest calendar year with a published annual average (period M13)."""
    body = json.dumps({"seriesid": ["CUUR0000SA0"], "startyear": str(datetime.date.today().year - 2),
                       "endyear": str(datetime.date.today().year), "annualaverage": True}).encode()
    req = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/", data=body,
                                 headers={**UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        res = json.load(r)
    if res.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API said {res.get('status')}: {res.get('message')}")
    years = [int(d["year"]) for d in res["Results"]["series"][0]["data"]
             if d["period"] == "M13" and d["value"].strip() not in ("", "-")]
    return dict(latest_annual_average=str(max(years)) if years else None)


def fbi(key):
    """The Crime Data Explorer hands out a short-lived signed S3 link; the link itself changes every
    call, so compare the object's size and timestamp, not the URL."""
    req = urllib.request.Request(f"https://cde.ucr.cjis.gov/LATEST/s3/signedurl?key={key}", headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        payload = json.loads(r.read().decode())
    signed = payload[key] if key in payload else next(iter(payload.values()))
    # Where that link points is decided by the remote API, and this runs on a container with LAN
    # access. Without a check, an upstream returning an internal address makes this a blind
    # internal probe. The real links are https on S3; anything else is not something to fetch.
    u = urllib.parse.urlparse(signed)
    if u.scheme != "https" or not (u.hostname or "").endswith(".amazonaws.com"):
        raise ValueError(f"CDE signed link points somewhere unexpected: "
                         f"{u.scheme}://{u.hostname} - refusing to fetch it")
    # the signature covers GET, so ask for a single byte and read the total size out of Content-Range
    rng = urllib.request.Request(signed, headers={**UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(rng, timeout=TIMEOUT) as r:
        cr = r.headers.get("Content-Range", "")
        return dict(size=cr.split("/")[-1] if "/" in cr else r.headers.get("Content-Length"),
                    modified=r.headers.get("Last-Modified"))


SOURCES = {
    "census_finance": (lambda: census_years("finance"), "Census finance unit files - a new year here forces a full rebuild"),
    "census_employment": (lambda: census_years("employment"), "Census employment unit files"),
    "fbi_offenses": (lambda: fbi("master_files/reta/reta-2024.zip"), "FBI Return A master file (latest year we parse)"),
    "fbi_employees": (lambda: fbi("additional-datasets/law-enforcement/lee_1960_2025.csv"), "FBI police employee counts"),
    "bea_rpp": (bea_rpp, "BEA regional price parities"),
    "bls_cpi": (bls_cpi, "CPI-U annual averages"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    old = json.load(open(STATE)) if os.path.exists(STATE) else {}
    new, changed, failed = {}, [], []
    for name, (fn, label) in SOURCES.items():
        try:
            cur = fn()
        except Exception as e:                      # network, layout change, anything
            failed.append((name, f"{type(e).__name__}: {e}"))
            new[name] = old.get(name, {})
            continue
        prev = old.get(name, {}).get("value")
        new[name] = dict(value=cur, checked=datetime.date.today().isoformat(),
                         changed=(old.get(name, {}).get("changed") if prev == cur else datetime.date.today().isoformat()))
        if prev is not None and prev != cur:
            changed.append((name, label, prev, cur))
        time.sleep(1)

    width = max(len(k) for k in SOURCES)
    print(f"source poll {datetime.date.today().isoformat()}")
    for name, (_, label) in SOURCES.items():
        v = new.get(name, {}).get("value")
        mark = "CHANGED" if any(c[0] == name for c in changed) else ("FAILED" if any(f[0] == name for f in failed) else "same")
        print(f"  {name:<{width}}  {mark:<8} {json.dumps(v, default=str)[:150]}")
    for name, label, prev, cur in changed:
        print(f"\n{name} changed - {label}\n  was: {json.dumps(prev, default=str)[:400]}\n  now: {json.dumps(cur, default=str)[:400]}")
    for name, err in failed:
        print(f"\n{name} could not be checked: {err}", file=sys.stderr)

    fin = new.get("census_finance", {}).get("value") or {}
    if fin.get("latest_published") and fin.get("already_parsed") and fin["latest_published"] > fin["already_parsed"]:
        print(f"\nAction: Census finance year {fin['latest_published']} is published and we have parsed through "
              f"{fin['already_parsed']} - run pipeline/rebuild.py")
    if not args.dry_run:
        json.dump(new, open(STATE, "w"), indent=1, sort_keys=True, default=str)
    if failed:
        sys.exit(1)
    sys.exit(10 if changed else 0)


if __name__ == "__main__":
    main()
