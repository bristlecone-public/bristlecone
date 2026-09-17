# Instruments

16 instruments across 8 sections. Every feed below is keyless except `donki-cme`;
the dashboard is fully useful with zero secrets configured.

Verified column: ✅ = live-fetched successfully via
`node scripts/collect-local.mjs --force` on 2026-08-17.

| id | section | source | endpoint | cadence | key | threshold basis | verified |
|---|---|---|---|---|---|---|---|
| `kp-planetary` | Vitals | [NOAA SWPC](https://www.swpc.noaa.gov/products/planetary-k-index) | `/json/planetary_k_index_1m.json` (value) + `/products/noaa-planetary-k-index.json` (series) | 5m | — | NOAA **G-scale**: Kp 5 = G1 (warning), 7 = G3 (serious), 8 = G4 (critical) | ✅ |
| `goes-xray-flux` | Vitals | [NOAA SWPC / GOES](https://www.swpc.noaa.gov/products/goes-x-ray-flux) | `/json/goes/primary/xrays-6-hour.json` | 5m | — | NOAA **R-scale** on 0.1–0.8 nm flux: M1 = 10 µW/m² (warning), X1 = 100 (serious), X10 = 1000 (critical) | ✅ |
| `solar-wind-speed` | Vitals | [NOAA SWPC RTSW](https://www.swpc.noaa.gov/products/real-time-solar-wind) | `/products/geospace/propagated-solar-wind-1-hour.json` | 5m | — | Operational bands used in SWPC forecast discussions: 500 / 700 / 900 km/s | ✅ |
| `sunspot-number` | Vitals | [NOAA SWPC / SILSO](https://www.swpc.noaa.gov/products/solar-cycle-progression) | `/json/solar-cycle/sunspots.json` (+ `predicted-solar-cycle.json` for meta) | 1d | — | none — cycle-phase index, no hazard scale | ✅ |
| `f107-flux` | Sun | [NOAA SWPC / DRAO Penticton](https://www.swpc.noaa.gov/phenomena/f107-cm-radio-emissions) | `/json/f107_cm_flux.json` | 3h | — | none — activity index, no hazard scale | ✅ |
| `solar-flares` (events) | Sun | [NOAA SWPC / GOES](https://www.swpc.noaa.gov/products/goes-x-ray-flux) | `/json/goes/primary/xray-flares-7-day.json` | 15m | — | per-item severity from **flare class** (M = warning, M5+/X = serious, X10+ = critical) | ✅ |
| `solar-wind-bz` | Solar Wind | [NOAA SWPC RTSW](https://www.swpc.noaa.gov/products/real-time-solar-wind) | `/products/geospace/propagated-solar-wind-1-hour.json` | 5m | — | Southward IMF coupling: Bz ≤ −10 nT warning, ≤ −20 nT serious | ✅ |
| `noaa-scales` | Geomagnetic & Aurora | [NOAA SWPC scales](https://www.swpc.noaa.gov/noaa-scales-explanation) | `/products/noaa-scales.json` | 15m | — | The **NOAA R/S/G scales** themselves: 1 = minor, 3 = strong, 4 = severe | ✅ |
| `aurora-hemispheric-power` | Geomagnetic & Aurora | [NOAA SWPC OVATION](https://www.swpc.noaa.gov/products/aurora-30-minute-forecast) | `/text/aurora-nowcast-hemi-power.txt` | 5m | — | ⚠ **informal** OVATION hemispheric-power bands (50 / 100 / 150 GW), not a formal NOAA scale | ✅ |
| `proton-flux-10mev` | Radiation | [NOAA SWPC / GOES](https://www.swpc.noaa.gov/products/goes-proton-flux) | `/json/goes/primary/integral-protons-6-hour.json` | 5m | — | NOAA **S-scale**, defined directly on ≥10 MeV pfu: S1 = 10, S2 = 100, S3 = 1 000 | ✅ |
| `electron-flux-2mev` | Radiation | [NOAA SWPC / GOES](https://www.swpc.noaa.gov/products/goes-electron-flux) | `/json/goes/primary/integral-electrons-6-hour.json` | 5m | — | SWPC **ALTEF3 alert threshold** 1 000 pfu (deep-dielectric charging); 10 000 pfu serious | ✅ |
| `iss-altitude` | Orbit | [CelesTrak GP](https://celestrak.org/NORAD/elements/gp.php?CATNR=25544) | `gp.php?CATNR=25544&FORMAT=json` | 6h | — | none — decay/reboost trace, no hazard scale | ✅ |
| `neo-closest-approach` | Near-Earth Objects | [NASA/JPL CNEOS](https://ssd-api.jpl.nasa.gov/doc/cad.html) | `cad.api?date-min=now&date-max=+30&dist-max=0.05` | 6h | — | ⚠ **landmarks, not a scale**: 1 lunar distance (warning), 0.5 LD (serious), 0.11 LD ≈ geostationary belt (critical) | ✅ |
| `swpc-alerts` (events) | Events | [NOAA SWPC alerts](https://www.swpc.noaa.gov/products/alerts-watches-and-warnings) | `/products/alerts.json` | 15m | — | per-item severity parsed from the bulletin headline (G/R/S level, Kp value) | ✅ |
| `neo-close-approaches` (events) | Events | [NASA/JPL CNEOS](https://ssd-api.jpl.nasa.gov/doc/cad.html) | `cad.api?date-min=now&date-max=+30&dist-max=0.05&sort=dist` | 6h | — | per-item severity from miss distance in LD | ✅ |
| `donki-cme` (events) | Events | [NASA CCMC DONKI](https://ccmc.gsfc.nasa.gov/tools/DONKI/) | `api.nasa.gov/DONKI/CMEAnalysis` | 1h | `NASA_API_KEY` | per-item severity from DONKI's own CME type ladder (S/C/O/R/ER) | ✅ (verified with `DEMO_KEY`) |

## Notes on the sources

- **All `services.swpc.noaa.gov` products are keyless, unauthenticated JSON/text and
  US Government public domain.** They are the same files that back SWPC's own
  dashboards. Nothing here scrapes HTML.
- **Solar wind** uses the *propagated* geospace product rather than the raw L1
  DSCOVR/ACE stream: SWPC has already shifted the observations from L1 to the
  Earth's bow shock, which is what you actually want on a "now" dashboard. One
  6 KB document backs both `solar-wind-speed` and `solar-wind-bz`.
- **GOES particle/X-ray feeds** use the 6-hour windows, not the 1-day ones
  (60 KB vs 242 KB per poll at a 5-minute cadence). The series is stitched
  together locally by the collector, so the sparklines still reach back a week.
- **Sunspot number** is a monthly series, polled daily. It is in Vitals because it
  sets the baseline every other number is read against, not because it moves fast.
- **`sunspots.json` vs `observed-solar-cycle-indices.json`**: both carry the monthly
  SSN back to 1749; the former is 127 KB and the latter 512 KB. We use the small one
  and pull the SWPC prediction for the current month from `predicted-solar-cycle.json`
  into `meta` (failures there are swallowed — a missing forecast must not fail the card).
- **ISS altitude** is derived, not reported: mean motion from the CelesTrak element
  set inverted through Kepler's third law. This gives the mean altitude (clean decay
  sawtooth) rather than the instantaneous one, which swings ±5 km every 90 minutes.
  Expect ~1 km of offset versus an osculating altitude — the *trend* is the point.
- **`neo-close-approaches` items are in the future.** The framework sorts every events
  wall newest-`at`-first and renders relative ages, so the furthest-out approach lands
  at the top and ages read as negative. The approach date is therefore spelled out at
  the front of each item title so rows stand on their own.
- **DONKI / api.nasa.gov**: `DEMO_KEY` works and was used to verify the code path
  (30 req/hour/IP, 50/day). A free personal key raises that to 1 000 req/hour. The
  instrument declares `needsKey: 'NASA_API_KEY'` and is skipped until the secret is set.

## Candidates / next

Verified as live and useful, but not wired up in this pass:

- **SWPC flare & proton probabilities** — `https://services.swpc.noaa.gov/json/solar_probabilities.json`
  (daily; C/M/X-class and ≥10 MeV proton probabilities for the next 1–3 days, plus a
  polar-cap-absorption flag). A natural "Sun" forecast card.
- **Sunspot region report** — `https://services.swpc.noaa.gov/json/sunspot_report.json`
  (per-region area, spot count, Zurich/Mount Wilson magnetic class). Count of
  β-γ-δ regions is the best short-horizon predictor of X-class flares.
- **JPL Sentry impact-risk list** — `https://ssd-api.jpl.nasa.gov/sentry.api`
  (570 KB, returns `count`; `?ps-min=-3` narrows to ~6 notable objects in 1.7 KB).
  Good as "objects currently on the impact-risk list" with Torino/Palermo in meta.
- **Launch Library 2** — `https://ll.thespacedevs.com/2.3.0/launches/upcoming/?limit=10&mode=list`
  (keyless, ~15 req/hour, so 1h cadence minimum; responses took ~10 s in testing).
  A launches events wall. Also forward-looking, so it hits the same sort quirk as
  the NEO wall.
- **OVATION aurora map** — `https://services.swpc.noaa.gov/json/ovation_aurora_latest.json`
  (900 KB GeoJSON-ish grid of aurora probability by lat/lon). Too big for a metric,
  but it would make a real map panel if the framework ever grows one.
- **CelesTrak catalogue counts** — `gp.php?GROUP=starlink&FORMAT=csv` (1.6 MB,
  ~10 900 objects) or `GROUP=active`. A daily "objects in orbit" counter; skipped
  here only to keep payloads small.
- **DONKI `GST` / `FLR` / `notifications`** — same key as `donki-cme`; geomagnetic
  storm records with observed Kp, and the flare catalogue with active-region numbers
  and source locations (which the GOES flare list lacks).
- **GOES `xray-flares-latest.json`** — 451 bytes, the in-progress flare with its
  current class. A cheap "flare in progress right now" indicator.

## Dead ends

- `https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json` and
  `.../mag-7-day.json` — **404**. These paths appear in a lot of older tutorials but
  are gone. Use `/products/geospace/propagated-solar-wind-1-hour.json` (used here) or
  the `/json/rtsw/` family for raw L1 data.
- `https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json` — works, but
  657 KB per request. At a 5-minute cadence that is ~190 MB/day of pointless traffic
  against SWPC; the 6-hour file plus local series accumulation gives the same picture.
- Instantaneous ISS altitude from `api.wheretheiss.at` — keyless and it works, but it
  is a hobby API with no stated SLA, and the instantaneous value oscillates ±5 km per
  orbit, which buries the decay signal the card is meant to show. CelesTrak +
  Kepler inversion replaced it.
