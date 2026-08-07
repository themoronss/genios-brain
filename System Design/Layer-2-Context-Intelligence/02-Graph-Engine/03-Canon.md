# Canon — company knowledge as a participant, not a passenger

*`context/canon.py` · `capture/internal_knowledge.py`*

> Layer 1 gives company knowledge the **highest authority in the system** — rank 4, above any
> connected tool. Layer 2 then did almost nothing with it.

---

## §1 · The bug this closed

Trace one refund policy through `process_event` as it stood:

```
you write a refund policy
   → the author is an internal seat (an org_seats email)
   → sender_node becomes the AUTHOR's person node
   → every extracted fact attaches to the author
   → internal nodes are excluded from correlation anchors
   → the policy reaches NO situation
```

**Your refund policy became facts about you.** The most authoritative material in the system was
also the least connected — filed under whoever happened to type it.

---

## §2 · What exists now

A canon document becomes a **node of its own**.

| | |
|---|---|
| `node_type` | the internal kind — `policy`, `project`, `pricing`, … |
| `canonical_key` | `internal:<kind>:<key>` |
| `display_name` | the document's title |
| Facts | attach **to it**, not to the author |

The key is shaped like the structured lane's `<source>:<object id>` on purpose — canon **is** a
system of record, and the company is the system.

```python
def canon_key(kind, knowledge_key):
    return f"internal:{kind}:{knowledge_key}"
```

### One node per document, not per chunk

A 30-chunk pricing PDF keyed on the *event* would create **thirty separate "Pricing" entities**,
each holding a slice of one document — the graph would look like thirty price lists.

`upload_routes._emit_chunk` therefore passes `knowledge_key = file_id` for every chunk of a
tagged file. The written-knowledge door passes a slug of the title.

---

## §3 · Anchoring versus reference

The decision that shapes everything downstream.

```python
ANCHORING_KINDS = frozenset({"project"})     # capture/internal_knowledge.py
```

| Class | Kinds | Can other signals group under it? |
|---|---|---|
| **Anchoring** | `project` | **Yes** — a Slack thread, a commit and a meeting about Project Phoenix are one situation |
| **Reference** | policy · sop · product · pricing · goal · kpi · org_structure · employee_profile · task · asset · wiki | **No** — standing knowledge, not something happening |

**The line is not importance.** Pricing may matter more than any single project. It is whether
other events **cluster** around it. Emails cluster around a project; nothing clusters around a
refund policy.

Letting every policy and price list open its own situation would bury the handful that need
attention under a filing cabinet — the opposite of what situations are for.

### Why `task` is not anchoring yet

One situation per to-do item would swamp the same list, and nothing downstream ranks at that
granularity. It moves into `ANCHORING_KINDS` the day something consumes it — a one-line change,
because `ANCHOR_PRIORITY` is derived from that constant rather than restated:

```python
def _anchor_priority():
    return ("deal", *sorted(ANCHORING_KINDS), "company", "person")
# → ('deal', 'project', 'company', 'person')
```

A project sits **above** a company: "the Phoenix migration" should not be filed under "Acme"
alongside the renewal.

---

## §4 · How a mention finds it — and why by name

A Slack message says *"Project Phoenix is blocked."* How does that reach the project node?

**Not by entity type — that cannot work.** Verified:

| | |
|---|---|
| `context/extract/prompt.py` | never asks for a `project` entity type |
| `pipeline.py:_NODE_TYPES` | has no `project` entry |

A type-based lookup would have **silently never fired.** The feature would look built, pass its
tests, and do nothing.

So resolution is by **name**, through the exact-match alias table Step 1 built:

```python
resolve_canon_mention(conn, org_id=..., name="Project Phoenix")
    → canon_title_key("Project Phoenix") = "project phoenix"
    → look up alias_type = ALIAS_CANON
    → return (node_id, node_type)
```

### The type comes back with the id

A second bug that would have made this inert. Correlation anchors on node **type**. A resolver
returning only an id forces the caller to invent one — and an invented type matches nothing in
`ANCHOR_PRIORITY`, so the mention would resolve *perfectly* and then correlate under **nothing**.

### Canon has its own alias namespace

`ALIAS_CANON = "canon"`, separate from `ALIAS_COMPANY_NAME`.

A project called "Acme" and the customer called "Acme" can therefore **never contend for one
key** — no false merge proposal is ever raised between a project and a company.

**Company is checked first.** When a name could mean either, the customer wins: its alias is
derived from a real email domain, which is harder evidence than a title somebody typed. (An
earlier draft checked canon first, contradicting its own comment.)

---

## §5 · The hot path, and its blast radius

`process_event` runs for **every** event. Canon handling must be inert when `internal_kind` is
absent, or this feature's blast radius is the entire product.

```python
canon_node = None
if internal_kind:
    canon_node = register_canon_node(...)
    touched[canon_node] = internal_kind

...
content_subject = canon_node or sender_node
```

| Rerouted to the canon node | Deliberately NOT rerouted |
|---|---|
| extracted facts | `works_at` edges |
| observations | `corresponded_with` edges |
| questions and commitments | |

Who corresponded with whom is a fact about **people**. Rerouting it would make a policy document
appear to have colleagues.

---

## §6 · What canon refuses to do

| Refused | Why | Whose job |
|---|---|---|
| **Policy comparison** — *"1000 leads uploaded, only 130 match ICP"* | requires knowing what an ICP is | Layer 3 |
| **Goal progress** — *"we are 60% to target"* | a judgement about how things are going | Layer 4 |
| **Anchoring on our own company** | would recreate the Step 2 bug where every outbound email filed into one enormous situation | — |

Building either of the first two here would repeat the risk-detector mistake: two layers with an
opinion about the same thing, and no way to tell which one was wrong.

---

## §7 · Worked example

You upload `Q3-Pricing.pdf` tagged `pricing`, 8 chunks.

| Stage | Result |
|---|---|
| L1 | 8 events, `internal_kind='pricing'`, each carrying `knowledge_key = upl_9f2` |
| L2, chunk 1 | node `internal:pricing:upl_9f2`, display name `Q3-Pricing.pdf`, alias `q3 pricing pdf` |
| L2, chunks 2–8 | **the same node** — find-or-create by canonical key |
| Facts | `"Enterprise tier is $2,400/yr"` on the pricing node at **R4** |
| Correlation | `pricing` is **reference**, so no situation is anchored on it |
| Later | an email says *"as per Q3-Pricing"* → resolves to the node → the mention attaches there |

Now compare a project brief tagged `project`, titled *Project Phoenix*: same path, except
`project` **is** anchoring — so a Slack message naming Phoenix joins a Phoenix situation, and
the brief is evidence in it.

---

*Related: [Entity Resolution](01-Entity-Resolution.md) · [Anchoring](../03-Cross-Correlation-Engine/01-Anchoring.md) · [Facts](../01-Enterprise-Context-Graph/02-Facts.md)*
