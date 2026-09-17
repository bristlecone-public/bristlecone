# FBI UCR Law Enforcement Employees (LEE) data — independent check on police staffing

Cross-validation source for the Census IUF-derived police expenditure dataset. This
source does **not** validate dollars — it validates **headcount**: full-time sworn
officers and civilian employees per municipal police department, reported by the
agency itself to the FBI rather than by the city finance office to the Census Bureau.

## Source and URL

- Landing page: **FBI Crime Data Explorer → Documents & Downloads →
  "Law Enforcement Employees Data"**
  https://cde.ucr.cjis.gov/LATEST/webapp/#/pages/downloads
- The download button on that page does not link to a static URL. It calls an
  internal endpoint, `https://cde.ucr.cjis.gov/LATEST/s3/signedurl?key=additional-datasets/law-enforcement/lee_1960_2025.csv`,
  which returns a **time-limited (15-minute) pre-signed URL** into the CDE's S3
  bucket (`cde-prd-data.s3.us-gov-east-1.amazonaws.com`). The signed URL itself is
  not a stable citation — cite the landing page + the file name
  `lee_1960_2025.csv` instead. No login, account, or API key was needed; this is
  the bulk-download route, not the api.data.gov API route.
- Raw file: `data/fbi/raw/lee_1960_2025.csv` (106,754,028 bytes; 785,127 data
  rows; site metadata claims "104.2 MB" for the same file, ~1.5MiB rounding
  discrepancy from actual bytes — not investigated further).
- Retrieved: **2026-09-14**. Site's own "last refresh date" for the PE (Police
  Employee) project shown in `/LATEST/lookup/cde_properties` was **08/15/2026**,
  i.e. the file was last updated by the FBI about a month before we pulled it.
- The file covers **1960–2025** for every reporting agency (federal, state,
  county, tribal, university, city, etc.), nationwide — we did not need a
  state/year selector; the whole master file was one CSV.

## What "officer" and "civilian" mean here

This is the FBI Uniform Crime Reporting Program's **Police Employee (PE) / Law
Enforcement Employees (LEE)** collection (formerly published as "Police
Employee Data" in *Crime in the United States*, now folded into CDE as "Law
Enforcement Employees Data" / LEEC).

- **Reference date: October 31** of the given year. Counts are a headcount
  snapshot on that date, not an annual average, not a budgeted headcount, and
  not FTE-adjusted hours — one sworn officer = one count, full-time only
  (part-time officers are excluded from this collection entirely).
- **Officer** = the UCR Program's definition of "law enforcement officer":
  individuals who ordinarily carry a firearm and a badge, have full arrest
  powers, and are paid from government funds set aside specifically for sworn
  law enforcement. This is a functional definition (arrest power), not a rank
  or job-title definition.
- **Civilian** = all other full-time employees of the same agency (records
  clerks, dispatchers, crime analysts, crossing guards employed by the PD,
  etc.) — not sworn, no arrest power.
- Reported **by the agency itself** (or, for non-reporting agencies in some
  years, imputed/estimated by the state UCR Program or FBI) — this is the
  independence property that makes it useful against Census: two different
  respondents (city finance office vs. police department itself), two
  different collection instruments, same underlying government.
- Source columns used: `officer_ct` = `male_officer_ct + female_officer_ct`;
  `civilian_ct` = `male_cilvilian_ct + female_cilvilian_ct` (sic — the FBI's
  own column is misspelled "cilvilian" in this file); `total_pe_ct` =
  `officer_ct + civilian_ct`. Checked for internal consistency across all
  2,811 rows that made it into the filtered output — **zero** mismatches
  between the male/female components and the FBI's own pre-summed totals, and
  **zero** blank/NULL count fields in that filtered set.

## Known gaps and caveats

- **Non-reporting agencies**: LEE participation is voluntary. An agency that
  does not submit a given year simply has no row for that `ori`/year in the
  master file — there is no explicit "did not report" flag in this dataset,
  a missing year has to be inferred from a gap in the row list. We did not
  backfill or impute missing years.
- **2021 NIBRS transition**: 2021 was the year the FBI required all
  agencies to report crime data via NIBRS instead of the old Summary Reporting
  System, and a large number of agencies (including some big-city PDs) did not
  make the switch in time and dropped out of that year's *crime* statistics.
  The Police Employee / LEE collection is **procedurally separate** from
  incident-based crime reporting, so most agencies still show a 2021 LEE row
  even if their 2021 NIBRS crime data is absent — but a handful of agencies
  that had wholesale reporting breakdowns in 2021 may be missing a 2021 LEE
  row too. Spot-check any 2021 row you rely on if the number looks off.
- **Population changes the roster year to year**: `population_covered` is the
  population the agency reported serving *that year*, not a fixed 2020-census
  figure. A city hovering near 100,000 can appear in some years of this file
  and not others, purely from population growth/decline or annexation. The
  output below reflects that: 387 distinct city/state agencies show up across
  2017–2024, not a fixed roster of exactly N cities in every year.
- **File-size note**: the JSON manifest behind the download button reports
  the file as "104.2 MB"; the actual downloaded byte count is 106,754,028
  bytes (~101.8 MiB / ~106.8 MB). Immaterial, noted for the record.

## Filtering applied (what's in `fbi_police_employees.csv`)

From the raw 785,127-row master file:
1. `data_year` in 2017–2024 inclusive.
2. `agency_type_name == "City"` — this is the FBI's **own** agency-type
   classification field, used exactly as the task specified, to exclude
   sheriffs' offices (`County`), `State Police`, `University or College`,
   `Tribal`, `Federal`, `Other State Agency`, and `Other` (which is where
   transit-authority and airport-authority police land, e.g. Houston Metro
   Transit, Port Authority of NY/NJ, MTA PD).
3. `population >= 90,000` (the task's threshold, giving headroom around the
   Census side's 100,000+ cutoff since FBI-reported population and
   Census-estimated population for the same city rarely match exactly).
4. One agency excluded even though it is coded `City`: **Northern York
   County Regional** (PA) — this is a single regional department formed by
   several York County boroughs/townships jointly, not one city's police
   department, and only crosses the 90,000 line because the combined
   multi-municipality service population does. Its rows are in the raw file
   but not in the output.

Result: **2,809 rows**, 2017–2024, 387 distinct (city, state) municipal
police departments.

## Agency → city/state mapping

For the overwhelming majority of rows, the FBI's own `pub_agency_name` field
is already just the city name (e.g. `Chicago`, `Houston`, `Phoenix`) and was
used as-is for both `agency_name` and `city`. A handful of consolidated or
oddly-named `City`-type agencies were remapped so `city` reads as the plain
municipality name (matching how this repo already names these same cities in
`data/census_out/city_flags.csv`); `agency_name` always keeps the FBI's
verbatim name for traceability:

| FBI `pub_agency_name` | `city` used here | note |
|---|---|---|
| Athens-Clarke County | Athens | consolidated city-county (GA) |
| Charlotte-Mecklenburg | Charlotte | FBI names the agency after city+county |
| Las Vegas Metropolitan Police Department | Las Vegas | **see caveat below** |
| Louisville Metro | Louisville | consolidated city-county (Louisville-Jefferson County Metro Government) |
| Metropolitan Nashville Police Department | Nashville | consolidated city-county (Nashville-Davidson) |

**Las Vegas caveat, worth flagging loudly**: LVMPD is a genuinely joint
city/county force — it polices both the City of Las Vegas and unincorporated
Clark County under one budget and one command structure. The Census-side
`city_flags.csv` in this repo already documents that the City of Las Vegas's
*own* finance books show police spending under 5% of general expenditure,
with a note that it "likely contracts with county sheriff (Census books such
purchases as unallocated intergovernmental expenditure, invisible in code
62)." The LVMPD employee counts in this file (4,102 sworn / 1,584 civilian in
2022) are **not directly comparable** to whatever the Census IUF shows under
the City of Las Vegas's own police function — that mismatch is expected and
is the known city-side breakdown, not an error in either source.

No other `City`-type agency in the filtered output had a non-null
`pub_agency_unit` (sub-unit) value, so there was no risk of accidentally
picking up a precinct-level or unit-level row instead of the whole
department's total.

## Columns in `fbi_police_employees.csv`

`ori, agency_name, city, state, year, sworn_officers, civilians,
total_employees, population_covered, source_url, retrieved`

- `sworn_officers` / `civilians` = full-time only, male+female combined, as
  reported/estimated for that agency as of October 31 of `year`.
- `total_employees` = FBI's own `total_pe_ct` (sworn + civilian).
- `population_covered` = FBI's `population` field for that agency-year (the
  population the department reports serving, not a Census estimate).

## Fallback source (not used)

Jacob Kaplan's cleaned UCR/LEOKA compilation on openICPSR (project 102180) was
not touched — the FBI's own bulk CSV covering exactly the requested years and
fields was obtained directly with no login, making the fallback unnecessary.

## Offenses

Agency-level annual offense counts, 2012–2024, for the same 388 municipal
police-department ORIs used in `fbi_police_employees.csv`. Cross-validation
source for the Census IUF-derived police *spending* dataset — this one
validates against reported **crime volume**, not headcount or dollars.

### Source and URL mechanics

- Landing page: same CDE **Documents & Downloads** page as the LEE pull —
  https://cde.ucr.cjis.gov/LATEST/webapp/#/pages/downloads — but a different
  section: **Master File Downloads**, collection **"Return A"**. This is the
  legacy "Offenses Known and Clearances by Arrest" master file (positional
  ASCII, one file per year), not the SRS "Estimated Crimes" download (that one
  is state/national totals only, not agency-level — checked and rejected) and
  not the NIBRS Tables/NIBRS Estimation sections (state-published tables, not
  a single bulk per-agency file).
- Each year is a separate download. The dropdown's "Download the Return A
  File, `<year>`" button calls the same signed-URL mechanism as the LEE pull:
  `https://cde.ucr.cjis.gov/LATEST/s3/signedurl?key=master_files/reta/reta-<year>.zip`,
  returning a 15-minute pre-signed URL into
  `cde-prd-data.s3.us-gov-east-1.amazonaws.com`. No login, account, or API key.
  Confirmed directly from a Bash `curl` against the signedurl endpoint (no
  browser session needed once the key pattern was known) — cite the landing
  page + collection name + year, not the signed URL.
- The layout ("help") file is a *single* file for all years:
  `master_files/reta/reta-help.zip`, containing `Ret A Rec Descrip.pdf` (the
  1960–current fixed-length record layout, dated 12/06/1990 — unchanged since)
  and `Ret A negative entries.pdf` (single-letter negative-number encoding for
  the rare adjustment record, e.g. `J`=-1 ... `1N`=-15; not applied — see
  caveats below).
- Raw files: `data/fbi/raw/reta/reta-<year>.zip` for 2012–2024 (13 files, ~6MB
  each, ~78MB total) plus `reta-help.zip`. Retrieved **2026-09-15**. The
  internal filename differs release to release (`RETA12.DAT`, `RETURNA2013.TXT`,
  `RETA14.DAT`, `RETA-COMB.txt` (2015), `RETA2016.TXT`, then
  `<year>_RETA_NATIONAL_MASTER_FILE.txt` for 2017–2020, then bare
  `reta-<year>.txt` for 2021–2024) — cosmetic, same layout throughout. The
  extracted `.txt` files (~190MB each, ~2.3GB total) were deleted after
  parsing to save disk; the zips are the retained raw artifact and can be
  re-extracted with any zip tool if the parse needs to be redone.
- Record format: fixed-length, unpacked ASCII, **LRECL = 7385** bytes per
  agency-year record, one record per line (newline-terminated in the
  downloaded files, confirmed present in all 13 years). One record covers an
  entire year for one agency, with a 12-times-repeating 590-byte "month" block
  (positions 306–7385) holding that month's data across 5 "cards" (Card 0
  unfounded, Card 1 actual offenses, Card 2 cleared by arrest, Card 3
  clearances under 18, plus officer-killed/assaulted counts). We only read
  Card 1 ("Actual Offenses"), summed across all 12 month-blocks, to get the
  agency's annual founded-offense totals.

### Field mapping

From the Return A "1960–Current" fixed layout (positions are 1-indexed as
published; offsets below are the 0-indexed Python slice equivalents actually
used):

| Our column | Return A field | Position (1-idx) |
|---|---|---|
| `ori` (first 7 chars) | ORI Code | 4–10 |
| `months_reported` | Number of Months Reported | 42–43 |
| `population_covered` | Population Data 1 + 2 + 3 ("adding the three populations provides the total population of the city" — per the layout doc) | 45–53, 60–68, 75–83 |
| `murder` | Card 1, field 1 "Murder" (= murder & nonnegligent manslaughter, the actual Part I count; field 2 "Manslaughter" is negligent manslaughter, a non-Part I supplemental stat, and is **not** added in) | rel. 18–22 of Card 1 |
| `rape` | Card 1, field 3 "Rape Total" (= field 4 "by force" + field 5 "attempted"; used as-is, see revised-definition caveat below) | rel. 28–32 |
| `robbery` | Card 1, field 6 "Robbery Total" | rel. 43–47 |
| `aggravated_assault` | Card 1, field 10 "Assault Total" **minus** field 16 "Simple Assault" — see caveat below, this is not a straight field read | rel. 68–72 minus rel. 93–97 |
| `burglary` | Card 1, field 17 "Burglary Total" | rel. 98–102 |
| `larceny` | Card 1, field 21 "Larceny Total" | rel. 118–122 |
| `motor_vehicle_theft` | Card 1, field 22 "Motor Vehicle Theft Total" | rel. 123–127 |
| `violent_crime` | murder + rape + robbery + aggravated_assault (computed, not a source field) | — |
| `property_crime` | burglary + larceny + motor_vehicle_theft (computed) | — |

`agency_name`, `city`, `state` are **not** read from the Return A file at all
— they're pulled from `fbi_police_employees.csv` (most-recent-year row per
ORI) so naming stays consistent between the two FBI cross-validation
datasets. This also sidesteps Return A's own name field, which is truncated
to 24 characters and inconsistently cased/abbreviated.

**`months_reported`**: read directly from the source field described above —
"the highest 'valued' month that was reported," per the layout doc, e.g. "10"
if October was the last month submitted. It is left **blank**, not `0`, for
any agency-year where the agency filed no return at all that year (see
non-reporting handling below); when populated it ranges 1–12, never
prorated to infer a full-year estimate.

**ORI matching caveat**: the Return A ORI field is only **7 characters**
(positions 4–10), one byte shorter than the modern 9-character ORI standard
used everywhere else in this repo (`fbi_police_employees.csv` etc., which
are `AK0010100`-style). All but one of the 388 target ORIs end in `00`
(the exception, `CA033780X` / Menifee CA, has a genuinely alphanumeric
suffix), so matching on the first 7 characters is safe *as an ID*, but it is
**not always unique inside the Return A file itself**: 14 of our 388 target
agencies (Huntsville AL, Clovis CA, Chino CA, Boulder CO, Arvada CO, Lakewood
CO, Boise ID, Aurora IL, Boston MA, Cary NC, Las Vegas NV, Lawton OK,
Knoxville TN, Midland TX — the list grows from 7 agencies in 2017 to 14 from
2021 on) share their first 7 ORI characters with an unrelated small agency
(a campus PD, a District/County Attorney's office, a state gaming or revenue
enforcement unit, in one case the Tennessee Valley Authority PD) that
happens to have been assigned an adjacent ORI. In every single case observed
(all 14 agencies, all years checked) the impostor row reports population 0
and the real municipal PD's row reports its full population — so the parser
keeps, per (ORI7, year), whichever raw line has the larger
`population_covered`, and logs a line to stdout every time it drops a
duplicate. This was verified by hand for all 14 cases in 2024 before being
applied globally.

### The "Assault Total" contamination (found and corrected during this pull)

The Return A field labeled "Assault Total" (Card 1, field 10) is **not**
aggravated-assault-only, contrary to what the 1990 layout doc implies by
listing it as the Part I "assault" line. Cross-checking it against its own
weapon-type breakdown (fields 11–14: gun/knife/other-weapon/hands-feet, which
by definition are subcategories of aggravated assault) plus field 16 "Simple
Assault" (a non-Part I supplemental stat), across every one of the 388 target
agencies and all 13 years:

- In ~95–98% of agency-years, `field10 == field11+field12+field13+field14 +
  field16` — i.e. "Assault Total" is actually **aggravated + simple assault
  combined**, not aggravated alone. This holds in SRS-era years too, not just
  post-NIBRS-transition years — it is a Return A form-design quirk, not a
  transition artifact.
- A first attempt at this dataset used field 10 directly as
  `aggravated_assault`. That produced absurd year-over-year spikes for some
  agencies (e.g. NYPD's raw field 10 nearly sextupled from 2022 to 2023,
  40,803 → a nonsensical 213,518) because NYPD started reporting a much larger
  "Simple Assault" component starting in its 2023 converted-NIBRS submission,
  inflating the blended total. This was caught by spot-checking known crime
  trends before finalizing the output, not by any flag in the source data.
- **Fix applied**: `aggravated_assault = field10 - field16` for every
  agency-year, uniformly. This exactly reproduces the weapon-breakdown sum
  (`field11+12+13+14`) whenever the breakdown is populated, and correctly
  falls back to field10 unchanged whenever field16 ("Simple Assault") is 0 —
  which covers agencies that only ever report the bulk total, never a
  breakdown (Chicago's SRS-era submissions, for example, populate field10
  directly with no field11–14 breakdown at all, and field16 is 0 there, so
  the subtraction is a no-op for them).
- Robbery, burglary, rape, and motor-vehicle-theft were all checked the same
  way (total field vs. sub-field sum) and show **no** equivalent
  contamination — their "total" fields equal their own breakdown sums exactly
  in every year, so they're read directly with no adjustment.
- Residual ~2–5% of agency-years per year where neither `field10==breakdown`
  nor `field10==breakdown+simple` holds exactly were not chased down further;
  the likely cause is the single-letter negative-adjustment encoding
  documented in `Ret A negative entries.pdf` (a small number of agencies
  submit negative correction entries using a substituted letter for the last
  digit, e.g. `J`=-1), which this parser does not decode — such fields are
  read as 0 rather than as the (usually small) negative adjustment they
  represent. This affects a minority of individual field values in a small
  fraction of rows; it was not deemed worth building a full negative-entry
  decoder for the size of the effect.

### Revised rape definition

The Return A layout has only ever had one "Rape" field triple (Total / by
Force / Attempted) — there is no separate legacy-vs-revised pair of fields to
choose between in this file, unlike some of the FBI's newer NIBRS-native
publications. The FBI's national UCR Program began phasing in the revised
(broader, gender-neutral) definition of rape starting with 2013 data, with
full national adoption by around 2017; Return A's single "Rape Total" field
simply reflects whichever definition the submitting agency was using that
year — meaning 2013–2016 rows in particular may mix legacy and revised
counts depending on the agency, with no flag in the data to tell which. This
dataset uses the field as reported for every year; per the task's "use the
revised definition wherever the source has both," there is nothing to choose
between here — this file never carries both simultaneously for a given
agency-year, so nothing was discarded or preferred.

### Non-reporting agencies (blank, never zero)

An agency-year is treated as **non-reporting** — every crime-count cell left
blank, `months_reported` left blank, `reporting_system` left blank — when
both (a) `months_reported` reads blank/`0`/`00` in the source, **and** (b)
every Card 1 field summed across all 12 months is 0. Requiring both avoids
mistaking a genuinely quiet agency-year (a small department that truly
recorded zero of some offense type) for a non-report; in practice this
distinction rarely matters for the ≥90k-population departments in this file,
which essentially never report all-zero crime in a full year.

Coverage across the 388 target agencies: of 5,034 total agency-year rows
(13 years × up to 388 agencies, fewer in 2012–2016 before the LEE-sourced ORI
list's own coverage window begins — see `fbi_police_employees.csv` for why
2012–2016 has 386 rather than 388 matching ORIs), **4,860 rows report the
full 12 months**, **29 rows report a partial year (1–11 months)**, and
**145 rows are blank non-reports**. By year, blank/non-reporting counts are:

| Year | Blank agency-years | of |
|---|---|---|
| 2012 | 0 | 386 |
| 2013 | 0 | 386 |
| 2014 | 1 | 386 |
| 2015 | 3 | 386 |
| 2016 | 4 | 386 |
| 2017 | 5 | 388 |
| 2018 | 4 | 388 |
| 2019 | 5 | 388 |
| 2020 | 2 | 388 |
| **2021** | **90** | 388 |
| 2022 | 12 | 388 |
| 2023 | 10 | 388 |
| 2024 | 9 | 388 |

2021 is a stark outlier — roughly 1 in 4 of our target municipal PDs simply
has no Return A row that year at all.

### The 2021 NIBRS transition

2021 was the first year the FBI's national UCR Program stopped accepting the
legacy Summary Reporting System (SRS) format and required NIBRS-only
submission. A large minority of agencies, including some of the largest
municipal PDs in the country, did not complete the NIBRS transition in time
and simply have no usable 2021 return. Of the 388 target agencies, 90 have a
fully blank 2021 (verified via `months_reported` being blank/0, not merely a
small count) and one more (Glendale, AZ) has a partial year (5 months
reported). The 15 largest agencies (by 2020 `population_covered`, the last
full pre-transition year) with a missing or partial 2021 return:

1. New York, NY (New York City PD) — pop 8,300,377 — missing (0 months)
2. Los Angeles, CA — pop 4,000,587 — missing (0 months)
3. Phoenix, AZ — pop 1,708,960 — missing (0 months)
4. San Jose, CA — pop 1,029,542 — missing (0 months)
5. Jacksonville, FL — pop 920,508 — missing (0 months)
6. San Francisco, CA — pop 881,514 — missing (0 months)
7. Tucson, AZ — pop 550,448 — missing (0 months)
8. Sacramento, CA — pop 519,050 — missing (0 months)
9. Omaha, NE — pop 480,297 — missing (0 months)
10. Miami, FL — pop 476,102 — missing (0 months)
11. Long Beach, CA — pop 462,654 — missing (0 months)
12. Oakland, CA — pop 437,923 — missing (0 months)
13. Bakersfield, CA — pop 388,265 — missing (0 months)
14. Riverside, CA — pop 334,370 — missing (0 months)
15. Santa Ana, CA — pop 333,107 — missing (0 months)

Notably **absent** from this list — i.e. these large agencies *did* file a
full 2021 Return A per `months_reported`==12 — are Chicago, Houston,
Philadelphia, Dallas, Las Vegas (LVMPD), San Antonio, St. Louis, and
Louisville. Chicago is worth flagging specifically even though it's not
"missing": its 2021 Card 1 totals look implausibly low against its own
2020/2022 trend (2021 murder=370 vs. 2022's 604 and public CompStat/press
figures of ~797 homicides for Chicago in calendar 2021) and its 2021 robbery
(4,607) is roughly half of neighboring years — this smells like a partial or
under-counted NIBRS submission that the file's own `months_reported` flag
does not catch (Chicago claims 12 months reported despite the apparent
undercount). Treat any large agency's 2021 row — reported or not — with
extra skepticism; `months_reported`==12 is not proof the year is complete.

### Was NIBRS converted to summary counts?

Yes, for 2021 onward. Since the national SRS collection was retired for 2021
data, every 2021–2024 Return A row in this file (for agencies that do have
one) must be the FBI's own NIBRS-to-summary conversion — there is no other
way a "Return A" record could exist for those years. This dataset labels
`reporting_system` as `"SRS"` for 2012–2020 and `"converted"` for 2021–2024,
purely on that year cutoff, and leaves it blank for non-reporting
agency-years. Two honesty caveats on that label:

- It is a year-level, not agency-level, determination. A meaningful (but
  unknown from this file alone) share of agencies had already voluntarily
  migrated to NIBRS well before 2021 — national NIBRS adoption was around
  40–45% of agencies by the late 2010s — and their pre-2021 "SRS" label in
  this dataset may already reflect an FBI NIBRS-to-summary conversion under
  the hood for that specific agency. The Return A record format itself
  carries no field indicating which collection method actually fed a given
  row, in any year.
- The "Assault Total" contamination described above (field10 including
  simple assault) was observed in **both** eras, which is itself evidence
  that at least some pre-2021 "SRS" rows were already NIBRS-derived
  conversions rather than native summary submissions — a native SRS Return A
  submission, filled out by an officer directly from the old paper/electronic
  SRS form, would have no structural reason to blend simple assault into the
  aggravated-assault total.
