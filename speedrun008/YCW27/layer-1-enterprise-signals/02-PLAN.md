# L1 · the plan — sections → functions → components → units

**Audience:** the CTO and the coding agent. **Read `01-CROSSCHECK.md` first** — this plan only
covers what that audit found to be genuinely open.

**Build order is bottom-up.** Units first, then the component that composes them, then the
function, then the section. A parent is never started before its children are green.

---

## ⛔ Correction to `01-CROSSCHECK.md` §4

The cross-check said relevance *"gets no model in production"* and called it **a one-line wiring
fix**. That was wrong, and the correction matters because it changes what we build.

The wiring is complete and correct. `platform/wiring.py:780-813`:

```python
if not is_semantic_activated(engine, org_id):
    return None                     # ← the whole SemanticLane
if llm is None:
    return None
return SemanticLane(..., relevance_page=RelevancePage(llm=llm, governor=governor, ...))
```

`RelevancePage` is **always** constructed with a real client when the lane exists at all. The
`no_model_wired` path is reached through a different door — `pipeline.py:1272`:

```python
assess_relevance([candidate], llm=stage.relevance_llm)
```

`stage.relevance_llm` is `None` exactly when the lane is `None`, and the lane is `None` when
`l1_semantic_activation` holds no live row for the org. `is_semantic_activated` is **fail-closed
by design**.

> **`no_model_wired = 251` is not a bug. It is a switch that was never turned on for this tenant —
> the same class as the L3 domain activation, one layer down.**

That is a better finding, not a smaller one: it means Layer 1's judgment has never run in
production on the pilot, and nothing in the code needs changing to start it.

It also exposes a second fact worth carrying: there are **two relevance paths**, and only one is
batched. `RelevancePage` is *"the seam `assess_relevance` could not be"*; `pipeline.py:1272` hands
it **one candidate at a time**. Turning activation on routes traffic to the batched seam.

---

## The shape

```
L1 · Enterprise Signals
├── S1 · Judgment activation          ← smallest, largest effect, nothing to decide first
├── S2 · Object placement             ← one decision, four consequences
├── S3 · The signal bundle            ← M9.C1
├── S4 · The evidence-need door       ← M9.C2
└── S5 · Operational readiness        ← tracked, not ours to build
```

| Section | Functions | Components | Units |
|---|---|---|---|
| S1 Judgment activation | 2 | 4 | 4 |
| S2 Object placement | 2 | 5 | 5 |
| S3 The signal bundle | 3 | 6 | 6 |
| S4 The evidence-need door | 3 | 6 | 6 |
| S5 Operational readiness | — | — | 3 (tracked) |
| | **10** | **21** | **21 + 3** |

---

# S1 · Judgment activation

> **What is true now.** The pilot has no live row in `l1_semantic_activation`. Every ambiguous
> event takes the fail-open at `RULE_NO_MODEL_WIRED` with authority **3000** — the same value the
> cascade gives an unknown actor, because that is exactly what it means: *nobody decided*.
> Measured: **251 events**. `ambiguous_over_budget = 0`, so the budget allocator is healthy.

> **What must be true.** Relevance judgment runs on the pilot through the **batched** seam, and the
> change is visible as a histogram that moved, not as a claim.

### F1.1 · Prove the state before changing it

**C1.1.1 · Read the activation and the histogram**

- **U-S1-01** — a probe that reports, per org: whether `l1_semantic_activation` holds a live row,
  and the full `relevance_rule` histogram.
  - *artifact* `scripts/l1_relevance_state.py`
  - *verify* `uv run --no-sync python scripts/l1_relevance_state.py --org <pilot>` exits 0 and
    prints both
  - *why* the before-number has to exist before the after-number means anything

**C1.1.2 · Pin the fail-open so it is never "fixed"**

- **U-S1-02** — a test pinning that `assess_relevance(..., llm=None)` returns `no_model_wired`,
  keeps the event, and scores authority **3000**.
  - *artifact* `tests/capture/esqe/test_relevance_fails_open.py`
  - *verify* `uv run --no-sync pytest tests/capture/esqe/test_relevance_fails_open.py -q`
  - *why* ⛔ the fail-open is **correct** and somebody will eventually read `no_model_wired` as a
    bug and make it drop. Losing 251 events would be far worse than not judging them

### F1.2 · Turn it on, and prove the lane exists

**C1.2.1 · The row, and the receipt that it changed the pass**

- **U-S1-03** — the activation row for the pilot, plus a receipt that the `SemanticLane` was
  **actually constructed** — not merely that the row exists.
  - *artifact* `genios_engine/platform/activation.py`
  - *verify* `uv run --no-sync pytest tests/platform/test_semantic_activation_builds_the_lane.py -q`
  - *why* ⛔ `l3_activation` shipped with a reader, a gate, an erasure row, an admin API and a
    report — **and no caller**. Never again ship a switch that cannot prove it changed the pass

**C1.2.2 · Measure the move**

- **U-S1-04** — re-run the probe and assert the shape changed: `no_model_wired` → 0, and the
  `llm5_*` buckets non-zero.
  - *artifact* `scripts/l1_relevance_state.py`
  - *verify* `uv run --no-sync python scripts/l1_relevance_state.py --org <pilot> --assert-judged`
  - *why* a switch is finished when the histogram moved, not when the row was written

**Impact when S1 is green**

| | |
|---|---|
| 251 events a sweep stop reaching L2 at authority 3000 | they arrive judged, at `llm5_business` 6000 or refused |
| relevance traffic moves to the **batched** seam | per-page prompts instead of per-event calls |
| `llm_share_bp` becomes reportable | *"the model sees under 5%"* becomes a measured rate, not a hope |
| the drop ledger gains real components | `qualification_drops` starts recording a judged relevance instead of "nobody decided" |

**Cost** — one model call per ambiguous batch per page, bounded by the shared `CostGovernor` that
S2's extractor already uses. **One governor, one ledger** — two would be *"the second budget nobody
reconciles."*

**Risk** — spend rises on the pilot from ~0 for this component. The governor caps it; the probe in
U-S1-04 is what tells us where it landed.

---

# S2 · Object placement

> **What is true now.** Four objects the Atlas wants at L1 are elsewhere or partial:

| Object | Now | Where |
|---|---|---|
| open question | above L1 | `ASK_KINDS` · `is_ask` · `context/open_loops.py` |
| meeting follow-up link | above L1 | `context/meeting_touch.py` |
| condition | split | L1 has `Commitment.is_conditional` + `condition_text`; `DormantCondition` is `context/correlation_timeline.py` |
| thread terminal state | partial | signal-level in `esqe/lifecycle.py`; thread-level does not exist |

> **What must be true.** One rule, written once, that says whether **L1 produces the object or the
> evidence for it** — and four placements pinned by tests so nothing drifts back.

### F2.1 · Decide once

**C2.1.1 · The rule**

- **U-S2-01** — record the rule and the rejected alternative where the code reads it.
  - *artifact* `docs/LAYER_MAP.md` + `genios_engine/LAYERS.py`
  - *verify* `uv run --no-sync pytest tests/test_layer_topology.py -q`
  - *why* this is the **same decision** as correlation placement and absence signals. Answering it
    per-object is how three different answers end up in one codebase

**Recommendation on record.** *L1 produces the evidence; L3 produces the object.* It is what the
code already does in every case, it keeps L1 free of graph reads — which decision 2 requires — and
the alternative moves four producers downward for a naming benefit.

### F2.2 · Pin each placement

Each unit is a **guard**, not a move — it fails if the producer changes layer.

- **U-S2-02** — open question: the producer stays in `context/`, and L1's evidence for it
  (`ASK_KINDS` inputs) is named. *verify* `pytest tests/capture/test_object_placement.py -q -k ask`
- **U-S2-03** — meeting follow-up link: producer in `context/meeting_touch.py`; L1 supplies the
  calendar and thread evidence. *verify* `… -k meeting`
- **U-S2-04** — condition: L1 keeps `is_conditional` + `condition_text`; `DormantCondition` stays
  L3. ⛔ **The split is the point** — `parse_condition` refuses what it cannot ground, and that
  refusal is what the `condition_now_true` angle gates on. Collapsing the split would destroy the
  refusal queue. *verify* `… -k condition`
- **U-S2-05** — thread terminal state: ⛔ **genuinely missing at thread level.** Either build it at
  L3 beside the other thread state, or declare it deferred with a reason in `deferrals.yaml`.
  *verify* `… -k thread_terminal`

**Impact when S2 is green** — four recurring arguments stop recurring, and the L1 scope for S3's
bundle is finally bounded: a bundle that does not read the graph cannot carry objects that need it.

---

# S3 · The signal bundle

> **What is true now.** No bundle exists. Related signals arrive at L2 as separate events, and the
> coverage receipt — which **does** exist, per source and frozen — is carried on the signal, not on
> a group.

> **What must be true.** L2 receives one bundle per group of incoming signals, carrying the
> candidate relationships and the coverage that licenses a negative claim about them.

### F3.1 · The contract and its store

**C3.1.1 · The type**
- **U-S3-01** — `QualifiedEnterpriseSignalBundle`: signals, entities, candidate relationships,
  `unresolved[]`, coverage receipt.
  - *artifact* `genios_engine/contracts/signal.py`
  - *verify* `uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q`
  - ⛔ the receipt **reuses** `SourceCoverage` — per source, never blended. *"A tenant with complete
    calendar coverage and 8% email coverage has two different licences to make a negative claim,
    and one blended number would grant the stronger one to both."*

**C3.1.2 · The table**
- **U-S3-02** — `migrations/0187_signal_bundle.sql`, keyed so a replayed signal is idempotent.
  - *verify* `uv run --no-sync pytest tests/platform/test_migrations_apply.py -q`
  - ⛔ **that test file does not exist yet** — see "Three unsound verifies" below

### F3.2 · Assembly

**C3.2.1 · The grouper**
- **U-S3-03** — incoming signals only, joined by entity, thread, time window, commitment, meeting.
  - *artifact* `genios_engine/capture/esqe/bundle.py`
  - *verify* `uv run --no-sync pytest tests/capture/esqe/test_bundle.py -q`
  - ⛔ **it must not read the graph.** The moment it does, L1 imports L3 and
    `test_layer_topology.py` fails the build. This is decision 2 made concrete

**C3.2.2 · The coverage receipt on the group**
- **U-S3-04** — assembled from `signal_coverage` + the window read; unknown stays `None`.
  - *verify* `uv run --no-sync pytest tests/capture/esqe/test_bundle_coverage.py -q`
  - ⛔ **never 100% by default.** *"Defaulting it full would write Gemini's failure into our own
    contract."*

### F3.3 · Emission, measured

**C3.3.1 · Beside, not over**
- **U-S3-05** — the publisher emits a bundle **beside** `qualified_signals`.
  - *artifact* `genios_engine/capture/esqe/publisher.py`
  - *verify* `uv run --no-sync pytest tests/capture/esqe/test_publisher_emits_a_bundle.py -q`
  - ⛔ the publisher is *"the one crossing"*. It must keep wiring
    `validate_publication` rather than growing a second copy of V-1…V-7

**C3.3.2 · The comparison**
- **U-S3-06** — both paths counted on one sweep before either is retired.
  - *verify* `uv run --no-sync pytest tests/capture/esqe/test_both_paths_are_counted.py -q`
  - *why* the same rule `card_source.COMPARISON_KEYS` already keeps at L5

**Impact** — L2 can reason about a group instead of re-deriving it, and the bundle is the object
`EvidenceNeed` will attach to.

---

# S4 · The evidence-need door

> **What is true now.** Nothing. L2 can only HOLD and wait. `context/residue.py` already computes
> the demand — `signal_unreached` measures *"the Layer 1 verdicts no Layer 2 reading consumes"* —
> and it reaches the model angles and stops there.

> **What must be true.** L2 names one missing fact; L1 goes and gets it; the situation that was
> held clears itself.

### F4.1 · The contract and its store

- **U-S4-01** — `EvidenceNeed`: question, why it changes the decision, acceptable and
  **unacceptable** sources, time range, visibility, cost limit, expiry, idempotency key.
  - *artifact* `genios_engine/contracts/evidence.py`
  - *verify* `uv run --no-sync pytest tests/contracts/test_evidence_need.py -q`
  - ⛔ *unacceptable* sources are not decoration: a vendor quote email may not stand in for a signed
    contract, and the contract is where that is enforceable
- **U-S4-02** — `migrations/0188_evidence_needs.sql` — open / met / unavailable, never hard-deleted.

### F4.2 · The executor

- **U-S4-03** — fetch the full thread. *verify* `pytest tests/capture/test_evidence_need_executor.py -q -k thread`
- **U-S4-04** — backfill older history beyond the window. *verify* `… -k backfill`
- **U-S4-05** — re-extract an attachment. *verify* `… -k reextract`

Each bounded by the need's own cost limit and expiry. ⛔ **An unavailable need closes with a
reason** — it never sits open forever, because a permanently open need is a HOLD that can never
clear, which is the failure this section exists to end.

### F4.3 · The wire

- **U-S4-06** — `residue.signal_unreached` raises an `EvidenceNeed`.
  - *artifact* `genios_engine/context/residue.py`
  - *verify* `uv run --no-sync pytest tests/context/test_residue_raises_a_need.py -q`
  - ⛔ **this is the edge the whole architecture is missing.** The measurement half already exists;
    only the wire does not

**Impact** — the 60-day wall becomes askable rather than absolute, and `"message 1 of 1"` becomes
recoverable for the threads that matter instead of only for mail arriving from now on.

---

# S5 · Operational readiness — tracked, not ours

| Item | State | Owner |
|---|---|---|
| **OCR has never run** | 122 document rows, **zero** ever carried an engine; 830 `ocr_unavailable`. The flag has been right since 10 Sep; the tesseract image never reached the host | Harsh — **deploy, from the Dockerfile** |
| **Backfill 60 → 365** | the pilot connection still fetches 60 days; 6- and 12-month questions stay structurally unanswerable | Harsh, after `0184` |
| **37 events carry no domain** | 125 of 162 tagged (77%) | open — investigate after S1, because judged relevance may change the denominator |

⛔ **The heartbeat does not run in production** (`../01-BASELINE.md` §3). It is upstream of the
attachment drain that feeds OCR. Nothing in S5 can be called fixed until it runs.

---

## Three unsound verifies, named before we start

1. **`tests/platform/test_migrations_apply.py` does not exist**, and `U-S3-02` and `U-S4-02` both
   name it. Add the unit that creates it, or change both verifies.
2. **`U-S2-01` verifies on `test_layer_topology.py`, which passes today.** The test must be
   extended by the unit, or the unit goes green having changed nothing.
3. **`U-S1-03`'s receipt** must assert the lane was *constructed*, not that the row exists. A row
   is not a pass.

## Order

```
S1 (nothing to decide first, largest measured effect)
  → S2 (one decision, bounds S3's scope)
    → S3 (the bundle)
      → S4 (needs the bundle to attach to)
S5 runs alongside, owned elsewhere
```

## What we are deliberately NOT doing in L1

| | Why |
|---|---|
| the four-value importance split | three of four already exist with the right owners; only L2 **materiality** is missing, and it is L2's |
| an untrusted-content boundary | built, and stronger than specified — schema enforcement, not prompt text |
| version and supersession | built; `lifecycle.py` even decided the pointer direction where two specs disagreed |
| coverage receipts | built, per source, frozen at the observation moment |
| "six object types" as an L1 build | two exist, two are partial, two are a placement decision — see S2 |
