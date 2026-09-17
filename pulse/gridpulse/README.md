# GridPulse

The electric grid, live: demand, prices, reserves, generation mix, carbon, and grid emergencies.

A live "vital signs" dashboard in the style of [pulse.bighawk.uk](https://pulse.bighawk.uk/):
many independent public feeds → one page → every instrument shows its **source**
and **data age**, thresholds flag what matters, and an events wall tracks what
just happened. Stale beats fake.

Built on a shared framework (Cloudflare Worker + KV + zero-dependency frontend)
that also powers the sibling dashboards:
gridpulse · skypulse · netpulse · healthpulse · econpulse · computepulse.

## Sections

- **Vitals** — the headline reads: ERCOT system demand at 5-minute resolution, the US
  nuclear fleet's average output behind it, and (with a free key) total demand
  across the contiguous 48 states.
- **Texas / ERCOT** — what is filling the gap between demand and capacity:
  hourly wind + solar output, and whether the battery fleet is charging off the
  grid or holding it up.
- **Frequency & Reserves** — the two numbers control rooms actually watch:
  ERCOT's physical responsive capability against its published emergency
  triggers, and GB system frequency against NESO's 50 Hz bands.
- **Prices** — scarcity shows up here before it shows up anywhere else: the
  ERCOT real-time hub price against the $5,000/MWh offer cap, and the GB
  half-hourly wholesale price for contrast.
- **Generation Mix** — what the electrons are being made from: the renewable
  share in Texas and the carbon-free share in New York.
- **Carbon** — what that mix costs the atmosphere: GB grid carbon intensity with
  the official index bands, and California's CO₂ output in tonnes per hour.
- **Events** — the weather that breaks grids. Live NWS warnings for extreme
  heat, extreme cold, high wind and ice.

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

Cron fires every 30 minutes; each instrument declares its own cadence, and any
cadence shorter than the cron interval effectively samples at the cron rate.

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
