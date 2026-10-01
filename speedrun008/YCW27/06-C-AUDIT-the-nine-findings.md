# C · the nine findings the cascade was hiding — audit, cross-check, then execute

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01.
**Why they exist:** fixing `receipts.evaluate()` turned `13 ERROR` into `1 ERROR + 8 FAIL`. Twelve
phantom errors had been hiding nine real findings. This page measures each one and says whose it is.

**Method:** one `set transaction read only` connection to production. No writes, no model.

---

# ⛔ PART 0 · I SUSPECTED TWO RECEIPTS OF ASKING THE WRONG QUESTION. BOTH SUSPICIONS WERE WRONG

Recording this first, because the audit's value was in **not** changing them.

## `L4 · at least one seat has a manager` — the receipt is right

I suspected it of checking only `manager_seat_id` while `assignment.manager_of` reads the dated
`seat_responsibilities.reports_to` **first** — the correction I found in M12.

Measured: **`seat_responsibilities` has 0 rows**, and it carries no `reports_to` column at all. There is
genuinely no reporting line by either path. ⛔ **The receipt is narrower than the code and still correct,
because the wider path is empty too.**

## `L6 · there is a channel this tenant can be reached on` — also right

The SQL asks `channel in ('slack')` and the tenant has **3 active `in_app` rows**. That looked like a
claim broader than its query.

It is not. `contracts/execution.py:158` — `IN_APP = "in_app"  # the card surface — **always available,
never interrupts**`. `platform/seats.py:77` — *"`get_channel('in_app')` is None — **there is nothing to
send, because the card is already on** [the surface]"*. `deliver/routing.py:30` — `PULL_SURFACE =
"in_app"`. And `migrations/0032` created `org_channels` for *"where a tenant wants to hear (v1: one
Slack incoming-webhook per org)"*.

⛔ **`in_app` is a PULL surface, not a push channel.** A tenant reachable only by coming to look is not
reachable, and `ready: false` is a true statement about delivery readiness. The detail explains **how to
read** the failure — *"nothing is wrong upstream"* — not that it should not fail.

> **So C is far smaller than it looked: exactly one receipt asks the wrong question.**

---

# PART 1 · THE NINE, EACH MEASURED

| # | | claim | value | verdict | whose |
|---|---|---|---|---|---|
| 1 | L1 | the parked queue is not a black hole | **1,662** pending | ✅ real gap | **Harsh** — a drain or a review pass |
| 2 | L1 | every drop we might be wrong about can still be reviewed | **26** | ✅ real gap | **Harsh** |
| 3 | L1 | attachments carry readable text | **872** unsupported / fetch_failed | ✅ real gap | **Harsh** — ⛔ *and it is the same root as the suite's one failing test* |
| 4 | L4 | at least one seat has a manager | **0** | ✅ real gap | **Rohit** — one reporting-line row |
| 5 | L5 | every delivered card carries a lane | `ERROR` | ✅ **`0190` unapplied** | **Harsh** |
| 6 | L4 | the score components are measured, not placeholders | **59** frozen at 5000 | ✅ real gap | upstream |
| 7 | L6 | cards carry a written draft, not a template stub | **60** | ⛔ **THE RECEIPT IS WRONG** | **mine** |
| 8 | L6 | there is a channel this tenant can be reached on | **0** | ✅ real gap | **Rohit** — connect Slack |
| 9 | L7 | a human verdict has reached the loop | **0** | ✅ real gap | **Rohit** — nobody has clicked |

## ⛔ #3 is the same root as the one test that fails in the whole suite

`tests/capture/documents/test_ocr_enablement.py` has failed all session because `pytesseract` is not
installed on this machine. Production says **872 `document_jobs` are `unsupported` or `fetch_failed`.**
The receipt and the test are two views of one gap: **the OCR path has no engine.** Worth saying because
I have reported that failing test as *"unrelated to my work"* every time — true, and it is **not**
unrelated to the product.

---

# PART 2 · #7 · the one receipt that is wrong, and it is wrong in BOTH directions

```
claim   : cards carry a written draft, not a template stub
detail  : raw_slot with an EMPTY ARTIFACT BODY is a card with no content
sql     : select count(*) from cards where render_mode <> 'llm'      → 60, expect 0
```

Measured:

| render_mode | total | empty body |
|---|---|---|
| `llm` | 105 | **13** |
| `raw_slot` | 59 | 24 |
| `template` | 1 | 1 |

⛔ **Three mismatches between the claim, the detail and the query:**

1. it **counts 35 `raw_slot` cards that DO have a body** — a `raw_slot` fallback with real content is
   the designed behaviour when the model refuses or the validator rejects, not a stub;
2. it **misses 13 `llm` cards with an empty body** — which by its own detail *are* cards with no content;
3. `expect n == 0` demands every card be model-rendered, which would make the deterministic fallback a
   permanent failure.

## And the honest question is narrower still

Of the **38** empty-body cards:

```
level=prescriptive   abstained=False   n=18     ⛔ instructing with no content
level=review         abstained=True    n=13     ✅ correct — a review card has no draft by design
level=observation    abstained=True    n=6      ✅ correct
level=observation    abstained=False   n=1
```

⛔ **An abstained card is SUPPOSED to have no draft.** `card_builder` strips `run_play` and `render.py`
sets `art = ""` when the artifact is rejected — so demanding a body from the 19 abstained cards would
demand a draft the engine deliberately refused to write.

> **The honest number is 18: a card with no content that is nonetheless giving an order.**

⛔ **And the fixed receipt still FAILS, at 18.** This is not weakening a verify to make it pass — it is
asking the question the claim and the detail already state, and the answer is still a failure. It
simply names 18 real cards instead of 60 cards of which 35 are fine and 13 real ones are missed.

---

# PART 3 · THE PLAN — 1 unit

```
level 0 ·  C.U01   the draft receipt asks what its own detail describes
```

| | |
|---|---|
| artifact | `genios_engine/platform/receipts.py` |
| verify | `tests/platform/test_a_card_that_instructs_has_content.py` |

**The new SQL:** cards with an empty artifact body, **not abstained**, at an instructing level
(`prescriptive`/`predictive`). `expect n == 0`. Today: **18 → FAIL.**

⛔ **`level in ('prescriptive','predictive')` is `abstention.ACTIONABLE`**, and a NULL level is excluded
rather than assumed — the same rule `calibrate._PRECISION_SQL` already states: *"a card whose level
nobody recorded is ungradeable, and defaulting it to 'instruction' is how the old behaviour comes
back."*

⛔ **Both conditions, not either.** `abstained_because is null` AND an actionable level: a card can be
downgraded by level without an abstention reason (1 such card exists), and a reason without a downgrade
would be a contradiction the card layer does not produce.

---

# PART 4 · WHAT C DOES NOT DO

| | Why |
|---|---|
| change the other eight receipts | ⛔ **all eight are correct.** Two I suspected were verified right |
| drain the parked queue, fix OCR, write a reporting line | they are the findings, and each has a named mover |
| make #7 pass | the honest question still answers 18. **A receipt is not fixed by making it green** |
