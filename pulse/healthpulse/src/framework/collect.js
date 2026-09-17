// The collector: runs due instruments and maintains ONE KV document (`state`)
// that holds every snapshot, the section layout, and the run log.
//
// KV layout (v2 — quota-friendly):
//   state       { site, generatedAt, status, sections, instruments:{id:snap}, runlog }
//
// One read at the start of a run, at most ONE write at the end — and no write
// at all if nothing was due. (v1 wrote snap:<id> per instrument + state +
// runlog every tick: ~3–6k KV writes/day across six workers, blowing the
// 1,000/day free-tier cap. v2 is ~1 write per worker per tick with changes.)
// Legacy v1 `snap:<id>` keys are read once as a migration source, never written.
//
// "Stale beats fake": on fetch error we keep the last good snapshot and only
// annotate it with lastError / lastErrorAt. Age is always visible.

import { parseCadence } from './registry.js';
import { evaluateStatus, worstLevel, effectiveStatus } from './status.js';
import { makeHttp } from './http.js';

const CONCURRENCY = 6;
const RUNLOG_MAX = 20;

export async function collect({ env, instruments, site, force = false, only = null, now = Date.now() }) {
  const http = makeHttp({ userAgent: site.userAgent });
  const kv = env.SNAPSHOTS;
  const prevState = (await kv.get('state', 'json')) || null;
  const snaps = { ...(prevState?.instruments || {}) };

  // one-time migration from v1 per-instrument keys
  for (const inst of instruments) {
    if (!snaps[inst.id] || snaps[inst.id].empty) {
      const legacy = await kv.get(`snap:${inst.id}`, 'json').catch(() => null);
      if (legacy) snaps[inst.id] = legacy;
    }
  }

  const results = [];
  const queue = instruments.filter((i) => !only || only.includes(i.id));
  let changed = false;
  let idx = 0;

  async function runOne(inst) {
    const prev = snaps[inst.id] && !snaps[inst.id].empty ? snaps[inst.id] : null;
    const started = Date.now();
    const base = { id: inst.id, ran: false, ok: null, ms: 0 };

    if (inst.needsKey && !env[inst.needsKey]) {
      const skipped = `missing ${inst.needsKey}`;
      if (prev?.skipped !== skipped) { snaps[inst.id] = { ...(prev || {}), id: inst.id, skipped }; changed = true; }
      return { ...base, skipped };
    }
    const due = force || !prev?.fetchedAt || now - Date.parse(prev.fetchedAt) >= parseCadence(inst.cadence) * 0.95;
    if (!due) return { ...base, skipped: 'not due' };

    try {
      const out = await inst.fetch({ env, http, prev, now });
      const snap = mergeSnapshot(inst, prev, out, now);
      snap.status = evaluateStatus(inst, snap);
      delete snap.skipped;
      snaps[inst.id] = snap;
      changed = true;
      return { ...base, ran: true, ok: true, ms: Date.now() - started, value: snap.value ?? snap.items?.length };
    } catch (err) {
      snaps[inst.id] = {
        ...(prev || { id: inst.id }),
        lastError: String(err?.message || err).slice(0, 500),
        lastErrorAt: new Date(now).toISOString(),
        errorCount: (prev?.errorCount || 0) + 1,
      };
      changed = true;
      return { ...base, ran: true, ok: false, ms: Date.now() - started, error: snaps[inst.id].lastError };
    }
  }

  async function worker() {
    while (idx < queue.length) {
      const inst = queue[idx++];
      results.push(await runOne(inst));
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, queue.length) }, worker));

  let state = prevState;
  if (changed || !prevState) {
    const runlog = (prevState?.runlog || []);
    runlog.unshift({
      at: new Date(now).toISOString(),
      force,
      ran: results.filter((r) => r.ran).length,
      ok: results.filter((r) => r.ok).length,
      failed: results.filter((r) => r.ok === false).map((r) => ({ id: r.id, error: r.error })),
    });
    state = assembleState({ instruments, site, snaps, runlog: runlog.slice(0, RUNLOG_MAX), now });
    await kv.put('state', JSON.stringify(state)); // the run's single write
  }

  return { results, state };
}

export function mergeSnapshot(inst, prev, out, now) {
  const fetchedAt = new Date(now).toISOString();
  if (inst.kind === 'events') {
    const seen = new Map((prev?.items || []).map((i) => [i.id, i]));
    for (const it of out.items || []) {
      if (!it.id) it.id = `${it.at}|${it.title}`.slice(0, 200);
      seen.set(it.id, it);
    }
    const asc = inst.order === 'asc';
    const items = [...seen.values()]
      .filter((i) => i.at && (!asc || Date.parse(i.at) >= now - 3_600_000)) // forward walls drop past items
      .sort((a, b) => (asc ? 1 : -1) * (Date.parse(a.at) - Date.parse(b.at)))
      .slice(0, inst.history);
    return {
      id: inst.id, kind: 'events', items, at: out.at || items[0]?.at || fetchedAt,
      fetchedAt, meta: out.meta || prev?.meta || null, errorCount: 0,
      firstSeenAt: prev?.firstSeenAt || fetchedAt,
    };
  }

  // metric
  const at = out.at || fetchedAt;
  // Returned series are MERGED with what we already hold (union by timestamp,
  // new values win) so feeds that expose only a rolling window still accumulate
  // history. Set `seriesMode: 'replace'` on the instrument to opt out.
  let series = out.series
    ? (inst.seriesMode === 'replace' ? out.series.slice() : [...(prev?.series || []), ...out.series])
    : (prev?.series || []).slice();
  if (!out.series && out.value != null) {
    const ts = Date.parse(at);
    const last = series[series.length - 1];
    if (!last || last[0] !== ts) series.push([ts, out.value]);
    else last[1] = out.value;
  }
  series = dedupeSeries(series).slice(-inst.history);
  const value = out.value ?? (series.length ? series[series.length - 1][1] : null);
  const prevValue = series.length > 1 ? series[series.length - 2][1] : null;
  const vals = series.map((p) => p[1]).filter((v) => v != null);
  return {
    id: inst.id, kind: 'metric', value, at, fetchedAt,
    delta: value != null && prevValue != null ? value - prevValue : null,
    series,
    range: vals.length ? { min: Math.min(...vals), max: Math.max(...vals), n: vals.length } : null,
    meta: out.meta || null,
    errorCount: 0,
    firstSeenAt: prev?.firstSeenAt || fetchedAt,
  };
}

function dedupeSeries(series) {
  const m = new Map();
  for (const [t, v] of series) if (t != null && Number.isFinite(t) && v != null) m.set(t, v);
  return [...m.entries()].sort((a, b) => a[0] - b[0]);
}

function assembleState({ instruments, site, snaps, runlog, now }) {
  const withStatus = {};
  // Per-instrument stored `status` stays the raw threshold status (cards read it
  // and mark their own staleness). `effective` is the rollup-only status that is
  // degraded for stale/failed feeds so section + page pills can't read all-green
  // over a dead feed. See effectiveStatus() in status.js.
  const effective = {};
  for (const inst of instruments) {
    const s = snaps[inst.id];
    const snap = s ? { ...s, status: s.status || 'unknown' } : { id: inst.id, status: 'unknown', empty: true };
    withStatus[inst.id] = snap;
    effective[inst.id] = effectiveStatus(inst, snap, now);
  }
  const sections = [];
  for (const inst of instruments) {
    let sec = sections.find((s) => s.name === inst.section);
    if (!sec) { sec = { name: inst.section, instruments: [], status: 'unknown' }; sections.push(sec); }
    sec.instruments.push(publicInstrument(inst));
  }
  for (const sec of sections) sec.status = worstLevel(sec.instruments.map((i) => effective[i.id]));
  return {
    site: { name: site.name, tagline: site.tagline, domain: site.domain },
    generatedAt: new Date(now).toISOString(),
    status: worstLevel(Object.values(effective)),
    sections,
    instruments: withStatus,
    runlog,
  };
}

// Read-only view for the API: return the stored doc, or an empty skeleton.
export async function buildState({ env, instruments, site, now = Date.now() }) {
  const stored = await env.SNAPSHOTS.get('state', 'json');
  if (stored) return stored;
  return assembleState({ instruments, site, snaps: {}, runlog: [], now });
}

// Strip fetch() and other non-serializable bits before sending to the client.
export function publicInstrument(inst) {
  const { fetch: _f, thresholds, ...rest } = inst;
  return { ...rest, thresholds: typeof thresholds === 'function' ? 'custom' : thresholds };
}
