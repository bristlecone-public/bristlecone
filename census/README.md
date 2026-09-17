# census — cohort residual tracing

*Where did the children of 2000 go?*

Traces synthetic birth cohorts through the U.S. decennial censuses
(1950 → 2020, seven decades) at county level. A decade moves every cohort up
exactly two 5-year age bins, so the 10–14-year-olds counted somewhere in 2000
are the 20–24-year-olds counted somewhere in 2010. Comparing each county's actual
cohort count against the count expected from national survival yields a **net
migration residual**: which places hemorrhage their 20-somethings, which
import them, and how that has shifted between the 2000s and the 2010s.

## Method

Census survival ratio method — no external life tables required:

1. For each cohort (5-year age bin × sex at census *t*), compute the
   **national** ratio of its size at *t+10* to its size at *t*. This ratio
   absorbs mortality *and* net international migration.
2. Each county's expected count at *t+10* is its count at *t* times that
   ratio.
3. `actual − expected` is the county's net migration residual relative to the
   national average — primarily net domestic migration. Residuals sum to zero
   nationally by construction.

Counties are compared on **constant-territory analysis units**: FIPS recodes
are mapped (Oglala Lakota, Kusilvak, Dade→Miami-Dade) and counties involved
in splits/merges (southeast Alaska, Denali, Valdez–Cordova, Broomfield CO,
Bedford / Alleghany / Halifax VA) are combined into merged units across all
years. See `cohort_trace/crosswalk.py`.

### 1990

The Census API only hosts decennial data from 2000 forward, so 1990 comes
from the raw STF1A dBase files on `www2.census.gov` (`CD90_1A_*` CD-ROM
images): `cohort_trace/fetch1990.py` downloads two segments per state,
sums table P12 (race × sex × 31 age categories) over race, and keeps the
SUMLEV 050 rows. The parse refuses to cache unless the national total
matches the published 1990 count exactly (248,709,873 + 3,522,037 PR).
1990 has no county group-quarters age table, so 1990–2000 runs on the
total-population basis.

### 1950–1980

These come from NHGIS (IPUMS) via the extract API — free account required
(https://account.ipums.org, include NHGIS; set `IPUMS_API_KEY`, or
`IPUMS_API_KEY_FILE`, or `~/.ipums_api_key`). `cohort_trace/fetchnhgis.py`
submits one extract, polls until built, and parses the county sex-by-age
tables: 1950 `cAge/NT8`, 1960 `cAge1/NT5`, 1970 `Cnt2/NT2A` (single years),
1980 `cASRS/NT004` (single years) + `STF1/NT10B` (its 75–84/85+ top).
Validation demands exact matches against published totals (1960/70/80 to
the person; 1950 continental exact, with Hawaii Territory's ~1% published
age-not-reported gap allowed).

Coverage limits: Alaska is excluded before 1980 (judicial divisions and
election districts aren't comparable to boroughs) and Puerto Rico before
1990, so those units enter the flows in the 1980–90 and 1990–2000 decades
respectively. The engine adapts cohort bins per decade (1950 publishes a
merged 75–84; 1980 tops out at 75–84/85+, so 1970's 65–74 traces as one
combined cohort). Pre-1990 decades run on total population — military
bases and college towns dominate their young-adult flows, visibly so in
the 1950s–60s (Fort Leonard Wood, Cape Canaveral, the Vietnam-era forts).
Virginia's independent-city churn is handled with merged constant-territory
units (see `crosswalk.py`); smaller VA annexations of the 1950s–70s remain
an accepted caveat.

### Group quarters

Colleges, prisons, and military bases would dominate young-adult flows (a
university county "imports" 18–22-year-olds by construction), so the
pipeline also fetches each census's group-quarters sex-by-age table and
traces the **household population** (total minus group quarters) whenever
both ends of a decade have GQ data *at 5-year resolution*. The GQ table is
*discovered at runtime* — located by its published description in the
dataset's metadata, with variables mapped from their labels — so no fragile
variable IDs are hardcoded; if a year lacks a usable table, that period
falls back to total population and the report says so.

**Only 2010→2020 runs on the household basis.** 2010 SF1 and 2020 DHC both
publish group quarters by sex by 5-year age (the `PCO1` / DHC tables), so
they can be subtracted cohort-for-cohort. 2000 and 1990 cannot:

- **2000 SF1 has no group-quarters-by-5-year-age table.** Its only GQ
  sex-by-age tables (`P038`, `PCT017`) add a group-quarters-*type* dimension
  and tabulate age in just three coarse bands — Under 18 / 18–64 / 65+.
  `fetch_gq_by_type_year` still fetches one and sums over the type dimension:
  the recovered national total, **7,778,633** (50 states + DC; 7,825,407
  including Puerto Rico), matches the published Census 2000 figure exactly,
  which confirms the recovery is correct. But three coarse bands cannot be
  subtracted at 5-year resolution — the college-dorm distortion lives inside
  the undividable "18–64" band — and 2000 SF1 has no household-by-age table
  either, so **2000→2010 stays on the total-population basis**. Apportioning
  the coarse bands into 5-year bins would be a fabricated age distribution,
  which this pipeline deliberately does not do.
- **1990 STF1A carries no county group-quarters age breakdown at all**, and
  even if it did, 1990→2000 would still need 2000 at 5-year resolution, which
  is unavailable. So **1990→2000 stays on the total-population basis** too.

Because decades sit on different bases, **they are not level-comparable**:
subtracting group quarters shifts a college or prison county's young-adult
rate by tens of percentage points, so the report and explorer label every
decade's basis and warn against reading a basis switch as a migration trend.

Even the household basis does **not** neutralize college towns. The Census
counts only dorms and recognized Greek houses as group quarters; most students
live off-campus and are tabulated as household population, so subtracting group
quarters removes dorm residents but not the larger off-campus student influx.
University-county young-adult "gains" therefore persist on the household basis
(see Known caveats).

### Known caveats

The residual is net migration *relative to the national average*, but several
other signals ride inside it and bias specific, identifiable county types.

- **Off-campus students inflate college-town young-adult gains — even on the
  household basis.** The Census counts only dormitories and recognized
  fraternity/sorority houses as group quarters; ~65–80% of undergraduates and
  >95% of graduate students live off-campus and are tabulated as *household*
  population. Subtracting group quarters removes dorm residents but not the
  larger off-campus student influx, so the top young-adult-gaining counties on
  the 2010→2020 household basis are still dominated by university towns
  (Charlottesville/UVA, Clarke GA/UGA, Harrisonburg/JMU, Riley KS/KSU,
  Whitman WA/WSU, Story IA/ISU, Montgomery VA/Virginia Tech). That ranking
  largely measures off-campus university enrollment, not economic in-migration.
- **International immigration inflates gateway metros and penalizes rural
  counties.** The single national survival ratio absorbs net international
  migration, which concentrates in gateway metros (Miami, NYC, Houston, LA,
  Chicago, Dallas). Those counties post positive residuals that are really
  foreign arrivals, not domestic attraction; meanwhile the immigration-boosted
  national ratio inflates the *expected* count everywhere, penalizing
  low-immigration rural and Midwestern counties and mislabeling them as
  domestic out-migration.
- **Differential undercount and young-adult mortality masquerade as
  out-migration.** Census coverage differs by age, sex, race, and decade, and
  the method treats every uncounted person *and every death* as an out-migrant.
  The biggest "out-migration" counties are disproportionately tribal (Rolette,
  Benson ND), high-poverty Delta (Phillips, Lee AR), border (Presidio TX), and
  Puerto Rican (Guánica) — exactly the populations the 2020 Post-Enumeration
  Survey found net-undercounted (on-reservation American Indian −5.6%, Black
  −3.3%, Hispanic −5.0%) — while 2010–2020 brought historic rural young-adult
  mortality (opioids, motor-vehicle deaths, suicide). None of this is corrected
  here.
- **2020 differential privacy**: 2020 counts carry injected noise. County
  totals are accurate, but rows with `reliability = low`
  (expected < 100) should not be interpreted individually.
- **Broomfield over-merge**: the constant-territory unit for the 2001 creation
  of Broomfield County bundles Broomfield with its parent counties into one
  merged unit, coarser than the actual boundary change (see `crosswalk.py`).
- The `85+` open bin cannot be traced; the 75–84-year-olds of *t* are traced
  as one combined cohort into `85+` at *t+10*.

## Running it

Requires outbound HTTPS to `api.census.gov` **and a Census API key** — as of
2025 the API answers keyless data queries with a "Missing Key" page. Keys are
free and instant: <https://api.census.gov/data/key_signup.html>. Export it as
`CENSUS_API_KEY` before running. Total download is a few MB; everything runs
in seconds on one core.

```sh
git clone https://github.com/bristlecone-public/bristlecone.git
cd bristlecone/census
make setup && make test && make all
```

Outputs land in `output/`:

- `report.md` — top/bottom counties for young-adult retention, per decade
- `cohort_flows_2000-2010.csv`, `cohort_flows_2010-2020.csv` — every
  county × cohort × sex row (expected, actual, residual, rate)
- `cohort_flows_both_sexes.csv` — sexes combined
- `explorer.html` — self-contained interactive county choropleth
  (decade / cohort / sex controls, per-county cohort profiles, ranked
  tables; no external requests at view time). Rebuild with `make explorer`.

Individual steps: `make fetch`, `make build`, `make report`. Different years:
`.venv/bin/python -m cohort_trace all --years 2000 2010`. The default years
are 1990 2000 2010 2020; the 1990 fetch downloads the STF1A files, which
occupy ~2.6 GB uncompressed (cached under `data/raw/cd90/` as 205 dBase
segments) — size disk accordingly.

## Project layout

```
cohort_trace/
  fetch.py       Census API client (P12 + group quarters, county level, cached)
  fetch1990.py   1990 STF1A dBase parser (www2.census.gov CD-ROM images)
  fetchnhgis.py  1950-1980 via the NHGIS/IPUMS extract API
  discover.py    runtime table discovery + label-driven variable mapping
  normalize.py   published age categories -> standard 5-year bins
  crosswalk.py   constant-territory county units across 2000/2010/2020
  engine.py      census survival ratio cohort tracing (household/total basis)
  report.py      CSVs + markdown report
  cli.py         fetch | build | report | all
explorer/        build_explorer.py + template.html + county topology
                 (us-atlas counties-albers-10m, pre-projected) -> explorer.html
tests/           synthetic-fixture tests (run offline)
```

## Roadmap

- Tract-level tracing via NHGIS standardized time series.
- ~~1950–1980 back-extension via NHGIS~~ — done.
- ~~1990 SF1 back-extension~~ — done, from the raw STF1A files.
- ~~Maps and an interactive explorer for the flows~~ — done: `make explorer`.
  Puerto Rico is in the explorer's tables/search but not drawn (the Albers
  composite topology covers the 50 states + DC).
