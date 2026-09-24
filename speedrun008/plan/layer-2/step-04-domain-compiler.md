# L2-4 · Domain Compiler — stop failing silently

**Needs Harsh:** no · **Migration:** none · **Model calls:** one, and only on a miss**

⛔ **This is the step Rohit named as most important: *"most important jo domain compiler, wo
perfectly kaam kare".*** It is also where the sharpest measured defect in Layer 2 sits.

---

## 1. ⛔ Premise — fundraising is structurally dark

`reason/domain_shadow.py:391`:

```python
_L2_TO_L3_DOMAIN = {"admin": "admin", "sales": "sales",
                    "support": "customer_support", "customer_support": "customer_support"}
```

```
L2 domains       admin · sales · support · FUNDRAISING · general
L3 corpora       admin · sales · customer_support
                                  ⛔ fundraising → NOTHING
                                  ⛔ general     → NOTHING
```

And `live_lane()`:

```python
if domain is None:
    return False        # no package, no signal — on EVERY tenant configuration
```

**The pilot tenant is a fundraising founder.** The benchmark is investors end to end — 3one4, Titan,
Neon, Antler, PeakXV, Surge, IIMA, Suvan. **Every fundraising situation resolves to `domain = None`,
publishes no package and emits no signal.**

That is the second half of *"domain expertise kuch kaam hi nahi kar raha hai"*. The first half is
ordering — expertise arrives after the conclusion. **The second half is that for the tenant's
dominant domain there is no expertise at all.**

### The mapping's own comment is right, and that is what makes this hard

> *"`fundraising` and `general` map to NOTHING and that is not an oversight: no corpus was authored
> for them... mapping them onto `admin` to 'get some coverage' would put Admin doctrine on a
> fundraising situation."*

**That decision is correct.** Borrowing Admin doctrine for an investor thread is how *"six VCs and
three accelerator programmes became sales opportunities"* happened in the first place. The fix is
not to re-point the mapping. **The fix is to stop the miss being silent, and then to author the
corpus.**

---

## 2. The second defect: it already failed silently once, for 33 situations

`domain_shadow`'s own comment:

> *"`variants_by_domain` is built from `live_domains`, which are corpus ids (`customer_support`);
> `row["domain"]` is Layer 2's (`support`). ... it silently returned `()` for every support
> situation on the tenant — **33 of them** — so that corpus could never receive an overlay however
> it was declared. `admin` and `sales` spell the same on both sides, **which is why the miss was
> invisible.**"*

⛔ **The compiler's failure mode is silence.** Same class of defect, twice, in the same function.

---

## 3. Units

### L2-4-U0 · Count the unroutable — before changing anything
How many situations resolve to `domain = None`, by domain, on the pilot. **This is the measurement
that makes the rest of the step honest**, and it is the number nobody has.

```
verify:  scripts/unroutable_report.py --org <pilot>     # prints count by L2 domain
```

### L2-4-U1 · `UNROUTED` becomes a counted outcome, not a `None`
⛔ **The single most valuable unit in this step.** Today an unroutable situation returns `None` and
disappears. It must land in the pass tallies with its domain named, exactly as a dropped signal in
L1 lands in the ledger with its reason.

*"DROP ≠ DELETE"* — L1 wrote that rule for signals. It applies to routing.

```
verify:  pytest tests/reason/test_unroutable_is_counted.py -q
```

### L2-4-U2 · A totality guard on `_L2_TO_L3_DOMAIN`
The repo idiom — `PRECEDENCE`, `SIGNAL_TYPE_WEIGHT_BP`, `ANCHOR_FAMILIES` all do this. **Every L2
domain gets a row**, and a row may map to `None` **only with a written reason**. An import-time check
fails if `domain_spec` grows a domain the table has never heard of.

This is the guard that would have caught `support` → `customer_support` before 33 situations died.

```
verify:  pytest tests/reason/test_domain_mapping_is_total.py -q
```

### L2-4-U3 · The `fundraising` corpus — the authored gap
Not code: **doctrine**. What an investor relationship going quiet means, what a stage gate is, what a
conditional re-engage looks like, when silence after a rejection cluster is a pattern rather than an
event.

⛔ **This is the largest non-code item in the whole Layer 2 plan**, and it is the one that decides
whether the pilot tenant sees anything at all. It needs a named author and an admission reviewer —
`require_admission` exists precisely so that unreviewed doctrine cannot carry authority.

### L2-4-U4 · Model on the miss, and only the miss
When nothing routes, **one Haiku call** asks *"which authored corpus is nearest, and how confident?"*
— and the answer is a **proposal for review**, never a route. Routing stays matching.

```
verify:  pytest tests/reason/test_miss_proposes_never_routes.py -q
```

---

## 4. Cost check

| | |
|---|---|
| model calls | **only on an unroutable situation** — expected ~5% |
| tier | Haiku |
| migration | none |
| the corpus | authoring time, not compute |

---

## 5. What this step does NOT do

* **It does not re-point `fundraising` at `admin`.** The existing comment is right and the borrowing
  would reproduce the original defect.
* **It does not make routing a model decision.** Matching stays matching; the model proposes at a
  miss.
* **It does not author the corpus inside this repo's code.** Doctrine is content, reviewed and
  admitted.

---

## 6. Completion criteria

1. Unroutable count measured and written into the findings file, by domain.
2. `UNROUTED` appears in the pass tallies — **a silent miss is now impossible**.
3. `_L2_TO_L3_DOMAIN` is total over `domain_spec`, with a reason on every `None`.
4. A miss produces a reviewable proposal, not a route.
5. The `fundraising` corpus has a named author, or the STATUS row says plainly that it does not and
   that fundraising stays dark until it does.
