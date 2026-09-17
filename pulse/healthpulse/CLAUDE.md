# HealthPulse — agent notes

One of six sibling projects under `pulse/` in the bristlecone monorepo. Read
`docs/ARCHITECTURE.md` first, then
`docs/INSTRUMENTS.md` for the feed inventory.

Rules:
- Add a feed = one file in `src/instruments/`, export `defineInstrument()`s, register in `index.js`.
- Never touch `src/framework/` for a domain need — extend via instrument options or open an issue; all six keep `src/framework/` byte-identical. A genuine framework fix is edited once, then copied to the other five sibling directories under `pulse/` in the same commit; verify with `md5sum pulse/*/src/framework/<file>`.
- Every instrument: real `source.url`, honest `cadence` (respect upstream rate limits and update frequency), `describe` in plain English, thresholds only where the domain has an accepted scale.
- No keys required for the default experience; keyed feeds use `needsKey`.
- Verify locally: `npm run check` (registry) → `npm run collect -- --force --only <id>` (live fetch) → `npm run collect -- --serve` (UI).
- No build step, no frameworks, no TypeScript. Plain ESM.
