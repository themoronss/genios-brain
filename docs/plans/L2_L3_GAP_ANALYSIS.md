> **Created:** 2026-08-27 · **Status:** Active
> **Purpose:** Why a complete Sales corpus still changes nothing on the live org. Every claim below was measured against `org_e97e86f858ad48b2bbf64b8a`, read-only. Nothing was deleted.

# The one-sentence finding

The Sales corpus is complete (47 of 47 capabilities) and roughly **20 of them can never be reached**,
because Layer 2 does not create the node type their situations anchor on.

This is a Layer 2 gap, not a corpus gap, and no amount of further authoring closes it.

# What was measured

| | |
|---|---|
| Situations on the org | 61 |
| Routing | 56 / 61 (91%) |
| Capabilities actually reached | **9** |
| Sales capabilities authored | 47 |
| `review_state` on live packages | `accepted` — no admission gaps, no hollow |

The 9 reached: `account_research`, `lead_generation`, `expansion`, `icp_definition`,
`lead_qualification`, `customer_success`, `investor_relations`, plus three Admin
(`commitment_tracking`, `inbox_and_correspondence`, `follow_up_coordination`).

**All nine were already promoted before this session's batches 2–13.** That is the honest reason
routing and `card_audit` never moved across nine batches of authoring.

# Layer 2 — four gaps, in order of cost

## L2-1 · There is no `deal` node. This is the big one.

`context/pipeline.py` creates exactly four node types:

```
commitment · company · person · thread
```

`deal` is never among them. But `domain_spec.py:174` types a sales situation from its anchor:

```python
situation_types={"deal": "deal", "company": "opportunity", "person": "prospect_relationship"}
```

No deal node → no `deal` situation → the entire deal lane is unreachable.

The facts exist. `deal.status` is present on 45 rows across 38 nodes — written onto **person** (41),
**service** (3) and **company** (1) nodes. The data is being captured and has nowhere to live.

**What this costs:** roughly 20 authored capabilities that can never compile on a
correspondence-only tenant — `closing`, `negotiation`, `pricing`, `proposal_creation`,
`objection_handling`, `contract_management`, `legal_review`, `procurement`, `forecasting`,
`deal_review`, `pipeline_management`, `revenue_intelligence`, the whole qualification cluster,
`discovery`, `need_analysis`, `value_proposition`, `demo`.

**Everything downstream of the node is ALREADY BUILT and waiting.** This was checked link by link:

| Link | State |
|---|---|
| `correlation.py:91` `ANCHOR_PRIORITY` | `("deal", ...)` — **`deal` is FIRST**, above company and person |
| `situations.py:382` | `situation_type(corr.anchor_type, corr.domain)` |
| `domain_spec.py:174` | `situation_types={"deal": "deal", ...}` |
| Corpus | 4 situations bound to the `deal` type |
| Corpus | ~20 capabilities behind those situations |

The correlation layer already prioritises a deal above every other anchor. The situation typer already
maps it. The corpus already binds it. **The only missing link in the entire chain is that
`pipeline.py` never creates the node.**

That makes this a single-point fix rather than a subsystem change, which is worth knowing before
anyone plans it as a large piece of work.

**The fix has a working precedent in the same file.** `pipeline.py:930` already mints a `commitment`
node when it finds a dated promise:

```python
cnode = store.find_or_create_node(conn, org_id=org_id, node_type="commitment",
                                  canonical_key=ck, display_name=..., event_id=event_id)
```

A `deal` node wants the same shape: when `deal.status` / `deal.last_inbound` are extracted for a
counterparty, mint a deal node keyed on the account, attach the deal facts to it, and edge it to the
person and company. Situations then type as `deal` and ~20 capabilities become reachable **without a
line of new corpus**.

## L2-2 · Eleven observation kinds are emitted by nothing

`context/vocabulary.py::CANONICAL_OBS_KINDS` declares 34 kinds and the extractor is offered all of
them. On the live org, 23 appear. Absent entirely:

```
budget_approved · budget_freeze · champion_change · contract_requested · discount_pressure
legal_review · objection_price · verbal_yes · stakeholder_added · stakeholder_left · churn_risk
```

These are not exotic — they are the trigger set for closing, negotiation, churn prevention and
relationship management. Several authored rules name them and say in their own `limits` that they
have no live trigger.

**Worth determining before authoring more:** is this an extraction-quality problem (the model is not
recognising them), a data problem (this founder's inbox genuinely contains none), or a prompt problem?
The distinction decides whether it is fixable at all.

## L2-3 · `commitment.status` and `commitment.text` are on 3 of 31 commitment nodes

`pipeline.py:941` writes all three fields together:

```python
for fld, val, vt in (("commitment.due_at", ...), ("commitment.text", ...), ("commitment.status", "open", "enum")):
```

Yet `commitment.due_at` has 31 rows and the other two have 3. The 28 older commitments were created
by a path that wrote only the date. Anything reasoning about commitment STATE sees almost nothing.

## L2-4 · No stage history

`deal.status` holds a current value, not a sequence. Stage-to-stage conversion and time-in-stage —
the core instruments of `sales_analytics` and `pipeline_management` — are therefore not computable,
and both capabilities say so in their `limits`.

# Layer 3 — three gaps, none of them authoring

## L3-1 · Admin and Customer Support cannot deliver at all

`ReasoningStore.persist_complete` (store.py:928) refuses a write unless `config_pack ==
capability_pack`. The tenant holds `general 1.4.0` and `sales 1.13.0`. The only pack modules that
exist in code are `general_v1.py` and `sales_v1.py`.

So every Admin and Customer Support capability — **91 of them, including the 6 already authored and
on a live route** — dies at `domain_shadow.py:387` under `no_tenant_pack` and emits nothing.

**Fix:** an `admin_v1.py` pack module (`general_v1.py` is 230 lines and is the right template),
then `scripts/promote_packs.py` to put the tenant on it.

## L3-2 · Three Customer Support core objects unauthored

`customer_support.obj.core.{customer_account, named_contact, support_plan}` are referenced and do not
exist, which is `required_missing=2` on the probe. Authoring them takes routing **56/61 → 58/61** —
the only corpus-fixable routing gain left.

## L3-3 · 91 hollow capabilities

Admin 51, Customer Support 40. Sales is 0. Blocked behind L3-1 regardless.

# Recommended order

1. **L2-1 — mint the deal node.** Largest return by a wide margin: ~20 already-authored capabilities
   become reachable, no new corpus. Everything downstream is already built — correlation, situation
   typing, domain spec and corpus all handle `deal` today and are waiting on a node that is never
   created. Working precedent for creating it is in the same file (`pipeline.py:930`).

   Concretely, three edits: (a) mint a `deal` node when `deal.*` facts are extracted, keyed on the
   account; (b) route `deal.*` facts to it in the generic fact loop at `pipeline.py:710` instead of
   letting them land on the person; (c) edge it to the company and the person so the neighbourhood
   reaches it. Then re-run the sync and the `deal` situations appear on their own.
2. **L2-2 — diagnose the missing observation kinds.** Determines whether the closing and churn rules
   can ever fire, and it is a diagnosis before it is a fix.
3. **L3-1 — `admin_v1` pack.** Unblocks 51 Admin capabilities, 3 of which are on a live route today.
4. **L3-2 — the three CS objects.** Routing 56 → 58.
5. **L2-3, L2-4** — backfill and stage history, both smaller.
6. Remaining Admin/CS authoring, last, because it is worthless before item 3.

# Two things NOT done, deliberately

* **No data was deleted.** The analysis is entirely read-only. A wipe of the design partner's live org
  during a trial is irreversible and was not part of what the analysis needed.
* **No Layer 2 code was changed.** This document is the diagnosis; the fixes are separate work with
  their own tests.
