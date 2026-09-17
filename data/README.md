# Data

Published outputs from the pipelines in this repository, so the numbers behind the write-ups and
dashboards can be checked without re-running anything. Everything here is **regenerable** — each
file names the pipeline that produced it.

Licensing: the MIT licence covers the code, **not** these files. See
[DATA_SOURCES.md](DATA_SOURCES.md) for provenance, terms, and attribution per source.

Bulk download: a `bristlecone-data.zip` of this whole directory is attached to the repository's
latest Release.

## `cpi-lab/` — CPI Lab pipeline outputs

The base panel plus one JSON per pipeline. Every JSON carries its own `generated_at`, a `notes` or
`caveats` block stating what the number is **and is not**, and most carry a `validation` block
comparing computed values against BLS published figures — that block is the point if you're
auditing rather than just reading.

| File | Size | What it is | What you'd use it for |
|---|---|---|---|
| `cpi_item_month.parquet` | 7.8 MB | **The base panel.** 225,479 rows × 10 cols, one row per (CPI item, month), **1913-01 → 2026-08**. Columns: `item_code`, `ym`, `idx_nsa`, `idx_sa`, `mom_sa`, `mom_nsa`, `yoy`, `ann3m`, `weight`, `contrib_yoy`. | Recomputing any analysis here from scratch, or any item-level CPI work of your own. This is the table everything else derives from. |
| `p1_salience.json` | 122 KB | Frequency-weighted ("salience") CPI: five index variants, bootstrap CIs, 173 items' latest values, a 728-row sensitivity grid. | Comparing a purchase-frequency-weighted basket against the official one. Read `r1_expectations.json` before concluding it means anything about perceptions. |
| `p2_distribution.json` | 755 KB | Cross-sectional shape of item inflation: summary stats (all and ex-shelter), a 60-month ridgeline, variance shares. | Asking whether inflation is broad or concentrated in a few items in a given month. |
| `p3_persistence.json` | 201 KB | Sticky vs flexible: AR(1) persistence and half-lives for 174 items, a treemap, and the Atlanta Fed sticky-price series alongside for comparison. | Separating persistent from transitory components — with the caveat that statistical persistence ≠ menu-cost stickiness. |
| `p4_vintages.json` | 371 KB | Revision vintages for 13 series: first-print → final transitions, fan charts, revision standard errors. | Judging how much a fresh CPI print can move, and whether a headline tenth is signal. |
| `p5_quality.json` | 218 KB | Instrument health: imputation rates, response rates, collection modes, 92 dated events. | Checking whether a surprising month is real or a collection artifact. |
| `p6_pipeline.json` | 995 KB | PPI→CPI pass-through: 61 verified pairs with full cross-correlograms, local-projection betas at **every horizon 0–12** (`beta`, plus `disc_beta`), and a 36-month "pressure still to come" series with 82 validation rows. | Studying producer-to-consumer pass-through, or re-deriving the pressure index under your own assumptions. `disc_beta` is the response curve used to discount already-realised pass-through. |
| `p7_tariff.json` | 337 KB | Tariff exposure: 103 series, a 179-item treemap, 87 dated tariff events, 26 event studies, PCE import content by category. | Event-study work on trade policy. Note the exposed-vs-domestic split is confounded by tech hedonics vs services — see the file's `notes`. |
| `p8_chained.json` | 342 KB | CPI-U vs C-CPI-U substitution gap: 29 items, heatmap, decomposition, full revision history by stage. | Quantifying substitution bias in the fixed-weight index. |
| `p9_metro.json` | 260 KB | 23 metros: local CPI, real wages from QCEW, a 213-row dispersion series, CPI-shelter series. | Comparing metro inflation and real wage growth. **ZORI-derived values are removed** — see the note below. |
| `p10_network.json` | 162 KB | Lead-lag network across 74 CPI categories: 5 overlapping windows, 6 groups, raw and common-factor-removed variants, 20 sanity checks. | Exploring co-movement structure. It is **screened correlation, not causation** — most edges do not pass Granger tests, which the file says plainly. |
| `r1_expectations.json` | 54 KB | The research note's panel and regressions: 54 months, Michigan/NY Fed expectations, incremental tests. | The honest counterweight to P1 — it finds the frequency-weighted index does **not** explain household inflation expectations. |

### Vintages

These are snapshots, not a live feed, and they are deliberately uneven — each pipeline runs when
its upstream data moves. Check each file's `generated_at`. As published: P4/P5/P6/P8/P9 are
2026-09-16; P1/P2/P7/P10 and the parquet are 2026-09-12; P3 is 2026-09-05; R1 is 2026-08-19.

### Note on `p9_metro.json` and ZORI

The published copy has all Zillow-derived values removed: `zori_yoy_l12`, the CPI-shelter/ZORI
`gap`, the best-lag correlation table, and the ZORI column of every
`shelter_small_multiples` series. Zillow's Terms of Use do not grant redistribution rights for
Zillow Observed Rent Index data (see [DATA_SOURCES.md](DATA_SOURCES.md)).

Nothing methodological is lost: `cpi-lab/pipelines/p9_metro.py` is unchanged and
`coverage.zori_source` still names the exact CSV, so you can download ZORI from Zillow yourself,
under their terms, and regenerate the complete file.

## `census/` — cohort tracing outputs

| File | Size | What it is | What you'd use it for |
|---|---|---|---|
| `cohort_flows_both_sexes.csv.gz` | 13.4 MB (46 MB raw) | The complete cohort-flow table, sexes summed: one row per (period, unit, cohort). Columns include `period`, `unit`, `cohort_age_at_t0`, `birth_years`, `count_t0`, `count_t1`, `expected_t1`, `net_residual`, `net_migration_rate`. Seven decades, 1950→2020, on constant-territory county units. | Reproducing every ranking in `census/output/report.md`, or doing your own county migration analysis. `net_residual` is the headline quantity: actual minus survival-expected. |

The per-decade, per-sex files (~158 MB) are not published — regenerate them with
`cd census && python -m cohort_trace all`.

**Read the caveats before using the residuals.** They absorb international migration, differential
undercount, and mortality alongside domestic migration; off-campus students inflate college-town
young-adult gains; pre-1990 decades run on total population, so military installations and resource
booms dominate them. The caveat section of `census/output/report.md` is not boilerplate.
