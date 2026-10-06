# STEP-02 · PENDING — owner: Rohit (push, batched) and Harsh (deploy, with migration 0191) · the change gate — no new evidence, no new decision

**Owner:** Claude. **Depends on:** `STEP-00` (one branch). **Decision:** `06` D11 (recommended: keep
the current decider, behind this gate). **Moves:** `l4_llm_decision` + `l4_llm_r1` **~1,400 calls a
day → under 100**; cards stop appearing and vanishing; a DEFER stops expiring a card.

---

⚠️ **Re-checked against the code on 2026-10-06, claim by claim, and measured on the golden runner**
(§8). Every claim in §1 holds; three of the seven units in §3 would have broken something as
drafted. **What will be built is §8.3** — tree block `yc2_w27_s02`, 12 units, proposed and
awaiting Rohit's go.

✅ **Everything that is Claude's is done** — 2026-10-06, on Rohit's go (*"Haan, ab step 2 start
karo"*), tree `yc2_w27_s02`, 13 units, each red before and green after, and the whole QA tier green
at `aaca7e67` (§9): on all 40 founder cases a sweep that brings nothing new now makes **0 decider and
0 R-1 calls** — F29 made 12 — with the same cards and every verdict unchanged.

⏳ **What is left, and whose:** **Rohit** — push the batch (`06` D10). **Harsh** — deploy; it carries
migration `0191`, applied at boot when the database is writable (§9.5). Then the production number:
`@model_calls_by_day` before and after.

---

## 1 · What is true now

| | Evidence |
|---|---|
| One new event re-reasons **every** node and situation in the org | `[CODE]` `api/routes.py:947-950`; `reason/runner.py:856-910`. `process_pending` knows which nodes it touched (`context/runner.py:534, 559`) and returns only their count (`:1556`) |
| No unchanged-check runs **before** a model is paid | `[CODE]` `no_new_evidence` runs after reasoning (`reason/runner.py:1190-1212`) and rarely fires: derived and waiting facts are rewritten every drain with `occurred_at = now` (`context/derived.py:145-161`, `context/waiting.py:348-353`). The only pre-reasoning check is the deal composite (`reason/composer.py:265-270`) |
| Every key moves every sweep | `[CODE]` `input_hash`, `context_snapshot_id`, `idempotency_key` all include `evaluation_time` (`reason/store.py:785-802`, `contracts/reasoning.py:479-496, 779-786`, `reason/audit.py:211-215`); the decider's and R-1's caches are in-process and keyed on it → never hit across sweeps |
| Shadow runs pay for discarded decisions | `[CODE]` `reason/orchestrator.py:252-263` has no mode check; `reason/domain_shadow.py:1178-1193` reasons shadow rows, then `continue`s `[inference]` |
| A DEFER expires the card | `[CODE]` DEFER is not in the indeterminate set (`reason/runner.py:1116-1125`) → suppressed as `shadow` (`:1168-1175`) → the lifecycle pass resolves the signal and expires the card (`:1382-1410`) |
| What it costs | `[PROD]` 874 + 528 calls a day; one legacy rule flips 113 decisions / 118 DEFERs on unchanged evidence |

## 2 · Why first

It is the cheapest visible win and depends on nothing else. It also hands nothing to a formula:
the current model-based decider keeps deciding — it just stops re-deciding what has not changed.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | **the material fingerprint** | new `reason/fingerprint.py` | a hash of what a decision may depend on: the situation's correlation member event ids (`context/situation_bso.py:195-199`); its **non-derived** `fact_version_id`s (`derivation_type != 'deterministic_derived'`); status, type, anchor; L1 conflict ids; open-loop counts (`reason/runner.py:902-904`); new human verdicts (`card_events`, `card_feedback_verdicts`); **bucketed clocks** — days waiting and days to a deadline in the timeline unit's ladder (`reason/reasoners/timeline_unit.py:89-96`); pack version. **Never** `evaluation_time`, `graph_version`, or the `occurred_at` of a derived fact. Sorted before hashing — `3f8d51e0` is why |
| 3.2 | the store | migration `0191_reasoning_fingerprints.sql` | `(org_id, subject_key, fingerprint, run_id, decided_at)`; `subject_key` = `situation_id` (compiled lane) or `rule_id:node_id` (legacy). The chain of runs uses the existing, never-written `reasoning_runs.supersedes_run_id` |
| 3.3 | the gate, compiled lane | `reason/domain_shadow.py`, between admission (`:1054`) and `reason_native_capability` (`:1178`) | same fingerprint **and** a standing open signal (the query at `:306-313`) → skip: zero calls, an `unchanged` receipt. Re-review is forced before `authority_expires_at` (`reason/authority.py:264`, default 168 h) so a still-true card is renewed, not lost |
| 3.4 | the gate, legacy lane | `reason/runner.py` | move the `no_new_evidence` test ahead of `reason_legacy_rule` (`:1057`); make `_newest_evidence_at` (`:263-279`) ignore clock-rewritten facts; keep the `fired.add` |
| 3.5 | no model for shadow | `reason/orchestrator.py:252-263`, `reason/decision_maker.py:1119-1126` | call R-1 and the decider only when `request.mode == LIVE` and the capability has `live_delivery_enabled` |
| 3.6 | a DEFER keeps the card | `reason/runner.py:1116-1125` | `llm_decision_unavailable:*` and a model DEFER join the indeterminate set; the lifecycle pass no longer expires on them |
| 3.7 | the counter and the check | `platform/funnel.py`; `scripts/pipeline_health.py` | `reasoning_skipped_unchanged` per sweep; a health check that fails when a subject is re-decided without a fingerprint change |

## 4 · What will happen

| When | Today | After |
|---|---|---|
| 10:00 sweep — Maria's thread, no new mail since 3 Oct | the decider is asked again; DEFER or DECISION by chance; on DEFER the card expires | fingerprint unchanged → **no call**; the card stands |
| 10:15 — a new mail from Maria | asked again (as every sweep) | the member event ids changed → **one** call → the card updates |
| Theresa's wait crosses from 6 to 7 days | asked again every 15 minutes regardless | the days-waiting bucket changed → one call |
| The model is down or over its cap | DEFER → the card expires | indeterminate → the card stands |

## 5 · Expected

| Measure | Before | After |
|---|---|---|
| `l4_llm_decision` + `l4_llm_r1` calls a day | ~1,400 | **< 100** — roughly *situations with new evidence that day × 1.3* `[MODELLED]` |
| A subject flipping decision ↔ DEFER on unchanged evidence | daily | **0** |
| Cards expired by a DEFER | measured in `STEP-01` | **0** |
| Model spend a day, this org | ~$7 | ~$3 *(the decider and R-1 were ~$4 of it)* |

## 6 · Verify

```
.venv/bin/python -m pytest tests/reason/test_material_fingerprint.py -q
#   stable under row order; stable when only evaluation_time moves; stable across two sweeps
#   15 minutes apart with no new event; changes when a member event is added, a non-derived
#   fact version changes, a bucket boundary is crossed, or a verdict lands — each by mutation
.venv/bin/python -m pytest tests/replays -q          # the founder case "unchanged sweep → zero calls"
# production, read-only, the day before and the day after deploy:
#   select purpose, count(*) from llm_costs where org_id = :o
#     and created_at > now() - interval '1 day' group by 1;
```

## 7 · Risks

| Risk | Guard |
|---|---|
| The fingerprint misses an input that matters → a stale card | forced re-review before authority expiry; human verdicts and clock buckets are inputs; one mutation test per input |
| The fingerprint carries an input that moves every sweep → no saving | the two-sweeps-no-events test, and the health check in 3.7 |
| Shadow lanes stop producing receipts someone reads | they still write the run; only the model call is skipped |

## 8 · The check of 2026-10-06 — what the first draft got right, and wrong

Every claim was re-read against `speedrun008` @ `56528ddb` (the cited lines in `reason/runner.py`
have moved; the rest still match), and the chain was run on the golden runner with the ideal
reader — no spend.

### 8.1 · Measured

**On the golden runner** — each case run once more, 15 minutes after its last sweep, with nothing
new (`tests/replays/engine_runner.run_case`, ideal reader):

| Case | Model calls on that unchanged sweep | Of the decider's, shadow (paid, then discarded) |
|---|---|---|
| F13 | 2 — decider 1, R-1 1 | 0 |
| F12, F25, F28 | 4 — decider 2, R-1 2 | 0 |
| F07 | 5 — decider 3, R-1 2 | — |
| F29 | 12 — decider 7, R-1 5 | 3 of 7 |

Every one changed nothing: the same cards before and after. Between the two sweeps, every derived
fact was re-written with a new `occurred_at` and the same value; two values moved — a continuous
clock (`response.overdue_hours`) and an org-wide count (`period.active_situations`).

**In production** (`baseline/2026-10-05/production_state.txt`, `@model_calls_by_day`):
`l4_llm_decision` + `l4_llm_r1` = 1,213 (2 Oct), 759 (3 Oct), 1,887 (4 Oct).

### 8.2 · The claims

| Claim | Verdict |
|---|---|
| one new event re-reasons every node and situation | ✅ — and a sweep with **no** new event does too: `run_l3` runs unconditionally after `process_pending` (`api/routes.py:748-772`). `process_pending`'s `affected` set holds only each drained event's primary node, so it cannot be the gate |
| no unchanged-check runs before a model is paid | ✅ — `reason_legacy_rule` (`reason/runner.py:1080`) runs before `no_new_evidence` (`:1250`); the model is reached through `orchestrator.py:259-265` → `decision_maker.py:1124` |
| every key moves every sweep | ✅ — and removing `evaluation_time` would not fix it: the context snapshot copies each fact's `occurred_at`, which the derived and waiting passes re-write every drain. A separate fingerprint is the right tool |
| shadow runs pay for discarded decisions | ✅, wider than drafted — R-1 and R-6 run on shadow rows too; `reason/domain_shadow.py:1192-1193` discards after paying |
| a DEFER expires the card | ✅, wider than drafted — the formula's own DEFERs (`below_confidence_floor`, `abstain_on_conflict`) and a cap hit (`llm_decision_unavailable:daily_call_cap`) expire it the same way: suppressed as `shadow` (`runner.py:1217`), then resolved and expired by the lifecycle pass (`:1450-1459`) |
| 3.1 the fingerprint's inputs | ⚠️ — member event ids are stable; derived facts keep their `fact_version_id` (an upsert on `fv_derived_<node>_<field>`), so it is their **values** that matter, not their ids; open loops should be ids, not counts; `card_events` carries system kinds that would make the fingerprint change itself; there is no days-waiting ladder (timeline_unit's is for deadline hours); the pack's `authority_revision` must be in it, or a skip after a calibration bump leaves a card that fails delivery |
| 3.2 reuse `reasoning_runs.supersedes_run_id` | ❌ — it is part of `input_hash` and the replay check; filling it changes every run's id. The store stands alone |
| 3.3 the compiled gate "between admission and reason_native_capability" | ⚠️ — just before `reason_native_capability` (`domain_shadow.py:1178`), where pack, manifest and anchor are known. And nothing renews a card's authority today: a re-run after expiry replaces it. So the gate must not skip a subject whose signal is about to lose authority |
| 3.4 move `no_new_evidence` ahead of reasoning | ❌ — it only applies when a prior signal exists, so DEFER and shadow subjects would still pay every sweep; it would skip the dormant and delivery checks a shadow run needs; `derivation_type` is never loaded. Replaced by the same gate as the compiled lane |
| 3.5 no model for shadow | ❌ as drafted — replay re-derives a decision with no mode (`decision_maker.py:1030-1033`), two tests and the native lane's suppressions read shadow decisions. **Dropped**: the gate skips a shadow row's unchanged sweeps, which is where the waste is. Whether a shadow row should pay a model at all is a later question |
| 3.6 a DEFER keeps the card | ✅ — widened to every DEFER of a live, deliverable run |
| 3.7 a `reasoning_skipped_unchanged` funnel stage | ❌ — the funnel's vocabulary is closed (`platform/funnel.py` STAGES, migration 0188's check). Counted on `run_all`'s outcomes, beside `no_new_evidence` |

### 8.3 · What will be built — tree block `yc2_w27_s02`

| # | Unit | Where | What |
|---|---|---|---|
| 1 | `M20.C1.L-contract.V0.U01` | `reason/fingerprint.py` | `MaterialInputs` — open loops, conflicts, human verdicts, the pack's revision; the clock ladders |
| 2 | `M20.C1.L-data.V1.U02` | `reason/fingerprint_inputs.py` | reads them in one round trip |
| 3 | `M20.C1.L-logic.V1.U03` | `reason/fingerprint.py` | `material_fingerprint` — the decision's inputs with every timestamp out, clocks bucketed, floats quantised, org-wide counts out; sorted; never `evaluation_time` |
| 4 | `M20.C2.L-contract.V0.U01` | `migrations/0191_reasoning_fingerprints.sql` | one row per subject: fingerprint, run, outcome, decided and last-checked, skips |
| 5 | `M20.C2.L-data.V1.U02` | `reason/fingerprint_store.py` | read, record a run, record a skip |
| 6 | `M20.C3.L-logic.V0.U01` | `reason/change_gate.py` | skip only on the same fingerprint with the card's authority good for another 24 h; say why otherwise |
| 7 | `M20.C3.L-integration.V2.U02` | `reason/domain_shadow.py` | the compiled lane asks the gate, live and shadow rows alike |
| 8 | `M20.C5.L-logic.V0.U01` | `reason/runner.py` | every DEFER of a live, deliverable run is indeterminate: the card stays |
| 9 | `M20.C4.L-integration.V3.U01` | `reason/runner.py` | the legacy and native lanes ask the gate; a skip replays the last outcome's bookkeeping |
| 10 | `M20.C6.L-interface.V4.U01` | `reason/runner.py` | `skipped_unchanged` and `deferred` counted, every lane, zero included |
| 11 | `M20.C6.L-interface.V4.U02` | `scripts/pipeline_health.py` | fails when a subject was re-decided on an unchanged fingerprint |
| 12 | `M20.C6.L-integration.V5.U03` | `tests/replays/test_an_unchanged_sweep_costs_nothing.py` | **the acceptance**: on every founder case an unchanged sweep makes 0 decider and 0 R-1 calls, and the cards are the same |

Critical path: 4 units (`C1` → `C3` → `C4` → `C6`). One migration (`0191`) — Harsh applies it with
the deploy. Not in this block: renewing a standing card's authority (replaced at expiry today —
`STEP-14`, one living card) and the in-process daily cap (`STEP-18` B9).

**The production number** (after the deploy, read-only): `baseline/production_state.sql`
`@model_calls_by_day` — `l4_llm_decision` + `l4_llm_r1` from ~760–1,890 a day to **under 100**.

## 9 · Built — 2026-10-06 (`yc2_w27_s02`, 13 units green)

### 9.1 · What was built

| Unit | Where | What it does |
|---|---|---|
| the store | `migrations/0191_reasoning_fingerprints.sql`, `reason/fingerprint_store.py` | one row per subject: the fingerprint its last decision was made on, the run, the outcome, the skips |
| the fingerprint | `reason/fingerprint.py`, `reason/fingerprint_inputs.py` | the decision's **own request** — capability and context snapshot — with time taken out, clocks on their rungs, plus the pack's revision, the human verdicts and who decides |
| the rule | `reason/change_gate.py` | skip only on the same fingerprint, and for a live card only while its authority has not lapsed |
| the compiled lane | `reason/domain_shadow.py` | asks the gate just before `reason_native_capability`, live and shadow rows alike |
| the legacy and native lanes | `reason/runner.py` | ask the gate before a rule or a native capability is reasoned; a skip replays the skipped decision's bookkeeping |
| a DEFER keeps the card | `reason/runner.py`, `executive/explain.py` | a live DEFER is indeterminate — the card stands — and `why_not` says *"could not decide"*, not *"shadow mode"* |
| counted and checked | `reason/runner.run_all`; `scripts/pipeline_health.py` | `skipped_unchanged`, `skipped_unchanged_compiled`, `deferred` on every sweep; a health check that the gate runs and saves |
| the acceptance | `tests/replays/test_an_unchanged_sweep_costs_nothing.py` | the 40 founder cases, in the `golden-pg` CI job |

### 9.2 · Measured

| | Before | After |
|---|---|---|
| model calls on a sweep that brings nothing new — golden set | F13 2 · F12/F25/F28 4 · F07 5 · F29 12 | **0 on all 40** |
| the cards after that sweep | the same | the same |
| the golden board | §F.1 | **unchanged** — the gate moved no verdict |
| production `l4_llm_decision` + `l4_llm_r1` | 1,213 · 759 · 1,887 a day (2–4 Oct) | ⏳ after the deploy — target under 100 |

### 9.3 · Found and fixed while building — each a measurement, not a guess

- **who decides is an input.** A test that switched the LLM decider on between two sweeps was
  skipped as unchanged; in production, flipping `GENIOS_L4_LLM_DECISION_MAKER` would have kept every
  old decision. The fingerprint carries the decider.
- **a re-run before expiry renews nothing.** The rule's first margin was a day, so a card was
  re-decided on every sweep of its last day — about 96 decider and R-1 pairs per card per week —
  found by the acceptance on F27. The margin is zero.
- **the fingerprint would have raised on any decimal** (hashing a canonical payload twice), and
  **dropping `occurred_at` threw away a source fact's age** — both caught by the fingerprint's own
  mutation check, before wiring.
- **`run_all` threw the compiled pass's result away**, so nothing the compiled lane counted reached
  the sweep.
- **a DEFER was logged as `shadow`** and explained to the founder as "the pack is in shadow mode".

### 9.4 · QA

`baseline/yc2w27-s02-qa/qa_record.txt`, at `aaca7e67`, an empty scratch database: the units 17 / 0 / 0;
the whole database suite 17,290 passed, 0 failed; the golden lane 398 passed, 100 xfailed, 0
skipped; the board matches; the hermetic job 16,087 passed. The first run, at `ac021462`, failed three
repo-wide guards; they were fixed and the whole tier re-run.

### 9.5 · The deploy

Migration `0191` ships. `main.py` applies pending migrations at boot when the database is writable.
On a read-only database the boot is degraded: the gate then fails open — every subject is decided,
as before, so nothing is lost but nothing is saved — and `/reset` fails until `0191` is applied,
because the reset now wipes `reasoning_fingerprints`.

### 9.6 · What it does not do yet

- renew a standing card's authority — it is replaced at expiry, as it was before (`STEP-14`);
- a legacy signal kept open by `no_new_evidence` past its authority is decided every sweep after the
  lapse, as it was before;
- a shadow row still pays the model when its inputs do change;
- the fingerprint takes time out by name — a new field re-stamped every sweep would make the gate save
  nothing, which the health check and the acceptance both catch.
