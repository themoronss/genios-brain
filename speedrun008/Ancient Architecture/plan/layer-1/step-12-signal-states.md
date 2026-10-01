# Step 12 — Per-type signal states and commitment fulfilment

**Status:** NOT STARTED · **Effort:** weeks · **Depends on:** 3, 4 · **Engine:** L detects, D commits
**Moves:** metric 6 — benchmark objects present (P2's missing half)

> **Added after the first plan.** The gap audit found that steps 1–11 never built commitment
> fulfilment. P2 is the prompt L1 is strongest on, and this is the half it cannot answer.

## 1. Why this step exists

The P1–P5 audit scored P2 at **6 of 9 objects built**. The three missing ones are all the same
thing: *did the promise get kept?*

| Object | State |
|---|---|
| Commitment, promisor, beneficiary, object, deadline, evidence | ✅ typed, built |
| **Fulfilment link** — a later message that satisfies the promise | ❌ nothing joins them |
| **State** OPEN / FULFILLED / BROKEN / UNKNOWN | ❌ no such vocabulary |
| Delivery failure | → step 2 |

`esqe/lifecycle.py` ALG-19 has **four generic states**: `active` / `superseded` / `expired` /
`resolved`. That machine is correct and careful — supersession keyed on
`(subject_key, signal_type)`, authority-gated, world-time ordered. But it is **one machine for
fifteen signal types**, and a commitment needs words it does not have.

**And the distinction that matters most is BROKEN vs UNKNOWN.** Claude's benchmark run marked four
promises "Broken" — correctly, because it could read nearly the whole sent folder. On a mailbox
where coverage is 8%, the same absence means **UNKNOWN**, not broken. Telling a founder they broke
a promise they actually kept is worse than saying nothing.

> **A state is only as strong as the coverage behind it.** This step depends on step 5 for that
> reason — see §4 E1.

## 2. Current status

| What | Where |
|---|---|
| Four generic lifecycle states | `esqe/lifecycle.py`, `SIGNAL_STATES` in `contracts/signal.py` |
| Supersession key | `(subject_key, signal_type)` — step 3 makes it cross the seam |
| `Commitment.due` | typed, ALG-09 resolves it as a **range with a certainty** |
| Fulfilment evidence | **nothing looks for it** |
| Per-type states | **do not exist** |

## 3. Expected result

| Signal type | States it needs |
|---|---|
| Commitment | `OPEN` · `FULFILLED` · `BROKEN` · `UNKNOWN` |
| Conditional trigger | `UNMET` · `MET` · `UNKNOWN` · `EXPIRED` |
| Availability | `ACTIVE` · `ENDED` · `UNKNOWN` |
| everything else | the four generic states, unchanged |

Plus: a **fulfilment link** — the later event that satisfied a commitment, carried as evidence.

**Prediction:** on the pilot, most commitments land in `UNKNOWN`, not `BROKEN`, because the corpus
is 27% emit rate. **If most land in `BROKEN`, the coverage gate in §4 E1 is not wired** and the
step has produced a confident lie.

## 4. Edge cases and failure scenarios

| # | Scenario | What must happen | Why |
|---|---|---|---|
| **E1** | No fulfilment evidence found | `UNKNOWN`, **never `BROKEN`**, unless coverage over the window is high enough to make absence meaningful | the single most important rule in this step |
| E2 | Coverage is unknown | `UNKNOWN`. A state asserted without a denominator is Gemini's 18-of-18 | depends on step 5 |
| E3 | Fulfilled late | `FULFILLED`, with the delta recorded — late is not broken | |
| E4 | Partially fulfilled ("sent half the deck") | `UNKNOWN` unless the promise was decomposable | do not invent a partial state |
| E5 | The promise was withdrawn ("never mind") | `RESOLVED`, not `BROKEN` | |
| E6 | Re-promised with a new date | the old one is **superseded**, not broken — step 4's G7-U2 detects the modification | |
| E7 | Fulfilment happened outside any connected source (a phone call) | `UNKNOWN`, and the **coverage declaration says why** | this is `coverage/declaration.py`'s existing argument, one level down |
| E8 | A conditional whose condition needs company state | `UNKNOWN` — **evaluating it is L2's** | the boundary in §9 |
| E9 | Deadline is a range with low certainty ("sometime next week") | no `BROKEN` until the range's far end passes | ALG-09 already stores certainty; read it |

## 5. How to do it — unit by unit

| Unit | What | Engine |
|---|---|---|
| 12-U1 | a per-type state vocabulary, declared as data — **not a second state machine** | R |
| 12-U2 | the type→states map is validated at import, like `ImportanceWeights`' total check | D |
| 12-U3 | fulfilment candidate detection: a later event that plausibly satisfies an open commitment | **L** proposes |
| 12-U4 | the link is **validated** — same subject, same actor, after the promise, with a resolvable span | D |
| 12-U5 | the state transition is committed by the machine, never by the model | D |
| 12-U6 | **the coverage gate**: `BROKEN` requires a coverage figure above a per-tenant threshold; below it, `UNKNOWN` | D |
| 12-U7 | the fulfilment event is carried as evidence on the commitment signal | D |

**Model proposes, machine commits** — the same pattern as step 4 and step 9.

## 6. Test cases

| # | Test | Asserts | RED today |
|---|---|---|---|
| T1 | promise + later satisfying message | `FULFILLED`, with the link | no such state |
| T2 | promise, no later message, **high** coverage | `BROKEN` | — |
| T3 | promise, no later message, **low** coverage | **`UNKNOWN`** | the case that matters |
| T4 | promise, no coverage figure at all | `UNKNOWN` | — |
| T5 | fulfilled two days late | `FULFILLED`, delta recorded | — |
| T6 | re-promised with a new date | old superseded, **not** broken | — |
| T7 | a conditional needing company state | `UNKNOWN`, and L1 does not reach for the graph | boundary guard |
| T8 | the four generic states on other types | unchanged | **regression guard** |

## 7. Verify

```bash
uv run --no-sync pytest tests/capture/esqe/test_lifecycle.py -q -p no:randomly
uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q -p no:randomly
uv run --no-sync pytest tests/capture/esqe/test_commitment_states.py -q -p no:randomly   # new
```

## 8. Done criteria

**Ticked 2026-09-24.** Three closed, one needs the live corpus.

- [x] **per-type states exist and are validated at import** — `STATES_FOR_TYPE` lives in
      `contracts/signal.py` (beside `SIGNAL_STATES`, because `tests/test_layer_topology.py` refuses
      an import from `contracts` up into `capture`) and the resolver lives in
      `capture/esqe/signal_states.py`. The contract enforces it in **two rungs**: a word legal for
      no type (what a typo produces) and a word from ANOTHER type's vocabulary — the second needs
      `signal_type`, so it is a model validator, and without it `availability_change` could carry
      `broken`.
- [x] **T3 green — low coverage produces `UNKNOWN`, not `BROKEN`** — `BROKEN_REQUIRES_COVERAGE_BP
      = 9000`, deliberately very high. `coverage_bp=None` lands on the same side as a low number
      and for a sharper reason: **nobody measured**, and the honest state for *"we did not look at
      whether we looked"* is `unknown`. The gate guards ONE direction — `FULFILLED` needs no
      coverage, because finding evidence is a positive observation.
- [ ] **the pilot's commitment state distribution is in `STATUS.md`, with the coverage figure
      beside it** — **NOT DONE; needs the live corpus.** §3's prediction is what that measurement
      exists to test: *"most commitments must land in UNKNOWN. If most land in BROKEN, the
      coverage gate is not wired and the step has produced a confident lie."* Harsh's.
- [x] **the four generic states are unchanged for every other type** — and **this is where I got
      it wrong first.** See §8.1.

### 8.1 · The correction six Layer 2 tests forced

The first `STATES_FOR_TYPE` listed only the fulfilment words for a commitment. **Six L2 tests went
red**, including `test_every_lifecycle_state_the_contract_allows_can_be_built[active]` — and they
were right: **every commitment signal ever stored carries `state="active"`**, so that vocabulary
would have refused the entire existing corpus at the contract on deploy day.

The reason is not backward compatibility. **They are two axes sharing one column:**

| axis | words | question |
|---|---|---|
| lifecycle | `active · superseded · expired · resolved` | has this signal been **replaced**? |
| fulfilment | `open · fulfilled · broken · unknown` | was the **promise kept**? |

§3's table reads as though the four were swapped out; **§9 is the binding half** — *"do not build a
second state machine"* — and a union honours it where a replacement does not.

> **Second time in four steps that a narrowed vocabulary would have broken the existing corpus.**
> Step 9's `UNKNOWN=9000` was the first. Both were caught by tests that already existed, in under a
> minute, and both now carry the failure that produced them.

## 9. What this step must NOT do

- **Do not say `BROKEN` without a coverage figure.** E1 is the whole step.
- **Do not evaluate a condition against company state** — that needs the graph, and the graph is
  Layer 2's. L1 says the condition exists and that its satisfaction is `UNKNOWN`.
- **Do not build a second state machine.** The per-type vocabulary is data that ALG-19 reads.
- **Do not let the model commit a transition.** It proposes the fulfilment candidate; the machine
  decides legality.
