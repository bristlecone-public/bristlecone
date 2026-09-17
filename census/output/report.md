# Cohort residual tracing report

Net migration residuals by cohort, relative to national survival. A negative residual means the unit kept fewer members of that cohort than national survival predicts (net out-migration); positive means net in-migration.

## Population basis (read before comparing decades)

Each decade is traced on one of two bases, labelled below:

- **Household population** (group quarters subtracted): 2010-2020.
- **Total population** (group quarters included): 1950-1960, 1960-1970, 1970-1980, 1980-1990, 1990-2000, 2000-2010.

**Decades on different bases are NOT level-comparable.** Subtracting group quarters (college dorms, prisons, military barracks, nursing homes) moves a college or prison county's young-adult retention rate by tens of percentage points, so a household-basis decade sitting next to a total-basis decade will look like a migration surge or collapse that is really just the basis switch. Compare same-basis decades, or compare a county against its peers within one decade.

Why the split: 2010 and 2020 publish group quarters by sex by 5-year age (the Census PCO1 / DHC tables), so 2010->2020 runs on the household basis. 2000 SF1 tabulates group quarters by sex by age only in three coarse bands (Under 18 / 18-64 / 65+; tables P038 / PCT017) -- enough to confirm the ~7.78M national total, but too coarse to subtract at 5-year resolution -- and the 1990 STF1A county files carry no group-quarters age detail at all. So any decade touching 1990 or 2000 stays on the total-population basis.

## Known caveats and directional biases

The residual is net migration *relative to the national average*, but several other signals ride inside it and bias specific, identifiable county types. Read the rankings with these in mind:

1. **Off-campus students inflate college-town young-adult 'growth' -- even on the household basis.** The Census counts only dormitories and recognized fraternity/sorority houses as group quarters; roughly 65-80% of undergraduates and over 95% of graduate students live off-campus and are tabulated as *household* population. So subtracting group quarters removes dorm residents but NOT the far larger off-campus student influx. The top young-adult-gaining counties on the 2010->2020 household basis are therefore still dominated by university towns -- Charlottesville (UVA), Clarke GA (UGA), Harrisonburg (JMU), Riley KS (KSU), Whitman WA (WSU), Story IA (ISU), Montgomery VA (Virginia Tech) -- and that ranking largely measures off-campus university enrollment, not economic in-migration.

2. **International immigration inflates gateway metros and penalizes rural counties.** The survival ratio is a single national number, and it absorbs net international migration, which concentrates in a handful of gateway metros (Miami, New York, Houston, Los Angeles, Chicago, Dallas). Those counties post positive residuals that are really foreign arrivals, not domestic attraction. The same immigration-boosted national ratio inflates the *expected* count everywhere, so low-immigration rural and Midwestern counties are penalized and can be mislabeled as domestic out-migration when they are merely not receiving immigrants.

3. **Undercount and young-adult mortality masquerade as out-migration.** The method treats every uncounted person AND every death as an out-migrant. The biggest 'out-migration' counties are disproportionately tribal (Rolette, Benson ND), high-poverty Mississippi Delta (Phillips, Lee AR), border (Presidio TX), and Puerto Rican (Guanica). The 2020 Post-Enumeration Survey found large net undercounts for exactly these populations (on-reservation American Indian -5.6%, Black -3.3%, Hispanic -5.0%), and 2010-2020 brought historic rural young-adult mortality (opioids, motor-vehicle deaths, suicide). Both channels appear here as negative residuals indistinguishable from out-migration. These two channels are largest in the recent decades; the heavy out-migration of 1950-1980 instead reflects farm and coal-mine mechanization (the Oklahoma/Arkansas and Appalachian losses) and the Second Great Migration of African Americans out of the Deep South Black Belt, so read the pre-1990 loss rankings against that history rather than this caveat's modern one.

4. **A few Virginia independent-city annexations inflate their apparent gains.** Virginia's independent cities are county-equivalents that annexed populated territory from their neighbouring counties through the 1950s-70s. `crosswalk.py` folds the major cases into constant-territory merged units (Richmond, Roanoke, the Tidewater and Hampton Roads cities, Fairfax city + county, and others), but three fast-growing cities are deliberately left standalone and their annexations therefore register as migration: **Alexandria** (annexed 7.5 sq mi from Fairfax County on 1 Jan 1952), **Charlottesville** (from Albemarle in 1963 and 1968), and **Harrisonburg** (from Rockingham in 1953, 1962 and 1982). Each posts triple-digit young-adult 'gains' in the decades bracketing its annexations that are partly a boundary transfer, not cohort migration -- all three appear in the national top ranks for the 1950s-70s. They are not merged because Charlottesville (UVA) and Harrisonburg (JMU) are also the clearest modern college-town cases, which the 2010-2020 household basis shows standalone on purpose; read their pre-1980 ranks as boundary-inflated and their post-2000 ranks as enrollment-driven.

Other caveats: 2020 counts carry differential-privacy noise, so treat small units cautiously. Broomfield CO (08014), created in 2001 from parts of four counties, is traced standalone from 2000 onward -- its 4/1/2000 baseline reconstructed from the Census Bureau's intercensal estimates base (2010 boundaries, parents already reduced), which sums to the parents' raw 2000 total within ~140 people -- so Adams, Boulder, Jefferson and Weld keep their own signals instead of being bundled into one ~2M-person merged unit; the 1990-2000 decade still uses the parents' full pre-Broomfield territory. The 1980 county age data splices single-year counts (ages up to 74) with a coarser table for the 75-84 and 85+ split, so a small seam can appear at age 75 in the oldest cohorts; the national totals are anchor-checked, the mismatch is logged at build time, and the young-adult rankings above are unaffected. The oldest traced cohort (75-84 -> 85+) is contaminated at the destination, because the open-ended 85+ bin at t1 also holds people already 85+ at t0 -- counties with large elderly-institution populations get spuriously positive residuals, so read the 85+ cohort in the CSVs and explorer as indicative only. And Alaska is excluded from 1950, 1960 and 1970 (its pre-borough judicial divisions and election districts are not county-comparable) and therefore from every decade that traces into those years (1950-60, 1960-70, 1970-80): Alaskan counties carry no residual there and the 1970s Trans-Alaska Pipeline boom does not appear. Those decades' national ratios are computed on the Lower 48 plus Hawaii -- Alaska is cleanly dropped from both endpoints of the ratio, not misattributed to the other states.

## 1950-1960: where the 10-19-year-olds of 1950 went

**Basis: total population** — no 5-year group-quarters age table for both endpoints, so college, prison, and military counties inflate these flows. Not level-comparable with household-basis decades (see the population-basis note above).

Units with expected young-adult cohort >= 1,000. (2,747 units qualify.)

*On this total-population basis group quarters are not subtracted, so whole installation and institutional populations register directly. The top of this ranking is dominated by military and training bases and by resource/resort boomtowns -- not by universities. In the 1950s-60s these are Cold War and Vietnam-era mobilizations (Fort Leonard Wood, Fort Polk, Fort Benning) and aerospace/proving grounds (Cape Canaveral); in the 1970s, energy and ski-resort booms (the Powder River and Wyoming trona fields; Aspen, Vail). The largest net losses reflect farm and coal-mine mechanization and the Second Great Migration out of the Deep South, not the modern undercount and young-adult mortality of caveat 3.*

### Largest net gains (importing 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Pulaski County, Missouri (29169) | 1,763 | 15,924 | +14,161 | +803.0% |
| Brevard County, Florida (12009) | 2,938 | 17,300 | +14,362 | +488.8% |
| Elmore County, Idaho (16039) | 1,073 | 3,647 | +2,574 | +239.8% |
| Broward County, Florida (12011) | 10,447 | 34,641 | +24,194 | +231.6% |
| Orange County, California (06059) | 27,828 | 91,386 | +63,558 | +228.4% |
| MG-VA-PRINCE-WILLIAM | 3,455 | 11,102 | +7,647 | +221.4% |
| Adams County, Colorado (08001) | 5,883 | 18,695 | +12,812 | +217.8% |
| Clark County, Nevada (32003) | 5,922 | 18,092 | +12,170 | +205.5% |
| Okaloosa County, Florida (12091) | 4,276 | 12,402 | +8,126 | +190.0% |
| MG-VA-FAIRFAX | 12,625 | 34,976 | +22,351 | +177.0% |
| Sarpy County, Nebraska (31153) | 2,198 | 5,886 | +3,688 | +167.8% |
| Midland County, Texas (48329) | 3,689 | 9,726 | +6,037 | +163.7% |
| Otero County, New Mexico (35035) | 2,380 | 6,253 | +3,873 | +162.8% |
| Geary County, Kansas (20061) | 2,657 | 6,844 | +4,187 | +157.6% |
| Anoka County, Minnesota (27003) | 5,032 | 12,926 | +7,894 | +156.9% |
| Orange County, Florida (12095) | 14,641 | 36,423 | +21,782 | +148.8% |
| Island County, Washington (53029) | 1,433 | 3,504 | +2,071 | +144.5% |
| Onslow County, North Carolina (37133) | 9,371 | 22,702 | +13,331 | +142.2% |
| Randall County, Texas (48381) | 2,162 | 5,228 | +3,066 | +141.8% |
| Comanche County, Oklahoma (40031) | 8,984 | 21,314 | +12,330 | +137.3% |

### Largest net losses (exporting 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Okfuskee County, Oklahoma (40107) | 3,436 | 809 | -2,627 | -76.5% |
| Reynolds County, Missouri (29179) | 1,476 | 348 | -1,128 | -76.4% |
| Haskell County, Oklahoma (40061) | 2,674 | 647 | -2,027 | -75.8% |
| Delta County, Texas (48119) | 1,500 | 365 | -1,135 | -75.7% |
| Coal County, Oklahoma (40029) | 1,526 | 378 | -1,148 | -75.2% |
| McIntosh County, Oklahoma (40091) | 3,721 | 943 | -2,778 | -74.7% |
| Atoka County, Oklahoma (40005) | 3,042 | 816 | -2,226 | -73.2% |
| Mora County, New Mexico (35033) | 1,972 | 530 | -1,442 | -73.1% |
| Newton County, Arkansas (05101) | 1,860 | 516 | -1,344 | -72.3% |
| Pushmataha County, Oklahoma (40127) | 2,379 | 661 | -1,718 | -72.2% |
| Carroll County, Mississippi (28015) | 3,298 | 923 | -2,375 | -72.0% |
| Woodruff County, Arkansas (05147) | 3,824 | 1,073 | -2,751 | -71.9% |
| Choctaw County, Oklahoma (40023) | 3,961 | 1,113 | -2,848 | -71.9% |
| Dewey County, Oklahoma (40043) | 1,643 | 467 | -1,176 | -71.6% |
| Sharp County, Arkansas (05135) | 1,766 | 502 | -1,264 | -71.6% |
| Fulton County, Arkansas (05049) | 1,717 | 489 | -1,228 | -71.5% |
| Marion County, Arkansas (05089) | 1,496 | 432 | -1,064 | -71.1% |
| Hughes County, Oklahoma (40063) | 3,865 | 1,127 | -2,738 | -70.8% |
| Wilcox County, Alabama (01131) | 5,223 | 1,524 | -3,699 | -70.8% |
| Love County, Oklahoma (40085) | 1,448 | 426 | -1,022 | -70.6% |

## 1960-1970: where the 10-19-year-olds of 1960 went

**Basis: total population** — no 5-year group-quarters age table for both endpoints, so college, prison, and military counties inflate these flows. Not level-comparable with household-basis decades (see the population-basis note above).

Units with expected young-adult cohort >= 1,000. (2,756 units qualify.)

*On this total-population basis group quarters are not subtracted, so whole installation and institutional populations register directly. The top of this ranking is dominated by military and training bases and by resource/resort boomtowns -- not by universities. In the 1950s-60s these are Cold War and Vietnam-era mobilizations (Fort Leonard Wood, Fort Polk, Fort Benning) and aerospace/proving grounds (Cape Canaveral); in the 1970s, energy and ski-resort booms (the Powder River and Wyoming trona fields; Aspen, Vail). The largest net losses reflect farm and coal-mine mechanization and the Second Great Migration out of the Deep South, not the modern undercount and young-adult mortality of caveat 3.*

### Largest net gains (importing 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Vernon Parish, Louisiana (22115) | 3,633 | 20,201 | +16,568 | +456.1% |
| Chattahoochee County, Georgia (13053) | 3,183 | 14,650 | +11,467 | +360.3% |
| Dale County, Alabama (01045) | 5,458 | 15,921 | +10,463 | +191.7% |
| Riley County, Kansas (20161) | 7,986 | 22,311 | +14,325 | +179.4% |
| MG-VA-PRINCE-WILLIAM | 7,759 | 20,969 | +13,210 | +170.3% |
| Clayton County, Georgia (13063) | 7,914 | 20,208 | +12,294 | +155.3% |
| Prince George County, Virginia (51149) | 3,859 | 9,377 | +5,518 | +143.0% |
| Clark County, Nevada (32003) | 19,127 | 44,920 | +25,793 | +134.9% |
| Johnson County, Iowa (19103) | 8,895 | 20,854 | +11,959 | +134.4% |
| MG-VA-VIRGINIA-BEACH | 14,880 | 34,449 | +19,569 | +131.5% |
| Coryell County, Texas (48099) | 5,333 | 12,296 | +6,963 | +130.6% |
| Charlottesville city, Virginia (51540) | 4,135 | 9,264 | +5,129 | +124.1% |
| Clarke County, Georgia (13059) | 8,494 | 18,945 | +10,451 | +123.0% |
| Mohave County, Arizona (04015) | 1,302 | 2,889 | +1,587 | +121.9% |
| El Paso County, Colorado (08041) | 24,245 | 53,629 | +29,384 | +121.2% |
| Prince George's County, Maryland (24033) | 61,012 | 133,261 | +72,249 | +118.4% |
| Monroe County, Indiana (18105) | 11,367 | 24,510 | +13,143 | +115.6% |
| Bell County, Texas (48027) | 16,606 | 35,491 | +18,885 | +113.7% |
| Alexandria city, Virginia (51510) | 13,338 | 28,394 | +15,056 | +112.9% |
| Cleveland County, Oklahoma (40027) | 8,962 | 19,057 | +10,095 | +112.6% |

### Largest net losses (exporting 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Knox County, Texas (48275) | 1,417 | 405 | -1,012 | -71.4% |
| Greene County, Alabama (01063) | 3,050 | 922 | -2,128 | -69.8% |
| Logan County, North Dakota (38047) | 1,132 | 346 | -786 | -69.4% |
| Tunica County, Mississippi (28143) | 3,633 | 1,118 | -2,515 | -69.2% |
| Iron County, Michigan (26071) | 2,918 | 907 | -2,011 | -68.9% |
| Pemiscot County, Missouri (29155) | 8,316 | 2,657 | -5,659 | -68.0% |
| Clark County, South Dakota (46025) | 1,258 | 403 | -855 | -68.0% |
| Dunn County, North Dakota (38025) | 1,332 | 429 | -903 | -67.8% |
| Clay County, West Virginia (54015) | 2,883 | 956 | -1,927 | -66.8% |
| Costilla County, Colorado (08023) | 1,016 | 337 | -679 | -66.8% |
| Mora County, New Mexico (35033) | 1,453 | 482 | -971 | -66.8% |
| Stafford County, Kansas (20185) | 1,255 | 417 | -838 | -66.8% |
| Webster County, West Virginia (54101) | 3,199 | 1,068 | -2,131 | -66.6% |
| Hale County, Alabama (01065) | 4,323 | 1,443 | -2,880 | -66.6% |
| Miner County, South Dakota (46097) | 1,002 | 335 | -667 | -66.6% |
| McDowell County, West Virginia (54047) | 16,306 | 5,465 | -10,841 | -66.5% |
| Haskell County, Texas (48207) | 1,952 | 657 | -1,295 | -66.3% |
| Hettinger County, North Dakota (38041) | 1,296 | 437 | -859 | -66.3% |
| McPherson County, South Dakota (46089) | 1,010 | 341 | -669 | -66.2% |
| Warren County, North Carolina (37185) | 4,590 | 1,551 | -3,039 | -66.2% |

## 1970-1980: where the 10-19-year-olds of 1970 went

**Basis: total population** — no 5-year group-quarters age table for both endpoints, so college, prison, and military counties inflate these flows. Not level-comparable with household-basis decades (see the population-basis note above).

Units with expected young-adult cohort >= 1,000. (2,790 units qualify.)

*On this total-population basis group quarters are not subtracted, so whole installation and institutional populations register directly. The top of this ranking is dominated by military and training bases and by resource/resort boomtowns -- not by universities. In the 1950s-60s these are Cold War and Vietnam-era mobilizations (Fort Leonard Wood, Fort Polk, Fort Benning) and aerospace/proving grounds (Cape Canaveral); in the 1970s, energy and ski-resort booms (the Powder River and Wyoming trona fields; Aspen, Vail). The largest net losses reflect farm and coal-mine mechanization and the Second Great Migration out of the Deep South, not the modern undercount and young-adult mortality of caveat 3.*

### Largest net gains (importing 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Liberty County, Georgia (13179) | 3,413 | 12,717 | +9,304 | +272.6% |
| Pitkin County, Colorado (08097) | 1,062 | 3,336 | +2,274 | +214.2% |
| Eagle County, Colorado (08037) | 1,498 | 4,660 | +3,162 | +211.0% |
| Routt County, Colorado (08107) | 1,355 | 3,888 | +2,533 | +187.0% |
| Douglas County, Nevada (32005) | 1,219 | 3,232 | +2,013 | +165.2% |
| Brazos County, Texas (48041) | 12,253 | 32,195 | +19,942 | +162.7% |
| Sweetwater County, Wyoming (56037) | 3,742 | 9,816 | +6,074 | +162.3% |
| Teton County, Wyoming (56039) | 1,009 | 2,625 | +1,616 | +160.2% |
| Campbell County, Wyoming (56005) | 2,677 | 6,546 | +3,869 | +144.5% |
| Walker County, Texas (48471) | 5,074 | 12,213 | +7,139 | +140.7% |
| Coryell County, Texas (48099) | 7,532 | 17,792 | +10,260 | +136.2% |
| Converse County, Wyoming (56009) | 1,281 | 3,019 | +1,738 | +135.7% |
| Hood County, Texas (48221) | 1,167 | 2,612 | +1,445 | +123.7% |
| Moffat County, Colorado (08081) | 1,313 | 2,927 | +1,614 | +123.0% |
| Gwinnett County, Georgia (13135) | 13,902 | 30,096 | +16,194 | +116.5% |
| Blaine County, Idaho (16013) | 1,140 | 2,435 | +1,295 | +113.6% |
| Fort Bend County, Texas (48157) | 11,630 | 24,702 | +13,072 | +112.4% |
| Union County, Florida (12125) | 1,337 | 2,831 | +1,494 | +111.8% |
| Dare County, North Carolina (37055) | 1,204 | 2,508 | +1,304 | +108.4% |
| Riley County, Kansas (20161) | 11,704 | 24,325 | +12,621 | +107.8% |

### Largest net losses (exporting 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Emmons County, North Dakota (38029) | 1,789 | 594 | -1,195 | -66.8% |
| Logan County, North Dakota (38047) | 1,002 | 371 | -631 | -63.0% |
| McPherson County, South Dakota (46089) | 1,158 | 434 | -724 | -62.5% |
| Lee County, Arkansas (05077) | 4,737 | 1,905 | -2,832 | -59.8% |
| Webster County, Nebraska (31181) | 1,143 | 488 | -655 | -57.3% |
| Quitman County, Mississippi (28119) | 3,889 | 1,713 | -2,176 | -56.0% |
| Grant County, North Dakota (38037) | 1,210 | 533 | -677 | -55.9% |
| McIntosh County, North Dakota (38051) | 1,125 | 496 | -629 | -55.9% |
| Moody County, South Dakota (46101) | 1,998 | 887 | -1,111 | -55.6% |
| Hettinger County, North Dakota (38041) | 1,224 | 549 | -675 | -55.2% |
| Hand County, South Dakota (46059) | 1,381 | 630 | -751 | -54.4% |
| Tensas Parish, Louisiana (22107) | 2,536 | 1,166 | -1,370 | -54.0% |
| Tunica County, Mississippi (28143) | 2,990 | 1,395 | -1,595 | -53.3% |
| Edmunds County, South Dakota (46045) | 1,190 | 566 | -624 | -52.4% |
| Kidder County, North Dakota (38043) | 1,050 | 501 | -549 | -52.3% |
| McHenry County, North Dakota (38049) | 2,050 | 980 | -1,070 | -52.2% |
| Wells County, North Dakota (38103) | 1,731 | 832 | -899 | -51.9% |
| Graham County, Kansas (20065) | 1,118 | 539 | -579 | -51.8% |
| Mora County, New Mexico (35033) | 1,213 | 592 | -621 | -51.2% |
| Traverse County, Minnesota (27155) | 1,369 | 671 | -698 | -51.0% |

## 1980-1990: where the 10-19-year-olds of 1980 went

**Basis: total population** — no 5-year group-quarters age table for both endpoints, so college, prison, and military counties inflate these flows. Not level-comparable with household-basis decades (see the population-basis note above).

Units with expected young-adult cohort >= 1,000. (2,772 units qualify.)

*On this total-population basis group quarters are not subtracted, so whole installation and institutional populations register directly. The top of this ranking is dominated by military and training bases and by resource/resort boomtowns -- not by universities. In the 1950s-60s these are Cold War and Vietnam-era mobilizations (Fort Leonard Wood, Fort Polk, Fort Benning) and aerospace/proving grounds (Cape Canaveral); in the 1970s, energy and ski-resort booms (the Powder River and Wyoming trona fields; Aspen, Vail). The largest net losses reflect farm and coal-mine mechanization and the Second Great Migration out of the Deep South, not the modern undercount and young-adult mortality of caveat 3.*

### Largest net gains (importing 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Summit County, Colorado (08117) | 1,088 | 3,342 | +2,254 | +207.1% |
| MG-AK-ALEUTIANS | 1,333 | 4,088 | +2,755 | +206.7% |
| Camden County, Georgia (13039) | 2,710 | 7,113 | +4,403 | +162.5% |
| Arlington County, Virginia (51013) | 16,108 | 41,216 | +25,108 | +155.9% |
| Eagle County, Colorado (08037) | 1,791 | 4,570 | +2,779 | +155.2% |
| Harrisonburg city, Virginia (51660) | 4,209 | 10,049 | +5,840 | +138.8% |
| Alexandria city, Virginia (51510) | 11,429 | 27,241 | +15,812 | +138.3% |
| Denton County, Texas (48121) | 25,740 | 59,805 | +34,065 | +132.3% |
| Liberty County, Georgia (13179) | 7,592 | 16,842 | +9,250 | +121.9% |
| Onslow County, North Carolina (37133) | 23,425 | 51,057 | +27,632 | +118.0% |
| Gwinnett County, Georgia (13135) | 29,898 | 65,008 | +35,110 | +117.4% |
| Charlottesville city, Virginia (51540) | 5,740 | 12,288 | +6,548 | +114.1% |
| Osceola County, Florida (12097) | 8,092 | 16,826 | +8,734 | +107.9% |
| Brazos County, Texas (48041) | 19,159 | 39,535 | +20,376 | +106.4% |
| Johnson County, Iowa (19103) | 13,922 | 28,240 | +14,318 | +102.8% |
| Pitkin County, Colorado (08097) | 1,235 | 2,488 | +1,253 | +101.5% |
| Riley County, Kansas (20161) | 12,006 | 23,811 | +11,805 | +98.3% |
| Walker County, Texas (48471) | 6,427 | 12,493 | +6,066 | +94.4% |
| Williamsburg city, Virginia (51830) | 2,329 | 4,451 | +2,122 | +91.1% |
| Clarke County, Georgia (13059) | 13,871 | 26,428 | +12,557 | +90.5% |

### Largest net losses (exporting 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Emmons County, North Dakota (38029) | 1,300 | 443 | -857 | -65.9% |
| Cavalier County, North Dakota (38019) | 1,449 | 550 | -899 | -62.0% |
| Greenlee County, Arizona (04011) | 2,122 | 814 | -1,308 | -61.6% |
| Platte County, Wyoming (56031) | 1,994 | 787 | -1,207 | -60.5% |
| McHenry County, North Dakota (38049) | 1,410 | 558 | -852 | -60.4% |
| Pierce County, North Dakota (38069) | 1,268 | 505 | -763 | -60.2% |
| Lee County, Arkansas (05077) | 3,507 | 1,402 | -2,105 | -60.0% |
| McLean County, North Dakota (38055) | 2,067 | 827 | -1,240 | -60.0% |
| Red Lake County, Minnesota (27125) | 1,144 | 460 | -684 | -59.8% |
| Knox County, Nebraska (31107) | 1,976 | 796 | -1,180 | -59.7% |
| Mahnomen County, Minnesota (27087) | 1,184 | 478 | -706 | -59.6% |
| Lincoln County, Minnesota (27081) | 1,478 | 598 | -880 | -59.5% |
| Bent County, Colorado (08011) | 1,029 | 418 | -611 | -59.4% |
| Big Stone County, Minnesota (27011) | 1,337 | 544 | -793 | -59.3% |
| LaMoure County, North Dakota (38045) | 1,098 | 454 | -644 | -58.7% |
| Valley County, Montana (30105) | 1,881 | 778 | -1,103 | -58.6% |
| Caribou County, Idaho (16029) | 1,576 | 656 | -920 | -58.4% |
| Pocahontas County, Iowa (19151) | 2,069 | 873 | -1,196 | -57.8% |
| Palo Alto County, Iowa (19147) | 2,433 | 1,031 | -1,402 | -57.6% |
| Grand County, Utah (49019) | 1,471 | 624 | -847 | -57.6% |

## 1990-2000: where the 10-19-year-olds of 1990 went

**Basis: total population** — no 5-year group-quarters age table for both endpoints, so college, prison, and military counties inflate these flows. Not level-comparable with household-basis decades (see the population-basis note above).

Units with expected young-adult cohort >= 1,000. (2,790 units qualify.)

*On this total-population basis group quarters are not subtracted, so college dorms, prisons, and military barracks register directly in these flows. University counties still top the gains (dorm plus off-campus enrollment), alongside institutional and Sunbelt-growth counties -- read the top ranks as enrollment and base population, not purely economic in-migration.*

### Largest net gains (importing 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Summit County, Colorado (08117) | 1,292 | 6,528 | +5,236 | +405.3% |
| Eagle County, Colorado (08037) | 2,568 | 8,802 | +6,234 | +242.8% |
| Arlington County, Virginia (51013) | 13,771 | 42,116 | +28,345 | +205.8% |
| Alexandria city, Virginia (51510) | 9,052 | 26,398 | +17,346 | +191.6% |
| Charlottesville city, Virginia (51540) | 4,777 | 13,901 | +9,124 | +191.0% |
| Teton County, Wyoming (56039) | 1,368 | 3,514 | +2,146 | +156.9% |
| Pitkin County, Colorado (08097) | 1,012 | 2,343 | +1,331 | +131.6% |
| Harrisonburg city, Virginia (51660) | 6,297 | 13,589 | +7,292 | +115.8% |
| Clarke County, Georgia (13059) | 15,694 | 33,213 | +17,519 | +111.6% |
| Travis County, Texas (48453) | 84,652 | 177,152 | +92,500 | +109.3% |
| San Francisco County, California (06075) | 71,702 | 147,447 | +75,745 | +105.6% |
| Brazos County, Texas (48041) | 23,312 | 47,379 | +24,067 | +103.2% |
| Clark County, Nevada (32003) | 100,701 | 202,121 | +101,420 | +100.7% |
| Johnson County, Iowa (19103) | 14,894 | 28,950 | +14,056 | +94.4% |
| New York County, New York (36061) | 149,078 | 288,237 | +139,159 | +93.3% |
| Denver County, Colorado (08031) | 55,003 | 106,262 | +51,259 | +93.2% |
| Douglas County, Kansas (20045) | 14,482 | 27,823 | +13,341 | +92.1% |
| Gunnison County, Colorado (08051) | 1,857 | 3,560 | +1,703 | +91.7% |
| Centre County, Pennsylvania (42027) | 19,314 | 36,403 | +17,089 | +88.5% |
| Long County, Georgia (13183) | 1,088 | 2,022 | +934 | +85.9% |

### Largest net losses (exporting 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Mercer County, North Dakota (38057) | 1,627 | 447 | -1,180 | -72.5% |
| McKenzie County, North Dakota (38053) | 1,132 | 362 | -770 | -68.0% |
| McLean County, North Dakota (38055) | 1,820 | 601 | -1,219 | -67.0% |
| Bottineau County, North Dakota (38009) | 1,405 | 525 | -880 | -62.6% |
| Rosebud County, Montana (30087) | 2,244 | 851 | -1,393 | -62.1% |
| Ward County, Texas (48475) | 2,643 | 1,026 | -1,617 | -61.2% |
| Mineral County, Nevada (32021) | 1,060 | 417 | -643 | -60.6% |
| Boone County, Nebraska (31011) | 1,042 | 416 | -626 | -60.1% |
| Day County, South Dakota (46037) | 1,074 | 431 | -643 | -59.9% |
| Lac qui Parle County, Minnesota (27073) | 1,322 | 532 | -790 | -59.8% |
| Yoakum County, Texas (48501) | 1,754 | 711 | -1,043 | -59.5% |
| Ontonagon County, Michigan (26131) | 1,342 | 554 | -788 | -58.7% |
| Holt County, Nebraska (31089) | 2,041 | 846 | -1,195 | -58.6% |
| Los Alamos County, New Mexico (35028) | 2,849 | 1,197 | -1,652 | -58.0% |
| McDowell County, West Virginia (54047) | 7,107 | 3,029 | -4,078 | -57.4% |
| Richland County, Montana (30083) | 1,913 | 827 | -1,086 | -56.8% |
| Pocahontas County, Iowa (19151) | 1,388 | 602 | -786 | -56.6% |
| Teton County, Montana (30099) | 1,101 | 480 | -621 | -56.4% |
| Lincoln County, Montana (30053) | 3,082 | 1,345 | -1,737 | -56.4% |
| Antelope County, Nebraska (31003) | 1,316 | 575 | -741 | -56.3% |

## 2000-2010: where the 10-19-year-olds of 2000 went

**Basis: total population** — no 5-year group-quarters age table for both endpoints, so college, prison, and military counties inflate these flows. Not level-comparable with household-basis decades (see the population-basis note above).

Units with expected young-adult cohort >= 1,000. (2,811 units qualify.)

*On this total-population basis group quarters are not subtracted, so college dorms, prisons, and military barracks register directly in these flows. University counties still top the gains (dorm plus off-campus enrollment), alongside institutional and Sunbelt-growth counties -- read the top ranks as enrollment and base population, not purely economic in-migration.*

### Largest net gains (importing 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Arlington County, Virginia (51013) | 15,940 | 51,076 | +35,136 | +220.4% |
| Alexandria city, Virginia (51510) | 9,877 | 25,904 | +16,027 | +162.3% |
| Riley County, Kansas (20161) | 11,170 | 26,139 | +14,969 | +134.0% |
| Clarke County, Georgia (13059) | 16,760 | 37,702 | +20,942 | +124.9% |
| Summit County, Colorado (08117) | 2,395 | 5,360 | +2,965 | +123.8% |
| San Francisco County, California (06075) | 66,969 | 148,774 | +81,805 | +122.2% |
| New York County, New York (36061) | 150,889 | 328,291 | +177,402 | +117.6% |
| Albany County, Wyoming (56001) | 5,467 | 11,443 | +5,976 | +109.3% |
| Monongalia County, West Virginia (54061) | 12,960 | 26,871 | +13,911 | +107.3% |
| Harrisonburg city, Virginia (51660) | 8,421 | 17,325 | +8,904 | +105.7% |
| Brazos County, Texas (48041) | 29,491 | 60,288 | +30,797 | +104.4% |
| Onslow County, North Carolina (37133) | 24,510 | 49,970 | +25,460 | +103.9% |
| Whitman County, Washington (53075) | 7,409 | 15,015 | +7,606 | +102.7% |
| Centre County, Pennsylvania (42027) | 21,641 | 43,236 | +21,595 | +99.8% |
| Fredericksburg city, Virginia (51630) | 3,110 | 6,164 | +3,054 | +98.2% |
| Payne County, Oklahoma (40119) | 11,154 | 21,789 | +10,635 | +95.4% |
| Suffolk County, Massachusetts (25025) | 92,192 | 179,125 | +86,933 | +94.3% |
| Johnson County, Iowa (19103) | 17,711 | 34,042 | +16,331 | +92.2% |
| Lafayette County, Mississippi (28071) | 6,648 | 12,708 | +6,060 | +91.2% |
| Watauga County, North Carolina (37189) | 7,575 | 14,478 | +6,903 | +91.1% |

### Largest net losses (exporting 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Boise County, Idaho (16015) | 1,066 | 402 | -664 | -62.3% |
| Bear Lake County, Idaho (16007) | 1,398 | 528 | -870 | -62.2% |
| Fillmore County, Nebraska (31059) | 1,094 | 445 | -649 | -59.3% |
| Elbert County, Colorado (08039) | 3,640 | 1,503 | -2,137 | -58.7% |
| Ontonagon County, Michigan (26131) | 1,005 | 415 | -590 | -58.7% |
| Cedar County, Nebraska (31027) | 1,806 | 748 | -1,058 | -58.6% |
| Holt County, Nebraska (31089) | 2,036 | 854 | -1,182 | -58.0% |
| Boone County, Nebraska (31011) | 1,148 | 484 | -664 | -57.8% |
| Price County, Wisconsin (55099) | 2,417 | 1,020 | -1,397 | -57.8% |
| Lac qui Parle County, Minnesota (27073) | 1,332 | 563 | -769 | -57.7% |
| Huerfano County, Colorado (08055) | 1,052 | 449 | -603 | -57.3% |
| Los Alamos County, New Mexico (35028) | 2,868 | 1,227 | -1,641 | -57.2% |
| Jefferson County, Montana (30043) | 1,870 | 802 | -1,068 | -57.1% |
| Knox County, Nebraska (31107) | 1,508 | 647 | -861 | -57.1% |
| Burt County, Nebraska (31021) | 1,249 | 540 | -709 | -56.8% |
| Cameron Parish, Louisiana (22023) | 1,767 | 769 | -998 | -56.5% |
| Pierce County, Nebraska (31139) | 1,491 | 652 | -839 | -56.3% |
| Antelope County, Nebraska (31003) | 1,359 | 597 | -762 | -56.1% |
| Teton County, Montana (30099) | 1,122 | 497 | -625 | -55.7% |
| Pocahontas County, Iowa (19151) | 1,453 | 644 | -809 | -55.7% |

## 2010-2020: where the 10-19-year-olds of 2010 went

**Basis: household population** (group quarters subtracted).

Units with expected young-adult cohort >= 1,000. (2,690 units qualify.)

*College towns dominate the top of this ranking even on the household basis: off-campus students are counted as household population, so subtracting group quarters does not remove them (caveat 1 above).*

### Largest net gains (importing 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Arlington County, Virginia (51013) | 14,149 | 51,758 | +37,609 | +265.8% |
| Charlottesville city, Virginia (51540) | 3,835 | 12,922 | +9,087 | +236.9% |
| Clarke County, Georgia (13059) | 11,615 | 33,476 | +21,861 | +188.2% |
| Harrisonburg city, Virginia (51660) | 4,693 | 13,227 | +8,534 | +181.9% |
| Riley County, Kansas (20161) | 6,796 | 18,815 | +12,019 | +176.9% |
| Whitman County, Washington (53075) | 4,438 | 12,281 | +7,843 | +176.7% |
| Alexandria city, Virginia (51510) | 9,253 | 24,186 | +14,933 | +161.4% |
| Clay County, South Dakota (46027) | 1,267 | 3,304 | +2,037 | +160.8% |
| San Francisco County, California (06075) | 57,705 | 147,842 | +90,137 | +156.2% |
| Radford city, Virginia (51750) | 1,559 | 3,977 | +2,418 | +155.1% |
| New York County, New York (36061) | 123,717 | 314,673 | +190,956 | +154.3% |
| Story County, Iowa (19169) | 9,347 | 23,474 | +14,127 | +151.1% |
| Watauga County, North Carolina (37189) | 4,802 | 12,037 | +7,235 | +150.7% |
| Suffolk County, Massachusetts (25025) | 72,535 | 178,320 | +105,785 | +145.8% |
| Albany County, Wyoming (56001) | 3,890 | 9,517 | +5,627 | +144.6% |
| Montgomery County, Virginia (51121) | 9,836 | 24,054 | +14,218 | +144.6% |
| District of Columbia, District of Columbia (11001) | 53,620 | 130,394 | +76,774 | +143.2% |
| Oktibbeha County, Mississippi (28105) | 5,146 | 12,413 | +7,267 | +141.2% |
| Gallatin County, Montana (30031) | 9,759 | 23,303 | +13,544 | +138.8% |
| Williams County, North Dakota (38105) | 2,846 | 6,696 | +3,850 | +135.3% |

### Largest net losses (exporting 20-somethings)

| Unit | Expected | Actual | Net | Rate |
|---|---:|---:|---:|---:|
| Presidio County, Texas (48377) | 1,359 | 586 | -773 | -56.9% |
| Alexander County, Illinois (17003) | 1,031 | 446 | -585 | -56.7% |
| Phillips County, Arkansas (05107) | 3,655 | 1,677 | -1,978 | -54.1% |
| Ripley County, Missouri (29181) | 1,986 | 966 | -1,020 | -51.4% |
| Guánica Municipio, Puerto Rico (72055) | 2,932 | 1,434 | -1,498 | -51.1% |
| Coleman County, Texas (48083) | 1,145 | 564 | -581 | -50.7% |
| Floyd County, Texas (48153) | 1,037 | 512 | -525 | -50.6% |
| Emery County, Utah (49015) | 1,801 | 892 | -909 | -50.5% |
| Conejos County, Colorado (08021) | 1,342 | 668 | -674 | -50.2% |
| Shannon County, Missouri (29203) | 1,180 | 600 | -580 | -49.2% |
| Jefferson County, Montana (30043) | 1,595 | 815 | -780 | -48.9% |
| Lee County, Arkansas (05077) | 1,300 | 665 | -635 | -48.8% |
| West Feliciana Parish, Louisiana (22125) | 1,696 | 868 | -828 | -48.8% |
| Sabine County, Texas (48403) | 1,290 | 662 | -628 | -48.7% |
| Rolette County, North Dakota (38079) | 2,437 | 1,252 | -1,185 | -48.6% |
| Archer County, Texas (48009) | 1,406 | 726 | -680 | -48.4% |
| Benson County, North Dakota (38005) | 1,142 | 592 | -550 | -48.1% |
| Hickory County, Missouri (29085) | 1,001 | 519 | -482 | -48.1% |
| Ozark County, Missouri (29153) | 1,160 | 602 | -558 | -48.1% |
| Oregon County, Missouri (29149) | 1,500 | 786 | -714 | -47.6% |
