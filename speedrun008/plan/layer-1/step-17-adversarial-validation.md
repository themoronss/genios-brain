# Step 17 — Adversarial validation: failures, scenarios, conditions

**Status:** NOT STARTED · **Effort:** weeks · **Depends on:** all · **Engine:** D
**Moves:** every metric — this is the step that decides whether the other sixteen are real
**Runs:** LAST, and then again after every future change

> **This step does not build a feature. It tries to break the other sixteen.**
> Its output is a list of things that are wrong, not a list of things that were shipped.

---

## 1. Why this step exists

The build record already answers this, from experience. Every wave of L1 v2 ran
**build → gate → adversarial review → fix**, and it records the outcome plainly:

> *"The review is what found nearly everything below, and it is the part worth keeping."*
> *"Each was found by adversarial review, never by the test suite — because a unit test passes
> perfectly well on code nobody calls."*

Every single defect in this investigation was sitting behind a **green suite**:

| Defect | The suite said |
|---|---|
| `coverage_ready` `None` on 100% of events | green |
| 193 of 223 signals carrying an identical score | green |
| `reconstruct_thread` called by nothing | green |
| The upload door never calling the finalizer | green |
| 9 of 28 columns crossing the seam | green |
| 7 claim types with no field for a receipt | green |
| `assemble_chain` never running on real headers | green |
| 33 of 109 deleted emails sitting at a parse-default 0.5 | green |

**A green suite is not evidence. This step is where evidence comes from.**

---

## 2. The five techniques — the repo's own, and why each one is here

These are not chosen from a textbook. They are the five the build record names as the ones that
**actually caught defects**.

| # | Technique | What it catches | Proven here by |
|---|---|---|---|
| **1** | **Mutation testing** — break the code, confirm a test goes red | decorative tests | `money.py`: deleting one term killed **23** tests. `importance.py`: `return 5000` killed **16** |
| **2** | **Distribution over examples** — measure the shape of thousands, not three cases | the flat-score class of bug | G7 measures 5,760 scores; the old flat-score bug passed **every** example test that existed |
| **3** | **Independent reproduction** — the reviewer writes their own probes, then neutralises each fix in memory to confirm the probe is sensitive | a probe that would pass either way | the gate agent's method across all ten waves |
| **4** | **Import-graph assertions** — structural claims enforced by walking imports | "the vocabulary must not import the rules" | a code review cannot enforce this; a test can |
| **5** | **Real Postgres, always** | silently skipped tests | the hermetic lane skipped **~800** tests; a scratch DB surfaced **12** failures the green suite never showed — **10 of them from a dirty scratch DB**, so *drop and recreate before every full run* |

**Rule for this step:** a fix is not accepted until technique 3 has been applied to it — neutralise
the fix and confirm the probe goes red. A probe that passes with the fix removed proves nothing.

---

## 3. The failure taxonomy — every miss gets a class

No failure is recorded as "it didn't work". Twenty classes, and each one points at a different
layer of the plan:

| Class | Failure | Usually caused by | Step that owns it |
|---|---|---|---|
| **F01** | Ingestion omission — the object was never fetched | connector, window | 5, 16 |
| **F02** | Pagination omission — the cursor did not exhaust | sync runner | 5 |
| **F03** | Scope mismatch — answered a 30-day question with 90-day data | query layer | 11 |
| **F04** | Field omission — the field was never captured | **connector manifest** | **16** |
| **F05** | Structural extraction failure — token, offset, thread | S1 | 16 |
| **F06** | Entity ambiguity — two people merged, or one split | identity keys | 13 |
| **F07** | Intent interpretation failure | S2 | 7 |
| **F08** | Category interpretation failure | ALG-15/16 | 7 |
| **F09** | Relationship inference failure | typed claims | 4 |
| **F10** | Temporal interpretation failure — wrong date, wrong window | ALG-09 | 14 |
| **F11** | Contradiction failure — a conflict missed or wrongly resolved | ALG-12 | — |
| **F12** | Evidence grounding failure — a claim with no resolvable span | ALG-08 | 4 |
| **F13** | Qualification **false negative** — a real signal refused | the floor | 8, 10 |
| **F14** | Qualification **false positive** — noise admitted | the floor | 8 |
| **F15** | Lifecycle transition failure — wrong state, or a state never reached | ALG-19 | 12 |
| **F16** | Cross-source join failure — calendar and email not connected | identity keys | 13 |
| **F17** | Permission / visibility failure | `visibility_rules` | 16 |
| **F18** | Dedup semantic collapse — an **update** destroyed as a duplicate | dedup keys | 12, 16 |
| **F19** | Coverage misreporting — claimed more than was read | the denominator | 5, 15 |
| **F20** | `unknown` → `false` or `true` — manufactured certainty | the whole doctrine | 12, 15 |

**F20 is the one to watch hardest.** It is the failure that loses trust rather than quality:
telling a founder a promise was broken when it was kept, or that a condition was met when nothing
in the source said so. Gemini did exactly this on 3one4.

---

## 4. The scenario matrix — real, practical, drawn from real data

Every scenario below is taken from the **pilot corpus**, the **benchmark**, or a **defect found in
this investigation**. None is invented.

### 4a · Ingestion and fields

| # | Scenario | Expected | Fails today because | Class |
|---|---|---|---|---|
| S01 | A branched thread — two people reply to the same message | `assemble_chain` reconstructs the **branch** | `In-Reply-To` never captured; falls back to chronology | F04/F05 |
| S02 | A bcc'd recipient | captured, and `visibility_rules` restricts who sees it | `bcc` never captured | F04/F17 |
| S03 | A tentative calendar invite | `responseStatus = tentative` survives | attendees flattened to emails | F04 |
| S04 | A 6-month backfill | cursor exhausts; the row says so | never proven | F02 |
| S05 | An attachment-only email from an unknown sender | survives N-06 via `important_attachment` | **works today** — regression guard | — |
| S06 | A message re-synced after a new field is added | gains the field, **does not re-land as new** | dedup key must not shift | F18 |

### 4b · Bounces and delivery

| # | Scenario | Expected | Class |
|---|---|---|---|
| S07 | Hard bounce, 5.1.1 | `DELIVERY_FAILURE`, joined to the sent message | F01 |
| S08 | Soft bounce, 4.x.x | **not** a failure — retryable | F20 |
| S09 | Delay notice, still retrying (Surge's took 47h) | **`UNKNOWN`**, not failed | F20 |
| S10 | Bounce with no parseable original id | signal publishes, join marked unresolved | F12 |
| S11 | An out-of-office carrying `Auto-Submitted` | takes the N-05 path unchanged | regression guard |
| S12 | A `noreply@` newsletter | still drops at N-03 | regression guard — the exemption must not widen |

### 4c · Claims, evidence and the seam

| # | Scenario | Expected | Class |
|---|---|---|---|
| S13 | A role claim with a quotable span | span resolves against real characters | F12 |
| S14 | A role claim the model could not anchor | **kept and flagged**, never dropped, never given an invented span | F12/F20 |
| S15 | Two signals on one event | **each** resolves its own extraction | F09 |
| S16 | A published signal and its refused sibling | same `subject_key` | F09 |
| S17 | A composed situation | carries domains, confidence, `occurred_at` — none `None` | F09 |
| S18 | The same sweep replayed | byte-identical | F19 |

### 4d · Judgement, and the things that must not be manufactured

| # | Scenario | Expected | Class |
|---|---|---|---|
| S19 | Promise + a later satisfying message | `FULFILLED`, with the link | F15 |
| S20 | Promise, nothing after, **high** coverage | `BROKEN` | F15 |
| S21 | Promise, nothing after, **low** coverage | **`UNKNOWN`** — the single most important row in this table | **F20** |
| S22 | Promise, no coverage figure at all | `UNKNOWN` | F20 |
| S23 | Fulfilled two days late | `FULFILLED`, delta recorded — late ≠ broken | F15 |
| S24 | Re-promised with a new date | old **superseded**, not broken | F18 |
| S25 | A conditional needing company state ("if we hit 10 users") | condition captured, satisfaction **`UNKNOWN`** — L1 does not reach for the graph | **F20** |
| S26 | A CEO writing *"I heard Acme is leaving"* | composes **below** the same CEO stating it first-hand | F11 |
| S27 | A multi-domain sentence | ≥2 domains, each with confidence | F08 |
| S28 | A signal whose domains are all uncovered | still emits, **degraded** — never filtered | F13 |

### 4e · The gate, and recall

| # | Scenario | Expected | Class |
|---|---|---|---|
| S29 | Low confidence + **high** importance | `REVIEW`, and the queue drains | F13 |
| S30 | Low confidence + **low** importance | park or drop, with a reason | F14 |
| S31 | A signal carrying a conflict | travels regardless of score | regression guard |
| S32 | An **unscored** signal | travels — *"never block on a missing score"* | regression guard |
| S33 | The 68 pilot floor-refusals replayed | a REVIEW count that is **neither 0 nor 68** | F13 |
| S34 | A newsletter | dropped, **with a ledger row** | F14 |

### 4f · Identity and cross-source

| # | Scenario | Expected | Class |
|---|---|---|---|
| S35 | `keshav@rocketsdr.com` and `keshav@gmail.com` | **two** identities — L1 must not merge them | **F06** |
| S36 | Same address, two display names | one identity | F06 |
| S37 | Meeting attendee ↔ email sender | L1 preserves both keys; **L2** decides they are one person | F16 |
| S38 | A cohort session vs an external meeting | distinguishable — 5 of the pilot's 7 were cohort | F16 |
| S39 | A warm intro where the introduced person was never emailed | the recipient graph can answer it | F16 |

---

## 5. How to run it — unit by unit

| Unit | What |
|---|---|
| 17-U1 | encode every scenario in §4 as a test, each tagged with its failure class |
| 17-U2 | **mutation pass** — for each of the sixteen steps, break its central function and confirm tests go red. A step whose mutation kills nothing has decorative tests |
| 17-U3 | **distribution pass** — for anything that produces a number, measure the shape over the whole corpus, not three examples |
| 17-U4 | **independent reproduction** — write probes without reading the implementation, then neutralise each fix and confirm the probe is sensitive |
| 17-U5 | **import-graph pass** — every structural claim in `ARCHITECTURE.md` §10 becomes a walking test |
| 17-U6 | **real-Postgres pass** — drop, recreate, run the full suite. A skipped test is a failure |
| 17-U7 | the failure log: every miss gets a class, a scenario id, and the step that owns it |

---

## 6. The conditions a scenario must satisfy to count

A scenario is only evidence if all five hold. Otherwise it is decoration.

1. **It fails for the right reason today.** A test that was green before the change proves nothing
   about the change.
2. **It is sensitive.** Neutralise the fix; the test must go red. (Technique 3.)
3. **It runs on the real lane.** Postgres where the code touches Postgres. A skip is a failure.
4. **It drives a real request path.** Constructing the collaborator inside the test proves the unit,
   not the wiring.
5. **It carries a failure class.** An untyped failure cannot be counted, compared or trended.

---

## 7. Verify

```bash
# the full scenario suite, by class
uv run --no-sync pytest tests/scenarios -q -p no:randomly

# real Postgres — drop and recreate FIRST. 10 of 12 past failures came from a dirty scratch DB.
export GENIOS_TEST_DATABASE_URL="<scratch>"
uv run --no-sync pytest -q -p no:randomly

# the structural claims
uv run --no-sync pytest tests/test_layer_topology.py tests/test_every_llm_call_site_is_metered.py -q

# the purity greps — all three must return nothing
grep -rn "float(" genios_engine/capture/validate/
grep -rn "datetime.now\|date.today" genios_engine/capture/validate/
grep -rn "LLMClient\|anthropic" genios_engine/capture/validate/

# the distributions
python scripts/importance_distribution.py --org <org> --database-url "<url>"
python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"
```

## 8. Done criteria

- [x] all 39 scenarios encoded, each tagged with a failure class — **40 rows**, in
      `tests/scenarios/_registry.py`. The extra is `S01b`: `assemble_chain` being correct and the
      pipeline feeding it ONE message are two different facts, and one row could only record one.
      **Machine-checked both ways** — a scenario with no test and a test with no class both fail.
- [~] ⛔ **"every one of them was RED first" CANNOT BE MET, and meeting it would mean the previous
      sixteen steps failed.** This plan was written before they ran: S01's *"fails today because
      `In-Reply-To` never captured"* was closed by step 16, S03 by step 13, S21/S22 by steps 12 and
      15. Making them red means **un-fixing the product**, which §9 forbids in as many words.
      **Replaced by technique 3, which §2 and §6 already require and which is strictly stronger:**
      RED-first proves a test was failing — possibly for reasons unrelated to the change.
      Sensitivity proves it fails **precisely when this fix is removed**. **27 mutation
      rows**, plus one that applies technique 3 to the harness itself.
- [x] the mutation pass run against **all sixteen** steps — `tests/scenarios/test_sensitivity.py`.
      Nine steps were covered at first draft and nine is not sixteen; rows for steps 1, 3, 6, 7,
      10, 11 and 14 were added to close it. **Three rows reproduce regressions that ACTUALLY
      HAPPENED in this round** (step 9's `UNKNOWN=9000`, step 13's cohort rung order, step 4's
      unwalked lanes), and a 28th applies technique 3 **to the harness itself**.
- [ ] ⛔ **BLOCKED — the full suite on a freshly recreated Postgres, 0 skips.** `995` skips, and
      **`991` of them say `GENIOS_TEST_DATABASE_URL not set`**; `618` tests carry the `pg` marker.
      **A skip is not a pass** and this cannot be ticked. Harsh item 1, open since step 1.
- [x] the failure log exists, typed by class — [`FAILURE-LOG.md`](FAILURE-LOG.md), and **its own
      counts are machine-checked against the registry**. It drifted while being written (said 31
      closed / 3 corpus against a real 29 / 4) and the guard caught it.
- [x] **S21, S22, S25 green** — and each **dies under mutation**: lower step 12's gate to zero and
      S21 fails; read a missing coverage figure as full and S22 fails; empty `_NEGATIVE_STATES`
      and the contract stops refusing an unproven negative.
- [x] the six START-vs-END numbers written into `STATUS.md` — with **two corrections**: metric 6's
      START was 16 and is **15** (step 11 found the audit miscounting itself), and metrics 1, 4 and
      5 **cannot be re-measured without the corpus**, so they are recorded as blocked rather than
      given a number nobody measured.

## 9. What this step must NOT do

- **Do not weaken an assertion to make it pass.** Fix the code, or redraw the unit.
- **Do not accept a skip as a pass.**
- **Do not accept a fix without technique 3.** Neutralise it; if the probe stays green, the probe
  is decoration.
- **Do not count a scenario that was green before the change.**
- **Do not quote any number externally from one mailbox.** N=1, and this founder's outbound volume
  is unusually small, which flatters sent-side results.
