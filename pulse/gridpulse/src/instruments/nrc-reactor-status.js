// US nuclear fleet output, from the NRC's daily Power Reactor Status Report.
// Pipe-delimited plain text, one row per reactor per day, 365 days deep:
//
//   ReportDt|Unit|Power
//   8/17/2026 12:00:00 AM|Arkansas Nuclear 1|100
//
// "Power" is percent of licensed thermal power. 0 = shut down (refuelling or
// trip). The fleet mean is the single best keyless read on US baseload health.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

// Use the canonical capitalisation: nrc.gov's Akamai edge serves it reliably
// and 403s the all-lowercase alias. It also rejects long User-Agent strings,
// so we send a short one — still identifying GridPulse, no browser spoofing.
const URL =
  'https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/PowerReactorStatusForLast365Days.txt';
const HEADERS = { 'user-agent': 'GridPulse/0.1 (+https://gridpulse.pages.dev)' };

export const usNuclearFleet = defineInstrument({
  id: 'us-nuclear-fleet',
  section: 'Vitals',
  title: 'US nuclear fleet output',
  unit: '%',
  decimals: 1,
  cadence: '1d',
  history: 365,
  source: {
    name: 'NRC Power Reactor Status Report',
    url: 'https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/',
    license: 'US federal government work — public domain',
  },
  higherIsWorse: false,
  describe:
    'Average percent of rated power across every operating US commercial reactor — the always-on floor under the grid, which sags every spring and autumn as units go offline to refuel.',
  async fetch({ http }) {
    // ~1.3 MB of plain text; give it room.
    const text = await http.text(URL, { headers: HEADERS, timeout: 45_000 });
    const lines = text.split(/\r?\n/);
    if (!/ReportDt/i.test(lines[0] || '')) throw new Error('unexpected NRC header row');

    const byDay = new Map(); // dayMs -> { sum, n, offline }
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i];
      if (!line.trim()) continue;
      const cells = line.split('|');
      if (cells.length < 3) continue;
      const m = /^\s*(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(cells[0]);
      const pct = num(cells[2]);
      if (!m || pct == null || pct < 0 || pct > 105) continue;
      const t = Date.UTC(+m[3], +m[1] - 1, +m[2]);
      const rec = byDay.get(t) || { sum: 0, n: 0, offline: 0, full: 0 };
      rec.sum += pct;
      rec.n += 1;
      if (pct === 0) rec.offline += 1;
      if (pct >= 99) rec.full += 1;
      byDay.set(t, rec);
    }
    if (!byDay.size) throw new Error('no reactor rows parsed');

    const days = [...byDay.entries()].sort((a, b) => a[0] - b[0]);
    const series = days.map(([t, r]) => [t, Math.round((r.sum / r.n) * 100) / 100]);
    const [lastT, lastR] = days[days.length - 1];

    return {
      value: Math.round((lastR.sum / lastR.n) * 100) / 100,
      at: new Date(lastT).toISOString(),
      series,
      meta: {
        reactorsReporting: lastR.n,
        reactorsOffline: lastR.offline,
        reactorsAtFullPower: lastR.full,
        reportDate: new Date(lastT).toISOString().slice(0, 10),
      },
    };
  },
});
