"""Fetch 1950-1980 county sex-by-age counts from NHGIS (IPUMS).

Pre-1990 decennial data isn't on either api.census.gov or the CD-ROM
archives, so it comes from NHGIS via the IPUMS extract API: we request the
county sex-by-age table for each census, their servers build the extract,
we poll until it's ready and download one zip of CSVs.

Tables (chosen from the metadata API for bin quality at county level):
  1950_cAge  NT8    Sex by Age, 5-year bins, 75-84 merged, 85+
  1960_cAge1 NT5    Sex by Age, full standard 5-year bins to 85+
  1970_Cnt2  NT2A   Sex by Age, single years 0..100+ (-> full bins)
  1980_cASRS NT004  Sex by Age, single years 0..74 + 75+
  1980_STF1  NT10B  Sex by Age, coarse -- used only for its 75-84 / 85+
  1980_gqASRS NT004 GQ Sex by Age (cached for a possible future household
                    basis; not parsed yet)

Requires an IPUMS API key: env IPUMS_API_KEY, or a file named by
IPUMS_API_KEY_FILE, or ~/.ipums_api_key. Free signup at
https://account.ipums.org (include NHGIS), key at
https://account.ipums.org/api_keys.

Each year is cached as data/raw/p12_county_<year>.json in the same
[header, *rows] shape as the other fetchers, with synthetic variable names
M01../F01.. over bins.NHGIS_YEAR_BINS[year] (already standard bins, so
normalize needs no new mappings).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import requests

from .bins import NHGIS_YEAR_BINS

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
NHGIS_DIR = RAW_DIR / "nhgis"

API = "https://api.ipums.org"
V = "version=2"

# dataset -> (tables, geog levels). DC is absent from the 1950 and 1970
# county-level files (it's published at state level there), so those two
# datasets also request state rows and DC is injected from them.
EXTRACT_SPEC = {
    "1950_cAge":   (["NT8"],   ["county", "state"]),
    "1960_cAge1":  (["NT5"],   ["county"]),
    "1970_Cnt2":   (["NT2A"],  ["county", "state"]),
    "1980_cASRS":  (["NT004"], ["county"]),
    "1980_STF1":   (["NT10B"], ["county"]),
    "1980_gqASRS": (["NT004"], ["county"]),
}

# Published resident-population anchors (US totals as tabulated), and
# Alaska's published counts for the years it is excluded (pre-borough
# geography) so the check can still demand exactness.
ANCHORS = {1950: 150_697_361, 1960: 179_323_175,
           1970: 203_211_926, 1980: 226_545_805}
AK_PUBLISHED = {1960: 226_167, 1970: 300_382}

NHGIS_YEARS = (1950, 1960, 1970, 1980)

# Raw NHGIS (state, county) codes needing special handling before the
# suffix strip: South Norfolk city is 7805 (stripping would collide with
# South Boston's 7800), and the Idaho sliver of Yellowstone National Park
# (pop ~30) has no successor unit worth tracing.
GEO_OVERRIDES: dict[tuple[str, str], tuple[str, str] | None] = {
    ("51", "7805"): ("51", "785"),  # South Norfolk city, VA (historic FIPS)
    ("16", "0875"): None,           # Yellowstone NP (Idaho part): drop
}


def _key() -> str:
    key = os.environ.get("IPUMS_API_KEY", "").strip()
    if key:
        return key
    for cand in (os.environ.get("IPUMS_API_KEY_FILE"),
                 Path.home() / ".ipums_api_key"):
        if cand and Path(cand).exists():
            key = Path(cand).read_text().strip()
            if key:
                return key
    raise RuntimeError(
        "No IPUMS API key. Set IPUMS_API_KEY (or IPUMS_API_KEY_FILE, or "
        "~/.ipums_api_key). Free signup: https://account.ipums.org "
        "(include NHGIS); key: https://account.ipums.org/api_keys")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = _key()
    return s


# --- extract lifecycle ------------------------------------------------------

def _submit(session: requests.Session) -> int:
    body = {
        "datasets": {ds: {"dataTables": tbls, "geogLevels": geogs}
                     for ds, (tbls, geogs) in EXTRACT_SPEC.items()},
        "dataFormat": "csv_header",
        "description": "cohort tracing: county sex by age, 1950-1980",
    }
    r = session.post(f"{API}/extracts?collection=nhgis&{V}", json=body,
                     timeout=120)
    r.raise_for_status()
    n = r.json()["number"]
    print(f"  NHGIS: submitted extract #{n}")
    return n


def _wait(session: requests.Session, number: int) -> dict:
    for i in range(240):  # up to ~60 min
        r = session.get(f"{API}/extracts/{number}?collection=nhgis&{V}",
                        timeout=120)
        r.raise_for_status()
        j = r.json()
        status = j.get("status")
        if status == "completed":
            return j
        if status in ("failed", "canceled"):
            raise RuntimeError(f"NHGIS extract #{number} {status}")
        if i % 8 == 0:
            print(f"  NHGIS: extract #{number} is {status}...", flush=True)
        time.sleep(15)
    raise RuntimeError(f"NHGIS extract #{number} not ready after 60 min")


def _download(session: requests.Session, extract: dict) -> None:
    url = extract["downloadLinks"]["tableData"]["url"]
    print(f"  NHGIS: downloading table data...")
    r = session.get(url, timeout=600)
    r.raise_for_status()
    NHGIS_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for name in z.namelist():
            if name.endswith((".csv", ".txt")):
                (NHGIS_DIR / Path(name).name).write_bytes(z.read(name))
    print(f"  NHGIS: cached {len(list(NHGIS_DIR.glob('*.csv')))} CSVs + "
          f"codebooks in {NHGIS_DIR}")


def _cache_table_meta(session: requests.Session) -> None:
    for ds, (tbls, _geogs) in EXTRACT_SPEC.items():
        for tbl in tbls:
            path = NHGIS_DIR / f"meta_{ds}_{tbl}.json"
            if path.exists():
                continue
            r = session.get(
                f"{API}/metadata/nhgis/datasets/{ds}/data_tables/{tbl}?{V}",
                timeout=120)
            r.raise_for_status()
            path.write_text(json.dumps(r.json()))


def ensure_extract(force: bool = False) -> None:
    """Make sure the NHGIS CSVs and table metadata are cached locally.

    A manifest records the spec the cache was built from; a changed spec
    triggers a fresh extract.
    """
    manifest = NHGIS_DIR / "manifest.json"
    spec = json.dumps(EXTRACT_SPEC, sort_keys=True)
    if (not force and manifest.exists()
            and manifest.read_text() == spec):
        return
    session = _session()
    number = _submit(session)
    extract = _wait(session, number)
    _download(session, extract)
    _cache_table_meta(session)
    manifest.write_text(spec)


# --- parsing ----------------------------------------------------------------

def _table_columns(ds: str, tbl: str) -> list[tuple[str, str, str]]:
    """[(csv_column, sex, age_text)] for a table, from cached metadata."""
    meta = json.loads((NHGIS_DIR / f"meta_{ds}_{tbl}.json").read_text())
    out = []
    for v in meta["variables"]:
        m = re.match(r"(Male|Female) >> (.+)$", v["description"])
        if not m:
            raise RuntimeError(f"{ds}/{tbl}: unexpected variable "
                               f"description {v['description']!r}")
        out.append((v["nhgisCode"], "M" if m.group(1) == "Male" else "F",
                    m.group(2)))
    return out


def _find_csv(columns: list[str], level: str = "county") -> Path:
    """Locate the cached CSV at this geog level carrying these columns."""
    for p in sorted(NHGIS_DIR.glob(f"*_{level}.csv")):
        with p.open(encoding="latin-1") as f:
            header = f.readline().strip().split(",")
        if set(columns) <= {c.strip('"') for c in header}:
            return p
    raise RuntimeError(f"no cached NHGIS {level} CSV contains columns "
                       f"{columns[:3]}...; run the fetch first")


def _age_to_bin(age_text: str, year: int) -> str | None:
    """Map a label's age text onto this year's bin, None to drop."""
    t = age_text.lower().replace(" of age", "").replace(" years", "") \
        .replace(" year", "").strip()
    if m := re.match(r"under 1$|under 1\b", t):
        lo = 0
    elif m := re.match(r"^(\d+)\s*(?:and over|\+|to|-|$)", t):
        lo = int(m.group(1))
    else:
        raise RuntimeError(f"unparseable age text: {age_text!r}")
    bins = NHGIS_YEAR_BINS[year]
    for b in bins:
        if b.endswith("+"):
            if lo >= int(b[:-1]):
                return b
        else:
            blo, bhi = map(int, b.split("-"))
            if blo <= lo <= bhi:
                return b
    return None


def _read_table(ds: str, tbl: str, year: int) -> dict:
    """Sum a table's CSV into per-county bin counts.

    Returns {(state_fips, county3): {"name": str, "M": {bin: n}, "F": ...}}.
    """
    cols = _table_columns(ds, tbl)
    path = _find_csv([c for c, _, _ in cols])
    out: dict = {}
    raw_codes: dict = {}
    with path.open(encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f):
            statea, countya = row["STATEA"], row["COUNTYA"]
            if not statea.isdigit():
                continue  # second header row carries the human labels
            # 1950/1960 use NHGIS codes (FIPS*10 + suffix; non-zero suffixes
            # mark territory-era entities); 1970/1980 use plain FIPS. The
            # suffix is dropped — the FIPS prefix identifies the county —
            # and a collision guard below catches any true conflict.
            st = statea[:2] if len(statea) == 3 else statea
            if (st, countya) in GEO_OVERRIDES:
                geo = GEO_OVERRIDES[(st, countya)]
                if geo is None:
                    continue
            else:
                county3 = countya[:3] if len(countya) == 4 else countya
                geo = (st, county3)
            prev = raw_codes.setdefault(geo, countya)
            if prev != countya:
                raise RuntimeError(
                    f"county code collision at {geo}: NHGIS codes "
                    f"{prev!r} and {countya!r} both map there")
            slot = out.setdefault(geo, {
                "name": f"{row.get('COUNTY', '?')}, {row.get('STATE', '?')}",
                "M": defaultdict(int), "F": defaultdict(int),
            })
            for col, sex, age_text in cols:
                b = _age_to_bin(age_text, year)
                if b is not None:
                    slot[sex][b] += int(row[col] or 0)
    return out


def _dc_from_state(ds: str, tbl: str, year: int) -> dict:
    """DC's row from the state-level file (absent from 1950/1970 county
    files; the District is its own county equivalent)."""
    cols = _table_columns(ds, tbl)
    path = _find_csv([c for c, _, _ in cols], level="state")
    with path.open(encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f):
            statea = row["STATEA"]
            if not statea.isdigit():
                continue
            st = statea[:2] if len(statea) == 3 else statea
            if st != "11":
                continue
            slot = {"name": "District of Columbia, District of Columbia",
                    "M": defaultdict(int), "F": defaultdict(int)}
            for col, sex, age_text in cols:
                b = _age_to_bin(age_text, year)
                if b is not None:
                    slot[sex][b] += int(row[col] or 0)
            return slot
    raise RuntimeError(f"{year}: DC not found at state level either")


def fetch_year_nhgis(year: int, force: bool = False) -> Path:
    path = RAW_DIR / f"p12_county_{year}.json"
    if path.exists() and not force:
        print(f"  {year}: cached at {path}")
        return path

    ensure_extract(force=False)
    bins = NHGIS_YEAR_BINS[year]

    if year == 1980:
        # Single years to 74 from cASRS; 75-84 and 85+ from STF1 NT10B.
        base = _read_table("1980_cASRS", "NT004", 1980)
        top = _read_table("1980_STF1", "NT10B", 1980)
        mismatch = 0
        for geo, slot in base.items():
            t = top.get(geo)
            if t is None:
                raise RuntimeError(f"1980: {geo} in cASRS but not STF1")
            for sex in ("M", "F"):
                casrs_75p = slot[sex].pop("75-84", 0) + slot[sex].pop("85+", 0)
                s7584, s85 = t[sex].get("75-84", 0), t[sex].get("85+", 0)
                if casrs_75p != s7584 + s85:
                    mismatch += 1
                slot[sex]["75-84"] = s7584
                slot[sex]["85+"] = s85
        if mismatch:
            print(f"  1980: note - cASRS 75+ != STF1 75-84+85+ in "
                  f"{mismatch} sex-county cells (using STF1 split)")
        counties = base
    else:
        ds, tbl = {1950: ("1950_cAge", "NT8"),
                   1960: ("1960_cAge1", "NT5"),
                   1970: ("1970_Cnt2", "NT2A")}[year]
        counties = _read_table(ds, tbl, year)
        if ("11", "001") not in counties:
            counties[("11", "001")] = _dc_from_state(ds, tbl, year)

    if year <= 1970:
        # Alaska used judicial divisions (1950) and election districts
        # (1960/70) — not comparable to boroughs; excluded before 1980.
        ak = [g for g in counties if g[0] == "02"]
        for g in ak:
            counties.pop(g)
        if ak:
            print(f"  {year}: excluded {len(ak)} Alaska units "
                  f"(pre-borough geography)")

    total = sum(sum(slot[s].values()) for slot in counties.values()
                for s in ("M", "F"))
    if year == 1950:
        # Continental US must be exact; Hawaii Territory's age table
        # tabulates ~1% fewer than the published 499,794 (age-not-reported
        # excluded; Kalawao absent) — allowed within 2%.
        hi = sum(sum(slot[s].values()) for geo, slot in counties.items()
                 if geo[0] == "15" for s in ("M", "F"))
        cont = total - hi
        gap = ANCHORS[1950] - cont  # the dropped Idaho YNP sliver
        if not 0 <= gap <= 100:
            raise RuntimeError(f"1950: continental total {cont:,} vs "
                               f"published {ANCHORS[1950]:,} (gap {gap:,}; "
                               f"only the ~30-person Idaho YNP drop is "
                               f"expected)")
        if abs(hi - 499_794) / 499_794 > 0.02:
            raise RuntimeError(f"1950: Hawaii total {hi:,} too far from "
                               f"published 499,794")
        note = (f"continental exact minus {gap}-person Idaho YNP sliver; "
                f"HI {hi:,} vs published 499,794 (age-not-reported gap)")
    else:
        anchor = ANCHORS[year] - AK_PUBLISHED.get(year, 0)
        if total != anchor:
            raise RuntimeError(
                f"{year}: parsed total {total:,} != expected {anchor:,} "
                f"(published minus excluded Alaska); refusing to cache")
        note = ("matches published exactly" if year not in AK_PUBLISHED
                else "matches published minus excluded Alaska exactly")

    header = (["NAME"]
              + [f"M{i+1:02d}" for i in range(len(bins))]
              + [f"F{i+1:02d}" for i in range(len(bins))]
              + ["state", "county"])
    rows = []
    for (st, cnty), slot in sorted(counties.items()):
        rows.append([slot["name"]]
                    + [str(slot["M"].get(b, 0)) for b in bins]
                    + [str(slot["F"].get(b, 0)) for b in bins]
                    + [st, cnty])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([header] + rows))
    print(f"  {year}: {len(rows)} counties, {total:,} persons "
          f"({note}) -> {path}")
    return path
