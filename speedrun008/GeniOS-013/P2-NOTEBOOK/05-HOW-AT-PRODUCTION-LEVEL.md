# P2 · Notebook · 05 · How it will be done at production level

**Owner:** Harsh and the agents Harsh assigns. Rohit approves each tenant's activation.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)).

---

## 1 · Tables

The product gets the Intelligence Graph: the same objects the notebook proved, with tenant ids, in the same database as the Evidence Graph. Migration numbers are assigned when written; the ones printed in older plans are taken.

| Table | Holds | Based on |
|---|---|---|
| `work_items` | The business situation: title, kind, status, lifecycle state, stage, whose move and since when, next expected, importance, current verdict, version | GeniOS-013 [05](../05-THE-WORK-OBJECT.md) (the work object) |
| `work_item_versions` | Every admitted change: what changed and why, the run that made it, the evidence ids | notebook `work_versions` |
| `work_members` | Mail, meeting, Screen thread, execution, founder action; joined, and left with a reason | notebook `members` (more evidence kinds) |
| `work_loops` | Questions, asks and promises: who owes them, the opening and settling evidence, due date | notebook `loops` |
| `work_claims` | What we told people: metric, value, to whom, when | notebook `claims` |
| `work_links` | Part of, evidence for, contradicts, duplicate | notebook `links` |
| `company_goals` | Extended with the goal object's fields (target, captured, plan, progress, status, next move, gaps, parent, approval) | migration 0254 (built), plus columns |
| `work_goal_links` | The one link set: relation, through, evidence, who linked it | replaces `goal_situation_links` (0255, 0 rows today) |
| `decisions` | The founder's answers, approvals and "not now" (the table exists with 0 rows) | built, unused |
| `admission_held` | Each refused change as proposed, with its reason | notebook `held` |

**Indexes:**
- (tenant, work item, version);
- (tenant, next expected date), which is the date index P1 reads hourly;
- (tenant, goal).

## 2 · Admission goes live, per tenant

- The code check (`nb/checks.py`, ported) runs **before** a change is kept, change by change: one bad line never holds the page.
- It replaces the shadow admission for a tenant when that tenant's loop row (P1) goes from `shadow` to `live`.
- The word-by-word checker that held 66 of 86 results stays only as a second opinion that logs. It never blocks a page.

## 3 · Migrating the existing data

1. **Group** existing mail into business situations with the notebook's Phase D. That means registrable-domain clustering, model grouping per cluster, one situation per introduction, and system mail grouped by sender. It runs in shadow and is checked on the golden tenant.
2. **Judge** each situation once (P4). That is the onboarding cost, about $8–10 for a founder-size tenant.
3. **Keep the old notes as evidence only.** Promises, questions and conflicts written by rules are no longer turned into cards once the tenant is live. The page decides.
4. **Retire the old rule situations per tenant**, after the parity gate (P1 §4).

## 4 · Archived mail (if Rohit says yes to D-P2-3)

- Use the existing promotion path (`capture/landing/promote.py`). Archived mail is promoted **only when it belongs to a live situation**: a reminder from a programme the company applied to, or a renewal notice for a tool it pays for.
- The stored payload is already encrypted with the tenant's key. Bulk and newsletter mail stays archived and unread.

## 5 · Privacy, storage, erasure

- **Size:** the conclusions are a few MB per founder-size tenant (the notebook's whole schema, with every build and test build, is 54 MB).
- **Isolation:** every row carries its tenant id; no reasoning reads across tenants. Learning across tenants ("company patterns" beyond one company) needs the tenant's consent and is not part of this plan.
- **Erasure:** a tenant's conclusions are deleted with its evidence by the existing erasure path, which gets the new tables added.
- **"Your data stays with you"** (the film): today it is true per tenant in the product's own database, and fully local in the notebook. A local-first deployment is a product decision for later, not part of this plan.

## 6 · What must never happen

- **A conclusion kept without evidence**, or without passing the check.
- **A page version that doesn't say what changed.**
- **A card standing on a dormant, done or history situation.**
- **A goal shown as confirmed** that the founder didn't confirm.
- **A silent drop.** Every refused change is held with its reason, and every unlinked live situation is listed.
