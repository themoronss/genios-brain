# Step 7 — Intent split and the silent predicates

**Status:** NOT STARTED · **Effort:** days · **Depends on:** 4 · **Engine:** M + D
**Moves:** debuggability; metric 6

> **Re-measure before starting.** Step 4 may itself wake some of the silent predicates.

## 1. Why this step exists

**Two defects, both about not being able to tell what went wrong.**

**a · Intent is buried in a mega-prompt.** LLM-2 is asked for entities, commitments, dates,
amounts, decisions, dependencies, observations **and** intent in one call. When the answer is
wrong you cannot distinguish *"intent was wrong"* from *"the whole extraction was wrong"*.

**b · Four signal types have never fired.** Of 15 types, 395 signals fired 11. Never:
`escalation`, `anomaly`, `information_conflict`, `availability_change`. **Nothing says whether the
tenant had none, or whether the predicate cannot fire.** A predicate that can never fire is
indistinguishable from a correct absence — the same class of bug the drop ledger was built to kill.

## 2. Current status
`contracts/intent.py` is well built — closed enums (`IntentCategory` 8, `Tone` 8, `Formality` 6,
`Band` 6), every one with `unknown`, and an **observation-vs-judgement standing** that ranks
judgements below observations. **That design is correct and must not be rebuilt.** What is wrong is
only *where the inference happens* and *that nothing counts its outcomes*.

## 3. Expected result

| | Before | After |
|---|---|---|
| Intent failures attributable | no | yes — its own contract, confidence and span |
| Types that never fire | **4, unexplained** | 0 unexplained: each either fires on a fixture or is retired |
| `unknown` rate per source | uncounted | reported |
| Taxonomy prose | says 14 | says the true number (16 after step 2 adds `DELIVERY_FAILURE`) |

## 4. Edge cases
E1 intent and the extraction disagree → **record it**; today `merged_with` folds them and the
disagreement vanishes · E2 a source returns `unknown` for 80% of its mail → a prompt defect, and
nothing currently counts it · E3 retiring a type is a **contract change**, not a deletion — old
rows may carry it · E4 splitting the call costs another model site → meter it · E5 the split must
not lose `merged_with`'s rule that *a silent extractor never erases the gate's reading*.

## 5. How to do it
| Unit | What |
|---|---|
| 7-U1 | intent as its own contract call — same context, **separable contract** |
| 7-U2 | record intent↔extraction disagreement instead of folding it |
| 7-U3 | `unknown` rate per source, on the trace and in the report |
| 7-U4 | one fixture per silent type that MUST fire it |
| 7-U5 | any type no fixture can fire is **retired from the enum**, deliberately |
| 7-U6 | correct the "closed 14-member taxonomy" prose; pin `len(SignalType)` in a test |

## 6. Test cases
T1 intent carries its own confidence and span · T2 a disagreement is recorded, not folded ·
T3 each of the four silent types fires on its fixture (RED today) · T4 `len(SignalType)` matches
the documented number · T5 the gate's reading survives a silent extractor (**regression guard**).

## 7. Verify
```bash
uv run --no-sync pytest tests/capture/esqe/test_detector.py tests/capture/esqe/test_classifier.py -q -p no:randomly
uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q -p no:randomly
```

## 8. Done criteria
**Ticked 2026-09-24.** Three closed, one **AMENDED** — one third of it is something the codebase
already argues against in writing, and the argument is right.

- [~] **intent has its own contract, confidence and ~~evidence~~** — **AMENDED.**
      * *its own contract* — **already true before this step.** `MessageIntent` has its own closed
        enums and its own observation-vs-judgement split.
      * *confidence* — **done**, as `confidence_bp`, DERIVED from the axes the model already
        answered. Never asked for: doctrine 1 forbids a model scoring itself, and asking would
        change LLM-2's prompt, move `vocabulary_fingerprint` and **re-extract the whole corpus for
        a third time**.
      * *evidence* — **REFUSED, and the refusal is the right answer.** `contracts/intent.py`:
        *"'the tone is warm' or 'a person composed this' have no quotable span to point at. A field
        for them would invite a model to manufacture a citation for something that is not a
        quotation, which is worse than having none."* §9 of this very step says the design is
        correct and must not be rebuilt. A regression guard now asserts intent has NO evidence
        field.
- [x] **each of the four silent types fires on a fixture, or is retired** — **all sixteen members
      have a test that fires them, so nothing is retired.** The four "silent" types are a CORPUS
      fact, not a code fault. `test_every_signal_type_has_a_fixture_that_fires_it` keeps that
      answerable from the repo rather than re-derived by whoever asks next.
- [x] **`unknown` rate per source is reported** — `capture/intent_rate.py` plus three counters on
      `SyncSummary`, **incremented on the capture loop** and driven by
      `test_the_intent_counters_have_a_real_consumer`. An event that never reached S4 is in neither
      counter: counting it as unreadable blames the reader for messages nobody handed it.
- [x] **taxonomy prose matches `len(SignalType)`** — five sites fixed by **removing the counts
      rather than updating them**. A prose count over a closed set is a comment with an expiry
      date, and this one had already expired twice.

### 8.1 · What was deliberately NOT built

**7-U1, the model-call split.** Priced and declined: it costs a third full re-extraction plus a
second model call on every message forever. Its stated purpose was attribution, and the derived
confidence delivers attribution for nothing. Recorded as a priced option in the Harsh runbook.

> **This is the second step where the cost check changed the design rather than documenting a
> bill** — step 6 gave the domain proposer its own call for the same reason, in the opposite
> direction.

## 9. Must NOT do
**Do not rebuild the observation-vs-judgement split** — it is correct. Do not add a taxonomy member
to make a predicate fire. Do not guess `unknown` away.
