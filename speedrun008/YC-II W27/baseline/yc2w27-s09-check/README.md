# STEP-09 check — the golden measurement (2026-10-07, at `c1cab2fc`)

`measure_workstreams.py` replays the 32 cases STEP-09 is about from their cassettes through the real
chain and reads each tenant's rows before removing it — correlations, situations with their admission
and end, open loops, signals, cards and, for every introduced contact, whether it is a person in
memory, has its own file, and whether that file holds its introduction. No model spend.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/<a NEW scratch database> \
        .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s09-check/measure_workstreams.py" [CASE …]

It writes one JSON per case into `out/` beside itself (not kept here; `summary.json` is the run's
index: 32 runs, 0 errors, 0 golden tenants left). `table.md` is the per-case table STEP-09 §8.1 reads.
