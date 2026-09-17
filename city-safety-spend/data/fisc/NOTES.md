# FiSC (Lincoln Institute Fiscally Standardized Cities) — cross-validation source

Retrieved 2026-09-14. No account, login, or registration required at any point.

## What this source is

FiSC takes the central city's **own municipal government record** from the Census Bureau's
Annual Survey of State & Local Government Finances individual unit files, and adds an
**allocated share** of the overlying county, independent school district(s), and special
districts that serve the city's residents. The point is to make Houston (thin municipality,
fat county/school overlay) comparable to Nashville (consolidated, dependent schools).

That gives us exactly the two views this repo wants:

| view in our CSV | FiSC column suffix | meaning |
|---|---|---|
| `city_only` | `_city` | the central city municipal government alone, **no allocation applied** |
| `fisc`      | *(none)* | city + allocated county + school districts + special districts |

FiSC also publishes `_cnty`, `_schl`, `_spec` separately; we did not extract those.

## Access method

Two independent channels were used, and they agree (see Validation).

1. **Complete Dataset workbook** — a plain public link, no gate:
   `https://www.lincolninst.edu/app/uploads/2026/01/FiSC-Full-Dataset-2023-Update.xlsx`
   (30 MB, sheets `About` / `Data` / `Variable List`; 10,246 city-year rows x 548 columns
   = 107 fiscal variables x 5 levels of government, 1977-2023.)
   Saved to `raw/FiSC-Full-Dataset-2023-Update.xlsx`.

2. **The interactive "Create a Table" tool** at
   `https://app.lincolninst.edu/research-data/data-toolkits/fiscally-standardized-cities/search-database`
   (iframed into `https://www.lincolninst.edu/data/fiscally-standardized-cities/access-fisc-database/`).
   Driven in a browser to select all 212 cities, years 2012/2017/2022/2023, the four
   spending variables + City Population, display = **Total dollars / Nominal**, level of
   government = **FiSC + City**.

   The tool's own table renderer posts a URL-encoded form to a public JSON endpoint,
   `POST https://app.lincolninst.edu/fisc/api/results` (see its `js/fisc.js`, which does
   `$.ajax({type:'POST', url:'/fisc/api/results', data:$form.serialize()})`). The endpoint
   needs **no session, cookie, CSRF token, or `form_build_id`**, so the four year-tables
   were pulled reproducibly with `curl`. Saved to `raw/fisc_api_results_{2012,2017,2022,2023}.json`.

   **The numbers in `fisc_police_fire.csv` come from channel 2** — those are the
   publisher's own nominal-dollar figures, requiring no arithmetic on our side.
   The `population` column comes from channel 1 (see Populations below).

3. `raw/user_guide_for_fisc_database.pdf` — the 6-page user guide, for the definitions below.

The CMU mirror named in the brief (`cmustatistics.github.io/.../standard-cities.html`,
`fisc_full_dataset_2020_update.csv.gz`) was **not** used: it stops at 2020 (no 2022/2023)
and is a stale vintage of the same workbook. The primary source is better in every respect.

## Coverage

- **212 cities**, all 50 states + DC. This is FiSC's whole universe — 150 "Core FiSCs"
  (two largest cities in each state, plus all cities over ~150k) and 95 "Legacy Cities"
  (>=20% decline from peak population), 33 of which are in both samples.
- **Years 2012, 2017, 2022, 2023.** 2022 and 2023 are both present; 2023 is the newest
  year FiSC publishes. The full source covers 1977-2023 annually if more years are wanted.
- **1,696 rows** = 212 cities x 4 years x 2 views. No missing values.
- FiSC's 212 cities are *not* the same universe as this repo's "population >= 100,000".
  FiSC includes small legacy cities (Gadsden AL, Rutland VT, ~15k) and omits many
  100k+ suburbs. Treat FiSC as a spot-check set, not a population frame.

## How FiSC defines the variables (and where it departs from Census)

The user guide's rule is: *FiSC follows the Census Bureau's "Methodology for Summary
Tabulations" for every variable not explicitly listed as different.*

- **Police Protection** and **Fire Protection** are **not** in the list of departures,
  so they are the standard Census function tabulation — direct expenditure for the
  function: current operations + construction + other capital outlay, i.e. **E62/F62/G62**
  for police and **E24/F24/G24** for fire, matching this repo's item codes. (Corroborating:
  the guide's "Other General Capital Outlay" tabulation explicitly lists F62/G62, and
  FiSC's by-function total reconciles only if the functional lines carry E+F+G.)
  Police excludes corrections and inspection/regulation, which FiSC lists separately.

- **Total Expenditures** — the one documented departure that bites us.
  *Census:* includes employee retirement trust expenditure.
  *FiSC:* **excludes X11 and X12** (employee retirement benefits and withdrawals);
  otherwise identical.
  So `total_expenditure_usd` here is **not** this repo's `total_expenditure`
  (which per `docs/CONVENTIONS.md` includes insurance-trust benefits). For cities with
  large municipally-administered pension systems the FiSC figure will be materially lower.

- **General Expenditures** — an *undocumented* departure, confirmed empirically.
  FiSC's "General Expenditures" is exactly the sum of its eight functional children
  (Education, Health & Welfare, Transportation, Public Safety, Environment & Housing,
  Governmental Administration, Interest on General Debt, Miscellaneous) — verified to
  hold for **all 1,696 city-year-level records, zero exceptions**. That makes it
  **direct general expenditure**, i.e. Census general expenditure **minus
  intergovernmental expenditure**. This repo's `general_expenditure` (total minus utility,
  liquor, insurance trust) *includes* intergovernmental expenditure, so the two differ for
  any city that pays money to other governments. It is not a rounding-level gap:
  New York City 2022 city-level intergovernmental expenditure is $1,025/capita (~$8.7bn),
  Boston $534/capita, Sacramento $447/capita, Flint $408/capita. 34 of 212 cities show a
  nonzero gap in 2022; the other 178 are clean.

  Other identities verified across all 1,696 records:
  - `Total Expenditures == Intergovernmental + Direct` — holds exactly, 0 exceptions.
  - `Public Safety == Police + Fire + Corrections + Inspection` — holds exactly, 0 exceptions.
  - `Total == General + Utility + Liquor + Intergovernmental` — holds for 1,677 of 1,696.
    The 19 exceptions are DC (all 4 years, both views — DC behaves like a state and
    carries other insurance-trust expenditure), Garland TX at the FiSC level only, and
    four small 2023 records with small negative residuals (Indianapolis, Hamtramck MI,
    McKeesport PA, Wilkes-Barre PA).

- FiSC also re-tabulates a number of **revenue** lines differently from Census
  (income taxes, license taxes, transfer taxes, other charges, fines & forfeits...).
  Irrelevant to us; documented on p.2 of the user guide if ever needed.

## Is the `city_only` view exactly the Census municipal record?

**Conceptually yes; numerically not for the denominators.**

- The `_city` columns carry the central city municipality's own individual-unit record.
  The FiSC allocation machinery (GIS-based apportionment of overlying governments) touches
  only `_cnty` / `_schl` / `_spec`. Philadelphia is a clean demonstration: it is a
  consolidated city-county, has no overlying county, and its `city_only` police and fire
  are **identical to the dollar** to its `fisc` police and fire.
- **For police and fire, `city_only` is the Census municipal record — verified.**
  Joined against this repo's own Census IUF output
  (`data/census_out/city_police_fire_all_years.csv`, as of commit `bea2105`) on
  city + state + fiscal year; 504 of 848 `city_only` rows matched (the rest are FiSC
  legacy cities below this repo's 100k floor, plus consolidated city-counties whose
  Census name differs — Denver, Baton Rouge, Columbus GA, Nashville-Davidson etc.):

  | measure | FiSC `city_only` vs Census | median relative diff |
  |---|---|---|
  | police | **99.0%** agree within 0.5% (499/504) | 6.2e-06 |
  | fire | **99.4%** agree within 0.5% (500/503) | 1.0e-05 |
  | `general_expenditure_usd` vs Census **general** | 63.3% | 1.0e-03 |
  | `general_expenditure_usd` vs Census **direct general** | **91.7%** | **1.1e-06** |
  | `total_expenditure_usd` vs Census total | 63.9% | 6.3e-04 |

  The police/fire median differences are at the level of Census's own $1,000 rounding
  (Census publishes thousands; FiSC publishes exact dollars), i.e. the same number.
  The general-expenditure rows are the empirical proof of the point above: FiSC's
  "General Expenditures" tracks Census **direct** general expenditure (median diff
  1.1e-06, essentially exact) and not Census general expenditure. `total` behaves as
  the X11/X12 exclusion predicts.

  **All eight police/fire disagreements above 0.5%**, worth resolving in `validation/`:

  | city | year | measure | FiSC city_only | Census | gap |
  |---|---|---|---|---|---|
  | Las Vegas NV | 2023 | police | 1,865,073 | 16,347,000 | 88.6% |
  | Fargo ND | 2012 | police | 14,044,602 | 28,197,000 | 50.2% |
  | St. Louis MO | 2012 | police | 140,815,701 | 251,236,000 | 44.0% |
  | Omaha NE | 2012 | police | 112,054,516 | 90,124,000 | 24.3% |
  | Seattle WA | 2023 | police | 275,595,755 | 319,496,000 | 13.7% |
  | Milwaukee WI | 2012 | fire | 91,158,047 | 112,584,000 | 19.0% |
  | Seattle WA | 2023 | fire | 245,635,284 | 266,789,000 | 7.9% |
  | St. Louis MO | 2012 | fire | 69,886,774 | 64,827,000 | 7.8% |

  Four of the eight are 2012, which is the year the Census-side pipeline already flags as
  tracing to a Willamette build defect — so those are likely the Census side's problem,
  not FiSC's. Las Vegas is a genuine structural case (LVMPD is a merged city-county
  department; the city's own police line is small and unstable) and both figures look
  suspect. Seattle 2023 and Omaha 2012 are unexplained and worth a source-document check.
- **For the denominators it is definitely not the Census municipal record**: FiSC's
  `total` drops X11/X12 and FiSC's `general` drops intergovernmental expenditure
  (see above). Compare denominators only after adjusting, or compare shares only against
  a denominator you have reconstructed on FiSC's definition.
- Separate structural caveat, same as this repo's `city_flags.csv` concern: for
  **consolidated city-counties** (34 of them — Philadelphia, Nashville, Indianapolis,
  Louisville, Anchorage...) and cities with **dependent school systems** (New York,
  Boston, Baltimore...), the Census *municipal* record already contains county and/or
  school functions. "City only" there is not a plain municipality. FiSC carries the flags
  `consolidated_govt` and `relationship_city_school` (values 1-5) in the raw workbook —
  they are not in our normalized CSV but are worth joining in before any share comparison.
- FiSC applies **its own annual population estimates** (Census intercensal estimates for
  places 2000+, modelled before that), not necessarily the population attached to the
  Census finance files.

## Units and conversion

The workbook stores everything as **real per-capita dollars**, and its `About` sheet says
"($2022)". **That text is stale** — the tool's own control reads "Real (**2023** Dollars)"
and the workbook's `cpi` column is exactly `1` for 2023 (2022 = 1.041165). Anyone
converting from the workbook must deflate on a 2023 base, not 2022.

Our CSV avoids the issue: it carries the tool's **nominal total dollars**, unrounded,
straight from the API. **Whole dollars, not thousands.**

## Validation

Every value in `fisc_police_fire.csv` was cross-checked against the *other* channel — the
workbook's real per-capita figures converted by `nominal_total = real_per_capita / cpi * population`,
which is the conversion the `About` sheet prescribes.

- **6,772 values compared** (212 cities x 4 years x 2 views x 4 measures).
- **Maximum relative difference: 5.9e-06** (0.0006%). Zero values differed by more
  than 1e-5.
- The residual is rounding: the workbook publishes per-capita figures to 2 decimals,
  so a city the size of Philadelphia carries a few thousand dollars of slack on a
  ten-billion-dollar line. The tool computes from unrounded internals, which is why the
  tool's figures were chosen for the deliverable.
- Spot check against the tool's rendered HTML table (not just its JSON) for Houston,
  Dallas, Philadelphia, Nashville 2022, both views, all four measures: identical.
- `city_only <= fisc` holds for every city, year, and measure. No violations.

### Populations

`population` is taken from the **workbook**, not the tool. The tool rounds City Population
to 6 significant figures for display (Chicago 2022: 2,706,320 vs the true 2,706,324);
30 of 848 city-years were affected, all by <= 5 people. The workbook value is exact.
The two views share a population by construction — FiSC allocates overlying government
finances to the city's resident population, so the denominator is the city's population
in both views.

## Friction and things to be careful about

- **Four published zeros that are almost certainly bad source data**, carried through
  faithfully rather than blanked. Both channels agree on them, so this is FiSC's data,
  not our parsing:

  | city | year | symptom |
  |---|---|---|
  | Syracuse NY | 2022 | city police = 0, city **and** FiSC fire = 0. (2023: police $53.5m, fire $48.6m) |
  | Toledo OH | 2022 | city police = 0, city and FiSC fire = 0 |
  | Toledo OH | 2023 | same again — two consecutive years |
  | Harrisburg PA | 2023 | city police = 0, city and FiSC fire = 0. (2022: police $23.1m, fire $12.1m) |

  In each case the FiSC-level police figure survives but is tiny ($13.1m for Syracuse
  2022, $12.5m for Toledo) — that is the *allocated county share only*, with the city's
  own police record missing. Harrisburg's 2023 city general expenditure also collapses
  from $1,709/capita to $83/capita, so its whole 2023 municipal record looks broken.
  **Do not treat these as real declines, and exclude them from any share calculation.**

- **The Excel export button does not work in an automated browser.** "Export to CSV"
  opens the file in a new tab, which a controlled browser blocks. The
  `/fisc/api/results` endpoint above is the reliable path and returns the same table.

- The wizard is a six-panel horizontal slider. Panels that are off-screen are still in the
  DOM but at large negative x coordinates, so coordinate clicks silently miss. Changing
  the city-group radio (Core / Legacy / All) **clears the city selection** but preserves
  years, variables, and display options.

- The site fired its EU cookie-consent endpoint (`/eu-cookie-compliance/store_consent/banner`)
  during the session. This was incidental to clicking through the wizard, not a deliberate
  acceptance of terms; no account was created and nothing was submitted on the user's behalf.

- The tool's row labels are **"Police Spending" / "Fire Spending"**, but the underlying
  variables are `police` / `fire` and the hierarchy label is "Police Protection" /
  "Fire Protection". Same thing.

- Aggregate pseudo-cities ("Average for All Cities", "Median for Core FiSCs", etc.) appear
  as rows in the workbook and as selectable columns in the tool. They are **excluded**
  from our CSV; 218 workbook names = 212 real cities + 6 aggregates.

## Column mapping

| our column | FiSC source |
|---|---|
| `city`, `state` | split from FiSC's `city_name` (`"TX: Houston"`) |
| `fiscal_year` | FiSC `year` |
| `view` | `city_only` -> `_city` columns; `fisc` -> unsuffixed |
| `population` | workbook `city_population` (exact) |
| `police_usd` | `police` / `police_city` — Census E62+F62+G62 |
| `fire_usd` | `fire` / `fire_city` — Census E24+F24+G24 |
| `total_expenditure_usd` | `spending_total` / `spending_total_city` — **Census total less X11/X12** |
| `general_expenditure_usd` | `spending_general` / `spending_general_city` — **direct general, excludes intergovernmental** |
| `source_url` | the Create-a-Table tool page |
| `retrieved` | 2026-09-14 |

Suggested citation (from the workbook's `About` sheet):
Lincoln Institute of Land Policy, *Fiscally Standardized Cities database*,
https://www.lincolninst.edu/data/fiscally-standardized-cities/

Methodology working paper (allocation method, population estimates):
https://www.lincolninst.edu/data/fiscally-standardized-cities/methodology-fiscs/
