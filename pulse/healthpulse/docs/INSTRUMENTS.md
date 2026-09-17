# Instruments

14 instruments across 7 sections. 13 are keyless and live-verified; 1 needs a
free API key and is skipped until you set it. Everything is US-national except
the WHO outbreak wall (global) and the AQI card (Houston).

Verified ✅ = fetched live and returned a sane value during this build
(2026-08-17). ⚠ = code path reviewed but not run against the real upstream.

| id | Section | Source | Endpoint | Cadence | Key | Threshold basis | Verified |
|---|---|---|---|---|---|---|---|
| `ari-ed-visits` | Vitals | [CDC NSSP — ED Respiratory Daily](https://data.cdc.gov/d/vjzj-u7u8) | Socrata `vjzj-u7u8`, `geography='United States' AND pathogen='ARI'` | 6h | — | none — CDC grades ARI by state percentile, not fixed cut-offs | ✅ |
| `ili-national` | Vitals | [CDC ILINet via CMU Delphi](https://cmu-delphi.github.io/delphi-epidata/api/fluview.html) | `/epidata/fluview/?regions=nat` | 12h | — | CDC national ILI epidemic baseline ≈3%; 5% / 7% for moderate / high seasons | ✅ |
| `wastewater-covid` | Vitals | [CDC NWSS WVAL](https://data.cdc.gov/d/atcp-73re) | Socrata `atcp-73re`, `avg(site_wval)` grouped by week, `pathogen_target='SARS-CoV-2'` | 12h | — | CDC WVAL categories: ≥3 Moderate, ≥4.5 High, ≥8 Very High | ✅ |
| `wastewater-influenza-a` | Wastewater | [CDC NWSS WVAL](https://data.cdc.gov/d/atcp-73re) | same, `pathogen_target='Influenza A virus'` | 12h | — | CDC WVAL categories | ✅ |
| `wastewater-rsv` | Wastewater | [CDC NWSS WVAL](https://data.cdc.gov/d/atcp-73re) | same, `pathogen_target='RSV'` | 12h | — | CDC WVAL categories | ✅ |
| `ed-visits-covid` | Emergency Dept | [CDC NSSP via CMU Delphi](https://cmu-delphi.github.io/delphi-epidata/api/covidcast-signals/nssp.html) | `covidcast` `nssp` / `pct_ed_visits_covid`, `geo_type=nation` | 12h | — | none — no accepted national cut-offs | ✅ |
| `ed-visits-influenza` | Emergency Dept | same | `nssp` / `pct_ed_visits_influenza` | 12h | — | none | ✅ |
| `hosp-rate-covid` | Hospitalizations | [CDC RESP-NET](https://data.cdc.gov/d/kvib-3txy) | Socrata `kvib-3txy`, `surveillance_network='COVID-NET'`, Overall/All, Weekly Rate, Observed | 12h | — | none — peaks differ by an order of magnitude between viruses | ✅ |
| `hosp-rate-influenza` | Hospitalizations | same | `surveillance_network='FluSurv-NET'` | 12h | — | none | ✅ |
| `who-outbreak-news` | Outbreaks | [WHO Disease Outbreak News](https://www.who.int/emergencies/disease-outbreak-news) | `who.int/api/news/diseaseoutbreaknews` (OData JSON) | 6h | — | events wall — severity by pathogen class | ✅ |
| `fda-food-recalls` | Recalls & Shortages | [openFDA Food Enforcement](https://open.fda.gov/apis/food/enforcement/) | `api.fda.gov/food/enforcement.json`, `classification:"Class I"`, 180-day window | 6h | — | events wall — Class I is FDA's most serious class by definition | ✅ |
| `drug-shortages` | Recalls & Shortages | [openFDA Drug Shortages](https://open.fda.gov/apis/drug/shortages/) | `api.fda.gov/drug/shortages.json?count=status` → `Current` | 6h | — | none — FDA publishes no banding for list size | ✅ |
| `heat-cold-alerts` | Environment | [NOAA / NWS active alerts](https://api.weather.gov/alerts/active) | `/alerts/active?event=<6 heat & cold types>` | 15m | — | operational, not official: 10 / 50 / 150 active alerts | ✅ |
| `airnow-aqi` | Environment | [AirNow](https://docs.airnowapi.org/) | `/aq/observation/zipCode/current/`, ZIP 77002, 50 mi | 1h | `AIRNOW_API_KEY` | EPA AQI categories: 51 Moderate, 101 USG, 151 Unhealthy | ⚠ |

`airnow-aqi` is ⚠ because AirNow rejects unauthenticated requests. The parsing
path was exercised against a stubbed payload of the real response shape (max-AQI
selection, local-hour → UTC conversion, metadata), and the live endpoint was
confirmed to return a clean `401 {"WebServiceError":[{"Message":"Invalid API
key"}]}` for a bad key — so the request shape reaches AirNow's auth layer.

## Why so many instruments have no thresholds

The framework colours a card only when the domain has a real, published scale.
Respiratory surveillance mostly does not: NSSP ED percentages and RESP-NET
hospitalisation rates have no official severity bands, and inventing cut-offs
would make the dashboard look more certain than the data is. Those cards show
`unknown` and let the sparkline carry the meaning. Where an accepted scale does
exist — CDC's WVAL categories, the ILI epidemic baseline, EPA's AQI — it is used
verbatim and cited in the code.

## Upstream quirks handled

- **MMWR epiweeks.** Delphi keys weekly data by epiweek (`202631`), not by date.
  `_lib.js` converts to the week-ending Saturday using the "week 1 contains the
  first Wednesday of the year" rule, spot-checked against four known CDC
  week-ending dates.
- **Contaminated `site_wval`.** A minority of NWSS rows carry raw concentrations
  instead of the normalized index — as of 2026-09 the column maxes out at 1.25e4
  (SARS-CoV-2), 6.9e8 (influenza A) and **~2.7e21** (RSV), and the tail keeps
  growing as new bad rows land. One such row destroys a mean over ~1,000 sites:
  unguarded, the RSV weekly mean for the week ending 2025-01-25 is ~2.1e8. Rows above 100 are
  excluded. The cut sits far above the genuine tail (which runs continuously to
  ~50); re-running the January 2026 COVID surge with and without the guard gives
  identical weekly means to 2 dp, whereas a tighter cut at 15 would understate
  those weeks by ~30%. `median()` was rejected — SoQL returns integers on this
  column, flattening the out-of-season series to a constant "1".
- **Partial trailing weeks.** NWSS keeps collecting for days after a week is
  published (918 sites vs 1,033 the week before, while this was built). A
  trailing week with under 80% of the prior week's site count is dropped rather
  than rendered as a fake dip. `meta.sites` always shows the real count.
- **NWS repeated query params.** `api.weather.gov/alerts/active` takes **one**
  comma-separated `event=` parameter. Repeating `event=` — the obvious guess —
  returns HTTP 200 but silently honours only the *last* occurrence. This shipped
  as a bug first: the card read 0 active alerts (the last event happened to be
  out of season) when 52 were in force.
- **RESP-NET facets.** `kvib-3txy` is long-format; without pinning
  `rate_type='Observed'` the same date returns two or three times with
  Observed / Estimated / Age-Adjusted variants and the series silently keeps
  whichever landed last.
- **openFDA zero-hit 404.** openFDA answers an empty result set with HTTP 404
  and `{error:{code:'NOT_FOUND'}}`. The recall fetcher translates that into an
  empty wall instead of a failed instrument.
- **Socrata floating timestamps.** Dates arrive either bare (`2026-08-08`) or as
  zone-less timestamps (`2026-08-08T00:00:00.000`). Both are pinned to UTC
  midnight so sparkline spacing stays exact.

## Candidates / next

Verified to return usable data, not wired yet:

- **RSV ED visits** — `nssp` / `pct_ed_visits_rsv`, same Delphi call as the other
  two ED cards. Dropped only to stay inside the instrument budget.
- **RSV hospitalisation rate** — RESP-NET `surveillance_network='RSV-NET'`
  (106 weeks available). Same fetcher, one argument.
- **CIDRAP news wall** — `https://www.cidrap.umn.edu/rss.xml` returns valid RSS
  (200, `application/rss+xml`). A good second events instrument; overlaps WHO DON.
- **Measles in wastewater** — [`akvg-8vrb`](https://data.cdc.gov/d/akvg-8vrb),
  updated weekly. Topical given recent US measles activity.
- **Avian influenza A(H5) in wastewater** — [`mtpu-urpp`](https://data.cdc.gov/d/mtpu-urpp).
  The single best early indicator for an H5 spillover event.
- **Mpox in wastewater** — [`xpxn-rzgz`](https://data.cdc.gov/d/xpxn-rzgz).
- **RSV test positivity by HHS region** — [`3cxc-4k8q`](https://data.cdc.gov/d/3cxc-4k8q) (NREVSS).
- **State-level ARI activity** — [`f3zz-zga5`](https://data.cdc.gov/d/f3zz-zga5),
  a categorical activity level per state; would suit a map more than a card.
- **Preliminary US COVID / RSV burden estimates** — [`ahrf-yqdt`](https://data.cdc.gov/d/ahrf-yqdt),
  [`sumd-iwm8`](https://data.cdc.gov/d/sumd-iwm8).
- **CDC content syndication API** — `https://tools.cdc.gov/api/v2/resources/media?format=json`
  returns 6,633 items with topic tags; a tag-filtered outbreak wall is possible
  but the feed is mostly evergreen health content, so it needs careful filtering.

## Dead ends

- **WHO Disease Outbreak News RSS** — `https://www.who.int/feeds/entity/csr/don/en/rss.xml`
  returns **HTTP 404** with WHO's HTML error page. WHO's own OData endpoint
  (`/api/news/diseaseoutbreaknews`) serves the same list as clean JSON and is
  used instead.
- **ProMED-mail** — `https://promedmail.org/feed/` returns **HTTP 404** (a
  Next.js error page). ProMED now sits behind an account/subscription; no open
  machine-readable feed found.
- **CDC HAN (Health Alert Network) RSS** — `https://emergency.cdc.gov/han/rss/han.xml`
  returns HTTP 200 but with `content-type: text/html` and the CDC page shell,
  not XML. No working HAN feed found.
- **CDC outbreaks RSS** — `https://www.cdc.gov/outbreaks/rss/outbreaks.xml` → 404.
- **NSSP "combined" ED signal** — `nssp` / `pct_ed_visits_combined` exists in
  Delphi's metadata but is marked inactive and returns **zero rows** for 2026.
  The Socrata equivalent (`vutn-jzwm`) offers only COVID-19 / Influenza / RSV as
  separate pathogens despite its title. Use ARI (`ari-ed-visits`) as the
  combined-respiratory headline instead.
- **RESP-NET "Combined" network** — only 3 weekly rows since Aug 2024, far too
  sparse for a series. COVID-NET and FluSurv-NET are dense (106 and 85 weeks).
- **NWSS site-level tables** (`2ew6-ywp6`, `j9g8-acpt`, `ymmh-divb`, `45cq-cw4i`)
  — these are raw per-sample concentration records, hundreds of thousands of
  rows, with no national rollup. `atcp-73re` + server-side aggregation is the
  cheap path.
- **Delphi covidcast wastewater** — there is no NWSS data source in covidcast;
  wastewater has to come from data.cdc.gov.
