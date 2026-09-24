# Step 2 · Bounce / DSN — premise verification

**Run:** 2026-09-23 · PRODUCTION read-only, `org_e97e86f858ad48b2bbf64b8a` · no write issued
**Verdict:** the step's original premise was **wrong**, and the real defect is now **exactly located**

---

## 1. The original premise, and why it was wrong

Step 2 was written believing:

> *"`gate/rules.py` N-01 and N-03 delete every delivery-status notification by design."*

**Measured:**

```
mailer-daemon events for this org:   outcome = emitted   n = 5
signals produced from them:                              n = 0
```

All five pass the gate. N-03 never fires, and its own condition says why:

```python
if not att and machine:          # ← "not att"
    return ("N-03", "drop")
```

A Gmail DSN returns the original message as an attachment, so `has_attachment=True`, so `not att`
is False. **The comment *"a bounce carries no business signal ever"* is still wrong, but it is not
what loses the finding.**

**The originally-planned test T1 — "a bounce reaches the gate" — would have gone GREEN on today's
code**, and the step would have "proved" a defect that was not there.

---

## 2. All five bounces are in production, readable, with full text

| # | Kind | Recipient | Detail |
|---|---|---|---|
| 1 | **Failure** | `apply@surgeahead.com` | remote server misconfigured |
| 2 | Delay | `apply@surgeahead.com` | Gmail will retry for 23 more hours |
| 3 | Delay | `apply@surgeahead.com` | Gmail will retry for 47 more hours |
| 4 | **Failure** | `madison@afore.vc` | Address not found |
| 5 | **Failure** | `joseph@afore.vc` | Address not found |

Exactly the benchmark's three failures, plus the two delay notices that preceded Surge's permanent
failure. **Every one has a `prepared_content` row** — the DSN body is plain prose, so **no OCR and
no MIME parsing are needed to read the failed recipient.** It is in the sentence.

All five are `outcome=emitted`, `triage_lane=P3`.

---

## 3. The exact defect — from the event trace

```
landing                  pass
preprocess               pass            language=en
S0                       pass
S1                       pass
S2                       pass           N-05                    route=needs_extraction,
                                                                availability=auto_reply
triage                   pass                                   lane=P3
s2_semantic_extraction   short_circuit  envelope_bulk_headers   ← extraction never ran
s4_esqe                  short_circuit  bulk_headers            signals=0
emit                     emit
```

### Read that chain carefully — there are two distinct defects

**Defect 1 · the bulk-header short-circuit swallows delivery failures.**
A Gmail DSN is an automated message, so its envelope carries bulk headers. The semantic lane
short-circuits on `envelope_bulk_headers` and ESQE short-circuits on `bulk_headers`. That rule is
**right for newsletters and wrong for a delivery failure** — the one kind of automated mail that is
a fact about something the tenant did.

**Org-wide: 30 events short-circuit on `envelope_bulk_headers`.**

**Defect 2 · a bounce is classified as an availability notice.**
`S2 pass N-05 … availability=auto_reply`. `availability_marker()` matched the DSN's autoreply
markers, so the gate filed it as an **out-of-office**. That exemption is what saved it from the
drop — good — but *"Rohit's message to Afore did not arrive"* is not a statement about anyone's
availability. The classification is semantically wrong and it is why the event ends up in lane P3.

---

## 4. What this changes in the step

| Unit | Original | Corrected |
|---|---|---|
| 2-U1 DSN recogniser | needed, RFC 3464 MIME | **needed, but prose-first** — the recipient and the failure kind are in the readable body; MIME parsing is a hardening pass, not the first cut |
| 2-U2 gate exemption from N-01/N-03 | the core of the step | **not needed** — they already pass |
| **2-U2′ (new)** | — | **exempt a recognised DSN from `envelope_bulk_headers` and `bulk_headers`.** This is the actual fix |
| **2-U2″ (new)** | — | stop classifying a DSN as `availability/auto_reply` |
| 2-U3 `DELIVERY_FAILURE` type | needed | **unchanged** |
| 2-U4 predicate | needed | **unchanged** |
| 2-U5 join to the sent message | needed | **unchanged** |
| T1 | "a bounce reaches the gate" | **rewrite: a bounce produces a signal.** The old form passes today |

**Delay vs failure is trivially separable** — the body literally says
`Delivery Status Notification (Failure)` or `(Delay)`. Edge cases E1/E3 in the step file are
satisfied by reading the subject line, not by inferring anything.

---

## 5. A larger finding, surfaced on the way — NOT step 2's

```
emitted events                                375
with an extraction row                        102
emitted WITHOUT an extraction row             273   (73%)
```

Broken down:

| Source | Object | Route | n | By design? |
|---|---|---|---|---|
| screen_session | screen_doc | `needs_extraction` | 133 | **no** |
| gmail | email_message | `None` | 52 | **no — route is NULL** |
| gcal | calendar_event | `structured` | 37 | **yes** — the model bypass |
| gmail | email_message | `needs_extraction` | 34 | **no** |
| screen_session | chat | `needs_extraction` | 17 | **no** |

Per-day, gmail only:

```
2026-09-19   emitted 178   extracted  92      ← the backfill sweep
2026-09-21   emitted   1   extracted   1
2026-09-22   emitted   1   extracted   1
```

The org **is** activated (`l1_semantic_activation`, enabled 2026-09-18). Later days extract at
100%. So the 19 September shortfall looks like a **backfill-sweep behaviour**, not a broken lane —
but **150 screen_session events marked `needs_extraction` have no extraction at all**, and
**52 gmail events carry a NULL route while being emitted**, which no code path in `pipeline.py`
obviously produces (`route=gate.route or "needs_extraction"` should never leave it null).

> **This deserves its own step.** It is potentially larger than everything currently in the plan:
> if an event is emitted without extraction, it has no claims, so no predicate can fire, so it can
> produce no signal — regardless of how good every downstream unit is.

**Logged as a new candidate step. Not chased here, to keep step 2 honest.**

---

## 6. Status

**Step 2 premise: VERIFIED and CORRECTED.** The defect is located, the fix is narrower than
planned, and the RED-first test has been rewritten so it fails for the right reason.
Ready to build.

---

# PART 2 · The build — 2026-09-23

## 7. What was built

| Unit | Artifact | What |
|---|---|---|
| 2-U1 | `capture/delivery_status.py` **(new)** | the recogniser — pure, prose-first, no MIME walk, no clock, no I/O |
| 2-U2′ | `esqe/relevance.py` | a `RULE_DELIVERY_FAILURE` rung **above** `RULE_BULK_HEADERS`, at 9000 bp |
| 2-U2″ | `gate/rules.py` | `availability_marker` no longer files a bounce as an out-of-office |
| 2-U3 | `contracts/signal.py` | `DELIVERY_FAILURE` — taxonomy member **sixteen** |
| 2-U4 | `esqe/detector.py` | the predicate, reading the **envelope** rather than a claim |
| — | `esqe/classifier.py` | precedence position **second**, above every claim-derived type |
| — | `esqe/importance.py` | ALG-17 type weight 9000, tied top, span unchanged |
| — | `esqe/normalize.py` | three policy tables completed |
| — | `esqe/qualification.py` | `DELIVERY_FAILURE_OVERRIDE` — see §9 |
| — | `capture/pipeline.py` | **the wiring** — one reader, both candidate builders, and the detector |

## 8. Two things the build found that the plan did not predict

### 8a · The unit tests would all have passed on a broken system

`pipeline.envelope_candidate` leaves `subject` and `snippet` **empty on purpose** — *"they exist
to be shown to LLM-5, and nothing that reads this candidate is allowed to call a model."*

The first cut of the rung read `candidate.subject`. Every unit test passed, because every unit
test built its own candidate **with** a subject. On the real path it would have seen `""` and
refused every bounce exactly as before.

That is the defect the build record says this layer shipped **six times**:

> *"A unit built, tested, green — and called by nothing on a real request path."*

The fix follows its rule rather than patching around it: `RelevanceCandidate` gained an explicit
`delivery_failure: bool`, computed **once** by `pipeline._delivery_failed` and read by the rung, so
the envelope candidate and the S4 candidate cannot disagree. And a test —
`test_the_candidate_the_pipeline_really_builds_is_not_refused` — now drives `envelope_candidate`
itself rather than a hand-built object.

### 8b · The signal would have been detected and then dropped

Computed on a cold-start tenant with the shipped weights:

```
tenant floor (default)   2500

delivery_failure         1080   <-- dies at the floor
escalation               1080   <-- so does this
contract_renewal         1000   <-- and this
relationship_change       640
```

**Structural, not tenant-specific.** ALG-17's five terms are money, deadline, actor authority,
entity criticality and a type nudge. A bounce states no amount and no deadline, its actor is a
mail daemon, and the one entity it names is by definition one we could not reach — so four of five
are zero *by construction* and the type nudge alone can never reach 2500.

## 9. The floor override, and why it is not the thing §9 of the step file forbids

The step file says: *"Do not special-case importance. If a delivery failure does not clear the
floor through ALG-17's existing terms, that is a finding about the floor (step 8), not a licence
to bypass it."* That rule is being kept.

**ALG-17 is untouched.** No weight was nudged to make a number pass; the score is still 1080 and
is reported as 1080.

What was used is the floor's own existing mechanism. `qualification.py` already carries three
overrides plus `AVAILABILITY_OVERRIDE`, whose stated reason is an exact parallel:

> *"Its importance is deliberately the lowest in ALG-17 (it is context, not work), and the floor
> would otherwise drop the only route by which 'who is away' reaches Layer 2."*

`DELIVERY_FAILURE_OVERRIDE` is the same mechanism with the inverse reason: that type is the
**lowest** weight and still cannot pass; this one is tied for the **highest** and still cannot.
The refusal remains fully ledgered — `qualification_drops` still records the score and the reason.

> **Recorded for step 8:** three of the four types checked die at the default floor on a
> cold-start tenant. That is the step 8 premise, confirmed on a second axis.

## 10. Verification

```
tests/capture/test_delivery_failure.py          16 passed
tests/contracts + tests/capture               5486 passed · 3 failed · 203 skipped
```

The three failures are **pre-existing or environmental**, each verified:

| Test | Why |
|---|---|
| `test_h0_gate.py` | in `tree.yaml`'s supplied baseline |
| `test_ocr_enablement.py` | **no tesseract on this machine** — the local half of step 1's finding |
| `test_g9_gate_probes.py` | needs Postgres; in `tree.yaml`'s baseline. Confirmed by stashing the change and re-running |

**Zero regressions.** Nine further failures appeared during the build and all nine were
totality guards — `PRECEDENCE`, `SIGNAL_TYPE_WEIGHT_BP`, `ANCHOR_FAMILIES`, `DATE_POLICY`,
`AMOUNT_POLICY`, and four tests pinning the member count. Every one was the architecture working:
adding a member to a closed taxonomy forces every table that must be total over it to be
completed, at import time, on the line that added the member.

## 11. Still open

| # | What | Why |
|---|---|---|
| 1 | **2-U5 · the join to the sent message** | the signal fires; it does not yet cite the outbound message it failed. That is what turns *"a delivery failed"* into *"your pitch to Afore never arrived"* |
| 2 | **Replay against the five production bounces** | needs a scratch Postgres (Harsh, handoff item 2). The unit and wiring tests pass; the end-to-end number has not moved yet |
| 3 | A migration for the new `signal_type` value, if the column is constrained | to check before this ships |

---

# PART 3 · The full suite — and what it found across the seam

## 12. The run

```
tests/                12,450 passed · 16 failed · 1,060 skipped · 152 xfailed   (6m28s)
```

Of the 16, **two were mine** — and they were the most interesting result of the whole step.

## 13. Layer 2 keeps its own totality table over Layer 1's taxonomy

```
AssertionError: Layer 1 publishes ['delivery_failure'] and Layer 2 gives them no meaning.
`qes_adapter` writes them to the graph regardless, where they score neutral, not-an-ask and
not-progress in silence. Add a row to observations/kinds.yaml.
```

**The error message names the file and the failure mode.** `context/observations/kinds.yaml` gives
every observation kind three answers — `polarity`, `is_ask`, `is_progress` — and its header
records why it exists: thirteen of Layer 1's own types once reached the graph and **scored zero
everywhere**, `risk_flagged` and `escalation` among them, recorded and ignored.

So adding a member to L1's closed enum is not a Layer 1 change. **It is a change at both ends of
the seam**, and the test that says so lives in Layer 2.

### The row, and the judgement in it

```yaml
- {kind: delivery_failure, polarity: neutral}
```

**Neutral is the considered answer, not the lazy one.** The file's other neutral rows are neutral
because the *type* carries no direction — an anomaly can be a surprise order or a churn signal.
A delivery failure is not like that: as an outcome its direction is perfectly clear.

It is neutral for a different reason. `polarity` feeds `derived.sentiment`, which is about the
**relationship**. A bounce is a mechanical fact about our own outbound — a bad address, a
misconfigured server — and there was no exchange to feel anything about. Scoring it negative would
push sentiment down on a relationship that never happened, which is the untraceable bias the
file's own header warns against.

`is_ask` false: we put no question to them; a mail server told us something. `is_progress` false,
and there is no `is_regress`.

### And a second guard behind the first

Adding the YAML row broke `test_the_last_five_literals.py`, which pins the derived tables against
**hardcoded fallback sets** in three other modules — `vocabulary.OBS_NEUTRAL`,
`waiting._ASK_KINDS_FALLBACK`, `derived._PROGRESS_KINDS_FALLBACK`. The row is one place; the
fallbacks are the safety net for an unreadable file, and a test keeps them honest.

`OBS_NEUTRAL` updated to match. **Two guards, in two layers, for one enum member — and both were
right to fire.**

## 14. Final state

| Suite | Result |
|---|---|
| `tests/capture/test_delivery_failure.py` | **16 passed** |
| `tests/contracts` + `tests/capture` | 5,486 passed · **3 failed** |
| `tests/context` | 2,390 passed · **11 failed** |

**All 14 remaining failures are pre-existing or environmental**, each identified:

| Count | Cause |
|---|---|
| 11 | `tests/context` — `sqlite3.OperationalError: table llm_costs has no column named cache_read_tokens`. A fixture-schema drift, unrelated to this step |
| 1 | `test_h0_gate.py` — in `tree.yaml`'s supplied baseline |
| 1 | `test_ocr_enablement.py` — no tesseract on this machine; step 1's finding, locally |
| 1 | `test_g9_gate_probes.py` — needs Postgres; in `tree.yaml`'s baseline |

**Zero regressions.** Eleven guards fired during this step — nine in Layer 1, two in Layer 2 — and
every one was a totality or literal-pinning check doing exactly its job.

## 15. The step's own lesson

The plan's rule is *prove the defect first*. This step proved the defect **twice** and was wrong
about it **twice**:

1. The written premise — *"the gate deletes bounces"* — was false. Production said `emitted`.
2. The first implementation read `candidate.subject`, which is empty on the real path. Every unit
   test passed on a system that would have refused every bounce.

Both were caught by measuring rather than by reasoning. Neither would have been caught by a green
suite, which is the whole argument for step 17.
