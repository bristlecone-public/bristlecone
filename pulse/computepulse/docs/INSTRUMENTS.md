# Instruments

14 instruments across 8 sections. 13 are keyless and were live-verified on
2026-08-17 (`node scripts/collect-local.mjs --force` → all `ok`). One needs a
free API key and is marked ⚠.

## A note on fragility

AI/compute has almost no institutional telemetry. There is no NOAA, no EIA, no
ECDC for this domain. Every feed below is either a company's own API (which can
change or start charging without notice), a research non-profit's CSV, or a
marketplace endpoint that exists to sell you something. Concretely:

- **Vast.ai** is a commercial marketplace with an undocumented, aggressively
  rate-limited console API (~1 request/minute/IP observed). It is the most
  likely instrument to break. There is no keyless institutional GPU price index.
- **Artificial Analysis** already ships a `deprecation` link header on the v2
  endpoint we call. Expect a v3 migration.
- **Hugging Face** publishes no total-count header, so `hf-new-models-24h`
  reconstructs the number by cursor-paginating the creation-sorted list. If Hub
  traffic grows past ~12,000 new models/day the count becomes a floor and
  `meta.truncated` flips true.
- **arXiv's** `submittedDate` search index runs 2–3 days behind real time, so a
  "papers in the last 24 h" metric returns 0 forever. We count a complete 7-day
  window ending 3 days ago instead, and report it as a daily rate. The card's
  data age will always read ~3 days. That is correct, not a bug.
- **Statuspage/BetterStack** endpoints are the only genuinely stable, purpose-
  built machine feeds in the whole set.

Nothing here is scraped from HTML.

## Cadence vs. the real runner

This worker's cron is **empty**; it is collected by gridpulse's PEERS fan-out at
**0, 6, 12, 18 UTC (every 6h)**. The `cadence` column below is what each
instrument *declares*, but nothing refreshes faster than the 6-hourly fan-out —
so a `15m`/`1h` cadence is effectively `6h`. Instruments now set `staleAfter`
accordingly so a healthy card never reads "stale":

- Sub-6h feeds (`hf-new-models-24h`, `ai-providers-degraded`, `hf-lab-releases`,
  `gpu-h100-spot`, `ai-incidents`, `lab-announcements`) → `staleAfter: 12h`
  (tolerates one missed fan-out).
- Lagged/observation-time feeds → `arxiv-ai-papers` `5d` (3-day index lag),
  `npm-ai-sdk-downloads` `7d` (API trails a few days), `epoch-frontier-models`
  `120d` and `epoch-largest-cluster` `720d` (cumulative / high-water-mark values
  whose `at` is a real event date that legitimately does not advance for long
  stretches; genuine breakage still surfaces as `lastError`).

## Inventory

| id | section | source | endpoint | cadence | key | thresholds | verified |
|---|---|---|---|---|---|---|---|
| `hf-new-models-24h` | Vitals | [Hugging Face Hub API](https://huggingface.co/docs/hub/api) | `/api/models?sort=createdAt&direction=-1&limit=1000` (cursor-paginated) | 1h | – | none | ✅ |
| `ai-providers-degraded` | Vitals | [OpenAI](https://status.openai.com/) / [Anthropic](https://status.anthropic.com/) / [Hugging Face](https://status.huggingface.co/) status pages | `/api/v2/status.json` ×2 + `index.json` | 15m | – | count of 3 (1 → warning, 2 → serious); not a domain scale, just "how many are unhappy" | ✅ |
| `openrouter-models` | Models | [OpenRouter](https://openrouter.ai/models) | `/api/v1/models` | 6h | – | none | ✅ |
| `hf-lab-releases` (events) | Models | [Hugging Face Hub API](https://huggingface.co/models?sort=created) | `/api/models?author=<org>&sort=createdAt` × 13 orgs | 1h | – | n/a | ✅ |
| `arxiv-ai-papers` | Research | [arXiv API](https://info.arxiv.org/help/api/index.html) | `/api/query?search_query=(cat:cs.AI OR cs.LG OR cs.CL) AND submittedDate:[…]` | 6h | – | none | ✅ |
| `hf-daily-papers` (events) | Research | [Hugging Face Daily Papers](https://huggingface.co/papers) | `/api/daily_papers?limit=30` | 6h | – | n/a | ✅ |
| `epoch-frontier-models` | Frontier & benchmarks | [Epoch AI — Notable AI Models](https://epoch.ai/data/notable-ai-models) | `https://epoch.ai/data/notable_ai_models.csv` | 1d | – | none (the 10²⁵ FLOP line is the *definition*, not a threshold) | ✅ |
| `epoch-largest-cluster` | Frontier & benchmarks | [Epoch AI — AI Supercomputers](https://epoch.ai/data/ai-supercomputers) | `https://epoch.ai/data/gpu_clusters.csv` | 1d | – | none | ✅ |
| `aa-intelligence-index` | Frontier & benchmarks | [Artificial Analysis](https://artificialanalysis.ai/) | `/api/v2/data/llms/models` (`x-api-key`) | 6h | `ARTIFICIAL_ANALYSIS_API_KEY` | none | ⚠ code path only — 401 without a key confirms the endpoint is live and keyed; response field names are from the v2 docs |
| `gpu-h100-spot` | Usage & prices | [Vast.ai marketplace](https://cloud.vast.ai/create/) | `https://console.vast.ai/api/v0/bundles/?q=<json>` | 1h | – | none | ✅ |
| `openrouter-price-longctx` | Usage & prices | [OpenRouter](https://openrouter.ai/models) | `/api/v1/models` | 6h | – | none | ✅ |
| `npm-ai-sdk-downloads` | Ecosystem | [npm registry download API](https://github.com/npm/registry/blob/master/docs/download-counts.md) | `/downloads/range/last-month/<pkg>` × 5 | 1d | – | none | ✅ |
| `ai-incidents` (events) | Incidents | OpenAI / Anthropic / [Google Cloud](https://status.cloud.google.com/) status pages | `/api/v2/incidents.json` ×2 + `incidents.json` | 15m | – | Statuspage `impact` → severity (critical/major/minor); Google `severity` (high/medium/low) | ✅ |
| `lab-announcements` (events) | Announcements | OpenAI / DeepMind / Google / Hugging Face / Mistral blogs | 5 RSS feeds | 1h | – | n/a | ✅ |

### Series that arrive populated on the first fetch

- `epoch-frontier-models` — cumulative count by publication date, 21 points back to GPT-4 (Mar 2023).
- `epoch-largest-cluster` — record-setting clusters only, 16 points from 4 H100-equivalents (2010) to 275,796 (xAI Colossus Memphis Phase 3, Jul 2025).
- `npm-ai-sdk-downloads` — 24 points of 7-day rolling totals from the last month; the instrument merges `ctx.prev.series` forward so history accumulates past the API's 30-day window.

Everything else accumulates one point per fetch.

## Candidates / next

Verified to return machine-readable data, not wired up yet:

- **PyPI download stats** — `https://pypistats.org/api/packages/openai/recent` and
  `.../overall` (six months of daily numbers). The Python-side twin of the npm
  instrument; would make a second Ecosystem card.
- **GitHub stars on local-inference runtimes** —
  `https://api.github.com/repos/ollama/ollama`,
  `https://api.github.com/repos/ggml-org/llama.cpp`. Keyless limit is 60 req/hr,
  so 6h cadence.
- **Hugging Face trending models** —
  `https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=20`
  or `https://huggingface.co/api/trending?type=model`. A second events wall,
  deliberately left out to avoid three HF walls on one page.
- **Epoch AI GPU-cluster power draw** — the same `gpu_clusters.csv` carries
  `Power Capacity (MW)`; "total confirmed AI datacentre power" is a strong
  buildout metric.
- **Epoch AI training-cost column** — `notable_ai_models.csv` has
  `Training compute cost (2023 USD)`, enough for a "cost of the frontier" card.
- **Lambda Labs GPU pricing** —
  `https://cloud.lambdalabs.com/api/v1/instance-types` (401 without a key;
  `LAMBDA_API_KEY`). A keyed cross-check on Vast.ai's spot number.
- **NVIDIA blog RSS** — `https://blogs.nvidia.com/feed/` resolves (262 KB) but is
  mostly marketing; would need filtering before it earns a slot.
- **Meta Newsroom tech feed** —
  `https://about.fb.com/news/category/technology-and-innovation/feed/` resolves
  and covers Llama launches, but is not an AI-only feed.
- **OpenRouter token throughput** — their `/api/v1/models` payload carries no
  usage volume; the public rankings page is HTML-only. If they ever expose the
  rankings as JSON it would be the single best demand metric on the page.

## Dead ends

- **LMArena leaderboard.** The Space
  `lmarena-ai/chatbot-arena-leaderboard` redirects to
  `lmarena-ai/arena-leaderboard`, which is a `static` Space last modified
  2026-02-21. Its newest data files are `elo_results_20250829.pkl` and
  `leaderboard_table_20250804.csv` — over a year stale, and the Elo results are
  pickled Python, not parseable in a Worker. There is no keyless JSON/CSV Elo
  feed. Left out entirely rather than shipped stale.
- **Anthropic announcements RSS.** `https://www.anthropic.com/rss.xml`,
  `/news/rss.xml`, `/news/rss`, `/feed.xml` and `/engineering/rss.xml` all
  return 404 (Next.js error page). Anthropic publishes no feed; they appear in
  the incidents wall only.
- **Meta AI blog RSS.** `https://ai.meta.com/blog/rss/` and `/blog/rss.xml`
  both return a Facebook HTML error shell.
- **Hugging Face incidents.** `https://status.huggingface.co/api/v2/incidents.json`
  returns the HTML status page — HF is on BetterStack, not Statuspage. Their
  `index.json` does expose `aggregate_state`, which is what
  `ai-providers-degraded` uses; the incident list inside it is nested behind
  `included[]` relationship objects and was not worth the parsing risk for the
  wall.
- **arXiv "last 24 h" counts.** `submittedDate:[now-24h TO now]` returns 0, and
  `[now-48h TO now-24h]` also returns 0 — the search index lags 2–3 days.
  `lastUpdatedDate` behaves the same. Hence the lagged 7-day window.
- **Artificial Analysis v1 / v3.** Only `/api/v2/...` exists; v1 and v3 return
  the site's 404 HTML.
- **Hugging Face total repo count.** No `X-Total-Count` header on
  `/api/models`, `/api/datasets` or `/api/spaces`, and no count-only parameter.
  Total-corpus-size metrics are not available without a full crawl.

## Framework quirks worked around

- `http.csv()` splits on newlines before handling quotes, so it mangles Epoch's
  CSVs (which contain quoted multi-line notes fields). `src/instruments/epoch.js`
  fetches with `http.text()` and runs a local quote-aware parser instead.
- `mergeSnapshot` treats a returned `series` as a **full replacement**, so a feed
  that only exposes a rolling window would never accumulate history.
  `npm-ai-sdk-downloads` concatenates `ctx.prev.series` itself; the collector's
  `dedupeSeries` makes that idempotent.
