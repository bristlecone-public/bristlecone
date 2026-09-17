// NASA/CCMC DONKI — coronal mass ejection analyses from the M2M catalog.
// This is the only feed on the dashboard that wants a key. api.nasa.gov accepts
// DEMO_KEY (30 requests/hour/IP), but a free personal key from
// https://api.nasa.gov lifts that to 1,000/hour, so the instrument declares
// NASA_API_KEY and is skipped until the secret exists.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

const DAY = 86_400_000;
const ymd = (ms) => new Date(ms).toISOString().slice(0, 10);

// DONKI's own CME type ladder (speed at 21.5 solar radii).
const TYPE_SEVERITY = { S: 'info', C: 'warning', O: 'serious', R: 'critical', ER: 'critical' };
const TYPE_LABEL = { S: 'slow', C: 'common', O: 'occasional', R: 'rare', ER: 'extremely rare' };

export const donkiCme = defineInstrument({
  id: 'donki-cme',
  section: 'Events',
  kind: 'events',
  title: 'Coronal mass ejections (DONKI)',
  cadence: '1h',
  history: 120,
  needsKey: 'NASA_API_KEY',
  source: {
    name: 'NASA CCMC DONKI (M2M catalog)',
    url: 'https://ccmc.gsfc.nasa.gov/tools/DONKI/',
    license: 'public domain (NASA), api.nasa.gov terms of use',
  },
  describe:
    'CMEs measured by NASA’s space-weather analysts over the last 30 days, with the speed and width of each eruption; fast, wide, Earth-directed ones are what produce geomagnetic storms a day or two later.',
  async fetch({ http, env, now }) {
    const url = `https://api.nasa.gov/DONKI/CMEAnalysis?startDate=${ymd(now - 30 * DAY)}&endDate=${ymd(now)}&mostAccurateOnly=true&api_key=${encodeURIComponent(env.NASA_API_KEY)}`;
    const rows = await http.json(url);
    if (!Array.isArray(rows)) throw new Error('DONKI CMEAnalysis did not return an array');
    const items = rows
      .map((r) => {
        const t = Date.parse(r.time21_5 || r.associatedCMEstartTime);
        if (!Number.isFinite(t)) return null;
        const speed = num(r.speed);
        const type = String(r.type || '').toUpperCase();
        return {
          id: r.associatedCMEID || r.link || `cme-${t}`,
          at: new Date(t).toISOString(),
          title: `CME ${speed ?? '?'} km/s, half-angle ${num(r.halfAngle) ?? '?'}°${TYPE_LABEL[type] ? ` (${TYPE_LABEL[type]})` : ''}`,
          severity: TYPE_SEVERITY[type] || 'info',
          url: r.associatedCMELink || r.link || 'https://ccmc.gsfc.nasa.gov/tools/DONKI/',
          meta: {
            speedKms: speed,
            halfAngleDeg: num(r.halfAngle),
            type,
            latitude: num(r.latitude),
            longitude: num(r.longitude),
            note: r.note || null,
          },
        };
      })
      .filter(Boolean);
    return { items };
  },
});
