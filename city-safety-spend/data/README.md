# city-safety-spend — raw source files

**Nothing in here is in git, and nothing in here should be.** These are the ~2.8 GB of government
source files the project is built from. They live in the monorepo so the provenance for every data
project sits in one place, rather than inside one project's working copy where a clone would look
complete while being unreproducible.

Moved here 2026-09-17 from `Documents\GitHub\city-safety-spend\data\`.

| directory | MB | what |
|---|---|---|
| `census_raw/` | 1,286 | Census Bureau individual unit files, finance and employment, 2012 to 2025 |
| `willamette/raw/` | 735 | Willamette University Government Finance Database, 1967 onward |
| `spotcheck/raw/` | 498 | 29 cities' own annual comprehensive financial reports |
| `fbi/raw/` | 180 | FBI Return A master files and law enforcement employee data |
| `fisc/raw/` | 30 | Lincoln Institute Fiscally Standardized Cities |
| `county_alloc/raw/` | 16 | Census population estimates, place within county |
| `bjs/raw/` | 14 | Bureau of Justice Statistics LEMAS and CSLLEA volumes |
| `rpp/raw/` | 3 | BEA regional price parities |
| `vera/raw/` | 1 | Vera Institute FY2020 city budgets |

## How the pipeline finds this

`pipeline/build.py` resolves `RAW_ROOT` in this order, so a fresh clone still works with nothing
configured:

1. `$CSS_RAW_ROOT`
2. the path written in `city-safety-spend/data/.raw_root` (one line, gitignored, per-machine)
3. `data/` inside the checkout, which is the original layout

On this machine option 2 points here. If the project itself moves into this monorepo, the raw files
are already in the right place relative to it and the pointer can be deleted.

## What is *not* here

The committed extracts stay in the project repo and are what most of the pipeline actually reads:
`data/bjs/bjs_police_budgets.csv`, `data/fbi/fbi_police_employees.csv`,
`data/willamette/willamette_municipal_100k.csv`, the spot-check CSVs, the CPI series and the BEA
deflator. Only five places in the pipeline touch the raw tree — the Census parser, the county
allocation, the price parities, the FiSC comparison and the source poller.

## Re-downloading

Every URL is in the project's `docs/METHODOLOGY.md` section 1. Downloading a new Census year is
deliberately manual: the file name and record layout have each changed twice, and `pipeline/poll_sources.py`
exists to tell you when that has happened rather than to fetch it for you.
