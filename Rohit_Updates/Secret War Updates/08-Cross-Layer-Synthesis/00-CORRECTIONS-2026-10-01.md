# ⛔ CORRECTIONS — the master matrix is stale in 6 of its cells, and wrong in 1

**Added 2026-10-01. Nothing is deleted from `01-Master-Atlas-vs-Code-Coverage-Matrix.md`; this is
an appended correction, because *how* a cell went stale is the part worth keeping.**

**The matrix's own baseline:** `harsh/mvp@b739bd5ca682d09550acc400ed2892c38c8518f8`, **audited
2026-08-22**. **Re-measured against:** the `speedrun008` working tree and production, read-only,
**2026-10-01** — six weeks and one architecture programme later.

> ⛔ **Read as current, this matrix would send the next person to build six things that already
> exist, and to "fix" one thing that is working as designed.**
> Full measurement: `speedrun008/YCW27/08-ATLAS-SCORECARD-L1-L2-L3.md`,
> `.../layer-2-reasoning/13-ATLAS-RECHECK...` and `.../14-PLANE-D-AND-R...`.

**The matrix's own rule, applied to itself.** It opens by distinguishing *Present · Wired · Live ·
Tested · Outcome-proven* and insists the statuses are "intentionally not collapsed". That care is
why most of it has held. What it had no mechanism for is **time**: a cell that was a measurement on
2026-08-22 is a claim today, and 24 of them were re-taken to find out which.

---

## THE SCORE

    EXPIRED — the matrix is wrong today       6
    STILL TRUE — the matrix is right         11
    ⛔ DISAGREEMENT — a design graded as a gap  1
    PARTLY EXPIRED                            2

**It was right about the hard things and wrong about the built things** — which is the correct way
round for an audit to age.

---

## ⛔ THE ONE CELL THAT IS NOT STALE BUT WRONG

### L2 Context · *"Coverage and missing-context truth"*

> *"Generic unregistered domain declares no expected fields and reports 100% coverage
> (`context/domain_spec.py:14-31,64-99`). **Empty requirements can look complete.**"*

**The behaviour is exactly as described. Grading it a gap is the error.** `domain_spec.py`'s own
header states the decision and the reasoning:

> *"**THE PROPERTY THAT MATTERS: OPEN BY DEFAULT.** An unregistered domain is not an error, not a
> gap, and not a special case… expected fields → none, so coverage is 100% ('we expect nothing, so
> nothing is missing'), never 0% ('we know nothing'). **That second one is the trap.** A registry
> that returns 'no expectations' as 'nothing known' would report every situation in a new domain as
> completely uncovered — **absence read as negative evidence, which this codebase refuses
> everywhere else.** It would make every new domain look broken on the day it was added."*

Both readings of 100% are defensible in isolation. The codebase's choice is the one consistent with
its own first law — *NULL is an answer, and absence is never negative evidence* — which it applies
in `unit_health`, in `capture/coverage`, in `core.impact`'s refusal to fabricate a zero, and in
`situation_absences`. A matrix cell that marks the consistent choice as a gap asks for the
inconsistency.

**Action: correct the cell in the Atlas. There is nothing to change in the code.**

---

## THE SIX EXPIRED CELLS

| Layer | Cell | What the matrix said | What is true on 2026-10-01 |
|---|---|---|---|
| **L1** | Full `QualifiedEnterpriseSignal` boundary | *"**Absent** as Atlas contract"* | `contracts/signal.QualifiedEnterpriseSignalBundle` exists; `capture/esqe/bundle.py` builds it. Needs migration `0186` to persist |
| **L1** | End-to-end source-to-card receipt | *"one authorized query cannot yet prove source span… end to end"* | `platform/funnel.py` carries all five counters — `signals_detected → situations_formed → capability_resolved → decision_emitted → card_delivered`. Needs `0188` |
| **L2** | Bounded context slice | *"**hardcodes** org visibility and `missing_fields=()`"* | `situation_bso.py:2086` → `missing_fields=_missing_paths(situation, facts, neighbor_facts)`. The file itself records the fix at :2029: *"This used to be a hardcoded empty tuple, and an empty `missing_fields` is not a neutral…"* |
| **L2** | Situation candidate generator | *"**No** explicit candidate/discard receipt exists"* | `context/quality/missing.py`, `context/quality/inference.py` and `situation_absences` exist; L3 STEP-03/04/05 added hold → need → clear |
| **L3** | Expert Brain authored depth / Admin expertise | *"**Stub.** 57 files, **all 57 stubs**, zero non-stub, **zero reviewed/accepted** and zero routes"* and *"All 12 non-stub entries are draft/unreviewed, with **zero reviewed or accepted**"* | **155 capabilities, every one `stable` + `approved`, 0 hollow.** Admin **59**, Support **49**, Sales **47**. Measured with the corpus's own `corpus_health()` |
| **L4** | Deterministic orchestrator | *"Seventeen units are registered; the common legacy manifest schedules roughly six. **Registered is not active.**"* | The two counts are **exact** — `CORE_UNITS` is 17, the built-in schedules 7. The conclusion has expired: **22 of 23** units have run in production, and the registry and production agree with no unit on either side the other does not have |

### ⛔ Why the L3 cell expired, and the lesson the code had already learned
The corpus was authored out from under the matrix. `capability_resolver._hollow` carries its own
dated retraction of exactly the same mistake:

> *"at the time this rule was written, 136 of the corpus's capabilities were `stable`, `approved`
> and hash-pinned over a file whose own notes read 'Phase 1 stub'. … ⛔ **THAT COUNT IS HISTORY, NOT
> A FACT ABOUT TODAY'S CORPUS, AND LEAVING IT UNMARKED COST A PLAN.** Measured 2026-09-24 by
> `corpus_health`: **0 hollow of 155.** The corpus was authored out from under this paragraph and
> nothing said so, because **nothing printed the number**."*

The code fixed it by moving the count into a function a test can run. **This matrix has no such
function**, which is why six of its cells had to be re-measured by hand.

---

## THE TWO PARTLY EXPIRED

| Layer | Cell | Correction |
|---|---|---|
| **L1** | Business-signal lifecycle — *"stable `new/active/satisfied/expired/superseded/revoked` signal identity is **absent**"* | It **exists**: `contracts/signal.SIGNAL_STATES = {active, superseded, expired, resolved}`. Four states, not six — `resolved` rather than `satisfied`, and no `new` or `revoked`. Not absent; not the Atlas's vocabulary either |
| **L2** | Typed `BusinessSituationObject` — *"emits one anchor, empty relationships/dependencies and **constant importance**"* | Importance is no longer constant: `context/importance.compose_situation_importance` is used, with `importance_source` recorded in metadata and a **named** fallback for a situation whose events published no live score. The anchor and relationships halves were not re-measured and stand |

---

## THE ELEVEN THAT STILL HOLD — and why that is the useful half

    L1-01  only ~7 distinct providers buildable of 36 catalogued   "catalogued is not connected"
    L1-07  no mandatory typed business roles leave L1              only a derived `subject_key`
    L1-08  RawObject/SourceEvent/GatedEvent do not require visibility   measured: zero declare it
    L1-09  the coverage snapshot is not mandatory on each signal   `coverage_ready: bool | None`
    L2-01  incorrect authority config would be applied consistently
    L2-02  distinct source labels are not independent authorities
    L2-03  first claimant owns a same-name alias
    L2-04  the explicit complete graph views are absent
    L2-05  same-company independent deals can collapse without a deal object
    L2-07  role/source readiness is not in the blocking vector     ← the ConfidenceVector decision
    L2-11  wrong first domain can still enter the wrong view
    L2-12  a tenant replay is missing

**Not one of these is code somebody forgot to write.** They are design decisions, a connector, and
a vocabulary choice — which is why six weeks of building did not move them and why they are the
part of this matrix worth reading.

⛔ **Every line number in the matrix should be treated as a name, not an address.** It cites
`situation_bso.py:144-166`; that file is now **2,133 lines**.
