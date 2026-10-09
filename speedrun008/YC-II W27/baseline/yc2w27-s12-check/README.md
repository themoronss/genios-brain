# STEP-12 check — the golden measurement (2026-10-10, at `c50f0f7e`)

- `cassette_sites.py` — what the model was asked across the 47 cases, from the cassettes alone (no
  database, no spend): 409 answers, 65 of them the decider's in 24 cases; of the 10 must-detect cases
  with no card, 7 never reach the decider (STEP-12 §8.1). Runs anywhere: `python3 cassette_sites.py`.
- `measure_expert_inputs.py` — what an expert pass would be handed per FILE in each case (the brief's
  line, the file, its timeline, its numbers with their n, its playbook, its situations and cards). Not
  run yet: the machine slept through the night of 9–10 Oct, and a golden run that spans a sleep is not a
  measurement (`03` F143). It runs on a NEW scratch database, on a machine that stays awake:

      GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55432/<new db> \
        .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s12-check/measure_expert_inputs.py"

  It writes one JSON per case into `out/` beside itself (not kept here).
