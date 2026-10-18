# S6 — DONE · every refusal is named, and an illegal lifecycle edge was being written

**Unit:** `M14.C2.S6` · **Owner:** me · ✅ **2026-10-02** · **46 tests · 9/9 mutations caught**
**Atlas:** the **no-silent-drop contract** · `L7-30` · `L7-22` — and ⛔ **`U03` un-retracted**
**Plan:** [`08-PLAN-v2-from-the-atlas.md`](08-PLAN-v2-from-the-atlas.md) §7 — *"the four unread
ledgers, demoted to monitoring"*

---

## 1 · Two defects, one cause: the ledgers that would have shown them are the unread ones

`F11` measured four ledgers `feedback/` writes that nothing reads. `S6` asked each one *"what
question would you answer?"* — and two of them answered with a live defect.

## 2 · ⛔⛔ The no-silent-drop contract, broken in nine lines

```python
for obj in proposals:
    ok, _ = validate_learning(obj, policy)      # ⛔ the reason is DISCARDED
    if not ok:
        held += 1                                #    counted, never named
        continue
    if not preflight(obj, policy, now=now).ok:   # ⛔ PreflightResult.reason_code DISCARDED
        refused += 1
        continue
    decision = govern(obj, policy)
    if decision.rejected:
        refused += 1                             # ⛔ GovernanceDecision.reason_code DISCARDED
        continue
```

**All three callees compute and return a reason, and all three call sites throw it away.**
`_record_evaluation` ran only on the paths that survived, so `learning_object_evaluations` recorded
**only the successes.**

The Atlas states the contract this breaks, in full:

> *"Every rejected or deferred candidate must retain `run_id`, tenant, unit, evidence IDs, **reason
> code**, failed gate, policy version, timestamp, and recovery status. 'No proposal' is valid only
> when accompanied by a machine-readable reason such as `insufficient_independent_support`,
> `outcome_unreconciled`, `visibility_forbidden`, `identity_unresolved`, or `ttl_missing`. **A
> weekly sweep that returns zero objects without this accounting is operationally indistinguishable
> from broken wiring.**"*

⛔ **And the ledger was built for it.** `migrations/0046`: *"`learning_object_evaluations`
append-only: every actual per-run decision (new or **HELD** object)"* — **the held case is named in
the schema's own comment and was never written.**

### ⛔ No migration was needed, and that is the measurement that made this small

| The Atlas asks for | `learning_object_evaluations` already has |
|---|---|
| `run_id` | `run_id` |
| tenant | `org_id` |
| policy version | `policy_revision` |
| timestamp | `evaluated_at` |
| failed gate / reason code | `sink_reason` (`not null`) |
| recovery status | `prior_state` / `result_state` |

⛔ **And `learning_id` carries no foreign key** — only `org_id` does — so a proposal that never
reached `persist` can still be recorded. *Checked before writing, because a refused object has no
`learning_objects` row.*

## 3 · ⛔⛔ An illegal lifecycle edge, on the most important path in the layer

`publisher.publish()` fixes `from_state = GOVERNED`, reassigns `target_state = PUBLISHED` after a
brain publish, and logs **once**:

```
every brain publish wrote:        governed → published
ALLOWED_LEARNING_TRANSITIONS[GOVERNED] = (temporary, human_review, promoted, rejected)
learning_can_transition(GOVERNED, PUBLISHED) = False          ⛔ ILLEGAL
```

⛔ The map's own docstring states the intended path — *"| Promoted→Published | Rejected}; Published →
{Superseded | RolledBack}"* — **two hops.** The publisher collapsed them and **skipped `PROMOTED`**:
the state that distinguishes *"promoted, publisher not yet done"* from *"published"*, which is
exactly the ambiguity the Atlas's **`L7-30`** names — *"Publisher crashes after persistence but
before activation receipt → **do not infer active state from row existence**."*

> ⛔ **`ALLOWED_LEARNING_TRANSITIONS` existed from the start and nothing checked it on this path.
> The ledger that would have shown the illegal edge is `learning_transitions` — written by five
> call sites and read by none.** *The data needed to guard the loop was already being written, and
> nothing asked it a question.*

### ⛔⛔ And my own retraction of this unit was wrong

[`07-ATLAS-CHECK`](07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md) §3 retracted `U03`
*"an illegal learning transition"*:

> *"RETRACTED as the spine. It was derived from a ledger, not from a named gap, and its gate
> question (does the second writer validate?) is answered by Atlas #9: the second writer **is** the
> repaired approval path."*

⛔ **That conflated two questions.** The second writer (`api/learning_routes.py`) is indeed the
repaired approval path and **both its edges are legal**. The **first** writer was the one emitting
an illegal edge, and I never looked at it.

> ⛔ **A retraction needs its own measurement, not a neighbouring one.** Fifth retraction in this
> programme — and the first of a **retraction**.

## 4 · What changed

| File | Change |
|---|---|
| `feedback/orchestrator.py` | all three refusal paths record their reason into `learning_object_evaluations`; `evaluations` counts every row and enters `counts` as the receipt's marker |
| `feedback/publisher.py` | ⛔ `publish()` logs the missing `governed → promoted` hop before `promoted → published`; ⛔ `log_transition` **refuses** an illegal edge, an unknown state, and exempts `from_state=None` |
| `platform/receipts.py` | ⛔ **two** correctness receipts, and `_ILLEGAL_TRANSITION_SQL` derives its legal pairs **from the contract** |
| `tests/feedback/test_no_transition_takes_an_edge_the_contract_forbids.py` | **46 tests** |

```
receipts                     36 → 38
feedback/ receipts            5 → 7
⛔ feedback/ CORRECTNESS       1 → 3     (0 before S5)
unread ledgers of the four    4 → 2
```

### ⛔ Why `log_transition` refuses rather than records

An illegal edge means the **lifecycle state machine is wrong**, and that is not something to log
and continue past. The weekly sweep already isolates one tenant's failure, and ⛔ **since `S3` it
names it in `skipped_by_reason`** — so a refusal here is visible rather than silent. The machinery
that makes a fail-closed usable was built two steps ago.

⛔ **Six call sites were enumerated before the raise was added**, because a raise inside a publish
is only safe if every caller is known:

| Site | from → to | |
|---|---|---|
| `publisher.persist` | `None` → governed | ✅ exempt — no predecessor exists |
| `publisher` lease supersede | temporary → archived | ✅ |
| **`publisher.publish`** | governed → **published** | ⛔ **the bug — fixed to two hops** |
| `org_rule_ingest:154` | validated at `:152` | ✅ |
| `brain_pipeline:231` | validated at `:223` | ✅ |
| `api/learning_routes:141` | human_review → promoted/rejected | ✅ both legal, ⛔ **raw SQL — not guarded at runtime** |

⛔ The API route builds a **deterministic id** for idempotency that `log_transition`'s
`new_id("ltr")` would break, so it is deliberately not routed through the guard — and
`test_the_unguarded_writer_in_the_api_writes_only_legal_edges` checks its two edges from its own
source instead. **An unguarded writer that is checked at build time is not an unguarded writer.**

### ⛔ The receipt's legal set is derived, never copied

`_ILLEGAL_TRANSITION_SQL` builds its `not in (...)` from `ALLOWED_LEARNING_TRANSITIONS` itself — 23
pairs, asserted identical to the map by test. ⛔ **A hand-written list would drift the first time a
state is added, and the drift would WIDEN what the receipt accepts.** The values are enum members
and the SQL is text, so each one is checked against `[a-z_]+` before interpolation.

### ⛔ And the drop receipt is gated on a marker

A run completed before refusals were recorded has `held`/`refused` above zero and **no evaluation
rows** — so an ungated claim would be red for history it could not have recorded.
`counts->>'evaluations' is not null` is the marker that the run executed under the contract.
*A gate that is always red is a gate nobody reads.*

⛔ **The edge receipt has no such gate, deliberately.** Rows written before today CAN be illegal,
and the receipt **names them rather than hiding them**. The read-only query that settles it is
`select from_state, to_state, count(*) from learning_transitions group by 1, 2` — which answers a
second question at the same time: **whether any brain value has ever been published at all**, which
is what `L7-27` asks.

## 5 · The mutation run — baseline first, 9/9

```
✅ baseline: 46 passed

  M1 the publisher goes back to ONE hop                ✅   M6 ⛔ the MAP is WIDENED so the
  M2 log_transition stops validating                   ✅      bug becomes legal        ✅ (3 failed)
  M3 the validator's reason is DISCARDED again         ✅   M7 the legal set is hand-copied   ✅
  M4 a refusal path stops recording                    ✅   M8 persist's edge stops being
  M5 the marker key is dropped from counts             ✅      excluded                      ✅
                                                            M9 a reader appears for
                                                               learning_metrics             ✅
✅ baseline again: 46 passed              9 caught · 0 survived
```

⛔ **`M6` is the one that matters most.** Widening `ALLOWED_LEARNING_TRANSITIONS` to make
`governed → published` legal — **the "fix" that weakens the verify instead of the code** — is
caught by **three** tests. *Never weaken a verify to make it pass* is now enforced rather than
remembered.

## 6 · The two ledgers that still have no reader — declared, not discovered

| Ledger | State |
|---|---|
| `learning_object_evaluations` | ✅ **reader: the no-silent-drop receipt**, and its `_by_run` index has its first query |
| `learning_transitions` | ✅ **reader: the illegal-edge receipt** |
| `learning_input_rejections` | ⛔ still unread. Written by `org_rule_ingest`'s discovery route; its denominator is `org_rule_discovery_runs`, which **is** read (`:235`, `:459`), so a ratio is now computable — `S7`'s |
| `learning_metrics` | ⛔ the VALUES are still unread. ⛔ But its failure mode became observable in this step: `publish_metric` returns `metric_identity_conflict`, which now reaches `sink_reason` in the evaluation ledger |

`test_the_remaining_unread_ledgers_are_still_unread` asserts both, so the day one gets a reader the
`F11` tally is updated **deliberately rather than discovered**.

## 7 · Verify

```bash
.venv/bin/pytest tests/feedback/test_no_transition_takes_an_edge_the_contract_forbids.py -q  # 46
.venv/bin/pytest tests/platform/test_every_package_says_what_it_does_not_call.py \
    tests/feedback tests/contracts -q                                                        # 980
.venv/bin/pytest -q                                                                   # FULL suite
```

## 8 · ⛔ What this hands to Rohit

**One read-only query, and it answers two questions at once:**

```sql
set transaction read only;
select from_state, to_state, count(*) from learning_transitions group by 1, 2;
```

⛔ A `governed → published` row means a brain value **was** published before today's fix, and the
illegal-edge receipt will be red until that history is accounted for. ⛔ **No rows at all** means no
brain value has ever been published — which is `L7-27`'s question (*"Stored learned version is never
consumed by Layer 3"*) and the same answer the Adaptive decision (`#11`) needs.

## 9 · Doctrine

| Rule |
|---|
| ⛔ **a retraction needs its own measurement, not a neighbouring one** — `U03` was retracted on a fact about a different writer |
| ⛔ **a counted refusal is not a named refusal** — the Atlas's no-silent-drop contract |
| ⛔ **the reason the callee computed is the reason to record** — three call sites, three discarded return values |
| ⛔ **derive the legal set from the contract; a copied list drifts in the permissive direction** |
| ⛔ **never weaken a verify to make it pass** — now enforced by three tests, not remembered |
| ⛔ **an unguarded writer that is checked at build time is not an unguarded writer** |
| **enumerate every caller before adding a raise** |
| **a guard at the writer protects the future and says nothing about the past** — hence the receipt |
