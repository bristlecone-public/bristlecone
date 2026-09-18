// AirNow (EPA / NOAA / NPS / state + tribal agencies) — current observed Air
// Quality Index. The only keyed instrument in this dashboard: AirNow requires a
// free API key, so the card is skipped (and says so) until AIRNOW_API_KEY is
// set. Everything else here works with zero keys.
//
// Key: https://docs.airnowapi.org/account/request/ — free, instant, 500
// requests/hour. A 12h cadence stays far inside that.
//
// ENDPOINT: the old `aq/observation/zipCode/current/` "Current Observations by
// Reporting Area" service is being RETIRED by AirNow in fall 2026, so this uses
// the surviving `aq/data/` Air Quality Data API instead. That API is
// monitor-level: it takes a lat/long BOUNDING BOX and returns per-site AQI rows,
// so we query a box around a reference metro and reduce to the worst current AQI
// across pollutants. Default box is Houston; override with AIRNOW_BBOX
// ("minLon,minLat,maxLon,maxLat"). AIRNOW_ZIP (from the old endpoint) no longer
// applies — aq/data has no zip lookup.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

// Houston, TX metro box (minLon, minLat, maxLon, maxLat).
const DEFAULT_BBOX = '-95.90,29.40,-94.90,30.20';
// AQI pollutants to request (AirNow parameter codes for the aq/data query).
const PARAMS = 'OZONE,PM25,PM10,CO,NO2,SO2';

// EPA AQI category name from the index value (the breakpoints the card's own
// thresholds also use). aq/data with dataType=A returns the AQI number, not a
// category label, so derive it.
function aqiCategory(aqi) {
  if (aqi == null) return null;
  if (aqi <= 50) return 'Good';
  if (aqi <= 100) return 'Moderate';
  if (aqi <= 150) return 'Unhealthy for Sensitive Groups';
  if (aqi <= 200) return 'Unhealthy';
  if (aqi <= 300) return 'Very Unhealthy';
  return 'Hazardous';
}

// aq/data timestamps are UTC without a zone suffix (e.g. "2026-09-12T13:00").
function parseUtc(s, fallback) {
  const t = String(s || '').trim();
  if (!t) return fallback;
  const ms = Date.parse(/[zZ]$|[+-]\d\d:?\d\d$/.test(t) ? t : `${t}Z`);
  return Number.isFinite(ms) ? new Date(ms).toISOString() : fallback;
}

// "YYYY-MM-DDTHH" in UTC for the aq/data start/end window.
function utcHour(ms) {
  return new Date(ms).toISOString().slice(0, 13);
}

export const airnowAqi = defineInstrument({
  id: 'airnow-aqi',
  section: 'Environment',
  title: 'Air Quality Index (Houston)',
  unit: 'AQI',
  decimals: 0,
  cadence: '12h',
  history: 720, // 30 days of hourly
  needsKey: 'AIRNOW_API_KEY',
  source: {
    name: 'AirNow (US EPA and partner agencies)',
    url: 'https://docs.airnowapi.org/',
    license: 'public domain (US Government work); AirNow API terms apply',
  },
  // EPA's published AQI categories: 51 Moderate, 101 Unhealthy for Sensitive
  // Groups, 151 Unhealthy, 201 Very Unhealthy.
  thresholds: [
    { level: 'critical', gte: 151 },
    { level: 'serious', gte: 101 },
    { level: 'warning', gte: 51 },
  ],
  higherIsWorse: true,
  describe:
    'Worst current AQI across the pollutants reported by monitors near downtown Houston. Above 100 the air is unhealthy for people with asthma, heart disease, or lung disease; above 150 it is unhealthy for everyone.',
  async fetch({ http, env, now }) {
    const bbox = env.AIRNOW_BBOX || DEFAULT_BBOX;
    // Last few hours so we always catch the most recent hourly posting.
    const start = utcHour(now - 3 * 3_600_000);
    const end = utcHour(now);
    const url =
      'https://www.airnowapi.org/aq/data/' +
      `?startDate=${start}&endDate=${end}` +
      `&parameters=${PARAMS}` +
      `&BBOX=${encodeURIComponent(bbox)}` +
      '&dataType=A&format=application/json&verbose=1&monitorType=2&includerawconcentrations=0' +
      `&API_KEY=${encodeURIComponent(env.AIRNOW_API_KEY)}`;

    // TIMEOUT: aq/data is slow enough in the afternoon to exceed the framework's
    // 20s default. The failures were strongly diurnal — 4/5 of the 18:30 UTC runs
    // (13:30 in Houston) aborted against 1/5 of the 06:30 ones — and the error was
    // always "The operation was aborted", i.e. our own AbortController, never an
    // HTTP status. AirNow answers; it just takes longer once the ozone monitors
    // are all reporting and the 3-hour window covers busy hours. A 12h cadence
    // can afford to wait.
    const rows = await http.json(url, { timeout: 60_000 });
    if (!Array.isArray(rows) || !rows.length) throw new Error(`AirNow aq/data returned no rows for BBOX ${bbox}`);

    // dataType=A → the AQI is in `AQI`. Each monitor posts hourly and the latest
    // hour is only partially reported, so keep each (site, pollutant)'s OWN most
    // recent reading, then take the worst across all — the AQI is defined so an
    // area's value is its worst monitor.
    const latest = new Map(); // "site|param" -> {param, aqi, utc, site}
    for (const r of rows) {
      const aqi = num(r.AQI ?? r.Value);
      if (aqi == null) continue;
      const param = r.Parameter || r.ParameterName || '?';
      const utc = String(r.UTC || r.DateObserved || '');
      const site = r.SiteName || r.AgencyName || null;
      const key = `${site}|${param}`;
      const prev = latest.get(key);
      if (!prev || utc > prev.utc) latest.set(key, { param, aqi, utc, site });
    }
    if (!latest.size) throw new Error('AirNow aq/data rows carried no numeric AQI');

    let worst = null;
    const perParam = {}; // pollutant -> worst current AQI across monitors
    for (const v of latest.values()) {
      if (perParam[v.param] == null || v.aqi > perParam[v.param]) perParam[v.param] = v.aqi;
      if (!worst || v.aqi > worst.aqi) worst = v;
    }

    return {
      value: worst.aqi,
      at: parseUtc(worst.utc, new Date(now).toISOString()),
      meta: {
        bbox,
        site: worst.site,
        pollutant: worst.param,
        category: aqiCategory(worst.aqi),
        all: perParam,
      },
    };
  },
});
