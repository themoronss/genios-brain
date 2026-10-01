# What each graph looks like, and whether the Intelligence Graph is visible

**2026-09-25** · read from `api/routes.py` and `api/intelligence_routes.py`

---

## 1. ⛔ Both are already exposed. One as a graph, one as a string.

### The Evidence Graph has a real graph endpoint

`GET /graph` returns exactly the shape a force-directed view renders:

```json
{ "nodes": [{"id","name","type","email","last_interaction_days"}],
  "links": [{"source","target","type","weight"}],
  "entity_type_counts": {...}, "connected_tools": [...] }
```

Its own docstring: *"What the dashboard graph view renders; a node click drills into its facts via
read-models."* Plus `GET /graph/node/{id}` for the side panel, `GET /graph/as-of` for point-in-time,
`GET /graph/stats`, `GET /api/org/{id}/graph/health`.

⛔ **And it is seat-visible.** `unreadable_nodes()` removes any node known only from another seat's
private evidence; private edges and private facts are filtered too. **A colleague cannot see your
private mail through the graph view.**

### The Intelligence side is visible as a flat trace

`GET /v1/intelligence/decisions/{id}/explain` — *"which rules fired, at what confidence, as-of which
graph version."*

But look at how it renders the path:

```python
decision_path = " → ".join(item.get("reasoner_id", "") for item in results)
```

⛔ **That is a graph drawn as a string, because there is no graph to draw.** The arrows are
characters in a text field. The edges do not exist as data, so they cannot be rendered, clicked,
walked backwards, or counted.

**That one line is the whole Layer 3 gap, visible in the API.**

---

## 2. What each one LOOKS like — and they are different shapes

### The Evidence Graph is a **web**

Many-to-many, no natural direction, no time axis. Force-directed is the right view.

```
                    ┌─────────────┐
                    │    ACME     │  company
                    └──┬───────┬──┘
            owns       │       │   works_at
        ┌──────────────┘       └──────────────┐
        ▼                                     ▼
  ┌───────────┐                        ┌────────────┐
  │  Deal     │                        │   John     │  person
  │  #1120    │                        │ john@acme  │
  │ negotiation│                       └──────┬─────┘
  └─────┬─────┘                               │ attended
        │ concerns                            │
        │            ┌──────────────────┐     │
        └───────────►│ Meeting Tue 14:00│◄────┘
                     └────────┬─────────┘
                              │ raised_in
                     ┌────────▼─────────┐
                     │ Thread "Pricing" │  ball_in_court: them
                     └──────────────────┘
```

**12 node types, 6 edge types.** Click a node → its facts, each with its receipt.

### The Intelligence Graph is a **chain in time**

Directed, time-ordered, branching only when we revise. A force-directed view would be **wrong** for
it — it wants a timeline, closer to a `git log` than to a network.

```
 MON            TUE        WED              THU
  │              │          │                │
┌─────────────┐  │          │                │
│ SITUATION   │  │          │                │
│   s-88      │──┼──────────┼────────────────┼───────────┐
│ "Acme quiet"│  │          │                │           │
└──────┬──────┘  │          │                │           │
       │ about   │          │                │      about│
       ▼         │          │                │           ▼
┌─────────────┐  │          │                │    ┌──────────────┐
│ DECISION    │  │          │                │    │ DECISION d-2 │
│ d-1 "chase" │  │  noop    │                │    │  "no chase"  │
│ conf 7200bp │  │ (same    │                │    └──────┬───────┘
└──────┬──────┘  │  slice)  │                │           │
       │ delivered_as       │                │ supersedes│
       ▼                    │                │           │
┌─────────────┐             │                │           │
│  DELIVERY   │             │                │           │
│  card-7     │             │                │           │
└──────┬──────┘             │                │           │
       │ resulted_in        │                │           │
       ▼                    │                │           │
┌──────────────────┐        │                │           │
│ OUTCOME          │◄───────┼────────────────┼───────────┘
│ expired_untouched│        │                │
└──────────────────┘        │                │
```

**5 node types, 6 edge types.** Read it top-to-bottom and you get the sentence:
*"We saw Acme go quiet, decided to chase, sent a card, it was ignored, and on Thursday we changed
our mind."*

**Neither graph can be drawn in the other's view.** The Evidence Graph has no time axis; the
Intelligence Graph has almost nothing but one.

---

## 3. Where they join — exactly two seams

```
   EVIDENCE GRAPH (a web)              INTELLIGENCE GRAPH (a chain)

      ┌────────┐                            ┌───────────┐
      │  ACME  │◄──── anchor_node_id ───────│ SITUATION │
      └────┬───┘      (already exists)      └─────┬─────┘
           │                                      │ about
      ┌────▼──────┐                         ┌─────▼─────┐
      │ deal.stage│◄──── cited ─────────────│ DECISION  │
      │  fact     │   reasoning_evidence_    └───────────┘
      └───────────┘      id_map (0117)
```

⛔ **Both seams already exist in the schema and carry nothing.** `context_situations.anchor_node_id`
points at a real Evidence node today. `reasoning_evidence_id_map` maps a decision's evidence ids to
a `context_snapshot_id` today.

---

## 4. Is the Intelligence Graph visible? **Yes — on three surfaces, and never on a fourth**

### ✅ Surface 1 — on the card itself (the one that matters)

Not a graph. **One line.**

```
┌────────────────────────────────────────────────┐
│ Acme has gone quiet — 9 days                   │
│ ────────────────────────────────────────────── │
│ Why:  no reply since Mar 3 · stage negotiation │   ← EVIDENCE, with receipts
│                                                │
│ ⛔ 3rd time · you dismissed this on Tuesday    │   ← INTELLIGENCE, one line
└────────────────────────────────────────────────┘
```

**That single line is 90% of the product value of the whole layer.** It is also the line that
cannot be written today, because nothing can count to three.

### ✅ Surface 2 — decision explain, upgraded from a string to a walk

`/explain` already exists. Today its `decision_path` is `" → ".join(...)`. With edges it becomes
clickable in both directions: *what led here*, and *what came of it*.

### ✅ Surface 3 — the founder's view, which does not exist at all

```
Last 30 days
   decisions made         412
   delivered               —  needs delivered_as
   acted on                —  needs resulted_in
   superseded by us        —  needs supersedes
   repeated ≥3 times       —  ⛔ the number you most need
```

The data is in `execution_outcomes` — 7 terminal labels, `seconds_to_close`, `progress_bp`. It does
not join back to a situation, **so it can be counted and never explained.**

### ⛔ Surface 4 — the one it must NEVER appear on

**Never in the same panel as evidence, and never labelled as evidence.**

```
   ✅ RIGHT                            ⛔ WRONG
   Why:  no reply since Mar 3         Why:  no reply since Mar 3
         stage: negotiation                 stage: negotiation
   ───────────────────────                  this deal is at risk   ← our guess,
   3rd time · dismissed Tue                 dressed as a fact
```

A user who cannot tell *"nobody replied since Mar 3"* from *"this deal is at risk"* will eventually
be wrong about the second one and stop trusting the first. **The separation is not internal
hygiene; it is what the user reads.**

### And it inherits the same seat rule

`GET /graph` already hides nodes known only from another seat's private evidence. **A decision made
on private evidence must be invisible to a colleague the same way** — otherwise the Intelligence
Graph becomes a side channel around a privacy rule the Evidence Graph already enforces.

---

## 5. Summary

| | **Evidence Graph** | **Intelligence Graph** |
|---|---|---|
| **shape** | a **web** — many-to-many, no time axis | a **chain** — directed, time-ordered |
| **right view** | force-directed network | timeline / `git log` |
| **nodes** | 12 types, entities | 5 types: situation · decision · delivery · outcome · (interpretation) |
| **API today** | ✅ `/graph`, `/graph/node/{id}`, `/graph/as-of`, `/graph/stats`, `/graph/health` | ⚠️ `/decisions/{id}/explain` — **a path joined with `" → "`, not a graph** |
| **user sees** | the network view, and the *Why* on every card | **one line on the card**: *"3rd time · dismissed Tuesday"* |
| **privacy** | ✅ `unreadable_nodes()` filters per seat | must inherit the same rule |
| **visible?** | **yes, already** | ⛔ **yes — but never beside evidence, never as evidence** |
