# Spot check: police and fire spending from cities' own financial documents, FY2022

Independent hand-read of 15 large cities' own published financial reports, to be
compared against the Census IUF parse. Retrieved 2026-09-14.

## What "FY2022" means here

Census fiscal year 2022 = **the city fiscal year ending between 1 July 2021 and
30 June 2022 inclusive**. That is *not* the same as the report the city labels
"FY2022" for every city:

| City | FY end date used | City's own label for that report |
|---|---|---|
| Houston, New York, Los Angeles, Phoenix, Philadelphia, Nashville-Davidson, Virginia Beach | 2022-06-30 | FY2022 |
| San Antonio, Dallas, Austin, Fort Worth | 2021-09-30 | FY2021 |
| El Paso | 2021-08-31 | FY2021 |
| Chicago, Denver, Seattle | 2021-12-31 | 2021 |

Every row in `spotcheck_fy2022.csv` carries `fiscal_year = 2022` (the Census
label) and the real `fy_end_date`. If someone later wants the city-labelled
FY2022 for the Sept/Dec cities, these are the wrong documents.

## Framings captured

- `acfr_statement_of_activities_governmental` — government-wide, full accrual,
  governmental activities only. Denominator = total governmental activities
  expenses. This is the framing most distorted by GASB 68/75 pension and OPEB
  expense, which can be large and *negative* (see Dallas, Nashville, Seattle,
  Fort Worth FY2020).
- `acfr_general_fund_by_function` / `_by_department` — modified accrual, General
  Fund column of the governmental-funds statement.
- `acfr_all_governmental_funds_by_function` / `_by_department` — same statement,
  total governmental funds column. **This is the closest ACFR analogue to an
  "all funds" figure** and is what the summary table below reports. It still
  excludes enterprise/proprietary funds (airports, water, electric) and the
  pension trust funds.
- `general_fund_budgetary_by_department` — the budgetary-comparison schedule,
  which is usually the only place in an ACFR where *police* and *fire* are split
  out as departments rather than lumped into "public safety".

## Cross-cutting comparability warnings

1. **Most ACFRs do not split police from fire.** Nine of the fifteen
   (Houston, San Antonio, Dallas, Austin, Fort Worth, El Paso, Chicago, Phoenix,
   Denver, Seattle, New York, Los Angeles) report a single lumped function line
   ("Public safety", "Protection of persons and property", "Public safety and
   judicial"). Only Philadelphia, Virginia Beach and Nashville split police and
   fire on the face of the fund statements. For the rest, the police/fire split
   comes from the budgetary schedule, which is on a *different basis* and a
   *different total* from the fund statement — do not mix the numerator from one
   framing with the denominator from another.
2. **The lumped "public safety" line is usually wider than police + fire.**
   It typically also includes municipal court, emergency communications/911,
   animal control, code/building inspection, jails, and in consolidated
   city-counties the sheriff and the courts. Where the budgetary schedule is
   available the gap is visible: e.g. Dallas public safety 866,072k vs
   police + fire 850,669k (the rest is 911 systems operations); Denver public
   safety 575,296k vs police + fire 349,574k (the rest is the undersheriff/jail
   and safety administration).
3. **Pension and OPEB treatment differs by city and by framing.** In the
   government-wide statement of activities, accrual pension/OPEB expense is
   allocated to functions, so police/fire are inflated or deflated by market
   returns. In the fund statements, some cities put the employer contribution
   *inside* the function line and some show it as a separate line. Cities where
   pension and/or fringe are **outside** the police/fire line at the fund level:
   New York, Chicago, Nashville, Philadelphia (budgetary framing only),
   Los Angeles (budgetary framing only), Seattle (legacy plans only).
4. **Fire does not always include EMS.** Austin, Philadelphia, Virginia Beach
   and Nashville all report a separate Emergency Medical Services function;
   Denver's ambulance EMS is run by Denver Health (a separate entity) and Fort
   Worth's by MedStar Mobile Healthcare (a separate authority). For the rest,
   EMS sits inside the fire department.
5. **`denominator_usd` is not the same concept across framings.** Always read
   `denominator_label`.

---

## Per-city notes

### Houston TX — FY ending 2022-06-30
- ACFR lumps police and fire into "Public safety" in every GAAP statement. The
  split (Police 954,187k / Fire 537,300k) is only in the General Operating Fund
  budgetary schedule, which has a *different* total (2,129,417k budgetary vs
  2,272,963k GAAP) because ten non-budgeted funds are folded into the GAAP
  General Fund.
- Retiree health/life (OPEB pay-go) is a separate GF line, "Retiree benefits"
  (11,837k). Pension contributions to HPOPS/HFRRF/HMEPS are not separately
  presented, so they are inside departmental "personnel services". Recorded
  `pensions_in_line = yes`, but this is inferred from the absence of a separate
  pension line rather than stated in the report.
- Houston Fire Department provides EMS.
- Houston has very large enterprise funds (Combined Utility System, Airport
  System) that are outside every framing here.

### San Antonio TX — FY ending 2021-09-30 (the city's "FY2021" ACFR)
- Clean split in the budgetary schedule: Police 479,435k, Fire 331,762k.
- General Fund revenue includes 383,127k of "Revenues from Utilities" (the CPS
  Energy transfer) — San Antonio's general fund is partly utility-financed,
  which changes what a "share of general fund" means.
- Police and fire are in the statutory Fire & Police Pension Fund; civilians in
  TMRS. Contributions are inside the departmental personal-services lines.
- SAFD provides EMS.

### Dallas TX — FY ending 2021-09-30
- **The statement-of-activities public-safety number is not usable as-is.**
  Governmental-activities Public safety expense is 306,796k against 897,953k of
  governmental-funds public-safety expenditures — a ~590m accrual credit,
  driven by the Dallas Police & Fire Pension System's GASB 68 expense. The
  General government line moves the other way (534,764k accrual vs 465,568k
  fund). Use the fund framings for Dallas.
- Budgetary split: Dallas Police 526,602k, Dallas Fire-Rescue 324,067k, plus
  9-1-1 systems operations 15,403k, all inside "public safety".
- DFR provides EMS.

### Austin TX — FY ending 2021-09-30
- **Fire does not include EMS.** Austin has a separate Emergency Medical
  Services department (87,794k GAAP actual / 100,213k budget basis) plus
  separate Emergency Communications (16,084k) and Forensic Science (11,908k)
  lines inside "Public safety".
- FY2021 is the year of Austin's police-budget "decoupling": the APD General
  Fund line carries an expense-refund credit of **-132,681k** that moves
  functions (forensics, 911, support services) to a Reimagining Safety /
  decoupled fund. The GAAP actual Police figure (314,340k) is therefore *not*
  comparable to Austin's FY2020 or FY2022 police numbers, and the budget-basis
  figure (384,835k) tells a different story again. Both rows are in the CSV;
  read them together.
- Austin's Electric and Water utilities are enterprise funds outside all of
  these framings, so Austin's police share of "all funds" would be far lower
  than its share of governmental funds.

### Fort Worth TX — FY ending 2021-09-30 — **partially complete**
- The City of Fort Worth web server returns HTTP 403 to every scripted request
  (curl, PowerShell, any user-agent), and the FY2021 ACFR PDF is larger than the
  10 MB WebFetch limit, so **the FY2021 ACFR itself could not be retrieved.**
- Workaround: the FY2021 figures were taken from the **FY2022 ACFR's statistical
  section** (Table 2 "Changes in Net Position" and Table 4 "Changes in Fund
  Balances of Governmental Funds", both last-ten-fiscal-years, FY2021 column),
  which was under the size limit. These are the same audited numbers, one year
  later, but they are unaudited statistical-section restatements — flag if this
  matters.
- No police/fire split is available from that source. The police/fire row is
  therefore the **FY2021 adopted General Fund budget** (Police 272,987,345,
  Fire 169,139,998, GF total 782,064,036), marked `actual_or_adopted = adopted`.
- Fort Worth has a **Crime Control and Prevention District** — a separate
  half-cent sales-tax district, blended into the city's governmental funds —
  that funds roughly another $80m/yr of police activity outside the General
  Fund. Any police share computed from the General Fund alone understates Fort
  Worth.
- Ambulance transport is provided by MedStar Mobile Healthcare, a separate
  governmental authority, not by the fire department.

### El Paso TX — FY ending 2021-08-31
- **El Paso's fiscal year ends 31 August**, not 30 September like the other
  Texas cities. The FY2021 ACFR (year ended 2021-08-31) is the one inside the
  Census window.
- Budgetary schedule splits Police 150,079,146 and Fire 125,878,771; note the
  Fire Department overspent its appropriation (105.6% of budget).
- The budgetary denominator ("Total charges to appropriations", 451,864,615) is
  larger than the GAAP General Fund total (415,739,917) because it includes
  budgeted transfers out.
- El Paso runs its own Firemen & Policemen's Pension Fund; employer
  contributions are inside the departmental lines.
- El Paso Fire provides EMS. El Paso Water is a component unit with a
  28 February year end, entirely outside these figures.

### New York NY — FY ending 2022-06-30
- **Pensions and fringe benefits are separate General Fund expenditure lines**
  (Pensions 9,599,122k; Fringe benefits and other benefit payments 8,556,605k;
  Judgments and claims 1,241,765k) and are *not* inside the agency figures.
  The NYPD 5,617,677k and FDNY 2,475,973k figures are therefore agency operating
  spending only — NYPD's all-in cost including pensions, fringe and debt service
  is roughly twice that. This is probably the single largest comparability trap
  in the set.
- The government-wide "Public safety and judicial" line (21,422,599k) *does*
  include allocated pension/OPEB expense; the fund line (11,936,786k) does not.
- "Public safety and judicial" also includes the Department of Correction
  (1,358,510k), Emergency Management, the DAs, and the Taxi & Limousine
  Commission.
- **New York City's budget includes the Department of Education** (33.5bn of
  governmental-funds expenditures) and City University. Denominators are
  therefore not comparable to a plain municipality.
- Agency figures come from the ten-year-trend schedule in the Comptroller's
  supplementary information; the FY2022 column was confirmed by matching
  "Total General Government" (4,225,605k) to the fund statement.
- FDNY includes EMS.

### Los Angeles CA — FY ending 2022-06-30
- The government-wide function is "Protection of Persons and Property", which
  besides Police and Fire contains Animal Services, Building & Safety and
  Emergency Management (about 141m of the 2,565m budgetary total).
- **Pension contributions are budgeted centrally, not in the department.**
  The General Fund budgetary schedule shows "Benefits" of 754,094k under General
  Government and a separate "Pension and Retirement Contributions" category;
  LAPD's 1,682,653k and LAFD's 746,979k are departmental appropriations only.
  The GAAP fund line for Protection of Persons and Property (3,414,251k) is
  ~850m larger than the sum of the departmental appropriations, which is where
  the benefit allocation shows up.
- The budgetary denominator used (7,999,008k "GRAND TOTAL" expenditures)
  **includes 2,529,043k of transfers to other funds**; net of transfers it is
  5,469,965k. Choose deliberately.
- Airports, Harbor and DWP are proprietary/independent and excluded.
- LAFD provides EMS.

### Chicago IL — FY ending 2021-12-31
- ACFR lumps everything into "Public Safety". The police/fire split comes from
  Schedule A-2, the General Fund budget-and-actual schedule: Chicago Police
  Department 1,620,221,941 and Chicago Fire Department 653,804,926, against a
  General Fund budgetary total of 4,971,362,842.
- **"Employee Pensions" is a separate governmental-funds expenditure line**
  (1,571,669k across all governmental funds, in dedicated Pension Funds). None
  of the city's police or fire pension contributions are inside the Public
  Safety line at the fund level. The government-wide Public Safety expense
  (4,534,257k vs 2,565,257k at the fund level) does include allocated pension
  expense.
- CFD provides EMS.

### Phoenix AZ — FY ending 2022-06-30
- Clean split in the budgetary schedule (Exhibit D-1): Police expenditures
  577,697k + 32,591k encumbrances; Fire 369,879k + 12,473k encumbrances. The
  CSV records the expenditures column only.
- Phoenix has several **dedicated public-safety sales-tax funds outside the
  General Fund** — Police/Fire Neighborhood Protection, Public Safety
  Enhancement, Public Safety Expansion — worth about 144m in FY2022 and shown
  in the ACFR as other financing uses. They are inside the all-governmental-
  funds Public safety line (1,172,208k) but not the General Fund line
  (951,323k). A General-Fund-only share understates Phoenix.
- "Criminal Justice" (municipal court, public defender) is a separate function
  from "Public Safety" in Phoenix, unlike most cities.
- PSPRS contributions are inside the departmental lines. Phoenix Fire provides
  EMS.

### Philadelphia PA — FY ending 2022-06-30
- Best-documented city in the set: Police and Fire are separate lines on the
  face of both the statement of activities and the governmental-funds statement,
  and again in the budgetary obligations schedule.
- **The two sets of numbers differ by a factor of ~1.7 for police** because the
  budgetary "obligations" schedule is departmental only (Police 774,948k,
  Fire 370,064k) while the GAAP fund statement allocates employee benefits and
  pension contributions into the function (Police 1,310,837k, Fire 503,288k).
  Philadelphia budgets employee benefits centrally under Finance.
- **Fire excludes EMS**: Emergency Medical Services is its own function
  (95,527k government-wide, 99,723k General Fund).
- Philadelphia is a **consolidated city-county**: the figures include the
  Prisons (313,373k), the Courts (348,574k) and the District Attorney. It also
  pays 297,884k to the School District ("Education"), though the School District
  itself is a separate reporting entity.

### Nashville-Davidson TN — FY ending 2022-06-30
- **The statement of activities is unusable for FY2022.** Governmental-activities
  expense for "Law enforcement and care of prisoners" is 38,343,330 and "Fire
  prevention and control" is 18,911,793, against fund-level expenditures of
  351,730,198 and 156,953,762. The reconciliation (Exhibit B-15) shows a
  **1,887,383,547 reduction in the total OPEB liability** in FY2022, allocated
  across functions in the accrual statement. The row is kept in the CSV for
  completeness but is flagged in `denominator_label`; do not use it.
- **Consolidated city-county with a dependent school system.** Total
  governmental-funds expenditures of 3,465,612,699 include 1,269,030,927 of
  education (Metro Nashville Public Schools). Shares computed against that
  denominator are not comparable to a plain municipality.
- **"Law enforcement and care of prisoners" is not police.** It combines the
  Metro Nashville Police Department with the Davidson County Sheriff's Office
  and the jails.
- **"Retiree benefits" (91,008,008) is a separate General Fund line**, so
  pension/OPEB is outside the police and fire lines at the fund level.
- Nashville Fire Department provides EMS.

### Virginia Beach VA — FY ending 2022-06-30
- Reported in whole dollars, and Police and Fire are separate department lines
  on the face of every statement — the cleanest city in the set.
- **Fire excludes EMS**: Emergency Medical Services is its own department
  (14,653,727 government-wide, 14,371,504 General Fund); VB EMS is largely
  volunteer-staffed, so its dollar cost badly understates the service.
- **City spending includes schools.** "Education" is 519,790,190 of the
  1,409,019,651 governmental-activities total and 519,866,042 of the
  1,616,285,220 all-governmental-funds total — the city appropriation to the
  School Board, which is a discretely presented component unit. Virginia Beach's
  police share of total spending is mechanically about a third lower than a
  city without a dependent school system.
- There is also a separate Sheriff's Department special revenue fund (Exhibit
  15-J) outside the Police line.
- VRS pension contributions are inside the departmental lines.

### Denver CO — FY ending 2021-12-31
- **Consolidated city and county.** The "Public safety" function includes the
  Undersheriff/jail (140,241k) and Safety Administration (26,261k) in addition
  to Police (240,863k) and Fire (108,711k). Police + fire is 349,574k of the
  575,296k General Fund public-safety total — a 39% overstatement if the lumped
  line is read as police + fire.
- **Fire does not include ambulance EMS**: Denver Health Paramedic Division
  provides ambulance transport, and is not in the city's governmental funds.
- Police and fire are in FPPA; contributions are inside the departmental lines.
- The copy of the 2021 ACFR published through the Colorado state local-government
  audit portal is a scanned image with no text layer; the city's own
  `acfr_denver2021.pdf` was used instead.
- Denver International Airport (921,608k of expenses) is an enterprise fund and
  is outside all of these framings.

### Seattle WA — FY ending 2021-12-31
- **The statement of activities understates public safety badly**: 536,517k
  government-wide against 778,683k at the fund level. The difference is accrual
  pension/OPEB expense (LEOFF/SCERS), which was strongly negative in 2021. Use
  the fund framings.
- Police and fire are not separate lines in any statement; the CSV figures are
  **sums of budget-control-level lines** in Schedule C-1:
  - Police Department = Administrative Operations 28,707 + Chief of Police 7,667
    + Collaborative Policing 12,658 + Compliance & Professional Standards 4,348
    + Criminal Investigations 53,775 + East Precinct 19,494 + Leadership &
    Administration 77,073 + North Precinct 29,122 + Office of Police
    Accountability 4,379 + Patrol Operations 11,739 + South Precinct 19,513 +
    Southwest Precinct 15,750 + Special Operations 49,814 + West Precinct
    25,507 = **359,546k**.
  - Fire Department = Fire Prevention 11,056 + Leadership & Administration
    40,718 + Operations 220,932 = **272,706k**.
  The Office of Police Accountability (4,379k) is an independent oversight body
  listed under the Police Department heading; subtract it if you want sworn-
  department-only.
- **Legacy pension funds are separate schedule lines**: Firefighters Pension
  19,889k and Police Relief & Pension 19,208k (closed pre-LEOFF local plans),
  plus Judgment & Claims - Police Act 7,958k. Current LEOFF/SCERS contributions
  are inside the departmental lines — hence `pensions_in_line = partly`.
- The budget-basis General Fund total (1,974,922k) is well above the GAAP
  General Fund total (1,720,046k); Seattle's budgetary General Fund covers
  subfunds (e.g. Human Resources health care services, 283,982k) that the GAAP
  statement presents differently.
- Seattle Fire runs Medic One EMS.
- Seattle City Light, Water, Drainage & Wastewater and Solid Waste are
  enterprise funds (1,883,638k of expenses) outside all framings. A "police as a
  share of all city spending" number for Seattle would be roughly half the
  governmental-funds share.

---

## Things that could not be obtained

| City | Missing | Why |
|---|---|---|
| Fort Worth | FY2021 ACFR itself; actual (rather than adopted) police/fire split; General Fund–only figures | fortworthtexas.gov returns HTTP 403 to all scripted requests and the FY2021 ACFR exceeds the 10 MB fetch limit. FY2021 totals recovered from the FY2022 ACFR's ten-year statistical tables; police/fire from the FY2021 adopted budget. |
| Austin | budget-basis General Fund total expenditures (denominator for the `general_fund_by_department_budget_basis` row) | The budget-basis column total was not on the extracted page; the GAAP General Fund total is provided on the companion row instead. |
| Nashville-Davidson | a usable government-wide police/fire figure | The FY2022 accrual figures are dominated by a 1.89bn OPEB credit (see above). |
| Houston, San Antonio, Dallas, Austin, El Paso, Chicago, Phoenix, Denver, Seattle, New York, Los Angeles | police/fire split at the *same* basis and total as the fund statements | These cities publish only a lumped public-safety function in the GAAP statements; the split exists only on the budgetary schedule. |

## Reproducing

`raw/` holds the downloaded PDFs and two helper scripts (`extract.py`,
`scan2.py`) used to locate and print statement pages; `build_csv.py` regenerates
the CSV from the transcribed figures.


---

## Round 2 (non-Texas)

Second hand-read, 14 cities, retrieved 2026-09-14, written to
`spotcheck_fy2022_round2.csv` (same columns as round 1; built by
`build_csv_round2.py`). Same fiscal-year rule: Census 2022 = the city year ending
between 1 Jul 2021 and 30 Jun 2022.

| City | FY end date used | City's own label for that report |
|---|---|---|
| San Diego, San Jose, Charlotte, Detroit, Boston, Baltimore, Memphis, Las Vegas, Louisville, St. Louis, Atlanta | 2022-06-30 | FY2022 |
| Jacksonville | 2021-09-30 | FY2021 |
| Columbus, Indianapolis | 2021-12-31 | 2021 |

Round-2 additions to the framing vocabulary: `general_fund_budgetary_by_function`
(a budgetary schedule that still lumps public safety), `acfr_general_fund_subfund_gaap`
(Indianapolis), `general_fund_by_department_annual_report` (San Jose, city
manager's year-end report), `general_fund_by_department_four_year_plan` /
`all_funds_by_department_four_year_plan` / `general_fund_budgetary_appropriation_lines`
(Detroit), `lvmpd_city_contribution` / `lvmpd_joint_venture_total_expenditures`
(Las Vegas), `all_funds_adopted_by_department` (Louisville), and the `_10yr_table`
suffix (Louisville, same workaround as Fort Worth in round 1).

### Pension administration summary (the field that decides whether Census lands above or below the document)

| City | Who administers police/fire pensions | Employer contribution inside the police/fire line? |
|---|---|---|
| San Diego | City (SDCERS, city-administered trust) | yes - ADC allocated to departments, no separate line |
| San Jose | City (Police & Fire Department Retirement Plan, Office of Retirement Services) | yes - in departmental personal services |
| Columbus | State (Ohio Police & Fire Pension Fund, OP&F) | yes - inside "Personal services" |
| Charlotte | State (NC LGERS) for police; city single-employer Charlotte Firefighters' Retirement System for fire | yes - departmental, no separate line |
| Indianapolis | State (INPRS 1977 Police & Firefighters' fund); pre-1977 benefits paid by the State since 2009 | yes for the 1977 fund; pre-1977 is a state pass-through |
| Jacksonville | City (Police and Fire Pension Fund, single-employer, own Board of Trustees) | yes (inferred - no separate pension line; contributions sit in the Sheriff / Fire budgets) |
| Detroit | City (Police and Fire Retirement System, Retirement Systems of the City of Detroit) | **partly** - current-year "Employee Benefits" inside departments; legacy "Pension-Related Payments" 153,639,989 is a non-departmental line |
| Boston | City (Boston Retirement System, city Retirement Board) | **no** - "Retirement costs" 502,585k (GAAP) / "Pension costs" 327,014k (budgetary) is a separate line, as is "Other employee benefits" 258,112k |
| Baltimore | City (Fire and Police Employees' Retirement System, single-employer) | yes (inferred - agency-level schedule has no central pension line) |
| Memphis | City (City of Memphis Retirement System, single-employer) | yes (inferred - inside "Personnel services") |
| Las Vegas | State (Nevada PERS) for fire and marshals; police pensions are inside LVMPD's own budget, not the city's | yes (fire: "Employee benefits" line inside the department) |
| Louisville | State (Kentucky CERS) for essentially all active police and fire; two closed city plans (Firefighters' Pension Fund, Policemen's Retirement Fund) | yes for CERS; the closed plans are separate lines (FY22 budget 1,639,400 + 1,351,000) |
| St. Louis | City-sponsored statutory boards (Police Retirement System, Firemen's Retirement System, Firefighters' Retirement Plan) | yes, but as **separate sub-lines inside the function** (Police Retirement System 26,340k; Firemen's Retirement System 8,703k) |
| Atlanta | City (Police Officers' and Firefighters' pension plans, city-administered) | yes (inferred - no separate pension line; FY2022 accrual expense was a credit, so SoA police 195,638k < fund police 226,073k) |

### Per-city notes

#### San Diego CA - FY ending 2022-06-30
- Cleanest of the round: police and fire are separate functions on every statement
  ("Public Safety - Police", "Public Safety - Fire and Life Safety and Homeland
  Security"). The fire function also carries Lifeguards and the Office of Homeland
  Security.
- Budgetary GF total (1,669,283k) is below the GAAP GF total (1,877,289k) because
  GASB 54 folds ten non-budgeted funds into the GAAP General Fund (same pattern as
  Houston).
- SDCERS is city-administered; the ADC is allocated to departments (the charter
  even funds a "Reserve for increases in the ADC"). Recorded `pensions_in_line = yes`,
  inferred from the absence of a separate pension line.
- SDFD provides EMS; ambulance transport is contracted (Falck) under a city
  contract, so part of the cost is outside the department.
- Water and Sewer utilities are enterprise funds outside all framings.

#### San Jose CA - FY ending 2022-06-30
- ACFR lumps "Public safety" in every statement (614,802k SoA; 724,909k GF;
  730,982k GF budgetary). The police/fire split comes from the City Manager's
  **2021-2022 Annual Report, Table D** (Police 486,209,322; Fire 269,091,701,
  both "expenditures including encumbrances"), against a GF total of
  1,606,749,398 that includes 504,863,946 of non-departmental spending
  (city-wide expenses, capital contributions, transfers). Departmental subtotal
  is 1,101,885,452.
- The city administers both single-employer plans (Police & Fire, Federated);
  contributions are inside departmental personal services.
- Fire excludes ambulance transport (Santa Clara County contracts it); SJFD
  provides paramedic first response only.
- Airport, wastewater, water and San Jose Clean Energy are enterprise funds.
- The sanjoseca.gov finance page returns 403 to plain requests; the ACFR was
  found via the "Annual Comprehensive Financial Reports Archive" folder with
  full browser headers.

#### Columbus OH - FY ending 2021-12-31
- ACFR lumps public safety; the split is in Exhibit A-1 (budget basis, whole
  dollars): Police 386,375,712, Fire 273,109,487, plus Safety Director 9,284,122
  and Support Services 18,305,976 inside the 687,075,297 public safety total.
- OP&F is a state cost-sharing plan; employer contributions are inside
  "Personal services".
- Columbus Division of Fire runs EMS.
- Budgetary GF total (925,286k) is below GAAP (954,434k); the reconciliation is
  on Exhibit 10.

#### Charlotte NC - FY ending 2022-06-30
- **No police/fire split anywhere in the ACFR** - even the budgetary comparison
  statement is by function. The split is the **FY2022 adopted budget**
  (Police 300,877,459; Fire 144,575,666; GF total 750,720,000), marked
  `adopted`. The same budget page shows FY2020 GAAP actuals if a prior-year
  actual is ever needed.
- Budgetary "total charges to appropriations" (769,566k) includes 32,597k of
  transfers out; GAAP GF expenditures are 736,376k.
- Police are in NC LGERS (state); firefighters are in the city's own Charlotte
  Firefighters' Retirement System (a blended component unit). No separate
  pension line in the budget.
- **Fire excludes ambulance transport**: MEDIC (Mecklenburg EMS Agency, a county
  agency) transports; CFD first-responds.
- Water, Storm Water, Airport and CATS transit are enterprise funds.
- Charlotte-Mecklenburg Police also polices unincorporated Mecklenburg County
  and small towns under contract (GF revenue "Law Enforcement Services -
  County" 16.9m) - the city's police figure is therefore slightly *wider* than
  the city.

#### Indianapolis IN - FY ending 2021-12-31 (Consolidated City-County)
- **Two ACFRs.** The Consolidated City of Indianapolis-Marion County reports
  as two component units: the *City of Indianapolis* (SBOA report B59599,
  used here) and *Marion County* (B59598, which the first search returned and
  which has no IMPD/IFD - it carries the Sheriff and jail: Corrections
  132,503,541 and "Protection of people and property" 10,908,544). A police
  share computed from the City ACFR alone omits the county Sheriff.
- The City ACFR lumps "Public safety" on the face of the statements, but the
  General Fund is presented by **subfund**: Metropolitan Police 270,450k and
  Fire 195,005k (GAAP), 245,906k and 168,925k (budgetary), out of public safety
  totals of 507,373k / 458,762k. The remainder is the Consolidated County
  subfund (30,473k), Public Safety Communications (9,854k) and Park (1,591k).
  The GAAP-vs-budgetary gap (~50m) is mostly the state-paid pre-1977 pension
  benefits booked as contribution revenue and expenditure (27,376k) plus
  accruals.
- 1977 fund is INPRS (state); pre-1977 police/fire pensions have been paid by
  the State since 2009.
- **Fire excludes EMS**: Indianapolis EMS is a division of the Health &
  Hospital Corporation of Marion County (separate entity).
- IMPD's service area is the consolidated county minus the excluded cities
  (Lawrence, Speedway, Beech Grove, Southport), which run their own police.

#### Jacksonville FL - FY ending 2021-09-30 (Duval consolidated)
- **Police = Office of the Sheriff** (484,725k actual, +8,945k encumbrances).
  The JSO also runs the Duval County jail and court security, so this line is
  police + corrections; the ACFR does not separate them.
- Fire/Rescue 287,609k (+914k encumbrances); JFRD provides EMS.
- Public safety at the fund level (779,318k) also includes the Medical
  Examiner, Courts, Public Defender/State Attorney support etc.
- Police and Fire Pension Fund is a city single-employer plan with its own
  Board of Trustees; the city's contribution is appropriated in the annual
  budget and sits inside the departmental lines (no separate line) - recorded
  `yes`, inferred.
- Statement-of-activities public safety (1,161,203k) is ~380m above the fund
  level (779,318k): accrual pension/OPEB expense was strongly positive in
  FY2021 (the reverse of Dallas/Nashville).
- JEA (electric/water), the Port, Airport and Transportation Authority are
  component units, outside all framings; the GF receives a 120,012k JEA
  contribution.

#### Detroit MI - FY ending 2022-06-30
- ACFR function is "Public protection" (593,992,170 SoA; 503,652,166 GF;
  546,197,997 all governmental funds) with no police/fire split, and the
  budgetary schedule is by *appropriation* (outcome-named lines such as
  "Criminal Code Enforcement"), not by department.
- **Department totals come from the FY2024-27 Four-Year Financial Plan,
  Section B**, whose budget-summary tables show FY2022 *actual* department
  expenditures: Police GF 322,030,865 / all funds 337,163,285 (B37-7); Fire GF
  136,894,832 / all funds 137,096,085 (B24-4). These are the city's own
  numbers but from a budget document, not the audited ACFR.
- Summing the ACFR appropriation lines that are explicitly labelled Police
  (Emergency Response 153,450,849 + Criminal Code Enforcement 71,091,562 +
  Administration 35,552,630 + Community Engagement 6,004,021 + Board of Police
  Commissioners 2,547,150 + Executive Protection Unit 2,169,901 = 270,816,113)
  understates the department by ~51m; DPD also carries 911 Communications
  Operations and the Detroit Detention Center under other appropriation names.
  The fire sum (133,838,476) is within 3m of the department total. Both sums
  are kept in the CSV, flagged.
- **Pensions are split**: current-year "Employee Benefits" are inside the
  departments, but the Plan-of-Adjustment legacy pension payments
  ("Pension-Related Payments" 153,639,989) are a non-departmental
  appropriation - `pensions_in_line = partly`. The city administers PFRS.
- DFD runs EMS.
- 36th District Court, BSEED and Homeland Security are also inside "Public
  protection".

#### Boston MA - FY ending 2022-06-30
- Budgetary schedule splits Police 420,412k and Fire 289,514k within a public
  safety function of 784,791k (also Traffic, Parking Clerk, Inspectional
  Services, Youth Fund, Emergency Preparedness).
- **Pensions and benefits are outside the department lines**: "Retirement
  costs" 502,585k and "Other employee benefits" 258,112k are separate GAAP
  lines (327,014k / 258,778k budgetary). The Boston Retirement System is
  city-administered. Same trap as New York.
- **Fire excludes EMS**: Boston EMS is part of the Boston Public Health
  Commission (a component unit; GF appropriation 114,802k).
- **Schools are inside every denominator** (Boston Public Schools 1,294,706k
  plus 229,842k charter tuition and 94,117k MBTA assessment); shares are not
  comparable to a plain municipality.
- Suffolk County Jail assessment (2,898k) is a state/district assessment.

#### Baltimore MD - FY ending 2022-06-30
- Function is "Public safety and regulation". **Statement of activities is
  badly distorted**: 495,295k government-wide against 867,723k at the fund
  level - a ~372m accrual pension/OPEB credit. Use the fund framings.
- Budgetary schedule is by agency: Police 513,796k, Fire 271,684k, against
  1,999,523k of GF expenditures and encumbrances. That total includes the
  275,514k appropriation to Baltimore City Public Schools, the Sheriff
  (22,025k), State's Attorney (34,168k) and Courts (20,133k) - Baltimore is an
  independent city with county functions.
- F&P ERS is a city single-employer plan; no central pension line in the
  agency schedule, so `yes` inferred.
- BCFD runs EMS. Water/wastewater/stormwater/parking are enterprise funds.
- The first search hit (msa.maryland.gov 20230151e.pdf) is the *State of
  Maryland* ACFR, not the city's; the city file is served from an S3 bucket
  behind baltimorecity.gov/media/document/acfrcy22pdf.

#### Memphis TN - FY ending 2022-06-30
- ACFR lumps public safety; Exhibit A-8 (basis of budgeting) splits Police
  283,012k and Fire 202,506k (public safety 485,518k; GF 746,812k). Both
  departments net an "Expense reimbursement" credit (Police -13,656k, Fire
  -9,694k) for costs recovered from other funds/grants.
- SoA public safety (614,942k) is ~131m above the fund level: accrual pension
  expense. City of Memphis Retirement System is city-administered;
  contributions are inside "Personnel services" (inferred).
- Memphis Fire Services runs EMS.
- MLGW (1.5bn of expenses) is a business-type activity outside all framings;
  Education (6,010k) is a residual line, Memphis having handed its schools to
  Shelby County in 2013.

#### Las Vegas NV - FY ending 2022-06-30
- **Police is a joint venture.** The Las Vegas Metropolitan Police Department
  (NRS 280) is funded by Clark County (63.6%) and the City (36.4%). Three
  police framings are recorded: (a) the GF budgetary "Police" function
  167,253,759 = 151,525,764 LVMPD contribution + 15,727,995 City Marshals
  (a separate city agency); (b) the amount the city paid Metro per the
  joint-venture note, 151,464,415; (c) LVMPD's own total expenditures,
  648,345,618, of which the city's share is ~36% - the rest is Clark County
  and Metro's own property-tax levy. Census codes the city's contribution as
  intergovernmental (L89), so the city's code-62 line should be roughly the
  Marshals only (see METHODOLOGY 2.2, `police_contracted`).
- Corrections (city jail, 57,299,066) is a separate public safety line in the
  city's budget.
- **Statement of activities public safety (268,545,568) is unusable**: it is
  135m *below* the fund level (403,404,813) because of the FY2022 Nevada PERS
  accrual credit.
- Fire 155,609,043 = Fire and rescue 155,410,514 + Emergency management
  198,529. Nevada PERS (state); contributions are the "Employee benefits" line
  inside the department. LVFR provides EMS including transport-capable
  rescues (private franchisees also transport).
- The city's General Fund is budgeted without the Fiscal Stabilization fund,
  which GAAP folds in (reconciliation on the budget statement).

#### Louisville KY - FY ending 2022-06-30 (Metro consolidated) - **partially complete**
- **louisvilleky.gov returns HTTP 403 to every scripted request for its
  report pages, and the FY22 ACFR file path could not be guessed** (the FY23
  file at /2024-02/fy23_acfr.pdf downloads fine). The FY2022 figures are
  therefore taken from the **FY2023 ACFR ten-year statistical tables** (same
  audited numbers, one year later, unaudited restatement) - the Fort Worth
  workaround.
- Louisville's statements are **by department**, and the stat tables carry the
  Louisville Metro Police Department as its own line (213,042,242 accrual;
  199,758,816 all governmental funds) but roll Fire into a "Public Protection"
  group (209,217,583 / 193,090,835) with EMS, MetroSafe, Corrections, Youth
  Transitional Services, Animal Services, the Criminal Justice Commission and
  the two closed pension funds. **No FY2022 actual for Fire alone was
  obtainable**; the CSV carries the FY2021-22 *original budget* instead
  (all funds: LMPD 195,895,700, Fire 72,346,000 of 830,291,200 operating;
  GF group: 185,295,900 / 69,355,000 of 717,305,100), marked `adopted`. The
  revised FY22 budget was LMPD 219,253,000 / Fire 72,398,500.
- Kentucky CERS (state) covers active police and fire; the closed Firefighters'
  Pension Fund and Policemen's Retirement Fund are separate budget lines
  (~3m).
- **Fire excludes EMS** (Louisville Metro EMS is its own department, 25.8m in
  FY23). **Louisville Fire covers only the Urban Services District (the
  pre-merger city)**; the rest of Jefferson County is served by ~16 suburban
  fire protection districts, separate taxing districts off Metro's books
  (Metro pays them 105,200). Any Louisville fire share is therefore a floor.
  LMPD covers the whole county except small cities with their own police.
- MSD (sewer), Louisville Water, TARC (transit) are component units.

#### St. Louis MO - FY ending 2022-06-30
- Police and fire are separate lines on the face of every statement (SoA:
  Police 170,281k, Fire 81,272k, Other 54,349k; GF: 155,724k / 72,435k / 35,378k;
  all governmental funds: 198,236k / 85,847k / 53,563k).
- **Pension contributions are separate appropriation lines inside the
  function**: Police Retirement System 26,340k and Firemen's Retirement System
  8,703k sit under "Public safety - police/fire" in Schedule 1, alongside the
  operating departments (Police 125,625k, Fire Operations 62,668k). Both
  systems are city-sponsored statutory boards; Census will most likely treat
  them as city-administered and exclude the contributions, so its police
  figure should land ~26m below the document's 152,793k.
- Public safety "Other" holds the City Jail (24,580k), Building Commissioner,
  Excise, Emergency Management and the Civilian Oversight Board. Judicial
  (Circuit Court, Sheriff, Circuit Attorney, Juvenile Detention) is a
  separate function - St. Louis is an independent city.
- **A large share of police spending is outside the General Fund**: all
  governmental funds police (198,236k) exceeds GF police (155,724k) by 42m
  because the two Public Safety Sales Tax funds and the Public Safety Trust
  fund carry police costs.
- STLFD runs EMS. Airport, Water and Parking are enterprise funds.

#### Atlanta GA - FY ending 2022-06-30
- Police and Fire are separate functions on every statement, and a separate
  Corrections line (11,712k SoA; 14,397k GF) keeps the jail out of police.
- Atlanta budgets on the GAAP basis, so the budgetary schedule (Police
  226,073k, Fire 102,902k, GF 640,760k) equals the fund statement.
- **Statement of activities is below the fund level** (Police 195,638k vs
  226,073k; Fire 79,966k vs 102,902k): FY2022 accrual pension credit on the
  city-administered Police Officers' and Firefighters' plans. Contributions
  are inside the departmental lines (inferred; no central pension line).
- **Fire excludes ambulance transport** (Grady EMS); AFRD first-responds.
- Watershed and Aviation (1.13bn of expenses) are enterprise funds outside all
  framings, so Atlanta's police share of "all funds" would be roughly half its
  governmental-funds share.
- All-governmental-funds police (255,441k) is 29m above the GF figure: grants
  and the E-911 special revenue fund.

### Other agencies carrying police spending outside the city's own department

| City | Agency / where it sits |
|---|---|
| Indianapolis | Marion County Sheriff and jail - on the *Marion County* component-unit ACFR (B59598), not the City's |
| Jacksonville | The Sheriff *is* the city police, and also runs the jail - police and corrections are inseparable in the city's figures |
| Las Vegas | LVMPD is a joint venture with Clark County; city pays a contribution (intergovernmental, not code 62) |
| Louisville | Suburban fire districts (separate taxing districts) and small-city police departments; Metro Corrections is a separate department |
| Charlotte | CMPD polices the county under contract (widens the city figure); MEDIC (county) provides EMS |
| Boston | Boston EMS is inside the Boston Public Health Commission component unit; Suffolk County Jail is a state assessment |
| Baltimore, St. Louis | Independent cities: Sheriff, State's Attorney/Circuit Attorney, courts and jail are on the city's books but outside the police line |
| Detroit | 36th District Court and Detroit Detention Center (DPD) inside "Public protection"; DDOT transit police in the enterprise fund |
| Atlanta, Memphis, San Diego, San Jose, Columbus | County sheriffs and school/transit police are on other governments' books; nothing extra on the city's |

### Things that could not be obtained (round 2)

| City | Missing | Why |
|---|---|---|
| Louisville | FY2022 ACFR itself; FY2022 *actual* Fire expenditure; any FY2022 General-Fund-only actual | louisvilleky.gov 403s every scripted request and the FY22 file path is not discoverable; FY2022 totals and LMPD recovered from the FY2023 ACFR ten-year tables (Fire is inside a "Public Protection" group there); Fire from the FY2021-22 original budget |
| Detroit | police/fire actuals on the audited ACFR basis | ACFR budgetary schedule is by appropriation, not department; department totals taken from the FY2024-27 Four-Year Financial Plan (FY2022 actual column) |
| Charlotte | actual (rather than adopted) police/fire split | ACFR has no departmental schedule; FY2022 adopted budget used |
| San Jose | police/fire split on the audited basis | ACFR lumps public safety; split from the City Manager's 2021-2022 Annual Report (includes encumbrances) |
| Columbus, Indianapolis, Jacksonville, Boston, Baltimore, Memphis, Las Vegas | police/fire split at the same basis and total as the fund statements | lumped public safety in the GAAP statements; split only on budgetary schedules |
| Jacksonville | police separate from corrections | JSO runs the jail; not separated in any city document |
| Indianapolis | a single document covering IMPD/IFD *and* the county Sheriff | consolidated government reports as two component units |

### Reproducing

`raw/` now also holds the round-2 PDFs (`sandiego_acfr_fy2022.pdf`,
`sanjose_acfr_fy2022.pdf`, `sanjose_fy2022_gf_expenditure_performance.pdf`,
`columbus_acfr_fy2021.pdf`, `charlotte_acfr_fy2022.pdf`, `charlotte_fy2022_budget.pdf`,
`indianapolis_acfr_fy2021.pdf`, `jacksonville_acfr_fy2021.pdf`, `detroit_acfr_fy2022.pdf`,
`detroit_fy2024_sectionB.pdf`, `detroit_police_fy2024_lpd.pdf`, `boston_acfr_fy2022.pdf`,
`baltimore_acfr_fy2022.pdf`, `memphis_acfr_fy2022.pdf`, `lasvegas_acfr_fy2022.pdf`,
`louisville_acfr_fy2023.pdf`, `louisville_fy2023_recommended_budget.pdf`,
`stlouis_acfr_fy2022.pdf`, `atlanta_acfr_fy2022.pdf`). Several city servers
(Columbus, Charlotte, San Jose, Louisville, Memphis) reject curl unless a full
browser header set is sent; `build_csv_round2.py` regenerates the CSV.
