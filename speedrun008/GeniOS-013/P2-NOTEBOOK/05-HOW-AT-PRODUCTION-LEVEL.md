# P2 · Notebook · 05 · How it will be done at production level

**Owner:** Harsh and the agents Harsh assigns. Rohit approves each tenant's activation.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)). The relief track (Q1–Q3) is the only exception, and each of its steps is behind a row.

---

## 1 · Tables

The product gets the Intelligence Graph: the same objects the notebook proved, in the same database as the Evidence Graph. Every row carries its tenant id and the audience of the evidence behind it (§8). Migration numbers are assigned when written; the ones printed in older plans are taken.

| Table | Holds | Based on |
|---|---|---|
| `work_items` | The business situation: title, kind, status, lifecycle state and since when, stage, whose move and since when, next expected (what, from whom, by when), importance, current verdict, version, audience | GeniOS-013 [05](../05-THE-WORK-OBJECT.md) (the work object) |
| `work_item_versions` | Every admitted change: what changed and why, the run that made it, the evidence ids | notebook `work_versions` |
| `work_members` | Mail, meeting, Screen thread, execution, founder action, answer. Each joined, and left with a reason | notebook `members` (more evidence kinds) |
| `work_loops` | Questions, asks and promises: who owes them, the opening and settling evidence, the due date | notebook `loops` |
| `work_claims` | What we told people: metric, value, to whom, when | notebook `claims` |
| `work_links` | Part of, evidence for, contradicts, duplicate | notebook `links` |
| `company_goals` | Extended with the goal object's fields: target, captured, plan, progress, status, next move, gaps, parent, approval | migration 0254 (built), plus columns |
| `work_goal_links` | The one link set: relation, through, evidence, who linked it | replaces `goal_situation_links` (0255, 0 rows today) |
| `decisions` | The founder's answers, approvals and "not now". The table exists, with 0 rows | built, unused |
| `admission_held` | Each refused change as proposed, with its reason | notebook `held` |
| `evidence_citations` | Which work item or goal cites which evidence, and since when. Retention reads this (§6) | new (P2-11) |

**Indexes:**
- (tenant, work item, version);
- (tenant, next expected date): the date index P1 reads hourly;
- (tenant, goal);
- (tenant, evidence id) on `evidence_citations`.

## 2 · Admission goes live, per tenant

- The code check (`nb/checks.py`, ported) runs **before** a change is kept, change by change, so one bad line never holds the page.
- It replaces the shadow admission for a tenant when that tenant's loop row (P1) goes from `shadow` to `live`.
- The word-by-word checker that held 66 of 86 results stays only as a second opinion that logs. It never blocks a page.
- The old situation admission (985 decisions in the first week) and the rule situations it admits are retired per tenant at the parity gate (P1 §4).

## 3 · Migrating the existing data

1. **Group** existing mail into business situations with the notebook's Phase D:
   - registrable-domain clustering;
   - model grouping per cluster;
   - one situation per introduction;
   - system mail grouped by sender.

   It runs in shadow and is checked on the golden tenant. The 603 thread objectives L1 already wrote are its cheapest input (U13-28).
2. **Judge** each live situation once (P4). That is the one-time onboarding cost: about $8–10 of reasoning for a founder-size tenant (P1 [06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md)).
3. **Keep the old notes as evidence only.** Promises, questions and conflicts written by rules are no longer turned into cards once the tenant is live. The page decides.
4. **Retire the old rule situations per tenant,** after the parity gate (P1 §4). The support-desk readings stop at once for a tenant without Support (Q1).

## 4 · Archived mail (if Rohit says yes to D-P2-3)

- Use the existing promotion path (`capture/landing/promote.py`). Archived mail is promoted **only when it belongs to a live situation**: for example, a reminder from a programme the company applied to, or a renewal notice for a tool it pays for.
- The stored raw copy is already encrypted with the tenant's key, and kept 180 days after capture. A promotion must happen inside that window.
- Bulk and newsletter mail stays archived and unread.

## 5 · Privacy, storage, erasure

- **Isolation:** every row carries its tenant id, and no reasoning reads across tenants. Learning across tenants ("company patterns" beyond one company) needs the tenant's consent, and is not part of this plan.
- **Erasure:**
  - a tenant's conclusions are deleted with its evidence by the existing erasure path;
  - the new tables (§1), and P1's `loop_wakeups`, `loop_runs` and `tenant_loop_policy`, are added to it;
  - a test erases a test tenant and finds no row left.
- **"Your data stays with you"** (the film): today it is true per tenant in the product's own database, and fully local in the notebook. A local-first deployment is a product decision for later, not part of this plan.

## 6 · Retention follows the work (D-P2-7)

**Today:** clean text is deleted 180 days after capture, and so is the encrypted raw mail (parked items: 365). The clock ignores the work.

**The rule:**

| Evidence | Kept |
|---|---|
| Cited by a live work item or goal (`evidence_citations`) | while it is cited, and 180 days after the work ends |
| Held by no work item (noise, bulk) | as today: 180 days after capture |
| The quotes a page admitted, with their source ids | with the page, until the tenant is erased |
| Encrypted raw copies | only until clean text exists and promotion is decided (§4); then the clean text is enough |

**How it is enforced:** the purge (`capture/prepared_store.purge_expired`, `capture/payload_store.purge_expired`) skips rows that `evidence_citations` holds.

## 7 · Size and the database plan (D-P2-9)

**Today:**
- One tenant: 570 MB reported against a 472 MB ceiling.
- About 280 MB of live rows when loaded fresh.
- The largest tables:
  - provenance links, 49 MB;
  - **one week** of Screen captures, 45 MB;
  - raw copies, 30 MB.

**In order:**
1. **Measure** production's sizes and dead rows (Q2).
2. **Cut the churn:**
   - the support desk off for tenants without Support (Q1);
   - whole-company work off the per-mail run (P1 R2).
3. **Set Screen capture retention per org**, and trim provenance kept for facts nobody reads.
4. **Move to a larger database plan before the second customer.**

**Budget per founder tenant, after a year:**
- conclusions under 50 MB;
- evidence as the retention rule above leaves it.

Health reports size per tenant every day (§9).

## 8 · Teams and visibility (D-P2-10)

- **Evidence carries its audience** from capture (`visibility_scope`, `visibility_principals` exist on `source_events` today).
- **A work item records the audience of the evidence it cites.** A situation that mixes a private thread and a shared one keeps the private part visible only to its owner.
- **Dossiers and cards are built per person,** from the evidence that person may see. The founder sees company-visible work; a member sees their own and the company's.
- **A member's mailbox connected later** is an onboarding wave for that seat (P1 [06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md) §7): their threads are placed into existing situations with their audience kept.
- **No team is onboarded** until P2-10's test passes in the notebook and again on the product.

## 9 · Monitoring

**Per tenant per day**, in the daily health row:
- work items by lifecycle state;
- versions written;
- changes held, by reason;
- goals by status, and goals with no next move;
- live work not linked to a goal (counted, never hidden);
- open loops past their date;
- invariant failures (there should be none);
- size of conclusions and of evidence.

**Alerts:**
- any invariant failure;
- a live work item whose evidence is due to expire;
- size over the tenant's budget;
- a held-change reason that jumps (a prompt or schema change gone wrong).

## 10 · What must never happen

- **A conclusion kept without evidence**, or without passing the check.
- **A page version that doesn't say what changed.**
- **A card standing on a dormant, done or history situation.**
- **A goal shown as confirmed** that the founder didn't confirm.
- **A silent drop.** Every refused change is held with its reason, and every unlinked live situation is listed.
- **The words behind live work deleted by a clock.**
- **A page quoting evidence its reader may not see.**
- **Readings for a department the company hasn't switched on.**
