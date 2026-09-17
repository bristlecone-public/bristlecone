# ComputePulse

AI and compute, live: model releases, research volume, benchmarks, GPU prices, token throughput, and the compute buildout.

A live "vital signs" dashboard in the style of [pulse.bighawk.uk](https://pulse.bighawk.uk/):
many independent public feeds → one page → every instrument shows its **source**
and **data age**, thresholds flag what matters, and an events wall tracks what
just happened. Stale beats fake.

Built on a shared framework (Cloudflare Worker + KV + zero-dependency frontend)
that also powers the sibling dashboards:
gridpulse · skypulse · netpulse · healthpulse · econpulse · computepulse.

## Sections

- **Vitals** — new model repos published on Hugging Face in the last 24 hours, and how many of the big three providers are currently self-reporting degradation.
- **Models** — how many distinct LLMs you can call through a single aggregator, plus a wall of the newest releases from the labs that set the frontier.
- **Research** — the daily rate of new cs.AI / cs.LG / cs.CL preprints, and the papers the ML community is actually upvoting.
- **Frontier & benchmarks** — cumulative models trained above 10²⁵ FLOP, the largest confirmed AI cluster in H100-equivalents, and the top capability-index score (needs a key).
- **Usage & prices** — the cheapest rentable H100 on the open spot market and the median price of a million input tokens on a long-context model.
- **Ecosystem** — combined weekly npm installs of the five SDKs most apps use to call a model.
- **Incidents** — every incident OpenAI, Anthropic and Google Cloud have opened on their own status pages.
- **Announcements** — model launches and research posts straight from the labs' own feeds.

See [docs/INSTRUMENTS.md](docs/INSTRUMENTS.md) for the full feed inventory
(endpoint, cadence, key needed, threshold basis) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it fits together.

## Quick start

```bash
npm i
cp .dev.vars.example .dev.vars          # optional keys
npm run check                            # validate registry, print inventory
npm run collect -- --force               # hit every feed once, write ./data/kv.json
npm run collect -- --serve               # dashboard at http://localhost:8787
```

## Deploy (Cloudflare)

```bash
npx wrangler kv namespace create SNAPSHOTS   # paste id + preview_id into wrangler.jsonc
npx wrangler secret put ADMIN_TOKEN
# any keyed feeds: npx wrangler secret put <KEY_NAME>
npx wrangler deploy
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "https://<your-domain>/api/collect?force=1"
```

This worker ships with an **empty cron** (Workers Free cron limit) and is
collected by gridpulse's PEERS fan-out, which fires **4×/day (0, 6, 12, 18
UTC)**. Each instrument still declares its own `cadence`, but the effective
refresh floor is ~6h; instruments whose observation time lags (arXiv, Epoch,
npm) carry a matching `staleAfter` so a healthy card is not flagged stale. On a
Paid plan, restore `"*/15 * * * *"` in `wrangler.jsonc` for true per-cadence
gating.

## API

| Route | Purpose |
|---|---|
| `GET /api/state` | everything the page needs, one document |
| `GET /api/instrument/:id` | one instrument with full series |
| `GET /api/health` | per-instrument age, errors, last runs |
| `GET /api/registry` | instrument definitions only |
| `POST /api/collect?force=1&only=a,b` | manual run (needs `ADMIN_TOKEN`) |

## Adding an instrument

One file in `src/instruments/`, one `defineInstrument({...})`, one line in
`src/instruments/index.js`. See `src/instruments/_example.js` for every shape.

## Status

Framework scaffold + first-pass instruments. Feeds marked ⚠ in
`docs/INSTRUMENTS.md` were not live-verified yet.
