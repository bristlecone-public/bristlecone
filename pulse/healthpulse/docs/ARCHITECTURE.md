# Architecture

This dashboard is one instance of a shared "vital signs" framework (the same
skeleton powers the sibling projects: gridpulse, skypulse, netpulse, healthpulse,
econpulse, computepulse). The framework is ~400 lines and lives in
`src/framework/`; everything domain-specific lives in `src/instruments/`.

```
┌──────────────┐  cron 2x/day  ┌──────────────────┐   KV    ┌───────────────┐
│ Cloudflare   │ ───────────▶ │ collect()        │ ──────▶ │ state         │
│ Worker       │              │  for each due    │         │ (single doc:  │
│              │              │  instrument:     │         │  snaps+runlog)│
│  fetch()     │ ◀── /api/* ──│  fetch → merge   │ ◀────── │               │
│  serves      │              │  → status        │         └───────────────┘
│  public/     │              └──────────────────┘
└──────────────┘                      ▲
        ▲                             │ ctx.http (timeout, UA, csv/rss helpers)
        │                             ▼
   public/app.js              upstream feeds (NOAA, EIA, CDC, …)
```

## Pieces

| Path | Role |
|---|---|
| `src/framework/registry.js` | `defineInstrument()` — the contract every feed implements |
| `src/framework/collect.js` | cadence gating, concurrency, merge, "stale beats fake", state build |
| `src/framework/status.js` | thresholds → good / warning / serious / critical |
| `src/framework/http.js` | fetch with timeout + UA; CSV, RSS/Atom, number parsing |
| `src/instruments/*.js` | one file per upstream feed; exports `defineInstrument()`s |
| `src/instruments/index.js` | ordered registry (page order) |
| `src/site.js` | name/tagline/domain/UA |
| `src/index.js` | Worker: `scheduled` → collect, `fetch` → API + assets |
| `public/` | zero-dependency dashboard (cards, sparklines, detail dialog) |
| `scripts/collect-local.mjs` | run collectors in Node with a JSON-file KV shim; `--serve` for local UI |
| `scripts/check-registry.mjs` | static registry validation + inventory table |

## Data model

Everything lives in ONE KV document, `state` — one read per page view, at most one
write per collector run, **no write when nothing was due** (KV free tier is 1,000
writes/day per account; per-instrument keys blew through it). Legacy `snap:<id>`
keys are read once as a migration source, never written.

Per-instrument snapshot inside `state.instruments` (metric):
```json
{ "id": "…", "kind": "metric", "value": 421.3, "at": "<observation ISO>",
  "fetchedAt": "<ISO>", "delta": 0.2, "series": [[epochMs, value], …],
  "range": { "min": …, "max": …, "n": … }, "status": "warning",
  "meta": {}, "errorCount": 0, "lastError": null, "lastErrorAt": null,
  "skipped": null, "firstSeenAt": "<ISO>" }
```
Events snapshots: same bookkeeping, plus `items: [{id, at, title, severity, url, meta}]`
deduped by `id`, capped at `history`. `order: 'desc'` (default) = newest first, a log
of what happened; `order: 'asc'` = soonest first for forward-looking walls (launches,
close approaches) — past items are dropped and the UI shows "in 3d".

Full doc: `{ site, generatedAt, status, sections:[{name,status,instruments:[def…]}], instruments:{id:snap}, runlog }`
— rewritten only when a run changed something, so the page is one KV read and quiet ticks cost zero writes.

## Design rules

1. **Stale beats fake.** A failed fetch never blanks a card. The last good value
   stays, marked with the failure time. Age is always visible.
2. **Every instrument names its source.** `source.name` + `source.url` are
   required and rendered on the card and in the detail dialog.
3. **Cadence lives on the instrument**, not in cron. Cron fires twice daily;
   the collector runs only what's due (≥95% of cadence elapsed). Cadences under
   15m therefore sample at cron rate — that's the KV-quota trade-off.
4. **Thresholds are declarative** where possible so the UI can draw them.
5. **Keys are optional.** `needsKey` instruments are skipped (and say so) until
   the secret exists. The dashboard must be useful with zero keys.
6. **No build step.** Plain ES modules in the Worker and the browser.

## Cron budget (Workers Free = 5 cron triggers per account)

Six dashboards + anything else you run won't fit. Fan-out instead: leave `triggers.crons`
empty on the overflow workers and add Service Bindings on one cron-bearing worker:
```jsonc
"services": [
  { "binding": "PEER_ECONPULSE",    "service": "econpulse" },
  { "binding": "PEER_COMPUTEPULSE", "service": "computepulse" }
]
```
Its `scheduled()` POSTs `/api/collect` to every `PEER_*` binding with the shared
`ADMIN_TOKEN` (so all workers must have the same token); peers still apply their own
per-instrument cadence. (Plain `fetch()` to a sibling's workers.dev URL is blocked by
Cloudflare — error 1042 — hence bindings.) Or upgrade to Workers Paid for 1,000 crons.

## Ops

```bash
npm i
npx wrangler kv namespace create SNAPSHOTS          # paste id into wrangler.jsonc
npx wrangler secret put ADMIN_TOKEN                  # for POST /api/collect
npx wrangler deploy
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "https://<domain>/api/collect?force=1"
```
Local: `npm run collect -- --force` then `npm run collect -- --serve` → http://localhost:8787.
