# 08 · For Harsh — deploying the batch, and what to run after

**Written for:** Harsh. **As of:** 2026-10-12 (pushed through `7766a06a`: STEP-12 and STEP-13's first part — §1.14; STEP-14 → STEP-18 are being built and merged step by step — §0c lists what each asks of you). Before that: 2026-10-10 (pushed through `db6328cd` — your merge is in it; the alignment block `yc2_w27_align` came with the next push — §0b). **From:** the `yc2_w27` build (Claude), pushed by
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
   ⛔⛔ **2026-10-09 — your three commits of 9 Oct are merged into `speedrun008`** (`c50f0f7e`):
   `f4a71022`, `b5c6b064`, `649208f2` made `harsh/mvp` 3 ahead and 315 behind, so the deploy was no
   longer a fast-forward. The merge is textually clean; four tests then failed and were resolved in it
   (`03` F137) — read them before you build on these files: `_is_paste` now bounds a paste's length on
   BOTH sides (a headline that adds who acted, "Priya will share the signed PO by Thursday", is no
   paste; an identical one still is), `tests/test_screen_memory_batch_pg.py` follows your drop of the
   manager's own promise, `scripts/screen_flow_report.py` is declared to the who-is-us guard, and the
   statement pin is 3,033. Open for you: that script reads `GENIOS_DATABASE_URL` from `.env` itself,
   not through `scripts/_db.py`. Once Rohit pushes the merge, `harsh/mvp` is an ancestor of
   `speedrun008` again and §2's `--ff-only` works.
   ⛔ **CORRECTED 2026-10-06, for the NEXT push:** it carries STEP-02 (§1.4) and STEP-03 (§1.5), and
   with them **two migrations — `0191_reasoning_fingerprints` and `0192_attention_and_archive`** —
   the first since `0190`. `main.py` applies them at boot when the database is writable; check the
   boot log names both (§2).
   ⛔ **And STEP-04 (§1.6) adds a third, `0193_org_self_identities`** — the tenant's declared addresses
   and domains. After the deploy: **declare** the design partner's identity, then the **repair**, dry
   run first, its list to Rohit, `--apply` only after Rohit reads it (§3.4).
   ⛔ **And STEP-05 (§1.7) adds no migration** — every kept mail and calendar event enters memory, and
   every recovery is read again. The **first chain pass after the deploy is heavy** (§3.5); read its
   numbers (§4.3). Boardy's archived introductions are promoted only after Rohit reads the dry run
   (`06` D23).
   ⛔ **And STEP-06 (§1.8) adds a fourth, `0194_situation_outcomes`** — what came of every admitted
   situation. Nothing to run after the deploy; read two numbers before and a day after (§4.4).
   ⛔ **And STEP-07 (§1.9) adds a fifth, `0195_company_brief`** — the founder's company brief. Nothing
   changes until Rohit accepts a line. After the deploy: draft it, send the dry run to Rohit, apply Rohit's
   answers (§3.6), then the health check (§4.5).
   ⛔ **And STEP-09 (§1.10) adds no migration** — a file for every piece of work. Nothing moves until the
   brief names a connector or a watchlist domain. It also carries the fix for `03` F101 — the history
   replay after every backfill drain filed every newsletter the drain kept out — so **deploy it before
   STEP-08's re-sync** (§3.7). After Rohit accepts the brief: the health check, and re-file the history
   if it names anything (§3.8, §4.7).
   ⛔ **And STEP-10 (§1.11) adds no migration** — the expert's numbers. The published pack moves
   1.5.0 → 1.5.1 (registered at boot); the first sweep re-decides each subject whose numbers changed,
   once (§3.9). After one sweep: the health check — every normal says its n (§4.8).
   ⛔ **And STEP-11 (§1.12) adds a sixth, `0196_company_brief_line_kind`** — one nullable column: an
   in-motion line's kind of work. The new Founder Office corpus compiles for NO tenant until it is
   switched on: after the deploy switch it on for Rohit's org ONLY — the dry run must list one switch
   (§3.10) — and send Rohit the refusal count a day later (§4.9). No fundraising card appears before
   Rohit's review of the two playbooks (`06` D45).
   ⛔ **And STEP-12 (being built, 10 Oct) adds a seventh, `0197_expert_reviews`** — the expert's one
   review of a file per fingerprint. Nothing writes it until the expert pass is built and its feature
   (`expert_review`) is switched on, which it is for no tenant; `/reset` wipes it, so the boot log must
   name it. ⛔ **And an eighth and a ninth (11 Oct), `0198_expert_review_inputs` and
   `0199_expert_review_triggers`** — one nullable column on it each: what the file was when it was judged,
   so a later review can say what moved, and what triggered the review.
2. After the deploy, **re-queue the attachments** the `file_name` refusal dead-lettered (§3.1).
3. **Read the first `refetch_last_error`** that comes back (§3.2).
4. **Pin the Composio toolkits** — the one unit of this block that is yours (§3.3).
5. **Run the probes** and send the outputs; each bug is closed on its own probe (§4).
6. **Do not** switch `calibration_apply` on for anyone (§5).

The commits after `77aba10e` change CI, test docstrings and these docs only — the engine is the
same. `2e7aea5b` fixes the CI `test` job (§6); it reaches GitHub with Rohit's next push.

## 0b · The alignment block (`yc2_w27_align`, M34) — in the next push

Built 10 Oct, before STEP-12 (`10-BEFORE-STEP-12.md`). **No migration.** What changes in production,
and what you run or read:

| | What changes | You |
|---|---|---|
| the brief's kinds | a seventh kind of work, `vendor` (`06` D18); the drafter's prompt is v3, so the next draft is one new call | — |
| a file's quiet window | by its kind of work (`06` D33): investor and program files stay open 90 quiet days, the rest 45 | — |
| the re-sync | `--apply` refuses, freeing nothing, while the connection's window is shorter than `--days` (exit 2) | §3.7, step 2 before step 3 |
| two new health checks | *memory reaches back as far as the Gmail connection's window* — red until the re-sync reaches it; *every piece of work the brief names in motion has one file* — red while a named programme's mail stays archived (`03` F125, open) | read both after §3.7 and §3.8 |
| dates read late | new reads frame *"by Friday"* against the mail's own day (`03` F148); a promise for a window is due when the window closes (F149) | §3.8: `scripts/reframe_stored_dates.py`, dry run then `--apply`, then re-file |
| programmes | a programme's or a portal's file is never decided as an investor: `situation_outcomes` says `unsupported`, `misfiled_kind` | — |
| a file's history | each ending is placed on its own file and generation (`03` F113): `derived.history.prior_*` values move | — |
| the first-connect Sync | judged at one instant, like the sweep (no change on a live Sync, which passes none) | — |
| the provider watch | the first outage after a boot alerts (`03` F145) | — |
| probes | four more in `baseline/production_state.sql` (§4) | send their outputs |

## 0c · STEP-13 → STEP-18 — your list (12 Oct)

One table for everything these six steps ask of you. **Pushed** means on `origin/speedrun008`; **built** means on
the integration branch, crosschecked, and pushed after its QA; **being built** means the exact commands are added
here when the step lands. Nothing in this table switches anything on by itself.

| Step | State (12 Oct) | Migrations — the boot log must name each | You do | Front-end (`genios-dashboard`) |
|---|---|---|---|---|
| STEP-13, check every claim | first part **pushed** (`7766a06a`); the check's and the question's fixes from its crosscheck are merged and being re-recorded; next push | `0200_expert_review_checks` (one nullable column on `expert_reviews`: the check), `0201_founder_questions` (one table; `/reset` wipes it) | §1.14, §3.12, §4.10 — nothing runs until the expert is on (§3.11); wire the needs queue's fetchers when you can (§3.12) | the **question card** and its **Answer** box; each card sentence's **source**; the workstream page reads `says` and `check` (§1.14) |
| STEP-17, real tests | **built**, merged on the integration branch | none | CI gains a `database` job (Postgres 17) and every job runs Python **3.11**, the Dockerfile's; after each deploy keep the health gate's output (`scripts/pipeline_health.py … --json <release record>/health.json`) and run it again the next day with `--require-data` — STEP-17's follow-up adds the exact step to §2/§3 | — |
| STEP-18, the known bugs | **built**, merged on the integration branch | `0210_every_wrong_reason_is_kept`, `0211_a_followup_names_its_observation` | **before the deploy:** set `GENIOS_JWT_SECRET` in production (a non-dev boot with the default secret refuses to start, exit 3). If you also set `GENIOS_ENV` to a non-dev value: a rotated secret signs every user and paired desktop app out (they sign in again), and unsigned Composio webhooks get 403 unless `GENIOS_COMPOSIO_WEBHOOK_SECRET` is set — read `GET /config` first — and since `06` D62 an UNSET `GENIOS_ENV` counts as not dev too, so the image refuses to boot on a public secret until both are set (§3.14). **After:** the s18-F9 and s18-F3 probes and the backfill of review objects stuck at `governed`, dry run first (§4.11) | — |
| STEP-14, the card | **being built** | `0220_the_living_card`, `0221_the_gold_card` (planned) | read the board as the app showed it (s14-D4) | one **living card per file**: a card has versions, and its history shows them; a question card stays open after your answer (*"your answer is in; the file is read again"*, s14-D3); the headline is cut by code, the move whole under *recommended* |
| STEP-15, the morning brief | **being built** | `0230_morning_briefs` (planned) | at deploy, **set `orgs.timezone` for Rohit's org** (otherwise it is inferred from his send hours); a Slack tenant gets the brief as its digest | the **Today view** (Atlas A.10 has the wireframe) reads the brief's route at 08:00 in the org's timezone; e-mail and WhatsApp come later |
| STEP-16, learning from you | **being built** | `0241_founder_corrections`, `0242_company_brief_corrections` (planned; `0240` is not needed — STEP-18's `0210` already keeps every reason) | do **not** arm calibration (D13 stays shadow) | the card's *wrong* shows four groups and a words box; a question card can be called *wrong* (*"don't ask me this"*); your corrections show on the file |

## 0d · ⛔ Claude 5 thinks by default — R-2 is probably cut in production today (13 Oct)

**The defect** (STEP-18 §9; `06` D71). Claude Sonnet 5 thinks unless the request turns it off, and the
tokens it spends thinking count toward `max_tokens` with the answer. Every model site here was sized for a
model that does not think, and `context/llm/client.LLMClient` — the one client R-1, R-2 and deep analyze
use — sends no thinking control. On `harsh/mvp` the R-2 narrator (`l4_bundle`) runs `claude-sonnet-5` at a
2,400-token ceiling: its answer is ~450 tokens, and a call whose thinking fills the rest is cut, retried
once at the same ceiling, and ends as the template — two charged calls for no narrative. Measured on the
golden set on 12 Oct: the R-7 expert on Sonnet 5 at 4,000 was cut on **203 of 203** calls (R-7 is not
on `harsh/mvp`).

**1 · Rohit runs this first** — read-only, the four `@thinking_*` blocks of the probe file (§4):

```
PGOPTIONS='-c default_transaction_read_only=on' psql "$URL" -f "speedrun008/YC-II W27/baseline/production_state.sql"
```

| Block | Confirms the defect | Refutes it |
|---|---|---|
| `@thinking_lanes` | `l4_bundle` × `claude-sonnet-5`: ≥ 10% of calls at 2,400 (`failures_at_ceiling` + `parsed_but_cut`) | every call since 4 Oct under 2,400 — the patch then only saves ~40% of R-2's output spend |
| `@thinking_r_sites` | R-2 `failed_generation` with `every_attempt_at_ceiling` (2 attempts, 4,800 tokens) | none |
| `@thinking_sonnet_by_day` | the Sonnet 5 lanes still at a ceiling after 4 Oct | — |
| `@thinking_models_in_use` | a T1 lane on a model other than Haiku (an override: the shared client would then think there too) | Haiku plus the two Sonnet 5 lanes only |

The blocks read Rohit's org only (the probe file's rule); `@thinking_expert_after_deploy` and
`@thinking_brief_after_deploy` read tables that come with the speedrun008 deploy (`0195`, `0197`) and
error before it — run them after.

**2 · The hotfix for `harsh/mvp`** — one file and its test, nothing else:
`speedrun008/YC-II W27/baseline/thinking/harsh-mvp-r2-thinking-off.diff`. It sends
`thinking: {"type": "disabled"}` to `claude-sonnet-5` — its own id or a dated snapshot, never a longer id
(Opus 5.5 and Fable cannot turn thinking off; `disabled` is a 400 there) — from `context/llm/client.py`,
and adds two tests to `tests/context/test_sampling_is_omitted_where_it_is_refused.py`. Haiku's requests do
not change by a byte.

```
git switch harsh/mvp && git pull --ff-only
git apply --check "speedrun008/YC-II W27/baseline/thinking/harsh-mvp-r2-thinking-off.diff"   # from a speedrun008 checkout, or copy the file
git apply "speedrun008/YC-II W27/baseline/thinking/harsh-mvp-r2-thinking-off.diff"
.venv/bin/python -m pytest -q tests/context/test_sampling_is_omitted_where_it_is_refused.py tests/context/test_a_truncated_call_is_not_bad_json.py
git commit -am "R-2: Sonnet 5 asked with thinking off (STEP-18 §9 hotfix)" && git push   # then deploy as you do
```

Proved on an extract of `origin/harsh/mvp` @ `84f00a40` (never a checkout):
`bash 'speedrun008/YC-II W27/baseline/thinking/check-harsh-mvp-hotfix.sh'` — it applies, harsh/mvp's two
client test files pass (25), and so do its `tests/context` and the R-site gauntlet and doctrine tests.
A day after, `@thinking_lanes` should show `l4_bundle` with no call at 2,400.

**3 · The speedrun008 deploy carries the whole fix** (`yc2_w27_s18` M50): a thinking control per model
family in the shared client, OFF by default; every R-site asks with thinking off (R-7 at 6,000 with a 120 s
timeout); deep analyze, the brief drafter (4,000) and the four moment lanes the same; a cut answer is a
failure on every ledger; `scripts/pipeline_health.py` sees a cut that parsed and fails an expert day more
than half cut. No migration. ⛔ Once the hotfix is committed on `harsh/mvp`, `harsh/mvp` is one commit
ahead of `speedrun008` and §2's `--ff-only` refuses: the lead merges that commit back into `speedrun008`
first, taking `speedrun008`'s side in `context/llm/client.py` and the test file (its table already sends
Sonnet 5 `disabled`), so the deploy fast-forwards again.

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

### 1.9 · STEP-07, the company brief — in the next push

| | What changes at runtime |
|---|---|
| new tables | `company_brief_lines` (one row per line: proposed · accepted · rejected · removed, never deleted) and `company_brief_reviews` (one per tenant per ISO week) — migration `0195`. Both SURVIVE `/reset`: the brief is the founder's word |
| new routes | `GET /v1/company-brief`; `POST /v1/company-brief/lines`; `POST /v1/company-brief/proposals/{id}/decide`; `DELETE /v1/company-brief/lines/{id}` — every write the account OWNER's (`06` D27). The dashboard's screen is not built yet |
| every judging prompt | carries the brief — but only once a line is accepted. Until then every prompt is byte for byte what it was |
| the gate | a sender the brief names (a connector's address, a watchlist domain) is W-07 — kept, read deep, never archived by a noise rule or the AI filter |
| the heavy tick | a weekly review per tenant WITH an accepted brief: one Sonnet call (≈ $0.05), proposals only — `company_brief_review` in the sweep's result |
| new scripts | `scripts/draft_company_brief.py` (patterns / dry run / `--apply`), `scripts/company_brief.py` (show / accept / reject / remove / add) |
| a new health check | *the company brief exists and is current* — FAILS until Rohit accepts a line (expected) |

### 1.10 · STEP-09, a file for every piece of work — in the next push

| | What changes at runtime |
|---|---|
| no migration | nothing new is stored: a file is the correlation the drain already writes, read together |
| the L2 drain | reads the company brief once per pass (as it reads who is us). A connector the brief names is an introducer wherever it appears; the people its introduction goes to become people (`party.role introduced`, an `introduced` edge, their names), even under its unsubscribe header; each has a file of their own, and the reply it calls for is owed to them, never to the connector. A watched portal's notice is filed under the portal. **No accepted connector or watchlist line: byte for byte what it was** |
| the history replay | `context/backfill.backfill_correlations` (after every backfill drain, and every rebuild) no longer files what the drain called noise (`03` F101) — it did, since L3-0A |
| a new route | `GET /v1/workstreams` — read only, the tenant's files; anyone who may read the tenant (`get_current_org`) |
| a new health check | *every counterparty the brief names that has mail has a file* — fails while a named counterparty's read mail is filed nowhere, or a connector's introductions sit in the connector's file; names each |
| what does NOT change | no card is added for a file in a domain that is not active (`06` D2); no stage is derived (`STEP-11`) |

### 1.11 · STEP-10, the expert's numbers — in the next push

| | What changes at runtime |
|---|---|
| no migration | the pack `general_v1` registers as **1.5.1** — 1.5.0's published bytes are immutable, and the only change is the send-interval baseline's name (`write_interval`, `06` D41) |
| the waiting pass | their reply time is counted ONCE (person nodes only) and measured inside each conversation; a normal is written only at five replies, with its n (`party.reply_cadence_n`) — **every "usually replies in X days" that rested on fewer goes**; your own reply time is written per counterparty and overall at five; a counterparty whose latest mail from us bounced is no longer waited on |
| the gate and the connector | a delivery report is kept and read — never archived, never judged junk; its attached original is not landed as a document |
| the L2 drain | a failed report writes `delivery_failure` on the address and the original's thread, `delivery.status = failed` on the address |
| history | per (anchor, domain): `derived.history.<fact>@<domain>`; the per-anchor rows are closed, never deleted |
| coverage | the sync summary carries its source and finish, so per-signal coverage is written (`STEP-18` B5); a bundle merges it (`03` F102, fixed) |
| a new route | `GET /v1/workstreams/{file_id}` — one file, its timeline and its numbers; read only; the tenant's own (`get_current_org`) |
| a new health check | *every reply time written as a normal says its n, and none rests on fewer than five* — names the file |
| what does NOT change | no card is added: a bounce, a wave and a reply time reach no card until `STEP-14`; the reply-owed threshold stays two days (`06` D42) |

### 1.12 · STEP-11, founder playbooks — in the next push

| | What changes at runtime |
|---|---|
| migration `0196` | `company_brief_lines.kind` — one nullable text column, no check constraint: its six values (investor · program · compliance · hiring · intro · partner) are validated by `contracts/company_brief.WORK_KINDS`. A brief whose lines name no kind keeps its version (`cb-…`) byte for byte, so no fingerprint moves for it |
| a new corpus | `Domain Expertise/Founder Office Expertise/` — `default_on: false`: it compiles for NO tenant until it is switched on (§3.10). Two capabilities authored — investor relations, programmes — both `draft`, not reviewed |
| fundraising situations | read the Founder Office, no longer the Sales copy (retired — Sales' `10-investor-relations` folders are gone). A tenant WITHOUT the Founder Office: measured in shadow, as before. A tenant WITH it: the live compiler refuses the unreviewed capability — `unsupported_unreviewed` in the pass's counts, the end `unsupported · unreviewed` in `situation_outcomes` — **no decider call, no card**, until Rohit's review admits it |
| the decider's prompt | `l4-llm-decision.v6`: each corpus claim quoted whole by its id (it read `{"rule": null}` — `03` F121), framing blocks under their own heading, each play's steps whole and numbered |
| a compiled play | named by its playbook; carries the playbook's success signal, outcome window and review state (the `expertise` adapter 2.1.0). Every compiled manifest changes, so **the first sweep re-decides each compiled-lane subject once** — its decision count says how many. A legacy-lane subject is re-decided only when its own inputs move (`03` F134) |
| a card | a Founder Office card whose playbook is not reviewed leads its *why* with *"playbook not yet reviewed"* (`06` D3); no other card changes, and the card builder's version does not move |
| routes | `GET /v1/workstreams/{file_id}` carries `"playbook"` — the file's kind of work and what the corpus says about it, or the named reason it says nothing; the company-brief routes carry a line's `kind` |
| scripts | `scripts/company_brief.py … --kind`; `scripts/playbook_review_sheet.py` — Rohit's review, local files only, no database |
| what does NOT change | no new environment variable; Admin's cards; nothing for any tenant that has not switched the Founder Office on |

### 1.13 · STEP-12, the expert pass — in the next push

| | What changes at runtime |
|---|---|
| migrations `0197`–`0199` | `expert_reviews` — one row per file per fingerprint: the review, its status and reason, its cost, what its fingerprint read (`inputs`) and what triggered it (`triggers`). `/reset` wipes it |
| a new L4 feature, `expert_review` | off for every tenant (§3.11). Off: no file is reviewed, nothing is spent, every situation is decided as before |
| with it on — the pass | each file whose fingerprint moved and that something touched is reviewed ONCE by R-7 (Sonnet-class, `06` D7), nearest deadline or meeting first, ten a pass, **$2 a day** on the R-sites' ledger; an unchanged sweep asks nothing; a refusal is a row with its reason |
| with it on — the decision (`06` D1) | a file a VALID review covers gets ONE audited decision from it — no decider, no R-1 — and what the review explains stands down: the compiled lane's situations on the file and its people, the packs' rules on them (`covered_by_review` in the suppression log), the shadow native lane. The file keeps one decision — the same advice stands, other advice replaces it, a review that names no move clears its card (`rule_cleared`). Its card speaks the review's own words, no narrator |
| the decider's spend | ends on covered files: the decider is asked only about what no valid review explains |
| R-6 | retired (`06` D51) — it never ran in production |
| what does NOT change | no new environment variable; nothing for any tenant without the feature |

### 1.14 · STEP-13, check every claim — first part pushed (`7766a06a`), the rest in the next push

| | What changes at runtime |
|---|---|
| migrations `0200`, `0201` | `expert_reviews.checked` — what the check found on each review; `founder_questions` — the one open question a file asks the founder, and his answer. `/reset` wipes both |
| the check (only with `expert_review` on) | every review the expert writes is checked line by line before anything reaches a card: a fact's quote must be in the mail it cites, a number is the calculator's (a date or a timestamp is not a number), a name must be on its own lines, a draft never goes to us or to the connector who made the introduction, an ask we already answered is not raised again. A line that fails is dropped, not the review (`06` D59); a move whose ground fell becomes ONE question to the founder |
| the question card | builder `founder_question.v1`, lane `investigation`, level `review`: the headline is the question, the situation the file as the check let it stand; actions `answer` and `snooze`. **Answer:** `POST /cards/{id}/action` with `{"action": "answer", "words": "…"}` (up to 4,000 characters) — kept once on the file; the next review reads it. Errors: `answer_says_nothing`, `answer_too_long`, `not_offered` (`run_play`/`do_it_myself` on a question card), `not_a_question`, `V-09` (the question is no longer open). The card lives while its question is asked (renewed before its authority lapses), and a question already answered is never asked again in the same words. Today `GET /cards` and `GET /cards/{id}` show it; `/v1/insights` and the workspace feed still read only decision cards |
| a card's sources | an expert card's `why` now LEADS with one entry per sentence (`"source": "expert_check"`): the headline with the mails and asks it rests on and their quotes, the situation labelled *the expert's reading — an inference*, the draft with what it stands on, *what doing nothing costs* checked too — show them as "where this came from" |
| the workstream page | `GET /v1/workstreams/{id}` → `review.latest` / `review.valid` no longer carry the review's raw words: `says` is what the check let stand (the card words), `check` is the check (fate, why, the question, each line's verdict) |
| the lanes | every writer of signals and cards now writes `output_lane` and `lane_reason` (the team and verify cards included); a new health check counts the last day's signals with no lane |
| what does NOT change | no new environment variable; nothing for a tenant without `expert_review`. When it is switched on (§3.11) every file is reviewed once more under the new prompt (`expert-review.v3`): about 46 reviews a day inside the $2 day, so a 150-file tenant is fully covered in 3–4 days |

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
the reset now wipes `reasoning_fingerprints` — ⛔ and, from STEP-06, until `0194` is (it wipes
`situation_outcomes`). ⛔ **STEP-11 adds `0196_company_brief_line_kind.sql`** — one nullable column on
`company_brief_lines`; the brief's store and routes write it, so the boot log must name it too.
⛔ **STEP-12 adds `0197_expert_reviews.sql`** — one new table; `/reset` fails until it is applied (the
reset wipes `expert_reviews`) — ⛔ **and `0198_expert_review_inputs.sql` and
`0199_expert_review_triggers.sql`** (11 Oct): one nullable column on it each, which the review store
writes, so the boot log must name them too.
⛔ **All of them, in one line** (11 Oct — the latest is `0199`): `migrations applied at boot:
['0191_reasoning_fingerprints.sql', '0192_attention_and_archive.sql', '0193_org_self_identities.sql',
'0194_situation_outcomes.sql', '0195_company_brief.sql', '0196_company_brief_line_kind.sql',
'0197_expert_reviews.sql', '0198_expert_review_inputs.sql', '0199_expert_review_triggers.sql']` — nine
files; the deploy is not done until the boot log names each.
⛔ **STEP-13 (12 Oct) adds `0200_expert_review_checks.sql`** (one nullable column on `expert_reviews`, written by
the review store) **and `0201_founder_questions.sql`** (one table; `/reset` fails until it is applied) — the boot
log names eleven files from `0191`.
⛔ **STEP-18 (12 Oct) adds `0210_every_wrong_reason_is_kept.sql` and `0211_a_followup_names_its_observation.sql`** (both additive), and BEFORE the deploy needs `GENIOS_ENV` and a real `GENIOS_JWT_SECRET` in the deployment's environment, or the new image refuses to boot — §3.14.
No new environment variable. One value we need from the
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
    --address ceo@thegenios.com --address mrrohitswerashi@gmail.com --domain thegenios.com --by "06 D6" --database-url "$URL"
python scripts/declare_self_identity.py --org org_e97e86f858ad48b2bbf64b8a \
    --address ceo@thegenios.com --address mrrohitswerashi@gmail.com --domain thegenios.com --by "06 D6" --database-url "$URL" --apply

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
    --sender-domain boardy.ai --database-url "$URL"
# after Rohit says
python scripts/promote_archived.py --org org_e97e86f858ad48b2bbf64b8a --rule N-02 \
    --sender-domain boardy.ai --database-url "$URL" --apply
```

⛔ **CORRECTED 2026-10-07 (the STEP-08 check): `boardy.ai`, not `boardy.com`.** Boardy writes from
`boardy@boardy.ai` (`context/pipeline.py:472`, 254 threads in your graph; `api/routes.py:5022`), and
the promotion matches the sender domain exactly (`capture/landing/promote.py`), so `boardy.com`
would list nothing. ⛔ And it can only see what was **archived after the deploy**: the 31 intros the
old gate deleted are `dropped`, not archived, until `STEP-08` lands them again.

The next chain pass reads them. ⛔ Two meeting nodes production holds from before were filed at their
meetings' start (`03` F73): an edit made before such a meeting lands as history until the meeting
passes. Nothing to do unless a reschedule of one of them must show sooner.

### 3.6 · STEP-07 — draft the company brief; Rohit decides every line

Nothing changes until a line is accepted. In this order — every command on production needs
`GENIOS_ALLOW_PROD_WRITE=1` (`scripts/_db.py`), the reads too:

```
ORG=org_e97e86f858ad48b2bbf64b8a
# 1 · what the drafter will read — counts, names, domains, dates; no model, no message
python scripts/draft_company_brief.py --org $ORG --database-url "$URL" --patterns
# 2 · the dry run — ONE Sonnet call (≈ $0.05); every proposed line with what it rests on. Send it to Rohit.
python scripts/draft_company_brief.py --org $ORG --database-url "$URL"
# 3 · write the lines as PROPOSALS — nothing is accepted
python scripts/draft_company_brief.py --org $ORG --database-url "$URL" --apply
# 4 · Rohit decides; apply exactly what Rohit says
python scripts/company_brief.py --org $ORG --database-url "$URL" show
python scripts/company_brief.py --org $ORG --database-url "$URL" --by rohit accept <id> <id> …
python scripts/company_brief.py --org $ORG --database-url "$URL" --by rohit accept <id> --text "Rohit's own words"
python scripts/company_brief.py --org $ORG --database-url "$URL" --by rohit reject <id> …
python scripts/company_brief.py --org $ORG --database-url "$URL" --by rohit add watchlist "Startup India" --domain sampark.gov.in
```

Accepting a connector, key person or watchlist line promotes what the gate archived from that sender
(every archiving rule; a public mail host never). ⛔ So accepting Boardy's connector line
(`boardy@boardy.ai`) IS `06` D23's promotion — skip §3.5's command if Rohit accepts that line. Then
`STEP-08` (the re-sync), only after the brief is accepted (`06` D26).

### 3.7 · STEP-08 — the mail the old gate deleted comes back (after §3.6, never before)

**No migration.** The 258 Gmail messages the gate deleted before STEP-03 are ledger rows with no body;
listed again, each lands as a duplicate. The script frees their keys, the backfill drain lands them
through today's gate, and the finish takes the old rows out (`STEP-08` §8.6, §9). Gmail only. Nothing
the founder has is reset. Every command on production needs `GENIOS_ALLOW_PROD_WRITE=1`, the dry run
too (`scripts/_db.py`):

```
ORG=org_e97e86f858ad48b2bbf64b8a
# 1 · the dry run (read-only): how many, by rule, month and sender domain; the oldest and the
#     window that reaches it; the attachments. Send it to Rohit, who names the window (D5 / D16).
python scripts/resync_deleted_mail.py --org $ORG --database-url "$URL"
python scripts/resync_deleted_mail.py --org $ORG --database-url "$URL" --days 365   # what 365 reaches and leaves out
# 2 · the connection lists that far back
#     PATCH /connections/<gmail connection id>/backfill-window   {"days": <N>}
# 3 · free the keys — the rows stay `dropped`; one trace row each. It REFUSES, freeing nothing,
#     while the connection's window is shorter than --days (step 2 first)
python scripts/resync_deleted_mail.py --org $ORG --database-url "$URL" --apply --days <N>
# 4 · the legacy door — every message fetched in full. NEVER /integrations/gmail/sync (it keeps
#     rule-junk as a list snippet). Wait for "backfill drain done". ⛔ A TRUNCATED drain spent its page
#     budget (500 pages of `limit` messages); the door always starts from the newest page, so a plain
#     re-run walks the same pages and stops in the same place — re-run with a larger page instead:
#     POST /connections/<gmail connection id>/backfill?limit=100
#     POST /connections/<gmail connection id>/backfill
# 5 · supersede what came back; say why the rest did not
python scripts/resync_deleted_mail.py --org $ORG --database-url "$URL" --finish
```

`--finish` prints how many came back and how many were not listed — older than the connection's
window, or not listed by Gmail (deleted there, in Spam or Trash, or the drain has not reached it yet).
Run the drain again and `--finish` again until the second number stops moving; every step is
idempotent. A walk of any of them (`GET /events/{id}/journey`) names the event that replaced it.

⛔ The bodies of mail captured before the deploy carry the old 30-day expiry (`03` F21): what was
captured 3–5 Oct loses its body around **2–4 Nov**. Deploy before then; STEP-08 does not cover it.

⛔ **Only on a deploy that carries STEP-09** (`567049fc` or later). Step 4's backfill drain runs the
history replay over everything it brings back (`api/routes._replay_l2_history`), and before STEP-09 that
replay filed every newsletter, connector mailing and out-of-office the drain kept out (`03` F101).
Before the run, count what an earlier backfill drain already filed (read-only, §3.8's query).

### 3.8 · STEP-09 — after Rohit accepts the brief's connectors and watchlist

**First, the dates late reads stored (`03` F148, `yc2_w27_align` M34.C2).** Until this batch, a mail's "by
Friday" or "this week" was resolved against the day the sync READ it, not the day it was written, and the
first connect read 60 days of history at once — so every relative date in that history is off by the gap,
and a stored answer is reused as it is. The fix makes new reads right; this re-frames the stored ones.
Read-only first; the count goes to Rohit; then apply, and the re-filing below carries them into the graph
(re-file even if the brief named nothing new, when the count is not 0):

```
python scripts/reframe_stored_dates.py --org $ORG --database-url "$URL"            # counts by month, no words
python scripts/reframe_stored_dates.py --org $ORG --database-url "$URL" --apply    # names each event
```

**No migration, nothing to run until the brief names a connector or a watched domain.** Mail read
before the founder named them was filed the old way — an introduction under the connector, a portal's
notice nowhere — and the drain only files NEW mail the new way. The health check says whether history
needs re-filing (§4.7). If it names anything, re-file in this order — the graph first, because the
correlation rebuild re-derives every file from it, and the graph rebuild alone keeps the old files
(node ids are new; a thread rejoins its old file):

```
ORG=org_e97e86f858ad48b2bbf64b8a
# 1 · read every event again with the brief in force (dry by default; --apply backs up every graph
#     table first; no road calls a model — S18-X06 took its refusal away). ⛔ It has no
#     --database-url: it reads the application's own DATABASE_URL, so run it where the app runs
python -m scripts.rebuild_graph --org $ORG
python -m scripts.rebuild_graph --org $ORG --apply
# 2 · re-derive every file from the rebuilt graph
#     POST /api/org/$ORG/situations/backfill?rebuild=true
# 3 · the health check must pass (§4.7)
```

The count for STEP-08's note above, read-only — events the drain called noise that a replay filed:

```
select count(*) from source_events se
 where se.org_id = :org and se.outcome = 'emitted'
   and exists (select 1 from graph_observations o where o.org_id = se.org_id
                 and o.created_by_event_id = se.event_id and o.kind like 'email_noise:%')
   and exists (select 1 from context_correlation_members m where m.org_id = se.org_id
                 and m.event_id = se.event_id);
```

Not zero: the step-2 rebuild above re-derives every file without them.

### 3.9 · STEP-10 — the first sweep after the deploy

Nothing to run. **The first sweep re-decides once** each subject whose request changed — the n beside a
reply time, a normal that went, history per domain, the renamed metric — as a new company brief does
(the change gate, `STEP-02`); the decision count of that sweep says how many. Then the health check
(§4.8).

### 3.10 · STEP-11 — switch the Founder Office on for Rohit's org, and nothing else

Every command on production needs `GENIOS_ALLOW_PROD_WRITE=1` (`scripts/_db.py`), the reads too:

```
ORG=org_e97e86f858ad48b2bbf64b8a
# 1 · what is live now — read only
python scripts/activate_tenant.py --org $ORG --database-url "$URL" --status
# 2 · the dry run. It must list exactly ONE switch: `L3 founder_office` (its effect column is
#     blank — `03` F135). If it lists anything else — `L1 semantic` SPENDS a model call on every
#     message — stop and send the output to Rohit
python scripts/activate_tenant.py --org $ORG --database-url "$URL" --domains admin,founder_office \
    --by harsh --notes "06 D2: the founder's own work, Rohit's org only"
# 3 · the same with --apply
python scripts/activate_tenant.py --org $ORG --database-url "$URL" --domains admin,founder_office \
    --by harsh --notes "06 D2: the founder's own work, Rohit's org only" --apply
```

Switch it on for no other tenant (`06` D2). From the next sweep Rohit's fundraising situations are
refused `unreviewed` — counted, no model call, no card — until Rohit's review admits a playbook;
the count is §4.9's. Then each in-motion line of the brief gets its kind of work and ONE counterparty —
Rohit's call, applied by Rohit or by you on Rohit's word: a line already accepted gains a kind by
`remove`, then `add in_motion "<Rohit's words>" --domain <domain> --kind <kind> --by rohit`
(`scripts/company_brief.py`, as §3.6). The review itself is Rohit's and needs nothing from you: the
admitted corpus ships with a later push.

### 3.11 · STEP-12 — switch the expert on for Rohit's org, after the live pass

Only after Rohit's yes on the live golden pass (`06` D50 — `scripts/golden_eval.py --dry-run --site expert`
counts it: 97 expert calls, ≈ $2.08). Then, as §3.10, with `GENIOS_ALLOW_PROD_WRITE=1`:

```
python scripts/activate_tenant.py --org $ORG --database-url "$URL" --status
python scripts/activate_tenant.py --org $ORG --database-url "$URL" --features expert_review \
    --by harsh --notes "06 D1, D7: the expert decides Rohit's files"           # the dry run: ONE switch
python scripts/activate_tenant.py --org $ORG --database-url "$URL" --features expert_review \
    --by harsh --notes "06 D1, D7: the expert decides Rohit's files" --apply
```

Switch it on for no other tenant. A day later run the expert's health check
(`scripts/pipeline_health.py`, `check_the_expert_says_why_and_stays_in_budget`) and send the output.

### 3.12 · STEP-13 — after the deploy, and after the expert is on

1. Nothing to run at the deploy itself: the check and the question act only on files the expert covers, and the
   expert is on for no tenant until §3.11.
2. When §3.11 has switched the expert on for Rohit's org: the first sweeps review every file once more (§1.14).
   Read §4.10 a day later.
3. **The needs queue — yours when you can.** A file's unknowns land in `evidence_needs`; their reader runs every
   pass (`reason/domain_shadow.work_the_needs` → `capture/acquire/need_executor.run_needs`) and, with no connector
   wired, refuses and closes nothing (counted `needs_refused`) — `build_fetchers` returns `{}`. Wiring a fetcher
   (Gmail search, Calendar, the web) is the integration that lets a need be fetched instead of asked. A question to
   the founder never waits on it.
4. Known and open (a unit is planned): an Answer pressed at the very moment the sweep re-binds the same question can
   deadlock with it; PostgreSQL aborts one of the two and a second press succeeds.

### 3.13 · STEP-17 — keep the health gate's output, and read it again the next day

The last step of every deploy (`06` D69, STEP-17 S17-D3). `scripts/pipeline_health.py` has three
verdicts since STEP-17 (`yc2_w27_s17` M40.C3): **PASS**, **FAIL** and **NO DATA** — a check whose
population was empty in its window judged nothing, and says so instead of PASS (measured on a tenant
with no data: 17 of 19 checks used to print PASS). NO DATA is never a failure and never a pass: it is
counted apart in the last line, `N/M checks passed, K with no data, F failed`.

**1 · Right after the deploy** — the record of the release. Keep the file with the deploy's log; send
it to Rohit:

```
REL="$HOME/genios-releases/$(date +%F)-$(git rev-parse --short origin/harsh/mvp)"; mkdir -p "$REL"
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL" \
    --json "$REL/health.json"
```

Exit 0: nothing failed — NO DATA allowed, and on the deploy day expected for any lane that has not
run since the boot. Exit 1: a check FAILED — read its `fix:` line before the next deploy (`06` D69).
`--json` writes every verdict (name, verdict, measured, expected, fix, detail) to the file as pure
JSON, PASS and NO DATA included, so the `[db]` lines on stdout cannot spoil it (`03` F36).

**2 · The next day** — every lane should have run by now, so NO DATA is no longer an answer:

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL" \
    --json "$REL/health-next-day.json" --require-data
```

Exit 2: nothing failed, but a check still judged nothing. What that means: the lane it reads made no
call, wrote no row or saw no event in its window — an LLM lane that called in the last 7 days and
not in the window is named in the check's own line (`03` F24's shape: a silent lane once read as a
healthy one). Send Rohit the file and the names of the NO DATA checks; a silent lane is a finding,
not a pass. Exit 1: as above. Exit 0: every check judged something, and none failed.

Where a section above says a check *must pass*, NO DATA on the deploy day is not a breach of it; on
the next day's `--require-data` run it is.

### 3.14 · STEP-18 — before and after the deploy

STEP-18 (`yc2_w27_s18`, its 20 units and the crosscheck's follow-ups) ships two migrations and one
boot rule. §0c's row is the summary; these are the steps.

**⛔ Before the deploy — the boot refuses a public secret, and an unset `GENIOS_ENV` is not dev**
(STEP-18 B7, s18-F11; `06` D62, Rohit 12 Oct; the crosscheck's S18-X02, X03, X04). From this image
on, a boot refuses to start — before it migrates or starts a worker — when `GENIOS_ENV` is **unset**
or names anything but `dev`, `development`, `test` or `local`, **and** `GENIOS_JWT_SECRET` is empty,
the default the repository ships, or `.env.example`'s `change-me-in-prod`
(`platform/config.insecure_boot`; `main.py` raises, uvicorn exits 3, the reason is the last line of
the deploy log). Until D62 an unset `GENIOS_ENV` read `dev` and booted on the public key; it no longer
does.

1. Read what production says it is. `env` is the deployed `GENIOS_ENV` — and `dev` when it is
   **unset** (the setting's default), so `"dev"` here means *read the deployment's environment*:
   ```
   curl -s "$API/config"        # {"env": "...", "composio": "real", "database": "postgres", ...}
   ```
2. In the deployment's environment (DigitalOcean), read — do not print — whether `GENIOS_ENV`,
   `GENIOS_JWT_SECRET` and `GENIOS_COMPOSIO_WEBHOOK_SECRET` are set.
3. **If production does not set `GENIOS_ENV`, or sets it outside dev, the new image will not boot
   until `GENIOS_ENV` and a real `GENIOS_JWT_SECRET` are set.** Set them together, in one change,
   before the deploy, knowing what each does:
   * **A new `GENIOS_JWT_SECRET` signs every user and every paired desktop app out.** Every session
     and device token is signed and checked with it (`platform/sessions.py`, `platform/auth.py`,
     `platform/devices.py`), and the dashboard, the desktop app and the extension do not call
     `/auth/refresh` yet (`platform/config.py`): each signs in again, each desktop app pairs again.
     If production already carries a secret of its own, keep it — nobody signs out. If it carries
     the default (or none), schedule the rotation and tell Rohit and the design partner first.
   * **A `GENIOS_ENV` other than exactly `dev` turns every unsigned Composio webhook into a 403**
     unless `GENIOS_COMPOSIO_WEBHOOK_SECRET` is set (`api/routes.py`, the Composio webhook route:
     *"webhook secret not configured"*) — push ingestion stops; the scheduled sync still runs. Set
     the webhook secret (Composio's signing secret) in the same change. The environment's name also
     tags every analytics event and decides the device-verification fallback (`platform/analytics.py`,
     `api/device_routes.py`).
4. Send Rohit what `/config` said, which of the three were already set, and what you set.

**The boot log** names `0210_every_wrong_reason_is_kept.sql` (every wrong-because reason a card's
*wrong* offers is kept: one NAMED check per table on `card_feedback_verdicts` and
`card_feedback_revisions`) and `0211_a_followup_names_its_observation.sql` (one nullable column,
`screen_followups.observation_id`) — §2. Both are additive; the previous image runs on them.

**After the deploy** — the two probes and the one-off backfill, in that order: §4.11.

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
| — | `@latest_migration` | `0190` | ⛔ **corrected 2026-10-11:** `0199_expert_review_triggers` after the deploy (it said `0193` on 7 Oct, `0196` until STEP-12's migration, `0197` and `0198` on 11 Oct) |
| STEP-02 | `@cards_expired_while_deferred` | measured in STEP-01 only | **0** — a DEFER keeps its card |
| STEP-02 | `@gate_redecided_unchanged` | — (the gate is new) | `decided_today_never_skipped` small and falling; `skips` growing |
| `03` F148 | `@dates_framed_late`, `@promises_framed_late` | — | the count `scripts/reframe_stored_dates.py` re-frames (§3.8); 0 after it |

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

**Before the deploy:** the three read-only queries in `STEP-06` §8.6. They read only tables production
already has: expired cards with no event (15 in the 4 Oct audit), every active situation's latest
admission by type, and the parked drain's queue by owner.

**A day after:** the two scripts. Both read `situation_outcomes`, so neither runs before `0194` is
applied.

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
python scripts/situation_ends.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL" --verbose
```

*Every situation and every card says how it ended* should read **0 and 0**; the lines under it name
each live situation type that has no open card, with the histogram of its ends — informational
(`06` D25).

### 4.5 · STEP-07 — after Rohit accepts

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

*The company brief exists and is current* passes and names the version (`cb-…`), the proposals still
waiting, what the budget left out (should be none) and the last weekly review. Before Rohit accepts a
line it FAILS — that is the check doing its job, not a broken deploy.

### 4.6 · STEP-08 — after `--finish`

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

*Every Gmail message in the window has its content, or a stated reason* must read **0** — the window
is the Gmail connection's. Until STEP-08 has run it FAILS by design, naming how many and the oldest;
its lines say which were never freed (by the rule that deleted them) and which were freed and are not
back yet. Keep the dry run's, `--finish`'s and this output in `baseline/<date>-after-resync/`, with the
funnel probe.

### 4.7 · STEP-09 — after Rohit accepts the brief, and after any re-file

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

*Every counterparty the brief names that has mail has a file* must pass. Its measured line says how
many named counterparties have mail, how much of it is filed, how many files the tenant has, and — if
any — how many introductions sit in the connector's file. A failure names each counterparty; its fix
is §3.8. Keep the output, and `GET /v1/workstreams`'s, in `baseline/<date>-after-files/`.

### 4.8 · STEP-10 — after one sweep

```
python scripts/pipeline_health.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

*Every reply time written as a normal says its n, and none rests on fewer than five* must pass. A normal
with no n is one written before the deploy, and the waiting pass retires it on its sweep — run the check
again after one more; a normal below five written since is a defect (its fix names the two tests). Keep
the output, with `GET /v1/workstreams/{file_id}` for one investor's file and this read-only count of how
many normals the deploy took away and kept:

```
select f.field, count(*) filter (where f.valid_to is null) as current,
       count(*) filter (where f.valid_to is not null) as retired
  from graph_facts f
 where f.org_id = :org and f.field in ('party.reply_cadence_days', 'party.our_reply_days',
                                       'derived.our_reply_days')
 group by f.field;
```

### 4.9 · STEP-11 — a day after the switch (§3.10)

```
python scripts/activate_tenant.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL" --status
python scripts/unroutable_report.py --org org_e97e86f858ad48b2bbf64b8a --database-url "$URL"
```

`--status` must show `L3 founder_office LIVE`; the report's routing must read `fundraising →
founder_office` and name no dark domain but `general`. Then this read-only count — the
`unsupported · unreviewed` rows are the fundraising situations waiting for Rohit's review, the
pilot's fundraising count the cutover table asks for (`reason/cutover.py`, Harsh 26):

```
select o.outcome, o.reason, count(*) as situations, max(o.last_seen_at) as last_seen
  from situation_outcomes o
 where o.org_id = :org and o.last_seen_at > now() - interval '1 day'
 group by o.outcome, o.reason
 order by situations desc;
```

Zero `unsupported · unreviewed` rows after a sweep means the switch did not take, or the org has no
open fundraising situation — `--status` says which. Keep the outputs in `baseline/<date>-after-founder/`.

### 4.10 · STEP-13 — a day after the expert is on (§3.11, §3.12)

Read-only:

```
select state, count(*) from founder_questions where org_id = :org group by state order by state;
select output_lane, count(*) from cards where org_id = :org and created_at > now() - interval '1 day'
 group by output_lane order by count(*) desc;
select count(*) as signals_with_no_lane from signals
 where org_id = :org and created_at > now() - interval '1 day' and output_lane is null;          -- expect 0
select (checked->>'fate') as fate, count(*) from expert_reviews
 where org_id = :org and status = 'valid' and reviewed_at > now() - interval '1 day'
 group by 1 order by 2 desc;                                                                       -- shown / held / suppressed / refused
```

and `python scripts/pipeline_health.py --org $ORG --database-url "$URL"` — *every new signal has a lane* must PASS
(it says NO DATA on a day with no signal). Send all of it; the fates say how often a real model's claims are held.

### 4.11 · STEP-18 — after the deploy

Every command on production needs `GENIOS_ALLOW_PROD_WRITE=1` (`scripts/_db.py`), the dry run too.
The two probes are read-only (`PGOPTIONS='-c default_transaction_read_only=on' psql "$URL"`); send
both outputs to Rohit.

**0 · s18-F9 — the behaviour brain's published entries of THEIR reply latency** (read-only). B11
(`packs/brains/behavior_distill`, M49.C2.L-logic.V0.U03) stops publishing the counterparty's latency
as our behaviour; an entry published before stays active, and nothing retracts it:

```
select count(*) from learned_brain_entries
 where brain = 'behavior' and active
   and subject like 'behavior:relationship.response_latency_hours:%';
```

0 closes it. Anything else is STEP-16's retraction path — send the count; change nothing.

**1 · s18-F3 — each learning object's row against its own ledger** (read-only). Since B4
(`feedback/publisher._rest_for_review`) a NEW object the weekly sweep sends for review rests at
`human_review`; for every other sink the row still says `governed` while its latest transition says
otherwise — STEP-16's to mend, this is the count:

```
select lo.state as row_state, lt.to_state as ledger_state, count(*)
  from learning_objects lo
  left join lateral (select t.to_state from learning_transitions t
                      where t.org_id = lo.org_id and t.learning_id = lo.learning_id
                      order by t.occurred_at desc, (t.from_state is null) asc, t.id desc
                      limit 1) lt on true
 group by 1, 2 order by 3 desc;
```

**2 · The backfill beside it — a review object stuck at `governed` waits for review again**
(`scripts/rest_stuck_reviews.py`, `yc2_w27_s18` M48.C1.L-data.V1.U14; the crosscheck's S18-X09).
Objects sent for review before B4's fix stay at `governed`: never listed, and the review route answers
them 409. The probe's `governed` / `human_review` row is their count. Dry run first; send its output
(ids, one line each) to Rohit; `--apply` after he reads it:

```
GENIOS_ALLOW_PROD_WRITE=1 PGOPTIONS='-c default_transaction_read_only=on' \
    python scripts/rest_stuck_reviews.py --database-url "$URL"            # dry run: writes nothing
GENIOS_ALLOW_PROD_WRITE=1 python scripts/rest_stuck_reviews.py --database-url "$URL" --apply
```

It moves exactly the rows whose state is `governed` and whose latest transition goes to
`human_review`, in one transaction, and writes no transition (the ledger already holds that edge).
Run the probe again after: the `governed` / `human_review` row reads 0.

## 5 · Do not

- switch **`calibration_apply`** on for any tenant. It is Rohit's decision (`06` D13), and not
  before `STEP-18` B22–B24: armed, an applied mute or nudge hides every open card of its pack;
- run the re-queue before the deploy;
- fix anything new silently — a finding goes to `03-FINDINGS.md` §E, a bug to `STEP-18`;
- accept, add or remove a line of the company brief that Rohit did not say — the brief steers every
  judgment the engine makes (`06` D27);
- run STEP-08's `--apply` before Rohit has named the window (D5 / D16) and accepted the brief (D26), or
  drain the re-sync through `/integrations/gmail/sync` instead of `/connections/{id}/backfill`;
- switch the Founder Office on for any tenant but Rohit's (`06` D2), or `--apply` an activation whose dry
  run lists more than `L3 founder_office`;
- mark a playbook reviewed, or run `scripts/playbook_review_sheet.py apply`, on anyone's word but Rohit's
  line-by-line review (`06` D45);
- answer a founder question (`POST /cards/{id}/action`, `answer`) on Rohit's behalf, or from a script — the answer
  is read by the expert as Rohit's own words (STEP-13).

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
