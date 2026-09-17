# Bristlecone

Public-data analysis, published so the methods and the numbers can be checked.

Everything here is built from primary public sources — Census Bureau decennial files, BLS and
BEA releases, NOAA/NASA feeds, and similar — with the pipelines, the documentation, and the
known biases in the open. Live dashboards: **[bristleconeanalytics.com](https://bristleconeanalytics.com)**.

## Projects

| Directory | What it does |
|---|---|
| `census/` | **Cohort residual tracing.** Synthetic birth cohorts pushed through seven decennial censuses (1950→2020) at county level using the census survival-ratio method — which places import their twenty-somethings and which lose them, decade after decade — with an interactive flow explorer. |
| `cpi-lab/` | **Item-level CPI analysis.** Eleven pipelines dissecting US consumer inflation below the headline: frequency-weighted ("salience") CPI, distribution shape, persistence, revision vintages, instrument health, PPI→CPI pass-through, tariff exposure, chained-CPI substitution, metro real wages, and a lead-lag network of item prices. |
| `city-safety-spend/` | **Municipal police and fire spending.** What share of city government spending goes to police and fire, for every US city of 100,000+ residents (332 cities), 1967 to 2024 — built from the Census Bureau's Annual Survey of State and Local Government Finances individual unit files and cross-validated against five independent sources. |
| `pulse/` | **Six "vital signs" dashboards** on a shared Cloudflare Worker + KV framework: `gridpulse` (the electric grid), `econpulse` (the economy), `healthpulse` (public health), `skypulse` (space weather), `netpulse` (the internet), `computepulse` (AI & compute). |

## Reading the numbers

Each project documents its own limitations in its `README.md` and `docs/`, and those caveats are
part of the result, not boilerplate. A few worth knowing before you cite anything:

- **census** — the survival-ratio residual absorbs international migration, differential
  undercount, and mortality alongside domestic migration; off-campus students inflate
  college-town young-adult gains even on the household basis; pre-1990 decades run on total
  population, so military installations and resource booms dominate them. See
  [`census/README.md`](census/README.md) and the caveats section of
  [`census/output/report.md`](census/output/report.md).
- **cpi-lab** — several pipelines are deliberately heuristic indices rather than causal
  estimates. The lead-lag network (P10) is screened co-movement, not proven causation; the
  pass-through index (P6) is historical-relationship arithmetic, not a forecast. Each `docs/P*.md`
  states what its number is and is not.
- **city-safety-spend** — every share column names its own denominator (`_pct_general`,
  `_pct_total`, `_pct_core`, `_pct_general_ex_edu`), and **none of them is the "general fund" share
  quoted in budget speeches**. Consolidated city-counties, cities running their own schools, and
  cities whose fire or police is provided externally are flagged and are not comparable to plain
  municipalities without adjustment. `docs/METHODOLOGY.md` §3 and `validation/REPORT.md` — which
  records where this dataset disagrees with BJS, FBI, FiSC, Vera and Willamette, and why — are
  required reading before citing a number.
- **pulse** — thresholds are fixed reference levels, not regime-adjusted signals, and each
  instrument names its source and cadence in `docs/INSTRUMENTS.md`.

## What is in this repository

- Every pipeline's source and documentation.
- **[`data/`](data/) — the published outputs**, so the numbers can be checked without running
  anything:
  - `data/cpi-lab/cpi_item_month.parquet` — the base CPI panel (225,479 rows, one row per item ×
    month, **1913-01 → 2026-08**) that every CPI Lab pipeline derives from;
  - `data/cpi-lab/p*.json`, `r1_expectations.json` — one output per pipeline, each carrying its own
    `generated_at`, its caveats, and (for most) a `validation` block comparing computed values
    against BLS published figures;
  - `data/census/cohort_flows_both_sexes.csv.gz` — the complete seven-decade cohort-flow table.

  [`data/README.md`](data/README.md) describes every file and what it is good for;
  [`data/DATA_SOURCES.md`](data/DATA_SOURCES.md) carries provenance, terms, and attribution. A bulk
  `bristlecone-data.zip` is attached to the latest Release.
- Published artifacts: [`census/output/report.md`](census/output/report.md) (the seven-decade
  write-up) and `census/output/explorer.html` (a self-contained interactive explorer — the county
  flow data is embedded in the page).

The per-decade, per-sex census cohort-flow CSVs (~158 MB) are regenerable rather than committed —
run the pipeline below to produce them.

### Live Pulse data — no download needed

Each of the six Pulse workers serves its current state as JSON over a public, keyless, CORS-enabled
API. Swap in any of `gridpulse`, `econpulse`, `healthpulse`, `skypulse`, `netpulse`, `computepulse`:

| Endpoint | Returns |
|---|---|
| `/api/state` | Every instrument's latest value, status, history series, and `fetchedAt` timestamp |
| `/api/instrument?id=<id>` | One instrument's full record, including its stored history |
| `/api/registry` | The instrument catalogue: ids, titles, units, cadences, thresholds, and source URLs |
| `/api/health` | Collector health — per-instrument success/failure and staleness |

```bash
curl https://gridpulse.bristleconeanalytics.com/api/state
curl https://econpulse.bristleconeanalytics.com/api/registry
```

Values are snapshots on each instrument's own cadence, and `/api/registry` names the upstream
source and licence for every one. (`/api/collect` exists but is admin-only and token-protected —
it triggers collection rather than reading it.)

## Reproducing

Some sources need a free API key. Copy the template and fill it in:

```bash
cp .env.example .env     # then edit .env
```

- **census** — free keys from [api.census.gov](https://api.census.gov/data/key_signup.html)
  (decennial API) and [ipums.org](https://www.ipums.org/) (NHGIS, for the 1950–1980 extension).

  ```bash
  cd census && python -m cohort_trace all
  ```

  `fetch` downloads and caches the raw tables, `build` normalises and crosswalks them onto
  constant-territory units, `report` traces every decade and writes the report plus CSVs.

- **cpi-lab** — set `CPI_ROOT` to a working directory, then run the pipelines (they are
  independent and each writes one JSON):

  ```bash
  cd cpi-lab/pipelines && CPI_ROOT=/path/to/workdir ./p0_fetch.py
  ```

  `run_monthly.sh` shows the intended order and gating.

- **pulse** — each app deploys on its own:

  ```bash
  cd pulse/gridpulse && npm install && npx wrangler deploy
  ```

  Create your own KV namespace and paste its id into `wrangler.jsonc` (the committed ids are
  placeholders). `npm run check` validates the instrument registry; `npm run collect -- --serve`
  runs the UI locally.

## Repository conventions

- The six Pulse apps share `pulse/*/src/framework/`, which **must stay byte-identical** across
  all six. Fix a framework bug in one, copy the file to the other five in the same commit, and
  verify with `md5sum pulse/*/src/framework/<file>`.
- Each project is self-contained: its own docs, its own tooling, no shared root build.
- Pipelines are idempotent and cache their raw downloads, so re-running is cheap and the raw
  inputs stay auditable.
