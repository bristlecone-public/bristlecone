# HealthPulse

Public health vital signs, live: wastewater surveillance, respiratory illness, outbreaks, and health alerts.

A live "vital signs" dashboard in the style of [pulse.bighawk.uk](https://pulse.bighawk.uk/):
many independent public feeds → one page → every instrument shows its **source**
and **data age**, thresholds flag what matters, and an events wall tracks what
just happened. Stale beats fake.

Built on a shared framework (Cloudflare Worker + KV + zero-dependency frontend)
that also powers the sibling dashboards:
gridpulse · skypulse · netpulse · healthpulse · econpulse · computepulse.

## Sections

- **Vitals** — the headline read on how much respiratory illness is out there
  right now: ED visits for acute respiratory illness, national %ILI, and
  SARS-CoV-2 in wastewater.
- **Wastewater** — influenza A and RSV viral activity levels across ~1,000 US
  sewersheds. Wastewater does not depend on anyone seeking care or getting
  tested, so it usually moves first.
- **Emergency Dept** — the share of US emergency department visits diagnosed as
  COVID-19 or influenza: illness that actually reached a hospital door.
- **Hospitalizations** — CDC RESP-NET weekly admission rates per 100,000 for
  COVID-19 and influenza, the severe end of the curve.
- **Outbreaks** — every formal WHO Disease Outbreak News notification, the
  closest thing to a global early-warning wall.
- **Recalls & Shortages** — the supply side of public health: Class I food
  recalls (the ones that can kill you) and the size of the FDA drug shortage
  list.
- **Environment** — acute environmental health hazards: active NWS heat and cold
  alerts nationwide, plus air quality (needs a free key).

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

Cron fires twice daily; each instrument declares its own cadence.

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
