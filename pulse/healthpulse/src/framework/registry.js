// Instrument registry — the one abstraction every dashboard shares.
//
// An instrument is a single "vital sign": one feed, one number (or one event
// stream), one source attribution, one cadence, optional thresholds.
//
//   defineInstrument({
//     id: 'co2-mlo',                 // stable, kebab-case, used as KV key
//     section: 'Air',                // dashboard grouping
//     title: 'CO₂ at Mauna Loa',
//     kind: 'metric' | 'events',     // metric = number + series; events = wall
//     order: 'desc' | 'asc',         // events only: desc = newest first (default),
//                                    //   asc = soonest first for FORWARD-looking walls
//                                    //   (launches, close approaches); past items drop off
//     unit: 'ppm',
//     decimals: 2,
//     cadence: '1d',                 // how often to re-fetch: 5m 15m 1h 6h 1d 7d
//     history: 365,                  // points of series to retain
//     source: { name: 'NOAA GML', url: 'https://…', license: 'public domain' },
//     needsKey: null | 'EIA_API_KEY',// env var name; instrument is skipped if unset
//     thresholds: [                  // evaluated top-down, first match wins
//       { level: 'critical', gte: 430 },
//       { level: 'serious',  gte: 425 },
//       { level: 'warning',  gte: 420 },
//     ],                             // or a function (value, snap) => level
//     higherIsWorse: true,           // colors deltas; null = neutral (no good/bad coloring)
//     staleAfter: '45d',             // UI marks the card stale past this data age;
//                                    //   default = max(3×cadence, 2h). Set for monthly
//                                    //   series whose `at` is the reference period.
//     seriesMode: 'merge' | 'replace', // returned series merge with held history (default)
//     describe: 'One-line plain-English meaning of the number.',
//     async fetch(ctx) {             // ctx = { env, http, prev, now }
//       return { value, at, series?, meta?, items? };
//     },
//   })
//
// fetch() return shape:
//   metric: { value: number, at: ISO string of the *observation* time,
//             series?: [[epochMs, value], …] (full replacement — collector merges),
//             meta?: {} }
//   events: { items: [{ id, at, title, severity?, url?, meta? }], at }
//
// Rules the collector enforces (so instruments stay dumb):
//   - never throw away the previous good snapshot on error ("stale beats fake")
//   - respect cadence; a manual /api/collect?force=1 bypasses it
//   - clamp series to `history`

const CADENCE_MS = {
  m: 60_000,
  h: 3_600_000,
  d: 86_400_000,
  w: 604_800_000,
};

export function parseCadence(s) {
  const m = /^(\d+)\s*([mhdw])$/.exec(String(s).trim());
  if (!m) throw new Error(`bad cadence "${s}" (use e.g. 5m, 1h, 1d, 7d)`);
  return Number(m[1]) * CADENCE_MS[m[2]];
}

const REQUIRED = ['id', 'section', 'title', 'cadence', 'source', 'fetch'];

export function defineInstrument(def) {
  for (const k of REQUIRED) {
    if (def[k] == null) throw new Error(`instrument missing "${k}": ${JSON.stringify(def.id)}`);
  }
  if (!/^[a-z0-9][a-z0-9-]*$/.test(def.id)) throw new Error(`instrument id must be kebab-case: ${def.id}`);
  parseCadence(def.cadence); // validate eagerly
  if (def.staleAfter) parseCadence(def.staleAfter);
  return {
    kind: 'metric',
    order: 'desc',
    staleAfter: null,
    seriesMode: 'merge',
    unit: '',
    decimals: 1,
    history: 200,
    needsKey: null,
    thresholds: null,
    higherIsWorse: true,
    describe: '',
    ...def,
  };
}

export function validateRegistry(list) {
  const seen = new Set();
  for (const inst of list) {
    if (seen.has(inst.id)) throw new Error(`duplicate instrument id: ${inst.id}`);
    seen.add(inst.id);
  }
  return list;
}
