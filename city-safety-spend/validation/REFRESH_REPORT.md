# Refresh report 2026-09-15 23:37

## Steps

| step | ok | seconds | last line |
|---|---|---|---|
| findings | yes | 0.3 |    "share": 2 |
| findings_page | yes | 0.1 | wrote <home>\Documents\GitHub\city-safety-spend\site\findings.html (24 KB) |

## New data

- Fiscal years added to the long series: none
- City-years now / before: 3695 / 3695

## Did history move?

Comparing every city-year present both before and after (3695 compared), **0** moved by more than half a point of the general-expenditure share; staffing: **0** of 4342 moved by more than 0.5 officers per 1,000.

## Validation headlines

| measure | before | after |
|---|---|---|
| 2022 cities with a complete record | 327 | 327 |
| 2022 median police+fire share of general expenditure | 27.75 | 27.75 |
| FBI sworn counts within 10% (reported years) | 82.1 | 82.1 |
| census 2012 item codes matching published totals | 100.0 | 100.0 |
| census 2017 item codes matching published totals | 99.979 | 99.979 |
| census 2022 item codes matching published totals | 98.552 | 98.552 |
| county jail allocation vs FiSC, median ratio | 1.0 | 1.0 |

## Then what

1. Read the moves above. If they are explained (a Census revision, a city reorganised), note them in `data/known_issues.csv` or `validation/REPORT.md`.
2. If a new year arrived, check the new year's flags: imputed cities, incomplete records, and any city whose share moved more than a couple of points.
3. Commit the rebuilt outputs, run `python pipeline/factsheets.py` if it was skipped, deploy with `scripts/deploy_factsheets.ps1`, and republish the dashboard artifact.
