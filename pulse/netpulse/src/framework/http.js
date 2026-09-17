// Small fetch helpers with timeout, UA, and friendly errors.
// Instruments receive these via ctx.http so they never touch fetch() directly.

const DEFAULT_TIMEOUT = 20_000;

// Redact secret-bearing query params so a key placed in a URL never reaches an
// error message (which is persisted to KV as lastError and served on the public
// /api/health, /api/state and instrument endpoints and rendered on the card).
export function redactUrl(u) {
  try {
    const url = new URL(String(u));
    for (const k of [...url.searchParams.keys()]) {
      if (/key|token|secret|password|sig|auth|pass/i.test(k)) url.searchParams.set(k, 'REDACTED');
    }
    return url.toString();
  } catch {
    return String(u).replace(/([?&](?:[^=&]*(?:key|token|secret|password|sig|auth|pass)[^=&]*)=)[^&#]*/gi, '$1REDACTED');
  }
}

export function makeHttp({ userAgent, timeout = DEFAULT_TIMEOUT } = {}) {
  async function raw(url, opts = {}) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), opts.timeout ?? timeout);
    try {
      const res = await fetch(url, {
        ...opts,
        signal: ctrl.signal,
        headers: { 'user-agent': userAgent, accept: '*/*', ...(opts.headers || {}) },
      });
      if (!res.ok) {
        const body = (await res.text().catch(() => '')).slice(0, 300);
        throw new Error(`HTTP ${res.status} ${res.statusText} for ${redactUrl(url)} :: ${body}`);
      }
      return res;
    } finally {
      clearTimeout(t);
    }
  }
  return {
    raw,
    async json(url, opts) { return (await raw(url, opts)).json(); },
    async text(url, opts) { return (await raw(url, opts)).text(); },
    // Tiny CSV parser: returns array of objects keyed by header. Handles quotes.
    async csv(url, opts) { return parseCsv(await (await raw(url, opts)).text(), opts?.csv); },
    // Minimal RSS/Atom → [{title, link, at, summary}]
    async feed(url, opts) { return parseFeed(await (await raw(url, opts)).text()); },
  };
}

// RFC-4180-ish: quoted fields may contain delimiters, doubled quotes, and newlines.
export function parseCsv(text, { comment = '#', delimiter = ',', headers } = {}) {
  const rows = [];
  let row = [], cur = '', q = false;
  const s = text.replace(/^﻿/, '');
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) {
      if (c === '"') { if (s[i + 1] === '"') { cur += '"'; i++; } else q = false; }
      else cur += c;
    } else if (c === '"') q = true;
    else if (c === delimiter) { row.push(cur); cur = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && s[i + 1] === '\n') i++;
      row.push(cur); rows.push(row); row = []; cur = '';
    } else cur += c;
  }
  if (cur !== '' || row.length) { row.push(cur); rows.push(row); }
  const kept = rows
    .map((r) => r.map((v) => v.trim()))
    .filter((r) => r.some((v) => v !== '') && !(comment && r[0].startsWith(comment)));
  if (!kept.length) return [];
  const head = headers || kept.shift();
  return kept.map((cells) => {
    const o = {};
    head.forEach((h, i) => { o[h] = cells[i]; });
    return o;
  });
}

export function parseFeed(xml) {
  const items = [];
  const re = /<(item|entry)\b[\s\S]*?<\/\1>/g;
  let m;
  while ((m = re.exec(xml))) {
    const block = m[0];
    const tag = (n) => {
      const r = new RegExp(`<${n}\\b[^>]*>([\\s\\S]*?)<\\/${n}>`, 'i').exec(block);
      return r ? decode(r[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1').trim()) : '';
    };
    const linkAttr = /<link\b[^>]*href="([^"]+)"/i.exec(block);
    items.push({
      title: tag('title'),
      link: tag('link') || (linkAttr ? linkAttr[1] : ''),
      at: tag('pubDate') || tag('published') || tag('updated') || tag('dc:date'),
      summary: tag('description') || tag('summary') || tag('content'),
      id: tag('guid') || tag('id'),
    });
  }
  return items;
}

function decode(s) {
  return s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
}

// Lenient number parse. Returns null (never 0) for blanks and the usual
// missing-value tokens ('', '.', 'NA', 'N/A', 'null', '-', 'M', '-999').
export const num = (v) => {
  if (v == null) return null;
  const s = String(v).replace(/[,$%\s]/g, '');
  if (s === '' || /^(\.|na|n\/a|null|none|-|m|-?999(\.9+)?|-9999)$/i.test(s)) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};
