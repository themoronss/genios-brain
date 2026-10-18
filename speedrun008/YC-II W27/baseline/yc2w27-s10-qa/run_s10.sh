#!/usr/bin/env bash
# The whole deterministic-qa tier for block yc2_w27_s10, exit codes recorded verbatim. Every database
# check runs on a database CREATED for it (auto mode refuses drops). The full suite runs ALONE (03 F115:
# four capture tests are sensitive to concurrent load); the golden lane, the board and the hermetic job
# then run side by side.
set -u
SP=/private/tmp/claude-501/-Users-rohitswerashi-Downloads-Artifacts-Product-genios-brain--yc-/cdd818fd-1396-4cba-baf1-c3496eac2192/scratchpad
REPO="/Users/rohitswerashi/Downloads/Artifacts/Product/genios-brain (yc)/genios-brain"
OUT=$SP/qa/s10run
mkdir -p "$OUT"
cd "$REPO" || exit 3
S="$OUT/summary.txt"; : > "$S"
echo "head $(git rev-parse --short HEAD)  code dirty=$(git status --porcelain -- genios_engine scripts tests tree.yaml 'Domain Expertise' | wc -l | tr -d ' ')  started $(date -u +%FT%TZ)" >> "$S"
RUN=$(date -u +%H%M%S)
newdb() { docker exec genios-yc2w27-pg psql -U postgres -q -c "create database $1" && echo "postgresql+psycopg://postgres:scratch@127.0.0.1:55432/$1"; }

"$SP/m19/ensure_pg.sh" >> "$OUT/pg.log" 2>&1 || { echo "postgres not ready" >> "$S"; exit 3; }
TS=$(date -u +%Y%m%dT%H%M%SZ)
python3 "$SP/qa/qa_block_nodrop.py" yc2_w27_s10 ".trace/reports/qa-yc2_w27_s10-units-$TS.json" > "$OUT/units.log" 2>&1
echo "units   exit=$?  $(tail -1 "$OUT/units.log")  report=.trace/reports/qa-yc2_w27_s10-units-$TS.json  $(date -u +%T)" >> "$S"

URL=$(newdb "genios_qa_s10_full_$RUN")
GENIOS_TEST_DATABASE_URL=$URL .venv/bin/python -m pytest -q -rs -p no:cacheprovider > "$OUT/fullsuite.log" 2>&1
echo "fullsuite exit=$?  $(tail -1 "$OUT/fullsuite.log")  db=genios_qa_s10_full_$RUN  $(date -u +%T)" >> "$S"

GURL=$(newdb "genios_qa_s10_golden_$RUN")
BURL=$(newdb "genios_qa_s10_board_$RUN")
( GENIOS_TEST_DATABASE_URL=$GURL GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest -q -rs -p no:cacheprovider tests/replays tests/test_golden_labels_sheet.py > "$OUT/golden.log" 2>&1
  echo "golden  exit=$?  $(tail -1 "$OUT/golden.log")  db=genios_qa_s10_golden_$RUN  $(date -u +%T)" >> "$S"
  echo "golden orgs left: $(docker exec genios-yc2w27-pg psql -U postgres -d genios_qa_s10_golden_$RUN -tA -c "select count(*) from orgs where id like 'org_golden_%'" 2>&1)" >> "$S" ) &
( GENIOS_TEST_DATABASE_URL=$BURL .venv/bin/python scripts/golden_score.py --assert-recorded "speedrun008/YC-II W27/03-FINDINGS.md" > "$OUT/board.log" 2>&1
  echo "board   exit=$?  $(grep -vE ' INFO | WARNING ' "$OUT/board.log" | tail -1)  $(date -u +%T)" >> "$S" ) &
( env -u GENIOS_TEST_DATABASE_URL -u GENIOS_GOLDEN_REQUIRED .venv/bin/python -m pytest -q -rs -p no:cacheprovider -m "not golden" > "$OUT/hermetic.log" 2>&1
  echo "hermetic exit=$?  $(tail -1 "$OUT/hermetic.log")  $(date -u +%T)" >> "$S" ) &
wait
echo "finished $(date -u +%FT%TZ)" >> "$S"
cat "$S"
