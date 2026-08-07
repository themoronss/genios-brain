# Attention — "look here first"

*`context/attention.py` · `context_attention` · migration `0028`*

> A precomputed 0–100 score per node. It **orders** retrieval. It may **never gate** evaluation.
>
> That second sentence is a constitutional rule with a test attached, and it exists because the
> alternative is a loop the system cannot recover from.

---

## §1 · The starvation loop

If attention narrowed *what gets evaluated*:

```
low attention → never evaluated → produces no signals → attention never rises → …
```

The node is now permanently invisible, and nothing in the logs says so. **Evaluation scope stays
every node, every sweep.** Attention decides what a human or a UI looks at *first*, never what
the engine looks at *at all*.

Enforced by `tests/test_attention.py::test_attention_never_gates_evaluation`, which fails if any
file under `reason/` so much as contains the string `context_attention`.

A second test — `test_context_is_sole_writer` — keeps `deliver/`, `feedback/`, `capture/` and
`packs/` from writing the table. They may read it for ordering; L2 owns the number.

This is the same law that governs [node lifecycle](04-Graph-Health-Metrics.md#5--node-lifecycle--a-label-never-a-filter)
and [projections](../05-Business-Situation-Engine/03-Projections.md). Three appearances, one rule.

---

## §2 · The formula

Deterministic integer arithmetic over graph-local features. **No LLM. No floats stored.**

```python
score = recency + ball + commitment + question + polarity + signal   # clamped 0..100
```

| Component | Range | Rule |
|---|---|---|
| `recency` | 0–40 | ≤3d → 40 · ≤7d → 30 · ≤14d → 20 · ≤45d → 10 · else 0 |
| `ball` | 0–15 | 15 when `thread.ball_in_court == "us"` |
| `commitment` | 0–25 | 25 if an open commitment is **overdue**, 15 if merely open |
| `question` | 0–15 | 15 if a question was asked in the last **14 days** |
| `polarity` | 0–10 | 10 if recent negatives outnumber positives; 5 if positives lead; else 0 |
| `signal` | 0–20 | `max_open_signal_score // 5`, capped at 20 |

```python
band = "critical" if score >= 75 else "high" if score >= 50 else "medium" if score >= 25 else "low"
```

### Why the weights sit where they do

| Weight | Reasoning |
|---|---|
| **recency 40** — the largest | a dead thread is rarely the most useful thing to look at, whatever else is true of it |
| **commitment 25 > ball 15** | an overdue promise is a stronger claim on attention than an unanswered message |
| **overdue 25 vs open 15** | the same commitment becomes more urgent by crossing its date, not by existing |
| **polarity −/+ asymmetry (10 vs 5)** | trouble deserves attention; momentum deserves *some* |
| **signal ÷ 5, capped 20** | L3's signal scores are 0–100; letting them contribute a fifth keeps L2's own features from being drowned by a single loud rule |

`polarity` reads the last **90 days** (`POLARITY_WINDOW_DAYS`), `question` the last **14**
(`QUESTION_WINDOW_DAYS`). Questions age faster than sentiment.

### Everything is stored

```python
inputs = {"recency": 30, "ball": 15, "commitment": 25, "question": 0,
          "polarity": 10, "signal": 12, "last_activity": "2026-08-04T09:12:00Z"}
```

Written to `context_attention.inputs` as jsonb. **A score nobody can account for is a score
nobody should act on** — the same reason situation confidence stores its arithmetic.

---

## §3 · What it runs over

Only `person` and `deal` nodes. Companies and canon documents are not scored — attention answers
*"who should I look at?"*, and a company is looked at through its people and its deals.

```python
refresh_attention(store, org_id, node_ids=None, eval_time=None)
```

Called at the **end of the L2 drain**, after read models. Wrapped in a bare `except` and
deliberately non-fatal: attention is an ordering hint, and a stale hint must never stop events
from landing.

Shape: a handful of **org-wide bulk queries** (facts, observations, open signals), then one
upsert per node. One query per concept beats one per row.

---

## §4 · The one cross-layer read

```sql
select subject_node_id, max(score) from signals where org_id = :o and status = 'open'
```

Layer 2 reading Layer 3's `signals` table looks like a layer violation. It is a **data read of
an output**, not a call into L3 logic — and it is the only way attention can know that a rule
already fired about this node.

The direction that would be illegal is the reverse: `reason/` reading `context_attention`. That
is exactly what §1's test forbids.

---

## §5 · Worked example

A prospect, `john@acme.io`:

| Feature | Value | Points |
|---|---|---|
| last activity | 4 days ago | `recency` 30 |
| `thread.ball_in_court` | `"us"` | `ball` 15 |
| open commitment | due 2 days ago | `commitment` 25 |
| question asked | 20 days ago | `question` 0 *(outside the 14-day window)* |
| recent observations | 2 negative, 1 positive | `polarity` 10 |
| highest open signal | 60 | `signal` 12 |
| | **total** | **92 → `critical`** |

Move the last activity to 30 days ago and the score drops to 72 — `high`, not `critical` —
without any of the other facts changing. Recency is the dominant term by design.

---

## §6 · Edge cases

| Case | Behaviour |
|---|---|
| No dated activity at all | `recency = 0`; other components still contribute |
| `ball_in_court` stored as JSON `"us"` with quotes | stripped before comparison |
| A node with no facts or observations | scores 0, band `low` — **still evaluated** |
| Merged node | `context_attention` is repointed by `merge.py:_NODE_REFERENCES` |
| Refresh fails | swallowed; the previous score stands until the next drain |

---

## §7 · Attention vs situation confidence — different questions

Easy to confuse; they answer opposite things.

| | Attention | Situation confidence |
|---|---|---|
| Question | *how urgently should someone look?* | *how much should we believe this?* |
| Subject | a node | a situation |
| Composition | **sum** of features | **minimum** of dimensions |
| High score means | act soon | trust it |
| Written by | `attention.py` | `situations.py` |

A situation can be highly confident and low attention (a resolved deal we are sure about), or
high attention and low confidence (a customer going quiet, on one unverified email). The second
combination is the one worth surfacing — and worth surfacing *with* its confidence attached.

---

*Related: [Confidence Vector](01-Confidence-Vector.md) · [Graph Health](04-Graph-Health-Metrics.md) · [Edges](../01-Enterprise-Context-Graph/03-Edges.md)*
