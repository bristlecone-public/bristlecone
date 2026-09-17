# Validation report

Build date: 2026-09-14. Everything below is reproducible with the scripts in `pipeline/`; the
comparison tables named here are in this folder.

## What was validated

The published dataset (`data/census_out/`) is a parse of the Census Bureau's individual unit finance
files. Four questions were tested:

1. Does the parser read the files correctly? (aggregate checks against Census's own published totals)
2. Does an independent implementation of the same aggregation get the same numbers? (Willamette GFD,
   Lincoln FiSC)
3. Do the police and fire numbers agree with what cities publish about themselves? (Vera FY2020
   adopted budgets; FY2022 annual financial reports and budget schedules for 29 cities in two rounds;
   BJS agency budgets FY1990 to 2000)
4. Where the numbers disagree, is the reason known and documented?

## 1. Parser correctness: exact against Census published totals

`checks.py` sums every expenditure item code across every municipality we parsed (all 19,000+, not
just the 332 large cities) by state, and compares to the municipal row of the Census Bureau's
state-by-type summary file shipped in the same release.

| year | state-by-code cells | exactly equal | notes |
|---|---|---|---|
| 2012 | 5,026 | 5,026 (100%) | published file uses alphabetical state codes; mapped |
| 2017 | 4,723 | 4,722 (99.98%) | one cell: Maryland central staff, 1.2% |
| 2022 | 2,901 | 2,859 (98.6%) | 42 cells, all our sum slightly under the published, largest 2.1% on a $5M code; police/fire only Florida fire (0.009%) and Kentucky police (0.004%) |

Police (E62) and fire (E24) specifically match in 51 of 51 states in 2012 and 2017 and 50 of 51 in
2022. The 2022 residuals are scattered across unrelated codes and states and are all in the same
direction, consistent with small revisions between the July 2026 reissue of the unit file we
downloaded and the earlier published summary. Sample years (2013 to 2015, 2018 to 2021, 2023, 2024)
cannot be checked this way because their published totals are weighted estimates of the whole
universe, not sums of respondents. `aggregate_check.csv`, `aggregate_check_all_codes.csv`.

## 2. Independent implementations of the same source

**Willamette Government Finance Database** (Pierson, Hand, Thompson; 1967 to 2024). Same Census
microdata, their own SAS build. Joined on FIPS place code for 3,428 city-years, 2012 to 2024:

- police: 35 disagreements, fire: 28. The rest are equal to the dollar.
- general expenditure: equal to the dollar in every 2022, 2023, 2024 row; disagrees in 10 to 45% of
  rows per year 2012 to 2021. Their notes document a defect in their 2007 to 2021 build (a
  double-counted highways line in total expenditure); the general-expenditure gaps sit in the same
  years and vanish outside them. Decomposing New York 2014: $3.2B of the $4.9B gap is utility interest
  and utility intergovernmental payments, which Willamette's general expenditure includes and ours does
  not; the remainder is unexplained and falls inside their documented 2007 to 2021 build defect. Their
  denominators are not used where ours exist. They are the only denominator available for 1967 to 2011
  and 2016 in the long series, and are labelled as such (`source` column).
- 2022 Houston, San Antonio, Dallas: police, fire, total, and general expenditure identical.
`willamette_vs_census.csv`, `data/willamette/NOTES.md`.

**Lincoln Institute Fiscally Standardized Cities** (212 cities; 2012, 2017, 2022, 2023). Their
`city_only` view is the Census municipal record republished unrounded. 540 city-years joined:

- police within 0.5% in 531 of 537, fire in 533 of 537, median relative difference 6 parts per million
  (Census rounds to $1,000; FiSC does not).
- Six police disagreements over 0.5%: four are 2012 (a different vintage of that file), plus Las
  Vegas 2023 and Seattle 2023.
- For consolidated city-counties the `fisc` view's county police component is the other municipalities in
  the county area, not a county government: verified to the dollar for 2022 in Indianapolis ($21.4M),
  Nashville ($10.0M), Louisville ($26.1M) and Jacksonville ($20.2M), and zero for Philadelphia and Denver,
  which contain no other incorporated places. See METHODOLOGY section 3.
- The `fisc` view adds a population share of the county's police to each city (Houston $981M city, $1,228M
  FiSC, the difference matching its share of the $513M Harris County Sheriff; median uplift 20% across 133
  cities). That overstates police for large cities whose residents get little sheriff patrol; see
  METHODOLOGY section 3.
- FiSC's "general expenditure" is direct general expenditure (no intergovernmental); matched against
  our `direct_general_expenditure_usd` it agrees within 0.5% in 494 of 540.
`fisc_vs_census.csv`, `data/fisc/NOTES.md`.

## 3. Independent sources: what cities publish about themselves

**Vera Institute, What Policing Costs (FY2020 adopted budgets, 72 cities).** Vera's headline number
folds pensions, debt service, and sheriff agencies into "policing" in 24 cities; their
department-only figure is the like-for-like comparator. 66 of 72 cities are in our universe.
Comparing Census actual police expenditure (closer of Census 2020 or 2021, since fiscal-year ends
differ) to Vera's department budget:

| | |
|---|---|
| median ratio Census / Vera | 0.98 |
| within 10% | 46 of 66 |
| within 20% | 59 of 66 |

Named exceptions: Las Vegas (0.11: police is the joint city-county Metro, and the round-2 spot check
shows the city's $151M contribution booked as intergovernmental), Los Angeles (1.47, central benefits
functionalized), St. Louis (1.65, and 1.47 in the spot checks; explained for FY2022 by non-police public safety coded as police, likely the same in FY2020), Providence (1.62, not
spot-checked), Seattle (0.66, below its own budget in every comparison; own pension fund),
Philadelphia (0.83, explained by the GAAP-versus-budgetary pension split). `vera_vs_census.csv`, `data/vera/NOTES.md`.

**FY2022 annual financial reports and budget schedules, 29 cities, two rounds.** Round 1: Houston,
San Antonio, Dallas, Austin, Fort Worth, El Paso, New York, Los Angeles, Chicago, Phoenix, Philadelphia,
Nashville, Virginia Beach, Denver, Seattle. Round 2 (non-Texas, chosen to cover plain large
municipalities and the cases other checks had flagged): San Diego, San Jose, Columbus, Charlotte,
Indianapolis, Jacksonville, Detroit, Boston, Baltimore, Memphis, Las Vegas, Louisville, St. Louis,
Atlanta. Every figure carries document URL, page, fiscal-year end, framing, whether pension
contributions sit inside the department line, and whether the city administers its own fund.
Against the department-level budgetary schedule, Census divided by document:

| | police | fire |
|---|---|---|
| median ratio | 1.03 | 1.04 |
| within 10% | 20 of 29 | 17 of 29 |
| within 20% | 23 of 29 | 25 of 29 |

| city | police | fire | pensions in line | own fund | note |
|---|---|---|---|---|---|
| Houston | 1.03 | 0.96 | yes | statutory boards | |
| San Antonio | 1.03 | 1.03 | yes | statutory board | |
| Chicago | 1.02 | 1.03 | no | city | matches the ex-pension line |
| New York | 1.04 | 1.04 | no | city | matches the ex-pension line; analyst-adjusted |
| Philadelphia | 1.01 | 0.93 | no (budgetary) | city | GAAP line with pensions gives 0.59 |
| El Paso | 0.98 | 1.25 | yes | statutory boards | |
| Phoenix | 0.95 | 0.98 | yes | state | |
| Denver | 1.09 | 1.15 | yes | state/city | |
| Virginia Beach | 1.05 | 1.16 | yes | state | |
| Dallas | 1.13 | 1.19 | yes | statutory board | |
| Fort Worth | 1.33 | 1.10 | yes | city | adopted budget; $80M Crime Control District outside general fund |
| Austin | 1.16 | 1.12 | yes | city | **imputed** by Census; city figure anomalous |
| Nashville | 0.77 | 1.03 | no | city | |
| Seattle | 0.75 | 0.89 | partly | city | |
| Los Angeles | 1.77 | 1.08 | no | city | central benefits functionalized into police |
| San Diego | 1.05 | 0.99 | yes | city | |
| San Jose | 1.05 | 0.97 | yes | city | split from City Manager's annual report |
| Columbus | 0.92 | 1.04 | yes | state | |
| Charlotte | 1.10 | 1.11 | yes | state/city | adopted budget; ACFR has no departmental split |
| Indianapolis | 0.98 | 0.92 | yes | state | **imputed** by Census |
| Jacksonville | 1.03 | 0.74 | yes | city | police is the Sheriff and includes the jail |
| Detroit | 1.03 | 1.00 | partly | city | legacy pension payments non-departmental |
| Boston | 1.05 | 1.00 | no | city | matches the ex-pension line |
| Baltimore | 0.90 | 1.29 | yes | city | |
| Memphis | 1.03 | 1.06 | yes | city | |
| Las Vegas | 0.11 | 1.04 | yes | state | city paid $151M to the joint Metro police; Census shows $18M |
| Louisville | 1.12 | 1.12 | yes | state | adopted budget; ACFR unobtainable |
| St. Louis | 1.47 | 1.14 | yes, as sub-lines | statutory boards | resolved: $54.3M of jail, inspection and other public safety coded as police (see below) |
| Atlanta | 0.94 | 0.95 | yes | city | |

On the combined police-plus-fire figure that the shares actually use, the ratio's interquartile range
is 0.96 to 1.11 and 25 of 29 cities are within 20%; METHODOLOGY section 2 translates that into about two
points of uncertainty on a 25% share.

**St. Louis, resolved (added 2026-09-15).** St. Louis's police ratio (1.47 police, 1.36 police plus fire)
was the one large unexplained residual. `data/spotcheck/stlouis_reconciliation_explainer.md` proposed that
Census built the city's record from the government-wide Statement of Activities. Verified against the
FY2022 ACFR (PDF p. 37): Census police $224,630K equals Statement of Activities police $170,281K plus
"Public safety: Other" $54,349K exactly, and fire, judicial, streets, health and welfare, interest,
airport, and water each equal their Statement of Activities line to the dollar. The "Other" line holds
the city jail, building inspections, excise, emergency management, and civilian oversight, so about
$54M of non-police spending sits in St. Louis's code 62. Without it the police-plus-fire ratio to the
city's schedule is 1.12, its share of general expenditure 23.1% rather than 28.0%, and its core share
31.8% rather than 38.7%. The Census values are left unaltered and the issue is recorded in
`data/known_issues.csv`. Two parts of the explainer did not verify: its all-funds police figure
($195,305K) mixes the budgetary general fund with GAAP special revenue funds, where the report's own
all-funds total is $198,236K (PDF p. 40); and its $25,024K "accrual adjustment" is a balancing figure
that does not appear on pages 40 to 43. Its claim that corrections is counted twice is consistent with
the evidence (Census current operations plus interest exceed the Statement of Activities total by
$97.7M, of which corrections and inspection codes are $49.9M) but not proven, and is recorded as
possible. Of the six spot-checked cities whose Statement of Activities splits police and fire, only
St. Louis matches Census, so this abstraction path is an exception, not a pattern.

Reading the table: ratios a few points above 1 are expected because Census counts all funds and the
schedules are general fund only. Where the document line excludes pensions (Chicago, New York, Boston,
Philadelphia budgetary) Census matches it, and where the line includes pensions paid into a
city-administered fund some cities land well below it (Philadelphia GAAP, Nashville, Seattle,
Baltimore), which is the manual's exclusion rule showing through. But San Diego, San Jose, Memphis and
Atlanta also administer their own funds with contributions inside the line and match within 6%, so
the treatment cannot be predicted from who runs the fund. Las Vegas confirms the contract-city
mechanism exactly. St. Louis, once the largest unexplained residual, is resolved below. `spotcheck_vs_census.csv`,
`data/spotcheck/NOTES.md`.

**Bureau of Justice Statistics, police operating budgets FY1990, 1993, 1997, 2000** (LEMAS agency
volumes and Police Departments in Large Cities; 229 cities, 609 agency-years, transcribed from the
published PDFs; FY2000 extracted from two separate BJS publications, 60 of 61 overlapping cities equal
to the dollar). The police chief answers the form, not the finance office, and BJS's definition
includes employer pension contributions and agency-run jails. Against the long series (Willamette
years, closer of Census Y or Y+1):

| BJS fiscal year | cities | median Census / BJS | within 10% | within 20% |
|---|---|---|---|---|
| 1990 | 61 | 1.03 | 35 | 52 |
| 1993 | 142 | 1.04 | 94 | 119 |
| 1997 | 168 | 1.05 | 100 | 139 |
| 2000 | 215 | 1.02 | 160 | 194 |

The expected below-1 ratio for cities with their own pension funds is visible in some (Dallas 0.85,
Cleveland 0.71) but not others (Chicago 1.17, Philadelphia 1.20, Boston 1.15), which is consistent
with the very low employer contributions many legacy funds made around 2000 and with BJS budgets
being agency operating appropriations that vary in what they carry. The pension effect is therefore
not cleanly separable at that vintage; the modern spot checks (section 3) show it directly. Later
LEMAS and CSLLEA waves (2016, 2018, 2020) collect budgets but only in login-gated microdata, and the
published CSLLEA 2018 tables contain no budget table. Akron FY2000 is a BJS printing error ($8.7M for
487 officers). `bjs_vs_census.csv`, `data/bjs/NOTES.md`.

## 3a. Employment counts (Phase 2)

**Parser check against published tables.** Summing every local government in the 2022 unit file by
state and comparing with the Census Bureau's published local-government employment table: nationally
within 0.35% for sworn officers (624,372 against 626,594), 0.11% for police civilians, 0.08% for
firefighters, 0.03% for other fire staff. By state, 47 of 51 are within 1% for sworn officers and 46 of 51
for firefighters, but only 30 of 204 state-by-item cells are exactly equal. Unit types and sub-units do
not explain the residual (Texas sworn: counties plus municipalities in the file sum to 55,216 against
55,544 published), and the documentation does not address it. Unlike the finance files, the employment
unit file is therefore close to, not identical with, the published totals. `employment_aggregate_check.csv`.

**Independent count: FBI police employee data.** The FBI's Uniform Crime Reporting program collects
sworn officers and civilians from each police agency as of October 31 (2,809 municipal agency-years,
2017 to 2024, `data/fbi/`). Joined to 2,279 Census city-years across 315 cities, excluding contract and
joint forces:

| | city-years | median Census / FBI | interquartile range | within 10% |
|---|---|---|---|---|
| sworn, Census reported | 1,499 | 1.009 | 0.975 to 1.051 | 82% |
| sworn, Census imputed | 546 | 1.028 | 0.963 to 1.122 | 58% |
| sworn, Census prorated | 192 | 1.030 | 0.943 to 1.114 | 57% |
| civilians, Census reported | 1,492 | 0.944 | 0.803 to 1.059 | 40% |

Sworn counts validate well, and the flags do real work: both modelled classes agree markedly less
often than reported ones. **Prorated is listed separately from imputed** because it is a different
failure - the department's unit total was reported and only the split across functions was
estimated - but it validates no better, at 57% against 58%, so the distinction matters for
interpretation rather than for quality. The median sits about 1% above the FBI from 2019 on, consistent with Census counting all city
employees with arrest powers in the police function against the FBI's department-only count, and with
the March versus October reference dates. Civilian counts do not validate and are not shown on the
dashboard. Largest 2022 sworn gaps among reported cities: Sunnyvale 0.50 (combined public-safety
officers split between police and fire codes), Indianapolis 0.69, Henderson 0.75, Chesapeake 0.77,
Charlotte 1.31. `fbi_vs_census.csv`, `data/fbi/NOTES.md`.

## 3b. County jails and courts allocation (Phase 2)

Checked against the Lincoln Institute FiSC county components (`corrections_cnty`, `admin_judicial_cnty`),
which apportion the same Census county records with FiSC's own geography. This tests the county matching
and the population shares; it is not independent of the Census source.

| year | measure | cities | median ours / FiSC | interquartile range | within 5% |
|---|---|---|---|---|---|
| 2012 | corrections | 106 | 0.999 | 0.997 to 1.000 | 104 |
| 2012 | judicial | 112 | 0.999 | 0.997 to 1.001 | 91 |
| 2017 | corrections | 104 | 0.999 | 0.995 to 1.001 | 104 |
| 2017 | judicial | 111 | 0.998 | 0.995 to 1.001 | 106 |
| 2022 | corrections | 104 | 1.000 | 0.997 to 1.003 | 102 |
| 2022 | judicial | 110 | 1.000 | 0.996 to 1.003 | 102 |

About 25 cities have no county corrections or courts on either side. Exceptions: Oklahoma City (ours 5.1
times FiSC) and Tulsa (1.35) in corrections, where our shares are correct but FiSC carries far less of
the Oklahoma and Tulsa County jail spending than the Census county record does, possibly because the
Oklahoma County jail moved to a public trust in 2020; unresolved. Five consolidated governments
(Indianapolis $5.0M, Baton Rouge $1.5M, Jacksonville $0.7M, Kansas City KS, Nashville) show small FiSC
county judicial amounts where the Census records hold no county government. `county_alloc_vs_fisc.csv`.

## 3c. Reported crime (Phase 2)

**Parser check against the FBI's own published tables.** 2019 violent, aggravated assault and property
counts parsed from the Return A master file, compared with the FBI's published Crime in the United States
2019 Table 8 for three states (`crime_vs_fbi_published_2019.csv`):

| state | cities | violent crime exact | median difference | property crime exact | median difference |
|---|---|---|---|---|---|
| California | 75 | 74 | 0.00% | 75 | 0.00% |
| Illinois | 7 | 4 | 0.00% | 5 | 0.00% |
| Texas | 42 | 13 | 0.94% | 13 | 0.30% |

California and Illinois confirm the parse, including the aggravated-assault derivation. Texas differs by a
median of about 1%, largest Denton and San Angelo near 20%, in both directions; the master file is updated
after publication and Texas agencies revise frequently, so we attribute the gap to later revisions. It is
not re-checked against a later FBI tabulation.

**Coverage and consistency.** 3,938 of 4,316 city-years are full-year reports. 332 are missing, 21
partial, 25 withheld because the agency polices far more than the city. 102 city-years from 2020 on break
sharply from the city's own pre-2020 level and are flagged; several are plainly incomplete submissions
filed as full years (Gainesville and Huntsville at 2% of their usual violent crime in 2021), others may be
real.

## 4. Known, documented reasons for disagreement

These come from the Census classification manual (`docs/refs/`) and were confirmed in the numbers:

- **Pension contributions: no single rule survives 29 cities.** The manual excludes payments into a
  fund the government administers itself and includes payments to other bodies. The exclusion is
  visible in Philadelphia (GAAP $1,317M, budgetary $775M, Census $784M), Nashville (0.77), Seattle
  (0.75) and Baltimore (0.90), and Census matches the ex-pension lines of Chicago, New York and Boston.
  Yet San Diego, San Jose, Memphis and Atlanta administer their own funds, carry contributions inside
  the department line, and match Census within 6%; Houston and San Antonio's statutory boards are
  matched at 1.03. Whatever Census does with a given city's contributions is not predictable from the
  fund's governance, cannot be corrected from the public file, and is the largest single comparability
  caveat. The spot-check table is the map; treat any city not in it as unverified on this point.
- **Centrally budgeted benefits are functionalized by Census.** Los Angeles budgets health benefits and
  workers' compensation outside the LAPD line; Census allocates them to police, giving 1.77x the
  department appropriation.
- **Contract police is invisible.** Las Vegas, Lancaster CA, and Spokane Valley before 2021 pay another
  government; the public file records that only as unallocated intergovernmental expenditure.
- **Fire districts.** 16 cities legitimately show $0 fire (Irvine, Lakewood CO, Port St. Lucie, Elk
  Grove and others): an independent district levies and spends it.
- **Imputation.** 39 of 332 cities have imputed police or fire in 2022, including Austin, Plano,
  Laredo, Frisco, McAllen, Mesquite, Round Rock, Odessa, Abilene, Pearland, Sugar Land, Lewisville,
  Allen, Tyler, Wichita Falls, Edinburg. Their values are Census estimates and are flagged as such on
  every row.
- **Partial responses.** 27 of 3,695 city-years (Toledo, Springfield IL, Syracuse 2022, Naperville and
  Centennial 2023-24, Wichita Falls 2024, Arvada 2017-18, Fishers 2020, Jurupa Valley) have shares set
  to null.
- **One-year spikes** in Corona, Pomona, Huntington Beach (2021-22) consistent with pension obligation
  bond proceeds paid to CalPERS; listed in `yoy_anomalies.csv`.
- **Fiscal-year ends.** Census 2022 is the fiscal year ending between July 2021 and June 2022, so
  cities with autumn or December closes (Dallas, San Antonio, Phoenix, Chicago, Denver, Seattle) report
  their FY2021 there; June-close cities (New York, Los Angeles, Houston, Philadelphia) line up.
- **Other agencies.** Code 62 is the municipal department only. Sheriffs, constables, transit, port,
  airport, and school police are on other governments' records under other functions (Houston METRO's
  $638M carries no police line at all). City police spending is a floor, not the total spent policing
  the city's residents.
- **General fund shares are a different statistic.** City budget messages quote police and fire as a
  share of the general fund (Phoenix 70%, Houston 70%, Chicago 46%, Seattle 32% in the FY2022
  schedules). The same dollars are 30%, 28%, 20%, and 16% of Census general expenditure. Both are true; only the
  Census denominator is defined the same way in every city.

## 5. What was not obtained

- Lincoln FiSC and Willamette are derived from the same Census microdata, so they validate the
  aggregation, not the underlying reporting. The only fully independent sources are Vera and the
  cities' own documents.
- Employee-retirement benefit payments (item X11) are in the 2012 to 2015 public files but not in
  2017 onward; `total_expenditure_usd` leaves them out in every year rather than carry a structural break.
- No national dataset of fire department budgets exists outside Census: the USFA registry has no financial field, NFPA publishes only national aggregates sourced to Census, and ICMA's series ended around 2009.
- Fort Worth's FY2021 and Louisville's FY2022 annual reports could not be retrieved (sites block
  scripted requests); adopted budgets used and flagged. Charlotte's report has no departmental split;
  adopted budget used. Detroit's department actuals come from its Four-Year Financial Plan rather than
  the report, whose budgetary schedule is by appropriation line.
