#!/usr/bin/env bash
# STEP-09 QA, the tiers after the full suite — run NOW, in parallel, each on a database created for it
# (the sequential driver is stopped after its full-suite line). Exit codes recorded verbatim.
set -u
SP=/private/tmp/claude-501/-Users-rohitswerashi-Downloads-Artifacts-Product-genios-brain--yc-/cdd818fd-1396-4cba-baf1-c3496eac2192/scratchpad
REPO="/Users/rohitswerashi/Downloads/Artifacts/Product/genios-brain (yc)/genios-brain"
OUT=$SP/qa/s09run
cd "$REPO" || exit 3
S="$OUT/summary_rest.txt"; : > "$S"
echo "head $(git rev-parse --short HEAD)  code dirty=$(git status --porcelain -- genios_engine scripts tests tree.yaml | wc -l | tr -d ' ')  started $(date -u +%FT%TZ)" >> "$S"
RUN=$(date -u +%H%M%S)
newdb() { docker exec genios-yc2w27-pg psql -U postgres -q -c "create database $1" && echo "postgresql+psycopg://postgres:scratch@127.0.0.1:55432/$1"; }
GURL=$(newdb "genios_qa_golden_p$RUN")
( GENIOS_TEST_DATABASE_URL=$GURL GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest -q -rs -p no:cacheprovider tests/replays tests/test_golden_labels_sheet.py > "$OUT/golden_p.log" 2>&1
  echo "golden  exit=$?  $(tail -1 "$OUT/golden_p.log")  db=genios_qa_golden_p$RUN  $(date -u +%T)" >> "$S"
  GENIOS_TEST_DATABASE_URL=$GURL .venv/bin/python scripts/golden_score.py --assert-recorded "speedrun008/YC-II W27/03-FINDINGS.md" > "$OUT/board_p.log" 2>&1
  echo "board   exit=$?  $(tail -1 "$OUT/board_p.log")  $(date -u +%T)" >> "$S"
  echo "golden orgs left: $(docker exec genios-yc2w27-pg psql -U postgres -d genios_qa_golden_p$RUN -tA -c "select count(*) from orgs where id like 'org_golden_%'" 2>&1)" >> "$S" ) &
( env -u GENIOS_TEST_DATABASE_URL -u GENIOS_GOLDEN_REQUIRED .venv/bin/python -m pytest -q -rs -p no:cacheprovider -m "not golden" > "$OUT/hermetic_p.log" 2>&1
  echo "hermetic exit=$?  $(tail -1 "$OUT/hermetic_p.log")  $(date -u +%T)" >> "$S" ) &
wait
echo "finished $(date -u +%FT%TZ)" >> "$S"
cat "$S"
