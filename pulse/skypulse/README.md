# SkyPulse

Space weather and near-Earth space, live: the Sun, solar wind, geomagnetic storms, aurora, satellites, and asteroid close approaches.

A live "vital signs" dashboard in the style of [pulse.bighawk.uk](https://pulse.bighawk.uk/):
many independent public feeds → one page → every instrument shows its **source**
and **data age**, thresholds flag what matters, and an events wall tracks what
just happened. Stale beats fake.

Built on a shared framework (Cloudflare Worker + KV + zero-dependency frontend)
that also powers the sibling dashboards:
gridpulse · skypulse · netpulse · healthpulse · econpulse · computepulse.

## Sections

- **Vitals** — the four numbers that describe space weather right now: planetary Kp, GOES soft X-ray flux, solar wind speed at Earth, and the monthly sunspot number that sets the baseline.
- **Sun** — F10.7 cm radio flux (the standard proxy for solar EUV output and satellite drag) and a rolling 7-day list of every X-ray flare GOES has recorded.
- **Solar Wind** — IMF Bz, the north–south field component that decides whether the solar wind couples into Earth's magnetosphere.
- **Geomagnetic & Aurora** — the NOAA R/S/G storm scales as SWPC currently has them set, and the OVATION nowcast of how many gigawatts are landing in the northern auroral oval.
- **Radiation** — GOES ≥10 MeV proton flux (the NOAA S-scale, polar HF and flight-crew dose) and ≥2 MeV electron flux (satellite internal charging).
- **Orbit** — the ISS's mean altitude, derived from its latest published orbit: drag-driven decay punctuated by reboosts.
- **Near-Earth Objects** — how close the nearest known asteroid comes in the next 30 days, in lunar distances.
- **Events** — SWPC's own alerts, watches and warnings; upcoming asteroid close approaches; and NASA DONKI's coronal mass ejection analyses.

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

First-pass instrument set: 16 instruments across 8 sections, all live-verified.
15 are keyless; only `donki-cme` wants a (free) `NASA_API_KEY` and is skipped
without it. See `docs/INSTRUMENTS.md` for the inventory, the feeds queued up
next, and the dead ends.
