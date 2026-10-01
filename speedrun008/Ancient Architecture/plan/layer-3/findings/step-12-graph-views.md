# L3-12 · The graph views — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ Eleventh premise wrong, and the original grep was the reason

The plan said *"`temporal`, `communication`, `resource`, `knowledge` return **zero** files."*

**The pattern behind that number was `"$v.*view\|view.*$v"`** — it looked for the word *"view"*
near the word. **It was measuring prose, not capability.**

Every one of the eight concerns is queryable: temporal through `occurred_at` / `valid_from` /
`correlation_timeline`, communication through `corresponded_with` and thread nodes, resource
through `deal` / `subscription` / `product_account` / `correlation_resource`, knowledge through
`document` nodes and `document_register`.

**And there is a projection layer:** `context/read_models.py` builds `person_360`, `company_360`,
`deal_360`, `meeting_360` and `entity_360` into `context_read_models`. ⛔ **Per-entity views, not
per-concern views** — a different design that carries all eight concerns for one entity, which is
what a card actually needs.

---

## 2. What was actually wrong — the third free-string vocabulary

```sql
node_type text not null    -- person | company | deal | meeting | ...
```

⛔ **The `| ...` is the tell**: an open-ended list in prose, with nothing enforcing it. Same shape
as `edge_type` before L3-09 and `residue_kind` before L3-10.

`NODE_TYPES` now closes it — **twelve types, each stating what ANCHORS it**, because the anchor is
what decides whether two sightings are one node, and getting it wrong is how a company is
fragmented across three nodes or two people are merged into one.

### 2.1 · ⛔ And there were TWO sets of node-type names

`pipeline._NODE_TYPES` is a **mention whitelist** — *"this whitelist governs ONLY the L2 mention
loop below; the structured lane is NOT gated here"* — a narrower rule about which LLM entity
mentions may become nodes at all. **Correctly scoped, correctly documented, and one rename away
from being read as the graph's vocabulary.** A test now holds the graph set as the superset, and
pins the whitelist's scope comment, because that comment is the only thing preventing the
confusion.

---

## 3. ⛔ My totality guard was not total, and the whitelist caught it

The first scan read `node_type="..."` and found **ten**. It called that the complete set.

**`document` and `product_usage_event` are minted through named constants** —
`DOCUMENT_NODE_TYPE`, `PRODUCT_USAGE_NODE_TYPE` — so a literal-only scan **saw ten of twelve and
called it total.**

⛔ **What exposed it was the mention whitelist**, which lists `document`: the cross-check between
two vocabularies failed, and that failure was the only reason the miss was visible.

**A totality guard that recognises only one spelling of the thing it counts is not total.** It now
reads both shapes — the keyword literal, and any module-level `*_NODE_TYPE = "..."` constant.

---

## 4. And the read-model map came out of a function body

`{"person": "person_360", …}` was an inline dict inside `build_entity_360`, so *"which entities
have a tailored view"* was a question you could only answer by reading a function body.

⛔ **The default is a real answer, not a fallback for an error** — `entity_360` carries the node's
facts, observations and edges. What was missing is that **adding a node type asked nobody** whether
it needed a view; it silently became generic.

---

## 5. Result

```
FULL SUITE   13,265 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-12: 13,254 passed · 14 failed
```

**+11 tests · 0 regressions · no migration · no model call.**

**Technique 3 — five mutations, all red:** drop a constant-minted type; a type stops saying what
anchors it; the map goes back inside the function; the whitelist stops declaring its scope; a node
type collides with an edge type.

## 6. What this step does NOT do

* ⛔ **It does not build eight concern-views.** The data is queryable and the projection layer is
  per-entity, which is what a card reads. **Eleventh "already built" in this layer.**
* **It does not add a check constraint.** Same reasoning as L3-09: a schema change to add a type,
  and a failure on unaudited historic rows.
