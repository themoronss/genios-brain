# Layer 2 — Architecture

**Measured 2026-09-24** against `speedrun008`. Every number below was counted, not quoted.

---

## 0. ⛔ The finding that unifies every defect below

**Layer 2's dominant failure mode is not a wrong answer. It is a correct refusal nobody can see.**

```
63 of 159 situations held     refusal correct (528–1920 vs a floor of 2500)   no surface says so
33 support situations dark    a spelling seam                                 "why the miss was invisible"
fundraising entirely dark     correct — no corpus authored                    every tenant, silently
21 untraceable promises       correct, and ten were carded first              "promises nobody made"
```

`situation_bso.py:565` calls it *"the fifth time this codebase has carried a refusal that was right
and invisible."* **The domain compiler's `UNROUTED` is the sixth.**

L1 wrote the rule for signals — **`DROP ≠ DELETE`**. L2 has the refusals and not the ledger, which
is why the layer reads as broken when it is mostly correct and mute.

---

## 1. The contract, in one sentence

> **Layer 2 takes what Layer 1 saw, reads it with the domain's expertise, and states what is
> happening — separating what was observed from what was inferred, and pointing every word at a
> receipt.**

`QualifiedEnterpriseSignal` in. `BusinessSituationObject` out.

### The one rule that defines the boundary

```
Observation  ≠  Inference  ≠  Hypothesis
```

Three fields, three write authorities. **A model may propose an inference and may never write an
observation.**

---

## 2. Where the code lives

```
genios_engine/context/     111 files   48,322 LOC      ← larger than L1's 42,311
```

| | |
|---|---|
| root modules | **57**, 30,477 LOC |
| code subpackages | **8**, 17,845 LOC |
| **content subpackages** | **5** — `anchors` `exclusions` `groupings` `observations` `seed` — YAML and README, **no `.py` at all** |

⛔ **Those five are a declarative layer, not dead code.** `exclusions/whose-turn-is-it.yaml`,
`groupings/works-at.yaml`, `observations/kinds.yaml` — vocabulary the engine reads. Treating them as
empty directories is how a vocabulary change gets shipped as a code change.

### The ten largest modules

```
situation_bso.py          2,133      ← the boundary builder, the biggest thing in the layer
pipeline.py               2,049
outreach_situations.py    1,898
support_situations.py     1,749
runner.py                 1,582
importance.py             1,371
graph_store.py            1,180
correlation_dependency.py 1,154
situations.py             1,140
correlation_timeline.py   1,126
analytic/  (11 files)     8,768      ← the largest subpackage by a wide margin
```

---

## 3. The seven groups

| group | what it answers | code | components |
|---|---|---|---|
| **L2.1** | Signal Intake — *did it arrive intact?* | `pipeline.py` `qes_adapter.py` `backfill.py` `runner.py` | 4 |
| **L2.2** | Evidence Graph — *what is true?* | `graph_store.py` `derived*.py` `identity.py` `merge.py` `canon.py` `projections.py` `read_models.py` `fact_visibility.py` | 8 |
| **L2.3** | Correlation — *what belongs together?* | `correlation.py` + 9 `correlation_*.py` | 9 |
| **L2.4** | Situation Assembly — *what candidate does that make?* | 7 `*_situations.py` · `situations.py` · `situation_bso.py` · `attention` `importance` `availability` `waiting` `open_loops` · `analytic/` `patterns/` `lifecycle/` `quality/` | 10 |
| **L2.5** | Domain Compiler — *whose doctrine reads it?* | `packs/compiler` (Plane D) · `reason/domain_shadow.py` | 4 |
| **L2.6** | Context Reasoning — *what does it mean?* | `angles/` `llm/` · ⛔ **the reasoner does not exist** | 3 |
| **L2.7** | Gate, Intelligence Graph, Publication | `situation_publisher.py` · `contracts/situation.py` · `context_situations` | 6 |

**44 components. 46 planned units across the eight steps.** Build order is units → components →
groups → layer, because a component assembled from unbuilt units is a diagram.

---

## 4. The groups in detail

### L2.1 · Signal Intake — *get it across the seam without losing it*

| component | units | files | state |
|---|---|---|---|
| L2.1.1 QES intake | 3 | `pipeline.process_event` | ✅ live — **no model call**, by design |
| L2.1.2 Adapter | 2 | `qes_adapter.py` | ✅ live |
| L2.1.3 Backfill | 3 | `backfill.py` | ✅ live |
| L2.1.4 Sweep orchestration | 4 | `runner.py` | ✅ live |

⛔ **This seam now carries five conversation fields it never used to** — `thread_key`, `direction`,
`turn_index`, `thread_depth`, `ball_in_court`, landed by L1 step 18. **Nothing in L2 reads them
yet**: `attention.py:66` still scores `ball_in_court == "us"` off its own weaker recomputation from
Gmail labels. That is a one-line change and it belongs in L2-7.

### L2.2 · Evidence Graph — *what is true, and who proved it*

| component | units | files | state |
|---|---|---|---|
| L2.2.1 Node identity | 4 | `identity.py` `canon.py` `merge.py` | ✅ versioned, `canonical_key` |
| L2.2.2 Fact writing | 5 | `graph_store.write_fact` | ✅ **authority-aware, out-of-order-aware** |
| L2.2.3 Observations | 3 | `write_observation` + kin | ✅ live |
| L2.2.4 Edges | 2 | `write_edge` | ✅ live |
| L2.2.5 Discrepancy | 2 | `write_discrepancy` | ✅ conflicts held, not overwritten |
| L2.2.6 Visibility | 3 | `fact_visibility.py` | ✅ **strong — do not touch** |
| L2.2.7 Projections | 3 | `projections.py` `read_models.py` | ✅ live |
| L2.2.8 Slice for the reasoner | 5 | — | ⛔ **NEW · L2-3** |

`write_fact`'s signature is the discipline:

```python
write_fact(subject_node_id, field, value, value_type, confidence, occurred_at,
           event_id,       # which event
           evidence,       # what proof
           source, authority_rank)
```

⛔ **`event_id` and `evidence` are not optional.** Nothing can be written here without a receipt —
the *"a model may not invent a fact"* rule is already enforced at the storage layer.

### L2.3 · Correlation — *what belongs together* · **9 correlators, zero model calls**

conversation · dependency · domain · history · membership · organization · people · resource ·
timeline.

> *"Nine of its correlators call none... the same graph re-swept tomorrow by a different model
> version produces the same answers."*

**This group is not changing.** It is the replayable half, and the plan spends replayability only on
interpretation.

### L2.4 · Situation Assembly — *the candidate*

| component | units | files | state |
|---|---|---|---|
| L2.4.1–7 Seven producers | ~24 | `analytic` `attention` `blocker` `condition` `meeting` `outreach` `support` | ✅ live, deterministic |
| L2.4.8 Candidate builder | 6 | `situation_bso.py` (2,133 LOC) | ✅ live |
| L2.4.9 Scoring | 4 | `importance.py` `attention.py` | ✅ **integers only, no model** |
| L2.4.10 State | 5 | `lifecycle/` `waiting` `open_loops` | ✅ live |

### L2.5 · Domain Compiler — *whose doctrine reads it*

| component | units | files | state |
|---|---|---|---|
| L2.5.1 Capability routing | 4 | `packs/compiler/capability_resolver.py` | ✅ live |
| L2.5.2 Domain mapping | 3 | `_L2_TO_L3_DOMAIN` | ⛔ **incomplete — L2-4** |
| L2.5.3 Five brains | 5 | `packs/brains/` | ⚠️ **four exist; Persona is missing** |
| L2.5.5 **Admission** | 4 | `Domain Expertise/` · `_tools/admit.py` | ⛔ **200 of 534 admissible — 37%** |
| L2.5.4 Package assembly | 4 | `ExpertisePackage` — 22 fields | ✅ live |

⛔ **The measured defect:**

```
L2 domains    admin · sales · support · FUNDRAISING · general
L3 corpora    admin · sales · customer_support
                               fundraising → NOTHING     general → NOTHING
```

and `live_lane()` returns `False` when the domain is `None` — **no package, no signal, on every
tenant configuration.** The pilot is a fundraising founder.

The four brains present are Expert · Organization · Behavior · Adaptive. **Persona is the fifth and
does not exist** — not in `BrainKind`, not as an `ExpertisePackage` lane. It holds *how this kind of
company and this role works*, which is what makes a tenant legible on day one, before Behavior has
any history. **Goals belong in Organization Brain**, whose machinery already reads written rules and
verifies the quote byte-for-byte — a goal needs a category row, not a subsystem.

### L2.6 · Context Reasoning — *what it means* · ⛔ **the hole**

| component | units | files | state |
|---|---|---|---|
| L2.6.1 Angles | 4 | `angles/` (1,495 LOC, 4 angles) | ✅ live doctrine |
| L2.6.2 Asker | 2 | `llm/` (197 LOC) | ✅ live |
| L2.6.3 **Context Reasoner** | 6 | — | ⛔ **no L2 site — but the PATTERN exists · L2-5** |

> *"An ANGLE is a question asked of one of those queues, and nothing else. **It is not a licence to
> read the graph.**"*

⛔ **Corrected by the pre-flight pass.** Saying the reasoner "does not exist" was too strong. Plane R
already runs `interpretation.py` — **R-1, the ambiguity interpreter** — whose contract is stronger
than anything this plan wrote:

> *"The model returns `{classification, confidence_bp}` **as evidence**; a unit reads it like any
> other input; **the formula decides**."* · *"**IT CANNOT RAISE CONFIDENCE.**"*

And every model consult in Plane R passes **one door**:

> **"THERE IS EXACTLY ONE C5 GATE, AND IT IS `reason/bundle/gate.RSiteGate`... no R-site may call a
> model directly."** — activation · precondition · budget · cache · tier+timeout · **the caller's
> validator** · deterministic fallback, all recorded.

**So L2 does not build a gate. It registers a site and writes a validator.** See
[`03-PRE-FLIGHT.md`](03-PRE-FLIGHT.md) §9.

Four angles exist, each asked only of a queue the deterministic layer itself refused. The reasoner is
a **different site with a different contract** — not a fifth angle.

### L2.7 · Gate, Intelligence Graph, Publication

| component | units | files | state |
|---|---|---|---|
| L2.7.1 v1 → v2 upgrade | 3 | `upgrade_situation` | ✅ live |
| L2.7.2 Eight admission laws | 8 | `validate_situation` | ✅ live |
| L2.7.3 **Interpretation gate** | 5 | — | ⛔ **NEW · L2-6** |
| L2.7.4 Publication | 4 | `publish_situation` | ✅ live |
| L2.7.5 Intelligence Graph write | 3 | `context_situations` | ⚠️ **table exists, wrong writer** |
| L2.7.6 Card seam | 6 | `deliver/pipeline.py` | ⛔ **reads SIGNALS · L2-7** |

---

## 5. The engine law — where a model may run

| package | metered call files |
|---|---|
| `capture` (L1) | 3 — `extract` · `relevance_gate` · `domain_proposal` |
| **`context` (L2)** | **2, and neither on the production path** |
| `packs` (Plane D) | 4 |
| **`reason` (Plane R)** | **13** |
| `deliver` | 2 |
| `executive` · `feedback` | 0 |

### After this plan, L2 gains exactly two call sites

```
Context Reasoner    per SITUATION    Haiku → Sonnet on escalation
Domain miss         per UNROUTED     Haiku, proposes never routes
Validation gate     ⛔ NONE — deterministic, and that is what makes Haiku safe
```

⛔ **The cost law:** the call attaches to the situation, not the event. 465 threads → ~40 situations
→ ~40 calls. Per event it would be 465. **That is a 10× difference decided by placement, not by
model.**

---

## 6. Two graphs

| | Evidence Graph | Intelligence Graph |
|---|---|---|
| holds | facts · entities · events · edges | situations · inferences · hypotheses |
| tables | `graph_nodes` `graph_facts` observations edges | `context_situations` |
| written by | deterministic, as data lands | ⛔ **today: correlators. Planned: a validated reasoner** |
| may a model write? | **never** | yes — every row carrying `evidence_refs` **into** the Evidence Graph |
| expiry | facts do not expire | interpretations carry `valid_until` |

**The split already exists physically.** The intelligence half is filled by the wrong writer —
`situations.py`, `periodic.py`, `meeting_touch.py`, `document_register.py`.

---

## 7. The invariants

1. **No model writes a fact.** `write_fact` requires `event_id` and `evidence`; the reasoner never
   calls it.
2. **Every interpretation cites, and the citation resolves.** An unresolvable ref is a fabricated
   receipt and is refused.
3. **Unknown survives.** Empty `unknowns` under low coverage is refused, not accepted.
4. **Integers only.** Basis points, V-7, no floats anywhere.
5. **No clock inside logic.** `eval_time` is a parameter, as in L1.
6. **The slice is handed, never fetched.** A reasoner that queries the graph cannot be replayed.
7. **Correlation stays deterministic.** The same graph re-swept tomorrow assembles the same
   candidate.
8. **A refusal has a row.** `REFUSE ≠ DELETE`, `UNROUTED ≠ silence`.

---

## 8. TODAY versus TARGET

```
TODAY
  QES ─→ graph ─→ correlate ─→ situation ─→ [expertise, unread] ─→ ⌀
   └──────────────────────────────────────────────────────────────→ CARD
                                                          one signal → one card

TARGET
  QES ─→ EVIDENCE GRAPH ─→ correlate ─→ candidate
                                            + slice + ExpertisePackage + goals
                                                  ↓
                                          CONTEXT REASONER     (Haiku)
                                                  ↓ proposal
                                          VALIDATION GATE      (free)
                                                  ↓
                                          BUSINESS SITUATION ─→ INTELLIGENCE GRAPH
                                                  ↓
                                                CARD           one situation → one card
```

---

## 9. How to verify this architecture holds

```bash
# import direction — a build failure, not a review nit
pytest tests/test_layer_topology.py -q

# every model call site is metered — fails in both directions
pytest tests/test_every_llm_call_site_is_metered.py -q

# the reasoner cannot write a fact
pytest tests/context/test_reasoner_cannot_write_observed_facts.py -q

# every interpretation resolves to a receipt
pytest tests/context/test_every_claim_resolves.py -q

# the domain mapping is total over domain_spec
pytest tests/reason/test_domain_mapping_is_total.py -q

# unroutable situations are counted, never silent
pytest tests/reason/test_unroutable_is_counted.py -q

# the card collapse — the headline number of this plan
scripts/card_collapse_report.py --org <pilot>
```

---

## 10. Where to go next

[`00-OVERVIEW.md`](00-OVERVIEW.md) for the contract · the eight `step-*.md` files for the plan ·
[`../STATUS.md`](../STATUS.md) for what is done.
