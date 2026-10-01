# Step 2 — DONE · `temperature` sent to models that refuse it · owner: us

> **Status:** DONE · tests green · **not deployed**
> **Written:** 2026-09-30 · found in `llm_costs` while investigating Step 1
> **Evidence:** [`findings/step-02-temperature.md`](findings/step-02-temperature.md)

---

## 1 · The finding, in one line

**`l4_bundle` had made 600 model calls and succeeded zero times**, 13 → 25 September, every one
refused with `"`temperature` is deprecated for this model."` The reasoning narrator has never once
produced a bundle.

## 2 · What was expected vs. what was true

| Expected | True |
|---|---|
| a flaky lane | a lane that has **never** worked |
| a model or key problem | our own request carried a field the model refuses |
| nobody knew | ⛔ **`reason/llm_decision_maker.py` knew, and worked around it privately** |

`llm_decision_maker` held the list of models that reject sampling and solved its own problem by
building a **separate thin client** — leaving every other lane on the shared client still sending
`temperature`.

> A second copy of a closed set is a set that drifts. **The module that sends the field must own
> which models accept it.**

## 3 · What we changed

| File | Change |
|---|---|
| `context/llm/client.py` | `NO_SAMPLING_PREFIXES` + `accepts_sampling(model)`; `call()` omits the field for those models |
| `reason/llm_decision_maker.py` | local copy **deleted** — imports the one list (`reason` → `context` is a legal downward import) |
| `tests/context/test_sampling_is_omitted_where_it_is_refused.py` | new · 14 tests |

## 4 · What we deliberately did NOT change

⛔ **`temperature=0` is still sent to every model that accepts it.** It is the determinism this
engine's replayability rests on. The field is *omitted where refused*, never *removed*. One test
exists purely to stop a later reader "simplifying" this into "stop sending temperature".

## 5 · Scenario → expected result

| Scenario | Expected |
|---|---|
| a call to `claude-sonnet-5` / `opus-5` / `opus-4-8` / `opus-4-7` / `fable` | no `temperature` in the request |
| a call to any Haiku-class model | `temperature=0`, unchanged |
| a model we have never seen | `temperature=0` — the default every Haiku call already ran under |
| someone re-adds a local copy of the list to `llm_decision_maker` | ⛔ **the build fails** |

## 6 · Proof

```
tests/context/test_sampling_is_omitted_where_it_is_refused.py      14 passed
tests/test_layer_topology.py + test_every_llm_call_site_is_metered  12 passed
full suite                                                     13,365 passed · 1 failed*
```

\* the 1 is pre-existing and environmental — see [Step 8](STEP-08-PENDING-HARSH-ocr.md).

## 7 · Still true after this fix

⛔ `l4_bundle` will **still** produce nothing until the account's API spend limit is raised — see
[Step 4](STEP-04-PENDING-api-limit.md). This removes one of the two reasons it was failing.
