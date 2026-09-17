// NOAA / National Weather Service active alerts, filtered to the event types
// that are direct heat- and cold-health hazards. Extreme heat is the deadliest
// weather hazard in the US, and cold snaps drive their own excess-mortality
// spike, so the count of active heat/cold alert areas is a genuine public
// health vital sign rather than a weather curiosity.
//
// Keyless, but api.weather.gov requires a descriptive User-Agent (the framework
// sets one from src/site.js). Alerts update continuously.
// Event names are the exact strings from https://api.weather.gov/alerts/types.

import { defineInstrument } from '../framework/registry.js';

const EVENTS = [
  'Extreme Heat Warning',
  'Extreme Heat Watch',
  'Heat Advisory',
  'Extreme Cold Warning',
  'Extreme Cold Watch',
  'Cold Weather Advisory',
];

// NOTE: api.weather.gov takes ONE comma-separated `event=` parameter. Repeating
// `event=` (the obvious guess) is accepted with HTTP 200 but silently honours
// only the last occurrence, so the count comes back wrong rather than erroring.
const URL =
  'https://api.weather.gov/alerts/active?event=' +
  EVENTS.map(encodeURIComponent).join(',');

export const heatColdAlerts = defineInstrument({
  id: 'heat-cold-alerts',
  section: 'Environment',
  title: 'Active heat & cold health alerts',
  unit: 'alerts',
  decimals: 0,
  cadence: '12h',
  history: 288, // ~3 days at 15 min
  source: {
    name: 'NOAA / National Weather Service — active alerts',
    url: 'https://api.weather.gov/alerts/active',
    license: 'public domain (US Government work)',
  },
  // Operational bands, not an official scale: a handful of alerts is routine,
  // dozens means a regional heat or cold event, hundreds means a national one.
  thresholds: [
    { level: 'critical', gte: 150 },
    { level: 'serious', gte: 50 },
    { level: 'warning', gte: 10 },
  ],
  higherIsWorse: true,
  describe:
    'How many NWS heat or cold health alerts are in force across the US right now. Extreme heat kills more Americans in a typical year than any other weather hazard, and these alerts are what triggers cooling centres and utility shut-off moratoria.',
  async fetch({ http, now }) {
    const d = await http.json(URL, { headers: { accept: 'application/geo+json' } });
    const features = d.features || [];

    const byEvent = {};
    let heat = 0;
    let cold = 0;
    for (const f of features) {
      const e = f.properties?.event || 'Unknown';
      byEvent[e] = (byEvent[e] || 0) + 1;
      if (/heat/i.test(e)) heat++;
      else cold++;
    }

    const at = Date.parse(d.updated) ? new Date(d.updated).toISOString() : new Date(now).toISOString();
    return { value: features.length, at, meta: { byEvent, heat, cold, events: EVENTS } };
  },
});
