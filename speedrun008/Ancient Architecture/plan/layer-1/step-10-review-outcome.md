# Step 10 — `REVIEW` as a fourth outcome

**Status:** NOT STARTED · **Effort:** days · **Depends on:** 4, 8 · **Engine:** R

> **Measure before building.** §5's first unit is a measurement, and it can cancel the step.

## 1. Why this step exists

A signal that is **low confidence but high value** has nowhere to go. Today it either clears the
floor and emits **as though it were certain**, or falls under and lands in the drop ledger where
nothing routes it to a person.

*"We should probably revisit this after the next board meeting"* at confidence 0.61 is worthless on
its own and potentially decisive next to a renewal date and an open negotiation — **and Layer 1
does not have the context to know which.** Dropping it is a decision made with less information
than the layer that would use it.

## 2. Current status — more is already right than is usually assumed

**There are already three outcomes, not two:**

```python
# contracts/publication.py:82-94
# closed — a fourth outcome invented at a call site would be an emit nobody reviewed.
EMIT = "emit" · PARK = "park" · REJECT = "reject"
```

And the floor already has **three "travel anyway" overrides**: a signal carrying a CONFLICT travels
(no score can rank a disagreement), company canon travels, and an **UNSCORED signal travels**
(*"never block on a missing score"*). So *uncertain ≠ drop* is already partly law.

What is missing is the **low-confidence-high-value** case. `PARK` exists but means *"blocked on
something mechanical"* — a missing envelope, an unfetched attachment — not *"a person should look"*.

## 3. Expected result
A fourth outcome, added **in the contract**, with a routing rule and a drain. Both thresholds
per-tenant rows.

## 4. Edge cases
E1 a `REVIEW` with no drain is **a slower drop** — the queue and its drain ship in the same change ·
E2 the volume must be bounded, or REVIEW becomes a second inbox · E3 the thresholds are rows with
owners, never module constants · E4 a reviewed signal that is accepted must re-enter the **full**
pipeline, not bypass qualification · E5 `PublicationOutcome` is closed and says so — this is a
deliberate contract change, and every reader of the enum must be found.

## 5. How to do it
| Unit | What |
|---|---|
| **10-U0** | **MEASURE FIRST.** Replay the pilot's 68 floor-refused signals and count how many would become `REVIEW`. **68 or 0 both mean the thresholds are wrong** — and 0 means the step is not needed yet |
| 10-U1 | `REVIEW` on `PublicationOutcome`, in the contract |
| 10-U2 | the routing rule: low confidence + high importance → `REVIEW`; everything else unchanged |
| 10-U3 | the queue and its drain, on the same "held, not lost" terms the parked queue already has |
| 10-U4 | a resolved review re-enters ESQE from the top |

## 6. Test cases
T1 U0's replay produces a count that is **neither 0 nor 68** · T2 a low-confidence high-importance
fixture routes to `REVIEW` · T3 a low-confidence **low**-importance fixture still parks or drops ·
T4 a resolved review walks the full pipeline · T5 V-1…V-7 behaviour for the other three outcomes is
unchanged (**regression guard**).

## 7. Verify
```bash
uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q -p no:randomly
uv run --no-sync pytest tests/capture/esqe/test_qualification.py tests/capture/esqe/test_rejection_ledger.py -q -p no:randomly
```

## 8. Done criteria
**Ticked 2026-09-24. One closed; three are OPEN ON PURPOSE because this step gated itself and
the gate is unrun.**

- [~] **U0's measured count is in `STATUS.md` before any code was written** — **U0 is BUILT and
      unrun.** `capture/esqe/review_candidates.py` is the measurement as a pure, tested function
      (13 tests), so the same code answers a fixture here and the tenant Harsh points it at. The
      COUNT needs `qualification_drops` from a live corpus, and the 68 is from the tenant
      re-synced away on 19 Sept. **No routing code was written**, which is the half of this
      criterion that was actually in my control.
- [ ] **the outcome exists in the contract, not at a call site** — **NOT DONE, DELIBERATELY.**
      `PublicationOutcome` is still closed at three. Its own docstring says *"a fourth outcome
      invented at a call site would be an emit nobody reviewed"*, and a fourth outcome invented
      before its measurement is the same mistake one step earlier. §5 gives U0 the power to cancel
      this step; exercising that power means not pre-empting it.
- [ ] **the drain ships in the same change as the outcome** — **not applicable yet, and E1 is why
      it must stay that way.** *"A REVIEW with no drain is a slower drop."* U1–U4 are one unit or
      none.
- [x] **thresholds are per-tenant rows with owners** — **already true and untouched.**
      `org_qualification_floors` carries an owner and `qualification_floor_changes` is an
      append-only log. E3 has a home; `NEAR_CEILING_BP` is explicitly documented as a starting
      point for the MEASUREMENT and never a shipped threshold.

### 8.1 · The routing rule as written cannot be built

`finalize.py` fixes the order `conflicts → QUALIFY → lifecycle → PUBLISH`, and ALG-13 composes
confidence inside `publisher.py` — at **publish**. So **at the moment the floor refuses a signal
its confidence has not been computed**, and `qualification_drops` has no confidence column because
there is nothing to put in one.

What the drop point CAN see is `importance_bp`, `floor_bp` and `components` — and **step 8 put
`achievable_ceiling_bp` in exactly that reach.** That is the better rule anyway: a signal at 2,400
against a **ceiling of 3,000** is near-maximal for what it could ever have earned, and an absolute
floor of 2,500 refuses it. Step 4 measured that exact population — `relationship_change`, published
4, dropped 54, its whole band below the bar.

> **Steps 4 → 8 → 10 are one finding seen three times.**

## 9. Must NOT do
**Do not ship `REVIEW` without its drain.** Do not add the outcome at a call site — the contract
forbids it in writing. Do not use `REVIEW` as a dumping ground for anything uncertain; that is how
recall becomes a second inbox nobody reads.
