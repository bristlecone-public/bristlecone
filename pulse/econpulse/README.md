# EconPulse

The economy's vital signs, live: rates, prices, labor, activity nowcasts, markets, and prediction markets.

A live "vital signs" dashboard in the style of [pulse.bighawk.uk](https://pulse.bighawk.uk/):
many independent public feeds → one page → every instrument shows its **source**
and **data age**, thresholds flag what matters, and an events wall tracks what
just happened. Stale beats fake.

Built on a shared framework (Cloudflare Worker + KV + zero-dependency frontend)
that also powers the sibling dashboards:
gridpulse · skypulse · netpulse · healthpulse · econpulse · computepulse.

## Sections

- **Vitals** — the three numbers to read first: the 10y–2y Treasury spread, the Dallas Fed's Weekly Economic Index, and the Atlanta Fed's GDPNow nowcast.
- **Rates** — the price of money from overnight out to thirty years: effective fed funds (with the target range and SOFR alongside), the 10-year Treasury, and the 30-year fixed mortgage.
- **Prices** — CPI inflation year-over-year, and the national average pump price for regular gasoline.
- **Labor** — the slowest and the fastest labour signals: the unemployment rate and weekly initial jobless claims.
- **Markets** — risk appetite and credit stress: the S&P 500 (the fastest-updating feed here), the VIX, and the high-yield credit spread.
- **Fiscal** — total federal debt outstanding, counted to the penny and republished every business day.
- **Prediction markets** — what real money expects: the traded odds the Fed holds at the next FOMC meeting, and the odds a US recession starts this year.
- **Events** — every official US macro release and Fed policy announcement as it publishes, merged from the Federal Reserve Board, BEA and Census Bureau.

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

Collected on gridpulse's ~6-hourly peer fan-out (this worker has no cron); each instrument declares its own cadence.

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
