// CAISO Today's Outlook emissions CSV — five-minute CO₂ output of the
// California grid, broken out by source, in metric tonnes per hour:
//
//   Time,Biogas CO2,Biomass CO2,Natural Gas CO2,Coal CO2,Imports CO2,Geothermal CO2
//     00:00,82,112,5047,0,1901,7
//
// Quirks handled: the Time column is a bare Pacific clock time with no date at
// all (the file is "today, so far"), values leading with whitespace, and empty
// cells for sources with nothing to report. Imports CO₂ can be negative when
// California is exporting.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, todayIn, zonedMs } from './_util.js';

const URL = 'https://www.caiso.com/outlook/current/co2.csv';
const TZ = 'America/Los_Angeles';
const HISTORY = 576; // 2 days of 5-minute points

export const caisoCo2 = defineInstrument({
  id: 'caiso-co2',
  section: 'Carbon',
  title: 'California grid CO₂',
  unit: 'tCO₂/h',
  decimals: 0,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: "CAISO Today's Outlook — emissions",
    url: 'https://www.caiso.com/todays-outlook/emissions',
    license: 'CAISO public data',
  },
  higherIsWorse: true,
  describe:
    'Tonnes of CO₂ per hour coming out of the California power system — near its floor at midday when solar carries the state, and climbing steeply the moment the sun sets.',
  async fetch({ http, prev, now }) {
    const rows = await http.csv(URL);
    if (!rows.length) throw new Error('CAISO co2.csv was empty');
    const cols = Object.keys(rows[0]).filter((k) => k && k !== 'Time');
    if (!cols.length) throw new Error(`unexpected CAISO co2.csv columns: ${Object.keys(rows[0])}`);

    const day = todayIn(TZ, now || Date.now());
    const pts = [];
    let lastRow = null;
    for (const r of rows) {
      const m = /^(\d{1,2}):(\d{2})$/.exec(String(r.Time || '').trim());
      if (!m) continue;
      let total = 0;
      let seen = 0;
      for (const c of cols) {
        const v = num(r[c]);
        if (v == null) continue;
        total += v;
        seen++;
      }
      if (!seen) continue; // trailing rows for intervals that have not happened
      pts.push([zonedMs(day.year, day.month, day.day, +m[1], +m[2], TZ), Math.round(total)]);
      lastRow = r;
    }
    if (!pts.length) throw new Error('CAISO co2.csv: no rows with data yet today');
    pts.sort((a, b) => a[0] - b[0]);

    const bySource = {};
    for (const c of cols) {
      const v = num(lastRow[c]);
      if (v != null) bySource[c.replace(/ CO2$/, '')] = Math.round(v);
    }

    const [lastT, lastV] = pts[pts.length - 1];
    return {
      value: lastV,
      at: new Date(lastT).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: { tonnesPerHourBySource: bySource, localTime: lastRow.Time },
    };
  },
});
