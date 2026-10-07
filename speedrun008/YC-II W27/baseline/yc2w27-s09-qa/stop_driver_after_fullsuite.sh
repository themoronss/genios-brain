#!/usr/bin/env bash
# Stop the sequential driver the moment its full-suite line is written: its later tiers already run
# in parallel (run_s09_rest.sh). Records what it stopped.
S=/private/tmp/claude-501/-Users-rohitswerashi-Downloads-Artifacts-Product-genios-brain--yc-/cdd818fd-1396-4cba-baf1-c3496eac2192/scratchpad/qa/s09run/summary.txt
until grep -q "^fullsuite" "$S"; do sleep 1; done
kill 47181 2>/dev/null; sleep 1
for pid in $(ps -o pid=,command= -ax | grep -E "pytest -q -rs tests/replays|pytest -q -m \"not golden\"|create database genios_qa_golden_[0-9]" | grep -v grep | awk '{print $1}'); do kill "$pid" 2>/dev/null; done
echo "driver stopped after its full-suite line at $(date -u +%T); golden, board and hermetic run in parallel — summary_rest.txt" >> "$S"
grep "^fullsuite" "$S"
