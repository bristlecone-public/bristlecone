# Instruments

Fourteen instruments across seven sections, from eight upstream sources.
Thirteen need no key at all; one (EIA) is optional and free.

Verified column: ✅ = live-fetched successfully with
`node scripts/collect-local.mjs --force` on 2026-08-17.
⚠ = code path checked but the data itself not seen (needs a key).

| id | section | source | endpoint | cadence | key | threshold basis | ✅/⚠ |
|---|---|---|---|---|---|---|---|
| `ercot-demand` | Vitals | [ERCOT supply & demand](https://www.ercot.com/gridmktinfo/dashboards/supplyanddemand) | `…/dashboards/supply-demand.json` | 5m | — | none (raw load has no accepted scale) | ✅ |
| `us-nuclear-fleet` | Vitals | [NRC Power Reactor Status](https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/) | `…/PowerReactorStatusForLast365Days.txt` | 1d | — | none | ✅ |
| `eia-us48-demand` | Vitals | [EIA Hourly Electric Grid Monitor](https://www.eia.gov/electricity/gridmonitor/) | `api.eia.gov/v2/electricity/rto/region-data/data/` | 1h | `EIA_API_KEY` | none | ⚠ |
| `ercot-wind-solar` | Texas / ERCOT | [ERCOT combined wind & solar](https://www.ercot.com/gridmktinfo/dashboards/combinedwindandsolar) | `…/dashboards/combine-wind-solar.json` | 1h | — | none | ✅ |
| `ercot-storage` | Texas / ERCOT | [ERCOT energy storage](https://www.ercot.com/gridmktinfo/dashboards/energystorage) | `…/dashboards/energy-storage-resources.json` | 5m | — | none (sign is the signal) | ✅ |
| `ercot-prc` | Frequency & Reserves | [ERCOT grid conditions](https://www.ercot.com/gridmktinfo/dashboards/supplyanddemand) | `…/dashboards/daily-prc.json` | 5m | — | **ERCOT Energy Emergency Alert triggers**: EEA1 at 2,300 MW, firm load shed at 1,750 MW; warning band at 3,000 MW | ✅ |
| `gb-frequency` | Frequency & Reserves | [Elexon BMRS — FREQ](https://bmrs.elexon.co.uk/system-frequency) | `data.elexon.co.uk/bmrs/api/v1/system/frequency` | 5m | — | **NESO frequency bands**: ±0.1 Hz normal, ±0.2 Hz operational limits, ±0.5 Hz statutory limits | ✅ |
| `ercot-rt-price` | Prices | [ERCOT system-wide prices](https://www.ercot.com/gridmktinfo/dashboards/systemwideprices) | `…/dashboards/system-wide-prices.json` | 15m | — | **scarcity pricing**: $100 above-normal, $1,000 sustained scarcity, $4,000 approaching the $5,000/MWh offer cap | ✅ |
| `gb-market-price` | Prices | [Elexon BMRS — MID](https://bmrs.elexon.co.uk/market-index-prices) | `…/api/v1/balancing/pricing/market-index` | 30m | — | none (no accepted scale for wholesale price) | ✅ |
| `ercot-fuel-mix` | Generation Mix | [ERCOT fuel mix](https://www.ercot.com/gridmktinfo/dashboards/fuelmix) | `…/dashboards/fuel-mix.json` | 5m | — | none | ✅ |
| `nyiso-fuel-mix` | Generation Mix | [NYISO real-time dashboard](https://www.nyiso.com/real-time-dashboard) | `mis.nyiso.com/public/csv/rtfuelmix/<YYYYMMDD>rtfuelmix.csv` | 5m | — | none | ✅ |
| `gb-carbon-intensity` | Carbon | [Carbon Intensity API (NESO)](https://carbonintensity.org.uk/) | `api.carbonintensity.org.uk/intensity/date` | 30m | — | **the API's own index bands**: moderate ≥90, high ≥150, very high ≥235 gCO₂/kWh | ✅ |
| `caiso-co2` | Carbon | [CAISO Today's Outlook](https://www.caiso.com/todays-outlook/emissions) | `caiso.com/outlook/current/co2.csv` | 5m | — | none | ✅ |
| `grid-alerts` (events) | Events | [NWS api.weather.gov](https://api.weather.gov/alerts/active) | `/alerts/active?status=actual&event=…` | 15m | — | NWS severity → palette (Extreme→critical, Severe→serious, Moderate/Minor→warning) | ✅ |

## Notes on the sources

- **ERCOT dashboard JSON** (`www.ercot.com/api/1/services/read/dashboards/*.json`) is
  the feed behind ercot.com's own public grid-conditions pages: keyless, no
  documented rate limit, updated every 5 minutes (`lastUpdated` is carried into
  each instrument's `meta`). Timestamps are `YYYY-MM-DD HH:MM:SS-0500` — not ISO
  until a `T` and an offset colon are inserted (`ercotTime()` in `_util.js`), but
  every row also carries an `epoch` field which we prefer.
- **daily-prc.json** publishes PRC roughly every 10 seconds (3,000+ rows/day). We
  bucket to 5 minutes so a sparkline spans two days instead of eight hours. Its
  `current_condition` block carries `eea_level`, `state` and ERCOT's own
  condition text, which land in `meta` — that is where an EEA declaration
  surfaces.
- **NRC** is 1.3 MB of pipe-delimited text covering 365 days, so one fetch fills
  the whole year-long sparkline. Two edge quirks: the all-lowercase URL alias
  intermittently 403s where the canonical capitalisation does not, and Akamai
  rejects long User-Agent strings — the instrument sends a short
  `GridPulse/0.1 (+https://gridpulse.pages.dev)` instead of the site UA.
- **CAISO** CSVs carry a bare Pacific clock time with no date at all; NYISO
  carries a local timestamp with the zone in a separate column (`EDT`/`EST`).
  Both are resolved to UTC in `_util.js` (`zonedMs`, DST-correct via `Intl`).
  NYISO's filename is keyed to the *Eastern* calendar date, so the instrument
  falls back to yesterday's file just after ET midnight.
- **Elexon BMRS Insights** requires `from`/`to` on both endpoints used here —
  there is no "latest" form. Market Index Data has two reporting providers;
  N2EX publishes zeros, so we take APX (`APXMIDP`).
- **Series merging.** The collector *replaces* `snap.series` whenever `fetch()`
  returns one, so every instrument whose upstream window is shorter than its
  `history` merges the previous series itself via `mergeSeries()` in
  `src/instruments/_util.js`. That file is a shared helper, not an instrument,
  and is deliberately not registered in `index.js`.

## Candidates / next

Verified as working during research but not wired up, in rough order of value:

- **CAISO Today's Outlook** — [`fuelsource.csv`](https://www.caiso.com/outlook/current/fuelsource.csv)
  (5-min generation by fuel, incl. batteries and imports),
  [`demand.csv`](https://www.caiso.com/outlook/current/demand.csv),
  [`netdemand.csv`](https://www.caiso.com/outlook/current/netdemand.csv) — the
  duck curve itself: demand minus wind and solar. All keyless, all 200 OK.
- **NYISO real-time load** — `https://mis.nyiso.com/public/csv/pal/<YYYYMMDD>pal.csv`
  (5-min load per zone, 11 zones; sum for statewide). Keyless, verified.
- **ERCOT load forecast vs actual** — `…/dashboards/loadForecastVsActual.json`.
  Forecast error in MW is a genuine grid-stress signal and the endpoint is live.
- **Elexon demand outturn** — `…/api/v1/demand/outturn/summary?from=&to=`
  (5-min GB national demand) and
  `…/api/v1/generation/outturn/summary` (GB fuel mix per settlement period).
  Both verified 200; would give GB a demand and a mix instrument.
- **Elexon system prices** — `…/api/v1/balancing/settlement/system-prices/<date>/<period>`
  (imbalance price, `DISEBSP`). Verified, but settles ~24 h late.
- **Carbon Intensity regional** — `api.carbonintensity.org.uk/regional` for a
  14-region GB breakdown.
- **EIA fuel-type-data** — `…/v2/electricity/rto/fuel-type-data/data/` for a
  US-wide hourly generation mix (same `EIA_API_KEY`).
- **EIA per-BA demand** — the same `region-data` route with
  `facets[respondent][]=ERCO|CISO|PJM|MISO` for a four-market comparison card.

## Dead ends

| Feed | What happened |
|---|---|
| `ercot.com/api/1/services/read/dashboards/todays-outlook.json` | **403 behind Incapsula.** Every other dashboard JSON on the same host is open; this one is bot-walled. Its content (load vs capacity outlook) is largely reconstructable from `supply-demand.json`, which is what `ercot-demand` uses. |
| `…/dashboards/wind-power-production---hourly-averaged-actual-and-forecasted-values.json` | 404. The wind data lives in `combine-wind-solar.json` instead. |
| `…/dashboards/real-time-system-conditions.json`, `systemWideDemand.json`, `hb-price.json`, `todays-outlook-d.json` | 404 — guessed names, no such endpoints. |
| MISO real-time data broker (`api.misoenergy.org/MISORTWDDataBroker/…?messageType=getfuelmix&returnType=json`) | Returns HTTP 200 with `{"error": "no data"}` for both `getfuelmix` and `gettotalload`. Endpoint is alive but serves nothing to us — possibly geo/agent gated. MISO is therefore absent from the dashboard. |
| **ERCOT system frequency** | No keyless machine-readable feed found. ERCOT's frequency widget lives on the Incapsula-protected `todays-outlook` path. `gb-frequency` (Elexon) carries the Frequency section instead; the brief's 59.95/60.05 Hz thresholds are for a 60 Hz system and were translated to GB's 50 Hz NESO bands. |
| `api.weather.gov/alerts/active?…&limit=N` | HTTP 400 — `limit` is not a recognised parameter on the `active` route (it is on `/alerts`). Items are capped instrument-side instead. |
| NWS event name `Excessive Heat Warning` | Returns an empty collection; the NWS retired it in favour of **Extreme Heat Warning**. Using the old name silently yields zero events. |
