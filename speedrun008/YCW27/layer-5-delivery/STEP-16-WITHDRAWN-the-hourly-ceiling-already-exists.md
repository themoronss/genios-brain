# Step 16 — WITHDRAWN · the per-recipient hourly ceiling already exists

**Unit:** `M13.C3.U16` · ⛔ **WITHDRAWN 2026-10-01 — there was no decision to make.**
**Found by:** `07-AUDIT §4.1` · **Withdrawn by:** measuring `deliver/timing.py`

## 1 · What is there

`deliver/rate_limiter.py` implements a **per-recipient, per-rolling-hour attention ceiling**:

| | |
|---|---|
| `hour_recipient_key` | *"The rolling-hour bucket key: a shared stream for chat families, else the seat"* |
| `reserve_slot` | *"Atomically reserve one attention slot. True if reserved, False if the window is full."* Unbounded budgets always reserve; a bounded window increments `used` only while strictly below `budget`, and the `where` on the conflict update is what makes two concurrent workers safe |
| `release_slot` | *"Give a reserved slot back — only on a DEFINITE non-delivery. Never below zero"* |

⛔ **Nothing in the engine imports this module.** 9 test callers, 0 engine callers.

## 2 · ⛔ And it is NOT a duplicate of something upstream — the grains differ

A `budget` suppression **does** run in production: `reason/runner.py:1294` writes
`_suppress(store, org_id, rule.id, node_id, "budget", …)`, and that reason code is in the why-not
vocabulary `executive/explain.py` already reads.

| | Grain | Status |
|---|---|---|
| `reason/runner.py:1294` | per **rule**, per **node**, **daily** | ⛔ live |
| `deliver/rate_limiter.py` | per **recipient**, per rolling **hour** | ⛔ orphan |

> ⛔ **Two implementations of one word can be two different questions.** One asks *"has this rule fired
> too often today?"*, the other *"has this person been interrupted too often this hour?"* Only the first
> is being asked, and the second is the one a founder would feel.

**So the honest statement: there is no per-recipient hourly ceiling in the running path.** Nothing has
exceeded one because nothing is delivering — the same mask that hides `0190` and the card outage.

## 3 · ⛔ What Rohit has to decide

**Should a per-recipient hourly ceiling exist, and what is it?**

| Option | What it means |
|---|---|
| **A** · yes, with a number | I wire `reserve_slot`/`release_slot` into the send path and the number becomes pack config, like `bands.py`'s urgency cuts — *"data, not engine constants"* |
| **B** · no | ⛔ `rate_limiter.py` is **deleted**, not left declared. A ceiling nobody wants is not a silent lane; it is dead code with a convincing docstring, and the declaration would preserve it forever |
| **C** · yes, but the daily rule is enough for now | the module stays declared with this step as its mover, and the entry says the decision was taken rather than deferred |

⛔ **This is adjacent to `U6d` in L4, which is the same question in a different layer** — *how many
warnings a founder should see a day* — and that one is also Rohit's and also blocked on a product
number. They should probably be answered together, because two ceilings set independently will
interact, and the interaction is what a founder experiences.

## 4 · What is NOT being asked

⛔ **I am not asking whether the code is correct.** It is: `reserve_slot`'s conflict-update `where` is
the thing that makes two concurrent workers safe, `release_slot` refuses to go below zero and fires only
on a **definite** non-delivery, and the key deliberately shares a bucket for chat families because one
stream is one interruption. **The module is well built. Nobody decided whether the product wants it.**

## 5 · Why it is recorded as a step rather than a note

Because the default outcome of leaving it undecided is the worst of the three: the module stays, reads
as a feature, and is cited by anyone asking whether GeniOS throttles notifications — ⛔ **a comment and
a module name both read as a measurement somebody took.**

## 6 · Expected outcome

One of A, B or C, written into `02-DECISIONS.md` with a date. ⛔ **Under B the deletion is the
deliverable**, and `delivery_health.py`'s three `UNCUT_OVER` entries for `rate_limiter` go with it.


---
---

# ⛔⛔ WITHDRAWN — 2026-10-01 · the question was manufactured by mis-measuring

## 1 · What this step asked, and why it should never have been asked

It asked Rohit to decide **"should a per-recipient hourly ceiling exist?"**, offering **A** wire it,
**B** delete `rate_limiter.py`, **C** decided-defer. Its premise, stated in `§2`:

> *"there is no per-recipient hourly ceiling in the running path."*

⛔ **There is. It is live, and it has a default.**

```
deliver/timing.py:59     _BURST_WINDOW = timedelta(hours=1)
deliver/timing.py:86     max_interrupts_per_hour: int = 3
deliver/timing.py:229    if state.interrupts_last_hour >= profile.max_interrupts_per_hour:
                             -> DEFER, carrying delivered_last_hour and limit in the detail
```

And the chain is wired end to end, every link measured with the qualified resolver:

```
outbox.drain (the live path)
  -> gate.admit                 1 qualified caller
    -> gate.evaluate_delivery    2
      -> timing.evaluate_timing  1   (gate.py:173)
         -> the burst limiter -> DEFER

rate_limiter.reserve_slot        0
```

> ⛔ **A per-recipient hourly ceiling exists, is enforced on every delivery, and DEFERS rather than
> drops.** The question this step put to Rohit was answered by the code before it was asked.

## 2 · ⛔ So what IS `rate_limiter.py` for? Measured, and it is not a duplicate

| | `timing.py` — **live** | `rate_limiter.py` — **orphan** |
|---|---|---|
| mechanism | reads `interrupts_last_hour` off resolved state and **decides** | ⛔ **atomically reserves** a slot — the `where` on a conflict update |
| concurrency | ⛔ **read-then-act** | safe by construction |
| on non-delivery | nothing to undo | `release_slot`, and only on a **DEFINITE** non-delivery |
| bucket | per (org, recipient, channel) | a **shared stream for chat families**, else the seat |

⛔ **And the read-then-act gap is deliberate, not sloppy.** `PgDeliveryContext.resolve` counts the
hour's deliveries and then calls `self._release()`, whose docstring gives the reason: *"The
connection stops sitting `idle in transaction` across an outbound HTTP call."* **Holding the
transaction across a webhook POST would be worse than the race.**

So: two workers draining two rows for the same recipient both read `2 < 3`, both pass, both send —
**four interrupts in an hour against a ceiling of three.**

## 3 · ⛔ And that race cannot happen today — measured

```
Procfile                     web: uvicorn genios_engine.main:app      ← no --workers, so ONE
platform/scheduler.py:77     ThreadPoolExecutor(max_workers=1)        ← one sweep tick at a time
```

**One process, one sweep thread → one drain worker → no concurrency → no overshoot.** The
`for update skip locked` in the drain is there for a deployment that does not exist yet.

## 4 · ⛔ Which makes every option wrong except the one the code already took

| | Verdict |
|---|---|
| **A** · wire `rate_limiter` with a number | ⛔ **WRONG.** It would be a **second** enforcement beside a live one, and *two implementations answering one question disagree the first time somebody tunes one* — the exact defect `tests/executive/test_an_unroutable_tenant_says_why.py` guards for receipts |
| **B** · delete `rate_limiter.py` | ⛔ **WRONG.** It is the **race-free** version the multi-worker path needs. Deleting it means rebuilding it at cutover time, and the cutover is when the race starts being possible |
| **C** · declared, moves with the cutover | ✅ **RIGHT — and `delivery_health.UNCUT_OVER` tier 4 already said so**, three steps before this question was written down |

> ⛔ **There was no decision to make.** `STEP-05` had already filed `rate_limiter` as tier 4 of an
> un-cut-over control plane, with a reason and a mover. `07-AUDIT §4.1` then read the same module,
> missed `timing.py`, and manufactured a product question out of it.

## 5 · ⛔ What survives, and it is a latent condition rather than a decision

The live ceiling is **exact only while the deployment is single-worker**, and nothing in the code
says so. That is the same shape as the spine's unguarded cutover: correct today, silently wrong the
day somebody adds `--workers 2`.

**So `rate_limiter`'s declaration is strengthened rather than its question re-asked.** Its
`UNCUT_OVER` entry now records:

- the ceiling is **already enforced** by `timing.py` (3/hour, deferring)
- `rate_limiter` is its **race-free successor**, not a second opinion
- the overshoot is **bounded by the worker count**, which is **1** today
- ⛔ **and it moves with the WORKER COUNT, not only with the cutover**

And a test pins the worker count, so raising it fails the build **here** rather than silently
widening the ceiling in production.

## 6 · The error, named

⛔ **Fourth retraction in this programme — and the first where what is retracted is a QUESTION
rather than a fix.** L4's F9 and F10 and L5's `expires_at` bound were all proposed *fixes* that
would have caused harm. This is a *decision* that should never have reached Rohit.

> ⛔ **I read one module and concluded a capability was absent from the layer.** `07-AUDIT §4.1`
> measured `rate_limiter` carefully — that nothing imports it, that `reason/runner.py:1294`'s
> `budget` is a different grain — and never asked whether `deliver/` enforced the same thing
> somewhere else. **The grain comparison was right and the search was one module wide.**
>
> **Same family as `no_model_wired` (L1), the graph-revision guard (L3), `manager_seat_id` (L4) and
> the invention validator (L5): a conclusion drawn from one name's absence.** Sixth instance, and
> the first to reach a document addressed to Rohit as a decision.

## 7 · Doctrine

| Rule |
|---|
| ⛔ **before asking whether a capability should exist, search the layer for it under every name it might have** |
| ⛔ **two implementations of one idea are not always a duplicate — one may be the race-free version of the other** |
| ⛔ **a deliberate transaction release can be more important than the race it opens** — holding one across a webhook POST is worse |
| **a limit that is exact only at one worker count is a latent condition, and it must be declared** |
| **a manufactured decision costs more than a wrong one: it spends somebody else's attention** |
