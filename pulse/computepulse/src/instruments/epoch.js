// Epoch AI open datasets — keyless CSV, updated continuously by their research team.
//
// These CSVs contain free-text fields with embedded commas AND embedded
// newlines, so the framework's line-oriented csv() helper would mangle them.
// We fetch text() and run a proper quote-aware parser here instead.

import { defineInstrument } from '../framework/registry.js';

const NOTABLE_MODELS_CSV = 'https://epoch.ai/data/notable_ai_models.csv';
const GPU_CLUSTERS_CSV = 'https://epoch.ai/data/gpu_clusters.csv';

// Frontier-scale threshold used by Epoch and by the EU AI Act / US EO reporting
// regimes to mark "very large training run".
const FRONTIER_FLOP = 1e25;

function parseCsvQuoted(text) {
  const rows = [];
  let row = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { cur += '"'; i++; } else inQuotes = false;
      } else cur += c;
    } else if (c === '"') inQuotes = true;
    else if (c === ',') { row.push(cur); cur = ''; }
    else if (c === '\n') { row.push(cur); rows.push(row); row = []; cur = ''; }
    else if (c !== '\r') cur += c;
  }
  if (cur !== '' || row.length) { row.push(cur); rows.push(row); }
  return rows;
}

function indexer(header, name) {
  const i = header.indexOf(name);
  if (i < 0) throw new Error(`Epoch CSV: column "${name}" missing (schema changed?)`);
  return i;
}

export const epochFrontierModels = defineInstrument({
  id: 'epoch-frontier-models',
  section: 'Frontier & benchmarks',
  title: 'Models trained above 10²⁵ FLOP',
  unit: 'models',
  decimals: 0,
  cadence: '1d',
  // `at` is the publication date of the most recent frontier model, which can
  // legitimately be weeks or months old (this is a cumulative counter, not a
  // live reading). Genuine feed breakage surfaces via lastError; this only
  // prevents a false "stale" flag when no new frontier model has shipped lately.
  staleAfter: '120d',
  history: 400,
  source: {
    name: 'Epoch AI — Notable AI Models',
    url: 'https://epoch.ai/data/notable-ai-models',
    license: 'CC BY 4.0',
  },
  higherIsWorse: false,
  describe:
    'Cumulative count of publicly known models trained with at least 10²⁵ floating-point operations — the compute level at which the EU AI Act and US reporting rules consider a training run frontier-scale.',
  async fetch({ http }) {
    const rows = parseCsvQuoted(await http.text(NOTABLE_MODELS_CSV));
    const head = rows.shift();
    const iModel = indexer(head, 'Model');
    const iOrg = indexer(head, 'Organization');
    const iDate = indexer(head, 'Publication date');
    const iFlop = indexer(head, 'Training compute (FLOP)');

    const recs = [];
    for (const r of rows) {
      const t = Date.parse(r[iDate]);
      const flop = Number(r[iFlop]);
      if (!Number.isFinite(t) || !Number.isFinite(flop) || flop <= 0) continue;
      recs.push({ t, flop, model: r[iModel], org: r[iOrg] });
    }
    if (!recs.length) throw new Error('Epoch: no models with both a date and a training-compute figure');

    const frontier = recs.filter((r) => r.flop >= FRONTIER_FLOP).sort((a, b) => a.t - b.t);
    if (!frontier.length) throw new Error('Epoch: no models at or above 1e25 FLOP');
    const series = frontier.map((r, i) => [r.t, i + 1]);
    const biggest = recs.reduce((a, b) => (b.flop > a.flop ? b : a));
    const newest = frontier[frontier.length - 1];

    return {
      value: frontier.length,
      at: new Date(newest.t).toISOString(),
      series,
      meta: {
        withComputeEstimate: recs.length,
        above1e26: recs.filter((r) => r.flop >= 1e26).length,
        largestRun: `${biggest.model} (${biggest.org}) ${biggest.flop.toExponential(2)} FLOP`,
        mostRecent: `${newest.model} (${newest.org})`,
      },
    };
  },
});

export const epochLargestCluster = defineInstrument({
  id: 'epoch-largest-cluster',
  section: 'Frontier & benchmarks',
  title: 'Largest known AI cluster',
  unit: 'H100-equivalents',
  decimals: 0,
  cadence: '1d',
  // `at` is the first-operational date of the current record-holding cluster,
  // which can stand for a year or more (e.g. xAI Colossus, Jul 2025). This is a
  // high-water-mark, not a live reading — a stuck fetch shows up as lastError,
  // so a long staleAfter just avoids a permanent false "stale" flag.
  staleAfter: '720d',
  history: 200,
  source: {
    name: 'Epoch AI — Data on AI Supercomputers',
    url: 'https://epoch.ai/data/ai-supercomputers',
    license: 'CC BY 4.0',
  },
  higherIsWorse: false,
  describe:
    'Size of the biggest AI training cluster Epoch has confirmed is operational, normalised to H100-equivalent chips. The series shows only record-breaking clusters, so it is the historical high-water mark of hardware concentration.',
  async fetch({ http }) {
    const rows = parseCsvQuoted(await http.text(GPU_CLUSTERS_CSV));
    const head = rows.shift();
    const iName = indexer(head, 'Name');
    const iH100 = indexer(head, 'H100 equivalents');
    const iDate = indexer(head, 'First Operational Date');
    const iOwner = indexer(head, 'Owner');
    const iPower = indexer(head, 'Power Capacity (MW)');
    const iStatus = indexer(head, 'Status');

    const recs = [];
    for (const r of rows) {
      const t = Date.parse(r[iDate]);
      const h = Number(r[iH100]);
      if (!Number.isFinite(t) || !Number.isFinite(h) || h <= 0) continue;
      if (r[iStatus] && r[iStatus] !== 'Existing') continue; // ignore planned / rumoured builds
      recs.push({ t, h, name: r[iName], owner: r[iOwner], mw: Number(r[iPower]) });
    }
    if (!recs.length) throw new Error('Epoch: no operational clusters with a size and a date');

    recs.sort((a, b) => a.t - b.t);
    const series = [];
    let best = null;
    for (const r of recs) {
      if (!best || r.h > best.h) { best = r; series.push([r.t, r.h]); }
    }
    return {
      value: best.h,
      at: new Date(best.t).toISOString(),
      series,
      meta: {
        cluster: best.name,
        owner: best.owner,
        powerMW: Number.isFinite(best.mw) ? Math.round(best.mw) : null,
        clustersTracked: recs.length,
      },
    };
  },
});
