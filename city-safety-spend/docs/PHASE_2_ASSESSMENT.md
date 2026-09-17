# Phase 2 roadmap: feasibility assessment

Assessed 2026-09-14 against `docs/PHASE_2_ROADMAP.md`. Every source named below was checked for
existence, access, and join key before the verdict; where the roadmap's description of a source was
wrong, the correction is stated.

## Verdicts at a glance

| Item | Verdict | Why |
|---|---|---|
| 1A Employment & payroll (ASPEP) | **Built 2026-09-15** | Public unit file, joins on our PID, splits sworn from civilian; publish headcount and payroll per FTE, never expenditure per FTE |
| 1B(i) CPI-U deflation | **Built 2026-09-15** | One BLS series |
| 1B(ii) Regional price parities | **Built 2026-09-15** | BEA publishes MSA-level RPP 2008+; cities must be mapped to metros |
| 2A Crime rates (FBI) | **Built 2026-09-15** | CDE bulk CSVs exist; 2021 is missing for several of the largest agencies |
| 2B EMS versus fire call split (NFIRS) | **Build once, no future** | PDR files 1980-2024 are public; NFIRS retired January 2026, NERIS has no public release yet |
| 3A Crowd-out index | **Dropped** | All codes are in our files already, but parks and libraries are often run by other governments |
| 3B Capital vs operating | **Already built, partly capped** | Columns exist; construction vs equipment cannot be split after 2021 |
| 3C Community burden for non-FiSC cities | **Built 2026-09-15 (jails and courts)** | Allocate county jails and courts only; county sheriff patrol and fire districts cannot be allocated honestly |
| 4A Peer-city engine | **Built 2026-09-15** | Everything needed is in `city_flags.csv` once RPP tiers exist |
| 4B Policy annotations | **Built 2026-09-15** | National markers are a list; local milestones are hand research per city |
| 4C Fact sheets | **Built 2026-09-15 (static pages + print view)** | The artifact sandbox blocks page-initiated downloads; a print view or a static export per city is the substitute |

## 1A. Employment and payroll: build

Verified in `data/census_raw/apes2022/` (2022 COG-E Individual Unit Files, 32 MB, public):

- Per-government records by function code with full-time employees, full-time March payroll,
  part-time employees, part-time payroll, each with an R/I-style data flag.
- **The sworn split exists.** Codes 062 "Police Protection, Persons with Power of Arrest" and 162
  "Police Protection, Other"; 024 "Fire Protection, Firefighters" and 124 "Fire Protection, Other".
  The roadmap's "sworn vs civilian" metrics are therefore direct reads, not estimates.
- Positions 75-80 carry the new 6-digit unit ID, which is the PID our finance pipeline keys on.
  No crosswalk needed for 2017 onward; the legacy 14-character ID in positions 1-14 covers 2012-2015.
- Census-year files (2012, 2017, 2022) cover every government; sample years cover the sampled units,
  which include all 100k+ cities.

Do not publish expenditure per employee. Code 62 dollars include or exclude pension and benefit costs
city by city (section 2 of METHODOLOGY), so dollars per FTE would show Los Angeles paying officers about
twice what Chicago does when the difference is where Chicago's pension contributions are booked. Publish
sworn officers and firefighters per 1,000 residents, the civilian share, and March payroll per full-time
employee, which is gross pay and unaffected by pension booking.

Caveats to carry: payroll is a single March month, so annual personnel cost per FTE has to be
approximated (x12) and will not reconcile to the finance file's current operations, which include
benefits, overtime patterns, and non-personnel costs. Census's own disclaimer says the unit data
"should not be viewed as an accurate time series for any individual unit." Treat headcount trends the
way we treat imputed dollars: flagged, not asserted.

## 1B. Deflation and regional prices: build

- CPI-U (BLS series CUUR0000SA0) is a single download; adding a real-dollar toggle to the long
  series is small work. The BEA state and local government consumption deflator is a defensible
  alternative for a public-sector series and is also public.
- BEA Regional Price Parities exist for every metropolitan statistical area from 2008, with all-items
  and rents/goods/services components. The work is the mapping: each of the 332 cities to its MSA
  (place-to-CBSA via the Census relationship files), and a rule for the years before 2008 (hold 2008
  constant, or leave RPP-adjusted views to 2008+). The roadmap's compensation figures ($150k-$200k
  versus $75k-$90k) are illustrative and should not appear in the product without a source.

## 2A. Crime context: build, with one documented hole

Commuter and tourist hubs (Atlanta, St. Louis, Orlando, Salt Lake City) divide crime by a resident
population far below their daytime population, which inflates their rates; any crime column needs that
caveat, and the 2x2 matrix is dropped. FBI Crime Data Explorer publishes agency-level bulk CSVs and an API (free key). The join is by
agency ORI to city, which is a one-time mapping for 332 police departments. The hole: the 2021
transition to NIBRS-only reporting left several of the largest agencies (New York, Los Angeles among
them) with no 2021 submission, and some remained partial into 2022. A crime-rate column has to carry the
reporting-coverage flag per city-year exactly as we carry Census imputation.
Contract cities are a second wrinkle: the sheriff's ORI covers more than the city.

## 2B. EMS share of fire workload: build once, no future

NFIRS Public Data Release files 1980-2024 are on OpenFEMA (20-table relational extracts, CSV after
2012). Incident type codes separate EMS/rescue from fire, so the EMS share per department is
computable. Two costs: the join is by fire department ID (FDID), which needs a manual FDID-to-city
map; and NFIRS participation is voluntary, so some large departments are absent or partial in some
years. The bigger issue is forward: NFIRS was retired on 31 January 2026 and its successor NERIS has
not published a public data release. This item can be built for 2012-2024 and then stops.

## 3A. Crowd-out index: dropped

All the codes are in the files we already parse: parks 61, libraries 52 (the roadmap says 60, which is
Parking), housing and community development 50, highways 44. The problem is not data but institutions.
Chicago's parks are the Chicago Park District, a separate government, so the city shows $30M of parks
against $1.6B of police; Honolulu's libraries are state-run and show $0. A ratio of police to
amenities would rank Chicago as the most safety-skewed large city in America for a purely
organizational reason. The index is buildable in an afternoon but would rank cities by organization chart; it is dropped.
If ever revived, restrict it to the FiSC basis, where park and library districts are already allocated.

## 3B. Capital versus operating: already in the dataset, capped after 2021

`police_current_ops_usd`, `police_capital_usd`, and the fire equivalents are already published, and
2,811 of 3,695 city-years have nonzero police capital. What cannot be done is the roadmap's
construction (F) versus equipment (G) distinction after 2021, because the 2022+ public files fold G
into F. A spike detector on the capital column is worth adding to `checks.py`.

## 3C. Community burden for the 197 non-FiSC cities: partly buildable, narrower than first assessed

The roadmap's count is wrong: 135 of our 332 cities are in FiSC, so 197 are not. The earlier version of
this section called a population-share allocation of the county sheriff "defensible, which is what FiSC
itself uses." It is what FiSC uses (Houston's FiSC police includes half of the $513M Harris County
Sheriff), but it is not defensible for police: county sheriff patrol covers unincorporated areas and
contract towns, not cities with their own departments. The allocation should be limited to countywide
functions every resident uses: jails (04, 05) and courts (25), by population share. County police (62)
is allocated only where the county force actually polices the city (joint departments such as Las Vegas
Metro, and sheriff-contract cities already flagged `police_contracted`). The fire-district component
remains unbuildable for the reasons below: 5,381 special districts report fire spending in 2022 (Orange
County Fire Authority alone spends $500M across many cities), and which cities each serves is not in any
Census file. The same limitation means the existing FiSC basis overstates police for most large cities;
see METHODOLOGY section 3.

## 4A. Peer-city engine: build

Population band, governance structure (`consolidated_or_independent`, `runs_schools`, `county_like`),
and service model (`fire_external`, `police_contracted`) are already in `city_flags.csv`. The
fourth criterion, regional cost tier, arrives with 1B. This is client-side work in the existing page.

## 4B. Policy annotations: build the national set, curate the local set

National markers (1994 Crime Act, the 2008-10 recession, 2020-21 CARES and ARPA) are a short list
with dates and are easy to draw on the trend chart. "Local milestones" means a researched
event list for each of 332 cities; that is not a data task and will not stay current. Recommend
shipping national markers plus a small hand-curated set for the Texas cities, clearly labelled.

## 4C. Fact sheets: not as a download button

The published-artifact sandbox blocks any download the page starts itself, including generated PDFs
and data-URI links. Two substitutes work: a print-styled fact-sheet view of the detail panel (the
viewer prints to PDF), or a script in `pipeline/` that renders one static HTML fact sheet per city
into the repo, which is also easier to cite. The content the roadmap lists (four denominators,
trajectory, peer rank, imputation status, spot-check citations) is all already computed.

## Status

- **1A employment, built.** 2012 to 2025, 4,342 city-years. Validated against published tables (within
  0.35% nationally, not exact) and against FBI police employee counts (sworn within 10% for 82% of
  reported city-years). Civilian counts failed validation and are kept off the dashboard.
- **1B(i) CPI-U, built.** Constant-dollar and per-resident columns in the long series and employment file;
  per-resident chart mode on the dashboard.

- **1B(ii) regional price parities, built.** All 332 cities mapped via the unit-ID county; price-adjusted
  per-resident spending in the long series and on the dashboard.
- **4A peer cities, built.** Computed in the pipeline, not the browser, so groups are reproducible; stable
  against weight changes; match-quality label flags the 7 cities with no structural match.

- **3C county jails and courts, built.** All 332 cities, not only the 197 outside FiSC, so the measure is
  uniform. Matches FiSC county components within 0.3% for the typical city; county police allocated only
  to contract-police cities.

- **2A reported crime, built.** Return A master files 2012-2024, validated against published 2019 city tables;
  coverage and consistency flags; shown as context only, with no quadrant or efficiency label.

- **4B annotations, built.** Four national markers plus four state fiscal limits, each sourced; no per-city
  milestone lists.
- **4C fact sheets, built.** 332 static pages (3 MB total) plus a print stylesheet on the dashboard, instead
  of the download button the sandbox forbids.

With 1A, 1B, 2A, 3C, 4A, 4B and 4C built, the Phase 2 roadmap is complete except the two items dropped on
the evidence: the crowd-out index (measures institutional fragmentation) and the NFIRS EMS split (high
effort, ends with NFIRS in 2026).

## Suggested order

1. 1A employment join and 1B CPI deflation (both self-contained, both strengthen the existing page).
2. 4A peer engine with 1B(ii) RPP tiers.
3. 3A crowd-out index and 3C county allocation, shipped with their institutional flags.
4. 2A crime overlay.
5. 2B NFIRS, if the EMS story is wanted, knowing it ends at 2024.
6. 4B national annotations; 4C as a print view or static export.
