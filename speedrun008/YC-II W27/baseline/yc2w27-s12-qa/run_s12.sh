#!/usr/bin/env bash
# The whole deterministic-qa tier for block yc2_w27_s12 (M32 and M33), exit codes recorded verbatim.
# Every database check runs on a database CREATED for it, on the second scratch server (127.0.0.1:55433,
# /dev/shm 1 GB) — the first holds ~1,359 databases and crashed creating another (12 Oct). The full
# suite runs ALONE (03 F115); the golden lane, the board and the hermetic job then run side by side.
set -u
SP=/private/tmp/claude-501/-Users-rohitswerashi-Downloads-Artifacts-Product-genios-brain--yc-/cdd818fd-1396-4cba-baf1-c3496eac2192/scratchpad
REPO="/Users/rohitswerashi/Downloads/Artifacts/Product/genios-brain (yc)/genios-brain"
OUT=$SP/qa/s12run${QA_RUN:-1}
mkdir -p "$OUT"
cd "$REPO" || exit 3
S="$OUT/summary.txt"; : > "$S"
echo "head $(git rev-parse --short HEAD)  code dirty=$(git status --porcelain -- genios_engine scripts tests tree.yaml 'Domain Expertise' | wc -l | tr -d ' ')  started $(date -u +%FT%TZ)" >> "$S"
RUN=$(date -u +%H%M%S)
newdb() { docker exec genios-yc2w27-pg2 psql -U postgres -q -c "create database $1" && echo "postgresql+psycopg://postgres:scratch@127.0.0.1:55433/$1"; }

TS=$(date -u +%Y%m%dT%H%M%SZ)
.venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s12-qa/qa_block_nodrop.py" yc2_w27_s12 ".trace/reports/qa-yc2_w27_s12-units-$TS.json" > "$OUT/units.log" 2>&1
echo "units   exit=$?  $(tail -1 "$OUT/units.log")  report=.trace/reports/qa-yc2_w27_s12-units-$TS.json  $(date -u +%T)" >> "$S"

URL=$(newdb "g12_qa_full_$RUN")
GENIOS_TEST_DATABASE_URL=$URL .venv/bin/python -m pytest -q -rs -p no:cacheprovider > "$OUT/fullsuite.log" 2>&1
echo "fullsuite exit=$?  $(tail -1 "$OUT/fullsuite.log")  db=g12_qa_full_$RUN  $(date -u +%T)" >> "$S"

GURL=$(newdb "g12_qa_golden_$RUN")
BURL=$(newdb "g12_qa_board_$RUN")
( GENIOS_TEST_DATABASE_URL=$GURL GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest -q -rs -p no:cacheprovider tests/replays tests/test_golden_labels_sheet.py > "$OUT/golden.log" 2>&1
  echo "golden  exit=$?  $(tail -1 "$OUT/golden.log")  db=g12_qa_golden_$RUN  $(date -u +%T)" >> "$S"
  echo "golden orgs left: $(docker exec genios-yc2w27-pg2 psql -U postgres -d g12_qa_golden_$RUN -tA -c "select count(*) from orgs where id like 'org_golden_%'" 2>&1)" >> "$S" ) &
( GENIOS_TEST_DATABASE_URL=$BURL .venv/bin/python scripts/golden_score.py --assert-recorded "speedrun008/YC-II W27/03-FINDINGS.md" > "$OUT/board.log" 2>&1
  echo "board   exit=$?  $(grep -vE ' INFO | WARNING ' "$OUT/board.log" | tail -1)  $(date -u +%T)" >> "$S" ) &
( env -u GENIOS_TEST_DATABASE_URL -u GENIOS_GOLDEN_REQUIRED .venv/bin/python -m pytest -q -rs -p no:cacheprovider -m "not golden" > "$OUT/hermetic.log" 2>&1
  echo "hermetic exit=$?  $(tail -1 "$OUT/hermetic.log")  $(date -u +%T)" >> "$S" ) &
wait
echo "finished $(date -u +%FT%TZ)" >> "$S"
cat "$S"
