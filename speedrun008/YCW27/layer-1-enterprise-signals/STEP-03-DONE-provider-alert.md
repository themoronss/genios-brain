# Step 3 — DONE · nothing noticed when the provider stopped answering · owner: us

> **Status:** DONE · tests green · **not deployed**
> **Written:** 2026-09-30
> **Evidence:** [`findings/step-03-provider-outage.md`](findings/step-03-provider-outage.md)

---

## 1 · The finding

**Five days with no working model call anywhere in the product, and no alert.**

```
last successful call:  2026-09-25 11:09:30 UTC
failures 26 → 30 Sep:  2,062 · 1,836 · 2,993 · 3,152 · 1,240
```

It had also happened on **16–17 September** and recovered on its own. **Neither occurrence was
noticed.**

## 2 · What was expected vs. what was true

| Expected | True |
|---|---|
| the data was missing | ⛔ `llm_costs.success` and `.error` recorded **every** failure, both times |
| nothing watched spend | an alert `platform_llm_cap_hit` exists — it watches **GeniOS's own** governor, which was behaving perfectly |
| something would have broken visibly | every lane **fails open by design**, so no queue backed up and the product kept producing output with no judgment in it |

> This is `not_carried` in a new place: a value computed correctly, written down correctly, and
> consulted by nothing.

## 3 · What we built

| File | Change |
|---|---|
| `platform/provider_health.py` | new · a streak watch over provider-side refusals → `ops_alert.notify("provider_refusing_calls", …)` |
| `context/graph_store.py` | `record_cost` observes it — *"every LLM call in the engine lands here"*, the same argument that already put PostHog reporting at this seam |
| `tests/platform/test_the_provider_refusing_calls_is_noticed.py` | new · 21 tests |

## 4 · The four design choices, and why

| Choice | Why |
|---|---|
| **a streak, not a rate** | a rate needs a window, a denominator and a clock — all wrong on a quiet tenant (two calls, one failure = "50%"). Twenty in a row cannot happen by chance |
| **only provider-side refusals count** | `unparseable JSON` is *ours*. An alert that fires for two reasons is one nobody reads |
| **our failures do not clear the streak either** | a bad prompt in the middle of an outage must not reset the count and hide it |
| **one-hour cooldown** | the real outage made 3,152 failures in a day; without it that is 3,152 messages |

⛔ **`temperature is deprecated` is deliberately NOT a provider refusal.** That was our bug
(Step 2). Alerting on it would send the on-call to the provider's console for a defect in our own
request.

## 5 · Scenario → expected result

| Scenario | Expected |
|---|---|
| 19 consecutive provider refusals | **silence** — transient 429s under retry must not page anybody |
| 20 consecutive | **one** alert |
| 520 consecutive | still **one** alert (cooldown) |
| a success on any lane | streak clears |
| `unparseable JSON` mid-outage | no alert, and the streak does **not** reset |
| the ops webhook itself is down | the accounting write still completes — the alert never breaks its caller |
| someone deletes the call from `record_cost` | ⛔ **the build fails** |

## 6 · Proof

```
tests/platform/test_the_provider_refusing_calls_is_noticed.py   21 passed
tests/platform + tests/context + tests/reason                3,828 passed · 0 failed
```

## 7 · What this changes operationally

Before: an outage was invisible for five days, twice.
After: it is visible within minutes of a normal sweep, naming the model, the purpose, and
**what to check** — the account's spend limit and key in the provider console.
