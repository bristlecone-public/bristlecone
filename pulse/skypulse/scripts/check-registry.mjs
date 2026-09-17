// Static sanity check: registry loads, ids unique, cadences parse, every
// instrument has a source URL. Prints the inventory table. Exit 1 on error.
import { instruments } from '../src/instruments/index.js';
import { validateRegistry, parseCadence } from '../src/framework/registry.js';

try {
  validateRegistry(instruments);
  const rows = instruments.map((i) => ({
    id: i.id, section: i.section, kind: i.kind, cadence: i.cadence,
    key: i.needsKey || '', source: i.source.name, thresholds: i.thresholds ? (typeof i.thresholds === 'function' ? 'fn' : i.thresholds.length) : '-',
  }));
  for (const i of instruments) {
    parseCadence(i.cadence);
    if (!i.source?.url) throw new Error(`${i.id}: source.url missing`);
    if (typeof i.fetch !== 'function') throw new Error(`${i.id}: fetch missing`);
  }
  console.table(rows);
  console.log(`${instruments.length} instruments in ${new Set(rows.map((r) => r.section)).size} sections — OK`);
} catch (e) {
  console.error('REGISTRY ERROR:', e.message);
  process.exit(1);
}
