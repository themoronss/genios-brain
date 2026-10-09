# STEP-11 check — the golden measurement (2026-10-09, at `353d06ea`)

`measure_expertise.py` replays all 47 founder cases from their cassettes through the real chain and reads,
before removing each tenant: its situations (type, domain, recorded end, admission, what R-1 answered), its
signals and its cards (domain, capability, rule). No model spend; read only.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/<a NEW scratch database> \
        .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s11-check/measure_expertise.py" [CASE …]

It writes one JSON per case into `out/` beside itself (not kept here). The run: 47 cases, 0 errors, 0 golden
tenants left; the verdicts equal the board's (`03` §F.1). `table.md` is the per-case table STEP-11 §8.1
reads.
