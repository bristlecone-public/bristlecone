// arXiv API — keyless Atom. Terms of use ask for <= 1 request per 3 seconds;
// this instrument makes exactly one request per fetch at a 6 h cadence.
//
// Quirk that shapes the design: arXiv's `submittedDate` search index trails
// real time by roughly two to three days (papers are indexed after the
// announcement cycle). A naive "last 24 h" count therefore returns 0 forever.
// We instead count a full 7-day window that ENDS three days ago, which is
// complete, and report it as a per-day rate.

import { defineInstrument } from '../framework/registry.js';

const LAG_DAYS = 3;
const WINDOW_DAYS = 7;
const CATS = '(cat:cs.AI OR cat:cs.LG OR cat:cs.CL)';

const pad = (n) => String(n).padStart(2, '0');
const stamp = (d) =>
  `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}`;

export const arxivAiPapers = defineInstrument({
  id: 'arxiv-ai-papers',
  section: 'Research',
  title: 'AI preprints posted to arXiv',
  unit: 'papers/day',
  decimals: 0,
  cadence: '6h',
  // `at` is intentionally the end of a window three days behind real time
  // (arXiv's submission index lags 2-3 days), so the data age always reads
  // ~3 days. Without this the card would be permanently flagged stale; allow
  // for the 3-day lag plus a fan-out cycle before flagging.
  staleAfter: '5d',
  history: 240, // 60 days of 6-hourly points
  source: {
    name: 'arXiv API',
    url: 'https://info.arxiv.org/help/api/index.html',
    license: 'arXiv API Terms of Use — metadata free to reuse with attribution',
  },
  higherIsWorse: false,
  describe:
    'Daily rate of new cs.AI / cs.LG / cs.CL submissions, averaged over a complete 7-day window ending three days ago (arXiv indexes submissions with that much lag).',
  async fetch({ http, now }) {
    const to = new Date(now - LAG_DAYS * 86_400_000);
    const from = new Date(now - (LAG_DAYS + WINDOW_DAYS) * 86_400_000);
    const q = `${CATS} AND submittedDate:[${stamp(from)} TO ${stamp(to)}]`;
    const xml = await http.text(
      `https://export.arxiv.org/api/query?search_query=${encodeURIComponent(q)}&start=0&max_results=1`,
    );
    const m = /<opensearch:totalResults[^>]*>(\d+)</.exec(xml);
    if (!m) throw new Error('arXiv: no <opensearch:totalResults> in response');
    const total = Number(m[1]);
    if (!total) throw new Error(`arXiv: window ${stamp(from)}–${stamp(to)} returned 0 (index lag grew?)`);
    return {
      value: total / WINDOW_DAYS,
      at: to.toISOString(),
      meta: {
        total,
        windowDays: WINDOW_DAYS,
        lagDays: LAG_DAYS,
        from: from.toISOString().slice(0, 10),
        to: to.toISOString().slice(0, 10),
        categories: 'cs.AI, cs.LG, cs.CL',
      },
    };
  },
});
