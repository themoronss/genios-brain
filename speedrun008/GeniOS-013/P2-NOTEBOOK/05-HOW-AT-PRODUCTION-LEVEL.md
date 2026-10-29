# P2 · Notebook · 05 · How it will be done at production level

**Owner:** Harsh and the agents Harsh assigns. Rohit approves each tenant's activation and the decisions in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).
**The specification is [07](07-THE-NOTEBOOK-SPEC.md).** This file says how it reaches production: the order, the switches, the migration and the operations.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)). The relief track (Q1–Q3) is the only exception, and each of its steps is behind a row.
**Architecture rules that bind every step** (GeniOS-008 `01-RULES`):
- beside, never instead of;
- contracts first;
- switch one situation type at a time;
- the ratchet only shrinks;
- every item cites 00-ARCHITECTURE.

---

## 1 · Tables: one chain, headed by `work_items` (D-P2-12)

The full map, with REUSE, ADAPT or BUILD for every object, is 07 §1. In short:

- **The situation is `work_items`**, with the columns of 07 §4.2. A row is written only when admission ADMITs an L2 mutation (GeniOS-008 L3-1).
  - It runs beside today's `context_situations`, so the old writers never touch it.
  - At each tenant's cutover, `context_situations` stops being written for that tenant.
  - Atlas III.4 is amended with Rohit's yes.
- **Its versions are `work_item_versions`**, append-only, holding the typed parts of 07 §4.7 (Atlas's interpretations).
- **Decisions, executions and outcomes hang off it by foreign key:** `decision_objects` (new), `executions` (adds `work_id`, `page_version`, `goal_version` and `approval_ref`) and `execution_outcomes`.
- **New tables keyed to the situation:**
  - `work_members`;
  - `intelligence_links`;
  - `company_claims`;
  - `founder_decisions`;
  - `party_profiles`, `party_addresses` and `party_identity_links`;
  - `company_milestones`, `company_patterns`, `predictions` and `preferences`;
  - `evidence_citations` and `tenant_retention_policy`;
  - `goal_progress`, `attributions` and `prediction_actual`.
- **Existing tables adapted:**
  - `open_loops`;
  - `discrepancies`;
  - `situation_absences`;
  - `evidence_needs`;
  - `situation_admission_decisions`;
  - `company_goals` and `goal_situation_links`;
  - `learned_brain_entries` and `learning_objects`;
  - `source_coverage`;
  - `qualified_signals` (all ten L1 fields) and the correlation join rows.
- **Reused as they are:**
  - `graph_nodes`, `graph_facts`, `graph_edges`, `graph_aliases` and `merge_history` (the Evidence Graph);
  - `graph_versions` (the tenant revision);
  - `reasoning_runs` (receipts).

**Every table:**
- carries `org_id`, `trace_id`, `audience`, `schema_version`, `producer`, `writer` and `writer_ref`;
- has row-level security on `org_id`;
- joins the erasure path.

Migration numbers are assigned when written. The ones printed in older plans (0257, 0258) are re-checked against the head before use.

**Indexes:**
- (tenant, situation, version);
- (tenant, date) over expectations, `dates`, loop `expected_by`, goal `target_by` and lease `expires_at`: P1's date index;
- (tenant, goal);
- (tenant, evidence id) on `evidence_citations` and `work_members`;
- (tenant, party) on `party_profiles`, `work_members` (kind `party`) and `company_claims.said_to`.

## 2 · Admission goes live, per tenant

- **The laws:** A-1 to A-32 (07 §11.2) run **before** a change is kept, change by change, so one bad line never holds the page.
- **The door:** `context/work_store` is the only writer. It adapts `context/situation_publisher` (whose V-1 to V-10 laws and hold reasons it keeps) and `context/l2_admission`.
- **Going live:** it replaces the shadow admission for a tenant when that tenant's loop row (P1) goes from `shadow` to `live`.
- **The word-by-word checker** that held 66 of 86 results stays only as a second opinion that logs. It never blocks a page.
- **The old situation admission** (985 decisions in the first week) and the rule situations it admits are retired per tenant and per type at the parity gate (P1 §4).

## 3 · Migrating the existing data

1. **Placement.** Existing mail is grouped by **L2's placement call** (P4), from code's candidate bundles:
   - registrable-domain clusters;
   - one bundle per introduction;
   - system mail by the organisation it is about.

   It runs in shadow and is checked on the golden tenant. The 603 thread objectives L1 already wrote are its cheapest input (U13-28).
2. **Judge** each live situation once (P4). That is the one-time onboarding cost: about $8–10 of reasoning for a founder-size tenant (P1 [06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md)).
3. **The old notes stay as evidence only.** Promises, questions and conflicts written by rules are stored as facts with `derivation_type = rule_derived`. They carry `epistemic_status = inferred`, are left out of snapshot block N, and are never the source of a Notebook card. They are no longer turned into cards once the tenant is live. The page decides.
4. **Old rule-born situations retire per tenant and per type,** after the parity gate (P1 §4); the ratchet shrinks. The readings of departments that are off stop at once (Q1).
5. **The clock-dependent derived writers** (about 8 of them, GeniOS-008 L3-5) stop writing to the graph. Their values become L2 tools on the snapshot. That ends most of the churn.

## 4 · Archived mail (D-P2-3)

- **Promoted through the existing path** (`capture/landing/promote.py`) in two cases:
  - **(a)** Code classes the mail as obligation-bearing (07 §2.3) from its headers and a code-only scan of its decrypted text.
  - **(b)** It belongs to a live situation, or L2 raises an EvidenceNeed for it.
- **No model sees it before promotion,** and promoted text is marked `recovered`.
- **L1 never reads the Notebook.** The promotion request arrives as an EvidenceNeed (07 §9.3); L1 runs "promote mail X".
- **Bulk and newsletter mail** stays archived and unread.

## 5 · Privacy, storage, erasure

- **Postgres is the only source of truth.** Dossiers, snapshots, the date index, the expertise index and any embeddings are caches. There is no graph database. Deleting the caches changes no answer (07 §12.3).
- **Object storage:** raw bodies and encrypted Screen captures, referenced by id, with retention per org (Atlas III.4).
- **Isolation:**
  - Row-level security on `org_id`.
  - A CI guard refuses SQL against Notebook tables without an `org_id` predicate.
  - No reasoning reads across tenants.
  - Learning across tenants needs the tenant's consent, and is not part of this plan.
- **Erasure:** a tenant's evidence and conclusions are deleted together by the existing path. Every table of 07 §1 is added to it, and a test erases a test tenant and finds no row left (P2-24).
- **Portability (D-P2-15):** no Notebook table or check depends on a cross-tenant join or a hosted-only feature, and a tenant's Notebook exports whole. `export_tenant` and `import_check` prove it (P2-24).
- **What a model saw:** `model_call_evidence` keeps the ids printed to every call (ids only), so the founder can see which data reached a model.

## 6 · Retention follows the work (D-P2-7)

**Today:** clean text is deleted 180 days after capture, and so is the encrypted raw mail (parked items: 365). The clock ignores the work.

**The rule** (07 §14):

| Evidence | Kept |
|---|---|
| Cited by any situation that is not closed (quiet included), or by a goal that has not ended | while cited |
| Cited only by closed situations or ended goals | `after_close_days` after the close (per tenant; 180 by default), then its citations are marked `quoted_only` |
| In a thread we wrote in | at least 365 days after its last message |
| Held by no situation | 180 days after capture, as today |
| Admitted quotes, with their source ids | with the page until erasure. When the evidence finally expires, the citation is marked `quoted_only` |
| Raw copies | deleted once clean text exists and promotion is decided, unless a provenance row or fact still points at them; a tenant's policy may only shorten this |

**How it is enforced:**
- The Notebook publishes a retention-hold list through its API.
- An L0 platform job, not `capture/`, applies it to the purges (`capture/prepared_store.purge_expired`, `capture/payload_store.purge_expired`).

## 7 · Size and the database plan (D-P2-9)

**Today:** one tenant, 570 MB reported against a 472 MB ceiling, and about 280 MB of live rows when loaded fresh. The largest tables are provenance links (49 MB), one week of Screen captures (45 MB) and raw copies (30 MB).

**In order:**
1. **Measure** production's sizes and dead rows (Q2).
2. **Cut the churn:**
   - departments that are off stop their readings (Q1);
   - whole-company work comes off the per-mail run (P1 R2);
   - clock-dependent values stop being written (§3 step 5).
3. **Move** Screen captures and raw bodies to object storage, and trim provenance kept for facts nobody reads.
4. **Move to a larger database plan before the second customer.**

**Budget per founder tenant after a year:** conclusions under 50 MB. Health reports size per tenant every day.

## 8 · Teams and visibility (D-P2-10)

- **Evidence carries its audience** from capture (`visibility_scope` and `visibility_principals` exist on `source_events` today).
- **Every conclusion stores the narrowest audience** of its evidence and of the rows it derives from (07 §14).
- **Pages and cards are built per reader.** Withheld evidence is counted, never quoted. A teammate's private evidence that the work needs becomes a task for that seat.
- **A Screen moment stays with the capturing seat.** It is stored as a content hash and quotes of at most 12 words.
- **A member's mailbox connected later** is an onboarding wave for that seat (P1 [06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md) §7).
- **No team is onboarded** until P2-10's test passes in the notebook and again on the product.

## 9 · Monitoring

**Per tenant per day**, in the daily health row:
- situations by state and attention band;
- versions written;
- admissions by verdict and law (from the ledger);
- goals by health, and goals with no next move;
- live work not linked to a goal (counted, never hidden);
- open loops past their date;
- conflicts to decide;
- invariant failures (there should be none);
- facts and situations whose department is off (there should be none);
- size of conclusions and of evidence.

Also, from 07 §12:
- **context health:** facts with a receipt %, fresh in 7 days %, sources connected;
- **company checks**, graded working, needs attention or broken.

**Pipeline counters per run:**
- `situations_formed`, with ids;
- `decision_emitted`, with ids;
- held and rejected by law.

**Daily:**
- human touches per resolved situation;
- calls and cost per admitted situation.

**Alerts:**
- any invariant failure;
- a live situation whose evidence is due to expire;
- size over the tenant's budget;
- a held-change reason that jumps (a prompt or schema change gone wrong);
- a switch or loop whose claim disagrees with the ledger (P1 §4).

## 10 · What must never happen

- **A conclusion kept without evidence**, or without passing the check.
- **A version row updated,** or a DELETE outside erasure.
- **A page version that doesn't say what changed.**
- **A card standing on a situation that is not live, or on a version that is not current.**
- **A goal shown as confirmed** that the founder didn't confirm.
- **A silent drop.** Every refused change is held with its reason, and every unlinked live situation is listed.
- **The words behind live work deleted by a clock.**
- **A page quoting evidence its reader may not see.**
- **Readings for a department the company hasn't switched on.**
- **A model call inside the Notebook,** or a module other than the store writing its tables.
- **A number or date on a page with no tool or quote behind it.**
- **GeniOS picking a side in a conflict,** or an absence stated as found when the source was not fully read.
