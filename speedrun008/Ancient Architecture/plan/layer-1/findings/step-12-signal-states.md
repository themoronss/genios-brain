# Step 12 · Per-type signal states and commitment fulfilment — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code
**Status:** 12-U1 · U2 · U4 · U5 · U6 **DONE** · 12-U3 and U7 **need a cross-event join — deferred
with a reason**

---

## 1. Premise check — every premise confirmed, and the dependencies are in place

| Written premise | Verdict |
|---|---|
| Four generic states, one machine for sixteen types | ✅ `{active, superseded, expired, resolved}` |
| No fulfilment vocabulary anywhere | ✅ `grep -rn "FULFILLED\|fulfil"` returned nothing in `genios_engine/` |
| Nothing looks for fulfilment evidence | ✅ confirmed |
| E2 needs step 5's coverage figure | ✅ **it exists** — `SyncSummary.claimed_total` + `cursor_exhausted` |
| E9 needs ALG-09's certainty and far end | ✅ **both exist** — `DateCertainty{EXACT,RANGE,RELATIVE,UNRESOLVED}` and `ResolvedDate.latest` |

**First step in twelve whose premises were all correct.** It was written after the gap audit, with
the code already read — which is itself evidence for the discipline: a premise checked before it is
written down does not need correcting afterwards.

Cost check: `grep vocabulary_fingerprint|_SETS genios_engine/capture/esqe/lifecycle.py` → 0.
Lifecycle and state resolution are post-extraction and deterministic. **No prompt, no re-extraction,
no model.**

---

## 2. ⛔ E1 is the whole step

> *"No fulfilment evidence found → `UNKNOWN`, **never `BROKEN`**, unless coverage over the window is
> high enough to make absence meaningful."*

Claude's benchmark run marked four promises **Broken** and was right — it could read nearly the whole
sent folder. On a mailbox where we read 8% of the window, **the identical absence means UNKNOWN.**

> **Telling a founder they broke a promise they actually kept is worse than saying nothing.**
> An absence of evidence is evidence of absence only when you can prove you looked.

`BROKEN_REQUIRES_COVERAGE_BP = 9000`, deliberately very high: a 5000 gate would let a coin-flip
corpus accuse people, and the costs are not symmetric. A false `BROKEN` tells a founder they failed
at something they did; a false `UNKNOWN` says we are not sure. The `Commitment` contract already
prices the first — *"the second false chase is the last time that founder reads a nudge from us."*

**The gate guards ONE direction.** `FULFILLED` needs no coverage figure: finding the evidence is a
POSITIVE observation and we are not reasoning from an absence. Suppressing it would be caution
applied where there is nothing to be cautious about.

`coverage_bp=None` lands on the same side as a low number, and for a sharper reason: `None` means
**nobody measured**, and the honest state for *"we did not look at whether we looked"* is `unknown`.

---

## 3. ⭐ The correction six Layer 2 tests forced

The first version of `STATES_FOR_TYPE` listed only the fulfilment words for a commitment. **Six
Layer 2 tests went red immediately**, including
`test_every_lifecycle_state_the_contract_allows_can_be_built[active]`.

They were right. **Every commitment signal ever stored carries `state="active"`**, so a vocabulary
that excluded it would have refused the entire existing corpus at the contract on deploy day.

**And the reason is not backward compatibility — it is that these are two axes sharing one column:**

| axis | words | question |
|---|---|---|
| lifecycle | `active · superseded · expired · resolved` | has this signal been **replaced**? |
| fulfilment | `open · fulfilled · broken · unknown` | was the **promise kept**? |

A commitment is legitimately `active` (nothing superseded it) **and** legitimately `fulfilled` (the
promise was kept). The step's §3 table reads as though the four were swapped out; **§9 is the
binding half** — *"do not build a second state machine"* — and a union honours it where a
replacement does not.

> That both axes share one `state` column is a compression this step **inherits** rather than
> causes. Splitting them is a migration and a seam change, and it belongs with step 14's temporal
> work rather than smuggled into a vocabulary table.

**Second time in four steps that a narrowed vocabulary would have broken the existing corpus** —
step 9's `UNKNOWN=9000` was the first. Both were caught by tests that already existed, in under a
minute, and both are now pinned with the failure recorded.

---

## 4. What was built

| Unit | What |
|---|---|
| **12-U1** | `CommitmentState` · `ConditionState` · `AvailabilityState` — three vocabularies, each a different shape |
| **12-U2** | `STATES_FOR_TYPE` in **`contracts/signal.py`**, validated at import |
| **12-U4** | `is_valid_fulfilment` — time ordering checked by the MACHINE, not asserted by the model |
| **12-U5** | `resolve_commitment_state` — the transition is committed here; the model only proposed the link |
| **12-U6** | the coverage gate, §2 |

### 4.1 · Where the data lives, and why it is not with the logic

`tests/test_layer_topology.py` refuses an import from `contracts` up into `capture`. So:

* **the VOCABULARY** (which words are legal for a type) is in `contracts/signal.py`, beside
  `SIGNAL_STATES` where it has always belonged;
* **the RESOLVER** (which state a given promise is in) is in `capture/esqe/signal_states.py`.

The contract now enforces it in two rungs, and both are needed:

```python
_known_state              # a word legal for NO type — what a typo produces
_state_belongs_to_this_type   # a word from ANOTHER type's vocabulary
```

A `field_validator` on `state` alone cannot see `signal_type`, so widening the first rung to the
union would have let `availability_change` carry `broken` — legal-looking and meaningless. The
model validator is what catches that, and a test pins it so nobody deletes it as redundant.

### 4.2 · The edge cases, each with its own row

| | |
|---|---|
| **E3** late is **not** broken | `FULFILLED`, with `days_late` recorded so a reader sees it without re-deriving |
| **E5** withdrawn is not broken | *"never mind"* retires a promise; it does not fail one |
| **E9** a RANGE deadline | overdue is measured against `due_latest`, the FAR end. Calling a promise broken on the near end of a range the speaker never committed to is inventing a deadline — the failure `Commitment`'s contract warns about |
| **E8/T7** a conditional | `UNKNOWN`. L1 says the condition exists; **evaluating it against company state needs the graph, and the graph is Layer 2's** |

---

## 5. What was NOT built, and why

**12-U3 · fulfilment candidate detection** and **12-U7 · carrying the link as evidence.**

Finding *"a later event that plausibly satisfies an open commitment"* is a **cross-event join**, and
L1's unit of work is one event. `capture_event` sees one message; `run_sync` sees a page. Nothing in
Layer 1 holds "every open commitment for this tenant" — that is a query over `qualified_signals`,
which is the object L2 owns.

The machinery that would host it exists (`is_valid_fulfilment` is the rule the machine applies), and
the state resolver already takes `fulfilment_event_id` as an input. **What is missing is the
producer, and building it inside L1 would mean L1 querying its own published output** — a shape this
architecture does not have anywhere else.

> It belongs beside **step 15** (coverage on the signal) or in L2's correlator. Recorded rather than
> half-built: a fulfilment detector that ran on a single event would find nothing and report it as
> an absence, which is precisely the `BROKEN`-vs-`UNKNOWN` error this step exists to prevent.

---

## 5b. Test result

```
FULL SUITE      12646 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 12: 12626 passed · 14 failed
```

**Zero regressions, +20 tests.** No migration, no model call, no re-extraction.

The six L2 failures my first vocabulary caused are gone — back to exactly the 11 pre-existing.

---

## 6. What this step does NOT do

* **It does not detect fulfilment.** §5 — the resolver is ready and the producer is not.
* **It does not evaluate conditions.** §9's boundary: that needs the graph.
* **It does not split the two axes.** §3 — one `state` column carries both, which is inherited and
  is a migration.
* **It does not produce the pilot's state distribution.** §8's third criterion needs the live
  corpus, and §3's prediction — *"most commitments must land in UNKNOWN"* — is what that
  measurement is FOR. Harsh's.
