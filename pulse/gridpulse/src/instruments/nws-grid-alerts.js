// Grid-stress weather: active NWS watches and warnings for the four hazards
// that actually move electricity demand or knock generation and lines over —
// extreme heat, extreme cold, high wind and ice.
//
// Every US grid emergency of the last decade started as one of these: Uri
// (extreme cold, Feb 2021), the September 2023 ERCOT conservation appeals
// (extreme heat), the 2022 Elliott rolling blackouts (extreme cold). The events
// wall is the "what is about to be tested" panel of the dashboard.
//
// api.weather.gov is keyless but expects a real User-Agent with contact info —
// the framework's site UA provides that.

import { defineInstrument } from '../framework/registry.js';

const EVENTS = [
  'Extreme Heat Warning',
  'Extreme Heat Watch',
  'Extreme Cold Warning',
  'High Wind Warning',
  'Ice Storm Warning',
];
const URL =
  'https://api.weather.gov/alerts/active?status=actual&event=' +
  EVENTS.map(encodeURIComponent).join(',');

// NWS severity vocabulary → the framework's status palette.
const SEVERITY = { Extreme: 'critical', Severe: 'serious', Moderate: 'warning', Minor: 'warning' };

export const gridAlerts = defineInstrument({
  id: 'grid-alerts',
  section: 'Events',
  kind: 'events',
  title: 'Grid-stress weather alerts (US)',
  cadence: '30m',
  history: 120,
  source: {
    name: 'NWS / api.weather.gov active alerts',
    url: 'https://api.weather.gov/alerts/active',
    license: 'US federal government work — public domain',
  },
  describe:
    'Live National Weather Service warnings for the weather that breaks grids: extreme heat, extreme cold, high wind and ice.',
  async fetch({ http }) {
    const d = await http.json(URL, { headers: { accept: 'application/geo+json' } });
    const features = d?.features || [];

    const counts = {};
    const items = [];
    for (const f of features) {
      const p = f?.properties;
      if (!p?.id) continue;
      counts[p.event] = (counts[p.event] || 0) + 1;
      const area = String(p.areaDesc || '').replace(/\s+/g, ' ');
      items.push({
        id: p.id,
        at: new Date(p.sent || p.effective || p.onset || Date.now()).toISOString(),
        title: `${p.event} — ${area.length > 110 ? `${area.slice(0, 110)}…` : area}`,
        severity: SEVERITY[p.severity] || 'info',
        url: p['@id'] || null,
        meta: {
          senderName: p.senderName || null,
          expires: p.expires || null,
          urgency: p.urgency || null,
          certainty: p.certainty || null,
        },
      });
    }

    return {
      items,
      at: d?.updated || new Date().toISOString(),
      meta: { activeNow: features.length, byEvent: counts, watching: EVENTS },
    };
  },
});
