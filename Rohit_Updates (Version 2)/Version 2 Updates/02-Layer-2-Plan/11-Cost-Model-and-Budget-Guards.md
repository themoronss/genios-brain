# L2 — Cost Model and Budget Guards

> **What this document can and cannot give you.** It gives the cost *structure*, the
> *drivers*, and the *guards*. It does not give a rupee figure, and any document that did
> would be fabricating one — Globe's own open-blocker list says so:
>
> *"Reference cost unit not benchmarked on real hardware — gross margin per unit of work
> is currently unknown, so **pricing is unfounded**."*
>
> That blocker is still open. What follows is the model to instrument, not a forecast.

---

## 1. The structural insight — L1 and L2 have inverted cost shapes

| | Layer 1 | Layer 2 |
|---|---|---|
| Fires on | **every event** (~6,000 per 60-day backfill) | **situations only** (~50–150 active) |
| Context per call | small — one message, 8–24k chars | **large** — situation + members + graph slice |
| Shape | **high volume, low context** | **low volume, high context** |
| Dominant lever | **batching + tiering** | **gating + caching** |

**L2's LLM volume is roughly one to two orders of magnitude lower than L1's.** Per call it
is more expensive, because a situation carries more context than a message. But it fires
far less often, and the levers that control it are different ones.

**Practical consequence:** do not reuse L1's batching strategy at L2. Batching a
situation-framing call gains almost nothing (there are 30 of them, not 6,000) and it costs
you the per-situation cache key, which is worth far more.

---

## 2. The cost equation

```
L2_daily_cost = Σ  over the 9 sites:

    fires_per_day
      × (1 − cache_hit_rate)
      × (input_tokens + output_tokens)
      × tier_rate
```

Four levers, in order of how much they matter:

| # | Lever | Effect |
|---|---|---|
| 1 | **Gating** — deterministic first | reduces `fires_per_day`, often by 10–20x |
| 2 | **Caching** — stable key | reduces effective fires by the hit rate |
| 3 | **Tiering** — T1/T2/T3 | reduces `tier_rate` |
| 4 | Context trimming | reduces `input_tokens` |

---

## 3. Per-site budget table

Volumes are **estimates for an active small-team org** and are the thing to measure first.

| Site | Tier | Gate that limits volume | Est. fires/day | Cacheable? |
|---|---|---|---|---|
| M-1 entity linking | T1 | only when the alias+domain cascade is inconclusive | 1–5 | yes — by entity pair |
| M-2 edge typing | T1 | only when the rule table cannot type it | 2–10 | yes — by claim hash |
| M-3 conversation matching | T1 | only the gray band of subject/participant/time overlap | 3–15 | yes — by thread pair |
| **M-4 resolution** | **T2** | **only ACTIVE situations with new activity, and only when `terminal_by_fact` is False** | **10–30** | **partially** — new message means new call |
| M-5 condition parsing | T2 | only conditional commitments a pattern could not parse | 1–5 | yes — by condition text |
| **M-6 framing** | **T2** | **only new or materially-changed situations** | **10–40** | **yes — by member-set hash** |
| M-7 timeline | T2 | folded into M-6 where possible | 5–20 | yes — same key |
| M-8 clustering | T1 | only ambiguous pairs after deterministic merge | 2–8 | yes — by situation pair |
| **M-9 cohort authoring** | **T3** | **on demand only — never in a sweep** | **0 baseline** | n/a |

### The two that need watching

**M-4** and **M-6** together are the bulk of L2's spend. Both have hard gates:

- **M-4 fires only when a message lands on an open situation.** 100 active situations with
  activity on 20 of them today means **20 calls, not 100**.
- **M-6 fires only when a situation's member set changes.** A stable situation is framed
  **once**, not daily. That is the difference between 40 calls a day and 400.

**M-9 is T3 and never runs in a sweep.** It fires when a founder types a cohort request.
Zero baseline cost.

---

## 4. The cache key

Same discipline as L1's extraction cache, which already exists and works:

```
key = sha256(
    org_id : site_id : subject_id : member_set_hash :
    PROMPT_VERSION : SCHEMA_VERSION : model_snapshot
)
```

**`member_set_hash` is the important component.** A situation whose members have not
changed does not need re-framing. Include it and a stable situation costs nothing after
its first framing; omit it and you pay daily for an unchanged answer.

**Expected steady-state hit rate: 70–85%.** Below 70% is an alert, not a cost problem —
it means the key is churning, and a churning key almost always means something is being
included that should not be (a timestamp, a counter, an unordered set serialized
unstably).

---

## 5. Budget guards

| Guard | Default | On breach |
|---|---|---|
| Per-org daily L2 LLM calls | **200** | stop making L2 calls; fall back deterministically |
| Per-org daily USD (L1 + L2 combined) | reuse the existing circuit breaker (`7e17a6d`) | refuse to START a new sync |
| M-9 (T3) | on demand only | never scheduled |
| Cache hit rate | floor 70% | alert — the key is broken |
| M-4 fires per situation per day | max 3 | further messages wait for the next day |

### The fallback rule — fail closed, never fail silent

**Every one of the nine sites has a deterministic fallback, and the fallback is a real
code path, not a theoretical one:**

| Site | On budget exhaustion |
|---|---|
| M-1 | no merge proposal — entities stay separate |
| M-2 | edge typed `related_to` (generic) and flagged |
| M-3 | threads stay uncorrelated |
| **M-4** | **falls back to `terminal_by_fact` only** |
| M-5 | condition stored unparsed, human review queue |
| **M-6** | **deterministic template headline** |
| M-7 | chronological timeline, no narrative |
| M-8 | situations stay separate (clustering under-merges) |

**Note the direction of every fallback.** Each one degrades toward *doing less*, never
toward *guessing more*:

- M-4 exhausted → we may **miss** a resolution. We never **invent** one.
- M-6 exhausted → a **plainer** card. Never a wrong one.
- M-8 exhausted → **three** cards about one thing (noisy) rather than one card merging
  two unrelated things (wrong).

**And every fallback logs.** A silent degradation is indistinguishable from a bug, and it
would be discovered as *"the product got worse and nobody knows when"*.

---

## 6. What to instrument first

Before tuning anything, measure these six numbers on one pilot tenant for one week:

| # | Metric | Why it is first |
|---|---|---|
| 1 | fires/day per site | every estimate in this document is a guess until this exists |
| 2 | cache hit rate per site | the single largest lever |
| 3 | input tokens per call, p50 and p95 | p95 is what actually costs; p50 misleads |
| 4 | tier distribution | if T2 share is above 40%, gating is too loose |
| 5 | fallback invocations per site | a fallback firing often means a guard is mis-set |
| 6 | **cost per delivered card** | **the only number that matters commercially** |

**Row 6 is the one to report.** Cost per call is an engineering metric; cost per card the
founder actually reads is the unit economics. A card that resolves a \$84K renewal
question is worth a great deal more than a fraction of a cent of inference, and that ratio
is the argument for the whole architecture — but it has to be measured, not asserted.

---

## 7. The honest bottom line

**Going heavy on the LLM at L2 does not multiply the bill**, for three structural reasons:

1. **Volume is low** — situations, not events. One to two orders of magnitude below L1.
2. **Gating is aggressive** — every site sees only the remainder a rule could not settle.
3. **Caching is effective** — a stable situation is framed once, ever.

**What could go wrong, and what to watch:**

- **Cache key churn** is the fastest way to turn a cheap layer into an expensive one.
  Watch the hit rate before watching the spend.
- **M-4 on a very noisy thread** could fire repeatedly; the per-situation daily cap of 3
  exists for exactly that.
- **Situation count growth** is the real scaling driver. If pattern matching (L2.6) is
  tuned too loosely, situation count rises and every per-situation site scales with it.
  **The cost control for L2 is therefore partly a *precision* control** — a pattern that
  fires too often costs money twice, once in inference and once in the founder's trust.
