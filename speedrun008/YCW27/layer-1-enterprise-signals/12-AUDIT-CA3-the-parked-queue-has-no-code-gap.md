# AUDIT CA3 · the parked queue — 1,662 pending, and not one of them is a code gap

> **Date:** 2026-10-01, read-only. This was brief **CA3** in `HANDOFF-CODING-AGENT.md`, written as
> *"measure before you build — do not write a drain, one exists."* Measured, and the brief was
> right to insist.

---

## PART 0 · THE RECEIPT, AND WHY THE OBVIOUS READING IS WRONG

    [L1] the parked queue is not a black hole        FAIL at 1662
    detail: "pending forever means a park is a slower delete"

The obvious conclusion — nothing looks at parked events — is **false**. The machinery exists and
is wired:

    capture/parked/drain.py          drain_parked(engine, *, org_id, limit=200, now)
                                     parked_aging(engine, *, org_id, now)      ← the read-only half
    capture/parked/recapture.py      NEEDS_RECAPTURE
    capture/parked/refetch.py
    capture/parked/refetch_policy.py NEEDS_REFETCH

`api/routes.py:1121-1127` calls `drain_parked` from **`run_sync_sweep`** — the heartbeat — with the
comment: *"a park is 'look at this again', so something has to look. Riding the existing heartbeat
on purpose — a new Celery periodic task would spend the quota-limited Upstash broker on a pass that
is cheap and idempotent here."*

So the question was never *"is anything looking"*. It was **which classes the 1,662 are in** — and
the brief said so, because the five possible answers have nothing in common.

---

## PART 1 · THE MEASUREMENT · `parked_events` where `status = 'pending'`

    low_relevance                709      43%
    DOC-06                       598      36%
    DOC-05                       148       9%
    DOC-02                        78       5%
    poison_quarantine             69       4%
    extraction_call_failed        37       2%
    extraction_parse_failed       19       1%
    llm_junk_unconfident           4       0%
                               -----
                               1,662            sums exactly, no residue

## PART 2 · EVERY CLASS TRACES TO SOMETHING ALREADY NAMED

### ⛔ 824 of 1,662 — half the queue — is H2's OCR deploy

`drain.NEEDS_REFETCH` is a closed set of exactly four codes, and the code annotates each:

    DOC-02   "unsupported binary; only OCR/native support changes this"      78
    DOC-04   "OCR ran but scored too low to trust"                            0
    DOC-05   "the attachment download itself failed"                        148
    DOC-06   "readable in principle, no OCR engine was wired"               598
                                                                          -----
                                                                            824

And the drain already refuses to pretend otherwise, in its own words at `drain.py:128`:

> *"Honest accounting: the retained payload is a stub, so re-entering the pipeline would re-park it
> and report work that did not happen."*

**These cannot drain until the Tesseract stack is in the image.** `DOC-06` alone — *no OCR engine
was wired* — is 598 rows, 36% of the whole queue. That is **`HANDOFF-HARSH.md` H2**, the same deploy
behind the L1 receipt's 872 unreadable `document_jobs` and the same root as audit **E**.

### 709 — `low_relevance` — is a policy question, not a defect

These were judged not relevant and parked rather than dropped, which is the park-never-drop
doctrine working. The receipt's own detail is the argument against leaving them: *"pending forever
means a park is a slower delete."* ⛔ **But the answer is a decision, not code:** either a judged
low-relevance park gets a terminal state (reviewed-and-closed, with a receipt), or the receipt's
question is narrowed to exclude a class that is deliberately parked. **Whose: Rohit.**

### 69 — `poison_quarantine` — deliberate, and correctly permanent

A poisoned row is quarantined on purpose. Draining it would re-poison the lane.

### 60 — the model-call failures — are the spend limit

    extraction_call_failed        37
    extraction_parse_failed       19
    llm_junk_unconfident           4

Every model call in the product has been refused since **2026-09-25 11:09 UTC**
(`400 invalid_request_error — "You have reached your specified API usage limits"`). These parks are
that outage, recorded correctly. **Whose: Rohit**, `STEP-04`.

---

## PART 3 · THE VERDICT

> **Zero of the 1,662 is a code gap.** 824 are a deploy, 778 are deliberate policy, 60 are the
> spend limit. The drain is wired, runs on every heartbeat, classifies every row, and declines to
> re-inject a stub rather than reporting work it did not do.

**Nothing was built here, and that is the finding.** The brief asked for a measurement first
precisely because the five candidate answers pointed at five different owners, and the real one
points at none of them being this layer.

### ⛔ What the receipt should become — and why it is not changed here

`[L1] the parked queue is not a black hole` asks `status='pending' = 0`, which cannot reach zero
while 824 rows wait on an image and 69 are quarantined on purpose. By the rule audit **D**
established — *a receipt over append-only history needs a lower bound, or it is not a gate but a
monument* — this is the same shape one layer over: **a receipt whose zero is unreachable for reasons
the layer cannot clear.**

The honest rewrite is narrower: *no parked event is pending for a reason nobody has named.* That is
a declaration (`drain.NEEDS_REFETCH` + `poison_quarantine` + the spend limit) checked against the
live `reason_code` distribution, and it goes red the moment a **new** code appears.

**Not done here**, and deliberately: it changes an L1 receipt while L1's owner has two open deploys
against the same rows, and rewriting the gate before the deploy would hide the thing the gate is
currently, correctly, shouting about. **It is its own unit, after H2.**
