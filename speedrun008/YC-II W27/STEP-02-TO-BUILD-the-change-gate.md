# STEP-02 · TO BUILD · the change gate — no new evidence, no new decision

**Owner:** Claude. **Depends on:** `STEP-00` (one branch). **Decision:** `06` D11 (recommended: keep
the current decider, behind this gate). **Moves:** `l4_llm_decision` + `l4_llm_r1` **~1,400 calls a
day → under 100**; cards stop appearing and vanishing; a DEFER stops expiring a card.

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
