# L2-3 · The evidence slice — handed, never fetched

**Needs Harsh:** no · **Migration:** none · **Model calls:** none

> ## ✅ COMPLETE — 2026-09-24 · [findings](findings/step-03-evidence-slice.md)
>
> 19 tests · 12,976 passed · 0 regressions · no migration · no model call.
>
> ⛔ **FOUR OF THE FIVE CRITERIA WERE ALREADY TRUE AND NOTHING WAS WATCHING THEM** — L2-0's finding
> in a different place. The builder does **zero I/O** (it cannot N+1 because it cannot query), the
> loaders are one org-wide query each, and the visibility rule **names *"a situation slice"* in its
> own docstring**. All four are now guarded.
>
> ⛔ **AND THE MEASUREMENT CONTRADICTED §2.** *"The difference between a 10,000-token thread and a
> 900-token slice is the whole bill"* holds for a small node and **stops holding for a busy one**:
> 8 facts → 714 tokens, but **100 facts → 8,049** — as much as the thread it replaces. The saving
> comes from the node being small, not from the slice being a slice. So the number became a
> **budget that reports and never truncates**, not a figure in a file.
>
> ⛔ **§0 AND §4 CONTRADICT EACH OTHER. §0 WINS** — one slice type, one builder. L2-1 just paid the
> bill for the alternative.

---

## 0. ⛔ CORRECTED — the slice builder exists and already carries typed absences

`situation_bso.build_context_slice` fills the slice, and at lines 2089–2090 it already puts
**`unknowable` and `absent`** into it, computed by `quality/missing.py` and read by
`packs/compiler/context_adapter.py:227` through the negative-inference licence.

> *"An org with no mailbox connected therefore satisfies `absent: thread.last_inbound` on every
> situation it has, and the authored rules that read it fire on a blind spot."*

**That loop is wired end to end.** This step therefore **extends the existing builder for a new
consumer**, and does not write a second one. A second slice builder would be a second answer to
"what may this reader see", which is the visibility defect waiting to happen.

---

## 1. Premise

The reasoner needs context. There are two ways to give it context, and **only one of them can be
replayed.**

```
FETCH    reasoner ──query──→ graph        replay impossible: the graph moved
HAND     graph ──slice──→ reasoner        replay exact: the slice is recorded
```

⛔ **This layer already made this decision once and wrote it down.** `SituationContextSlice`:

> *"The relevant Layer 2 graph slice supplied to Layer 3; **never fetched by Layer 3**."*

The reasoner gets the same treatment, for the same reason. A reasoner that can read the graph is a
reasoner whose answer cannot be reproduced — and the replay is what makes this an audit rather than
a re-guess.

---

## 2. What goes in the slice

The slice is **small on purpose**. Cost in L2 comes from tokens, not calls, and the difference
between a 10,000-token thread and a 900-token slice is the whole bill.

```
SLICE
├── the candidate                      what correlation assembled
├── observed facts about its entities  from graph_facts, with evidence refs
├── the timeline                       occurred_at ordering, not prose
├── coverage                           how much of the window was read
├── prior interpretations              what was concluded before, and when it expires
└── unknowns already recorded          so the reasoner does not re-discover them
```

And what is **deliberately absent**: raw message bodies beyond the cited spans, anything outside the
candidate's entities, and anything the seat may not see.

---

## 3. Units

### L2-3-U0 · Measure what a slice would weigh
Before building the builder: take ten real candidates and compute the slice size in tokens. **The
cost check for L2-5 depends on this number**, and guessing it would make that check theatre.

```
verify:  scripts/slice_weight.py --sample 10       # prints p50 / p90 token count
```

### L2-3-U1 · `ReasonerSlice` — the frozen contract
A type, not a dict. Frozen, with `graph_version` and `evaluation_time` stamped in, so two replays of
the same slice are provably the same input.

### L2-3-U2 · The builder — one read, bounded
Assembles the slice from the Evidence Graph in **one bounded read**. No N+1, no follow-on query, no
"while we are here" expansion.

```
verify:  pytest tests/context/test_slice_is_one_bounded_read.py -q
```

### L2-3-U3 · Visibility travels with the slice
⛔ A slice assembled for the org and handed to a reasoner acting for a seat is a **visibility leak
through a new door**. `fact_visibility.py` already governs who may read a fact; the slice builder
calls it rather than re-deriving it.

```
verify:  pytest tests/context/test_slice_respects_visibility.py -q
```

### L2-3-U4 · The slice is recorded with the situation
So a replay can reconstruct the exact input. Without this, `reasoning_trace` points at a conclusion
whose premises are gone.

---

## 4. What this step does NOT do

* **It does not call a model.** The slice is input; L2-5 is the caller.
* **It does not replace `SituationContextSlice`.** That one feeds the packs compiler and keeps its
  shape. This is a sibling with a different consumer.
* **It does not widen what the graph stores.** It reads.

---

## 5. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | slice weight p50/p90 recorded | ⚠️ **measured through the real builder** and turned into `SLICE_TOKEN_BUDGET`. p50/p90 on **real candidates** awaits the pilot — `scripts/slice_weight.py`, **Harsh 25** |
| 2 | `ReasonerSlice` frozen with `graph_version` + `evaluation_time` | ✅ **already true** — and **no new type**. §0 overrules §4 |
| 3 | one bounded read, proven by a test | ✅ **already true, and stronger than asked**: the builder does **zero I/O** — facts, observations and neighbours *arrive as arguments*, so it cannot N+1 because it cannot query |
| 4 | visibility through the existing rule | ✅ **already true**, and `_org_visible_clause` names *"a situation slice"* itself. Guarded at **both** fact loaders |
| 5 | the slice is persisted with the situation | ⛔ **HALF — the hash is stored, the slice is not.** A hash proves sameness and cannot reproduce the input. Deferred to **L2-5**, its only reader |

### 5.1 · ⛔ Where §0 and §4 disagree, and which one held

§4 says *"a sibling with a different consumer"*; §0 says *"a second slice builder would be a second
answer to what may this reader see."* **§0.** L2-1 measured the cost of two types sharing one job:
fifteen parameters across the Domain Expertise compiler annotated with the wrong one. On the field
that decides who may read what, that is not a risk worth re-running.

### 5.2 · What the units became

| planned | built |
|---|---|
| U0 · measure a slice's weight | ✅ `context/slice_weight.py` + `scripts/slice_weight.py` — **and it found §2's claim only half true** |
| U1 · `ReasonerSlice`, the frozen contract | ⛔ **struck.** It exists, frozen, with both versions. Guarded instead of rebuilt |
| U2 · the builder, one bounded read | ⛔ **struck.** Already true twice over. Guarded |
| U3 · visibility travels with the slice | ⛔ **struck.** Already true, upstream, and the rule says so. Guarded at both loaders |
| U4 · the slice is recorded | ⛔ **deferred to L2-5** — the hash is recorded; the slice is not |
| — | **unplanned: `SLICE_TOKEN_BUDGET`** — the measurement made actionable |
| — | **unplanned: `context/slice_silence.py`** — `evidence` is written by nothing, read by nothing, and **inside the content address**. Declared, with the 995 MB reason for not filling it |
