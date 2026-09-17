# Instruments

17 instruments across 8 sections. Every one is keyless — the dashboard is fully
useful with an empty `.dev.vars`. Verified ✅ means the instrument was live-fetched
and returned `ok` with a non-null value on 2026-08-17.

| id | section | source | endpoint | cadence | key | threshold basis | ✓ |
|---|---|---|---|---|---|---|---|
| `yield-curve-10y2y` | Vitals | [FRED · T10Y2Y](https://fred.stlouisfed.org/series/T10Y2Y) | `fredgraph.csv?id=T10Y2Y` | 6h | — | inversion (≤0) — every US recession since 1970 was preceded by one | ✅ |
| `weekly-economic-index` | Vitals | [FRED · WEI](https://fred.stlouisfed.org/series/WEI) (Dallas Fed) | `fredgraph.csv?id=WEI` | 6h | — | index is GDP-growth-scaled: ≤0 contraction, ≤−2 severe | ✅ |
| `gdpnow` | Vitals | [FRED · GDPNOW](https://fred.stlouisfed.org/series/GDPNOW) (Atlanta Fed) | `fredgraph.csv?id=GDPNOW` | 6h | — | same GDP-growth scale: ≤0 contraction, ≤−2 severe | ✅ |
| `fed-funds-effective` | Rates | [NY Fed reference rates](https://www.newyorkfed.org/markets/reference-rates/effr) | `/api/rates/unsecured/effr/last/750.json` | 6h | — | none (policy rate has no "bad" level) | ✅ |
| `treasury-10y` | Rates | [FRED · DGS10](https://fred.stlouisfed.org/series/DGS10) | `fredgraph.csv?id=DGS10` | 6h | — | none (level is regime-dependent) | ✅ |
| `mortgage-30y` | Rates | [FRED · MORTGAGE30US](https://fred.stlouisfed.org/series/MORTGAGE30US) (Freddie Mac PMMS) | `fredgraph.csv?id=MORTGAGE30US` | 6h | — | 7% / 8% — widely used affordability breakpoints | ✅ |
| `cpi-yoy` | Prices | [FRED · CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) (BLS) | `fredgraph.csv?id=CPIAUCSL`, YoY computed | 6h | — | 3 / 4 / 6% against the Fed's 2% target | ✅ |
| `gas-regular` | Prices | [FRED · GASREGW](https://fred.stlouisfed.org/series/GASREGW) (EIA) | `fredgraph.csv?id=GASREGW` | 6h | — | $3.50 / $4 / $5 — conventional US pain thresholds | ✅ |
| `unemployment-rate` | Labor | [FRED · UNRATE](https://fred.stlouisfed.org/series/UNRATE) (BLS) | `fredgraph.csv?id=UNRATE` | 6h | — | 4.5 / 5.5 / 7% | ✅ |
| `initial-claims` | Labor | [FRED · ICSA](https://fred.stlouisfed.org/series/ICSA) (DOL) | `fredgraph.csv?id=ICSA` | 6h | — | 250k / 300k / 400k — standard recession-watch levels | ✅ |
| `sp500` | Markets | [Yahoo Finance ^GSPC](https://finance.yahoo.com/quote/%5EGSPC/) | `/v8/finance/chart/^GSPC?range=1y&interval=1d` | 15m | — | none (index level) | ✅ ⚠ fragile |
| `vix` | Markets | [FRED · VIXCLS](https://fred.stlouisfed.org/series/VIXCLS) (Cboe) | `fredgraph.csv?id=VIXCLS` | 6h | — | 20 / 30 / 40 — the conventional calm / stressed / panic bands | ✅ |
| `high-yield-spread` | Markets | [FRED · BAMLH0A0HYM2](https://fred.stlouisfed.org/series/BAMLH0A0HYM2) (ICE BofA) | `fredgraph.csv?id=BAMLH0A0HYM2` | 6h | — | 5 / 7 / 10pp — historical credit-stress bands | ✅ |
| `federal-debt` | Fiscal | [Treasury Fiscal Data](https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny) | `v2/accounting/od/debt_to_penny?sort=-record_date&page[size]=520` | 6h | — | none (no accepted level) | ✅ |
| `fomc-hold-odds` | Prediction markets | [Kalshi KXFEDDECISION](https://kalshi.com/markets/kxfeddecision) | `trade-api/v2/events?series_ticker=KXFEDDECISION&with_nested_markets=true` | 15m | — | none (a probability is not good or bad) | ✅ |
| `recession-odds` | Prediction markets | [Kalshi KXRECSSNBER](https://kalshi.com/markets/kxrecssnber) | `trade-api/v2/events?series_ticker=KXRECSSNBER&with_nested_markets=true` | 1h | — | none | ✅ |
| `data-releases` | Events | Fed Board · BEA · Census (RSS) | `press_monetary.xml` + `apps.bea.gov/rss/rss.xml` + `census.gov/economic-indicators/indicator.xml` | 1h | — | severity by release type, not by value | ✅ |

## Notes on the sources

**FRED keyless CSV.** `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>&cosd=<YYYY-MM-DD>`
returns `observation_date,<ID>` CSV with no key and no documented rate limit — verified
for all eleven series above. Two quirks the shared `fredSeries()` helper in
`src/instruments/fred.js` handles:

- **Multi-series requests return a ZIP.** `?id=A,B` responds `application/zip`, not CSV,
  so the helper always requests exactly one series per call.
- **Missing observations are an empty cell** (market holidays) or `.`. Naive parsing turns
  `''` into `0` — `Number('')` is `0`, and the framework's `num()` helper has the same
  behaviour — so the helper explicitly drops `''`, `.`, `NA` before converting.
- For **quarterly** series, `cosd` returns the whole quarter containing the date, which is
  why `gdpnow` uses a 5-year window to keep the ±33% 2020 quarters off the sparkline.

An **optional keyed path** is implemented: set `FRED_API_KEY` and every FRED instrument
silently switches to the official JSON API (`api.stlouisfed.org/fred/series/observations`)
instead. No instrument declares `needsKey`, so the key is a pure upgrade and never a
requirement. `meta.via` reports which path was used.

⚠ The keyed path is **not end-to-end verified** — no FRED key was available. The request
was confirmed well-formed against the live API (`series_id`, `file_type`,
`observation_start` all accepted; only the unregistered key was rejected), and the
response mapping follows the documented `{ observations: [{ date, value }] }` shape with
`.` as the missing marker, which the shared parser already handles. Worth one live run
after the first key is set.

**Cadence.** Everything FRED-backed polls at 6h. The underlying data is daily to monthly,
but 6h means a CPI, claims or GDPNow print appears the same morning it lands rather than
up to a day later, at a cost of four cheap CSV requests per series per day.

**Observation dates are honest, which makes monthly cards look old.** `cpi-yoy`,
`unemployment-rate` and `gdpnow` are timestamped to the reference period, not to the
release date, so they show ~45 days of "age" on the day they publish. That is the
contract in `registry.js` (`at` = observation time) and the right call — the alternative
is stamping monthly data with the fetch time, which is exactly the "fake" that "stale
beats fake" rules out.

**Yahoo Finance is the one fragile feed.** It is keyless and undocumented, rate-limits
with HTTP 429, and sometimes demands a consent cookie from datacentre IPs — a Cloudflare
Worker may get treated worse than this laptop did. If `sp500` starts failing in
production, swap it for FRED series `SP500` (keyless, ~1 day behind) using `fredSeries()`;
the code comment in `src/instruments/yahoo.js` says so too. Yahoo's terms restrict use to
personal, non-commercial purposes.

**Kalshi** prices are dollars per $1 contract, i.e. already probabilities. The instruments
take the bid/ask midpoint and fall back to the last trade, because a thin book leaves
`last_price` stale for hours. The FOMC outcomes are mutually exclusive and exhaustive, so
they are normalised to sum to 1 before the hold probability and expected-move are computed;
`meta.outcomes` carries the full per-outcome breakdown and `meta.expectedMoveBps` the
probability-weighted expected policy move.

**Events wall** uses the Fed's *monetary policy* feed rather than `press_all.xml`. The
all-releases feed is dominated by bank enforcement actions and merger approvals, which
would bury the macro signal. Feeds are fetched with `Promise.allSettled` so one dead feed
degrades the wall instead of blanking it; only a total failure throws. The Census guid is
a stable slug (`retail_sales`) reused every month, so dedupe ids are
`<source>|<guid>|<timestamp>`.

## Candidates / next

Verified as working during research but not wired, to stay near the instrument budget:

- **US Dollar index** — FRED [`DTWEXBGS`](https://fred.stlouisfed.org/series/DTWEXBGS)
  (broad trade-weighted, daily, keyless). Drop-in `fredSeries()` call.
- **WTI crude** — FRED [`DCOILWTICO`](https://fred.stlouisfed.org/series/DCOILWTICO)
  (daily, keyless). Drop-in.
- **SOFR as its own card** — `https://markets.newyorkfed.org/api/rates/secured/sofr/last/750.json`.
  Currently rides along in `fed-funds-effective`'s meta (`meta.sofr`, `meta.sofrMinusEffr`);
  the SOFR–EFFR gap is the standard repo-funding-stress tell and deserves promotion if the
  Rates section grows.
- **Treasury interest expense** — `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/interest_expense?sort=-record_date&page[size]=400`.
  Verified keyless JSON. Monthly, but rows are split by security type
  (`expense_type_desc`), so it needs a group-and-sum over `fytd_expense_amt` per
  `record_date` — real work, not a one-liner.
- **Polymarket** — `https://gamma-api.polymarket.com/events?tag_slug=fed&active=true&closed=false`
  works keylessly and `markets[].outcomePrices` is a JSON-encoded string array. A second
  venue on the FOMC question, plus `slug=how-many-fed-rate-cuts-in-<year>` for an
  expected-cuts-this-year figure. Left out because the slug embeds the year and would need
  annual maintenance.
- **EIA weekly gasoline** — `https://api.eia.gov/v2/petroleum/pri/gnd/data/?api_key=…&frequency=weekly&facets[product][]=EPMR&facets[duoarea][]=NUS`
  (`needsKey: 'EIA_API_KEY'`). Deliberately *not* used: FRED `GASREGW` is the same EIA
  series, keyless, so the key would buy nothing.
- **BLS API v2** — `https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000`, keyless
  at 25 requests/day. Not used: FRED carries the same series with no quota.
- **Kalshi economics markets** worth a look:
  `KXRATECUTS` (number of cuts), `KXU3` (monthly unemployment print),
  `KXJOBLESSCLAIMS` (weekly claims), `KXCPIYOY`/`KXECONSTATCPIYOY` (inflation prints).
  Enumerate with `trade-api/v2/series?category=Economics`.

## Dead ends

- **Stooq CSV** (`https://stooq.com/q/d/l/?s=^spx&i=d`) — returns HTTP 200 with an HTML
  proof-of-work JavaScript challenge instead of CSV, for `^spx`, `^vix` and `btcusd` alike.
  Unusable from a Worker. Yahoo and FRED cover the same ground.
- **FRED multi-series CSV** (`?id=A,B`) — returns a ZIP archive, not concatenated CSV.
  Not decodable without a zip library, and there are no dependencies here. One request per
  series instead.
- **BLS latest-numbers RSS** (`https://www.bls.gov/feed/bls_latest.rss`) — parses fine but
  contains exactly **one** item, a rolling "Major Economic Indicators Latest Numbers"
  summary with the actual figures buried in an HTML blob in `<description>`. It is not an
  event stream and cannot be deduped into a wall. `https://www.bls.gov/feed/news_release.rss`
  is a 404. BLS releases still reach the wall indirectly, since BEA and Census cover the
  same calendar.
- **Fed `press_all.xml`** — works, but see above: enforcement actions and merger orders
  swamp monetary policy. Used `press_monetary.xml` instead.
