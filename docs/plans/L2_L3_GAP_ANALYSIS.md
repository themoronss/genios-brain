> **Created:** 2026-08-27 · **Status:** 🔵 Reference — **its headline is now false.** The `deal` node exists, Admin/CS have a pack lane, and Sales routing is 43/47 rather than the ~27 this file predicts. Four of its seven findings are closed; three remain and are named below. Re-verified 2026-08-30.
> **Purpose:** Why a complete Sales corpus still changes nothing on the live org. Every claim below was measured against `org_e97e86f858ad48b2bbf64b8a`, read-only. Nothing was deleted.

# The one-sentence finding

The Sales corpus is complete (47 of 47 capabilities) and roughly **20 of them can never be reached**,
because Layer 2 does not create the node type their situations anchor on.

This is a Layer 2 gap, not a corpus gap, and no amount of further authoring closes it.

---

# UPDATE 2026-08-27 — L2-1 fixed, and it was four faults in a row, not one

The deal node was the first of four, each of which alone was enough to keep the lane empty. All
four are fixed, each proven on a throwaway Postgres first and then on the live org, with the graph
backed up to `*_bak_20260827_deal` tables before anything was written.

| # | Fault | Where | Fix |
|---|---|---|---|
| 1 | No `deal` node was ever created, so `deal.*` facts landed on whichever person was the subject | `context/pipeline.py` | mint the deal on the account, move the facts to it, edge it to the company and the contact |
| 2 | History already had the facts, on the wrong nodes, with no way to get them onto a deal | `context/backfill.py` | `backfill_deal_nodes` — resolves the account by `works_at` OR email domain, and skips our own domains so `thegenios.com — deal` cannot happen |
| 3 | Correlation is thread-first, so a thread that anchored on the company before the deal existed pulled every later message back — releasing the affected events did nothing | `context/backfill.py`, `context/correlation.py` | `lift_companies_to_their_deals` (the direct analogue of the existing person→company lift, scoped to domains whose spec HAS a deal) plus a `rebuild` re-derivation |
| 4 | `deal.status` values were never constrained anywhere, so the model wrote `lost` / `rejected` / `engaged` while six `sales_v1` rules and three Sales situations all gate on the literal `open` | `context/pipeline.py` | normalise at the write to `open` \| `won` \| `lost`, keeping the model's own word as `deal.stage` |

Plus one in `domain_spec.py`: `general` had no `deal` entry, so an unhinted deal typed as
`general_deal` — a name no situation claims and the registry cannot resolve. `general` means *no
hint fired*, not *a domain called general*, and a deal node exists only because `deal.*` facts were
extracted. It now maps `deal → deal`.

## Measured on the live org, before → after

| | before | after |
|---|---|---|
| `deal` nodes | 0 | 33 |
| `deal.*` facts on a deal node | 0 of 83 | 57 (26 orphaned — personal-domain contacts with no account, correctly left) |
| `deal.status = open` | **0** | 7 (34 `lost`) |
| **`deal` situations** | **0** | **20** |
| `investor_relationship` situations | 13 | 9 — deliberately NOT eaten by the deal lift |
| events correlated | 162 of 354 | 287 of 354 |

Two things worth stating plainly rather than burying:

* **Most of this org's "deals" are investor rejections.** 34 of 41 `deal.status` facts normalise to
  `lost`, because the extractor reads a VC pass as a lost deal. The plumbing is now correct; the
  data on THIS inbox is thin, and a real sales inbox is what will exercise it.
* **The `general` domain dominates.** Most correspondence trips no keyword, which is why the
  `domain_spec` entry above mattered more than any corpus edit. Domain hint quality is the next
  real constraint on routing, not authoring.

## Tests

A new real-Postgres suite, `tests/test_deal_node_from_correspondence.py` (9 tests), covers minting,
fact placement, both edges, situation typing, idempotence, the backfill, the thread-first
limitation the `rebuild` flag exists for, and the domain scoping of the lift. It caught two defects
the hermetic suite could not see: a missing `nonlocal edge_n`, and a bare string written into a
`jsonb` column. Also fixed `tests/test_segments.py`, which seeded `node_id='p1'` — six modules used
that literal and `graph_nodes`'s primary key is `(node_id, version)` with no org in it, so on a
shared test database the second module to run silently seeded nothing.

---

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

## Re-verification — 2026-08-30

This document did its job: it found why nine batches of Sales authoring moved nothing, and the fix followed. Keeping the original text is right — but the headline must not be read as current.

### Closed

- **L2-1 · "There is no `deal` node. This is the big one." — DONE.** Minted at `context/pipeline.py:863` (`node_type="deal"`, `canonical_key="deal:" + company`); `deal` is in `_NODE_TYPES` at `:161`; both edges written at `:871-873` (`company owns deal`, `deal involves person`), with an inline note on why the person edge is load-bearing for a one-hop neighbourhood read. Backfill at `context/backfill.py:162 backfill_deal_nodes`, status normalisation at `:299 normalise_deal_status`, stage preserved at `:330`. `deal` is in the closed producible vocabulary at `tests/test_l3_route_vocabulary_contract.py:53`. Covered by `test_deal_node_from_correspondence.py`, `test_deal_join_wiring.py`, `test_deal_status_survives_a_sync.py`, `test_deal_conversation_join.py`.
- **L3-1 · "Admin and Customer Support cannot deliver at all" — DONE.** `packs/admin_v1.py` and `packs/support_v1.py` exist; `packs/wiring.py:20` — `BUILTIN_PACKS = [SALES_V1, GENERAL_V1, ADMIN_V1, SUPPORT_V1]`, with both in `DEFAULT_PACKS` at `:30-31`. `support_v1.py:10-19` documents the `support` vs `customer_support` id trap. **This was the second half of the headline.**
- **L3-2 · Three unauthored CS core objects — DONE.** `Domain Expertise/Customer Support Expertise/objects/core/{customer-account,named-contact,support-plan}.yaml`, plus `conversation`, `issue`, `satisfaction-score` (`6392498`) and `workaround`, `bug-report`, `product-area` (`68a4a8f`).
- **L3-3 · "91 hollow capabilities" — DONE, zero.** `admit.py --check` → 0 HOLLOW; 153/153 `identity.status: stable`, 153/153 `review_status: approved`, 0 stubs.

**The headline number specifically.** Sales unrouted is **4 of 47** — `demo`, `tam_sam_som`, `cold_calling`, `linkedin_outreach`. **None** of the ~20 this file names at lines 148-151 (`closing`, `negotiation`, `pricing`, `proposal_creation`, …) is among them.

### Still open — these are the reason this file is Reference and not archived

- **L2-2 · Eleven observation kinds emitted by nothing.** Undiagnosed and unchanged. The obs synonym normaliser at `context/pipeline.py:189-220` **predates this document** (`f462ff4`, 2026-08-05), so it is not the fix. Whether the eleven appear on a live org: **UNVERIFIED**, needs a DB.
- **L2-3 · `commitment.status` / `commitment.text` on 3 of 31 commitment nodes.** The forward writer now writes all three together (`context/pipeline.py:1138-1140`), but **there is no backfill** — `commitment` does not appear in `context/backfill.py` at all. Historical rows stay broken unless the graph is rebuilt.
- **L2-4 · No stage history.** `deal.stage` is written only as a current value (`pipeline.py:908`, `derived.py:239`, `backfill.py:330`). No `stage_history` or `time_in_stage` anywhere in `context/`.

One meta-note: this file's line 214-219 says "**No Layer 2 code was changed**". That was true of the diagnosis and is no longer true of the world — Layer 2 has changed substantially since, largely because of this file.
