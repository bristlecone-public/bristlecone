# BJS as an independent check on municipal police spending

Retrieved 2026-09-14. Everything in `raw/` was downloaded from `bjs.ojp.gov`
without a login and without creating any account.

## Short version

- **Police: yes, but only through FY2000.** BJS published per-agency operating
  expenditure for every law enforcement agency with 100+ officers in three
  volumes (LEMAS 1993, 1997, 2000), and for the 62 cities of 250,000+ in a
  fourth report covering FY1990. Those are extracted into
  `bjs_police_budgets.csv` — 609 agency-years, 229 cities.
- **Police, FY2003 onward: behind a login.** BJS still collects an operating
  budget in LEMAS (2003, 2007, 2013, 2016, 2020) and in the CSLLEA (2008, 2018,
  2022), but it stopped publishing per-agency volumes after the 2000 wave. The
  agency-level microdata lives on ICPSR/NACJD and the download requires a free
  ICPSR account, which we did not create. The BJS *reports* for those waves
  publish budget only as aggregates by population-size class.
- **Fire: nothing usable exists.** No national dataset records individual fire
  department budgets. Details in the "Fire departments" section below.
- **"Independent" needs a caveat.** LEMAS is a BJS collection, but the 1993,
  1997 and 2000 waves were *administered by the U.S. Census Bureau* on BJS's
  behalf (Form CJ-44). It is a different instrument, a different respondent and
  a different set of definitions from the Annual Survey of State & Local
  Government Finances — but it is not a different agency. See "How independent
  is this, really?".

## Files

| file | what |
|---|---|
| `bjs_police_budgets.csv` | normalized output, municipal PDs serving 100k+ cities |
| `extract_bjs_lemas.py` | reproduces the CSV from `raw/` (needs `pdfplumber`) |
| `raw/bjs_lemas93.pdf` | LEMAS 1993 individual-agency volume, NCJ-148825 |
| `raw/bjs_lemas97.pdf` | LEMAS 1997 individual-agency volume, NCJ 171681 |
| `raw/bjs_lemas99.pdf` | LEMAS 1999 individual-agency volume — **no expenditure tables** |
| `raw/bjs_lemas00.pdf` | LEMAS 2000 individual-agency volume, NCJ 203350 |
| `raw/bjs_lema002a.pdf` | narrative-only companion to the 2000 volume |
| `raw/bjs_police_departments_large_cities_1990-2000.pdf` | NCJ 175703, appendix table C = the FY1990 wave |
| `raw/bjs_local_police_departments_2003.pdf` | LPD 2003, NCJ 210118 — aggregate budget tables only |
| `raw/bjs_local_police_departments_2013_ppp.pdf` | LPD 2013 — aggregate budget tables only |
| `raw/bjs_local_police_departments_2016_personnel.pdf` | LPD 2016 — **no** budget tables at all |
| `raw/csllea2018_statistical_tables_report.pdf` + `raw/csllea2018_tables/` | CSLLEA 2018, NCJ 302187, all 41 published tables — **none of them is a budget table** |

`bjs_police_budgets.csv` columns: `agency_name, city, state, fiscal_year,
operating_budget_usd, sworn_officers, source, source_url, retrieved`.
`operating_budget_usd` is **nominal dollars, not thousands** (unlike the Census
IUF). `sworn_officers` is full-time sworn personnel from the same volume's
personnel table, except for FY1990 where it is derived (see below).

Coverage: 62 agencies FY1990, 148 FY1993, 175 FY1997, 224 FY2000. 46 cities
appear in all four waves; 146 appear in at least three.

## What exists, wave by wave

### Published per-agency (obtained, no login)

| wave | source | universe printed | table |
|---|---|---|---|
| FY1990 | *Police Departments in Large Cities, 1990-2000*, NCJ 175703 | 62 cities of 250,000+ in both the 1990 and 2000 census | appendix table C |
| FY1993 | *LEMAS 1993: Data for Individual State and Local Agencies with 100 or More Officers*, NCJ-148825 | all local agencies with 100+ sworn officers | table 7a |
| FY1997 | same series, NCJ 171681 | same | table 6a |
| FY2000 | same series, NCJ 203350 | same | table 5a |

The series appears to stop there. There is no 2003, 2007, 2013, 2016 or 2020
equivalent that we could find: `lemas90.pdf`, `lemas03.pdf`, `lemas07.pdf`,
`lemas13.pdf` and `lemas16.pdf` all 404 on bjs.ojp.gov while `lemas93/97/99/00`
resolve, and no later individual-agency volume turns up in search. The 2000
volume (published March 2004) is the last one we located; that is an absence of
evidence, not a BJS statement. The 1999 volume exists but its
sections are personnel / community policing / operations / computers / policies —
the 1999 LEMAS did not carry the financial section.

### Collected but behind an ICPSR login

- **LEMAS 2016** — ICPSR 37323. **LEMAS 2020** — ICPSR 38651.
- **CSLLEA 2018** — ICPSR 38771. (CSLLEA 2008 = ICPSR 27681; CSLLEA 2022 in the
  field as of the 2022 OMB clearance.)

All are flagged "public-use ... available for access by the general public.
Access does not require affiliation with an ICPSR member institution" — but
"public-use" here means *no institutional affiliation required*, not *no login
required*. The actual file-delivery endpoint
(`/cgi-bin/bob/zipcart2?path=NACJD&study=38651&...`) 302s to
`https://www.icpsr.umich.edu/rpxlogin`. Creating an account was out of scope, so
these were not retrieved. A future pass with an ICPSR account would get:

- LEMAS 2020: overall operating budget per agency, all 1,079 agencies with 100+
  FTE sworn included with certainty — i.e. effectively every 100k+ city.
- CSLLEA 2018: total operating budget for ~18,000 agencies, a full census rather
  than a sample.

Worth knowing before trusting LEMAS 2020 budgets: BJS edited them. Agencies
whose budget-to-FTE-sworn ratio fell below $35,000 or above $400,000 per officer
were reviewed (299 agencies), and the budget figure for **140** of them was
replaced using "agency and government budgets reported on public websites and
prior survey data (from the 2016 LEMAS survey and 2018 CSLLEA)". So a nontrivial
slice of LEMAS 2020 is not an independent observation at all — it is BJS reading
the city's own budget document, which is the same thing our `spotcheck/` lane
does. That edit is documented on the ICPSR 38651 study page.

### Collected but never published at agency level

The CSLLEA 2018 questionnaire asks for total operating budget, and the BJS
announcement describes the collection as covering "government authority, budget,
functions, and personnel". But the published *Statistical Tables* release
(NCJ 302187) contains 20 tables, 5 figures and 16 appendix tables and **not one
of them reports budget** — they are all personnel, agency counts and functions.
Verified by grepping all 41 CSVs in `raw/csllea2018_tables/`. Same for
*Local Police Departments, 2016: Personnel* — no budget content at all.

The 2003 and 2013 LEMAS reports do publish budget, but only collapsed into
population-size bands (`Local Police Departments, 2013` appendix table 5:
1,000,000+, 500,000-999,999, ... ). Useful as a national sanity check on our
Census aggregates, useless for per-city validation.

## How BJS defines "operating budget"

This is the important part and BJS is unusually explicit about it. Verbatim from
the FY1997 volume's table note (the FY1993 and FY2000 notes are the same except
for dates):

> Data are for fiscal year ending June 30, 1997 or the most recent fiscal year
> completed prior to that date. Operating expenditure data include gross salaries
> and wages, employer contributions to employee benefits, jail expenditures (if
> applicable), and other operating expenditures such as the purchase of supplies,
> food, and contractual services. Capital expenditures such as equipment purchases
> and construction costs are not included. ... In some cases, data are estimates
> provided by agency.

The FY2000 note is shorter: "Budget data are for the calendar or fiscal year that
included June 30, 2000. Capital expenditures such as equipment purchases and
construction costs are not included."

The underlying questionnaire is Census Form CJ-44, reprinted in full in the 1997
volume. Section V — Financial Information asks:

> 1. Enter your agency's expenditures for the most recently completed fiscal
> year. If data are not available, provide estimates and mark with an asterisk(*).
> **Include expenditures of jails administered by your agency.**
> a. Gross salaries and wages, **including employer contributions to employee
> benefits**. If employer contributions to employee benefits are NOT included in
> the amount above, estimate the percentage of gross salaries necessary to account
> for these costs (e.g., 15%, 20%).
> b. Other operating expenditures (e.g., purchase of supplies, food, and
> contractual services, etc.)
> c. Equipment (e.g., purchase of cars, radios, computers, etc., with a life
> expectancy of 5 years or more)

Published operating expenditure = **1a + 1b**. Item 1c (equipment) is collected
separately and is *not* in the published figure.

So, answering the three questions directly:

- **Pensions / fringe:** **included.** Employer contributions to employee
  benefits are explicitly in item 1a, and where an agency could not separate
  them the form asks for a percentage estimate so BJS can gross them up.
- **Capital:** **excluded.** Both construction and equipment with a 5-year life.
- **Overtime:** **included** — it is inside gross salaries and wages. The 1993
  and 1997 volumes additionally print total overtime pay as its own column
  (table 7a / 6a), so for those two waves the overtime component of the figure is
  separately visible in `raw/`.
- **Jails:** **included** if the agency runs them. Matters little for municipal
  PDs, a lot for sheriffs (which this CSV excludes).

## Comparability with Census item code 62

Census `E62` (Police Protection — Current Operations) is defined in the 2006
*Government Finance and Employment Classification Manual* as "Direct expenditure
for compensation of own officers and employees and for supplies, materials, and
contractual services except any amounts for capital outlay". That is the same
shape as BJS 1a+1b, and both exclude capital (which in Census is `F62`/`G62`).
Close — but **not the same number**, for four specific reasons:

1. **Employer pension contributions (the big one).** BJS includes them. Census
   does not, when the city runs its own police pension fund: the manual classes
   "Contributions to a government's own system" as **an intragovernmental
   transfer**, excluded from expenditure entirely, with the pension fund's own
   benefit payments surfacing separately as insurance-trust expenditure. But
   "Contributions or other payments to systems administered by another
   government" *are* "classified as current operation expenditure". So the gap
   between BJS and `E62` is **city-specific**: it should be large for cities with
   their own police pension system (Houston, Dallas, Chicago, Philadelphia,
   Boston, Baltimore, …) and near zero for cities that participate in a
   state-administered system. This is the single most likely explanation for any
   systematic BJS-over-Census gap, and it is testable — the gap should correlate
   with whether the city runs its own fund.
2. **Jails.** BJS includes jail expenditures of jails the agency runs. Census has
   sent jails holding people beyond arraignment to Corrections (`*04`/`*05`)
   since the 1988 manual, and explicitly excludes "police jails that hold people
   beyond arraignment" from `*62`. Municipal lockups holding people only until
   arraignment stay in `62`, so for city PDs this is a small effect — but not
   zero.
3. **Agency vs function.** BJS's unit is *the police department*. Census's unit
   is *the police protection function of the city government*, which sweeps in
   police-protection spending that sits outside the department's own budget
   (crime labs, coroners/medical examiners, criminal justice planning) and
   excludes departmental activity that Census codes elsewhere (traffic
   engineering if not police-run; civil/bailiff work; special police forces of
   non-police agencies). `E62` should therefore be somewhat *broader* than the
   department budget on this axis, partly offsetting reason 1.
4. **Fiscal year alignment.** BJS asks for "the most recent fiscal year
   completed" before June 30 of the survey year — for FY2000, "the calendar or
   fiscal year that included June 30, 2000". Census aligns to the government's
   own fiscal year ending between July 1 and June 30. Usually the same year;
   for cities on an off-cycle FY, the labels can differ by one.

Two further mechanical notes: Census IUF amounts are **thousands of dollars** and
this CSV is **whole dollars**; and BJS figures are self-reported by the police
chief, sometimes flagged as agency estimates (35% of the 2013 budgets provided
were estimates, per that report's footnote), whereas Census figures carry an
imputation flag.

Recommended use: treat BJS as an **order-of-magnitude and direction-of-travel**
check on `E62`, not as a reconciliation target. A 5-15% level gap is expected and
explainable; a factor-of-two gap is a finding.

## How independent is this, really?

Be honest about this in the write-up. The 1993, 1997 and 2000 LEMAS surveys were
"collected by the Bureau of the Census for BJS" — the instrument is Census Form
CJ-44, mailed from the Census Bureau's Jeffersonville address, and the volumes
credit Census Bureau project staff. The later waves used a different contractor
(RTI International administered the 2016 and 2020 LEMAS and the 2018 CSLLEA).

So this is **not** institutional independence from the Census Bureau. What it is:

- a **different instrument** (a law-enforcement management survey, not a
  government-finance survey);
- a **different respondent** (the police chief / department, not the city
  finance officer);
- a **different classification system** (BJS's own definition above, not the
  Census functional code manual);
- a **different universe** (agencies, not governments).

That makes it a genuine cross-check on the *measurement*, and a weak one on the
*institution*. If the goal is a check that is independent of the Census Bureau as
an organization, the only real options are city ACFRs / adopted budgets
(`spotcheck/`) and, for the later waves, RTI-administered LEMAS/CSLLEA microdata
from ICPSR.

## Known defects in the extracted data

- **Akron (OH), FY2000: `$8,744,720` for 487 sworn officers — $17,956 per
  officer.** This is what BJS printed (`raw/bjs_lemas00.pdf`, table 5a, Summit
  County); it is not an extraction error. It is implausible as a full-department
  budget and is almost certainly a partial or mis-keyed response. Drop or flag it
  before using FY2000 Ohio. It is the only row in the whole file outside
  $20k-$400k per sworn officer.
- **Indianapolis (IN), FY2000.** LEMAS 2000 reports Indianapolis Police alone at
  `$88,435,463`; NCJ 175703 appendix table C reports `$146,520,013` because BJS
  deliberately aggregated Indianapolis Police *and* the Marion County Sheriff's
  Department for that report ("The city of Indianapolis is served by both ...
  data from these two agencies were combined"). The CSV carries the LEMAS
  (department-only) figure for 1993/1997/2000 and the combined figure for 1990.
  **Indianapolis is not comparable across waves in this file.**
- **FY1990 rows are derived, not printed.** Appendix table C is published in
  constant 2000 dollars. BJS states the conversion factor explicitly ("All
  monetary data were converted to 2000 dollars by multiplying them by 1.3393"),
  so nominal FY1990 = printed / 1.3393. Each FY1990 row's `source` field says so.
  `sworn_officers` for FY1990 is derived as total / per-sworn-employee (both in
  2000 dollars, so the deflator cancels) and is therefore an **FTE** count with
  part-timers at weight 0.5, not a headcount.
- **FY1990 consolidation quirks**, all documented in NCJ 175703's methodology:
  New York merges the transit and housing police into NYPD; Charlotte adds
  Mecklenburg County Police; Indianapolis adds the Marion County Sheriff;
  Anaheim's 1990 values are averaged from the 1987 and 1993 surveys because it
  did not respond in 1990; Las Vegas is LVMPD, whose jurisdiction extends well
  beyond the city.
- **Consolidated city-counties in the LEMAS waves** that need the
  `city_flags.csv` treatment before any share is computed: Honolulu, Anchorage,
  Nashville (Metropolitan), Louisville, Las Vegas (Metropolitan), Charlotte
  (-Mecklenburg), Columbus GA, Washington DC. Jacksonville FL appears only in the
  FY1990 wave, and its police function is the Jacksonville Sheriff's Office.
- **Towns, not cities.** Amherst (NY) and Ramapo (NY) are New York *towns* of
  100k+, not incorporated cities. Kept, because Census treats NY towns as
  municipal-type governments, but flag them if the published universe is
  "cities".
- **Not everything reported.** Costa Mesa (CA) and Paterson (NJ) are 100k+ cities
  whose departments appear in the FY2000 personnel table but left the budget item
  blank. The earlier waves have more such gaps — 148 agencies in FY1993 vs 224 in
  FY2000 reflects both survey growth and nonresponse, not a change in the 100k+
  universe.
- **County and special-jurisdiction agencies are excluded** by name pattern
  (sheriffs, county police including Metro-Dade/Miami-Dade, state police,
  airport/transit/housing/campus/park forces). The raw PDFs contain them if
  anyone wants the county lane later.

## Validation already done

The FY2000 figures were extracted twice from two independent BJS publications —
once from LEMAS 2000 table 5a and once from the FY2000 column of NCJ 175703
appendix table C. **60 of 61 overlapping cities match to the dollar.** The one
exception is Indianapolis, for the documented reason above. That is a strong
check on the PDF parsing, though not on BJS's underlying data.

## Fire departments

There is no national dataset of individual fire department budgets. Checked:

- **NFPA Fire Department Experience Survey / U.S. Fire Department Profile** —
  collects fires, deaths, injuries, dollar loss, firefighter counts, stations and
  apparatus. Responses are confidential and only weighted national/regional
  estimates are published; no per-department release. Decisively, NFPA's own
  *Total Cost of Fire in the United States* sources its "local fire department
  expenditures" line **to the Census Bureau** — NFPA's headline fire-spending
  number *is* the Census number, so it is not an independent check on anything.
- **USFA/FEMA National Fire Department Registry** — the public bulk CSV
  (`https://apps.usfa.fema.gov/registry/api/download/national`, no login) has
  columns: FDID, department name, HQ and mailing address, phone/fax, county,
  department type, organization type, website, number of stations, active
  firefighters (career / volunteer / paid-per-call), non-firefighting personnel
  (civilian / volunteer), primary emergency-management agency flag. **No budget,
  revenue or expenditure field of any kind.**
- **NFIRS** (USFA / OpenFEMA) — incident-level only. Carries estimated property
  dollar loss per incident, which is not department spending.
- **USFA/NFPA Needs Assessment of the U.S. Fire Service** (FA-240, 2002; 4th
  edition, 2016) — the only budget question asks for the *percentage* split of
  budgeted revenue by source (taxes / fundraising / per-call contracts / other),
  never dollars, and is asked only of all- or mostly-volunteer departments, so
  100k+ cities are out of scope by design. Published as aggregate cross-tabs; no
  per-department microdata.
- **ICMA** — survey microdata is purchase-only under a licensing agreement that
  forbids redistribution; the Police and Fire Survey series ends around 2009 and
  no dollar-budget variable is documented. ICMA's "Fire Department Budget and
  Assets Study" is a single-city consulting report, not a dataset.
- **NFORS** is operational fireground data. **CitySpend** is repackaged Census
  ASSLGF, i.e. not independent.

Conclusion for the fire lane: the only genuinely independent agency-level fire
figures are city ACFRs and adopted budget documents, scraped city by city. Budget
for that accordingly, or state plainly in the methodology that the fire series
rests on Census alone.
