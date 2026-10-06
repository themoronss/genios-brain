# 08 · For Harsh — deploying the batch, and what to run after

**Written for:** Harsh. **As of:** 2026-10-06. **From:** the `yc2_w27` build (Claude), pushed by
Rohit. Everything here can be checked against the repository; every number below names the file
or the command it came from.

---

## 0 · In one screen

1. **Deploy `speedrun008`**, at `77aba10e` or later. `origin/harsh/mvp` (`2c42722d`, 4 Oct) is
   **75 commits behind it and 0 ahead** — it fast-forwards, no merge, no conflict. **No migration**:
   the newest is still `0190`, which production has.
   ⛔ **CORRECTED 2026-10-06, for the NEXT push:** it carries STEP-02 (§1.4) and with it **migration
   `0191_reasoning_fingerprints`** — the first since `0190`. `main.py` applies it at boot when the
   database is writable; check the boot log says so (§2).
2. After the deploy, **re-queue the attachments** the `file_name` refusal dead-lettered (§3.1).
3. **Read the first `refetch_last_error`** that comes back (§3.2).
4. **Pin the Composio toolkits** — the one unit of this block that is yours (§3.3).
5. **Run the probes** and send the outputs; each bug is closed on its own probe (§4).
6. **Do not** switch `calibration_apply` on for anyone (§5).

The commits after `77aba10e` change CI, test docstrings and these docs only — the engine is the
same. `2e7aea5b` fixes the CI `test` job (§6); it reaches GitHub with Rohit's next push.

## 1 · What the deploy changes in production

33 commits in the push touch `genios_engine/`. Two groups.

### 1.1 · Fixes from this block — each with a test that fails without it

| | Commit | What changes at runtime |
|---|---|---|
| B2 | `d8c83cb4` | `context/graph_store.EDGE_TYPES` gains `involves`, `edited`, `assigned`, `used`. Events from the four writers that emit them used to roll back whole and park as *"model unavailable"*; they now commit. Latent today (production's memory writes almost none) |
| B17 | `94a93d9f` | the funnel's `decision_emitted` is written in every sweep — **zero included** — and counts the native and composite lanes as well as the rule lane. Expect a `decision_emitted` row per sweep from now on |
| B18 | `9bfd911e` `5c892922` `2e76cf4a` | the extractor's four park codes (`extraction_call_failed`, `_parse_failed`, `_schema_failed`, `_total_loss`) get a drain class; a parked extraction is selected for a re-read under a ladder, in the sweep's existing re-read pass. Expect the two mails parked since 3 Oct to be attempted |
| B20 | `36567231` `ba0577e3` | a fingerprint claimed by an event that was set aside no longer blocks the re-landed copy; `integration_disconnect(wipe_data=true)` deletes the events' `message_fingerprints` too. Before `STEP-08`'s re-sync this was mandatory |
| B19 | `681a85e3` | `GMAIL_GET_ATTACHMENT` is sent `file_name` (toolkit `20260915_00` requires it): the attachment's own name at capture, `"attachment"` on the refetch ladder. A response with no bytes the reader knows now stores its **shape** (keys and value types, never a value) in `parked_events.refetch_last_error` |
| B1 | `184269a0` | weekly calibration runs on Postgres again (it raised `UndefinedColumn card_level` on every run since 10 Sep) — **in shadow**: it records what it would mute or nudge and applies nothing unless the tenant's `calibration_apply` L4 feature is on, which is on for no one |
| STEP-01 | `bf28e7dc` | `routes._run_l2_chain` takes an optional `eval_time`; production passes none, so nothing changes |
| STEP-01 | `e730720d` `64110e92` | the narrator's prompt is built in one order: a card's quotes break ties on content, and its facts are sorted. Same content, stable order — the change gate (`STEP-02`) needs this |
| STEP-01 | `9e5cede8` | a stated dependency nobody could resolve anchors on the counterparty, chosen by canonical key, never on one of the company's own addresses — it could pin the founder as the counterparty of the founder's own mail |

### 1.2 · The 1–4 Oct work that was on `speedrun008` and never on `harsh/mvp` — 19 commits

The receipts-and-audit programme (`speedrun008/YCW27/`), merged with your branch in `568a245d`
(`STEP-00`). It ships with this deploy. The ones that change runtime behaviour, by their own commit
titles: `902284c8` the delivery findings (gate, outbox, push, pipeline, `card_builder`);
`32a5c3a4` L6 S1–S10 (learning-loop receipts); `ec275c70` `learning_objects` is write-once except
`state`; `2dc61dac` receipts gain a witness and a fourth status — `/readiness` now needs
*exercised*; `57465b1b` a reminder no longer names finished work; `2b110699` three Plane-D
situations accepted and live. The rest are receipts, declarations and audits. Their record, with
who owns what: `speedrun008/YCW27/19-PENDING-who-owns-what.md` and `21-PLAN-TO-PRODUCTION.md`.

### 1.4 · STEP-02, the change gate — in the next push

| | What changes at runtime |
|---|---|
| the gate | before the decider and R-1 are asked, each lane (compiled, legacy, native) fingerprints the request and skips a subject whose inputs did not move while its card keeps its authority — fewer `l4_llm_decision` and `l4_llm_r1` calls, the same cards |
| a DEFER | a live DEFER no longer expires the card it found; its suppression says `deferred` |
| new outcomes | `run_all` reports `skipped_unchanged`, `skipped_unchanged_compiled`, `deferred` every sweep |
| new table | `reasoning_fingerprints` (migration `0191`), wiped by the tenant reset |
| new health check | `scripts/pipeline_health.py` — *the change gate skips what did not change* |

The probe after the deploy: `@model_calls_by_day` in `baseline/production_state.sql` — 1,213 · 759 ·
1,887 a day on 2–4 Oct; the target is under 100.

### 1.3 · How it was tested before the push

`baseline/yc2w27-qa/qa_record.txt`, at `83dd87f3`, every check on an **empty** scratch Postgres 17:

| | Result |
|---|---|
| every unit's own verify, block `yc2_w27` | 55 pass / 1 fail / 0 skip — the fail is your unit, §3.3, not written yet |
| the whole suite, with the database and without it | exit 0 — first fully green database run on this branch was `e151a7db`: 16,736 passed, 0 failed |
| the golden set (`golden-pg`, as CI runs it) | 357 passed, 100 xfailed, 0 skipped |
| on GitHub, the first push | `golden-pg` ✅ passed (run `37407196202`, Python 3.12, Postgres 17); `test` — see §6 |

## 2 · Deploy

Production runs `harsh/mvp`. Either deploy `speedrun008` directly, or fast-forward your branch:

```
git fetch origin
git checkout harsh/mvp && git merge --ff-only origin/speedrun008    # 75 commits, no merge commit
git push origin harsh/mvp
```

No migration in the push of `77aba10e`. ⛔ **The next push carries `0191`**: `main.py` applies pending
migrations at boot, and the boot log says `migrations applied at boot: ['0191_reasoning_fingerprints.sql']`.
If it says `DEGRADED BOOT — database is read-only` instead, the change gate fails open (every subject
is decided, as today — nothing lost, nothing saved) and `/reset` fails until `0191` is applied, because
the reset now wipes `reasoning_fingerprints`. No new environment variable. One value we need from the
deploy's environment:
**`GENIOS_L4_LLM_DECISION_MAKER`** — on or off? The golden set runs the LLM decider on, as
`speedrun008/YCW27/STATUS.md` records production; `YCW27` decision R1 recommended off. Tell
Rohit which it is.

## 3 · After the deploy — in this order

### 3.1 · Re-queue the attachments the refusal dead-lettered

On Rohit's org, 2026-10-05: **88 of 88** stored refetch errors were the refusal, **50**
dead-lettered after five tries, **0** recovered (`baseline/2026-10-05/production_state.txt`,
`@attachment_refetch_errors`). A dead letter never retries on its own.

```
python scripts/requeue_refused_attachments.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"           # dry run: counts only
python scripts/requeue_refused_attachments.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL" --apply   # writes
```

- **Only after the deploy.** Before it, every row is refused five more times and dead-lettered
  again.
- It touches one tenant: Gmail parks `DOC-*` in `dead_letter` whose stored error names the
  refusal (`Missing required fields: file_name`). Each goes back to `pending`, attempts 0, next
  attempt now; the old error is kept, prefixed `requeued after the file_name fix (B19); was: `.
- `scripts/_db.py` refuses a production host unless `GENIOS_ALLOW_PROD_WRITE=1` is set — your
  call, for the `--apply` run only.

### 3.2 · Read the first error that comes back

Composio documents the action's output only as *"data from the action execution"*, so nobody
knows the current response shape. If a re-queued attachment still fails, its new
`refetch_last_error` now **names that shape** — keys and value types, no values:

```
select event_id, reason_code, status, refetch_attempts, refetch_last_attempt_at, refetch_last_error
  from parked_events
 where org_id = 'org_e97e86f858ad48b2bbf64b8a' and source = 'gmail' and reason_code like 'DOC-%'
 order by refetch_last_attempt_at desc nulls last
 limit 10;
```

Send the first one that is not *"requeued after the file_name fix"*. It tells us whether the
reader needs a change.

### 3.3 · Pin the Composio toolkits — `yc2_w27/M17.C3.L-integration.V2.U04`, yours

| | |
|---|---|
| what | replace `dangerously_skip_version_check=True` with pinned toolkit versions, in the one place each connector executes — Gmail at the version the `file_name` requirement was recorded against (`20260915_00`) — so an upstream schema change cannot silently refuse every call again |
| where | `genios_engine/capture/connectors/composio_base.py` |
| verify | `.venv/bin/python -m pytest tests/capture/connectors/test_composio_toolkits_are_pinned.py -q` — the test does not exist yet; it is part of the unit (today that command exits 4, *no tests ran* — the QA's one red line) |
| why you | it needs the Composio SDK the production image runs, and the versions confirmed against it; the SDK in the dev environment is not that one |

## 4 · The probes — send the outputs

Read-only, from `speedrun008/YC-II W27/baseline/production_state.sql`:

```
PGOPTIONS='-c default_transaction_read_only=on' psql "$URL" -f "speedrun008/YC-II W27/baseline/production_state.sql"
```

| Bug | Block | Before (2026-10-05) | After the deploy, expected |
|---|---|---|---|
| B17 | `@funnel_per_stage` | `decision_emitted` written in 3 of 64 sweeps, values 1–4, never 0 | written in every sweep, zeros included |
| B18 | `@park_queue` | 2 mails `extraction_parse_failed`, pending since 3 Oct 11:17 UTC, 0 attempts, no next attempt | attempted, with a next attempt or an end state |
| B19 | `@attachment_refetch_errors` | 88 of 88 the `file_name` refusal | no new refusal; re-queued rows fetched or failing with a named shape |
| B2 | `@l2_processing_runs` | 30 runs, 0 edge errors (latent) | still 0 |
| — | `@latest_migration` | `0190` | `0190` |

Two that are not in the file:

```
select max(evaluation_time), count(*) from calibration_runs;                                     -- B1: runs again after the next heavy tick
select count(*) from event_trace where reason_code = 'seen_on_screen';                           -- B20: after a reconnect, against events that no longer exist
```

## 5 · Do not

- switch **`calibration_apply`** on for any tenant. It is Rohit's decision (`06` D13), and not
  before `STEP-18` B22–B24: armed, an applied mute or nudge hides every open card of its pack;
- run the re-queue before the deploy;
- fix anything new silently — a finding goes to `03-FINDINGS.md` §E, a bug to `STEP-18`.

## 6 · CI

| Job | First push (`77aba10e`) | Why |
|---|---|---|
| `golden-pg` | ✅ passed | the golden set on Postgres 17, Python 3.12 — its first run anywhere but here |
| `test` | ⛔ red on its old install | it installed `.[dev]` alone. Reproduced exactly — that install, Python 3.12 — seven tests die at an import of a package `requirements.txt` ships: the six of `tests/test_office_extraction.py` (`openpyxl`, `python-pptx` — your `fb1d5c0b`, 10 Sep) and the golden runner's door test (`anthropic`). Every CI run listed since 27 Sep, on both branches, failed |

**Fixed in `2e7aea5b`** (`yc2_w27/M19.C5.L-integration.V5.U05`): the `test` job installs
`requirements.txt` first, as `golden-pg` already did; `tests/test_ci_runs_the_golden_set_on_postgres.py`
holds it. Run the way the new job runs — a git checkout of the commit, Python 3.12, `requirements.txt`
then `.[dev]`, `pytest -q -m "not golden"` — it gives **16,020 passed, 0 failed** (the 1,093
skipped are the database tests, which `golden-pg` and the database suite run). It reaches GitHub with Rohit's next push. The job's logs need admin rights to read — if
it is still red after that push, the log is yours to open.

## 7 · Where everything is

| | |
|---|---|
| what is done and owed, step by step | `07-WHAT-IS-DONE.md` |
| the step table | `00-START-HERE.md` |
| the bugs, with seams and probes | `STEP-18-TO-BUILD-known-bugs.md` |
| the golden set — what it is, how to run it | `STEP-01-PENDING-owner-harsh-the-golden-set.md` §10 |
| the before-score and the twelve findings it measured | `03-FINDINGS.md` §F.1, F38–F49 |
| the QA record | `baseline/yc2w27-qa/qa_record.txt` |
| the units | `tree.yaml`, block `yc2_w27` |
