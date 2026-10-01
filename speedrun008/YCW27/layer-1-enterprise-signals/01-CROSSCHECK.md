# L1 cross-check — built vs. asked, 30 Sep 2026

Every row below was read in the code, not inferred from a plan.

> **Verdict: Layer 1 is the most complete layer in the system, and the Atlas understates it
> substantially.** Of the nine things the Atlas lists as L1's gaps or targets, **five are built**,
> two are built *above* L1, and two are genuinely missing. The largest real L1 defect is not on the
> Atlas's list at all — it is a component that is built, tested, green, and gets no model in
> production.

---

## 1 · The eight qualification improvements — all eight built

| Improvement | Where | Note |
|---|---|---|
| Intent | `contracts/intent.py` · `IntentCategory` | travels **beside** `signal_type`, never instead of it; an unreadable intent arrives **absent**, so "intent read nothing" stays distinguishable from "the model was never asked" |
| Category | `contracts/signal.py` · `SignalType` | **16 types**, not the 15 an earlier note recorded — `DELIVERY_FAILURE` joined them |
| Importance | `esqe/importance.py` (1,262 lines) ALG-17 | plus ALG-18's **qualification floor** in `qualification.py` |
| Business relevance | `esqe/relevance.py` (1,092 lines) | ⛔ **see §4 — this is the defect** |
| Source analysis | `esqe/source_analyzer.py` | per claim |
| Domain mapping | `esqe/domain.py` | hints, not routing |
| Lifecycle | `esqe/lifecycle.py` (1,073 lines) | owns `state`, `supersedes`, and **decides the pointer direction** where two specs disagreed (C-12) |
| Evidence | `EvidenceSpan` on every extracted object | offsets, verifiable |

⛔ **The drop ledger is better than the spec asked for.** ESQE discards ~92% of traffic before it
costs anything downstream, and every refusal writes `qualification_drops` with the computed
importance, **every component that produced it**, the floor it failed, and a payload reference:

> *"A drop with no row is indistinguishable from a bug: nobody can tell a correct refusal from a
> predicate that failed to fire, from an extraction that never ran, from an event that was lost in
> transport. All four look identical — an absence — and the first three are incidents."*

And the floor is **per tenant, as a row**, with an `owner`, and `qualification_floor_changes` is
append-only — *"a module constant is how every tenant ends up sharing one cut-off, and how a
threshold gets changed by a deploy with no owner and no date attached."*

## 2 · Things the Atlas calls `target` that are shipped

| Atlas | Reality |
|---|---|
| Untrusted-content boundary | ✅ `capture/semantic/injection.py` — and **stronger than described**. Three layers, and the module is explicit that only the third holds: the model **cannot set** `_bp` fields, `signal_type` or `visibility`, because they are not in its output schema. *"Prompt text is advisory; the schema is enforcement."* `SCHEMA_ENFORCED_ABSENT` is read **off the contract** rather than retyped, so the test proves the guarantee about the real type |
| Version and supersession | ✅ `esqe/lifecycle.py` |
| Coverage receipt | ✅ `capture/coverage/signal_coverage.py` — per source, frozen at the observation moment, unknown stays `None` |
| Role extraction | ~ `actor_role` exists on the pipeline stage and reaches importance; `Commitment.actor` / `.beneficiary` are typed |
| Entity resolution with doubt | ~ `EntityMention.canonical_hint` is nullable with `confidence_bp`; a full abstain path is not named as one |

**And one the Atlas treats as a doctrine is already a shipped field:** `BusinessFact.standing` is
`observed | judgement`. Observation ≠ inference is enforced in the L1 contract, not just believed.

`UnclassifiedObservation.proposed_kind` is also already there — L1 has a channel for *"I saw
something I cannot type"*, which is the recall mechanism the Atlas asks for under model-first
detection.

## 3 · The six object types — 2 clean, 2 partial, 2 live above L1

| Atlas wants at L1 | Reality | Where |
|---|---|---|
| commitment | ✅ at L1 | `Commitment` — actor · action · beneficiary · due · `is_conditional` · `condition_text` |
| delivery status | ✅ at L1 | `capture/delivery_status.py` + `DELIVERY_FAILURE` |
| condition | ~ partial | L1 carries `is_conditional` + `condition_text`; the **`DormantCondition` object** is `context/correlation_timeline.py` |
| thread terminal state | ~ partial | signal-level terminal states in `esqe/lifecycle.py`; **thread-level does not exist** |
| open question | ❌ above L1 | `ASK_KINDS` · `is_ask` · `open_loops` — all `context/` |
| meeting follow-up link | ❌ above L1 | `meeting_touch` · `meeting_follow_through` — `context/` |

⛔ **This is the same shape as absence signals.** Four of the six are not missing — they live one
layer up. Moving them down is a **decision**, not a build, and it is the same decision as
correlation placement: does L1 produce the object, or does L1 produce the evidence and L3 produce
the object? Answer it once, for all of them.

## 4 · ⛔ The largest real L1 defect, and it is not on the Atlas's list

**`relevance.py` gets no model in production.**

```python
if self._llm is None:
    return self.stats          # `decide` fails open at `no_model_wired`
```

Measured on the pilot: **`no_model_wired` = 251** — the top bucket by a distance.
`ambiguous_over_budget` is **0**, so the budget allocator works; the component simply is not wired.

- It **fails open**, so nothing is lost — 251 events reached L2 **unjudged**, not dropped.
- 1,092 lines, built, tested, green, and **called with no client on the real path.**

This is the six-times defect, and it is the third instance of the same pattern in this codebase:
`l3_activation` shipped with no caller, `analytic/cohort.py` is never injected a client, and now
this. **It is a wiring fix at the composition root, not a build** — the cheapest high-value item
in Layer 1 by a wide margin, and it is not in `tree.yaml`.

## 5 · The importance-split critique is three-quarters wrong

The Atlas says L1 scores importance and urgency, upper layers never re-derive it, and *"the fix is
four separate values with four owners."* Measured:

| Value | Files | Owned by |
|---|---|---|
| `importance_bp` | 34 | `capture` (11) — signal salience |
| `priority_bp` | 18 | `executive` (6) — action priority |
| `urgency_bp` | 19 | `reason` (16) — delivery urgency |
| `salience_bp` | **0** | — |
| `materiality_bp` | **0** | — |

**Three of the four already exist, with the owners the Atlas asks for.** What is missing is L2
**situation materiality** — one value, not four — plus the rename of L1's to salience if we want
the vocabulary to match. That changes this from a four-value refactor across 71 files to one new
value in L2.

## 6 · Live operational problems at L1 that are not code

| | |
|---|---|
| OCR | 122 document rows, **not one** ever carried an engine; 830 `ocr_unavailable`. The flag has been right since 10 Sep — the tesseract image never reached the host. **Deploy, not code** |
| Backfill window | still **60 days** on the pilot; 6- and 12-month questions are structurally unanswerable until 60 → 365 |
| Domain coverage | 125 of 162 tagged (77%); **37 events carry no domain** |
| Heartbeat | does not run in production — 341 attachments stuck at `fetch_failed` |

---

## What this changes in M9

| Unit | Status after cross-check |
|---|---|
| `M9.C1.U01–U05` the bundle | ✅ stands — genuinely missing, and `U04` should **reuse** `SourceCoverage`, never blend a new number |
| `M9.C2.U06–U09` EvidenceNeed | ✅ stands — genuinely missing, and `U09`'s wire is still the highest-value edge |
| **new · wire the relevance model** | ⛔ **add, and put it first.** One injection at the composition root; 251 events a sweep stop arriving unjudged |
| **new · decide where the four objects live** | the open-question / meeting-link / condition-object / thread-terminal question, answered once |
| ~~six object types as an L1 build~~ | ❌ **withdraw as written** — two exist, two are partial, two are a placement decision |
| ~~untrusted-content boundary~~ | ❌ withdraw — built, and stronger than specified |
| ~~version and supersession~~ | ❌ withdraw — built |
| ~~four-value importance split~~ | ❌ **reduce to one** — L2 materiality |

**Order inside L1:** wire relevance → decide object placement → bundle → EvidenceNeed.
The first is a one-line fix with the largest measured effect, and it needs nothing decided first.
