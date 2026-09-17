# Outstanding Data Issues: Impact and Sensitivity Analysis
## Evaluating How Much Known Discrepancies Alter Substantive Conclusions

> **Verification note (2026-09-15).** Every testable figure was re-checked against the committed outputs,
> twice: a first pass before this file was committed and a full pass afterwards. Corrections are marked
> **[corrected]** and claims that cannot be tested from the repository are marked **[unverified]**.
>
> Verified as written: Houston's FiSC uplift and the 20.0% median across 133 cities; every Chicago crime
> count and rate, and the 102 flagged city-years; Seattle's 0.749 ratio, its $359.5M departmental total,
> the $536.5M statement-of-activities figure and all three legacy-fund amounts ($19.2M police relief,
> $19.9M firefighters, $8.0M judgment and claims); San Antonio's 27.4% to 30.7% step; the Oklahoma City
> and Tulsa variances and their 2017 agreement; the Texas crime medians; and the national employment gap
> of 2,222 officers with 47 of 51 states inside 1%.
>
> Corrected: Seattle's denominator and sensitivity (16.0% is police *and* fire, not police alone); the
> "exact digit across 82 cities" claim; the range for plain municipalities; the Oklahoma City root cause;
> the FiSC uplift range; Indianapolis as a zero-uplift city; Oklahoma City's police total; the date the FBI
> master file was downloaded; and one employment claim that no published source can support.

This document evaluates the seven outstanding data issues identified during the validation and red-teaming of the `city-safety-spend` codebase. Each issue is ranked by its potential to alter substantive empirical findings, accompanied by exact quantitative sensitivity metrics, identified root causes, and recommended analytical guardrails.

---

## Executive Summary & Sensitivity Ranking

| Rank | Issue | Scope / Exposure | Max Sensitivity on Measure | Change to Substantive Conclusion? |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Fiscally Standardized Basis** | 133 large cities (all county overlaps) | **[corrected]** median **+20%**; 18 cities between 30% and 40%, **28 above 40%**, up to **+94%** (St. Petersburg), excluding Las Vegas at +1,377% where the county force *is* the city's police | **HIGH**: Substantially alters cross-city comparisons and city-vs-suburb rankings. |
| **2** | **Chicago Crime After 2021** | Chicago trendline (2021–2024) | **-40% to -70%** artificial drop in reported violent crime | **HIGH for Chicago**: Erroneously implies violent crime collapsed after 2020. No impact on spending. |
| **3** | **Seattle Reads 0.75x Own Police Budget** | Seattle (and 3 other legacy-pension cities) | **[corrected]** +2.8 points of the police-plus-fire share (16.0% -> 18.8%), or +2.9 points on police alone (8.4% -> 11.3%) | **MEDIUM-LOW**: Shifts Seattle's relative ranking; does not alter national distribution. |
| **4** | **2012 Denominator Seam (Utilities)** | Long-time series (1967–2011 -> 2012–2024) for ~12 utility cities | **+2.0 to +3.5 percentage points** abrupt shift at 2012 boundary | **MEDIUM-LOW**: Distorts pre/post-2012 trend slope for utility cities; cross-sectional 2022 data unaffected. |
| **5** | **OKC & Tulsa County Jail Allocation** | Oklahoma City & Tulsa (Phase 2 broader metrics) | **$31.4M** in OKC, **$9.1M** in Tulsa corrections spending | **LOW**: Confined to Phase 2 county corrections; city core municipal spending unchanged. |
| **6** | **Texas Crime Counts vs. Published Tables** | Texas cities (2019 FBI Return A) | **Median 0.94%** (isolated outliers up to 20%) | **NEGLIGIBLE**: Well within normal reporting revisions; leaves all crime tiers intact. |
| **7** | **Employment File vs. Published Totals** | National employment counts | **<= 0.35% nationally**, 47 of 51 states within 1% | **NONE**: Far below statistical noise floor; sworn officer rates unaffected. |

---

## Detailed Decomposition & Sensitivity Assessment

### 1. Fiscally Standardized (FiSC) Basis
* **Nature of the Issue:** The Lincoln Institute of Land Policy's Fiscally Standardized Cities (FiSC) methodology standardizes municipal comparisons by allocating an overlapping population-share of county government expenditure (e.g., County Sheriff, County Jail, Courts) to the central city. However, in major urban counties (e.g., Harris County, TX; Dallas County, TX; Fulton County, GA), the County Sheriff primarily provides primary patrol services to unincorporated county areas, while city taxpayers are patrolled by their own municipal police department. FiSC allocates a population share of the Sheriff's entire patrol budget to the central city regardless of actual service delivery.
* **Quantitative Sensitivity:**
  * In Houston, Harris County Sheriff allocation inflates police spend from **$981M to $1,228M (+25.2%, or +$247M)**. Across 133 large cities, the median uplift in police spend under FiSC is **+20.0%**.
  * **[corrected]** 22 of the 133 have no uplift at all, being consolidated or independent cities with no overlying county
    (Philadelphia, San Francisco, St. Louis, Washington, Virginia Beach, Norfolk, Richmond and so on). **Indianapolis is not
    one of them: its uplift is 8.9%**. Investigated 2026-09-15 and resolved: Marion County has no county government in
    the Census records, and FiSC's county police component for Indianapolis is the police spending of the other
    municipalities inside Marion County - Lawrence, Beech Grove, Speedway, Southport and six smaller towns, $21.4M,
    matching to the dollar. The same holds for Nashville ($10.0M), Louisville ($26.1M) and Jacksonville ($20.2M).
    A consolidated city is therefore charged on the FiSC basis for its neighbours' police forces.
    At the other end the uplift reaches 94% (St. Petersburg), 85% (Hialeah) and 69% (Fresno), so "30 to 40%" is the
    middle of the upper tail, not its limit.
* **Impact on Conclusions:** **VERY HIGH.** Using the unadjusted FiSC police figure severely distorts comparative questions such as *"Which cities prioritize policing most heavily?"* by artificially inflating police spending in central cities surrounded by large, growing unincorporated suburbs.
* **Mitigation in Dataset:** The primary dashboard does not use FiSC police allocations. The Phase 2 county allocation was deliberately restricted to **corrections (`E04` institutions and `E05` other corrections) and courts (`E25`)**, excluding county sheriff patrol (`E62`) except for genuine contract or joint agencies.

---

### 2. Chicago Crime After 2021
* **Nature of the Issue:** In 2021, the FBI retired the legacy Summary Reporting System (SRS) and mandated the National Incident-Based Reporting System (NIBRS). Chicago Police Department (CPD) experienced severe technical transition hurdles. In the FBI master data, Chicago's record is marked as having 12 months reported ("full coverage"), but violent crimes plummeted from **26,583 in 2020 to 7,766 in 2021**, before partially rebounding to **14,321 in 2022** and **15,952 in 2023** (still ~40% below historical averages of ~26,000/year).
* **Quantitative Sensitivity:**
  * Reported violent crime rate per 1,000 residents drops precipitously from **9.87 (2020) to 2.88 (2021)** and **5.35 (2022)**.
* **Impact on Conclusions:** **HIGH for Chicago analyses; ZERO for expenditure conclusions.** Any regression or scatter plot evaluating Chicago's police expenditures against crime rates would show police spend rising while crime fell by 70%, creating a phantom "efficiency" or "de-policing" artifact. However, crime data is strictly contextual in this repository and does not alter budgetary shares.
* **Mitigation in Dataset:** The pipeline's automated consistency check successfully flags Chicago (and 101 other city-years) with `consistency = 'break_low'`. Longitudinal charts must refuse to render an unbroken crime trendline across 2020–2021 for Chicago.

---

### 3. Seattle Reads 0.75x Own Police Budget
* **Nature of the Issue:** In the FY2022 spot-check against Seattle's Annual Comprehensive Financial Report (ACFR), Census `E62` Police is **$269.3M**, whereas the City's General Fund Schedule C-1 budget-control lines sum to **$359.5M** (a ratio of **0.749**).
* **Root Cause & Accounting Mechanics:**
  * Seattle maintains two closed legacy pension systems: the *Police Relief & Pension Fund* ($19.2M) and the *Firefighters Pension Fund* ($19.9M), alongside its Judgment & Claims fund ($8.0M). Active sworn officers participate in Washington State LEOFF Plan 2.
  * The city's budget-basis Schedule C-1 rolls up departmental sub-funds (including legacy pensions and employee healthcare funds), whereas Census abstracted from fund-level or adjusted GAAP statements. Furthermore, the Statement of Activities public safety expense was deflated to $536.5M by massive negative net pension liability adjustments in FY2021.
* **Quantitative Sensitivity:** **[corrected]** Seattle's Census general expenditure is **$3,192M**, not $1,681M, and the
  16.0% figure in the dataset is police *and* fire together, not police alone.
  * Police alone: $269.3M is **8.4%** of general expenditure; at the city's departmental figure of $359.5M it would be
    **11.3% (+2.9 points)**.
  * Police plus fire: **16.0%**, rising to **18.8% (+2.8 points)** if police is taken at the city's figure.
* **Impact on Conclusions:** **MEDIUM-LOW.** Seattle moves up within the pack but stays below the middle: the
  police-plus-fire share across the 235 plain municipalities with complete records runs from **20.3% at the tenth
  percentile to 41.5% at the ninetieth, median 29.5%** (full range 8.3% to 55.4%), so Seattle sits low either way.
  The percentile shift quoted in an earlier draft was not reproduced and is withdrawn.

---

### 4. 2012 Denominator Seam for Utility-Owning Cities
* **Nature of the Issue:** The historical longitudinal dataset (1967–2024) relies on the Willamette Government Finance Database for 1967–2011 and 2016, and on raw Census IUF microdata for 2012–2015 and 2017–2024. Willamette's general expenditure definition mistakenly included utility interest (electric, water) and intergovernmental utility payments.
* **Quantitative Sensitivity:**
  * In cities operating massive municipal electric or gas utilities (e.g., San Antonio's CPS Energy, Austin Energy, Jacksonville JEA), Willamette's pre-2012 denominator was inflated.
  * At the 2012 boundary, San Antonio's police-plus-fire share abruptly jumps from **27.4% in 2011 to 30.7% in 2012 (+3.3 percentage points)**, despite no underlying policy change.
* **Impact on Conclusions:** **MODERATE for the utility cities named above; ZERO for cross-sectional 2022 comparisons,
  and - tested - ZERO for the panel as a whole.** The count of affected cities was never established, so "~12" is
  **[unverified]**; what can be tested is whether the seam year stands out. It does not. Across cities present in both
  years, the 2011-to-2012 move has a median of 1.64 points, against 1.43 for 2012-to-2013 and 1.70 for 2009-to-2010,
  both of which sit entirely inside one source. The share of cities moving more than three points is 26% at the seam
  against 23% and 31% either side. So the seam is real and material for a named handful, and invisible in the aggregate.
* **Mitigation in Dataset:** Reconciling Willamette's utility-interest column overshoots corrections; therefore, no synthetic numeric adjustment is applied. Instead, all chart segments connecting Willamette years are rendered with **dashed lines**, and the seam is explicitly documented.

---

### 5. Oklahoma City and Tulsa County Jail Allocation
* **Nature of the Issue:** In Phase 2 county allocations, our calculated county corrections share for Oklahoma City is **5.15x** FiSC ($39.0M vs. $7.6M), and Tulsa is **1.35x** FiSC ($35.5M vs. $26.4M). In 2017 both matched FiSC within 1% (Oklahoma City $26.9M vs $26.8M; Tulsa $29.5M vs $29.8M).
* **Root Cause:** **[corrected to unresolved]** A 2020 transfer of the Oklahoma County Detention Center to a public
  trust is a plausible mechanism, but the year-by-year evidence does not fit it: Oklahoma City's ratio is **3.17 in 2012**,
  **1.00 in 2017** and **5.15 in 2022**, so the divergence predates the transfer and then disappears for a census year.
  Tulsa behaves differently again (1.00 in 2012, 0.99 in 2017, 1.35 in 2022). Whatever differs between our apportionment
  and FiSC's is not a single 2020 reclassification. Treat the cause as unknown.
* **Quantitative Sensitivity:** A variance of **$31.4M** for Oklahoma City and **$9.1M** for Tulsa.
* **Impact on Conclusions:** **LOW.** This variance only affects the secondary "City + County Public Safety Burden" metric in Phase 2. Core municipal police spend (**[corrected]** $160M in Oklahoma City, with fire at $141M), fire spend, and general
  fund shares remain unaltered.

---

### 6. Texas Crime Counts vs. Published Tables
* **Nature of the Issue:** Comparing parsed 2019 FBI Return A counts against the FBI's published *Crime in the United States 2019* Table 8, **[corrected]** California matched on **74 of 75** cities for violent crime and 75 of 75 for property crime; Illinois
  matched **4 of 7** and 5 of 7, the rest within 0.9%. The earlier draft's "exact digit across 82 cities" overstates it. Texas cities differed across 42 agencies by a **median of 0.94%** in violent crime and **0.30%** in property crime.
* **Root Cause:** **[unverified]** A centralized Texas state repository submitting post-publication updates would explain
  the pattern - the differences run in both directions and cluster in one state - but nothing in this repository tests it.
  What is established is that the file is a later vintage than the published tables: **[corrected]** it was downloaded on
  2026-09-15 and was last modified by the FBI on 2026-08-14, whereas the comparison tables are the 2019 publication.
* **Quantitative Sensitivity:** A median difference of under 1%. A city reporting 1,000 violent crimes might show 1,009 or 991.
* **Impact on Conclusions:** **NEGLIGIBLE.** A 0.9% variance is well within standard statistical noise and does not shift any city's crime rate tier or cross-jurisdictional ranking.

---

### 7. Employment File vs. Published Totals
* **Nature of the Issue:** Aggregating individual agency records in the 2022 Census employment unit file yields 624,372 sworn officers nationally, compared to 626,594 in the Census Bureau's published summary table—a national gap of **0.35%** (2,222 officers).
* **Root Cause:** Routine synchronization lag between published summary releases and later microdata unit reissues (minor state sub-units or late edits present in aggregate tables).
* **Quantitative Sensitivity:** National deviation <= 0.35%; 47 of 51 states within 1% for sworn officers and 46 of 51
  for firefighters. **[corrected]** The claim that individual city headcounts are "exact or within 1 to 2 officers" is
  withdrawn: the Census Bureau publishes these totals by state, not by city, so there is nothing to check a single city
  against. The per-city evidence is the independent FBI comparison instead - sworn counts within 10% for 82% of the
  city-years Census marks as reported, and for 58% of the years it imputed.
* **Impact on Conclusions:** **NONE.** Sworn officers per 1,000 residents and payroll per FTE are identical at standard precision.

---

## Strategic Recommendations for Publication

1. **Maintain Municipal Focus for Headline Findings:** Anchor all primary ranking metrics and headline distributions on the **plain municipal Census IUF basis**, where 20 of 29 spot-checked cities match local ACFRs within 10% and major anomalies (e.g., St. Louis) are fully explained.
2. **Quarantine Post-2020 Chicago Crime:** Require a prominent disclaimer or suppress continuous plotting across 2020–2021 for Chicago and other agencies flagged with `break_low`.
3. **Caveat FiSC Comparisons:** When presenting Fiscally Standardized data, explicitly warn that FiSC allocates county-wide sheriff patrol spending to central-city residents, artificially inflating apparent police spend in fragmented metropolitan counties by ~20%.
