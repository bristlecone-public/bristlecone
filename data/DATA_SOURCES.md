# Data sources, terms, and attribution

The MIT licence in this repository covers **the code**. The files under `data/` carry the terms of
their original sources. Most are works of the United States Government and are in the public
domain; two sources have conditions worth reading before you redistribute anything.

## Summary

| Source | Feeds | Status |
|---|---|---|
| **Bureau of Labor Statistics** (CPI, PPI, CE Diary, QCEW, import/export price indexes) | `cpi_item_month.parquet`, P1–P10, R1 | US Government work — public domain |
| **Bureau of Economic Analysis** (input-output tables, PCE bridge) | `p7_tariff.json` | US Government work — public domain |
| **Census Bureau** (decennial SF1 / DHC / STF1A) | `cohort_flows_both_sexes.csv.gz` | US Government work — public domain |
| **IPUMS NHGIS** (1950–1980 county tabulations) | `cohort_flows_both_sexes.csv.gz` | Public-domain census tabulations, redistributed by IPUMS — **citation requested**, see below |
| **Federal Reserve (FRED / ALFRED)** | `p4_vintages.json` | Free to use with attribution |
| **Federal Reserve Bank of Atlanta** (Sticky-Price CPI) | `p3_persistence.json` | Free to use with attribution |
| **Zillow** (Zillow Observed Rent Index) | `p9_metro.json` — **REMOVED, not redistributed** | See below |

## Zillow Observed Rent Index (ZORI) — excluded from this repository

`p9_metro.json` is published with **all ZORI-derived values removed** (`zori_yoy_l12`, the
CPI-shelter/ZORI `gap`, the best-lag correlation table, and the ZORI column of every
`shelter_small_multiples` series).

Zillow's Terms of Use (updated 2025-10-28) §4(C) grant the right to "display and distribute
derivative works" only of "Aggregate Data provided on the Zillow Local-Info Pages", and go on to
state: *"You are prohibited from displaying any other Zillow Companies' data without our prior
written approval."* ZORI is published through Zillow's Research CSVs, not the Local-Info pages, so
we do not redistribute values derived from it.

This costs you nothing methodologically. `cpi-lab/pipelines/p9_metro.py` is unchanged, and
`coverage.zori_source` in the published file names the exact CSV. Download ZORI from
[Zillow Research](https://www.zillow.com/research/data/) under your own acceptance of Zillow's
terms, re-run the pipeline, and you get the complete file. If you publish anything derived from
ZORI, Zillow requires the citation "Data Provided by Zillow Group" and prohibits use of their
logos.

## IPUMS NHGIS

The 1950–1980 county sex-by-age tabulations behind the pre-1990 decades were obtained through
IPUMS NHGIS. The underlying tabulations are public-domain Census Bureau products; IPUMS asks that
work using them cite NHGIS. What is published here is derived several steps downstream — cohort
survival residuals on constant-territory units, not the extracts themselves — but the citation is
owed regardless:

> IPUMS National Historical Geographic Information System, University of Minnesota,
> [www.nhgis.org](https://www.nhgis.org). (Cite the specific version used; see the NHGIS site for
> the current citation form.)

## Attribution for the Federal Reserve series

- Revision vintages are drawn from **ALFRED**, Federal Reserve Bank of St. Louis.
- The comparison series in `p3_persistence.json` is the **Sticky-Price CPI**, Federal Reserve Bank
  of Atlanta. It is included for benchmarking; our persistence classification is our own and
  differs from theirs by construction (see the file's `notes`).

## Live Pulse data

The six Pulse workers are not represented under `data/`. They serve current readings over a public
API (`/api/state`, `/api/registry`, …; see the main README). `/api/registry` names the upstream
source and licence for every instrument individually — several of those upstreams have their own
terms, so check the registry entry before redistributing any Pulse reading.

## If you spot a problem

If any file here misstates a source, omits a required attribution, or redistributes something it
shouldn't, please open an issue and it will be corrected or removed.
