// Dashboard renderer. Zero deps. Reads /api/state, renders sections → cards.
// Card = title + age · hero value + unit + delta · sparkline · status + source.
// Click a card → detail dialog with a full chart (crosshair tooltip), thresholds,
// source/license, and a table view of the series.

const $ = (s, r = document) => r.querySelector(s);
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v != null) e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
};
const SVG = 'http://www.w3.org/2000/svg';
const svg = (tag, attrs = {}) => {
  const e = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};

// ---------- formatting ----------
const fmtNum = (v, d = 1) => {
  if (v == null || !Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return (v / 1e9).toFixed(2) + 'B';
  if (a >= 1e6) return (v / 1e6).toFixed(2) + 'M';
  if (a >= 1e5) return Math.round(v).toLocaleString();
  return v.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: a < 100 ? Math.min(d, 2) : 0 });
};
const ago = (iso) => {
  if (!iso) return '—';
  let s = (Date.now() - Date.parse(iso)) / 1000;
  const future = s < -90;
  if (future) s = -s;
  const span = s < 90 ? null : s < 3600 ? `${Math.round(s / 60)}m` : s < 86400 * 2 ? `${Math.round(s / 3600)}h` : `${Math.round(s / 86400)}d`;
  if (!span) return future ? 'now' : 'just now';
  return future ? `in ${span}` : `${span} ago`;
};
const cadenceMs = (c) => { const m = /^(\d+)([mhdw])$/.exec(c); return m ? m[1] * { m: 6e4, h: 36e5, d: 864e5, w: 6048e5 }[m[2]] : 0; };
const fmtDate = (t) => new Date(t).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
const LEVEL_LABEL = { good: 'normal', warning: 'watch', serious: 'elevated', critical: 'critical', unknown: 'no threshold' };
const LEVEL_ICON = { good: '●', warning: '▲', serious: '◆', critical: '■', unknown: '○' };

// ---------- theme ----------
const root = document.documentElement;
const savedTheme = localStorage.getItem('theme');
if (savedTheme) root.dataset.theme = savedTheme;
$('#theme').addEventListener('click', () => {
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = dark ? 'light' : 'dark';
  localStorage.setItem('theme', root.dataset.theme);
});

// ---------- sparkline ----------
function sparkline(series, { w = 260, h = 44, pad = 3 } = {}) {
  const s = svg('svg', { class: 'spark', viewBox: `0 0 ${w} ${h}`, preserveAspectRatio: 'none' });
  const pts = (series || []).filter((p) => p[1] != null);
  if (pts.length < 2) { s.append(svg('line', { class: 'base', x1: 0, x2: w, y1: h - 1, y2: h - 1 })); return s; }
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = (t) => pad + ((t - x0) / (x1 - x0 || 1)) * (w - 2 * pad);
  const Y = (v) => h - pad - ((v - y0) / (y1 - y0 || 1)) * (h - 2 * pad);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('');
  s.append(svg('path', { class: 'area', d: `${d}L${X(x1).toFixed(1)},${h}L${X(x0).toFixed(1)},${h}Z` }));
  s.append(svg('path', { class: 'line', d }));
  const last = pts[pts.length - 1];
  s.append(svg('circle', { class: 'end', cx: X(last[0]).toFixed(1), cy: Y(last[1]).toFixed(1), r: 3 }));
  return s;
}

// ---------- big chart with crosshair + threshold lines ----------
function bigChart(inst, snap) {
  const w = 720, h = 220, ml = 46, mr = 12, mt = 10, mb = 24;
  const s = svg('svg', { class: 'big-chart', viewBox: `0 0 ${w} ${h}` });
  const pts = (snap.series || []).filter((p) => p[1] != null);
  if (pts.length < 2) { s.append(svg('text', { x: ml, y: h / 2 })).textContent = 'Not enough history yet.'; return s; }
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  const thr = Array.isArray(inst.thresholds) ? inst.thresholds : [];
  for (const t of thr) { const v = t.gte ?? t.gt ?? t.lte ?? t.lt; if (v != null && v > y0 * 0.5 && v < y1 * 2) { y0 = Math.min(y0, v); y1 = Math.max(y1, v); } }
  const padY = (y1 - y0 || 1) * 0.08; y0 -= padY; y1 += padY;
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const X = (t) => ml + ((t - x0) / (x1 - x0 || 1)) * (w - ml - mr);
  const Y = (v) => mt + (1 - (v - y0) / (y1 - y0 || 1)) * (h - mt - mb);
  // gridlines + y labels
  for (let i = 0; i <= 4; i++) {
    const v = y0 + ((y1 - y0) * i) / 4;
    s.append(svg('line', { class: 'grid', x1: ml, x2: w - mr, y1: Y(v), y2: Y(v) }));
    const t = svg('text', { x: ml - 6, y: Y(v) + 4, 'text-anchor': 'end' }); t.textContent = fmtNum(v, inst.decimals); s.append(t);
  }
  // x labels
  for (let i = 0; i <= 4; i++) {
    const t = x0 + ((x1 - x0) * i) / 4;
    const tx = svg('text', { x: X(t), y: h - 6, 'text-anchor': i === 0 ? 'start' : i === 4 ? 'end' : 'middle' });
    tx.textContent = new Date(t).toLocaleDateString(undefined, x1 - x0 > 864e5 * 3 ? { month: 'short', day: 'numeric' } : { hour: '2-digit', minute: '2-digit' });
    s.append(tx);
  }
  // thresholds
  for (const t of thr) {
    const v = t.gte ?? t.gt ?? t.lte ?? t.lt;
    if (v == null || v < y0 || v > y1) continue;
    s.append(svg('line', { class: `thr ${t.level}`, x1: ml, x2: w - mr, y1: Y(v), y2: Y(v) }));
  }
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join('');
  s.append(svg('path', { class: 'line', d }));
  // crosshair
  const cross = svg('line', { class: 'cross', y1: mt, y2: h - mb, x1: -10, x2: -10 });
  const dot = svg('circle', { r: 4, fill: 'var(--series)', stroke: 'var(--surface)', 'stroke-width': 2, cx: -10, cy: -10 });
  s.append(cross, dot);
  const tip = $('#tip');
  s.addEventListener('mousemove', (ev) => {
    const r = s.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * w;
    const t = x0 + ((px - ml) / (w - ml - mr)) * (x1 - x0);
    let best = pts[0];
    for (const p of pts) if (Math.abs(p[0] - t) < Math.abs(best[0] - t)) best = p;
    cross.setAttribute('x1', X(best[0])); cross.setAttribute('x2', X(best[0]));
    dot.setAttribute('cx', X(best[0])); dot.setAttribute('cy', Y(best[1]));
    tip.hidden = false; tip.textContent = `${fmtDate(best[0])} · ${fmtNum(best[1], inst.decimals)} ${inst.unit || ''}`;
    tip.style.left = ev.clientX + 12 + 'px'; tip.style.top = ev.clientY - 28 + 'px';
  });
  s.addEventListener('mouseleave', () => { tip.hidden = true; cross.setAttribute('x1', -10); cross.setAttribute('x2', -10); dot.setAttribute('cx', -10); });
  return s;
}

// ---------- cards ----------
function statusPill(level) {
  return el('span', { class: `pill ${level}` }, el('i'), el('b', {}, `${LEVEL_ICON[level] || ''} ${LEVEL_LABEL[level] || level}`));
}

// Two thresholds, not one. `stale` colours the small age label and is deliberately
// twitchy. `badly` is the honesty gate: past it the reading is not a slightly-late
// current value, it is a historical one, and the card must stop presenting it as
// live. At least a day, so a couple of missed polls never triggers it.
function staleness(inst, snap) {
  const limit = inst.staleAfter ? cadenceMs(inst.staleAfter) : Math.max(cadenceMs(inst.cadence) * 3, 2 * 36e5);
  const age = snap.at ? Date.now() - Date.parse(snap.at) : 0;
  return { stale: !!snap.at && age > limit, badly: !!snap.at && age > Math.max(limit * 2, 24 * 36e5) };
}

function ageEl(inst, snap) {
  const { stale } = staleness(inst, snap);
  return el('span', { class: `age${stale || snap.lastError ? ' stale' : ''}`, title: `observed ${snap.at || '—'} · fetched ${snap.fetchedAt || '—'}` },
    snap.lastError && !snap.at ? 'fetch failed' : ago(snap.at));
}

function metricCard(inst, snap) {
  const { badly } = staleness(inst, snap);
  const card = el('article', { class: `card status-${snap.status || 'unknown'}${badly ? ' is-stale' : ''}`, tabindex: 0, role: 'button', 'aria-label': inst.title });
  card.append(el('h3', {}, el('span', {}, inst.title), ageEl(inst, snap)));
  if (snap.skipped) {
    card.append(el('p', { class: 'skip' }, `Skipped — ${snap.skipped}`));
  } else if (snap.empty || snap.value == null) {
    card.append(el('p', { class: 'empty' }, snap.lastError ? '' : 'No data yet.'));
  } else {
    const dir = snap.delta > 0 ? 'up' : snap.delta < 0 ? 'down' : '';
    const goodBad = snap.delta == null || snap.delta === 0 || inst.higherIsWorse == null ? '' : ((snap.delta > 0) === !!inst.higherIsWorse ? 'bad' : 'good');
    card.append(el('div', { class: 'value-row' },
      el('span', { class: 'value' }, fmtNum(snap.value, inst.decimals)),
      el('span', { class: 'unit' }, inst.unit || ''),
      snap.delta != null ? el('span', { class: `delta ${dir} ${goodBad}` }, `${snap.delta > 0 ? '▲' : snap.delta < 0 ? '▼' : '='} ${fmtNum(Math.abs(snap.delta), inst.decimals)}`) : null,
    ));
    card.append(sparkline(snap.series));
  }
  // "showing last good value" is fine for a value that is minutes late and
  // misleading for one that is weeks old, so say which it is and how old.
  if (snap.lastError) {
    const msg = snap.value == null
      ? `⚠ last fetch failed ${ago(snap.lastErrorAt)}`
      : badly
        ? `⚠ not current — last successful reading ${ago(snap.at)}; every fetch since has failed`
        : `⚠ last fetch failed ${ago(snap.lastErrorAt)} — showing last good value`;
    card.append(el('p', { class: 'err', title: snap.lastError }, msg));
  }
  card.append(el('div', { class: 'card-foot' },
    statusPill(snap.status || 'unknown'),
    el('a', { href: inst.source.url, target: '_blank', rel: 'noopener', onclick: (e) => e.stopPropagation() }, inst.source.name),
  ));
  card.addEventListener('click', () => openDetail(inst));
  card.addEventListener('keydown', (e) => { if (e.key === 'Enter') openDetail(inst); });
  return card;
}

function eventsCard(inst, snap) {
  const card = el('article', { class: `card events status-${snap.status || 'unknown'}` });
  // events walls: header age = when the feed was last checked (items carry their own times)
  card.append(el('h3', {}, el('span', {}, inst.title), ageEl(inst, { ...snap, at: snap.fetchedAt })));
  const items = snap.items || [];
  if (snap.skipped) card.append(el('p', { class: 'skip' }, `Skipped — ${snap.skipped}`));
  else if (!items.length) card.append(el('p', { class: 'empty' }, 'No events yet.'));
  else card.append(el('ul', { class: 'wall' }, items.slice(0, 40).map((it) => el('li', {},
    el('time', { datetime: it.at, title: it.at }, ago(it.at)),
    el('span', {}, el('i', { class: `sev ${it.severity || ''}` }), it.url ? el('a', { href: it.url, target: '_blank', rel: 'noopener' }, it.title) : it.title),
  ))));
  if (snap.lastError) card.append(el('p', { class: 'err', title: snap.lastError }, `⚠ last fetch failed ${ago(snap.lastErrorAt)}`));
  card.append(el('div', { class: 'card-foot' },
    el('span', { class: 'muted' }, `${items.length} items`),
    el('a', { href: inst.source.url, target: '_blank', rel: 'noopener' }, inst.source.name),
  ));
  return card;
}

// ---------- detail ----------
let STATE = null;
async function openDetail(inst) {
  const dlg = $('#detail');
  dlg.innerHTML = '';
  dlg.append(el('button', { class: 'ghost close', onclick: () => dlg.close() }, '✕'));
  dlg.append(el('h2', {}, inst.title));
  if (inst.describe) dlg.append(el('p', { class: 'describe' }, inst.describe));
  dlg.showModal();
  const r = await fetch(`/api/instrument/${inst.id}`).then((r) => r.json());
  const snap = r.snapshot || {};
  if (inst.kind === 'metric') {
    dlg.append(el('div', { class: 'value-row' }, el('span', { class: 'value' }, fmtNum(snap.value, inst.decimals)), el('span', { class: 'unit' }, inst.unit || ''), statusPill(snap.status || 'unknown')));
    dlg.append(bigChart(inst, snap));
  }
  const rows = [
    ['Source', el('a', { href: inst.source.url, target: '_blank', rel: 'noopener' }, inst.source.name)],
    ['License', inst.source.license || '—'],
    ['Cadence', inst.cadence],
    ['Observed', snap.at ? `${new Date(snap.at).toLocaleString()} (${ago(snap.at)})` : '—'],
    ['Fetched', snap.fetchedAt ? `${new Date(snap.fetchedAt).toLocaleString()} (${ago(snap.fetchedAt)})` : '—'],
    ['Range', snap.range ? `${fmtNum(snap.range.min, inst.decimals)} – ${fmtNum(snap.range.max, inst.decimals)} over ${snap.range.n} points` : '—'],
    ['Thresholds', Array.isArray(inst.thresholds) ? inst.thresholds.map((t) => `${t.level}: ${Object.entries(t).filter(([k]) => k !== 'level').map(([k, v]) => `${k} ${v}`).join(' ')}`).join(' · ') : (inst.thresholds || 'none')],
    ['Last error', snap.lastError ? `${snap.lastError} (${ago(snap.lastErrorAt)}, ×${snap.errorCount})` : 'none'],
    ['API', el('a', { href: `/api/instrument/${inst.id}`, target: '_blank' }, `/api/instrument/${inst.id}`)],
  ];
  if (snap.meta) rows.push(['Meta', el('code', {}, JSON.stringify(snap.meta).slice(0, 400))]);
  dlg.append(el('table', { class: 'meta-table' }, rows.map(([k, v]) => el('tr', {}, el('td', {}, k), el('td', {}, v)))));
  if (snap.series?.length) {
    const det = el('details', {}, el('summary', {}, `Table view (${snap.series.length} points)`));
    det.append(el('table', { class: 'data-table' },
      el('tr', {}, el('th', {}, 'time'), el('th', {}, inst.unit || 'value')),
      snap.series.slice(-200).reverse().map(([t, v]) => el('tr', {}, el('td', {}, new Date(t).toLocaleString()), el('td', {}, fmtNum(v, inst.decimals)))),
    ));
    dlg.append(det);
  }
}

// ---------- render ----------
function render(state) {
  STATE = state;
  const main = $('#main'), nav = $('#nav');
  main.innerHTML = ''; nav.innerHTML = '';
  $('#generated').textContent = `updated ${ago(state.generatedAt)}`;
  const ov = $('#overall'); ov.className = `pill ${state.status}`; $('b', ov).textContent = `${LEVEL_ICON[state.status] || ''} ${LEVEL_LABEL[state.status] || state.status}`;
  for (const sec of state.sections) {
    const id = 'sec-' + sec.name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    nav.append(el('a', { href: '#' + id }, el('span', { class: `dot ${sec.status}` }), sec.name));
    const grid = el('div', { class: 'grid' });
    for (const inst of sec.instruments) {
      const snap = state.instruments[inst.id] || { status: 'unknown', empty: true };
      grid.append(inst.kind === 'events' ? eventsCard(inst, snap) : metricCard(inst, snap));
    }
    main.append(el('section', { class: 'sec', id }, el('h2', {}, el('span', { class: `dot ${sec.status}` }), sec.name), grid));
  }
}

async function load() {
  try {
    const state = await fetch('/api/state').then((r) => r.json());
    render(state);
  } catch (e) {
    $('#loading').textContent = 'Failed to load /api/state: ' + e.message;
  }
}
load();
setInterval(load, 60_000);
