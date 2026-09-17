# Methodology

## 1. Primary source

**U.S. Census Bureau, Annual Survey of State and Local Government Finances (ALFIN) and Census of
Governments: Finance component, Individual Unit Files (public use).**

- Downloaded from `https://www2.census.gov/programs-surveys/gov-finances/tables/<year>/` (2017 to 2024)
  and `https://www2.census.gov/govs/local/` (2012 to 2015). No 2016 individual unit file is published.
- Each record is one item code for one government: amount in thousands of dollars, fiscal year, and an
  imputation flag. Every figure we publish is the sum of specific item codes, so it is reproducible from
  the raw files by anyone.
- Scope: Census **Type 2 municipal governments** (cities, boroughs, incorporated towns and villages) with
  100,000 or more residents in any year 2012 to 2024. Type 3 towns and townships are excluded. In most
  states they are overlapping or minor governments (29 Illinois and Indiana townships exceed 100k and run
  no police or fire), but in New York and New Jersey they are the primary municipal tier: the exclusion
  drops Hempstead (764k), Brookhaven (480k), Islip (329k), Oyster Bay (297k), North Hempstead (230k),
  Babylon (210k), Huntington (200k), Ramapo (138k), Amherst (126k), Smithtown (116k) in New York and
  Lakewood (107k) in New Jersey. The New York towns are policed by Nassau and Suffolk county departments,
  so their own police codes would read near zero. Honolulu is classified Type 2 by Census and is included.
- Years ending in 2 and 7 are full censuses: every municipality reports (or is imputed). Other years are
  a sample. All municipalities over 100k population are certainty units, so they are in every year's
  sample, but a city can still be a nonrespondent in a given year: 20 to 35 of the 332 are absent from
  each sample year (the 2022 file has 332 rows, 2021 has 302). Anyone computing medians or aggregates
  across years should hold the panel fixed rather than let composition change every fifth year.
- Census fiscal year Y covers fiscal years ending 1 July Y-1 through 30 June Y. A city with a 30 June
  close (New York, Los Angeles, Houston, Philadelphia) reports its FY2022 as Census 2022; a city closing
  30 September (Dallas, Phoenix) or 31 December (Chicago, Denver, Seattle) reports what it calls FY2021
  as Census 2022. Compare to city documents with this in mind.

Pre-2012 coverage comes from the Willamette University Government Finance Database (Pierson, Hand,
Thompson), which is a cleaned repackaging of the same Census unit files back to 1967. It is not an
independent source, but it is an independent implementation of the same aggregation and is used as such
in `validation/`.

## 2. What counts as police and fire

Census function code **62 Police Protection** and **24 Local Fire Protection**, definitions from the
2006 Government Finance and Employment Classification Manual (`docs/refs/`):

- Police (62) includes regular police departments, criminal investigation, crime labs, coroners and
  medical examiners, temporary lockups, police communications. Excludes jails that hold people beyond
  arraignment (Corrections, 05), municipal courts and prosecutors (Judicial, 25), park rangers, transit
  police, campus police.
- Fire (24) includes fire suppression, prevention, inspection, and **ambulance/EMS when run by the fire
  department**. EMS run by a health department is coded Health (32).

We sum the direct-expenditure characters for each function:

| column | item codes |
|---|---|
| `police_usd` | E62 current operations + F62 construction + G62 other capital outlay |
| `fire_usd` | E24 + F24 + G24 |
| `police_current_ops_usd`, `fire_current_ops_usd` | E62, E24 alone |
| `police_capital_usd`, `fire_capital_usd` | F+G |

Two classification rules matter for comparability and cannot be undone from the public file:

1. **Pensions.** By the manual, a government's contributions to a retirement system it administers
   itself are an interfund transfer, excluded from functional expenditure, while contributions to a
   system run by another body (state plans such as TMRS or CalPERS, Social Security, independent
   boards) are included. Twenty-nine spot checks (`validation/REPORT.md`, section 3) show the
   exclusion clearly in some cities (Philadelphia: GAAP $1,317M with pensions, budgetary $775M without,
   Census $784M; Nashville 0.77 and Seattle 0.75 against their general funds; Baltimore 0.90) and show
   Census matching ex-pension department lines in Chicago, New York and Boston. But cities that also
   administer their own funds and carry contributions inside the department line (San Diego, San Jose,
   Memphis, Atlanta) match Census within 6%, and the Texas statutory boards (Houston, San Antonio)
   match at 1.03. The treatment is therefore not predictable from fund governance and cannot be
   applied as a blanket adjustment. Los Angeles goes the other way: health, workers' compensation and
   pension costs budgeted centrally are functionalized by Census into the police line, 1.77 times the
   department appropriation. Use the spot-check table city by city.
2. **Contract services.** When a city buys police or fire service from another government (a county
   sheriff contract, a joint metro police, a regional fire authority) the payment is intergovernmental
   expenditure. The public unit file carries intergovernmental expenditure only as "general NEC" (L89/M89),
   not by function, so such cities show little or no code 62/24 spending. They are flagged, not adjusted.
3. **Other police agencies serving the same residents are not in code 62.** The city's record covers
   the municipal police department only. County sheriffs and constables are on the county's record;
   transit police are coded to the transit function of the transit authority (Houston METRO's $638M is
   entirely code 94, with no police line at all; the same holds for New York's MTA and the Bay Area's
   BART); port, airport, and school-district police are coded to those functions on those governments.
   State police are state expenditure. The Fiscally Standardized basis (`fisc_share.csv`) adds a
   population share of the county's police and corrections; nothing in any Census product adds the rest.
   A city's "police spending" here is therefore a floor on what is spent policing its residents.

### How uniform the numerator is

The denominators are defined identically in every city; the police and fire numerators are not perfectly
uniform, for the reasons above. The 29-city spot check measures how much this matters. Census police
plus fire divided by the city's own department-level budget schedule (a conservative comparison, since
Census counts all funds and the schedules are general fund only):

| | |
|---|---|
| median | 1.03 |
| interquartile range | 0.96 to 1.11 |
| within 10% | 16 of 29 |
| within 20% | 25 of 29 |
| outside 20% | Los Angeles 1.56, St. Louis 1.36, Fort Worth 1.24, Las Vegas 0.56 |

Half the interquartile range is about 7% of the figure, so a share of 25% carries a typical numerator
uncertainty of roughly two points (one point at 15%, two and a half at 35%). Rankings that separate
cities by less than that are not meaningful, and a minority of cities are off by much more. Cities
outside the 29 are unverified on this point.

## 3. Denominators

Never say "budget" without saying which one. Each share is published against four denominators:

| column suffix | definition | use it when |
|---|---|---|
| `_pct_total` | all expenditure characters (E F G I J L M Q S), i.e. Census total expenditure less insurance-trust expenditure. Employee-retirement codes (X11 benefit payments) appear only in the 2012 to 2015 public files and are dropped from the unit file from 2017 on, so they are left out in every year to keep the series comparable | you want "every dollar the city government spends" on services, utilities included |
| `_pct_general` | total minus utilities (functions 90-94: liquor, water, electric, gas, transit) | the standard Census "general expenditure"; removes the CPS Energy / Austin Energy / LADWP effect |
| `_pct_general_ex_edu` | general minus education (09, 12, 16, 18, 21) | comparing cities that run schools (New York, Boston, Baltimore, Virginia cities, most New England cities) to cities that do not |
| `_pct_core` | general minus education, minus county-type functions (corrections 04/05, hospitals 36, welfare 77/79), minus health other than hospitals (32), minus airports and seaports (01, 87). Judicial and legal (25) is kept: it holds municipal courts and city attorneys every city runs, and is only 0.8% of plain municipalities' general expenditure against 1.7% for consolidated governments. Health is removed because it is 0.6% versus 4.1% ($2.8B in San Francisco, $2.2B in Philadelphia); removing it lifts San Francisco's core share from 12.0% to 16.4% and Philadelphia's from 13.0% to 17.4%, while the plain-municipality median moves from 30.9% to 31.4% | the closest thing to an apples-to-apples "municipal services" denominator across consolidated city-counties, independent cities, and plain municipalities |

**The Fiscally Standardized basis over-allocates county police to large cities.** Lincoln FiSC adds a
population share of the county's police spending to each city: Houston's FiSC police is $1,228M against
$981M on its own books, the $247M difference being almost exactly Houston's population share of the
$513M Harris County Sheriff budget. The median uplift across 133 matched cities is 20%. That is correct
where the county force actually polices the city (Las Vegas Metro), but most county sheriff patrol
covers unincorporated areas and contract towns, not large cities with their own departments. The FiSC
basis is fair on education, health, courts and jails; on police it overstates what city residents
receive. It is kept as a denominator with this caveat rather than adjusted, because FiSC does not
publish the county components needed to remove patrol.

**For consolidated city-counties the "county" component is not a county at all.** Indianapolis, Nashville,
Louisville and Jacksonville have no county government in the Census records, yet FiSC still reports a county
police component for each. Traced to the dollar in 2022, that component is the police spending of *the other
municipalities inside the county area*: Indianapolis $21.4M is Lawrence, Beech Grove, Speedway, Southport and
six smaller towns; Nashville $10.0M is Goodlettsville, Belle Meade and Berry Hill; Louisville $26.1M is
Jeffersontown, St. Matthews and 52 other small cities; Jacksonville $20.2M is Jacksonville Beach, Atlantic
Beach, Neptune Beach and Baldwin. Philadelphia and Denver, which have no separately incorporated places
inside their boundaries, show zero. So on the FiSC basis a consolidated city is charged for its neighbours'
police departments, which inflates its police figure by 4% (Jacksonville) to 13% (Louisville). FiSC's
`city_only` view is unaffected and still equals the Census municipal record exactly.

Note that none of these is the **general fund** share quoted in news coverage and city budget messages.
General fund shares are typically 2 to 3 times higher (Houston and Phoenix about 70% of the general
fund versus 28% and 30% of general expenditure; Chicago 46% versus 20%) because the general fund excludes enterprise funds, capital projects, grants, and
debt service. General fund denominators are not comparable across cities because each city decides what
lives in its general fund. We record general-fund figures only in `data/spotcheck/`, from the cities'
own documents, and only to validate the numerators.

## 4. Data-quality fields carried on every row

- `police_flags`, `fire_flags`: the set of Census imputation flags on the summed items. `R` reported;
  `I` imputed by Census (the city did not report that item); `A` analyst correction; `S` alternative
  source (typically the city's audited financial report). Treat `I` as an estimate, not a fact.
- `unit_imputed_share`: fraction of the city's total expenditure dollars that were imputed.
- `record_complete`: false when the unit reports zero police spending (every 100k+ city has a police
  department or a police contract, so zero is a missing item), fewer than 30 item codes, or zero general
  expenditure. Zero fire can be real (see `fire_external`). Shares are null on incomplete records so they
  cannot be averaged in. 27 of 3,695 city-years are incomplete.
- `full_census_year`: true for 2012, 2017, 2022.

## 5. Comparability flags (`data/census_out/city_flags.csv`)

Derived from the data itself for the latest full-census year, so the rules are inspectable:

- `runs_schools`: education over 5% of general expenditure.
- `consolidated_or_independent`: a fixed list of consolidated city-counties, city-parishes and independent
  cities (New York, Philadelphia, San Francisco, Denver, Washington, Nashville, Indianapolis, Jacksonville,
  Louisville, Lexington, Baton Rouge, Lafayette, New Orleans, Augusta, Columbus GA, Macon, Athens, Kansas
  City KS, Honolulu, Anchorage, Baltimore, St. Louis, and every Virginia city). A threshold rule alone
  misses several of these (Louisville 2.5%, Jacksonville 0.2%, Baltimore 0.1%, Honolulu 0.6%).
- `county_like_functions`: corrections + hospitals + welfare over 3% of general expenditure, kept as a
  data-driven complement. It also catches cities that own a hospital (Norman OK, Cambridge MA).
- `fire_external`: zero fire spending on a complete record. Fire is provided by an independent fire
  district or county agency whose spending is not on the city's books (Irvine, Lakewood CO, Port St.
  Lucie, Elk Grove, Simi Valley, Thousand Oaks, Renton and others).
- `police_contracted`: police under 5% of core expenditure. Police is bought from another government
  (Las Vegas via the joint Metropolitan Police Department; Lancaster CA via the Los Angeles County
  Sheriff).

## 5a. Employment (Phase 2)

Source: Census Bureau Annual Survey of Public Employment & Payroll and the Census of Governments:
Employment, individual unit files 2012 to 2025 (`data/census_raw/apes/`). Built by
`pipeline/employment.py` into `data/census_out/city_employment_all_years.csv`.

- **Item codes.** 062 police protection, persons with power of arrest (sworn); 162 police protection,
  other (civilian); 024 fire protection, firefighters; 124 fire protection, other; 000 all functions.
- **Reference period.** Full-time and part-time employees and gross payroll for March of year Y (31-day
  monthly equivalent). Payroll includes overtime paid that month and excludes employer pension and
  benefit costs.
- **Join.** Positions 1-72 of the record are identical in every year. From 2021 the file carries the same
  6-digit unit ID as the finance files; earlier years map the 14-character legacy ID through the Census
  PID/GID crosswalk. Where both exist (2021 to 2025) they agree on every record; the build fails if not.
  Population is taken from the employment ID file and equals the finance file's population for all 332
  cities in 2022.
- **Flags.** Reported: R, C, K, U, V, Z. Prorated (`T`): the city reported a total that Census split across
  functions using last year's proportions, so the sworn/civilian split is an estimate. Imputed: anything
  else. In 2022, 191 cities' police counts are reported, 31 prorated, 88 imputed. Carried per row as
  `police_flag_class` and `fire_flag_class`.
- **Prorated is not imputed.** Imputation estimates a value the agency never reported. Proration takes
  a unit total the agency *did* report and splits it across functions by last year's distribution, so
  the total is real and only the sworn-versus-civilian division is modelled. They are reported
  separately everywhere, including `compare_fbi.py` and `validation/REPORT.md`, where prorated had
  previously been computed and then dropped from the summary. Against the FBI's independent count they
  validate about equally badly, so the distinction matters for interpreting a figure rather than for
  ranking its quality:

  | staffing class | city-years | within 10% of the FBI count |
  |---|---|---|
  | reported | 1,499 | 82% |
  | imputed | 546 | 58% |
  | prorated | 192 | 57% |

- **Modelled staffing is not filtered out of the analysis**, and filtering would not be an improvement:
  dropping the modelled cities trades measurement error for selection on whatever makes an agency
  answer a survey, and loses a third of the sample. `findings.py` instead computes
  `staffing_robustness`, the crime-to-staffing correlation by class with Fisher intervals, which the
  findings piece publishes. The relationship survives in every class and is weakest where Census
  estimated the number outright (+0.32 imputed against +0.57 reported) - the signature of measurement
  error diluting a relationship rather than inventing one.
- **Derived measures.** Full-time sworn officers and firefighters per 1,000 residents; annualized pay
  (March full-time payroll x 12 per full-time sworn officer or firefighter), nominal and in constant
  dollars. A single March can carry retroactive raises, cash-outs, or unusual overtime, so pay for any one
  city-year is noisy; use it for broad comparison only.
- **Civilian counts are published but not recommended.** They agree with the FBI's civilian counts within
  10% for only 40% of reported city-years (median ratio 0.94), because cities place dispatchers, records,
  and forensic staff in police departments or in separate departments inconsistently.
- **Deliberately not produced:** finance expenditure divided by employees. Code 62 dollars carry pension
  and benefit costs city by city (section 2), so dollars per officer would measure accounting, not pay.
- **Scope limits.** Contract and joint-force cities count only the city's own employees (Las Vegas: 91
  marshals, not Metro's 4,102 officers). Combined public-safety departments (Sunnyvale CA) split officers
  between the police and fire codes.

## 5b. Constant dollars (Phase 2)

- **Index.** CPI-U, U.S. city average, all items, not seasonally adjusted (BLS series CUUR0000SA0),
  annual averages 1966 to 2025 from the BLS Public Data API, committed as `data/cpi/cpi_u_annual.csv`
  and cross-checked against FRED CPIAUCNS (largest difference 0.06 index points). The 2025 annual
  average is BLS's published figure; October 2025 was not collected because of the federal shutdown.
- **Alignment.** Census fiscal year Y covers fiscal years ending July Y-1 to June Y, whose midpoints all
  fall in calendar year Y-1, so finance dollars for Census year Y are deflated with the calendar Y-1
  average. Employment payroll is a March Y snapshot and uses the calendar Y average.
- **Base.** The latest complete calendar year (currently 2025). Columns ending `_real_usd` and
  `_real_per_resident` are in those dollars; `real_dollar_base_year` names it on every row.
- **Per resident.** Constant-dollar police and fire divided by residents, in the long series
  (`police_fire_real_per_resident`). Residents only: cities with large commuter or visitor populations
  look higher per resident than their service load implies.
- **Both deflators are published.** CPI-U answers "what would this spending buy a household today".
  The BEA implicit price deflator for state and local government consumption expenditures and gross
  investment answers "how much more policing and fire protection did the money actually buy", which is
  the better question for whether spending grew. Government prices rise faster because the work is
  labour and does not get manufacturing's productivity gains: over 1971 to 2021 that index rose 8.24x
  against roughly 7x for consumer prices.
- **The choice is worth 37 points of growth.** On the balanced panel, median real police and fire
  spending per resident from 1972 to 2022 rises **1.99x on CPI-U and 1.62x on the government
  deflator** ($390 to $778 against $466 to $754). Neither is flat; "doubled" is true only of the
  consumer-price version, so the findings piece reports both and does not use the word. Series:
  FRED `A829RD3A086NBEA`, committed as `data/deflator/bea_state_local_deflator.csv` with its
  provenance in `data/deflator/SOURCE.md`; computed in `findings.py` as `trend.govt_deflated`.
- **Shares are unaffected** by the deflator choice, since numerator and denominator share it.

## 5c. Regional price parities (Phase 2)

- **Source.** BEA Regional Price Parities by metropolitan statistical area, 2008 to 2024 (released
  2026-02-19), all items and housing services, U.S. = 100 (`data/rpp/rpp_msa.csv`).
- **Geography.** Each city goes to the metro area of the county named in its 2022 Census unit ID,
  using the July 2023 OMB delineation that BEA itself uses; the 2022 IDs already carry Connecticut's
  planning regions. All 332 cities map. As a cross-check the city's place code is run through the 2020
  place-by-county file; the three disagreements (Raleigh, Cary, High Point, each split across two
  counties) are resolved correctly by the unit-ID county. Output `data/census_out/city_rpp.csv`.
- **Use.** `police_fire_real_rpp_per_resident` in the long series divides constant-dollar spending per
  resident by the metro price level of calendar year Y-1 (the same alignment as CPI), for Census years
  2009 to 2025. 2022 metro price levels across the 332 cities run from 85 to 118; San Francisco's
  per-resident spending falls from $1,734 to $1,445, El Paso's rises from $531 to $572.
- **What it is not.** RPP is a consumer price index dominated by rents. It is a fair proxy for regional
  living costs and loosely tracks the pay a city must offer, but it does not measure public-sector
  compensation, so adjusted figures are labelled price-adjusted, not labor-cost-adjusted.

## 5d. Peer cities (Phase 2)

`pipeline/peers.py` gives every city the 8 most similar cities with complete 2022 records
(`data/census_out/peer_groups.csv`). Distance adds:

| component | contribution |
|---|---|
| structure | 1.5 for each mismatch in consolidated or independent status, runs schools, outside fire district, contract police; 1.0 for the county-function flag |
| size | absolute log2 of the population ratio (twice or half the size adds 1.0) |
| prices | absolute difference in 2022 metro price level divided by 10 |

The weights are judgment calls, stated so they can be changed. Peer sets are stable against them:
scaling the structural weights by two thirds or by one and a half keeps 96 to 97% of peers on average,
and halving or doubling the size or price terms keeps 82 to 84%. Each group is labelled `close`
(median peer distance under 1.5, 304 cities), `loose` (under 3.0, 21 cities) or `weak` (3.0 or more,
or every peer differs on a structural flag; 7 cities: New York, Seattle, Las Vegas, Lancaster, Kent,
Lafayette, Cambridge). A weak group still lists 8 cities, but the label says they are not like it.
**Fact sheets do not print an ordinal rank.** A position in a total order over nine shares whose own
uncertainty is about two points is mostly decided by noise, and a caveat sitting beside a rank does
not stop a reader reading the rank. Each sheet instead says how many peers have a clearly lower or
clearly higher share, counting only gaps wider than two points, and names the rest as
indistinguishable. That statement survives the noise floor and is more informative for an outlier
than a rank was, while telling a city in a tight cluster that the ordering means nothing.

## 5f. County jails and courts (Phase 2)

`pipeline/county_alloc.py` adds, for Census years 2012, 2017 and 2022, a population share of the overlying
county government's corrections (functions 04 and 05) and judicial and legal (25) spending to each city
(`data/census_out/city_county_allocation.csv`).

- **Not allocated: county police.** County sheriff patrol mostly covers unincorporated areas and contract
  towns, not cities with their own departments (the adversarial audit's point; the Lincoln Institute's
  FiSC basis does allocate it). The exception is a city flagged `police_contracted`, whose police force
  is the county's: Las Vegas receives 28% of Clark County's $869M police spending ($248M, close to the
  city's actual 36.4% share of Metro's $648M budget), Lancaster 1.7% of Los Angeles County's.
- **Shares.** City population in each county it spans, over that county's population, from the Census
  Bureau population estimates by place within county, same year. Houston draws 47.1% of Harris County,
  4.8% of Fort Bend and a sliver of Montgomery.
- **Consolidated and independent cities.** No separate county government exists in the Census records for
  Philadelphia, San Francisco, Nashville, Jacksonville, Louisville, Indianapolis, St. Louis, Baltimore,
  Washington, or any Virginia city; nothing is allocated, and their own corrections and courts are counted
  instead. The combined measure `public_safety_and_justice_usd` (police, fire, own corrections and courts,
  allocated county corrections and courts, and contract county police where flagged) is therefore defined
  the same way whatever the structure.
- **Not included.** State-funded courts and prisons, which are on no local record; this is why Boston,
  whose Suffolk County government was abolished and whose sheriff and courts are state-run, receives no
  allocation. Four places are absent from the estimates file under their Census place codes (Athens-Clarke,
  Louisville, Nashville, Honolulu); all four have no county government, so the fallback changes nothing.
- **Per resident, constant dollars.** Offered per resident rather than as a share, because a share would
  need the county's whole budget allocated into the denominator, which reintroduces the patrol problem.

## 5g. Reported crime (Phase 2)

Source: FBI Uniform Crime Reporting Return A master files 2012 to 2024 ("Offenses Known and Clearances by
Arrest"), agency level, card 1 actual offenses (reported minus unfounded), summed over the months reported
(`data/fbi/fbi_offenses.csv`, `data/fbi/NOTES.md`). Joined by `pipeline/crime.py` to the 332 cities
(`data/census_out/city_crime.csv`).

- **Measures.** Violent crime (murder and nonnegligent manslaughter, rape, robbery, aggravated assault),
  property crime (burglary, larceny, motor vehicle theft), murders; rates per 1,000 residents (murders per
  100,000) using the Census population used everywhere else here.
- **A trap in the source.** The Return A field labelled "Assault Total" includes simple assault; aggravated
  assault is that field minus simple assault. Validated against the FBI's published 2019 city tables below.
- **Coverage.** `full` (12 months), `partial` (rate withheld), `missing` (no report; 2021 is the gap year,
  when the FBI accepted only incident-based reports and New York, Los Angeles, Phoenix, San Jose,
  Jacksonville, San Francisco and others filed nothing), `not_city` (the reporting agency covers more than
  1.5 times the city's population, e.g. Las Vegas Metro; rate withheld).
- **Consistency.** From 2020 a city-year is flagged `break_low` or `break_high` when violent crime falls
  below 0.6 or rises above 1.8 times the city's own 2015 to 2019 median (or property crime below 0.5 or above
  2 times). The reporting-system change left some agencies filing incomplete years that still claim 12
  months: Chicago's violent crime reads 25,553 in 2019, 7,766 in 2021 and 14,321 in 2022. 102 city-years
  are flagged, most in 2021 and 2024. Flagged rates are published with a warning, not removed, since a
  real change can trip the flag.
- **Not produced:** a spending-versus-crime quadrant or any efficiency label. Crime per resident overstates
  risk where daytime population is far above resident population, and reported crime depends on reporting
  practice; the adversarial audit's point stands.

## 5h. Policy annotations and fact sheets (Phase 2)

- **Annotations** (`data/annotations.csv`) mark the trend chart: four national events (the 1994 Crime Act and
  its COPS hiring grants, the 2008-2010 recession, the 2020 CARES Act, the 2021 American Rescue Plan funds)
  and four state fiscal limits shown only to cities in that state (California Proposition 13, Massachusetts
  Proposition 2 1/2, Colorado TABOR, Texas Senate Bill 2). Each carries a note and a source link. Per-city
  milestone lists were considered and rejected: 332 hand-researched event lists would not stay current.
  Markers say when something happened, not that it caused what the line does.
- **Fact sheets** (`pipeline/factsheets.py` to `site/factsheets/`) render one self-contained page per city:
  2022 figures on all four denominators, per resident in constant and price-adjusted dollars, data-quality
  flags and known issues, staffing, reported crime, county jails and courts, the series since 1967, and the
  peer group. No scripts, inline styles, prints cleanly, about 9 KB each. The dashboard carries a
  print stylesheet so printing it produces the same sheet for the selected city; a download button is not
  possible because the published-artifact sandbox blocks page-initiated downloads.

## 5e. Known source-data issues

`data/known_issues.csv` records problems in a specific city-year's Census record that validation has
traced to the source, with evidence. They are appended to that city's notes in `city_flags.csv` and
shown on the dashboard; the Census values themselves are not altered.

- **Build stamps come from the computation, not the clock.** `findings.py` records the date it computed
  the numbers into `findings.json`, and the page renders that. This matters because the deploy
  re-renders the page to inject its fact-sheet links: stamping at render time made the container claim
  a later build date than the committed and published copies, which it did for a day. `deploy_site.ps1`
  now refuses to deploy if the two stamps disagree, so the failure is loud rather than silent.

## 5i. Keeping it current

Five sources refresh on different cadences: Census finance and employment around mid-year, FBI in the
autumn, BEA regional prices in winter, CPI each January. `pipeline/poll_sources.py` checks all five and
records what it saw in `data/source_state.json` (committed, so the first run after a clone is quiet).
Exit code 10 means something changed; `scripts/refresh.sh` is the cron wrapper.

`pipeline/rebuild.py` re-runs every step and writes `validation/REFRESH_REPORT.md`: steps and timings,
years added, how many past city-years moved by more than half a point, and each validation headline
before and after. It exits 2 if a step failed and 3 if history moved a lot or a headline got worse.
A rebuild from unchanged inputs is byte-identical, so any movement in that report is real.

Downloading a new Census year is deliberately manual. Twice in this project a new year arrived with a
changed file name or record layout; the URLs are in section 1 and the poller says when a year appears.
The 654 MB Willamette file is not needed for a refresh: the normalized extract it produces is committed,
and the pre-2012 rows it feeds never change.

## 6. Pipeline

```
python pipeline/build.py        # parse all years -> data/census_out/
python pipeline/checks.py       # aggregate + year-over-year checks -> validation/
python pipeline/compare_vera.py # and the other compare_*.py scripts
python pipeline/cpi.py          # refresh CPI-U from BLS (optional; result is committed)
python pipeline/employment.py   # employment join -> city_employment_all_years.csv
python pipeline/employment_checks.py
python pipeline/compare_fbi.py
python pipeline/rpp.py          # after build.py; before compare_willamette.py
python pipeline/peers.py --sensitivity
python pipeline/county_alloc.py && python pipeline/compare_county_alloc.py
python pipeline/crime.py
python pipeline/factsheets.py
python pipeline/poll_sources.py   # monthly; exit 10 = something new upstream
python pipeline/rebuild.py        # re-run everything and diff against the committed baseline
```

Stdlib Python only. Raw downloads are gitignored and re-fetchable from the URLs above.

## 7. Known artifacts in the source files

- **Capital outlay coding changed in 2022.** Through 2021 the unit files carry F (construction) and G
  (other capital outlay) separately; from the 2022 file onward no G codes are published and F carries all
  capital outlay. `police_usd` and `fire_usd` sum E+F+G in every year so totals are consistent, but
  `*_capital_usd` should not be split into construction vs equipment across that boundary.
- **One-year spikes consistent with pension obligation bonds.** Several California cities show general
  expenditure and police current operations roughly doubling for a single year in 2021 or 2022 and then
  reverting (Huntington Beach 2021, Pomona 2021, Corona 2022). Each issued pension obligation bonds in
  that window; a lump-sum payment to CalPERS is a payment to another government's retirement system and
  is therefore booked as current operations expenditure of the function involved (see section 2). These
  city-years are listed in `validation/yoy_anomalies.csv`; treat their shares as non-representative.
- **Contract transitions.** Spokane Valley WA shows near-zero police through 2020 and about $22M from
  2021, with no change in service: the sheriff contract moved from intergovernmental coding to code 62.
- **The balanced panel is not a cross-section.** Any 50-year trend uses only cities with a complete
  record in every decade year, currently 131 of the 327 with a complete 2022 record. That is required
  - an unbalanced panel measures who entered the sample, not how budgets changed - but surviving fifty
  years of continuous reporting selects for the older and the larger. The panel is 48% Sunbelt against
  74% of the cities it excludes, median population 263,094 against 125,587, and the excluded cities
  spend a median 29.0% of their budgets on police and fire today against 25.5% for the panel. The
  direction does not depend on the panel: over 2012 to 2022 the 324-city panel moves 27.6% to 27.8%
  and the 131-city panel 24.7% to 25.5%. The level does. Computed in `findings.py` as
  `panel_composition`.
- **The long series changes denominator at 2012.** Rows for 1967 to 2011 and 2016 take
  `general_expenditure_usd` from the Willamette compilation. In the overlapping years its figure equals
  ours for roughly 80% of cities but is broader for cities that own utilities, because it carries some
  utility interest and utility transfers. Police and fire dollars are identical; only the denominator
  shifts. The step is negligible for most cities (New York 8.6% in 2011 to 8.7% in 2012) but real for
  utility owners: San Antonio 27.4% to 30.7%, and Austin and Jacksonville similarly. Subtracting
  Willamette's utility-interest column does not reconcile the two (it matches fewer cities, and
  overshoots San Antonio to 32.4%), so no numeric correction is applied. The dashboard draws every
  segment that touches a Willamette year dashed so the seam is visible; treat a jump at 2012 in a
  utility-owning city as a definitional artifact.
- **Dollars are nominal.** Shares are scale-free, but the dollar columns are not inflation-adjusted;
  deflate with CPI-U before comparing dollars across years.
- **Published state totals for 2012-2015** use Census alphabetical state codes (01 AL, 02 AK, 03 AZ ...),
  not FIPS. `checks.py` maps them.
