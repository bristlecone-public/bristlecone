# NetPulse

The internet's vital signs, live: traffic, outages, attacks, routing, protocol adoption, and the software ecosystem.

A live "vital signs" dashboard in the style of [pulse.bighawk.uk](https://pulse.bighawk.uk/):
many independent public feeds → one page → every instrument shows its **source**
and **data age**, thresholds flag what matters, and an events wall tracks what
just happened. Stale beats fake.

Built on a shared framework (Cloudflare Worker + KV + zero-dependency frontend)
that also powers the sibling dashboards:
gridpulse · skypulse · netpulse · healthpulse · econpulse · computepulse.

## Sections

- **Vitals** — the three-number answer to "is the internet OK right now": human
  pageviews across every Wikimedia project, how many of seven load-bearing
  providers are degraded, and Cloudflare's application-layer attack index.
- **Outages** — IODA's worldwide connectivity-loss alerts, as a six-hour count
  and as a wall of the country- and region-level drops behind it.
- **Routing** — size of the IPv4 and IPv6 BGP tables (the memory every
  default-free router carries) plus the day's hijacks and route leaks.
- **Adoption** — the slow protocol migrations: share of end users who can reach
  the world over IPv6, and share of requests already speaking HTTP/3.
- **Ecosystem** — the software supply chain, measured as whole-registry npm
  downloads per day.
- **Privacy & Tor** — daily Tor users and the volunteer relay count the whole
  anonymity guarantee rests on.
- **Incidents** — one wall of open and recently-resolved incidents declared by
  GitHub, Cloudflare, npm, Discord, OpenAI, Atlassian, Zoom and AWS.

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

Cron fires hourly; each instrument declares its own cadence.

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
