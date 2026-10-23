# 12 · Production-ready for every customer, not only Rohit

**Written for:** Harsh (CTO), and Rohit for the product calls marked 🔒.
**The problem this file solves:** Steps 1–7 make GeniOS produce the `/preview` cards for **one** org, partly by hand: a plan fixed in the database, switches flipped by an admin, brief lines Rohit accepted, a resync Harsh ran. A customer must get the same result with no engineer touching their account. This file lists what turns each hand action into product, how a release is judged safe, and how quality and cost are measured per customer.

---

## A · Every hand action becomes onboarding

| What was done by hand for Rohit | Where | What it becomes for every customer | Unit | Status |
|---|---|---|---|---|
| plan set to non-expiring internal | `orgs` row (S02.U1) | design partners: an `is_internal` plan set by the staff tool at signup; paying customers: billing; a lapse **alerts** (U12-01) and follows Rohit's read-only decision (D-12-1) | U12-01 | ⬜ |
| `expert_review`, `l2_reasoning`, `founder_office` switched on | admin routes (S02.U3) | onboarding switches them on for a founder-type company once the real-model pass (S07.U4) and the parity gate (Gate 7) pass on the design partners: `NOT_DEFAULT_ON` (`platform/l4_activation.py:167-203`) loses `expert_review` and `l2_reasoning`; Founder Office `default_on` becomes true for orgs whose setup says "founder-led" | new: U12-20 | ⬜ after Gate 7 |
| `l2_cards` per type | S25.U3 | per type, globally, when that type's board passes, never per tenant by hand | S25.U1, S25.U4 | ⬜ |
| brief lines naming senders and work in motion | Rohit accepted lines (S02.U4) | the 10-minute setup asks: "who are you raising from / applying to / selling to / hiring?" and offers what the drafter (S27.U1) already proposes from the mail; each answer becomes an accepted brief line, so the gate's W-07 and the kind windows work from day one | S27.U3 + the setup form (dashboard, dummy first) | ⬜ |
| self identity (our addresses and domain as "us") | declared for Rohit (S02.U4) | derived from the connected mailbox's address and domain at connect time, confirmed in setup | new: U12-21 | ⬜ |
| 365-day window | PATCH by Harsh (S09.U4) | the founder's pick, written through (S09.U1), with the **estimated cost and time shown before they confirm**; default for founder-led companies: 365 (Rohit's D16) | S09.U1 + the estimate in the setup | 🔨 |
| the resync of old deleted mail | Harsh ran the script | only Rohit's org had the old deleting gate; new customers never need it | — | n/a |
| promotion of archived intros | Harsh ran the script | the gate keeps them from the start (U12-05); promotion stays a staff tool | U12-05 | ⬜ |
| catch-up budget | a row Harsh writes (U12-17) | written automatically when a first backfill completes, capped by plan tier | U12-17 | ⬜ |
| categories | Rohit's eight | each domain's default list in Plane D; renaming through the brief | N2 | ⬜ |

**U12-20 · Founder defaults on, after the gate.** Change `NOT_DEFAULT_ON` and Founder Office's `domain.yaml` `default_on` only after Gate 7 passes on Rohit's org and on at least two more design partners. Test: a new tenant created by `make_tenant_live` with setup "founder-led" has the three switches on; one without it does not.

**U12-21 · Self identity at connect.** When a Gmail connection is created, record the mailbox's address and its domain (unless it is a public host like gmail.com, where only the address counts) as "us" in the brief, pending the founder's confirmation in setup. Test: a synthetic connection on `founder@acme.example` adds `acme.example` as us; on `someone@gmail.com` adds only the address. Uses the canonical public-host list (S08.U2).

---

## B · The release gate: when a change may reach customers

A change reaches `harsh/mvp` only when all five hold. `scripts/release_gate.py` (S05.U3) checks 1–4 by exit code.

1. **CI green on that SHA** (branch protection, S03.U2).
2. **Migrations apply in order on a fresh database** and on a copy of production's schema head (`GET /health` `schema_head`). Watch: migrations apply at boot, and a read-only database silently skips them (GeniOS-011 04 §A2).
3. **For any change to a prompt, a gate, the claim check or a model site: a capped real-model pass** (probe of 1–2 calls first, then the pass), held share and cost logged.
4. **The golden board did not regress** (63/4 on 23 Oct; it may only improve), on both paths.
5. **The next day, on Rohit's org first:** `daily_health` cards ≥ half the 14-day median, no lane emptied, `why_no_card` distribution not worse, and `preview_parity.py` not worse. Only then to the other design partners.

**Rollback:** every unit is one commit, so `git revert <sha>` and redeploy. A switch is rolled back with `DELETE /admin/l4-activation/<org>` or `/admin/l3-activation/<org>`. A migration is additive (columns `if not exists`, new tables), so a rollback leaves it in place harmlessly.

---

## C · Quality, measured per customer, every week

| Number | Definition | Source | Bar for "working" |
|---|---|---|---|
| **Card usefulness** | cards judged useful ÷ cards judged, per lane | the founder's card verdicts, read by `GET /feedback/precision` (S40.U2 ✅) | ≥ 70% |
| **Held share** | held judgments ÷ judgments, per model site | `expert_reviews`, `reasoning_results` | ≤ 25% |
| **Why no card** | the 8 counts per sweep (judged, held, refused, truncated, carried_budget, fell_back, covered_not_carded, budget_exhausted) | S18.U3 ✅, `daily_health` | no single reason > 30% of judged files |
| **Filed share** | events filed ÷ events kept by the gate | S14.U4 | ≥ 90% |
| **Meeting coverage** | external meetings in a file ÷ external meetings in the window | U12-07 | ≥ 90% |
| **Important-situation recall** | of a human-labelled set of the customer's important situations, how many produced a card or brief item | S43.U3 (the blind P1–P5 benchmark re-run) | measured, then a bar Rohit sets |
| **Parity with the ideal** (design partners who allow it) | `preview_parity.py` and `ideal_card_gap.py` against an ideal set made the way `/preview` was | the customer's own machine or a consented run | ≥ 18 of 20 present; subject, steps, draft, goal and category present |
| **Cost per admitted situation** | model spend ÷ admitted situations | `llm_costs`, `l2_admissions` | within the plan's margin (Rohit sets it against the ~$20/seat price) |

---

## D · Cost: what is known, what must be measured

| Item | Known today | To measure before customers |
|---|---|---|
| R-7 expert / R-9 L2 | Sonnet 5, $2.00/day each per org, $0.10 / $0.15 per call (`reason/bundle/budget.py:63-71`) | cost per judged file on the production model (S07.U4) |
| R-10 card writer (S34.U3) | one call per new card version | the probe's cost per card |
| Gate batch + extraction on a backfill | unknown at 365 days | the S09.U4 dry run's message count × per-message cost |
| Weekly brief drafter (S27.U1) | one Sonnet-class call per tenant per week, now for every tenant | skip expired orgs (GeniOS-011 follow-up (e)) |
| Catch-up after a resync (U12-17) | proposed 3 days × $10/day per site | the actual first-look count per customer |

No number above may be quoted to a customer until measured (Admin Atlas rule: every number is Sourced, Measured, Illustrative or Target).

---

## E · Privacy, safety and the public repository

| Issue | Today | What to do | Owner |
|---|---|---|---|
| The brain repository is **public** and carries Rohit's address, the production org id and real counterparties' names in older docs | GeniOS-011 06 decision `process-repo-is-public-with-real-data` | make it private, or scrub; until then, nothing new with real data (this folder follows that) | 🔒 Rohit |
| `/preview` holds real mail | owner-only route, the HTML in a server-only module (`src/server/ideal-preview-html.ts`) in the **private** dashboard repo | stays, per Rohit (23 Oct) | — |
| Private events | in no file, even for their owner | D-12-2 ([05 Part A](05-L3-CONTEXT-GRAPH.md)) | 🔒 Rohit |
| External messages | GeniOS drafts; a human sends; agents never send externally | unchanged; every draft on a card is copy-only | — |
| Visibility | a conclusion is never shown wider than its evidence (seat visibility) | unchanged | — |
| Customer data exit | the pilot terms say data is removed on exit | `/reset` erases tenant rows (incl. `daily_health`, `7d3a5c7b`); verify it covers the new tables (goals, links, copy) when they land | Claude, per new table |

---

## F · Operations

| Item | State | Action |
|---|---|---|
| DB size | 446 MB on 19 Oct; `daily_health` alerts at 450 MB (`GENIOS_DB_SIZE_CEILING_MB`) | plan the tier before the 365-day resync (it adds bodies) | 🔒 Harsh |
| Alerts | `ops_alert` is a log line unless a webhook is set (S10.U4) | set the webhook | 🔒 Harsh |
| Branch and push owner | 823 commits reached production in one push on 18–21 Oct with CI red four times | one prod branch, one push owner, protection on (S03.U2, S03.U3) | 🔒 Rohit + Harsh |
| Deploy facts | `/health` names the SHA once `GENIOS_BUILD_SHA` is set | set it at every deploy | 🔒 Harsh |

---

## G · The production-ready checklist

GeniOS is production-ready for customers when every line is ✅, measured, with the source named in [13-LOG](13-LOG.md):

1. Gate 7 passed on Rohit's org ([09](09-STEPS.md)).
2. Gate 7's parity (or the scenario set of [11](11-SCENARIOS.md)) passed on two more design partners, with no hand action beyond the setup form.
3. Every hand action of §A is onboarding.
4. The release gate (§B) runs on every deploy.
5. The quality numbers (§C) are measured weekly and at the bar for four weeks running.
6. Cost per admitted situation is measured and inside the margin Rohit set.
7. The privacy items (§E) are decided.
8. Alerts reach a person (§F).
