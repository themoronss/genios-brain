# L3-11 · Three-valued predicates — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ Ninth and tenth premises wrong — it is all built

| the plan said | measured |
|---|---|
| *"no three-valued `true / false / unknown` predicate type"* | ⛔ `PredicateState.TRUE / FALSE / UNKNOWN` ＋ `PredicateVerdict` |
| *"the eight quality components exist as scattered reads, not a verdict"* | ⛔ `context/quality/` — `lens`, `missing`, `inference`, `epoch`, `refusals` |
| *"`unknown` must never silently become `false`"* | ⛔ `quality/inference.may_infer_absent`, **wired** into `context_adapter.evaluate` |

`quality/inference.py` opens by naming the exact failure it was built for:

> *"Both answer TRUE today whenever the thing is not in the slice — with no reference of any kind
> to whether a source that could have carried it was connected. **An org with no mailbox connected
> therefore satisfies `absent: thread.last_inbound` on every situation it has**, and the authored
> rules that read it fire on a blind spot."*

**Tri-state is idiomatic throughout** — `bool | None` in 42 files, with `ready_for` returning `None`
for "nobody declared" rather than `False`.

---

## 2. ⛔ What is open, and it is declared by the code that has it

```
"may_infer_absent is `path not in unknowable`, and unknowable_fields holds only what somebody
 DECLARED unknowable — so A PATH NOBODY CLASSIFIED FALLS THROUGH TO 'LICENSED', and this branch
 concludes absence from silence… Closing it means making the coverage map TOTAL… and would turn
 MOST absent: answers into abstentions until it is done."
```

⛔ **This is a fail-OPEN default in a module where every other branch fails closed.**

And it contains an admission worth keeping:

> *"A first cut of this comment shipped a `may_infer_absent` call here as if it fixed that. It could
> not: the `unknowable_fields` test three lines above has already returned, so the call can only
> ever answer True. Recorded rather than deleted, because **a no-op wearing a fix's comment is
> worse than the gap it claims to close.**"*

### 2.1 · ⛔ "Most" is an unmeasured word, and a decision not to act was resting on it

The reason for not closing the gap is that it *"would turn **most** `absent:` answers into
abstentions"*. **Nobody has measured "most."**

That is exactly what this plan's cost checks exist for: **10× became 2.9×; "the largest saving in
the plan" became ~$3/month.** A number can be argued with. An adjective cannot.

**So this step does not close the gap — closing it is a product decision about abstention rates. It
makes the gap COUNTABLE.**

`ABSENT_OUTCOMES` — five named buckets, counted **where the branch happens**:

| | |
|---|---|
| `refused_unknowable` | declared unknowable, no inference licensed |
| `finding_typed_absent` | the intelligence — absence as TRUE |
| `abstained_missing` | missing but untyped → UNKNOWN |
| ⛔ `unclassified_licensed` | **THE GAP** — nobody classified it, absence concluded from silence |
| `held` | the fact is present |

⛔ **Counted at the branch, not inferred from the verdict, because TRUE from "typed absent" and
TRUE from "nobody looked" are the same value** — which is precisely why the gap was invisible.

---

## 3. ⛔ My own counter crashed the compiler

The first cut initialised the tally in `__init__`. **Four tests failed instantly** with
`AttributeError` on *every* `{absent: …}` evaluation, because
`test_the_borrow_reaches_the_rule_gate` builds its adapter with
`ContextAdapter.__new__(ContextAdapter)` — *"constructed directly rather than through a fixture"*.

⛔ **A counter had been given the power to crash the compiler.** That is L2-7's lesson at a third
seam in this layer: *"a receipt that can abort the thing it is a receipt for turns an accounting
failure into a product failure."*

**The tally is now a lazy property that cannot raise**, and a test pins that an adapter built
without `__init__` still has one. **A tally may be wrong, empty, or never read. It may not raise.**

---

## 4. Two more of my test bugs

* the `absent` branch slice split on the **first** `may_infer_absent` — which is in a **comment**
  (eleventh in the family; comments stripped)
* the gap-counting test asserted the **line existed** and stayed green when its branch became
  `elif False:` — **present and unreachable.** ⛔ **Now behavioural: it runs the evaluator and
  asserts the counter moved.**

---

## 5. Result

```
FULL SUITE   13,254 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-11: 13,244 passed · 14 failed
```

**+10 tests · 0 regressions · no migration · no model call.**

**Technique 3 — five mutations, all red:** the licence re-derived; the gap uncounted; the gap's
bucket stops saying it is the gap; the gap branch unreachable; the no-op warning deleted.

## 6. What this step does NOT do

* ⛔ **It does not close the fail-open default.** That turns `absent:` answers into abstentions at
  a rate nobody has measured — **which is now measurable, and is Rohit's call once it is.**
* **It changes no verdict.** Every predicate answers exactly what it answered.
