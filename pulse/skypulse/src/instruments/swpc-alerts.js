// SWPC alerts, watches and warnings — the official space-weather events wall.
// Each record is a fixed-format text bulletin; we lift the headline line out of
// the message body and map it onto the dashboard's severity palette.

import { defineInstrument } from '../framework/registry.js';

const URL = 'https://services.swpc.noaa.gov/products/alerts.json';
const HEADLINE = /^(EXTENDED\s+|CONTINUED\s+|CANCEL\s+)?(ALERT|WARNING|WATCH|SUMMARY)\s*:/i;

function headline(message) {
  const line = String(message || '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .find((l) => HEADLINE.test(l));
  return line ? line.replace(/\s+$/, '') : null;
}

function serial(message) {
  const m = /Serial Number:\s*(\d+)/i.exec(String(message || ''));
  return m ? m[1] : null;
}

export function severityFor(title) {
  const t = String(title || '').toUpperCase();
  if (/^(CANCEL|SUMMARY)/.test(t)) return 'info';
  // Top of each NOAA scale, plus the Kp equivalents (Kp 8-9 = G4/G5).
  if (/\b[GRS][45]\b/.test(t) || /K-INDEX OF [89]/.test(t)) return 'critical';
  if (/\b[GRS]3\b/.test(t) || /K-INDEX OF 7/.test(t) || /X-RAY EVENT.*\bX\d/.test(t)) return 'serious';
  // Kp 4 is unsettled, not a storm — G1 only starts at Kp 5.
  if (/K-INDEX OF 4/.test(t)) return 'info';
  if (/^(ALERT|WARNING|EXTENDED WARNING|CONTINUED ALERT|EXTENDED ALERT)/.test(t)) return 'warning';
  if (/^WATCH/.test(t)) return 'warning';
  return 'info';
}

export const swpcAlerts = defineInstrument({
  id: 'swpc-alerts',
  section: 'Events',
  kind: 'events',
  title: 'SWPC alerts, watches & warnings',
  cadence: '1h',
  history: 150,
  source: {
    name: 'NOAA SWPC alerts',
    url: 'https://www.swpc.noaa.gov/products/alerts-watches-and-warnings',
    license: 'public domain (US Gov)',
  },
  describe:
    'Every alert, watch and warning SWPC has issued in the last month — geomagnetic storms, radio blackouts, radiation storms and sudden impulses — as the official record of what actually happened.',
  async fetch({ http }) {
    const rows = await http.json(URL);
    const items = rows
      .map((r) => {
        // issue_datetime is "YYYY-MM-DD HH:MM:SS.mmm" in UTC with no suffix.
        const t = Date.parse(`${String(r.issue_datetime).replace(' ', 'T')}Z`);
        const title = headline(r.message);
        if (!Number.isFinite(t) || !title) return null;
        return {
          id: `swpc-${r.product_id}-${serial(r.message) || t}`,
          at: new Date(t).toISOString(),
          title,
          severity: severityFor(title),
          url: 'https://www.swpc.noaa.gov/products/alerts-watches-and-warnings',
          meta: { productId: r.product_id, serial: serial(r.message) },
        };
      })
      .filter(Boolean);
    if (!items.length) throw new Error('no parseable SWPC alerts');
    return { items };
  },
});
