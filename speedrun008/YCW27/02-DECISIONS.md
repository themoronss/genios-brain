# Four decisions that block every layer

Each one is **recorded as enforced code, not prose**, when it is made — a constant plus a test that
fails when the code drifts from it. A decision written only in a document is a decision that will
be re-litigated in six weeks.

**Status:** all four open. Unit ids are `M8.C2.*` in `tree.yaml`.

---

## 1 · The confidence vector's axes · `M8.C2.L-contract.V0.U05`

**They do not match, and only two of six overlap.**

```
code  (contracts/situation.py):  evidence · freshness · consistency · identity · coverage · analytic
Atlas (A.4):                     evidence · frame · temporal · causal · authority · coverage
```

The code's axes also carry a law the Atlas does not state for its own:

> *"`overall_bp` is bounded by the weakest axis that went into it. Composition is otherwise a
> machine for manufacturing certainty: several weak axes agreeing is not corroboration, and a mean
> over them produces a number larger than anything it was computed from."*

And every axis is **nullable on purpose** — `coverage_bp: None` means *"we never declared what
complete means for this domain"*, which must read as neither covered nor absent.

**This is live right now, not theoretical.** One of the seven `pg` failures is
`situation_publisher` asserting five axes including `coverage`, against `situations.py:366` which
documents `coverage` as legitimately unknown for a domain registering no field expectations.

**What has to be decided**

- Keep the code's six and correct the Atlas; or
- adopt the Atlas's six and migrate `ConfidenceVector`, `compose_*`, the publisher and the pg test; or
- keep both — code axes as the *measurement*, Atlas axes as the *card's reading* — with an explicit
  mapping and the weakest-axis law preserved.

**Blocks:** L2 lanes (`M11.C2`), L5 card + floor replacement (`M13.C2`), and closing that pg failure.

---

## 2 · Where correlation lives · `M8.C2.L-contract.V0.U06`

The Atlas draws **one** Signal Correlation component inside L1. The code has **ten** correlator
modules in `context/` — 5,234 lines — and every one of them reads the graph.

The Atlas puts the graph in L3, **downstream** of L1. So correlation-in-L1 would need L1 to read
L3: an upward import, which `tests/test_layer_topology.py` fails the build on.

**What has to be decided**

- Correct the picture — correlation stays in `context/`, and L1 gets only *incoming-signal*
  bundling that never reads the graph (this is what `M9.C1` is written for); or
- split it for real — bundling down into L1, relationship reasoning up into L2 over the L3 graph —
  which is a genuine migration of 5,234 lines and needs its own milestone.

**Recommendation on record:** the first. The picture is cheap to fix; the code is not, and the
group law the correlators already follow — *"correlation answers one question: do these belong to
the same thing? It does not prioritise, score risk, or recommend"* — is already correct.

**Blocks:** L1 bundle scope (`M9.C1`), and the L3 chapter's boundary.

---

## 3 · The naming freeze · `M8.C2.L-contract.V0.U07`

Several Atlas names already exist in code under different names. Nobody may start a layer until it
is settled which side moves, because every diff depends on it.

| Atlas name | Code name that already holds it | Where |
|---|---|---|
| `ReasoningResult` | `ReasoningDecision` | `contracts/reasoning.py:1344` |
| `DecisionObject` | `ReasoningDecision` + `DECISION_PROJECTIONS` | settled by `test_the_decision_object_is_one_object.py` |
| `DeliveryResult` | `DeliveryObject` / `DeliveryDecision` | `contracts/delivery.py` |
| decision brief | `brief.v1` | `executive/brief.py` |
| coverage receipt | `SourceCoverage` + the window read | `capture/coverage/`, `context/quality/window.py` |

The output is **one table in `docs/LAYER_MAP.md`** plus a totality guard (`M8.C2.V1.U09`) that
fails in **both** directions: a name the Atlas uses that the code does not hold, *and* a boundary
contract the code holds that the Atlas never names. One direction alone is half a guard.

**Blocks:** every contract unit in M9, M10, M14.

---

## 4 · Is a "layer" the package or the product layer? · `M8.C2.L-contract.V0.U08`

`context/` is product **L2 and L3**. `reason/` is product **L2 and L4**. If we schedule "L2 work"
and "L3 work" as separate passes, both will edit `context/` and collide — one writer per file is a
rule this repository already keeps.

**What has to be decided**

- Address work by **package** (`capture`, `context`, `reason`, …) and treat the product layer as a
  label only; or
- address by **product layer** and first split `context/` and `reason/` along the seam — a large
  refactor that has to be its own milestone, not a side effect.

**Recommendation on record:** address by package; keep the product numbering for the Atlas, the
deck and the customer conversation. `LAYERS.py` already says it: *"always name the package, never
the digit alone."*

**Blocks:** the scheduling of M10 and M11 against each other.

---

## How a decision gets closed

1. Decide, in one line, with the rejected option named.
2. Record it where the code reads it — `LAYERS.py`, `docs/LAYER_MAP.md`, or the contract itself.
3. Add the test that fails when code drifts from it.
4. Only then open the layer folder that was waiting on it.

---

## ⛔ 2026-10-01 · STATUS UPDATE — the header's *"all four open"* is no longer true

The line at the top of this file was correct when written on 2026-09-30. It is corrected here rather
than edited, because a status line that reads as current is exactly the defect that cost seven step
files their titles (`07-LEDGER` PART 3). **Two of the four are closed.**

| | Decision | Status now | Evidence |
|---|---|---|---|
| **1** | the confidence vector's axes | 🔴 **OPEN · Rohit** | 3 options; recommendation on record is **A** — keep the code's six axes and correct the Atlas. Only 2 of 6 axes overlap, so this cannot be split |
| **2** | where correlation lives | 🟢 **CLOSED in practice** | correlation stayed in `context/` (product L3). `docs/LAYER_MAP.md:127,139` records the condition split as *"deliberate and load-bearing"*, with L1 keeping `extraction.Commitment.is_conditional` + `.condition_text` and `correlation_timeline.DormantCondition` staying L3. The Atlas's L1 placement would have required an L1→L3 read, which `tests/test_layer_topology.py` fails the build on. **What remains is editing the Atlas, not the code** |
| **3** | the naming freeze | 🔴 **OPEN · Rohit** | still only the options. `ReasoningDecision`/`ReasoningResult`, `DeliveryObject`/`DeliveryResult`, `brief.v1`/`DecisionObject`. ⛔ **Nothing is blocked on it** — every layer was built on the code's names, so this is now a documentation decision, not an architectural one. It got cheaper by being deferred |
| **4** | is a "layer" the package or the product layer? | 🟢 **CLOSED · in code** | **the product layer.** `genios_engine/LAYERS.py` is the single source of layer numbers; `docs/LAYER_MAP.md` is the translation table — *"Four specs number the layers four different ways. Nobody says 'L5' without a package name attached"*; and `tests/test_layer_topology.py` **fails the build** on an upward import. Enforced, not merely agreed |

### ⛔ The thing worth noticing about #1 and #3

Both were called *blocking* at the start of the programme — *"every upper layer depends on them."*
**All six layers and both planes were then built without either being settled**, because both turned
out to be about **names and axis labels**, not about data flow. #4 was the one that actually blocked,
and it blocked by being enforceable in a test.

That is the correction worth carrying forward: a decision that can be enforced by a test is the kind
that blocks. A decision about what to call something can almost always be deferred, and deferring it
made it cheaper rather than more expensive.
