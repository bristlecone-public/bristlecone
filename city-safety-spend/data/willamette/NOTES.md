# Willamette Government Finance Database — municipal subset

## What this is

The Government Finance Database (GFD) assembled by Kawika Pierson, Michael L. Hand and
Fred Thompson at Willamette University's Atkinson Graduate School of Management. It is a
re-packaging of the **same** Census Bureau source this project uses directly — the Census of
Governments / Annual Survey of State & Local Government Finances individual unit files —
with the raw object+function codes (E62, F24, …) replaced by natural-language column names
and all years stacked into one panel.

**It is therefore not an independent check on our Census parse.** It is a check on our
*processing* of the Census files: if our numbers disagree with Willamette's, one of the two
parses is wrong, because the underlying microdata are identical. Treat it as a replication
partner, not as a cross-validation source in the sense of `docs/CONVENTIONS.md`.

Citation:

> Pierson, K., Hand, M. L., & Thompson, F. (2015). The Government Finance Database: A Common
> Resource for Quantitative Research in Public Financial Analysis. *PLoS ONE* 10(6): e0130119.
> doi:10.1371/journal.pone.0130119

## Access

- Landing page: https://my.willamette.edu/site/mba/public-datasets
- Download (public Google Drive, "Municipal" file):
  https://drive.google.com/file/d/1oiH2jRpupXYtnxDWwys3_Z_aAcHxoHYp/view?usp=sharing
- ICPSR mirror (study 37641) was not needed.
- Retrieved: **2026-09-14**.

The Drive file is large enough to trigger the virus-scan interstitial, so a plain `curl` gets
an HTML page. `pip install gdown` then `python -m gdown <url>` handles the confirm token
(note: gdown 6.x dropped the `--fuzzy` flag — fuzzy matching is now the default, and passing
`--fuzzy` is an error).

Raw files land in `data/willamette/raw/`, which is already gitignored by the existing
`data/*/raw/` rule in the repo `.gitignore` (no new rule was needed; PDFs are also covered by
`*.pdf`).

| file | bytes | sha256 |
|---|---|---|
| `Government Finance Database Municipal Data.zip` | 110,645,216 | `4425fc5d79ab5bd3c02b228371e081ec383e2c85321572d41e9a2a799164bb2b` |
| `MunicipalData.csv` (extracted) | 654,510,085 | `d93ed4aaa0f5be6b6c6c8771f10f2f0c186fa90858927d1588fed8a078d4160a` |

The zip also contains the PLoS ONE paper, the appendix (variable→census-code map plus the
full SAS build code), the Census 2006 classification manual, and the 2017 IUF disclaimer.

`MunicipalData.csv` is 456,773 rows × 593 columns covering **type_code 2 (municipalities) only**.

## Years covered

**1967, 1970–2024.** 1968 and 1969 are absent entirely (they do not exist in the Census
early-file series). That is 56 distinct years.

Census (full enumeration) years — years ending in 2 or 7 — have ~19,000–19,500 municipalities:
**1972, 1977, 1982, 1987, 1992, 1997, 2002, 2007, 2012, 2017, 2022**.

Every other year is the **annual sample**, and the sample size swings enormously:

| era | municipalities per non-census year |
|---|---|
| 1967–1978 | ~3,800–4,800 |
| 1979, 1981, 1984–1986 | ~16,400–17,700 (large-sample years) |
| 1980, 1983, 1988–1991 | ~4,800–8,900 |
| 1993–2000 | ~3,300–3,500 (post-1993 sample cut) |
| 2001, 2003 | ~1,170 (the two thinnest years in the file) |
| 2004–2024 | ~2,900–4,000 |

For **our** universe (population ≥ 100,000) the large cities are effectively a certainty
stratum and are present every year: 130 cities in 1967 rising to 305 in 2024. But sample years
still drop roughly 20–35 cities that *are* over 100k, heavily concentrated in California
(contract-city / county-service places). Example: 33 cities present in the 2022 census year
are missing from the 2021 sample year — Berkeley, Concord, Costa Mesa, Escondido, Garden Grove,
Inglewood, Lancaster, Palmdale, Salinas, Thousand Oaks, Arvada CO, Miami Gardens FL,
South Fulton GA, Nampa ID, Lee's Summit MO, Edinburg TX, and others. **A panel built only on
annual years has a composition break every five years.** 108 of the 351 distinct places in the
100k file appear in all 56 years.

## Units

Census files, and therefore the GFD, report **thousands of nominal dollars**. Every `*_usd`
column in `willamette_municipal_100k.csv` has been multiplied by 1,000 **exactly once** and is
in whole nominal dollars. No deflation applied.

## Variable mapping

Item codes below are the Census object+function codes (62 = police protection,
24 = fire protection), taken from Appendix B of the bundled appendix PDF and confirmed
against the SAS source in Appendix C.

| our column | Willamette column | Census codes |
|---|---|---|
| `gov_id` | `GOVSid` | 9-char Census government ID (state-type-county-unit) |
| `census_id` | `FIPSid` | 14-char FIPS-based Census government ID |
| `place_geoid` | `FIPS_Code_State` + `FIPS_Place` | 7-digit Census place GEOID (derived here) |
| `city` | `Name` | raw, unmodified (e.g. `HOUSTON CITY`) |
| `state` | derived from `FIPS_Code_State` | USPS abbreviation |
| `fiscal_year` | `Year4` | survey year |
| `population` | `Population` | persons |
| `police_usd` | `Police_Prot_Total_Exp` | E62 + F62 + G62 + L62 + M62 |
| `police_direct_usd` | `Police_Prot_Direct_Exp` | E62 + F62 + G62 |
| `police_current_ops_usd` | `Police_Prot_Current_Exp` | direct − capital outlay (≈ E62) |
| `police_capital_outlay_usd` | `Police_Prot_Cap_Outlay` | F62 + G62 |
| `police_construction_usd` | `Police_Prot_Construct` | F62 |
| `police_ig_to_state_usd` | `Police_Prot_IG_To_Sta` | L62 |
| `police_ig_to_local_usd` | `Police_Prot_IG_Loc_Govts` | M62 |
| `fire_usd` | `Fire_Prot_Total_Expend` | E24 + F24 + G24 + L24 + M24 |
| `fire_direct_usd` | `Fire_Prot_Direct_Exp` | E24 + F24 + G24 |
| `fire_current_ops_usd` | `Fire_Prot_Current_Exp` | direct − capital outlay (≈ E24) |
| `fire_capital_outlay_usd` | `Fire_Prot_Cap_Outlay` | F24 + G24 |
| `fire_construction_usd` | `Fire_Prot_Construction` | F24 |
| `fire_ig_to_state_usd` | `Fire_Prot_IG_To_State` | L24 |
| `fire_ig_to_local_usd` | `Fire_Prot_IG_Local_Govts` | M24 |
| `total_expenditure_usd` | `Total_Expenditure` | all E/F/G/I/J/L/M/Q/S + X11,X12,Y05,Y06,Y14,Y53 |
| `general_expenditure_usd` | `General_Expenditure` | E/F/G 01–89 + J19,J67,J68,J85 + I89 |
| `fy_end_date` | `FYEndDate` | MMDD, see caveat below |
| `pop_year` | `YearPop` | 2-digit vintage year of the population figure |

`General_Expenditure` excludes liquor (90), the four utilities (91–94), insurance-trust
benefits and utility debt interest — i.e. exactly the `general_expenditure` denominator
defined in `docs/CONVENTIONS.md`. `Total_Expenditure` matches the conventions
`total_expenditure` definition. Mapping to the conventions agent schema: `denominator_usd` =
`general_expenditure_usd` with `denominator_type` = `general_expenditure` (or the total column
with `total_expenditure`); both denominators are carried side by side rather than melted.

Note the GFD's `*_Current_Exp` columns are computed as *direct minus capital outlay*, not read
straight from E62/E24. Arithmetically identical, but it means a bad capital-outlay value
propagates into current ops.

## The 2012 (really 2017) ID change — how the GFD handles it

The Census replaced its historic 9-digit government ID with a 14-digit FIPS-based ID. The GFD
carries **both** keys on every row (`GOVSid` and `FIPSid`) and backfills across the break, so a
straightforward `GOVSid` join reconstructs the full 1967–2024 panel for almost every city.
Contrary to what "2012 ID change" suggests, in this file the break actually shows up at
**2017**, not 2012: `FIPSid` is blank on some pre-2017 rows (54 municipalities in 1967, 487 in
1972, tapering to 2–3 by 2016) and `GOVSid` is blank on some 2017+ rows (35–108 municipalities
per year). Within the 100k universe `FIPSid` is complete for all 12,230 rows and `GOVSid` is
missing on only 43.

**The trap — Connecticut.** All five CT cities over 100k (Bridgeport, Hartford, New Haven,
Stamford, Waterbury) lose their `GOVSid` from 2017 onward **and** their `FIPSid` changes,
because the county segment of the ID switched from county FIPS to the planning-region/COG
code. Hartford: `GOVSid 072002002` / `FIPSid 00092003161441` through 2016, then blank `GOVSid`
and `FIPSid 00092110161441` from 2017. South Fulton GA (incorporated 2017) likewise has no
`GOVSid`. **Neither supplied ID is a safe panel key across 2016/2017.** That is why this file
adds `place_geoid` (state FIPS + place FIPS): it is present and internally consistent on all
12,230 rows, unique within year, and stable across the break. Use `place_geoid` to join.

## Known issues found in this file

1. **`Total_Expenditure` is overstated for 2007–2021.** The GFD's SAS build code sums `E44`
   (regular highways, current operations) **twice** in `Total_Expenditure` — a visible typo in
   Appendix C, `sum(... E36, E44, E44, E45, E50, ...)`. Empirically the identity
   `Total_Expenditure = Direct_Expenditure + Total_IG_Expenditure` fails for ~99% of 100k-city
   rows in **2007 through 2021**, and the excess equals `Regular_Hwy_Current_Exp` almost
   exactly (all but ~5–9 rows per year). It holds cleanly for 1977–2006 and for **2022–2024**,
   so the newest vintages were built by a corrected or different path.
   *Houston 2012: `Total_Expenditure` 4,664,698k vs Direct+IG 4,540,802k — the 123,896k gap is
   precisely Houston's regular-highway current operations.*
   **Do not use `total_expenditure_usd` from this file as a denominator for 2007–2021 without
   subtracting regular-highway current ops.** 2022 (our headline comparison year) is unaffected.
2. **`General_Expenditure` is clean.** The same typo does *not* appear in the
   `General_Expenditure` sum, and the identity
   `General_Expenditure = General_Current_Oper + General_Capital_Outlay + General_Assist___Sub
   + General_Debt_Interest + IG_Exp_To_State_Govt + IG_Exp_To_Local_Govts` holds for every
   100k-city row in 2008–2024 and almost all of 1977–2006. **Prefer
   `general_expenditure_usd` as the denominator.** Exception: **2007**, where it fails for 121
   of 257 rows. Treat 2007 as suspect on both denominators.
3. `Total_IG_Expenditure` has the same class of typo (`M52` listed twice), and the SAS sum for
   `Total_Expenditure` silently drops `L21`, `L24` and `L50` that Appendix B says should be
   there. Small effects for municipalities, but they mean the two documents do not agree with
   each other.
4. **Police and fire identities are clean** in every year: `police_usd = direct + IG-to-state +
   IG-to-local` and `direct = current ops + capital outlay` hold for all 12,230 rows (a handful
   of pre-1977 exceptions, 1–2 cities/year). The police and fire figures are the trustworthy
   part of this file.
5. **1967–1976 are internally noisy.** `General_Expenditure` fails its component identity for
   10–48 of the ~150 cities per year, and 8–17 cities per year fail the total-expenditure
   identity. These come from the Census early files themselves, not from the GFD recode.
6. **Zero ≠ missing.** Non-reporting is encoded as `0`, not blank, throughout. Any city-year
   with `police_usd = 0` or `fire_usd = 0` must be inspected, not averaged in.
   - Legitimate zeros: cities whose fire service is a separate district or county authority.
     In 2022, 20 cities over 100k report zero fire, almost all in California (Irvine, Elk
     Grove, Concord, Antioch, Lancaster, Norwalk, San Bernardino, Simi Valley, Thousand Oaks,
     Vista-area places) plus Arvada/Centennial/Lakewood CO, Port St. Lucie and Miami Gardens FL,
     South Fulton GA, Renton and Spokane Valley WA.
   - Broken records: Toledo OH reports zero police *and* zero fire with total expenditure of
     only $234.9M (2022) / $255.5M (2023) / $282.5M (2024) — far too low for a 270k city.
     Same pattern for Springfield IL (2022–2024), Syracuse NY (2022), Naperville IL and
     Centennial CO (2023–2024), and Wichita Falls TX 2024 (total expenditure $6.5M).
     Arvada CO 2017 and 2018 have total expenditure of exactly 0.
7. **46 rows in the source have a blank `Year4`.** All are tiny towns with every financial
   field zero and a population vintage of 22; they are dropped here (all are far under 100k).
8. **`FYEndDate` is unreliable before 1977.** It is `0` for 379 of the pre-1977 100k-city rows,
   and where present it is inconsistently 1-, 2-, 3- or 4-digit (`9` vs `930` for September 30).
   From 1977 on it is a consistent MMDD. `YearPop` (population vintage) is blank before 1987.
9. **Population is carried forward, not annual.** Houston shows 1,232,802 for 1970–1973 and
   2,296,224 for 2015–2018. `pop_year` tells you the vintage. Do not treat `population` as a
   current-year estimate when computing per-capita series.
10. **Consolidated city-counties and cities with dependent school systems are not flagged** in
    this file. Use `data/census_out/city_flags.csv` per `docs/CONVENTIONS.md`. Likewise the
    utility-heavy municipal utilities show up only in the total-vs-general gap — San Antonio
    2022 has $6.23B total but $2.95B general because the city owns CPS Energy.
11. **No imputation flags.** The Census IUF's R/I/A/S flag is dropped by the GFD build
    (Appendix C explicitly drops `Data_Flag` and `Imputed_Record`). Any figure sourced from
    this file cannot carry the provenance flag `docs/CONVENTIONS.md` requires — another reason
    to use it only as a replication partner for our own IUF parse.

## Earliest year with usable police and fire data

**1967** — the first year in the file. All 130 municipalities over 100,000 population in 1967
report non-zero police and non-zero fire expenditure, and both the police and fire component
identities hold. The caveats are the *denominators*, not the safety numbers: 1967–1976
`General_Expenditure` is internally inconsistent for a fifth to a third of these cities
(issue 5 above), and 1968–1969 do not exist at all. The first year in which police, fire and
both denominators are all clean for essentially every 100k city is **1977**.

## Output

`willamette_municipal_100k.csv` — 12,230 rows, every municipality-year in the file with
population ≥ 100,000, sorted by year, state, city. 351 distinct places across 45 states plus DC
(no 100k municipality in DE, ME, VT, WV or WY in any year of the file).
Amounts in whole nominal dollars.
