// GOES X-ray flare list for the last 7 days — every flare SWPC's event detector
// has closed out, with begin / peak / end times and peak class.

import { defineInstrument } from '../framework/registry.js';

const URL = 'https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json';

// C1.0 → 'warning' territory only from M upward; X is the operationally serious one.
function severityFor(cls) {
  const letter = String(cls || '').charAt(0).toUpperCase();
  const size = parseFloat(String(cls || '').slice(1)) || 0;
  if (letter === 'X') return size >= 10 ? 'critical' : 'serious';
  if (letter === 'M') return size >= 5 ? 'serious' : 'warning';
  return 'info';
}

export const solarFlares = defineInstrument({
  id: 'solar-flares',
  section: 'Sun',
  kind: 'events',
  title: 'Solar flares (GOES, 7 days)',
  cadence: '1h',
  history: 200,
  source: {
    name: 'NOAA SWPC / GOES X-ray flare list',
    url: 'https://www.swpc.noaa.gov/products/goes-x-ray-flux',
    license: 'public domain (US Gov)',
  },
  describe:
    'Every X-ray flare GOES has recorded in the last week, with its peak class; M-class flares degrade HF radio and X-class ones can black it out on the sunlit half of Earth.',
  async fetch({ http }) {
    const rows = await http.json(URL);
    const items = rows
      .filter((r) => r.begin_time && r.max_class)
      .map((r) => {
        const at = new Date(r.max_time || r.begin_time).toISOString();
        const mins = r.begin_time && r.end_time
          ? Math.round((Date.parse(r.end_time) - Date.parse(r.begin_time)) / 60000)
          : null;
        return {
          id: `flare-${r.begin_time}-${r.max_class}`,
          at,
          title: `${r.max_class} flare peaked ${new Date(r.max_time || r.begin_time).toISOString().slice(11, 16)}Z${mins != null ? ` (${mins} min)` : ''}`,
          severity: severityFor(r.max_class),
          url: 'https://www.swpc.noaa.gov/products/goes-x-ray-flux',
          meta: {
            beginClass: r.begin_class,
            maxClass: r.max_class,
            beginTime: r.begin_time,
            endTime: r.end_time,
            peakFluxWm2: r.max_xrlong ?? null,
            satellite: r.satellite ?? null,
          },
        };
      });
    // A genuinely quiet week returns no flares — that is data, not a failure.
    return { items };
  },
});
