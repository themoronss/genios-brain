# The test suite — lanes, layout, and how to run it in parallel

## Layout

The 178 files at the top of `tests/` are the flat, historical suite. Everything for the
Layer 1 v2 build lives in a nested tree whose paths are the acceptance gates from
`Rohit_Updates (Version 2)/Version 2 Updates/01-Layer-1-Plan/09-Build-Order-and-Acceptance.md`,
so a gate is a command that runs rather than a path that may not exist yet:

```
tests/contracts/          G0   W0   the C-01..C-12 surface and its validators
tests/capture/
  conftest.py                       eval_time · worked-example text · span_of · FakeLLM · no-network guard
  structural/             G2   W2   quoted-reply/signature stripping, threads, chunking
  documents/              G2   W2   attachment refetch, OCR failure marking
  structured/             G2   W2   the CRM bypass lane (zero LLM calls)
  semantic/               G3/G4 W3/W4  vocabulary, schema gen, profiles, open lane, binder, extractor
  validate/               G1/G5 W1/W5  spans, dates, money, confidence · claim groups, conflicts
  esqe/                   G6/G7/G8 W6-W8  detection, importance (ALG-17), publication
  connectors/             G9   W9   backfill window
  acquire/                G9   W9   cadence + deterministic jitter
  coverage/               G9   W9   coverage_ready wiring
  test_webhook_parity.py  G9   W9   parity is a property of both lanes, so it sits above them
tests/golden/l1/          G4   W4   the 30 labelled messages + the graded replay
```

No `__init__.py` anywhere in the new tree — pytest's rootdir-relative import mode gives each
file a module name from its own directory, and adding package files would make every basename
collide with the flat suite above.

Every directory ships a placeholder that **skips** with the wave that will fill it (the
`l1_pending` fixture in `tests/conftest.py`). That is the build's progress bar:
`pytest tests/capture -q` printing *N skipped* names exactly what has not landed. **A skip is
not a pass** — a wave is done when its gate passes with zero skips.

## Markers

Registered in `pyproject.toml` under `--strict-markers`, so a typo is a collection error rather
than a silent no-op.

| marker | means | in CI? |
|---|---|---|
| `unit`  | hermetic: no network, no DB, no LLM, no wall clock | yes |
| `gate`  | a named acceptance gate (G0..G10) — must pass, never skip | yes |
| `pg`    | needs a real PostgreSQL via `GENIOS_TEST_DATABASE_URL` | no (skips) |
| `llm`   | calls a real model, costs money | no |
| `slow`  | minutes: golden corpus, distribution replays | no |

Everything under `tests/capture/` is hermetic **by construction**: `tests/capture/conftest.py`
refuses `socket.connect` for the duration of any test there that is not marked `pg` or `llm`.
The error message names the escape hatch, so the guard teaches rather than merely blocks.

```bash
pytest -q                                   # the default lane
pytest tests/capture -q -m gate             # the L1 gates, incl. the ones still skipping
pytest tests/capture -q -m "not pg"         # hermetic only, explicitly
GENIOS_TEST_DATABASE_URL=postgresql://localhost/genios_test pytest -q -m pg
```

## The production guard — do not weaken it

`tests/conftest.py` sets `GENIOS_DATABASE_URL` **at import time**, before the `lru_cache`d
`get_settings()` is first materialized: to the scratch URL when `GENIOS_TEST_DATABASE_URL` is
set, and to `""` when it is not. Every seam that resolves a database from settings — the `conn`
fixtures, `make_registry()` with no argument, anything written later — is covered by that one
assignment, and nine modules that call `make_registry()` during *collection* are the reason it
happens at import rather than in a fixture. The file's own comments carry the incident history
(commits `ae63ef9`, `d860b8e`); read them before changing a line of it.

There is deliberately **no fallback** to `get_settings().database_url`. Without a scratch URL,
`pg` tests skip. That is the contract, and "it skipped in CI" is not a reason to add one.

## pytest-xdist: the decision

**pytest-xdist is not installed today** (`pytest 9.1.1`, nothing else). This section is the
decision for when someone reaches for it, because reaching for `-n auto` on this suite as it
stands would corrupt the `pg` lane rather than fail honestly.

### Run the hermetic lane in parallel; run `pg` serially. Two commands, not one.

```bash
pytest -n auto -m "not pg and not llm and not slow" -q     # safe today, no changes needed
pytest -p no:xdist -m pg -q                                # serial, one worker, one database
```

### Why `pg` cannot go under `-n auto` as written

Each xdist worker is a **separate process running its own session**, and three things in the
`pg` lane are session-scoped against one shared database:

1. **Migrations run at conftest import, once per process.** `tests/conftest.py` calls
   `apply_migrations()` while the module loads. Under `-n auto` that is N processes issuing the
   same `create table if not exists` / `create index` DDL against one database at the same
   moment. Idempotent is not the same as concurrency-safe: concurrent identical DDL in
   PostgreSQL blocks on catalog locks and can fail outright (`tuple concurrently updated`,
   duplicate key on `pg_type`). The suite would fail during collection, in a different worker
   each run.

2. **One scratch org, shared by every worker.** `_seed_scratch_org()` seeds a single
   `org_scratch_tests`, and the `conn` fixtures start from `select id from orgs limit 1`. Every
   worker therefore writes into the same tenant. Tests that seed and then count rows for that
   org see each other's rows; which worker won is scheduling, so the failure is intermittent
   and reads as flakiness rather than as a design fault.

3. **The `conn` fixtures hold open transactions and roll back.** Two workers touching the same
   rows means one waits on the other's transaction id. On Supabase, where
   `idle_in_transaction_session_timeout = 0`, an interrupted worker leaves a transaction holding
   locks that nothing reclaims — this has already blocked the suite for hours once.

### The way out, if the `pg` lane ever gets slow enough to matter

Give each worker its **own database**, not its own schema — the migrations create extensions and
types, so schema isolation does not go far enough. `PYTEST_XDIST_WORKER` (`gw0`, `gw1`, …) is set
in each worker's environment, and `tests/conftest.py` would derive from it **before** the
import-time `apply_migrations()` call:

```python
_worker = os.environ.get("PYTEST_XDIST_WORKER", "")          # "" when not under xdist
if _base := os.environ.get("GENIOS_TEST_DATABASE_URL"):
    url = f"{_base}_{_worker}" if _worker else _base         # genios_test_gw0, genios_test_gw1
    _create_database_if_absent(url)                          # connect to `postgres`, CREATE DATABASE
    os.environ["GENIOS_TEST_DATABASE_URL"] = url
```

The cost is honest and worth stating: N full migration runs on every invocation (~1s each
today, and it grows with the migration count), plus N databases to drop. Do this only when the
serial `pg` lane is genuinely the bottleneck — and note that it does not remove the need for the
serial fallback, because `-p no:xdist` is still how you reproduce a failure a worker reported.

### What parallelism does not fix

The `slow` and `llm` lanes are bounded by a model, not by CPU. Running the golden corpus under
`-n auto` multiplies spend without shortening the wall clock much, and the extraction cache —
the thing that makes an unchanged re-run cost nothing — is keyed per content, so N workers
racing on the same corpus can each miss the same key. Run those serially, on purpose.
