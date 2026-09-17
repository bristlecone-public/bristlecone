# Vera Institute — *What Policing Costs: A Look at Spending in America's Biggest Cities*

Cross-validation source. **FY2020 adopted budgets, 72 cities.**

- Landing page: https://www.vera.org/publications/what-policing-costs-in-americas-biggest-cities
- Methodology PDF: https://vera-institute.files.svdcdn.com/production/inline-downloads/policing-budgets-methodology.pdf?dm=1646935288
  (*Local Budgets and Police Expenditure in the Biggest U.S. Cities: Methodology and Data Sources*, June 2020)
- Retrieved: **2026-09-14**

---

## 1. What was obtained, and how

Vera publishes **no** CSV/XLSX download button, no data appendix, and no GitHub repo. The
figures are served to the page's JavaScript. All three files in `raw/` were pulled directly
from the URLs the live page requests:

| `raw/` file | Source URL | What it is |
|---|---|---|
| `City-PD_HoverStats-12-2-2020-2.csv` | `https://vera-institute.files.svdcdn.com/production/data/datasets/City-PD_HoverStats-12-2-2020-2.csv?dm=1646885897` | The sortable-table / map dataset. 72 rows, machine-readable. **This is the authoritative headline file.** |
| `City-PD_HoverOverStats-12-2-2020.csv` | `…/City-PD_HoverOverStats-12-2-2020.csv?dm=1646885896` | Byte-for-byte the same 72 rows with the money pre-formatted (`"$211,084,000.00"`, `32%`). Kept for provenance only; do not parse. |
| `ConsolidatedExp_72PoliceDepartments-12-2-2020.csv` | `https://www.vera.org/police-budgets/static/media/ConsolidatedExp_72PoliceDepartments%2012-2-2020.111e9b81.csv` | The **line-item** file behind the per-city "budget calculator" React app (`/police-budgets/`). 2,289 rows × 72 cities: `city, stateAbb, year, department, expensecat, subdep, expensedescrip, personneltype, group, total`. Found via `read_network_requests` on a city page; it is not linked from anywhere. |
| `policing-budgets-methodology.pdf` | see above | Methodology + an appendix (pp. 4–6) listing **the exact budget-book / open-data URL Vera used for every one of the 72 cities**. Use this for spot-checks. |

**Wayback Machine was not consulted** — archive.org was returning
`Internet Archive: Temporarily Offline` for both the CDX API and playback during this
session. It was not needed: the live page still serves the complete data.

### Internal consistency check (passed)
Summing `total` over **all** rows of `ConsolidatedExp_…csv` reproduces
`Overall policing budget` in the headline file **exactly for 71 of 72 cities**. The single
exception is Arlington, TX, off by **$3** (117,847,635 vs 117,847,632) — a rounding artifact.

---

## 2. The denominator — read this before using `police_pct`

**Vera never defines it.** This is the single biggest caveat in this source.

What Vera actually publishes:

- The column is labelled, verbatim, **"Percent of city funds spent on policing"**. The
  phrase *"city funds"* is the whole of their framing. `budget_type` in
  `vera_fy2020.csv` therefore reads `city funds` for every row — that is Vera's exact
  language, not a normalization of ours.
- The methodology PDF says the volunteer data-entry template's first tab was
  *"a summary of the overall city budget"*. It never says "general fund", never says
  "all funds", and never states which total became the denominator for any city.
- The per-city pages describe the **numerator**, not the denominator:
  > "The numbers included below represent monies coming from the city's general fund and
  > other local, federal, and state funding sources."

  and, in the standing explainer text:
  > "The general fund typically represents unrestricted revenues that can be used for any
  > legal purpose. Spending on policing overwhelmingly comes from the general fund."

  So the *police* figure is general fund **plus** whatever external funding the city
  reported on its own line. The methodology adds that Vera
  "flags the small number of cities that only report general fund spending on policing" —
  **that flag is not present in any published file.** It exists only in Vera's internal
  workbook. There is no per-city exceptions list to transcribe.

**Consequence for this repo:** `police_pct` is *not* a clean
`police / general_expenditure` or `police / general_fund_budget` ratio in the sense
CONVENTIONS requires. Treat Vera's percent as an editorial statistic, **not** as a
denominator you can align with Census IUF aggregates.

### `city_budget_usd` is derived, not published

Vera publishes no city-budget total anywhere. `city_budget_usd` =
`police_budget_usd / police_pct`, and **`police_pct` is published rounded to the whole
percent** (the raw CSV carries `0.36`, `0.32`, …). The implied denominator therefore
carries a real band: at 36%, the true denominator lies anywhere in
`police / 0.365 … police / 0.355`, i.e. **roughly ±1.4%**; the band widens sharply at low
percentages (Washington DC at 5% ⇒ ±10%). The `city_budget_usd_basis` column in the CSV
restates this on every row.

**Do not cite `city_budget_usd` as a Vera figure.** It is an inversion of a rounded ratio.
Use it to *characterize* the denominator, not to publish it.

### What the implied denominators appear to be
Inverting the ratio lands, for most large cities, at a total far below the city's all-funds
budget and in the neighbourhood of an adopted **general fund** — consistent with the
methodology's framing. But it is not uniform, and at least two cities cannot be reconciled
to any single named published total:

- **New York, NY** — `police_pct` = 8% against a headline police figure of $11.04B implies
  a denominator of **~$138B**, which is far larger than NYC's FY2020 adopted expense
  budget. Vera's NYC source was `checkbooknyc.com/data-feeds`, a transaction feed, not a
  budget book. Treat NYC's percent as unusable.
- **Fort Worth, TX** — implied denominator ~$1.01B sits between Fort Worth's adopted
  general fund and its all-funds total, matching neither. Its staffing ratio is also a
  clear outlier (see §4).

The implied denominator for every city is shipped in the CSV so this can be re-checked
city by city against the budget documents listed in the methodology appendix.

---

## 3. Fiscal year

**FY2020 adopted budget for 71 of 72 cities.** One documented exception, stated in the
methodology and independently confirmed in the line-item file (it is the only city whose
`year` field is `2019`):

- **Newark, NJ — FY2019 adopted budget.** Vera's note: "the FY2020 budget was not readily
  available online."

`fiscal_year` in `vera_fy2020.csv` is `2020` for all rows except Newark (`2019`).

Vera notes FY2020 "spans a 12-month period that often begins in July 2019" — the fiscal
calendar is *not* aligned across the 72 cities, and Vera made no attempt to align it.

---

## 4. Caveats Vera published, plus ones found in the data

### Published by Vera
1. **Manually collected.** A one-week sprint by Goldman Sachs volunteers reading PDF budget
   books. Vera states plainly: *"Given the manual nature of the data collection and the
   thousands of rows of data collected and entered, some errors likely remain."*
2. **Coverage is top-50-by-population plus the largest city in each state.**
3. **Oakland, CA was dropped** — "lack of 2020 department-level budget data available."
   It is absent from all files, which is why the count is 72 and not 73.
4. **Detail varies wildly.** Three cities have only two line items (police personnel vs.
   everything else): **Arlington TX, Newark NJ, Tampa FL**. **Virginia Beach VA** has
   three. At the other end Austin has 462 rows. Anything below the department topline is
   not comparable across cities.
5. **Source type varies.** Budget book for every city *except* **Austin, Chicago, Dallas,
   Nashville**, where Vera used the city open-data portal instead.
6. **Employee ratio definition.** "The number of staff employed by the city's police
   department … full time, part time, civilian, or sworn staff. It does not include staff
   from other police agencies (Police Boards, Police Accountability Offices, etc.)",
   drawn from the FY2020 adopted budget book.
7. **No imputation.** "We made no assumptions and filled in only reported adopted numbers."
8. The historical trend charts on the city pages are **BJS data 1982–2016**, a different
   source with different coverage — not part of this capture.

### Found in the data during capture
9. **The headline police figure is not "the police department" in 24 of 72 cities.**
   `Overall policing budget` is the sum of *every* police-adjacent agency Vera coded, which
   in some cities includes pension contributions, debt service, judgments and claims, and
   sheriff/harbor/marshal agencies. Where this matters most:

   | City | Non-`Police Department` share of headline | What it is |
   |---|---|---|
   | Jacksonville, FL | **100%** | consolidated city-county: `Office of the Sheriff` only, no city PD line |
   | New York, NY | **49.3%** | Police Pensions $2.71B + "Police Miscellaneous Budget" $2.29B + Judgement & Claims $230M + Debt Service $211M |
   | Providence, RI | 34.4% | Police Pensions |
   | Newark, NJ | 25.6% | NJ Police & Firemen's Retirement System |
   | Sioux Falls, SD | 24.3% | Police Pensions |
   | St. Louis, MO | 20.8% | pensions / sheriff |
   | Phoenix, AZ | 19.3% | Police Pensions $175M |
   | Burlington, VT | 17.9% | Police Pensions |
   | Washington, DC | 14.6% | Fire & Police Pensions $93M + Office of Police Complaints |
   | Indianapolis, IN | 10.5% | Police Pensions |
   | Las Vegas NV 9.7% · Seattle WA 7.1% · Denver CO 7.9% · New Orleans LA 6.2% | | |

   The remaining 10 affected cities are under 2%. **This is load-bearing for comparison
   against Census item code 62**, which is scoped differently (and excludes insurance-trust
   benefit payments entirely). `vera_fy2020.csv` therefore ships
   `police_dept_only_usd` and `other_police_agency_usd` so the headline can be
   decomposed — use `police_dept_only_usd` for any Census comparison.

10. **`police_employees` is derived, not published.** Vera publishes only a rounded ratio
    (`"1 : 360"`). The CSV back-solves:
    `population = police_budget_usd / police_per_capita_usd`, then
    `employees = population / residents_per_employee`. Both inputs are rounded (per-capita
    to the dollar, ratio to the integer), so expect roughly **±0.5%**. The
    `police_employees_basis` column restates this per row. Cross-checks on large cities
    land within ~1% of known department headcounts.

11. **Fort Worth, TX's staffing ratio looks wrong.** `1 : 203` against a 72-city median of
    `1 : 345` implies ~5,853 police employees for a city of ~1.19M — roughly triple what a
    department that size carries, and the most extreme value in the file by a wide margin.
    Almost certainly a city-wide headcount entered in a department-headcount field. Do not
    use Fort Worth's ratio or its derived `police_employees`.

12. **The on-page calculator mis-renders one Houston line.** The React widget shows
    "Materials and Services = $3" and a total of $899,579,056; the underlying CSV has
    $300,000 and $899,879,053. The CSV is correct and is what this capture uses. Mentioned
    only so a future reader comparing against the live page isn't misled.

13. **Duplicate city names.** Charleston appears twice (SC and WV) and Portland twice
    (ME and OR). Key on `(city, state)`, never on `city`.

---

## 5. Mapping to `docs/CONVENTIONS.md`

CONVENTIONS specifies `city,state,fiscal_year,police_usd,fire_usd,denominator_usd,denominator_type,source_url,retrieved`.
`vera_fy2020.csv` uses the task-specified schema, which maps 1:1 with one gap:

| CONVENTIONS | `vera_fy2020.csv` |
|---|---|
| `police_usd` | `police_budget_usd` (or `police_dept_only_usd` for a Census-comparable scope) |
| `fire_usd` | **not available** — Vera collected police spending only; fire appears nowhere in any file |
| `denominator_usd` | `city_budget_usd` (**derived**, see §2) |
| `denominator_type` | `budget_type` = `city funds` (Vera's verbatim label; undefined by them) |

Only one CSV is written to this folder so a `data/vera/*.csv` glob cannot double-count.

## 6. Column reference for `vera_fy2020.csv`

| Column | Published by Vera? |
|---|---|
| `city`, `state` | yes |
| `fiscal_year` | yes (methodology + `year` field) |
| `police_budget_usd` | **yes, exact** — headline "Overall policing budget" |
| `city_budget_usd` | **no — derived**, see §2 |
| `budget_type` | yes, verbatim label (`city funds`) |
| `police_pct` | **yes**, as published (rounded to whole percent) |
| `police_per_capita_usd` | **yes**, as published (rounded to the dollar) |
| `police_employees` | **no — derived**, see §4.10 |
| `source_url` | Vera's per-city page |
| `retrieved` | 2026-09-14 |
| `police_dept_only_usd` | derived: sum of `department == "Police Department"` rows |
| `other_police_agency_usd` | derived: sum of all other departments |
| `police_employee_resident_ratio` | **yes**, as published (`"1 : N"`) |
| `city_budget_usd_basis`, `police_employees_basis` | provenance strings, constant per column |
