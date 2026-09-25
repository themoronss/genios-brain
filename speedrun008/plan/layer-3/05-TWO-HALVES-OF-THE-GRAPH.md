# The Context Graph's two halves — Evidence vs Intelligence

**2026-09-25** · measured from the schema and the code, not from prose
**Follows:** [`04-CORRECTION-GRAPH-MAKES-THE-SITUATION.md`](04-CORRECTION-GRAPH-MAKES-THE-SITUATION.md)

The Context Graph (L3) is **one graph with two halves**:

| half | the question it answers | state |
|---|---|---|
| **Evidence Graph** | *"दुनिया में क्या है? Sources ने क्या कहा?"* | ✅ **built** — 10 tables, 14 writers |
| **Intelligence Graph** | *"हमने क्या समझा? क्या भेजा? क्या हुआ?"* | ⚠️ **scattered** — 4 tables, zero edges between them |

⛔ **The Intelligence half is not zero.** That was the previous file's overstatement. The
information exists. What does not exist is **the graph shape over it** — no nodes, no edges, no
version counter, no health.

---

# PART 1 · The Evidence Graph, in full

## 1.1 · Its ten tables

| table | holds | migration |
|---|---|---|
| `graph_nodes` | the entities — **versioned**, `primary key (node_id, version)` | 0004 |
| `graph_facts` | what is true of an entity — **versioned**, `fact_id` stable across versions | 0004 |
| `graph_edges` | how entities relate — **versioned** | 0004 |
| `graph_observations` | events that happened to an entity, without asserting a value | 0004 |
| `graph_source_refs` | ⛔ **the receipt** — every fact/edge/observation → its `event_id` + span | 0004 |
| `graph_versions` | one monotonic `bigint` per org — the whole graph's clock | 0004 |
| `graph_change_outbox` | what changed, for anyone downstream who must react | 0004 |
| `graph_aliases` | `email`/`domain`/`name` → node. **One owner per key per org** | 0036 |
| `graph_health` | quality score. **MINIMUM of dimensions, never average** | 0039 |
| `graph_segments` | named clusters — Investor · Customer · Team · Vendor · Admin | 0048 |

## 1.2 · Its vocabulary, measured

**12 node types**
```
person · company · deal · meeting · task · thread · commitment
tenant · document · product_usage_event · product_account · subscription
```

**6 edge types**
```
works_at · attended · owns · concerns · raised_in · corresponded_with
```

**16 fact fields**
```
deal.stage · deal.status · commitment.due_at · commitment.last_due_at
thread.ball_in_court · thread.last_inbound · thread.last_outbound · thread.objective
party.role · party.role_basis · party.role_context_ref
relationship.direction · relationship.nature · attendees
derived.contract_spend.summary
```

## 1.3 · The five properties that make it trustworthy

**1 · Every claim has a receipt.**
`graph_source_refs` binds each `fact_version_id` / `edge_version_id` / `observation_id` to an
`event_id`, a `source_field_path`, and `evidence jsonb` — `{span:[s,e], text, page, bbox}`. **No
fact exists without the sentence it came from.**

**2 · It is bitemporal.**
`occurred_at` (when it happened in the world) is separate from `valid_from`/`valid_to` (when we
believed it). Nothing is deleted; it is closed. **So "what did we know last Tuesday" is answerable.**

**3 · Sources are ranked, and disagreement is a row.**
`authority_rank` R1–R4. When a rank-2 source challenges a held rank-1 value,
`graph_store.write_discrepancy` writes to the `discrepancies` table with `held` and `challenger`
side by side. **Conflict is recorded, not resolved by overwrite.**

**4 · Confidence travels with the value.**
`confidence numeric(4,3)` on every fact and edge. Not a property of the graph — a property of the
claim.

**5 · Identity collision is a signal, not an error.**
`graph_aliases` is `primary key (org_id, alias_type, alias_key)` — one owner per key. The comment is
explicit: *"The conflict IS the signal: an insert that would break this is a collision, and a
collision becomes a merge proposal."*

## 1.4 · Who writes it, and who reads it

**Writers — all L1 or L2:**
```
capture/pipeline · capture/screen/fingerprint · platform/screen_promoter
context/graph_store · context/derived · context/identity · context/availability
context/periodic · context/health · context/document_register
context/analytic/trend · context/derived_provenance · context/support_situations
api/segments_routes
```

**Readers — the 9 correlators**, which turn it into correlations, which the 7 producers turn into
situations, which become the **`BusinessSituationObject`**.

⛔ **`reason/`, `executive/`, `deliver/` and `feedback/` write NOTHING.** Every one of them reads.

---

# PART 2 · The Intelligence Graph

## 2.1 · What already exists — four tables, no edges

| table | what it already holds | what it is missing |
|---|---|---|
| `context_situations` | the situation, `anchor_node_id` → **into the Evidence Graph**, a 5-part confidence vector, lifecycle `active/dormant/resolved/archived` | it is a **row**, not a node. Nothing points *at* it |
| `situation_interpretations` **(0183)** | ⛔ **the best one.** One reading per (situation, slice), **with `context_slice jsonb` itself**, `outcome`, `reason_codes`, `valid_until` | no `decision` it led to; no link to the next reading |
| `execution_outcomes` | ⛔ **the richest.** `decision_hash`, `terminal_state`, 7 labels (`succeeded` … `cancelled_by_world`), `seconds_to_close`, `progress_bp` | nothing joins it back to the **situation** |
| `reasoning_evidence_id_map` **(0117)** | ⛔ **the bridge** — decision evidence ids → `context_snapshot_id`, with a `lane` that says `historic` when provenance cannot be proven | it maps ids; it is not an edge |

**So: 4 rich tables, and not one edge between them.**

## 2.2 · What it would need, mapped onto the Evidence Graph's own design

| Evidence Graph has | Intelligence Graph needs |
|---|---|
| 12 node types | **5** — `situation` · `decision` · `execution` · `delivery` · `outcome` |
| 6 edge types | **6** — `about` · `supersedes` · `caused` · `delivered_as` · `resulted_in` · `learned_from` |
| `graph_source_refs` (event + span) | ⛔ **already exists** — 0183's `context_slice` IS the receipt |
| `authority_rank` R1–R4 | **which admission law passed** ＋ the confidence vector |
| `discrepancies` (two sources, one field) | **supersession** — not two sources disagreeing, but *us changing our mind* |
| `occurred_at` + `valid_from`/`valid_to` | `decided_at` + `valid_until` — ⛔ **0183 already has `valid_until`** |
| `graph_versions` monotonic counter | the same, so a decision can name the graph state it was made against |
| `graph_health`, MINIMUM not average | the same discipline |

---

# PART 3 · Side by side

| | **EVIDENCE GRAPH** | **INTELLIGENCE GRAPH** |
|---|---|---|
| **question** | *what did the sources say?* | *what did we conclude, and what happened?* |
| **subject** | **the world** | **us** |
| **state** | ✅ 10 tables · 14 writers · live every sweep | ⚠️ 4 tables · **0 edges** · no graph shape |
| **nodes** | 12 types — person, company, deal, meeting, thread, commitment… | ⛔ **0** — situation and decision are rows beside the graph, not nodes inside it |
| **edges** | 6 — `works_at`, `attended`, `owns`, `concerns`, `raised_in`, `corresponded_with` | ⛔ **0** |
| **what a "fact" is** | a field on an entity — `deal.stage = 'negotiation'` | a conclusion — *"this situation needs a reply today"* |
| **where it comes from** | an **event + a character span** | a **context slice + an admission law** |
| **receipt** | `graph_source_refs` → `event_id` + `{span, text, page, bbox}` | ⛔ `context_slice` in 0183 — **built, unlinked** |
| **authority** | source rank **R1–R4** | which of the 8 L2 laws admitted it |
| **confidence** | `numeric(4,3)` per fact | 5-part vector, `overall` = **MIN** not average |
| **disagreement** | `discrepancies` — *two sources, one field* | **supersession** — *we changed our mind* |
| **time** | bitemporal: `occurred_at` ＋ `valid_from`/`valid_to` | `decided_at` ＋ `valid_until` |
| **version** | `graph_versions` — one `bigint` per org | ⛔ none |
| **health** | `graph_health` — MIN of dimensions, empty graph scores **100 not 0** | ⛔ none |
| **written by** | `capture/` (L1) ＋ `context/` (L2) | ⛔ **nobody** — `reason/`, `executive/`, `deliver/`, `feedback/` all read-only |
| **read by** | 9 correlators → 7 producers → **BusinessSituationObject** | ⛔ **nothing** |
| **if it were missing** | **no Business Situation could exist at all** | the **fourth identical card** gets sent |
| **failure it prevents** | inventing a fact nobody said | repeating a decision that already failed |

---

# PART 4 · The three sentences that matter

**1 · They are not two systems. They are two halves of one graph, and they must point at each
other.**
`context_situations.anchor_node_id` **already points into the Evidence Graph.**
`reasoning_evidence_id_map` **already maps a decision's evidence to a context snapshot.**
The bridge exists in both directions and carries nothing across yet.

**2 · The Evidence Graph must never hold a conclusion, and the Intelligence Graph must never hold a
fact.**
This is `Observation ≠ Inference ≠ Hypothesis` at the storage layer. The moment *"this deal is at
risk"* is written as a `graph_fact`, a replay can no longer tell what a source said from what a
model guessed — and the whole receipt discipline is spent.

**3 · The Evidence Graph is why GeniOS can be trusted. The Intelligence Graph is why it can
improve.**
Without the first, every claim is a guess. Without the second, every sweep is the first sweep —
which is exactly what `prior_decision = 0` means, and why the same card can be sent four times.

---

# PART 5 · The order to build it

| | | why this order |
|---|---|---|
| **1** | `situation` becomes a **node** | it already has `anchor_node_id` into the Evidence Graph; it needs an id things can point *at* |
| **2** | `decision` becomes a **node**, and `decision ─about→ situation` an **edge** | the `signals.situation_id` defect (L2-7), one seam up |
| **3** | `deliver/` and `feedback/` **write back** | `sent`, `opened`, `acted`, `ignored` — `execution_outcomes` already has 7 terminal labels waiting |
| **4** | `decision ─supersedes→ decision` | what a mute must reach; what "we already tried this" means |
| **5** | the **correlators may read it** | and then the fourth identical card cannot be produced, because the correlator can see the first three |

**Step 5 is the whole point. Steps 1–4 are plumbing for it.**
