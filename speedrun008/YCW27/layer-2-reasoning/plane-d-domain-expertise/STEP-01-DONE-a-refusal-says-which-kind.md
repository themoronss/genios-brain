# Plane D STEP 01 · `M11.C5.U05` · contract · a refusal says which kind it is · **DONE**

*(Level 0 — leaf. Nothing depends on it yet, by design: a contract unit that also changes behaviour
is two units.)*

## What was there

```python
class NoExpertiseRoute(DomainCompilerError):
    pass
```

Nothing. So the only way to tell its causes apart was to read the sentence it was built with — and
`scripts/corpus_route_probe.py`, the tool routing coverage is **read** from, did exactly that:

```python
text_ = str(exc)
if "unknown domains" in text_:   key = "unknown_domain_hint"
elif "no authored" in text_:     key = "no_route_predicate"
else:                            key = "no_route_type"
```

## ⛔ Three tests over FOUR causes — measured, not assumed

The plan said three. The resolver has **four** raise sites. Replayed the old classifier over the four
real messages before writing a line:

| raise site | message | old verdict |
|---|---|---|
| `:546` unknown hint | *"names unknown domains ['fundraising']"* | `unknown_domain_hint` ✅ |
| `:555` not activated | *"routes to ['sales'], none of which this tenant has activated"* | ⛔ **`no_route_type`** |
| `:720` predicate | *"matched the type index but no authored situation predicate"* | `no_route_predicate` ✅ |
| `:724` no binder | *"no expertise route for situation type 'vendor_renewal_decision'"* | `no_route_type` ✅ |

⛔ **`domain_not_activated` was published as `no_route_type`.** *"This tenant has not switched this
domain on"* reported as *"nobody authored a route for it."* **The raise site's own comment says those
two are different facts fixed in different places** — and the tool that measures coverage merged them.

And because the third branch is an `else`, **any rewording** of either sentence silently reclassifies
real failures into the one bucket this whole section exists to size.

## What was built

`NoExpertiseRoute.REASONS` — four, closed, validated at construction. `reason` is **required and
keyword-only**; `situation_type` rides along.

| reason | who fixes it |
|---|---|
| `unknown_domain_hint` | whoever set the hint — a **routing** bug |
| `domain_not_activated` | **operations** — `platform/l3_activation`. Often correct |
| `predicate_rejected` | the predicate's **author** — and possibly nobody: a `when` that declines is doing its job |
| `no_situation_binds_type` | **authoring** — somebody must own the type |

All four raise sites labelled. **19 tests.**

## ⛔ The right pattern was fourteen lines up, in the same file

`UnsupportedCoverage` already validates its reason against a closed set, with a docstring explaining
that folding distinct causes into one count meant the metric *"could never separate 'broken' from 'not
built yet'."* **The same argument, one class down, had never been applied.**

## Three decisions worth defending

⛔ **`reason` has no default.** A default lets a new raise site mint an unlabelled refusal that *reads*
as one of the four, and not guessing which is the entire point of the field. A test asserts the
parameter is keyword-only with no default.

⛔ **`situation_type` rides on the exception.** `domain_shadow` catches it inside a loop that still
holds the row, so it could supply the type itself — and then two places would decide what the pair
means. A raise that knows its own type and does not say so invites its caller to guess.

⛔ **Nothing behaves differently yet.** The message reaches a human unchanged, the class is still a
`DomainCompilerError`, and every existing `except` keeps working. A test asserts that
`UnsupportedCoverage` is still deliberately **outside** that hierarchy — its own docstring says
inheriting *"would put it one bare `except DomainCompilerError` away from being silently swallowed
again."*

## The measurement, kept as a test

`test_the_four_real_messages_were_genuinely_indistinguishable_to_three_tests` replays the old
classifier and asserts the two causes collapse — **so the finding can never be dismissed as
theoretical**, and if it stops holding, the test says to re-measure before trusting anything else.
