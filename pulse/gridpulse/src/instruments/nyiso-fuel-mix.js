// NYISO real-time fuel mix — a plain CSV published to the public MIS, one file
// per day, five-minute rows:
//
//   Time Stamp,Time Zone,Fuel Category,Gen MW
//   08/17/2026 00:05:00,EDT,Nuclear,3159.0
//
// Quirks handled: the filename is keyed to the *Eastern* calendar date (so just
// after midnight ET the file may not exist yet — we fall back to yesterday);
// timestamps are bare local clock times with the zone in its own column.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';
import { mergeSeries, todayIn, addDays, ymd } from './_util.js';

const TZ = 'America/New_York';
const HISTORY = 576; // 2 days of 5-minute points
const ZERO_CARBON = new Set(['Nuclear', 'Hydro', 'Wind', 'Other Renewables']);
const OFFSETS = { EDT: -4, EST: -5 };

const fileUrl = (d) => `https://mis.nyiso.com/public/csv/rtfuelmix/${ymd(d)}rtfuelmix.csv`;

function rowTime(stamp, zone) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})$/.exec(String(stamp).trim());
  if (!m) return null;
  const off = OFFSETS[String(zone).trim().toUpperCase()];
  if (off == null) return null;
  return Date.UTC(+m[3], +m[1] - 1, +m[2], +m[4] - off, +m[5], +m[6]);
}

export const nyisoFuelMix = defineInstrument({
  id: 'nyiso-fuel-mix',
  section: 'Generation Mix',
  title: 'New York carbon-free share',
  unit: '%',
  decimals: 1,
  cadence: '30m',
  history: HISTORY,
  source: {
    name: 'NYISO real-time fuel mix (public MIS)',
    url: 'https://www.nyiso.com/real-time-dashboard',
    license: 'NYISO public market information',
  },
  higherIsWorse: false,
  describe:
    'Share of New York State generation coming from nuclear, hydro, wind and other renewables — an upstate hydro-and-nuclear grid stapled to a downstate gas grid, which is why the number swings with the weather and the season.',
  async fetch({ http, prev, now }) {
    const today = todayIn(TZ, now || Date.now());
    let rows;
    try {
      rows = await http.csv(fileUrl(today));
    } catch {
      rows = await http.csv(fileUrl(addDays(today, -1))); // just after ET midnight
    }
    if (!rows.length || rows[0]['Gen MW'] === undefined) {
      throw new Error(`unexpected NYISO columns: ${Object.keys(rows[0] || {})}`);
    }

    const byTime = new Map(); // t -> { total, clean, fuels }
    for (const r of rows) {
      const t = rowTime(r['Time Stamp'], r['Time Zone']);
      const mw = num(r['Gen MW']);
      const fuel = (r['Fuel Category'] || '').trim();
      if (t == null || mw == null || !fuel) continue;
      const rec = byTime.get(t) || { total: 0, clean: 0, fuels: {} };
      rec.fuels[fuel] = Math.round(mw);
      if (mw > 0) rec.total += mw;
      if (ZERO_CARBON.has(fuel) && mw > 0) rec.clean += mw;
      byTime.set(t, rec);
    }
    if (!byTime.size) throw new Error('NYISO fuel mix: no rows parsed');

    const stamps = [...byTime.keys()].sort((a, b) => a - b);
    const pts = stamps
      .filter((t) => byTime.get(t).total > 0)
      .map((t) => {
        const r = byTime.get(t);
        return [t, Math.round((r.clean / r.total) * 1000) / 10];
      });
    if (!pts.length) throw new Error('NYISO fuel mix: every interval summed to zero');

    const lastT = pts[pts.length - 1][0];
    const lastRec = byTime.get(lastT);

    return {
      value: pts[pts.length - 1][1],
      at: new Date(lastT).toISOString(),
      series: mergeSeries(prev?.series, pts, HISTORY),
      meta: { mwByFuel: lastRec.fuels, totalMW: Math.round(lastRec.total) },
    };
  },
});
