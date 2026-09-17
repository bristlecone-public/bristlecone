// Lab announcement feeds. All keyless RSS/Atom, all verified to resolve.
//
// Anthropic and Meta AI publish no working feed (see docs/INSTRUMENTS.md,
// "Dead ends") — Anthropic shows up in the incidents wall instead.

import { defineInstrument } from '../framework/registry.js';

const FEEDS = [
  { lab: 'OpenAI', url: 'https://openai.com/news/rss.xml' },
  { lab: 'Google DeepMind', url: 'https://deepmind.google/blog/rss.xml' },
  { lab: 'Google', url: 'https://blog.google/technology/ai/rss/' },
  { lab: 'Hugging Face', url: 'https://huggingface.co/blog/feed.xml' },
  { lab: 'Mistral AI', url: 'https://mistral.ai/news/rss' },
];

const PER_FEED = 12;

export const labAnnouncements = defineInstrument({
  id: 'lab-announcements',
  section: 'Announcements',
  kind: 'events',
  title: 'Lab announcements',
  cadence: '6h',
  staleAfter: '12h', // effective cadence is the 6h fan-out, not 1h
  history: 150,
  source: {
    name: 'OpenAI / DeepMind / Google / Hugging Face / Mistral blogs',
    url: 'https://openai.com/news/',
    license: 'publisher RSS feeds',
  },
  describe:
    'What the labs themselves said this week — model launches, safety posts and research write-ups, straight from their own feeds.',
  async fetch({ http }) {
    const items = [];
    let live = 0;

    await Promise.all(
      FEEDS.map(async (f) => {
        let entries;
        try {
          entries = await http.feed(f.url);
        } catch {
          return;
        }
        if (!Array.isArray(entries) || !entries.length) return;
        live++;
        entries
          .map((e) => ({ ...e, t: Date.parse(e.at) }))
          .filter((e) => Number.isFinite(e.t) && e.title)
          .sort((a, b) => b.t - a.t)
          .slice(0, PER_FEED)
          .forEach((e) => {
            items.push({
              id: `${f.lab}:${e.id || e.link}`,
              at: new Date(e.t).toISOString(),
              title: `${f.lab} — ${e.title}`.slice(0, 240),
              url: e.link || null,
              severity: 'info',
              meta: { lab: f.lab },
            });
          });
      }),
    );

    if (!live) throw new Error('no announcement feed answered');
    return { items, meta: { feedsLive: live, feedsConfigured: FEEDS.length } };
  },
});
