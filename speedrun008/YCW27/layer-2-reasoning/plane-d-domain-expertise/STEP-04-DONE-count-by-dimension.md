# Plane D STEP 04 · `M11.C5.U06` · logic · refusals counted by (reason × type) · **DONE**

*(Level 1 — depends on `U05`. A dimension needs something to be dimensioned by.)*

## What was there

```python
except NoExpertiseRoute:
    counts["no_route"] += 1
```

The plan said *"nothing in the engine reports it at runtime."* **Wrong** — it has been counted per
sweep all along. What was missing is **which type**.

> *"Twelve situations found no route"* is one type twelve times, or twelve types once. **Opposite
> problems, opposite fixes, same number.**

⛔ This is the rule this programme wrote for itself in L1: **a count without its dimension is not a
measurement.** First time it has come back to bite our own code.

## What was built

```
no_route                 12      ← unchanged
no_route_by_reason       {"no_situation_binds_type": 9, "predicate_rejected": 3}
no_route_by_type         {"vendor_renewal_decision": 9, "reply_owed": 3}
no_route_unbalanced      (present only when the three disagree)
```

**19 tests.**

## Five decisions

⛔ **The flat total is NOT replaced.** `tests/reason/test_the_cutover_is_declared_before_it_happens.py`
asserts on `"no_route": 0` and scripts read the same key. **Replacing a counter to improve it is how a
measurement wave breaks the gate that was watching it.**

⛔ **The reason is read off the exception, never off its message.** That is the whole point of `U05`,
and a test asserts `str(exc)` appears nowhere in the handler.

⛔ **Plain dicts BESIDE the `Counter`, not inside it.** `counts` is a `Counter` of ints; a mapping
stored among them makes `most_common()` and `Counter.__add__` raise on a type comparison the moment
somebody reaches for either. My first version put them inside — a latent hazard with no symptom today.

⛔ **Both keys are declared even when empty.** A key that appears only when it fires is a key nobody
knows exists. An absent `no_route_by_reason` reads as *"this build does not measure that"*; an empty
one reads as *"nothing was refused"*, which is the fact.

⛔ **A refusal that could not name its type is counted as `"unknown"`, not dropped.** A slice the pass
could not dimension must be visible **as that** — dropping it would silently unbalance the totals.

## The receipt, and why it cannot raise

The two breakdowns must sum to the flat total. They are **compared**, and a disagreement sets
`no_route_unbalanced` and logs — it does not raise.

> ⛔ *"A receipt that can abort the thing it is a receipt for turns an accounting failure into a product
> failure."* — `BundleStore.record_call`, already written down in this codebase.

A test walks the AST of the balance check and fails if it contains a `raise`.

## ⛔ No migration, and no sixth funnel stage

The funnel's stage vocabulary is **closed** and check-constrained in `0188`. A route-refusal **reason**
is not a sixth stage — it is the *why* behind an existing drop between `situations_formed` and
`capability_resolved`. Widening a closed taxonomy to hold a different kind of thing is how the taxonomy
stops meaning anything.

And **five migrations (0186–0190) are already unapplied in production.** A sixth for a returned-dict
key is not the trade to make now. Two tests assert both.
