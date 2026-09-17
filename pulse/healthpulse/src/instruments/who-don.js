// WHO Disease Outbreak News — the authoritative global wall of "something is
// happening somewhere". Each DON is a formal WHO notification of an outbreak
// judged to have international public-health significance.
//
// WHO's advertised DON RSS feed (/feeds/entity/csr/don/en/rss.xml) is dead —
// it 404s and returns the WHO error page as HTML. The site's own OData endpoint
// still serves the same list as clean JSON, sorted, with publication timestamps
// and item slugs, so that is used instead. Keyless, no documented rate limit.

import { defineInstrument } from '../framework/registry.js';

const API =
  'https://www.who.int/api/news/diseaseoutbreaknews' +
  '?sf_provider=dynamicProvider372&sf_culture=en' +
  '&%24orderby=PublicationDateAndTime%20desc' +
  '&%24select=Title,PublicationDateAndTime,ItemDefaultUrl' +
  '&%24format=json&%24top=40&%24count=true';

const ITEM_BASE = 'https://www.who.int/emergencies/disease-outbreak-news/item/';

// High-consequence pathogens: viral haemorrhagic fevers, novel influenza,
// and the classic epidemic-prone diseases WHO tracks under the IHR.
const HIGH_CONSEQUENCE =
  /ebola|marburg|lassa|nipah|hendra|mers|smallpox|mpox|plague|anthrax|yellow fever|cholera|diphtheria|polio|influenza a\s*\(h[57]|avian influenza|crimean-congo|rift valley/i;

export const whoOutbreakNews = defineInstrument({
  id: 'who-outbreak-news',
  section: 'Outbreaks',
  kind: 'events',
  title: 'WHO Disease Outbreak News',
  cadence: '12h',
  history: 120,
  source: {
    name: 'World Health Organization — Disease Outbreak News',
    url: 'https://www.who.int/emergencies/disease-outbreak-news',
    license: 'WHO content, CC BY-NC-SA 3.0 IGO',
  },
  describe:
    'Every formal WHO notification of an outbreak with potential international significance — the closest thing there is to a global early-warning wall.',
  async fetch({ http }) {
    const d = await http.json(API, { headers: { accept: 'application/json' } });
    const rows = d.value || [];
    if (!rows.length) throw new Error('WHO DON API returned no items');

    const items = rows
      .map((r) => {
        const slug = String(r.ItemDefaultUrl || '').replace(/^\//, '');
        const t = Date.parse(r.PublicationDateAndTime);
        if (!Number.isFinite(t) || !r.Title) return null;
        return {
          id: slug || `who|${r.Title}`,
          at: new Date(t).toISOString(),
          title: r.Title,
          url: slug ? ITEM_BASE + slug : 'https://www.who.int/emergencies/disease-outbreak-news',
          severity: HIGH_CONSEQUENCE.test(r.Title) ? 'serious' : 'warning',
        };
      })
      .filter(Boolean);

    return { items, meta: { total: d['@odata.count'] ?? null, returned: items.length } };
  },
});
