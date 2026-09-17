// Big-provider health, read straight from the providers' own status pages.
//
// Statuspage.io exposes an identical, keyless, CORS-open JSON API on every
// hosted page:
//   /api/v2/status.json     → { status: { indicator: none|minor|major|critical } }
//   /api/v2/incidents.json  → { incidents: [ { id, name, status, impact, … } ] }
// (OpenAI's page is incident.io but emulates the same two routes.)
//
// AWS has no Statuspage; its Service Health Dashboard publishes RSS instead.
//
// Docs: https://www.atlassian.com/software/statuspage/features (Status API)

import { defineInstrument } from '../framework/registry.js';

// One list, used by both instruments below.
const PROVIDERS = [
  { name: 'GitHub', base: 'https://www.githubstatus.com' },
  { name: 'Cloudflare', base: 'https://www.cloudflarestatus.com' },
  { name: 'npm', base: 'https://status.npmjs.org' },
  { name: 'Discord', base: 'https://discordstatus.com' },
  { name: 'OpenAI', base: 'https://status.openai.com' },
  { name: 'Atlassian', base: 'https://status.atlassian.com' },
  { name: 'Zoom', base: 'https://status.zoom.us' },
];

const AWS_RSS = 'https://status.aws.amazon.com/rss/all.rss';
const DAY = 86_400_000;

// Statuspage "impact" / "indicator" → our four-level status palette.
const IMPACT = { none: 'good', maintenance: 'good', minor: 'warning', major: 'serious', critical: 'critical' };

// Fetch the same Statuspage route from every provider; tolerate individual
// failures (a status page being down must not blank the whole card) but fail
// loudly if nobody answered.
async function fromAll(http, route) {
  const settled = await Promise.allSettled(
    PROVIDERS.map(async (p) => ({ provider: p, data: await http.json(`${p.base}/api/v2/${route}`) })),
  );
  const ok = settled.filter((s) => s.status === 'fulfilled').map((s) => s.value);
  if (!ok.length) throw new Error(`all ${PROVIDERS.length} status pages failed for ${route}`);
  return { ok, failed: PROVIDERS.length - ok.length };
}

// RSS pubDate uses US timezone abbreviations ("Mon, 17 Aug 2026 04:22:30 PDT")
// which not every JS engine parses. Fall back to explicit offsets.
const TZ = { PDT: '-0700', PST: '-0800', EDT: '-0400', EST: '-0500', UTC: '+0000', GMT: '+0000' };
function parseRssDate(s) {
  let t = Date.parse(s);
  if (Number.isFinite(t)) return t;
  t = Date.parse(String(s).replace(/\b([A-Z]{3})\b$/, (m) => TZ[m] || m));
  return Number.isFinite(t) ? t : null;
}

export const providersDegraded = defineInstrument({
  id: 'providers-degraded',
  section: 'Vitals',
  title: 'Major providers degraded',
  unit: `of ${PROVIDERS.length}`,
  decimals: 0,
  cadence: '1h',
  history: 288,
  source: {
    name: 'Statuspage status APIs (GitHub, Cloudflare, npm, Discord, OpenAI, Atlassian, Zoom)',
    url: 'https://www.githubstatus.com/api',
    license: 'public status pages',
  },
  thresholds: [
    { level: 'critical', gte: 4 },
    { level: 'serious', gte: 2 },
    { level: 'warning', gte: 1 },
  ],
  higherIsWorse: true,
  describe:
    'How many of seven load-bearing internet providers are reporting anything other than "all systems operational" right now.',
  async fetch({ http, now }) {
    const { ok, failed } = await fromAll(http, 'status.json');
    const states = ok.map(({ provider, data }) => ({
      provider: provider.name,
      indicator: data?.status?.indicator || 'unknown',
      description: data?.status?.description || '',
    }));
    const degraded = states.filter((s) => s.indicator !== 'none' && s.indicator !== 'maintenance');
    return {
      value: degraded.length,
      at: new Date(now).toISOString(),
      meta: {
        checked: states.length,
        unreachable: failed,
        degraded: degraded.map((s) => `${s.provider}: ${s.description || s.indicator}`),
      },
    };
  },
});

export const providerIncidents = defineInstrument({
  id: 'provider-incidents',
  section: 'Incidents',
  kind: 'events',
  title: 'Major provider incidents',
  cadence: '1h',
  history: 120,
  source: {
    name: 'Provider status pages + AWS Service Health Dashboard',
    url: 'https://www.githubstatus.com/history',
    license: 'public status pages',
  },
  describe:
    'Open and recently-resolved incidents declared by the platforms most of the web leans on, newest first.',
  async fetch({ http, now }) {
    const cutoff = now - 14 * DAY;
    const items = [];

    const { ok } = await fromAll(http, 'incidents.json');
    for (const { provider, data } of ok) {
      for (const inc of data?.incidents || []) {
        const at = Date.parse(inc.updated_at || inc.started_at || inc.created_at);
        if (!Number.isFinite(at) || at < cutoff) continue;
        const live = inc.status && inc.status !== 'resolved' && inc.status !== 'postmortem';
        items.push({
          id: `sp:${provider.name}:${inc.id}`,
          at: new Date(at).toISOString(),
          title: `${provider.name} · ${inc.name}${live ? '' : ` (${inc.status})`}`,
          severity: live ? IMPACT[inc.impact] || 'warning' : 'good',
          url: inc.shortlink || `${provider.base}/incidents/${inc.id}`,
          meta: { provider: provider.name, impact: inc.impact, status: inc.status, startedAt: inc.started_at },
        });
      }
    }

    // AWS: RSS only, and chatty — keep the dozen most recent recent-enough items.
    try {
      const feed = await http.feed(AWS_RSS);
      const aws = feed
        .map((i) => ({ ...i, ts: parseRssDate(i.at) }))
        .filter((i) => i.ts && i.ts >= cutoff)
        .sort((a, b) => b.ts - a.ts)
        .slice(0, 12);
      for (const i of aws) {
        items.push({
          id: `aws:${i.id || i.link + i.ts}`,
          at: new Date(i.ts).toISOString(),
          title: `AWS · ${i.title}`,
          severity: /resolved|informational/i.test(i.title)
            ? 'good'
            : /disruption|outage/i.test(i.title)
              ? 'serious'
              : 'warning',
          url: i.link || 'https://health.aws.amazon.com/health/status',
          meta: { provider: 'AWS' },
        });
      }
    } catch {
      // AWS RSS is best-effort; the Statuspage half of the wall still stands.
    }

    return { items, at: new Date(now).toISOString(), meta: { providers: PROVIDERS.length + 1, windowDays: 14 } };
  },
});
