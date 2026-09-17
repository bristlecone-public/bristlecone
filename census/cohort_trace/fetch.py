"""Download county-level sex-by-age (P12) tables from the Census API.

Requires network access to api.census.gov (run this from the LXC, not a
sandboxed environment) and a free API key in CENSUS_API_KEY — since 2025
the API answers keyless data queries with a "Missing Key" HTML page.

Each census year is fetched in a single request (46 variables, all counties)
and cached as raw JSON under data/raw/.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests

from .bins import API_BINS, BINS_1990, NHGIS_YEAR_BINS

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

DATASETS = {
    2000: "https://api.census.gov/data/2000/dec/sf1",
    2010: "https://api.census.gov/data/2010/dec/sf1",
    2020: "https://api.census.gov/data/2020/dec/dhc",
}

KEY_SIGNUP = "https://api.census.gov/data/key_signup.html"

# Census Bureau 2000-2010 intercensal county age/sex file. Its 4/1/2000
# estimates base is reconstructed on 2010 boundaries, so it carries Broomfield
# County (08014) -- which did not exist in 2000 -- with its parents already
# reduced. Used only to reconstruct Broomfield's 2000 baseline (see broomfield.py).
INTERCENSAL_AGESEX_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/"
    "2000-2010/intercensal/county/co-est00int-agesex-5yr.csv"
)


def _get_json(session: requests.Session, url: str, params: dict | None = None,
              timeout: int = 300):
    """GET a Census API endpoint and decode JSON, translating the API's
    HTML error pages (served with status 200) into actionable errors.

    Since 2025 api.census.gov requires an API key for data queries and
    answers keyless ones with a 200 'Missing Key' HTML page.
    """
    resp = session.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError:
        snippet = resp.text[:200].strip().replace("\n", " ")
        head = resp.text[:2000].lower()
        if "missing key" in head:
            raise RuntimeError(
                "api.census.gov rejected the query: an API key is required. "
                f"Get a free key at {KEY_SIGNUP} and set CENSUS_API_KEY."
            ) from None
        if "invalid key" in head:
            raise RuntimeError(
                "api.census.gov rejected CENSUS_API_KEY as invalid. Usual "
                "causes: the key isn't activated yet (click the activation "
                "link in the signup email, then wait a few minutes), or the "
                "env var picked up stray whitespace/quotes."
            ) from None
        raise RuntimeError(
            f"api.census.gov returned non-JSON for {url}: {snippet!r}"
        ) from None


def _p12_vars(year: int) -> list[str]:
    """P12 variable names in published order: 23 male bins then 23 female.

    2000/2010 SF1: P012003..P012025 (male), P012027..P012049 (female).
    2020 DHC:      P12_003N..P12_025N,      P12_027N..P12_049N.
    """
    male = list(range(3, 26))
    female = list(range(27, 50))
    if year in (2000, 2010):
        return [f"P012{n:03d}" for n in male + female]
    if year == 2020:
        return [f"P12_{n:03d}N" for n in male + female]
    raise ValueError(f"unsupported census year: {year}")


def var_map(year: int) -> dict[str, tuple[str, str]]:
    """Map each variable name in a raw file to (sex, published age bin)."""
    if year == 1990:
        # Synthetic names emitted by fetch1990 (race already summed out).
        out = {}
        for i, cat in enumerate(BINS_1990):
            out[f"M{i+1:02d}"] = ("M", cat)
            out[f"F{i+1:02d}"] = ("F", cat)
        return out
    if year in NHGIS_YEAR_BINS:
        # Synthetic names emitted by fetchnhgis (bins already standard).
        out = {}
        for i, cat in enumerate(NHGIS_YEAR_BINS[year]):
            out[f"M{i+1:02d}"] = ("M", cat)
            out[f"F{i+1:02d}"] = ("F", cat)
        return out
    names = _p12_vars(year)
    out = {}
    for i, name in enumerate(names):
        sex = "M" if i < len(API_BINS) else "F"
        out[name] = (sex, API_BINS[i % len(API_BINS)])
    return out


def raw_path(year: int) -> Path:
    return RAW_DIR / f"p12_county_{year}.json"


def validate_variables(year: int, session: requests.Session) -> None:
    """Cross-check our hardcoded variable IDs against the API's own metadata.

    Fails loudly with the missing names so a table-layout surprise surfaces
    immediately instead of producing silently wrong bins.
    """
    url = f"{DATASETS[year]}/variables.json"
    published = _get_json(session, url, timeout=120)["variables"]
    missing = [v for v in _p12_vars(year) if v not in published]
    if missing:
        raise RuntimeError(
            f"{year}: {len(missing)} expected P12 variables not in "
            f"{url}: {missing[:5]}... Check the table layout for this year."
        )
    first = _p12_vars(year)[0]
    print(f"  {year}: all 46 P12 variables present "
          f"(e.g. {first} = {published[first].get('label', '?')!r})")


def fetch_year(year: int, force: bool = False) -> Path:
    """Fetch one census year's county-level P12 table, with on-disk caching."""
    if year == 1990:
        from .fetch1990 import fetch_1990
        return fetch_1990(force=force)
    if year in NHGIS_YEAR_BINS:
        from .fetchnhgis import fetch_year_nhgis
        return fetch_year_nhgis(year, force=force)

    path = raw_path(year)
    if path.exists() and not force:
        print(f"  {year}: cached at {path}")
        return path

    session = requests.Session()
    validate_variables(year, session)

    params = {"get": "NAME," + ",".join(_p12_vars(year)), "for": "county:*"}
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        params["key"] = key

    data = _get_json(session, DATASETS[year], params)
    if not isinstance(data, list) or len(data) < 2:
        raise RuntimeError(f"{year}: unexpected API response shape")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    print(f"  {year}: fetched {len(data) - 1} counties -> {path}")
    return path


def load_raw(year: int) -> list[list[str]]:
    return json.loads(raw_path(year).read_text())


# --- Broomfield 2000 reconstruction (intercensal estimates base) ------------

def broomfield_base_path() -> Path:
    return RAW_DIR / "broomfield_intercensal_2000.json"


def fetch_broomfield_base(force: bool = False) -> Path:
    """Download the intercensal 4/1/2000 base for Broomfield (08014) and its
    four parent counties, cached as a small JSON. See broomfield.py."""
    import csv
    import io

    from .broomfield import UNITS

    path = broomfield_base_path()
    if path.exists() and not force:
        print(f"  Broomfield 2000 base: cached at {path}")
        return path

    want = {u[2:] for u in UNITS}  # county codes within state 08
    resp = requests.Session().get(INTERCENSAL_AGESEX_URL, timeout=300)
    resp.raise_for_status()
    rows = list(csv.reader(io.StringIO(resp.text)))
    header, *body = rows
    idx = {c: i for i, c in enumerate(header)}
    for col in ("STATE", "COUNTY", "SEX", "AGEGRP", "ESTIMATESBASE2000"):
        if col not in idx:
            raise RuntimeError(
                f"intercensal file layout changed: no {col!r} column in "
                f"{INTERCENSAL_AGESEX_URL}"
            )

    out = []
    for r in body:
        if r[idx["STATE"]] != "08" or r[idx["COUNTY"]] not in want:
            continue
        sex, agegrp = r[idx["SEX"]], r[idx["AGEGRP"]]
        if sex == "0" or agegrp == "0":  # skip the both-sexes / all-ages totals
            continue
        out.append({"geoid": "08" + r[idx["COUNTY"]], "sex": sex,
                    "agegrp": int(agegrp),
                    "base2000": int(r[idx["ESTIMATESBASE2000"]])})

    # 5 units x 2 sexes x 18 age groups = 180 rows.
    if len(out) != len(UNITS) * 2 * 18:
        raise RuntimeError(
            f"Broomfield base: expected {len(UNITS) * 2 * 18} rows, got "
            f"{len(out)} -- check the intercensal file for these counties."
        )
    payload = {"source": INTERCENSAL_AGESEX_URL, "col": "ESTIMATESBASE2000",
               "rows": out}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    total = sum(x["base2000"] for x in out if x["geoid"] == "08014")
    print(f"  Broomfield 2000 base: {len(out)} rows -> {path} "
          f"(Broomfield 08014 total {total:,})")
    return path


def load_broomfield_base() -> dict | None:
    path = broomfield_base_path()
    if not path.exists():
        return None
    return json.loads(path.read_text())


# --- Group quarters (sex by age), discovered at runtime ---------------------

def gq_raw_path(year: int) -> Path:
    return RAW_DIR / f"gq_county_{year}.json"


def _fetch_chunked(session: requests.Session, base: str,
                   variables: list[str], key: str | None) -> list[list[str]]:
    """Fetch a variable list in <=45-variable chunks, merged on county."""
    merged: dict[tuple[str, str], dict[str, str]] = {}
    names: dict[tuple[str, str], str] = {}
    for i in range(0, len(variables), 45):
        chunk = variables[i:i + 45]
        params = {"get": "NAME," + ",".join(chunk), "for": "county:*"}
        if key:
            params["key"] = key
        header, *rows = _get_json(session, base, params)
        idx = {c: j for j, c in enumerate(header)}
        for row in rows:
            geo = (row[idx["state"]], row[idx["county"]])
            names.setdefault(geo, row[idx["NAME"]])
            merged.setdefault(geo, {}).update(
                {v: row[idx[v]] for v in chunk}
            )
    out_header = ["NAME"] + variables + ["state", "county"]
    out_rows = [
        [names[geo]] + [merged[geo].get(v, "0") for v in variables]
        + [geo[0], geo[1]]
        for geo in sorted(merged)
    ]
    return [out_header] + out_rows


def fetch_gq_year(year: int, force: bool = False) -> Path | None:
    """Fetch the county-level group-quarters sex-by-age table, if the
    dataset has one. The table is located by its published description and
    its variables are mapped from their labels (see discover.py), so no
    variable IDs are hardcoded. Returns None when no such table exists.
    """
    from .discover import build_var_map, find_group

    if year not in DATASETS:
        print(f"  {year}: not an API dataset, no group-quarters sex-by-age "
              f"table; skipping GQ adjustment for {year}")
        return None

    path = gq_raw_path(year)
    if path.exists() and not force:
        print(f"  {year}: GQ cached at {path}")
        return path

    base = DATASETS[year]
    session = requests.Session()
    group_name = find_group(_get_json(session, f"{base}/groups.json",
                                      timeout=120))
    if group_name is None:
        print(f"  {year}: no group-quarters sex-by-age table in this "
              f"dataset; skipping GQ adjustment for {year}")
        return None

    meta = _get_json(session, f"{base}/groups/{group_name}.json", timeout=120)
    var_map = build_var_map(meta["variables"])
    if not var_map:
        raise RuntimeError(f"{year}: table {group_name} matched but no "
                           f"sex-by-age variables parsed")

    variables = sorted(var_map)
    data = _fetch_chunked(session, base, variables,
                          os.environ.get("CENSUS_API_KEY"))
    payload = {"group": group_name,
               "var_map": {v: list(var_map[v]) for v in variables},
               "data": data}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    print(f"  {year}: GQ table {group_name}, {len(data) - 1} counties, "
          f"{len(variables)} variables -> {path}")
    return path


def load_gq_raw(year: int) -> dict | None:
    path = gq_raw_path(year)
    if not path.exists():
        return None
    return json.loads(path.read_text())


# --- Group quarters recovered from the "by group quarters type" table --------
#
# When a dataset lacks the plain GQ sex-by-age table (2000 SF1), it may still
# carry a GQ sex-by-age table with an extra group-quarters-type dimension
# (P038 / PCT017). Collapsing that dimension recovers GQ by sex by age -- but
# only across whatever age bands that table tabulates (2000: three coarse
# bands). We fetch and cache it for validation and reporting; whether it can
# feed the household basis is decided by its resolution (see discover.py).

def gq_bytype_raw_path(year: int) -> Path:
    return RAW_DIR / f"gq_bytype_county_{year}.json"


def fetch_gq_by_type_year(year: int, force: bool = False) -> Path | None:
    """Recover county-level GQ by sex by age from the dataset's
    "...BY GROUP QUARTERS TYPE" table, summing over the type dimension.

    Returns the cache path, or None if the dataset has no such table. The
    cached payload records the age resolution ('fine' / 'coarse'): coarse
    recoveries (2000's Under 18 / 18-64 / 65+) are kept for validation and
    reporting only -- they cannot be subtracted at 5-year resolution.
    """
    from .discover import (GQ_BYTYPE_DESCRIPTION, find_group,
                           gq_bytype_var_map, gq_resolution)

    if year not in DATASETS:
        return None

    path = gq_bytype_raw_path(year)
    if path.exists() and not force:
        print(f"  {year}: GQ-by-type cached at {path}")
        return path

    base = DATASETS[year]
    session = requests.Session()
    group_name = find_group(
        _get_json(session, f"{base}/groups.json", timeout=120),
        description=GQ_BYTYPE_DESCRIPTION,
    )
    if group_name is None:
        return None

    meta = _get_json(session, f"{base}/groups/{group_name}.json", timeout=120)
    var_map = gq_bytype_var_map(meta["variables"])
    variables = sorted(var_map)
    resolution = gq_resolution({var_map[v][1] for v in variables})

    data = _fetch_chunked(session, base, variables,
                          os.environ.get("CENSUS_API_KEY"))
    payload = {"group": group_name,
               "resolution": resolution,
               "var_map": {v: list(var_map[v]) for v in variables},
               "data": data}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))

    total, by_sex = gq_bytype_total(payload)
    bands = sorted({var_map[v][1] for v in variables})
    print(f"  {year}: recovered GQ from {group_name} (summed over "
          f"group-quarters type), {len(data) - 1} counties; national total "
          f"{total:,} (M {by_sex.get('M', 0):,} / F {by_sex.get('F', 0):,}); "
          f"age resolution '{resolution}' over bands {bands} -> {path}")
    return path


def gq_bytype_total(payload: dict) -> tuple[int, dict[str, int]]:
    """National GQ total and per-sex totals from a by-type recovery payload."""
    header, *rows = payload["data"]
    idx = {c: i for i, c in enumerate(header)}
    var_map = payload["var_map"]
    total = 0
    by_sex: dict[str, int] = {}
    for row in rows:
        for var, (sex, _band) in var_map.items():
            v = int(row[idx[var]])
            total += v
            by_sex[sex] = by_sex.get(sex, 0) + v
    return total, by_sex


def load_gq_bytype_raw(year: int) -> dict | None:
    path = gq_bytype_raw_path(year)
    if not path.exists():
        return None
    return json.loads(path.read_text())
