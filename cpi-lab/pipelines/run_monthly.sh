#!/bin/bash
# Daily poll (cron 09:35 America/Chicago; BLS releases CPI at 07:30 CT).
# Order: P5 → P0 → P4, P8, P6, P9 (always) → [new CPI data only] P1 → P2 → P3 → P10 → P7 → [Feb] weight refresh chain.
# Exit code 2 from any pipeline = a validation check outside tolerance; tables/JSON are still written.
: "${CPI_ROOT:?set CPI_ROOT to the pipeline working directory}"
cd "$CPI_ROOT" || exit 1
exec 9>$CPI_ROOT/.lock; flock -n 9 || exit 0
LOG=$CPI_ROOT/cpi.log
run() { # run <name> <cmd...>  — log a header, run, warn on non-zero, never abort the script
  local name=$1; shift
  echo "== $(date -Is) $name" >> $LOG
  "$@" >> $LOG 2>&1 || echo "WARNING: $name exited non-zero — see above" >> $LOG
}

# P5 (instrument health): its BLS sources (imputation, response rates, variance, notices) refresh on their
# own schedule, so it runs first and unconditionally; source failures are swallowed inside the pipeline.
run p5 ./p5_quality.py

echo "== $(date -Is) p0" >> $LOG
OUT=$(./p0_fetch.py 2>&1); rc=$?
echo "$OUT" >> $LOG
[ $rc -eq 2 ] && echo "WARNING: P0 validation mismatch — check before trusting this month" >> $LOG

# P4 (ALFRED vintages): ALFRED may post a vintage a day after BLS; self-gates, ~40 s when nothing new.
# Needs p5_se and cpi_item_month → after P5 and P0.
run p4 ./p4_vintages.py
# P8 (C-CPI-U vs CPI-U): interim/final chained revisions land with the quarterly releases and stage flips
# happen without new CPI data → unconditional; Last-Modified cached (~1.5 s when unchanged).
run p8 ./p8_chained.py
# P6 (PPI pipeline pressure): PPI publishes on its own calendar (~1 day around the CPI) and revises its
# last four months at every release, so the pressure figure and vintage history move even without new CPI
# data → unconditional. Needs cpi_item_month → after P0. ~27 s.
run p6 ./p6_pipeline.py
# P9 (metro CPI vs local wages/rents): metro CPI only moves with new CPI data, but QCEW posts a quarter in
# Mar/Jun/Sep/Dec and ZORI refreshes monthly, both off the CPI calendar → unconditional. Needs
# cpi_item_month for its US-city-average cross-check. ~16 s.
run p9 ./p9_metro.py

if echo "$OUT" | grep -q "nothing new"; then exit 0; fi

# ---- new CPI data ----
run p1 ./p1_salience.py
run p2 ./p2_distribution.py
run p3 ./p3_persistence.py
run p10 ./p10_network.py
run p7 ./p7_tariff.py

# February: annual weight refresh (new December weights + revised seasonal factors arrive with January CPI)
if [ "$(date +%m)" = "02" ]; then
  run p0-weights ./p0_fetch.py --weights --force
  run p1 ./p1_salience.py
  run p2 ./p2_distribution.py
  run p3 ./p3_persistence.py
  run p7 ./p7_tariff.py
fi
