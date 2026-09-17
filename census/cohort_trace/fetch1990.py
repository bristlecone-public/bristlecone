"""Fetch 1990 county sex-by-age counts from the raw STF1A CD-ROM images.

The Census API only hosts decennial data from 2000 forward, but the full
1990 STF1A files are on www2.census.gov as dBase III (.DBF) segments, one
set per state, spread over the CD90_1A_* CD-ROM directories. 1990 STF1 has
no plain sex-by-age table; P12 is Race(5) by Sex(2) by Age(31) — variables
P0120001..P0120310, race-major, male block then female block within each
race — so summing the five races yields sex by age. P12 spans segments
STF1A1<ss> through STF1A4<ss> (observed split 62/93/93/62 — the fetcher
takes whatever P012 fields each segment carries and asserts all 310 arrive).

County rows are SUMLEV 050. Downloads are cached under data/raw/cd90/, and
the parsed result is cached as data/raw/p12_county_1990.json in the same
[header, *rows] shape the API fetcher produces, with synthetic variable
names M01..M31 / F01..F31 (see fetch.var_map).
"""

from __future__ import annotations

import io
import json
import re
import struct
import time
import zipfile
from pathlib import Path

import requests

from .bins import BINS_1990

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
CD_CACHE = RAW_DIR / "cd90"

BASE = "https://www2.census.gov/census_1990"

# Published 1990 resident population, the parse-validation anchors.
US_1990 = 248_709_873
PR_1990 = 3_522_037

N_AGE = len(BINS_1990)          # 31
N_RACES = 5
P12_VARS = N_RACES * 2 * N_AGE  # 310
SEGMENTS = ("1", "2", "3", "4")  # P12 spans these STF1A segments


def _get(session: requests.Session, url: str) -> bytes | None:
    """GET with retry: www2.census.gov rate-limits bulk pulls with 429s."""
    delay = 20.0
    for attempt in range(6):
        resp = session.get(url, timeout=300)
        if resp.status_code == 404:
            return None
        if resp.status_code in (429, 502, 503, 504) and attempt < 5:
            wait = float(resp.headers.get("Retry-After") or delay)
            print(f"    HTTP {resp.status_code} for {url.rsplit('/', 1)[1]}; "
                  f"retrying in {wait:.0f}s", flush=True)
            time.sleep(wait)
            delay *= 2
            continue
        resp.raise_for_status()
        return resp.content
    raise RuntimeError(f"unreachable retry loop for {url}")


def discover_states(session: requests.Session) -> dict[str, dict[str, str]]:
    """Map each state abbreviation to its P12 segment URLs (segments 1-4).

    Scans the CD90_1A_* directory listings; file naming varies by disc
    (case, and .dbf.zip vs bare .dbf), so take whatever each disc offers,
    preferring the zip.
    """
    idx = _get(session, f"{BASE}/")
    if idx is None:
        raise RuntimeError(f"cannot list {BASE}/")
    dirs = sorted(set(re.findall(r'href="(CD90_1A[^"]*)/"', idx.decode())))
    out: dict[str, dict[str, str]] = {}
    for d in dirs:
        listing = _get(session, f"{BASE}/{d}/")
        if listing is None:
            continue
        files = re.findall(
            r'href="((?:stf1a|STF1A)[1-4][A-Za-z]{2}\.(?:dbf|DBF)(?:\.zip)?)"',
            listing.decode())
        per_state: dict[str, dict[str, str]] = {}
        for f in files:
            m = re.match(r"(?i)stf1a([1-4])([a-z]{2})\.dbf(\.zip)?$", f)
            seg, abbr, zipped = m.group(1), m.group(2).lower(), m.group(3)
            slot = per_state.setdefault(abbr, {})
            # prefer zipped when both are listed
            if seg not in slot or zipped:
                slot[seg] = f"{BASE}/{d}/{f}"
        for abbr, slot in per_state.items():
            if set(SEGMENTS) <= slot.keys():
                out.setdefault(abbr, slot)
    return out


def _read_dbf(data: bytes, id_fields: set[str],
              prefix: str) -> list[dict[str, str]]:
    """Minimal dBase III reader.

    Returns records as dicts holding the id fields (which must all exist)
    plus every field whose name starts with `prefix`.
    """
    n_records, header_size, record_size = struct.unpack_from("<IHH", data, 4)
    fields = []
    pos, offset = 32, 1  # offset 0 is the deletion flag
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\x00")[0].decode("ascii")
        length = data[pos + 16]
        fields.append((name, offset, length))
        offset += length
        pos += 32
    picked = [(n, o, l) for n, o, l in fields
              if n in id_fields or n.startswith(prefix)]
    missing = id_fields - {n for n, _, _ in picked}
    if missing:
        raise RuntimeError(f"DBF is missing id fields: {sorted(missing)}")
    out = []
    for i in range(n_records):
        rec = data[header_size + i * record_size:
                   header_size + (i + 1) * record_size]
        if len(rec) < record_size or rec[0:1] == b"*":
            continue
        out.append({n: rec[o:o + l].decode("ascii", "replace").strip()
                    for n, o, l in picked})
    return out


def _fetch_segment(session: requests.Session, url: str) -> bytes:
    CD_CACHE.mkdir(parents=True, exist_ok=True)
    cache = CD_CACHE / url.rsplit("/", 1)[1].lower()
    if cache.exists():
        raw = cache.read_bytes()
    else:
        raw = _get(session, url)
        if raw is None:
            raise RuntimeError(f"404 for {url}")
        cache.write_bytes(raw)
        time.sleep(1.0)  # politeness gap between bulk downloads
    if url.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            return z.read(z.namelist()[0])
    return raw


def _accumulate(seg_records: list[dict[str, str]],
                acc: dict[tuple[str, str], dict[str, int]]) -> None:
    """Fold one segment's county rows into per-county P012 variable dicts."""
    for rec in seg_records:
        if rec["SUMLEV"] != "050":
            continue
        geo = (rec["STATEFP"], rec["CNTY"])
        vals = acc.setdefault(geo, {})
        for k, v in rec.items():
            if k.startswith("P012"):
                vals[k] = int(v) if v else 0


def _cells(vals: dict[str, int]) -> list[int]:
    """Collapse the 310 race-by-sex-by-age variables to 62 sex-by-age cells.

    Layout is race-major (5 races), male ages 1..31 then female ages 1..31
    within each race: male var = r*62 + i + 1, female var = r*62 + 31 + i + 1.
    """
    if len(vals) != P12_VARS:
        raise RuntimeError(f"expected {P12_VARS} P012 variables per county, "
                           f"got {len(vals)}")
    out = []
    for sex_off in (0, N_AGE):
        for i in range(N_AGE):
            out.append(sum(vals[f"P012{r * 2 * N_AGE + sex_off + i + 1:04d}"]
                           for r in range(N_RACES)))
    return out


def fetch_1990(force: bool = False) -> Path:
    path = RAW_DIR / "p12_county_1990.json"
    if path.exists() and not force:
        print(f"  1990: cached at {path}")
        return path

    session = requests.Session()
    print("  1990: scanning CD90_1A directory listings on www2.census.gov...")
    states = discover_states(session)
    if len(states) < 52:
        raise RuntimeError(
            f"expected 52 state files (50 states + DC + PR), found "
            f"{len(states)}: {sorted(states)}")

    id_fields = {"SUMLEV", "STATEFP", "CNTY"}

    counties: dict[tuple[str, str], list[int]] = {}
    for abbr in sorted(states):
        if abbr == "pr":
            # Puerto Rico's STF1A has its own table set: P7 is already
            # Sex(2) by Age(31) over all persons (P007A/P007B), segment 1.
            recs = _read_dbf(_fetch_segment(session, states[abbr]["1"]),
                             id_fields, prefix="P007")
            n = 0
            for rec in recs:
                if rec["SUMLEV"] != "050":
                    continue
                geo = (rec["STATEFP"], rec["CNTY"])
                counties[geo] = (
                    [int(rec[f"P007A{i+1:03d}"] or 0) for i in range(N_AGE)]
                    + [int(rec[f"P007B{i+1:03d}"] or 0) for i in range(N_AGE)]
                )
                n += 1
            persons = sum(sum(v) for g, v in counties.items()
                          if g[0] == "72")
            print(f"    PR: {n} municipios, {persons:,} persons", flush=True)
            continue
        acc: dict[tuple[str, str], dict[str, int]] = {}
        for seg in SEGMENTS:
            recs = _read_dbf(_fetch_segment(session, states[abbr][seg]),
                             id_fields, prefix="P012")
            _accumulate(recs, acc)
        for geo, vals in acc.items():
            counties[geo] = _cells(vals)
        persons = sum(sum(counties[geo]) for geo in acc)
        print(f"    {abbr.upper()}: {len(acc)} counties, {persons:,} persons",
              flush=True)

    total = sum(map(sum, counties.values()))
    expected = US_1990 + PR_1990
    if total != expected:
        raise RuntimeError(
            f"1990 parse total {total:,} != published {expected:,} "
            f"(US {US_1990:,} + PR {PR_1990:,}) — table layout assumption "
            f"is wrong somewhere; refusing to cache")

    header = (["NAME"]
              + [f"M{i+1:02d}" for i in range(N_AGE)]
              + [f"F{i+1:02d}" for i in range(N_AGE)]
              + ["state", "county"])
    rows = []
    for (st, cnty), cells in sorted(counties.items()):
        rows.append([f"county {st}{cnty} (1990)"]
                    + [str(v) for v in cells] + [st, cnty])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([header] + rows))
    print(f"  1990: {len(rows)} counties, {total:,} persons -> {path}")
    return path
