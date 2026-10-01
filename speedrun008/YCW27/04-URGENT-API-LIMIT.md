# ⛔ URGENT — no model call has succeeded anywhere in GeniOS since 25 September

Found 30 Sep 2026 while investigating a Layer 1 relevance failure. It is not a Layer 1 problem.

---

## The fact

```
last SUCCESSFUL model call anywhere in the product:
    2026-09-25 11:09:30 UTC   l4_llm_decision   claude-haiku-4-5-20251001
```

**Five days.** Every model call since has failed with the same error:

```
Error code: 400 — invalid_request_error
"You have reached your specified API usage limits."
```

This is the **spend limit configured on the Anthropic account**, not a code fault, not a rate
limit, and not a model deprecation.

## The scale

Failures per day, all orgs:

| Day | Failed calls |
|---|---|
| 16 Sep | 1,339 |
| 17 Sep | 640 |
| *(recovered — 18–24 Sep clean)* | |
| 25 Sep | 256 · **last success 11:09** |
| 26 Sep | 2,062 |
| 27 Sep | 1,836 |
| 28 Sep | 2,993 |
| 29 Sep | 3,152 |
| 30 Sep | 1,240 (partial day) |

**Over 11,500 failed calls since 25 September**, and the rate is climbing because nothing backs
off — the system retries into a closed door every sweep.

⛔ It also happened on **16–17 September** and recovered. So this is the second occurrence, and
nothing alerted either time.

## What is broken, by purpose — last 6 days

| Purpose | Succeeded | Failed |
|---|---|---|
| `l4_llm_decision` | 385 | **1,758** |
| `l4_llm_r1` | 273 | **1,677** |
| `l1_relevance` | 91 | **384** |
| `relevance_gate` | 88 | **308** |
| `moment.screen_insight` | 11 | **48** |
| `l1_extract` | **0** | 11 |
| `l4_bundle` | **0** | 2 |
| `screen_memory_batch` | 90 | 0 |
| `l5_render` | 1 | 0 |

`l1_extract` has **zero** successes. That is the extraction call — the one that reads meaning out
of a message. Nothing is being extracted.

## Why nothing looked broken

Every one of these lanes **fails open by design**, and that design is correct:

- `l1_relevance` files `llm5_unavailable` and **keeps** the event at authority 3000
- the extraction lane degrades rather than dropping
- the screen lane has its own rule path

So no queue backed up, no error page appeared, and the product kept producing output — just
without any judgment in it. **Silence without a receipt is indistinguishable from a bug; this was
the opposite — receipts everywhere and nobody reading them.**

## A second, separate defect found in the same ledger

```
n=116   model=claude-sonnet-5
        Error code: 400 — "`temperature` is deprecated for this model."
```

**116 calls to `claude-sonnet-5` fail because the code sends `temperature`, which that model no
longer accepts.** This is a real code bug and it is independent of the spend limit — it will still
fail after the limit is raised.

---

## What has to happen

| # | Action | Owner | Urgency |
|---|---|---|---|
| 1 | **Raise or remove the spend limit in the Anthropic Console** | Rohit | now — the product has no intelligence until this is done |
| 2 | Stop sending `temperature` to `claude-sonnet-5` | code — one call site | next |
| 3 | **Alert on this.** Two occurrences, eleven days apart, neither noticed. `llm_costs.success` already carries the answer; nothing reads it | code | next |
| 4 | Back off instead of retrying into a closed door — 3,152 failures in one day is a loop, not a workload | code | after 3 |

⛔ **Nothing measured above this line can be trusted as a statement about the product** until the
limit is lifted and one clean sweep has run. Every Layer 2, 3 and 4 number taken since 25 September
was taken with the model switched off.

## What this invalidates

- The Layer 1 relevance investigation — the 39% and then 100% Gmail failure was **this**, not a
  wiring or activation fault.
- `no_model_wired = 632` is unrelated and remains correct behaviour (screen instant lane, by
  design — see `layer-1-enterprise-signals/03-S1-FINDINGS.md`).
- Harsh's 29 Sep shadow-pass tallies (39 compiled / 39 reasoned of 66) were measured during the
  outage.
