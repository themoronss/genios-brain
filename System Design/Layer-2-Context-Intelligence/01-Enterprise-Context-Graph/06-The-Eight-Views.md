# The eight graph views — spec versus code

*What the Atlas calls eight graphs is five tables queried differently.*

> **The spec says:** "This is **not one graph**. It is one logical graph made of eight
> interconnected views."
>
> **The code says:** it is one graph, in five tables, and six of the eight "views" are *queries*
> rather than structures. Two do not exist.
>
> The spec's framing is a good way to *think* about what the graph must answer. It is a bad map
> of the code, and this page is the correction.

---

## §1 · The mapping

| # | Spec view | Status | What it actually is |
|---|---|---|---|
| 1 | **Entity Graph** | ✅ real | `graph_nodes` — a table |
| 2 | **Relationship Graph** | ✅ real | `graph_edges` — a table |
| 3 | **Temporal Graph** | ✅ real, but not a table | `occurred_at` + `valid_from`/`valid_to` on every fact and edge |
| 4 | **Knowledge Graph** | ✅ real | `graph_facts` — the "facts not documents" store |
| 5 | **Communication Graph** | 🟡 partial | `graph_edges` of type `corresponded_with`, with `interaction_count` and `last_seen_at` |
| 6 | **Ownership Graph** | 🟡 weak | edges exist (`involves`, `works_at`); there is no `owns` edge type |
| 7 | **Authority Graph** | ❌ **not built** | no approval rights, no reporting lines, no "requires founder approval" |
| 8 | **Resource Graph** | ❌ **not built as a graph** | documents are evidence, not nodes — deliberately |

---

## §2 · The four that are real

### 1 · Entity Graph → `graph_nodes`

Every noun. Node types actually written today: `person`, `company`, `deal`, `meeting`,
`subscription`, `product_account`, plus canon types (`policy`, `project`, `pricing`, …).

Anchored by `canonical_key` — an email for a person, a domain for a company, `source:id` for a
structured object, `internal:kind:key` for canon. No key means no identity, and the P1 anchor
rule keeps such things out of the graph entirely.

### 2 · Relationship Graph → `graph_edges`

Typed, versioned, directional. Real edge types: `works_at`, `corresponded_with`, `involves`,
`attended`.

Note what is **not** here: `reports_to`, `owns`, `depends_on`, `approves`. The spec's richer
vocabulary was never populated because nothing produces it.

### 3 · Temporal Graph → two timestamp pairs, everywhere

Not a table. Every fact and edge carries:

| | Means |
|---|---|
| `occurred_at` | when it was true in the world |
| `valid_from` / `valid_to` | when we believed it |

That is what makes *"what did we know on 1 June?"* answerable, and it is why a backfilled 2024
email cannot overwrite today's state — see [Facts §5](02-Facts.md).

Sequence, deadlines, recency, decay and expiry are all computed from these two columns by
`attention.py`, `correlation.py`, `situations.py` and `health.py`. There is no separate temporal
structure to maintain, which is why it cannot drift out of sync with the facts.

### 4 · Knowledge Graph → `graph_facts`

The spec's best line, and the code honours it exactly:

> *"Facts, not documents. A fact survives its source document being deleted."*

`"314 Capital's cheque size is $250k"` is a row in `graph_facts` with an authority rank and a
pointer to the sentence that proved it. The PDF is evidence, not a node.

---

## §3 · The two that are partial

**5 · Communication Graph.** Migration `0028` added `interaction_count` and `last_seen_at` to
edges, turning a boolean adjacency list into a relationship graph — *how deep, how recent*. That
is the substrate `attention.py` scores on.

What is missing is the spec's *latency* modelling: *"founder → investor: email, ~4 day reply
latency."* Reply latency is not computed anywhere.

**6 · Ownership Graph.** `hubspot.deal.v1` produces `involves` edges from deal to contact, and
`_works_at` produces affiliation. Neither says *"Priya owns the Acme renewal."*

Ownership is arguably not a Layer 2 fact at all — it is a CRM field. When one is mapped, it
becomes a fact (`deal.owner`), not a new graph view.

---

## §4 · The two that are not built

### 7 · Authority Graph — *not built*

The spec's example: *"Discount > 20% → requires founder approval."*

Nothing in Layer 2 stores approval rights, reporting lines or thresholds. Grep confirms it: no
`approval_right` table, no `reports_to` edge type.

**Where it actually belongs.** The example is a *policy* — a rule about what requires approval.
That is domain knowledge (Layer 3) or a constraint evaluated at decision time (Layer 4's
`core.policy` and `core.constraint` units). Storing it as graph structure would put a decision
rule inside the layer that is forbidden from deciding.

The one piece Layer 2 *does* hold: `org_seats`, used to tell internal people from
counterparties. That is not an authority graph; it is a membership list.

### 8 · Resource Graph — *deliberately not built*

The spec lists `Files · Meetings · Documents · Links · Assets` as a view. Meetings **are** nodes
(via the calendar mapping). Documents are **not**, and that is a decision, not an omission.

The spec contradicts itself here — it also says *"Documents disappear. Facts remain."* Both
cannot be true. The code picked the second, and [Evidence](05-Evidence.md) is the mechanism: a
document's content becomes facts and observations, and the document itself becomes a
`graph_source_refs` row.

Making documents nodes would mean every uploaded PDF becomes an entity that shows up in
projections, counts toward orphan-node health, and needs its own lifecycle — for no gain, since
nothing reasons about a PDF.

---

## §5 · Why one graph and not eight

| | Eight graphs | One graph, many queries |
|---|---|---|
| Same customer | exists eight times | exists once |
| Disagreement between views | no way to say which is right | impossible — one row |
| Adding a view | new store, new sync, new staleness window | a query |
| Merge | eight repoints, eight chances to miss one | one `_NODE_REFERENCES` list |
| Cost | eight writes per event | one |

The eighth column is the argument. `merge.py` already has to enumerate every table that names a
node, and the `broken_edge` / `alias_to_closed_node` health checks exist because **missing one
is invisible**. Eight physical graphs would multiply that surface by eight.

This is the same instinct as [Projections](../05-Business-Situation-Engine/03-Projections.md),
one layer up: *one graph, many derived lenses — never separate graphs, because separate graphs
mean the same customer exists twice and no way to say which is right when they disagree.*

---

## §6 · How to check this page

```bash
# real
psql -c "\dt graph_*"          # nodes, facts, edges, observations, source_refs, aliases, health

# not built — these should return nothing
grep -rn "approval_right\|reports_to\|node_type='document'" --include='*.py' genios_engine/context/
```

---

*Related: [Nodes and Identity](01-Nodes-and-Identity.md) · [Facts](02-Facts.md) · [Edges](03-Edges.md) · [Evidence](05-Evidence.md)*
