# Plane D STEP 06 · `M11.C5.U07` · interface · read the field, never the message · **DONE**

*(Level 2 — last. Deleting the string match before the field existed would have left the probe unable
to tell the causes apart at all.)*

## What was there

`scripts/corpus_route_probe.py:106` — the tool routing coverage is **read** from:

```python
text_ = str(exc)
if "unknown domains" in text_:   key = "unknown_domain_hint"
elif "no authored" in text_:     key = "no_route_predicate"
else:                            key = "no_route_type"
```

⛔ **The blunt-grep family, in a measurement tool.** *"Assert on structure — never on text that happens
to sit near a thing."* And the third branch is an `else`, so **any rewording of either sentence
silently reclassifies real failures into the one bucket this probe exists to size.**

## What was built

`_PROBE_KEY` — reason → output key, closed against `NoExpertiseRoute.REASONS` **at import time in both
directions**. The handler reads `exc.reason`. The three string tests are gone. **13 tests.**

| reason | output key | |
|---|---|---|
| `unknown_domain_hint` | `unknown_domain_hint` | unchanged |
| `predicate_rejected` | `no_route_predicate` | unchanged |
| `no_situation_binds_type` | `no_route_type` | unchanged |
| `domain_not_activated` | `domain_not_activated` | ⛔ **new — it used to land in `no_route_type`** |

⛔ **The three existing output keys keep their exact names.** Reports and saved CSVs read them.
Renaming a key to improve a taxonomy breaks every reader of the measurement the taxonomy was improved
for.

⛔ **The sample message is still captured.** The structured field replaces the **diagnosis**, not the
evidence: an operator still needs the sentence to see which situation and which domains.

## The guard, and why it had to be an AST walk

A test walks `corpus_route_probe.py`, `domain_shadow.py` and `capability_resolver.py` and fails on any
comparison against an exception's text, or any name bound from `str(exc)`.

⛔ **It cannot be a grep, and the reason is concrete:** the probe now carries the old code **quoted in a
comment**, deliberately, so the next reader understands why the field exists. **A grep for `str(exc)`
would match that comment and fail on the documentation of the fix.**

This session broke the same rule four times — twice in L5, twice in L6 — before writing it into its
own tests. Here it was written first.
