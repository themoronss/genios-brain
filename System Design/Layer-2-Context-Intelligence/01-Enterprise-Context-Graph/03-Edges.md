# Edges — relationships, and how deep they run

*`graph_edges` · migration `0004` + `0028` · `graph_store.py:write_edge`*

> An edge says two entities are connected. Migration `0028` added two columns that turned a
> boolean adjacency list into something you can reason about: **how deep, and how recent.**

---

## §1 · What exists

```sql
create table graph_edges (
    edge_version_id text primary key,   -- this version
    edge_id         text not null,      -- stable across versions
    org_id          text not null,
    edge_type       text not null,
    from_node_id    text not null,
    to_node_id      text not null,
    authority_rank  int  not null default 1,
    confidence      numeric(4,3) not null default 0.5,
    valid_from      timestamptz not null default now(),
    valid_to        timestamptz,        -- null = current
    created_by_event_id text
);
-- added by 0028:
alter table graph_edges add column interaction_count int not null default 1;
alter table graph_edges add column last_seen_at timestamptz;

create index graph_edges_current on graph_edges (org_id, from_node_id, edge_type)
    where valid_to is null;
```

Versioned exactly like facts: an edge is closed (`valid_to = now()`), never deleted.

### The edge types that actually exist

| Type | From → To | Written by | Authority |
|---|---|---|---|
| `works_at` | person → company | `pipeline.py:_works_at`, from the email domain | R2 |
| `corresponded_with` | person ↔ person | `pipeline.py`, from To/Cc | R2 |
| `involves` | deal → person | `structured.py`, from `hubspot.deal.v1` relations | R3 |
| `attended` | person → meeting | `structured.py`, from `gcal.event.v1` attendees | R3 |

**Four types.** The spec's richer vocabulary — `reports_to`, `owns`, `depends_on`, `approves` —
does not exist, because nothing produces it. See
[The Eight Views §4](06-The-Eight-Views.md).

---

## §2 · Direction is canonicalised, or A→B and B→A become two edges

For a symmetric relationship, direction is meaningless but the row is not. `corresponded_with`
canonicalises on the lexically smaller email:

```python
frm, to = ((sender_node, rnode) if sender_norm < rn_email else (rnode, sender_node))
```

Without this, Monday's email creates `A→B` and Tuesday's reply creates `B→A`, and the graph
claims two relationships where there is one. Every later "how well do we know them" query is
then wrong by a factor of two.

Asymmetric types (`works_at`, `involves`, `attended`) carry real direction and are not
canonicalised.

---

## §3 · `interaction_count` and `last_seen_at`

The two columns that make the communication graph real.

| Column | Answers |
|---|---|
| `interaction_count` | **how deep** — a relationship with 40 exchanges is not the one with 1 |
| `last_seen_at` | **how recent** — a deep relationship that stopped six months ago is a different fact |

These are the substrate `attention.py` scores on, and the reason a merge must **sum** rather than
discard: `merge.py:_dedupe_edges` folds duplicate edges by keeping the most recently seen and
adding the counts, because merging two records of one person must not quietly halve how well we
appear to know them.

---

## §4 · Two caps that stop one email exploding the graph

```python
_MAX_RECIPIENTS  = 25   # cap fan-out from a mass To/Cc
_BULK_RECIPIENTS = 10   # above this, skip per-recipient nodes and edges entirely
```

| Recipients | Behaviour |
|---|---|
| ≤ 10 | every recipient becomes a node, with edges |
| 11 – 25 | **no per-recipient nodes or edges at all** |
| > 25 | same, and the list is truncated for any other use |

**A 40-person To line is a broadcast, not forty relationships.** Treating it as forty would add
780 spurious `corresponded_with` edges from one email and make the densest node in the graph an
all-hands announcement.

The email itself still lands in the L1 ledger and its facts are still extracted — this gate is
about the **network**, never about deleting data.

Both constants are marked `HYP` in the code: hypotheses to tune in shadow mode, not settled
truth.

---

## §5 · Noise never gets edges

```python
if not is_noise:
    _works_at(sender_email, sender_node)
    # … recipient edges
```

A newsletter, an automated notification or spam produces **no nodes and no edges**. You do not
"correspond with" a marketing list.

But its facts and observations are still committed. The rule is precise: *noise is excluded from
the relationship graph, not from the record.*

---

## §6 · Worked example

An inbound email from `john@acme.io` to `priya@ourco.com` and `sam@ourco.com`:

| Edge | Direction | Notes |
|---|---|---|
| `works_at` | `john` → `acme.io` | company node created from the domain |
| `works_at` | `priya` → `ourco.com` | our own company — created, but marked internal |
| `corresponded_with` | canonicalised `john` ↔ `priya` | `john@acme.io < priya@ourco.com` |
| `corresponded_with` | canonicalised `john` ↔ `sam` | |

Three days later John replies. No new edges are created — the existing `corresponded_with` rows
have their `interaction_count` incremented and `last_seen_at` moved.

Had this been a 15-recipient announcement, only the two `works_at` edges would exist.

---

## §7 · Edge cases

| Case | Behaviour |
|---|---|
| Sender is also a recipient | skipped — `rn_email == sender_norm` |
| Personal domain (gmail, outlook…) | no company node, so no `works_at` — a "gmail.com company" is never created |
| Same edge seen again | count incremented, not a new row |
| One endpoint closed by a merge | repointed; if both ends land on the survivor, the self-edge is **closed** |
| Both nodes had the same edge before a merge | deduped, counts summed |
| Edge whose endpoint no longer exists | the `broken_edge` integrity check — usually a merge that missed a table |

---

## §8 · Who reads them

| Reader | Uses |
|---|---|
| `attention.py` | relationship recency, via `last_seen_at` |
| `reason/signals_derived.py` | `single_threaded_deal` — a deal with one `involves` edge |
| `reason/composer.py` | neighbour traversal for card evidence |
| `projections.py:boundary_edges` | relationships that **leave** a lens, reported rather than dropped |

Four files under `reason/` read this table.

> **Why the deal→contact bridge mattered.** Before `hubspot.deal.v1` gained its `relations`,
> a CRM deal was an **island** — zero edges to any person. Every neighbour rule
> (`cooling_deal`, `competitor_in_live_deal`, `deal_sentiment_negative`) was structurally unable
> to fire, and `single_threaded_deal` fired on *every* deal because the edge count was always 0.

---

*Related: [Nodes and Identity](01-Nodes-and-Identity.md) · [The Eight Views](06-The-Eight-Views.md) · [Attention](../04-Context-Quality-Engine/05-Attention.md) · [Merge and Reverse](../02-Graph-Engine/02-Merge-and-Reverse.md)*
