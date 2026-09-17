# Conventions (read fully before touching this repo)

## Goal
A dataset of police and fire expenditure shares for all US municipalities with
population >= 100,000, across as many years as the Census individual unit files
allow (1967+ via Willamette compilation; 2012/2017/2022 full censuses and annual
samples parsed directly), that will hold up to outside scrutiny.

## Ground rules
- Primary source is the Census Bureau Annual Survey of State & Local Government
  Finances individual unit files (IUF). Item codes: 62 = police protection,
  24 = fire protection. Prefixes: E current ops, F construction, G other capital.
- Every number we publish carries: source file, item codes summed, and the Census
  imputation flag (R reported / I imputed / A analyst / S alternative source).
- Denominators are named explicitly. Never say "budget" without saying which one:
  - `total_expenditure`  = all E/F/G/I/J/L/M/Q/S codes (Census total less insurance trust; X codes absent after 2015)
  - `general_expenditure` = total minus utility (91-94), liquor (90), insurance trust
  - `general_fund_budget` = ONLY from city adopted budget documents (spot checks)
- Cross-validation sources are recorded in `validation/` with URL, retrieval date,
  the exact figure, and the framing (all funds / general fund / ACFR governmental
  activities). Disagreements are explained, not hidden.
- Amounts in Census files are thousands of dollars. Convert once, at load.
- Consolidated city-counties and cities with dependent school systems are flagged
  in `data/census_out/city_flags.csv`; their shares are not comparable to plain
  municipalities without adjustment.

## Layout
- `pipeline/`      Python, stdlib + pandas only. `python pipeline/build.py` rebuilds.
- `data/census_raw/` downloaded zips/txt (gitignored, re-downloadable by pipeline)
- `data/census_out/` published CSVs
- `data/<source>/`  each cross-validation source, raw + normalized CSV + NOTES.md
- `validation/`    comparison tables and the written validation report
- `docs/`          this file, methodology, source register

## Agent deliverables
Each research agent writes into its `data/<source>/` folder: the raw download (or a
note on why it could not be obtained), a normalized CSV with columns
`city,state,fiscal_year,police_usd,fire_usd,denominator_usd,denominator_type,source_url,retrieved`,
and a `NOTES.md` describing access, coverage, caveats, and anything surprising.
