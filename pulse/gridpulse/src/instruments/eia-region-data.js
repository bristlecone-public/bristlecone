// EIA Open Data v2 — hourly electricity demand for the Lower 48 (US48), the
// aggregate of every balancing authority in the contiguous United States.
// This is the only feed here that needs a key; it is free and instant:
//   https://www.eia.gov/opendata/register.php
//
// Response shape:
//   { response: { data: [ { period: "2026-08-17T13", respondent: "US48",
//                           type: "D", value: 512345, "value-units": "megawatthours" } ] } }
// `period` is an hour-resolution UTC timestamp with no zone marker.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries } from './_util.js';

const HISTORY = 336; // 14 days of hourly points
const ENDPOINT = 'https://api.eia.gov/v2/electricity/rto/region-data/data/';

function url(key) {
  const q = [
    `api_key=${encodeURIComponent(key)}`,
    'frequency=hourly',
    'data[0]=value',
    'facets[respondent][]=US48',
    'facets[type][]=D',
    'sort[0][column]=period',
    'sort[0][direction]=desc',
    'offset=0',
    'length=168',
  ].join('&');
  return `${ENDPOINT}?${q}`;
}

export const eiaUs48Demand = defineInstrument({
  id: 'eia-us48-demand',
  section: 'Vitals',
  title: 'US Lower-48 demand',
  unit: 'MW',
  decimals: 0,
  cadence: '1h',
  history: HISTORY,
  needsKey: 'EIA_API_KEY',
  source: {
    name: 'EIA Hourly Electric Grid Monitor (API v2)',
    url: 'https://www.eia.gov/electricity/gridmonitor/',
    license: 'US federal government work — public domain',
  },
  higherIsWorse: true,
  describe:
    'Total electricity demand across the contiguous United States, hour by hour — the national headline number every regional grid stress story is measured against.',
  async fetch({ http, env, prev }) {
    const d = await http.json(url(env.EIA_API_KEY));
    const rows = d?.response?.data || [];
    if (!rows.length) throw new Error('EIA returned no rows for US48/D');

    const pts = rows
      .map((r) => [Date.parse(`${r.period}:00:00Z`), num(r.value)])
      .filter(([t, v]) => Number.isFinite(t) && v != null)
      .sort((a, b) => a[0] - b[0]);
    if (!pts.length) throw new Error('EIA rows had no parseable period/value');

    const [t, v] = pts[pts.length - 1];
    return {
      value: v,
      at: new Date(t).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: {
        units: rows[0]['value-units'] || 'megawatthours',
        respondent: rows[0]['respondent-name'] || 'United States Lower 48',
        rows: rows.length,
      },
    };
  },
});
