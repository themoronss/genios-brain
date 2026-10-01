# Step 4 · Every claim carries a receipt — findings

**Run:** 2026-09-23 · premise checked against code and PRODUCTION (read-only) before any code
**Verdict:** hermetic work **COMPLETE** · nothing for Harsh to deploy · **no migration needed**

---

## 1. Premise check — the *reason* in the plan was wrong, the *work* was right

| Written premise | Verdict |
|---|---|
| Three lanes (`roles`, `availability`, `questions`) cannot carry an `EvidenceSpan` | ✅ confirmed |
| `esqe/detector.py` fires three real signal types off them | ✅ confirmed — lines 417, 424, 469 |
| Typing them will lift `relationship_change` over the qualification floor | ❌ **WRONG** |

### Why metric 3 was wrong, measured

Production, pilot org, `relationship_change`:

```
published   4
DROPPED    54
band    880 – 1560 bp        (the CEILING sits BELOW the floor)
best row:   monetary_exposure_bp 0 · deadline_proximity_bp 0
```

Those zeros are **not** an artifact of the untyped bag. They are policy:

```python
normalize.DATE_POLICY[RELATIONSHIP_CHANGE]   = none
normalize.AMOUNT_POLICY[RELATIONSHIP_CHANGE] = claims_only
```

A role change genuinely states no amount and no deadline. ALG-17 reads `primary_date` and
`primary_amount`, both `None` **by design**, so typing the lane changes the score by **zero basis
points**. That a type's ceiling sits below the floor is a **floor** question → **step 8**.

> **Fourth step in a row whose written premise production corrected.** Step 2's was *"the gate
> deletes bounces"*, step 3's was *"`array_agg[1]` loses signals"*, step 4's was *"typing lifts
> the score"*. All three caught by measuring, none by reasoning.

### What the step was actually worth doing for

1. a citable receipt on every claim — benchmark P1 and P3 both quote the source;
2. zero predicates firing on a claim that cannot carry one;
3. a per-claim confidence for ALG-13 to compose.

All three delivered.

---

## 2. What was built

### 2.1 Three new claim types — `contracts/extraction.py`

| Type | Fields |
|---|---|
| `RoleAssertion` | `party · role · evidence: list[EvidenceSpan] · confidence_bp` |
| `AvailabilityWindow` | `person? · kind · from_text (alias from) · to_text (alias to) · coverage_person? · evidence · confidence_bp` — see §2.6 for why `person` is optional |
| `OpenQuestion` | `text · asked_by · asked_of · evidence · confidence_bp` |

`questions: list[OpenQuestion]`, `roles: list[RoleAssertion]`, `availability: list[AvailabilityWindow]`.

**Two lanes deliberately NOT promoted.** `topics` is *"free text by design; topics are for
retrieval and grouping, not rule matching"* and `implied_actions` is *"what the message implies
somebody should do, in the model's words"* — judgements about the message, not claims about the
world. A receipt on a judgement adds ceremony without adding truth. Pinned by
`test_a_label_lane_is_deliberately_left_alone`.

### 2.2 The three lanes go through the REAL binder — `semantic/extractor.py`

This is the half the plan called *"remaining"* and it is the half that mattered.

The first implementation used a separate lenient reader (`_promoted_lane`) that defaulted
`evidence=[]`. That built claims **schema rule S-4 then refuses** — *"a claim with no receipt is
a guess"* — so one unquotable question triggered a repair retry and then a **parked extraction
that lost every commitment, amount and decision in the same message**. Caught by
`tests/capture/test_screen_semantics.py`, which is a harness test and had no business being the
thing that found it.

Fixed properly: `questions`, `roles` and `availability` joined `CLAIM_FIELDS`, so they now run
the same path as every other claim —

```
draft  →  bind_evidence  →  _build_claim  →  S-1..S-9
```

* a claim that **cited nothing but whose words are in the text** gets a synthesized span at
  `bp * 7 // 10`;
* a claim whose words are **nowhere** is dropped and counted;
* **S-4 then holds by construction**, and `_promoted_lane` was deleted.

Needles (`_NEEDLE_KEY`) — the field whose value is most likely to be the source's own words:

| Lane | Needle | Why |
|---|---|---|
| `roles` | `party` | *"Priya is taking this over"* puts the NAME in the text; the role is usually paraphrase |
| `availability` | `person` | the claim's subject, consistent with every other lane. It is optional (§2.6), so an unnamed window that also cited nothing produces an empty needle and is dropped — correct, because `_POLICY[AvailabilityWindow]` is DROP anyway |
| `questions` | `text` | a question is nearly always asked verbatim |

### 2.3 ALG-08 now grades them — `validate/spans.py` + `contracts/extraction.py`

**Found by a failing test, not by reading.** After promotion, `test_schema.py` began failing S-7
post-verification: the span on a `roles` claim stayed unverified while its copy in `all_evidence`
came back verified, so the two were no longer equal and S-7 said a claim-carried span was missing
from the index.

The symptom was S-7. The defect was that **ALG-08 never walked the three lanes at all** —
`evidence_from_claims()` did not list them and `apply_verdicts` did not rebuild them. So the only
three signal types derived from unverifiable claims were also the only three whose receipts were
never checked.

Both fixed. New `_POLICY` rows, written deliberately because `_policy_drops` raises on an
unlisted type:

| Type | Policy | Reason |
|---|---|---|
| `RoleAssertion` | **KEEP** | filed with `EntityMention` — a role is a fact about a PERSON that L2 resolves; deleting it removes somebody from the graph |
| `AvailabilityWindow` | **DROP** | filed with `ResolvedDate` — an invented *"back on Monday"* suppresses a chase that should have happened |
| `OpenQuestion` | **KEEP** | dropping deletes the awaited item rather than doubting it |

### 2.4 The detector now cites — `esqe/detector.py`

Four predicates that fired on claims and threw their receipts away:

| Signal | Was | Now |
|---|---|---|
| `RELATIONSHIP_CHANGE` / `role_asserted` | no span, and a comment saying so | `_spans(ex.roles)` |
| `AVAILABILITY_CHANGE` / `availability_stated` | no span | `_spans(ex.availability)` |
| `ANOMALY` / `non_routine_structure` | **no span at all** | `_spans(dependencies + decision_states + commitments + questions)` |

`ANOMALY` is the worst of the four: the catch-all, the type most likely to reach a human with no
explanation, was the one type that cited nothing. Four of its five inputs always carried spans and
the rung discarded them; the fifth (`questions`) could not carry one until today.

### 2.5 The L2 seam — `context/qes_adapter.py`

`adapt_qes_extraction` passed these lanes through as `dict(value)`, and projected a question whose
"receipt" was **a copy of its own text** — a citation of itself. Each lane is now projected field
by field and cites the span ALG-08 graded. The dict **shape** L2 reads is unchanged
(`context/pipeline.py` and `extract/availability.py` key off
`party`/`role`/`person`/`kind`/`from`/`to`/`evidence_text`), so this changes where the words come
from, not the wire.

### 2.6 `AvailabilityWindow.person` is OPTIONAL, and that was a modelling error found late

`person` shipped as required. `tests/test_availability_signal.py` then refused an out-of-office
that names nobody — and that is the commonest availability claim there is. The consumer already
read it the other way:

```python
def _person(value: object) -> str | None:
    """A claim's person / cover → a clean identifier, None when it names the author."""
```

So `person: str | None = None`, with `None` meaning **the message's own author**. Requiring a name
would have forced the extractor to invent an identity the message never stated. `coverage_person`
got the same validator: absent is a real answer, **blank is not** — `""` renders as an empty name
beside a real one.

`_build_claim` now requires only `kind`. The needle stays `person`, so an unnamed window that also
cited nothing produces an empty needle and the binder drops it — which is correct rather than a
gap, because `_POLICY[AvailabilityWindow]` is DROP and it would be deleted one stage later anyway.

### 2.7 THE ONE THAT WOULD HAVE BROKEN PRODUCTION — `_rehydrate_legacy_lanes`

`adapt_qes_extraction` rehydrates cached rows with `ExtractionResult.model_validate(...)` **on the
live L2 path**. Every row already in `l1_extraction_results` carries the old shape. Without a
read-side migration the promotion would not merely change the wire —

> **every cached extraction in every tenant becomes unreadable, and Layer 2 stops receiving
> anything from the cache on the day it ships.**

The cache is keyed on content version and only turns over when a message changes, so *"it will age
out"* is not an answer for a corpus nobody re-sends.

`ExtractionResult._rehydrate_legacy_lanes` (a `mode="before"` model validator):

* a bare string in `questions` → `{"text": <the string>}`;
* `evidence_text`, the free receipt string the old shape carried → a **PROBE** span (the model's
  own words at offsets `0..len`, `verified=False`) — the same convention
  `extractor._spans_from_payload` already uses for a model that quoted well and counted badly.
  ALG-08 relocates it. Dropping it would silently delete the only receipt a legacy claim ever had;
* missing `confidence_bp` → `LEGACY_LANE_CONFIDENCE_BP = 5000`, deliberately below anything the
  extractor states for itself, so a rehydrated legacy claim never outranks a graded one.

**It never invents a quote.** An entry with no `evidence_text` gets `evidence=[]` — the honest
*"this claim was stored without a receipt"* — and V-5 downgrades it. A payload already in the new
shape is untouched: every branch keys on a field the new shape does not have.

---

## 3. Files changed

### Production
| File | Change |
|---|---|
| `contracts/extraction.py` | 3 new claim types · 3 lanes retyped · `evidence_from_claims()` walks them · `_legacy_claim` + `_rehydrate_legacy_lanes` |
| `capture/semantic/extractor.py` | 3 lanes into `CLAIM_FIELDS` · 3 needles · 3 builders · `_promoted_lane` deleted |
| `capture/semantic/vocabulary.py` | `UNTYPED_LANES` 3 → 2 · `roles`/`availability` out of `UNTYPED_LANE_KEYS` |
| `capture/validate/spans.py` | 3 `_POLICY` rows · `apply_verdicts` rebuilds the 3 lanes |
| `capture/esqe/detector.py` | 4 predicates now carry receipts |
| `context/qes_adapter.py` | 3 lanes projected claim-wise with real spans |

### Tests
New: `tests/capture/test_every_claim_carries_a_receipt.py` (**16**) · 3 new detector receipt tests.
Eight of the sixteen were written **after** the implementation, because the implementation is what
surfaced the two defects in §2.3 and §2.7 — they pin the legacy read path, the probe span that may
never be stamped verified, the sensitivity case (a new-shape row must NOT be rewritten), the three
ALG-08 policy rows, and the fact that the lanes are in `CLAIM_FIELDS` rather than in a lenient
reader beside it.
Repaired fixtures: `test_schema.py`, `test_spans.py`, `test_l1_contracts.py`, `test_sink_guard.py`,
`test_g9_gate_probes.py`, `test_g56_gate_probes.py`, `test_detector.py`, `esqe/conftest.py`,
`test_screen_semantics.py`, `test_qes_adapter.py`.

Two fixture repairs were made **derived rather than listed**, so the next promotion shrinks them by
itself: `test_l1_contracts.UNTYPED_LANES` reads the annotation, and `test_sink_guard`'s parametrize
reads `UNTYPED_LANES`.

### Migrations
**None.** Nothing about this step touches a table. `l1_extraction_results` stores the extraction as
jsonb and the read-side migration in §2.6 is what makes old rows readable.

---

## 4. Test result

```
FULL SUITE     12470 passed · 1061 skipped · 152 xfailed · 14 failed
                                                            └── all 14 pre-existing
baseline before this step:  12450 passed · 14 failed
```

**Zero regressions**, and 20 more tests passing.

The three pre-existing:

| Test | Why |
|---|---|
| `test_ocr_enablement.py::test_the_wiring_returns_no_engine...` | no local tesseract |
| `test_g9_gate_probes.py::test_probe_deleting_an_org...` | needs Postgres |
| `test_h0_gate.py::test_every_layer_two_placeholder_skips...` | meta-test; reports the 11 L2 failures below |

The 11 L2 failures were confirmed pre-existing by stashing the whole branch, recording the baseline,
and restoring — `comm -13 baseline now` returns **empty**. They belong to L2's angle-audit writer
(`store.py:328`), not to this step.

---

## 5. The cost this step's plan never named

**Found while ticking the done criteria, not while designing the step.** The last unticked
criterion was *"the re-extraction cost is measured and recorded"*, and measuring it turned up a
fact nothing in the plan mentioned:

```
vocabulary_fingerprint()    151b9dabf235   ->   a3d5496aa0d3
```

`UNTYPED_LANE_KEYS` is folded into that digest and the digest is a component of the
`l1_extraction_results` cache key. Removing `roles` and `availability` from the key set therefore
**invalidates every cached extraction in every tenant** — the whole corpus re-extracts on the first
sweep after deploy.

**This is correct behaviour.** The prompt genuinely changed (`schema_gen` renders three lanes as
typed objects now), and the module records exactly why a surviving cache would be worse:

> *"260 cached extractions survived a prompt fix, the numbers did not move, and the conclusion
> drawn was that the fix had not worked."*

A cache that survived this change would make step 4 invisible in production. **What was wrong is
that the plan never named the bill.** Now pinned by
`test_promoting_a_lane_changes_the_vocabulary_fingerprint_and_therefore_the_cache_key`, which fails
the day the digest moves again.

**The rehydration in §2.7 is still needed and is not made redundant by this.** `context/runner.py`
joins `l1_extraction_results xr on xr.processing_key = q.qes_extraction_ref`, where the ref comes
off `qualified_signals` — signals PUBLISHED under the old key. Old rows keep being read for as long
as the signals pointing at them live. Pinned by
`test_an_already_published_signal_still_resolves_to_its_old_extraction_row`.

The row count needs a production read and is §5.3 of the Harsh runbook.

---

## 6. What this does NOT fix

* **It does not raise `relationship_change` above the floor.** See §1. That is step 8.
* **It does not close `relationships` or `scheduling_proposals`.** Both are still
  `list[dict[str, Any]]`. `relationships` is the next candidate; `scheduling_proposals` needs
  L2's scheduler to declare what it reads first.
* **It does not backfill.** Legacy rows rehydrate correctly and their probe spans are graded on
  read; nothing rewrites `l1_extraction_results` in place.
