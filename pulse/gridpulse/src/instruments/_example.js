// Reference instruments showing every shape the framework supports.
// Not imported by index.js — copy patterns from here.

import { defineInstrument } from '../framework/registry.js';
import { num } from '../framework/http.js';

// 1) Simple JSON metric with thresholds.
export const exampleJsonMetric = defineInstrument({
  id: 'example-json',
  section: 'Example',
  title: 'Example JSON metric',
  unit: 'units',
  decimals: 1,
  cadence: '1h',
  history: 168,
  source: { name: 'Example API', url: 'https://example.com/api', license: 'public' },
  thresholds: [
    { level: 'critical', gte: 90 },
    { level: 'serious', gte: 75 },
    { level: 'warning', gte: 60 },
  ],
  higherIsWorse: true,
  describe: 'What this number means in one sentence.',
  async fetch({ http }) {
    const d = await http.json('https://example.com/api/latest.json');
    return { value: num(d.value), at: d.timestamp };
  },
});

// 2) CSV series — return the whole recent series; collector clamps to history.
export const exampleCsvSeries = defineInstrument({
  id: 'example-csv',
  section: 'Example',
  title: 'Example CSV series',
  unit: '%',
  cadence: '1d',
  history: 365,
  source: { name: 'Example Agency', url: 'https://example.com/data.csv' },
  async fetch({ http }) {
    const rows = await http.csv('https://example.com/data.csv', { csv: { comment: '#' } });
    const series = rows
      .map((r) => [Date.parse(r.date), num(r.value)])
      .filter(([t, v]) => Number.isFinite(t) && v != null);
    const [t, v] = series[series.length - 1];
    return { value: v, at: new Date(t).toISOString(), series };
  },
});

// 3) Events wall — items are deduped by id and merged with previous ones.
export const exampleEvents = defineInstrument({
  id: 'example-events',
  section: 'Events',
  kind: 'events',
  title: 'Example alerts',
  cadence: '30m',
  history: 100,
  source: { name: 'Example Alerts', url: 'https://example.com/alerts.rss' },
  async fetch({ http }) {
    const items = await http.feed('https://example.com/alerts.rss');
    return {
      items: items.map((i) => ({
        id: i.id || i.link,
        at: new Date(i.at).toISOString(),
        title: i.title,
        url: i.link,
        severity: /warning|watch/i.test(i.title) ? 'warning' : 'info',
      })),
    };
  },
});

// 4) Keyed API — skipped automatically if the env var is not set.
export const exampleKeyed = defineInstrument({
  id: 'example-keyed',
  section: 'Example',
  title: 'Needs an API key',
  cadence: '1h',
  needsKey: 'EXAMPLE_API_KEY',
  source: { name: 'Example Keyed API', url: 'https://example.com' },
  async fetch({ http, env }) {
    const d = await http.json(`https://example.com/api?api_key=${env.EXAMPLE_API_KEY}`);
    return { value: d.value, at: d.period };
  },
});
