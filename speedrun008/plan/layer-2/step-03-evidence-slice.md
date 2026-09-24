# L2-3 · The evidence slice — handed, never fetched

**Needs Harsh:** no · **Migration:** none · **Model calls:** none

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

1. Slice weight measured on real candidates, p50 and p90 recorded in the findings file.
2. `ReasonerSlice` frozen, carrying `graph_version` + `evaluation_time`.
3. One bounded read, proven by a test that counts queries.
4. Visibility enforced through the existing rule, not a second copy.
5. The slice is persisted with the situation that used it.
