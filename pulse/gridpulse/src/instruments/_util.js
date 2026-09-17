// Shared helpers for GridPulse instruments. Not an instrument file — never
// registered in index.js. Keeps the framework untouched.

// The collector REPLACES snap.series when fetch() returns `series`, so any
// instrument whose upstream window is shorter than its `history` must merge the
// previous series itself. Everything here does.
export function mergeSeries(prevSeries, next, history = 500) {
  const m = new Map();
  for (const p of prevSeries || []) if (p && Number.isFinite(p[0]) && p[1] != null) m.set(p[0], p[1]);
  for (const p of next || []) if (p && Number.isFinite(p[0]) && p[1] != null) m.set(p[0], p[1]);
  return [...m.entries()].sort((a, b) => a[0] - b[0]).slice(-history);
}

// Keep one point per `bucketMs` window (the last one in each bucket).
export function downsample(points, bucketMs) {
  const m = new Map();
  for (const [t, v] of points) {
    if (!Number.isFinite(t) || v == null) continue;
    m.set(Math.floor(t / bucketMs) * bucketMs, v);
  }
  return [...m.entries()].sort((a, b) => a[0] - b[0]);
}

// Keep the most *interesting* point per bucket: the one furthest from `centre`.
// Used for frequency, where the excursion matters more than the mean.
export function downsampleExtreme(points, bucketMs, centre) {
  const m = new Map();
  for (const [t, v] of points) {
    if (!Number.isFinite(t) || v == null) continue;
    const k = Math.floor(t / bucketMs) * bucketMs;
    const cur = m.get(k);
    if (cur == null || Math.abs(v - centre) > Math.abs(cur - centre)) m.set(k, v);
  }
  return [...m.entries()].sort((a, b) => a[0] - b[0]);
}

// --- time zones -------------------------------------------------------------
// Several ISO feeds publish bare local clock times (CAISO "00:05", NYISO
// "08/17/2026 00:05:00"). Intl gives us the real UTC offset including DST.

function partsIn(date, tz) {
  const f = new Intl.DateTimeFormat('en-US', {
    timeZone: tz, hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  const p = {};
  for (const { type, value } of f.formatToParts(date)) p[type] = value;
  return {
    year: +p.year, month: +p.month, day: +p.day,
    hour: +p.hour % 24, minute: +p.minute, second: +p.second,
  };
}

function offsetMs(date, tz) {
  const p = partsIn(date, tz);
  return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - date.getTime();
}

/** Today's calendar date in `tz`, as {year, month, day}. */
export function todayIn(tz, at = Date.now()) {
  const p = partsIn(new Date(at), tz);
  return { year: p.year, month: p.month, day: p.day };
}

/** YYYYMMDD string for a {year,month,day}. */
export function ymd({ year, month, day }) {
  return `${year}${String(month).padStart(2, '0')}${String(day).padStart(2, '0')}`;
}

/** Shift a {year,month,day} by n days. */
export function addDays(d, n) {
  const t = new Date(Date.UTC(d.year, d.month - 1, d.day) + n * 86_400_000);
  return { year: t.getUTCFullYear(), month: t.getUTCMonth() + 1, day: t.getUTCDate() };
}

/** Wall-clock time in `tz` → epoch ms (DST-correct, refined once at the edge). */
export function zonedMs(year, month, day, hour, minute, tz, second = 0) {
  const guess = Date.UTC(year, month - 1, day, hour, minute, second);
  let ms = guess - offsetMs(new Date(guess), tz);
  ms = guess - offsetMs(new Date(ms), tz);
  return ms;
}

// --- misc parsing -----------------------------------------------------------

/** ERCOT stamps look like "2026-08-16 00:04:57-0500" — not ISO until fixed. */
export function ercotTime(s) {
  const t = Date.parse(String(s).replace(' ', 'T').replace(/([+-]\d{2})(\d{2})$/, '$1:$2'));
  return Number.isFinite(t) ? t : null;
}

/** ISO seconds + Z, the shape Elexon's from/to parameters want. */
export function isoZ(ms) {
  return new Date(ms).toISOString().slice(0, 19) + 'Z';
}
