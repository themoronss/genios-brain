# 08 · For Harsh — deploying the batch, and what to run after

**Written for:** Harsh. **As of:** 2026-10-07. **From:** the `yc2_w27` build (Claude), pushed by
Rohit. Everything here can be checked against the repository; every number below names the file
or the command it came from.

---

## 0 · In one screen

1. **Deploy `speedrun008`**, at `77aba10e` or later. `origin/harsh/mvp` (`2c42722d`, 4 Oct) is
   **75 commits behind it and 0 ahead** — it fast-forwards, no merge, no conflict. **No migration**:
   the newest is still `0190`, which production has.
   ⛔ **CORRECTED 2026-10-07, for the NEXT push:** measured after `git fetch origin`, `origin/harsh/mvp`
   (still `2c42722d`) is **189 commits behind** `speedrun008` (`7b2a91f2`) and 0 ahead — still a
   fast-forward.
   ⛔ **CORRECTED 2026-10-06, for the NEXT push:** it carries STEP-02 (§1.4) and STEP-03 (§1.5), and
   with them **two migrations — `0191_reasoning_fingerprints` and `0192_attention_and_archive`** —
   the first since `0190`. `main.py` applies them at boot when the database is writable; check the
   boot log names both (§2).
   ⛔ **And STEP-04 (§1.6) adds a third, `0193_org_self_identities`** — the tenant's declared addresses
   and domains. After the deploy: **declare** the design partner's identity, then the **repair**, dry
   run first, its list to Rohit, `--apply` only after he reads it (§3.4).
   ⛔ **And STEP-05 (§1.7) adds no migration** — every kept mail and calendar event enters memory, and
   every recovery is read again. The **first chain pass after the deploy is heavy** (§3.5); read its
   numbers (§4.3). Boardy's archived introductions are promoted only after Rohit reads the dry run
   (`06` D23).
   ⛔ **And STEP-06 (§1.8) adds a fourth, `0194_situation_outcomes`** — what came of every admitted
   situation. Nothing to run after the deploy; read two numbers before and a day after (§4.4).
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

### 1.5 · STEP-03, the gate keeps everything — in the next push

| | What changes at runtime |
|---|---|
| the gate | a mail a noise rule (N-01…N-10) or the AI filter's confident junk (`llm_junk`) used to **drop** is now **archived** — outcome `archived`, its encrypted payload kept 180 days, **no prepared text**, read by no model. Only S0 `out_of_scope` still drops, and no caller passes it |
| every row | `source_events.attention` (`deep` · `skim` · `archive`) and `attention_reason` — the rule that archived it, or what let it through. Rows from before the deploy stay null |
| payload TTL | an **emitted** mail's body is kept 180 days, not 30 — `_pull` inner-joins it, so a 30-day body stranded any event not drained in a month. More `raw_payloads` rows, all encrypted |
| the sync | `SyncSummary.archived`, `l1_sync_runs.archived`, `/ingest/all` totals carry `archived` |
| the drain | an archived `llm_junk` mail is re-admitted on the heartbeat exactly as a dropped one was (`03` F55, unchanged on purpose); its tier becomes `deep`, `readmitted:llm_junk` |
| a new receipt | *every archived mail can still be read* — `/readiness` shows it |
| a new health check | `scripts/pipeline_health.py` — *nothing captured was deleted at the gate* |
| a new outcome value | a gate verb the pipeline does not know now **raises** (the sweep quarantines that object) instead of being emitted |

What the founder sees does not change: on the golden set every case is marked exactly as before.

### 1.6 · STEP-04, who is us — in the next push

| | What changes at runtime |
|---|---|
| one answer | every module that asks "is this address, person or company one of us?" asks `platform/self_identity.identity_for` — the active seats, `orgs.email`, the connected accounts, and what the tenant **declared** (new table `org_self_identities`, migration `0193`). Twenty places used to decide it on their own (`03` F59) |
| `ceo@thegenios.com` | once declared: a **person**, never a `service`; never on a "waiting longest" line; never a card's subject |
| `thegenios.com` | once declared: our company in every event — never an anchor, never a deal, never "an outside company" |
| a Gmail founder | gmail.com is **never** ours as a domain — an investor writing from Gmail is an outside person (the support lane counted every Gmail sender as a colleague) |
| threads | a new thread is named after its **other** side — never "Mr Rohit Swerashi — <the pitch>". Old labels stay until the repair renames them |
| cards | a card whose subject is one of us is **refused** — counted per pass as `refused_subject_is_us`, logged, never built; an investor's "Rohit, can you send…" is carded about the investor |
| a new receipt | *no open card's subject is one of us* — `/readiness` shows it; it reads **red until the repair** has run |
| a new health check | `scripts/pipeline_health.py` — *we are never a card's subject or a thread's name* (0 and 0, after the repair) |
| `/reset` | keeps the declarations (they are who the tenant is, like the seats) |
| two scripts | `scripts/declare_self_identity.py` (declares), `scripts/repair_self_identity.py` (removes what was built before — dry run by default) |

⛔ **Domains are declared, never inferred.** The support lane, the deal backfill and engagement used to
take our domain from `orgs.email` or the seats — which is how gmail.com became ours. Now a domain is
ours only when declared. **Any other live tenant whose people share a company domain must declare
it** (`03` F62), or that company reads as a counterparty in those three places.

### 1.7 · STEP-05, every kept item enters memory — in the next push

| | What changes at runtime |
|---|---|
| the drain (`context/runner`) | takes every kept event with a road into memory, not only those with a live signal: a mail **below the floor** with its own L1 extraction (no model call; every claim ranked under the floor); an **archived** mail as names and dates only — who wrote to whom, their companies, the thread — read from the ledger's columns, its payload never decrypted, no thread state, no correlation (`committed_metadata`); every **calendar** event as a meeting, whatever its signal |
| meetings | keep their organizer; their facts are filed at the calendar's own edit time, so the newest edit wins; a colleague at a declared domain never anchors one |
| recoveries | every kept mail nothing read — a park the drain re-admitted, a manual recover, a refetch, a recapture, a promotion — joins the re-read ladder (`extraction_never_ran` in `parked_events`) and is read through the capture door on the next chain pass, up to **200 a pass, each one L1 extraction**, under the daily LLM cap. The gate whitelists a re-read (`W-06`) and never judges it out again |
| billing | a metadata write is **not** billed; a mail below the floor **is** (Layer 1's model read it) — expect one larger `message_read` row on the first pass |
| the progress bar | `_pending_count` counts exactly what the drain will take |
| a new receipt | *every kept event has entered memory* — may read red for the first day, until the drain and the ladder catch up |
| a new health check | `scripts/pipeline_health.py` — *every kept event entered memory, every calendar event is a meeting*, split by cause, with the ladder's backlog |
| promotion | `scripts/promote_archived.py` — dry run by default; nothing is promoted until Rohit says (`06` D23) |

### 1.8 · STEP-06, nothing is lost silently — in the next push

| | What changes at runtime |
|---|---|
| card expiry | every place that expires a card goes through `platform/card_lifecycle`, which writes one `card_events` row per card saying why (`replaced`, `rule_cleared`, `budget_held`, `not_authorized`, `plan_gone`, `rule_muted`; the lapse keeps `window.lapsed` / `expired`, the extension's dismiss `card.dismissed`, the repair `card.retired`). Expect a `card.expired` row wherever a card used to vanish |
| History | a card's last line now shows `card.expired`, `card.resolved` and `card.retired` with their cause |
| new table | `situation_outcomes` (migration `0194`): one row per admitted situation candidate, written once after each compiled pass — `decided`, or the stop and its reason. Wiped by the tenant reset |
| the drains | the parked drain's 200 are now only rows it can re-admit (the rest counted); the re-read ladder's 200 are only rows that are due |
| the journey | `GET /events/{id}/journey` gains `memory` and `end` — one end per event |
| two receipts | *every expired card says why* (cards created since `0194`) · *every admitted situation has a recorded end* |
| a new health check | `scripts/pipeline_health.py` — *every situation and every card says how it ended*, with each live situation type that has no open card shown with its histogram |
| a new script | `scripts/situation_ends.py --org …` — how every situation ended, per type (read-only) |

### 1.3 · How it was tested before the push

`baseline/yc2w27-qa/qa_record.txt`, at `83dd87f3`, every check on an **empty** scratch Postgres 17:

| | Result |
|---|---|
| every unit's own verify, block `yc2_w27` | 55 pass / 1 fail / 0 skip — the fail is your unit, §3.3, not written yet |
| the whole suite, with the database and without it | exit 0 — first fully green database run on this branch was `e151a7db`: 16,736 passed, 0 failed |
| the golden set (`golden-pg`, as CI runs it) | 357 passed, 100 xfailed, 0 skipped |
| on GitHub, the first push | `golden-pg` ✅ passed (run `37407196202`, Python 3.12, Postgres 17); `test` — see §6 |
| ⛔ STEP-04, in the next push (`baseline/yc2w27-s04-qa/qa_record.txt`) | units 48 / 0 / 0; the database suite 17,696 passed, 0 failed; the golden set 520 passed, 103 xfailed, 0 skipped, the board matches; the hermetic job 16,259 passed, 0 failed (run 2 — run 1 was red on one gate test, fixed in `78d7b4fd`) |
| ⛔ STEP-05, in the next push (`baseline/yc2w27-s05-qa/qa_record.txt`, at `4909f718`) | units 23 / 0 / 0; the database suite 17,843 passed, 0 failed; the golden set 584 passed, 87 xfailed, 0 skipped, the board matches; the hermetic job 16,300 passed, 0 failed — green on the first run |
| ⛔ STEP-06, in the next push (`baseline/yc2w27-s06-qa/qa_record.txt`, at `d2146f4f`) | `baseline/yc2w27-s06-qa/qa_record.txt` — run 1 at `d2146f4f`, green on every tier, a database created for every check: the units 28 / 0 / 0 (4 tree checks + 24 units; 1 retired); the whole database suite 17,989 passed, 0 failed (the same four optional skips, re-listed with their reasons); the golden lane 631 passed, 87 xfailed, 0 skipped; the board matches, unchanged (must-detect 11/32, must-abstain 11/12, Atlas 4/80); 0 golden tenants left; the hermetic job 16,339 passed, 1,388 skipped (the database tests, run in tier 2), 279 deselected, 72 xfailed in 763.88s (0:12:43). |

## 2 · Deploy

Production runs `harsh/mvp`. Either deploy `speedrun008` directly, or fast-forward your branch:

```
git fetch origin
git checkout harsh/mvp && git merge --ff-only origin/speedrun008    # 75 commits then; after the next push count them: git rev-list --count origin/harsh/mvp..origin/speedrun008
git push origin harsh/mvp
```

No migration in the push of `77aba10e`. ⛔ **The next push carries `0191` and `0192`**: `main.py`
applies pending migrations at boot, and the boot log says
`migrations applied at boot: ['0191_reasoning_fingerprints.sql', '0192_attention_and_archive.sql']`.
`0192` adds two nullable columns to `source_events`, a check on one of them, a column comment, and
`l1_sync_runs.archived integer not null default 0` — no rewrite, no index. The new capture code
writes the new columns, so it must not serve on a schema without `0192`; a migration that fails
crashes the boot (fail fast) rather than serving broken SQL.
⛔ **STEP-04 adds `0193_org_self_identities`** — one table, a primary key, two checks (`kind` is
`address` or `domain`; a value is trimmed, lowercased, non-empty), `on delete cascade` from `orgs`.
Every module that asks "is this us?" reads it through `platform/self_identity.identity_for`, the L2
drain included — so, like `0192`, the new code must not serve without it: the boot log must name
`0193_org_self_identities.sql` — ⛔ and, from STEP-06, `0194_situation_outcomes.sql` (the compiled
lane writes it after every pass; a degraded boot without it costs the record, never the pass, but
the receipt reads red). `0193` starts empty: until §3.4 declares, who is us is the seats,
`orgs.email` and the connected accounts — `ceo@thegenios.com` and `thegenios.com` become ours from
the declaration on.
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
  ⛔ **CORRECTED 2026-10-07:** not only `--apply`. `scripts/_db.resolve_database_url` refuses a
  production host without the flag whatever the script does next, so the **dry runs** here and in
  §3.4–§3.5, and the read-only `scripts/pipeline_health.py`, need it too. A dry run writes nothing
  with it set; `pipeline_health` reads through `scripts/_gate.read_only_connection`.

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

### 3.4 · STEP-04 — declare who the design partner is, then repair, in this order

`06` D6 (Rohit, 2026-10-05) and D14. `0193` must be applied (the boot log names it).

```
# 1 · declare — dry run, then the same with --apply
python scripts/declare_self_identity.py --org org_e97e86f858ad48b2bbf64b8a \
    --address ceo@thegenios.com --domain thegenios.com --by "06 D6" --database-url "$URL"
python scripts/declare_self_identity.py --org org_e97e86f858ad48b2bbf64b8a \
    --address ceo@thegenios.com --domain thegenios.com --by "06 D6" --database-url "$URL" --apply

# 2 · the repair — DRY RUN ONLY. Send its whole output to Rohit.
python scripts/repair_self_identity.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

The dry run lists the threads it would rename, the open signals and cards about us it would retire,
and the situations anchored on us (listed only — the correlation rebuild re-derives them). **Rohit
reads the list (D14).** Only then:

```
python scripts/repair_self_identity.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL" --apply
```

Every card it retires writes a `card_events` row (`card.retired`, cause `subject_is_us`), so it can be
audited and rebuilt. A second run writes nothing.

### 3.5 · STEP-05 — the first pass, and Boardy's introductions

**No migration.** Watch the **first chain pass** after the deploy: every archive (metadata), every mail
below the floor and every calendar event drains at once — hundreds of L2 runs, serial under the
graph-version lock. In the log: `stage=l2.process_pending … processed=<n>`. Then the re-read ladder
reads what recoveries left, up to 200 a pass.

Boardy's introductions stay archived until Rohit has read the list (`06` D23):

```
# DRY RUN ONLY — send its output to Rohit (event ids, dates, sender domains; never a body)
python scripts/promote_archived.py --org org_e97e86f858ad48b2bbf64b8a --rule N-02 \
    --sender-domain boardy.com --database-url "$URL"
# after Rohit says
python scripts/promote_archived.py --org org_e97e86f858ad48b2bbf64b8a --rule N-02 \
    --sender-domain boardy.com --database-url "$URL" --apply
```

The next chain pass reads them. ⛔ Two meeting nodes production holds from before were filed at their
meetings' start (`03` F73): an edit made before such a meeting lands as history until the meeting
passes. Nothing to do unless a reschedule of one of them must show sooner.

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
| — | `@latest_migration` | `0190` | `0190` — ⛔ **corrected 2026-10-07:** after the NEXT push's deploy, `0193_org_self_identities` |

Two that are not in the file:

```
select max(evaluation_time), count(*) from calibration_runs;                                     -- B1: runs again after the next heavy tick
select count(*) from event_trace where reason_code = 'seen_on_screen';                           -- B20: after a reconnect, against events that no longer exist
```

### 4.1 · STEP-03 — after the deploy, after the first sync

```
-- the gate's verdicts since the deploy, by tier and rule — `archived` appears, `dropped` does not
select outcome, attention, attention_reason, count(*) from source_events
 where org_id = 'org_e97e86f858ad48b2bbf64b8a' and captured_at > '<deploy instant>'
 group by 1, 2, 3 order by 4 desc;
-- STEP-03's number: 0
select count(*) from source_events
 where org_id = 'org_e97e86f858ad48b2bbf64b8a' and captured_at > '<deploy instant>' and outcome = 'dropped';
```

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

*Nothing captured was deleted at the gate* must pass. ⛔ **On the deploy day** its window starts at the
tenant's first archived mail: until one noise mail has been archived, mail the old gate dropped in
the previous 24 hours fails it, and the fix it prints asks whether STEP-03 is deployed. Run it after
the first sync. `scripts/workstream_funnel.py` reads `attention_reason` — run it only after `0192`.

### 4.2 · STEP-04 — after the declaration and the repair

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

*We are never a card's subject or a thread's name* must read **0 and 0**, and `/readiness` must show
*no open card's subject is one of us* green. Before the repair both are red by design — they are
counting what the repair removes. The read-only SQL behind them is `STEP-04` §8.6.

### 4.3 · STEP-05 — a day after the deploy

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

*Every kept event entered memory, every calendar event is a meeting* should read **0 and 0**; if not,
its split names what holds each one (never taken by the drain · an L2 run held, failed or parked ·
waiting for its re-read · given up by the ladder · never read and not in the ladder). The two numbers
STEP-05 moves, read-only (`STEP-05` §8.6):

```
-- kept events with an L2 run, share (was ~7%; target ≥ 95%)
select count(*) filter (where r.event_id is not null)::float / nullif(count(*), 0)
  from source_events se left join l2_processing_runs r on r.org_id = se.org_id and r.event_id = se.event_id
 where se.org_id = 'org_e97e86f858ad48b2bbf64b8a' and se.outcome in ('emitted', 'archived');
-- meeting nodes vs calendar events (was 2 of 34; target equal)
select (select count(*) from graph_nodes where org_id = 'org_e97e86f858ad48b2bbf64b8a' and node_type = 'meeting' and valid_to is null),
       (select count(distinct source_object_id) from source_events where org_id = 'org_e97e86f858ad48b2bbf64b8a' and source = 'gcal');
```

### 4.4 · STEP-06 — before the deploy and a day after

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
python scripts/situation_ends.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL" --verbose
```

*Every situation and every card says how it ended* should read **0 and 0** a day after; the lines under
it name each live situation type that has no open card, with the histogram of its ends — informational
(`06` D25). The read-only SQL behind the two numbers is `STEP-06` §8.6.

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
| the QA record | `baseline/yc2w27-qa/qa_record.txt` (STEP-00/01), `baseline/yc2w27-s02-qa/`, `baseline/yc2w27-s03-qa/` |
| the units | `tree.yaml`, block `yc2_w27` |
