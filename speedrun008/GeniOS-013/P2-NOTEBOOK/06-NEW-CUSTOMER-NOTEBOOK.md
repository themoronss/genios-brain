# P2 · Notebook · 06 · A new customer's notebook

**What this file answers:** what a new customer's Notebook must hold on day one; what building it costs; how much it stores; what changes for larger customers and teams; and when the Notebook is ready for customers beyond the design partner.

The loop that builds it, phase by phase, is P1's Onboard ([P1 06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md) §3). This file is about what that loop leaves behind.

---

## 1 · What the Notebook must hold on day one

In the order the Onboard loop builds it:

| # | What | Built from | Why it comes at this point |
|---|---|---|---|
| 1 | **The company page** (07 §3.4): who we are, our addresses and domains, our time zone, what we do, the founders, what we told people, the needed facts (each filled or "not stated anywhere") | the signup, our own sent mail | Everything after it needs to know who "us" is. Our addresses decide whose move it is, and our time zone decides "today" |
| 2 | **Parties** (07 §3.1): each person and organisation, with its kind, what it is to us, affiliations, identity strength, who introduced whom, and relationship state | mail headers, signatures, the company page | Placement and judging read parties, not addresses |
| 3 | **Coverage** (07 §2.6): per source and per thread, what was read and what could not be | the capture run | Every later "no reply" rests on it |
| 4 | **Situations:** one per piece of work, with their members | **L2's placement** over code's candidate bundles (P4), admitted here. Bundles come from organisation clusters, one per introduction, and system mail about what it names | The unit everything else hangs on (D-P2-1) |
| 5 | **Pages:** each live situation judged once. A page holds its Atlas state, whose move it is (derived), expectations and dates, loops and conditions, our claims, and the four kinds of absence | the snapshot: the situation's evidence, Plane D and Plane R | The date index (P1) and the cards (P5) read pages |
| 6 | **Loops by code** (07 §4.4, §4.8): follow-throughs after meetings, bounces made moot and re-sends opened, waves with their recipients | code, from members | These are the silences most ideal cards rest on |
| 7 | **Goals, proposed:** each with its target, the evidence and the situations that serve it, at the right grain | the pages | The founder confirms them; until then they are printed apart, as "proposed" (D-P2-13) |
| 8 | **Links, conflicts and lifecycle** | relate, and the pages | Facts travel along links (P2-6); conflicts wait for the founder (§4.5); quiet work stops making cards (P2-3) |

The **founder's corrections** come in from the first screen: the company page, the goals, and answers to questions. They are stored as evidence (P2-7). Nothing is "confirmed" until the founder confirms it.

## 2 · What building it costs, once

Measured on `b2`, the design partner's six months (about 1,800 mails):

| Phase | Calls | Cost | Time |
|---|---|---|---|
| Company page | 1 | $0.10 | 1 min |
| Parties | 9 | $0.66 | 2 min |
| Situations (grouping) | 107 | $1.11 | 2.7 min |
| Pages (378 situations judged) | 401 | $6.37 | about 25 min, 8 workers |
| Links and goals (relate) | 3 | $0.17 | 2.7 min |
| **Total** | | **$8.41, once** | about 40 min |

**For other sizes** the scale is in P1 [06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md) §4: about $10–15 once, for a founder with 365 days.

**After onboarding,** the Notebook changes only where the Evolve loop touches it. That costs under about $20 a month in reasoning (P1 [05](../P1-ORCHESTRATOR/05-HOW-AT-PRODUCTION-LEVEL.md) §6).

## 3 · What it stores, and how much

| | Size | Kept |
|---|---|---|
| Conclusions (pages, versions, loops, claims, links, goals, held changes) | a few MB per founder; target under 50 MB after a year | until the tenant is erased |
| Evidence, clean text | about 8 MB in the first week, for six months of mail | while live work cites it; then 180 days after the work closes, or after capture for mail no work holds (D-P2-7; 07 §14) |
| Evidence, encrypted raw copies | about 30 MB in the first week | until clean text exists and promotion is decided, and never while a fact or provenance row points at them (D-P2-7) |
| Screen captures | 45 MB in the first week | a retention per org, to be set (Q2) |
| Provenance links | 49 MB in the first week | to be trimmed (Q2) |

**What blocks a second customer:** one tenant is already over the database's ceiling (570 MB of 472). The order to fix it is in [05](05-HOW-AT-PRODUCTION-LEVEL.md) §7:
1. measure;
2. cut the churn;
3. set retention;
4. a larger database plan.

## 4 · Larger customers and teams

| Customer | What changes for the Notebook | Proved by |
|---|---|---|
| A founder with more mail (3–5× this one) | Bigger clusters in grouping. The cost should grow no faster than the mail | P2-12 (grouping at scale) |
| A team: several mailboxes | Threads cross mailboxes. Each piece of evidence carries its audience, and each page is built per reader | P2-10 (visibility), then [05](05-HOW-AT-PRODUCTION-LEVEL.md) §8 |
| A member who connects later | Their threads join the situations already known, as an onboarding wave for that seat | P1-4's placing step, with P2-10 |
| Other tools (Slack, Notion, a CRM …) | New kinds of evidence, each with an instant, an as-of rule, an id that can be cited, and a placing rule | P2-5 |

## 5 · Gaps today, for a new customer

| # | Gap | Fixed by |
|---|---|---|
| N-G1 | No conclusions are kept in the product at all | [05](05-HOW-AT-PRODUCTION-LEVEL.md) §1–§2 (the Intelligence Graph, admission live) |
| N-G2 | Situations are rule types, and most of them are a support desk the company may not have | Q1 now; the situations from grouping at the parity gate |
| N-G3 | "Who we are" is computed per read, and the company brief needs a founder's acceptance that never comes | the company page (phase 1), confirmed on the first screen |
| N-G4 | Goals have no target, plan, progress, status or next move | P2-1, P2-2, P4-6 |
| N-G5 | The founder's answers never arrive (40 asked, 0 answered) | P2-7, with P5's screens and P1-5 |
| N-G6 | Evidence text expires 180 days after capture, whatever the work | D-P2-7, P2-11, Q3 |
| N-G7 | One tenant fills the database | [05](05-HOW-AT-PRODUCTION-LEVEL.md) §7 |
| N-G8 | Teams: every mail is treated as the founder's | P2-10 |
| N-G9 | Grouping is proved on one mailbox only | P2-12 |

## 6 · Ready when

All of these must hold, each checked by a test or a measurement:

0. **The specification is built, not approximated:**
   - every admission law (07 §11.2) and invariant (§15) passes with its fixtures;
   - every read goes through the API (§12);
   - every table is on row-level security and the erasure path (P2-10, P2-24), and every guard fails on its seeded mutation (P2-8);
   - a tenant's export, loaded into an empty database, passes every invariant and guard (P2-24);
   - the 309 requirements in [08](08-REQUIREMENTS-TRACE.md) are each built or explicitly owned elsewhere;
   - snapshot reads are under 2 s and admissions under 1 s at p95.
1. **The golden tenant's Notebook passes** the P2 targets in [03](03-EXPECTED-VS-HAPPENING.md) and the acceptance set in [10](../10-ACCEPTANCE.md).
2. **Grouping at scale** (P2-12) holds its cost and finds the 17 ideal items.
3. **Visibility** (P2-10) passes its test, before any team.
4. **Retention follows the work** (§6 of [05](05-HOW-AT-PRODUCTION-LEVEL.md)): no live work loses its evidence in a weekly check.
5. **Size:** the golden tenant fits its database plan with room for the next customers, and health reports size per tenant.
6. **Erasure** removes a test tenant completely, including every new table.
