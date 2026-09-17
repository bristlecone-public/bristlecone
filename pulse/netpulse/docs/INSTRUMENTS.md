# Instruments

14 instruments across 7 sections. Every one was fetched live on 2026-08-17 and
returned `ok`. Three need a Cloudflare Radar token; the other eleven are keyless,
so the dashboard is fully useful with no secrets at all.

Legend: **verified** ✅ = live fetch returned a real value in this repo ·
⚠ = code path written but not live-verified.

| id | section | source | endpoint | cadence | key | thresholds | verified |
|---|---|---|---|---|---|---|---|
| `internet-pageviews` | Vitals | [Wikimedia Analytics](https://wikimedia.org/api/rest_v1/) | `/metrics/pageviews/aggregate/all-projects/all-access/user/daily/…` | 6h | — | none (no accepted scale) | ✅ |
| `providers-degraded` | Vitals | [7 provider status pages](https://www.githubstatus.com/api) | `<page>/api/v2/status.json` ×7 | 15m | — | count of non-`none` Statuspage indicators: 1→warning, 2→serious, 4→critical | ✅ |
| `radar-l7-attacks` | Vitals | [Cloudflare Radar](https://radar.cloudflare.com/security-and-attacks) | `/radar/attacks/layer7/timeseries?aggInterval=1h&dateRange=7d` | 1h | `CLOUDFLARE_API_TOKEN` | none (min-max index, not an absolute rate) | ✅ |
| `ioda-outage-alerts` | Outages | [IODA — Georgia Tech / CAIDA](https://ioda.inetintel.cc.gatech.edu/) | `/v2/outages/alerts?from=&until=&limit=1000` (6 h window) | 1h | — | none (volume is bursty; background ≈100-250/6 h) | ✅ |
| `ioda-alerts` (events) | Outages | [IODA](https://ioda.inetintel.cc.gatech.edu/dashboard) | same endpoint, 12 h window, country+region only | 30m | — | per-item: country→critical, region→serious | ✅ |
| `bgp-table-v4` | Routing | [APNIC / Geoff Huston](https://bgp.potaroo.net/index-bgp.html) | `https://bgp.potaroo.net/as2.0/bgp-active.txt` (tail via HTTP Range) | 1d | — | none | ✅ |
| `bgp-table-v6` | Routing | [APNIC / Geoff Huston](https://bgp.potaroo.net/index-bgp.html) | `https://bgp.potaroo.net/v6/as2.0/bgp-active.txt` (tail via HTTP Range) | 1d | — | none | ✅ |
| `radar-bgp-anomalies` | Routing | [Cloudflare Radar](https://radar.cloudflare.com/routing) | `/radar/bgp/hijacks/events` + `/radar/bgp/leaks/events` (24 h) | 1h | `CLOUDFLARE_API_TOKEN` | none | ✅ |
| `ipv6-capable` | Adoption | [APNIC Labs](https://stats.labs.apnic.net/ipv6/XA) | `https://data1.labs.apnic.net/v6stats/v6region/XA.json` | 1d | — | none | ✅ |
| `radar-http3-share` | Adoption | [Cloudflare Radar](https://radar.cloudflare.com/adoption-and-usage) | `/radar/http/summary/http_version?dateRange=1d` | 1h | `CLOUDFLARE_API_TOKEN` | none | ✅ |
| `npm-downloads` | Ecosystem | [npm registry](https://api.npmjs.org/downloads/point/last-day) | `https://api.npmjs.org/downloads/range/last-year` | 6h | — | none | ✅ |
| `tor-users` | Privacy & Tor | [Tor Metrics](https://metrics.torproject.org/userstats-relay-country.html) | `userstats-relay-country.csv?country=all&events=off&start=&end=` | 6h | — | none | ✅ |
| `tor-relays` | Privacy & Tor | [Tor Metrics](https://metrics.torproject.org/networksize.html) | `networksize.csv?start=&end=` | 6h | — | none | ✅ |
| `provider-incidents` (events) | Incidents | [7 status pages + AWS SHD](https://www.githubstatus.com/history) | `<page>/api/v2/incidents.json` ×7 + `https://status.aws.amazon.com/rss/all.rss` | 30m | — | per-item: Statuspage `impact` minor→warning, major→serious, critical→critical, resolved→good | ✅ |

## Notes per source

**Wikimedia pageviews** — bot-filtered (`agent=user`) daily totals across all
projects. Lands 24-48 h behind and occasionally skips a day; gaps are filtered
rather than drawn as a cliff. Needs a descriptive User-Agent, which the framework
supplies from `site.userAgent`. Licence CC0.

**Statuspage status APIs** — GitHub, Cloudflare, npm, Discord, OpenAI, Atlassian,
Zoom. Identical `/api/v2/status.json` and `/api/v2/incidents.json` shapes on all
seven (OpenAI runs incident.io, which emulates both routes). A single provider
failing is tolerated — the instrument only errors if *every* page is unreachable.
`incidents.json` returns full history, so the events instrument filters to the
last 14 days. AWS has no Statuspage; its RSS is merged into the same wall,
capped at the 12 most recent items because Direct Connect packet-loss notices are
very chatty.

**IODA** — alerts arrive in pairs (an onset alert with `level: critical` /
`condition: "< 0.25"`, then a matching recovery alert with `level: normal`);
only the non-normal half is ever counted or shown. AS-level alerts run to
hundreds a day, so the events wall keeps country and region entities only, while
the metric counts everything and breaks it down in `meta`. Licence is
CC BY-NC-SA 4.0 — **non-commercial use only**.

**bgp.potaroo.net** — the full history files are 3-5 MB of hourly
`"<epoch> <count>"` lines going back to 1988 (v4) and 2003 (v6). The instrument
requests `Range: bytes=-200000` (the server answers `206`, `accept-ranges: bytes`),
drops the first partial line, and downsamples to the last sample of each UTC day
— about 450 days from 200 kB. Attribution requested.

**APNIC Labs IPv6** — the `stats.labs.apnic.net` page is a Google-Charts wrapper,
but it links a bulk JSON file with the whole daily series back to 2013 (raw plus
10/30/60/90-day smoothing). That file is ~4 MB, so the instrument regex-scans the
text instead of `JSON.parse`-ing it, and keeps the last 400 days. Headline value is
the **raw** daily `capable_pc`; it is noisy day to day, and `preferred_pc` rides in
`meta`. The download can take 30 s+ — fine at a 1-day cadence.

**npm** — omitting the package name from the downloads API gives whole-registry
totals. The stats pipeline emits a literal `0` on days it misses a run (36 such
days in the trailing year); those are dropped. Weekday volume is roughly double
the weekend, so the shape matters more than any single point.

**Tor Metrics** — CSV with a `#` comment preamble, handled by `http.csv`.
`country=all` yields a blank `country` column for the world aggregate; the `frac`
column (share of directory authorities reporting) is surfaced in `meta` because a
low value means a shaky estimate. Data lags ~2-3 days. Licence CC0.

**Cloudflare Radar** — free, but every route needs a token. Create one at
<https://dash.cloudflare.com/profile/api-tokens> with **Account Analytics: Read**
and set `CLOUDFLARE_API_TOKEN`. Quirks found while wiring:
- `result_info` (pagination totals, incl. `total_count`) sits **next to** `result`,
  not inside it — needed to count BGP events beyond one page.
- `dateEnd` must be strictly in the past, so the BGP window ends 60 s short of now.
- `/attacks/layer7/timeseries` returns `normalization: MIN0_MAX`, i.e. an index
  where 1.0 is the busiest hour of the requested window — **not** a percentage of
  requests. The card is labelled as an index accordingly.
- `/http/summary/http_protocol` is HTTP-vs-HTTPS; the HTTP/1.1-vs-2-vs-3 split is
  `/http/summary/http_version`, which is what `radar-http3-share` uses.

## Candidates / next

Verified reachable but not wired, or plausible next additions:

- **Cloudflare Radar traffic anomalies** (keyed) —
  `https://api.cloudflare.com/client/v4/radar/traffic_anomalies?dateRange=7d` —
  a second outage events wall built from CDN traffic drops rather than active
  probing; complements IODA nicely.
- **Cloudflare Radar bot share** (keyed) — `/radar/http/summary/bot_class` —
  a *real* percentage of requests that are automated, unlike the L7 attack index.
- **Cloudflare Radar** (keyed) — `/radar/http/summary/ip_version` (IPv6 share of
  requests, a server-side counterpart to APNIC's client-side number),
  `/radar/netflows/timeseries` (traffic index), `/radar/quality/speed/summary`
  (median download speed), `/radar/bgp/routes/stats`.
- **IODA outage summary** — `https://api.ioda.inetintel.cc.gatech.edu/v2/outages/summary?from=&until=`
  — ranked list of the worst-hit entities. Verified 200, but 129 kB and ~5 s.
- **More status pages**, same zero-effort shape: Slack, Fastly, Twilio, Reddit,
  Shopify, DigitalOcean, Heroku (`https://<page>/api/v2/status.json`).
- **crates.io** — `https://crates.io/api/v1/summary` → `num_downloads`,
  `num_crates` (verified 200). Cumulative counters, so the daily delta is the
  interesting part.
- **RubyGems** — `https://rubygems.org/api/v1/downloads.json` → `{"total": …}`
  (verified 200). Same cumulative-counter caveat.
- **RIPE Atlas probe fleet** — `https://atlas.ripe.net/api/v2/probes/?status=1&page_size=1`
  → `count` of connected probes (verified 200, 14 650 at time of writing).
- **mempool.space** — `https://mempool.space/api/v1/fees/recommended` →
  `fastestFee` sat/vB (verified 200). Congestion of an internet-scale P2P network,
  if the domain is stretched that far.
- **Tor Metrics extras** — `userstats-bridge-country.csv` (bridge users, the
  censorship-circumvention signal) and per-country user series for a "who is being
  blocked today" wall.

## Dead ends

Checked and rejected — do not re-litigate without new evidence:

- **Google IPv6 statistics JSON** — `https://www.google.com/intl/en/ipv6/statistics/data/data.json`
  returns 404; only the HTML page survives. Replaced by APNIC Labs.
- **APNIC "JSON" query params** — `https://stats.labs.apnic.net/ipv6/XA?f=j` and
  `…&x=1` both return the 550 kB HTML page regardless. The real machine-readable
  file is `https://data1.labs.apnic.net/v6stats/v6region/XA.json` (linked from the
  page itself); `…/v6region/001.json` (UN world code) is a 404 — the world region
  code is `XA`.
- **Let's Encrypt certificates issued per day** — `https://letsencrypt.org/stats/`
  is a static Hugo page with image charts and no JSON/CSV behind it
  (`/stats/issuance.json` → 404). The page's own footnote points at Mozilla
  telemetry docs, not a queryable feed. Skipped.
- **HTTP Archive legacy reports** — `https://cdn.httparchive.org/reports/pctHttps.json`
  and `…/bytesTotal.json` both 404; that reports API is retired. The current data
  lives in BigQuery, which needs a Google Cloud account and billing.
- **RIPEstat `routing-table-size`** — not a real data call
  (`data_call_status: unsupported`). Replaced by bgp.potaroo.net.
- **Internet Society Pulse API** — `https://pulse.internetsociety.org/api/…`
  returns a Cloudflare interstitial (403) to non-browser clients.
- **NIST RPKI Monitor** — `https://rpki-monitor.antd.nist.gov/api/stats/v4` 404s;
  the site is a JS app with no documented JSON API.
- **Wikimedia unique devices** — `…/unique-devices/all-projects/all-sites/daily/…`
  404s ("project not loaded"); only per-project domains are served. Pageviews used
  instead.
- **Statuspage `/api/v2/incidents/unresolved.json`** — works on genuinely
  Statuspage-hosted pages but returns the HTML 404 shell on OpenAI's incident.io
  page, and would leave the events wall empty on first run anyway. Used
  `incidents.json` with a 14-day filter instead.
