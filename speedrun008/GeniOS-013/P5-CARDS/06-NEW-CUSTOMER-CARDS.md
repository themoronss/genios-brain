# P5 · Cards · 06 · A new customer's cards

**What this file answers:** what a new customer sees, card by card, from the minute they connect, and what has to hold so that every customer, not only the design partner, gets the same cards from the same code. The onboarding itself (the phases, the waves, the budget) is P1's ([P1 06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md)); how GeniOS thinks for a new customer is P4's ([P4 06](../P4-PLANE-R/06-NEW-CUSTOMER-REASONING.md)).

---

## 1 · The rule that makes cards scale

- **One card layer for every customer.** The raise rule, the lane map, the severity table, the rank, the contract, the budgets' starting values and the screens are code and data shipped once. No card rule names a customer, a person, an address, a domain or a card id (07 §0 rule 15; CG-12).
- **What differs per customer is data:** its time zone and working hours; its goals; its seats and their responsibilities; its company patterns ("yours", with n); its packs (which domains are live); its budgets as L6 tunes them, in shadow, from its own judgments.
- **A second tenant passes every test with no code change:** a fixture company that sells and supports, with different goals, gets sales and support cards with the same anatomy; the same fixture as a founder gets the Founder Office's cards (07 §15.10).

## 2 · Day one: what a new customer sees

| When (from connect) | The screen | Cards |
|---|---|---|
| **Minute 2** | "Connected. Reading your last 30 days first." | none, and no placeholder card |
| **Minute 30** | The count of mails read | none |
| **Minute 35** | "This is how we understand your company": the name, the addresses, the time zone (asked at signup or taken from the browser, for confirmation), what it does, who the founders are; confirm or correct | none |
| **Phase 5** (P1 06) | "We think you are driving toward these": the first goals, each with its target, its evidence and the situations that serve it; confirm, edit or drop each | — |
| **Hour 2 at the latest** | **First intelligence:** "N cards need you", ranked | only the cards that need the founder now, each with its kind, its goal (labelled "proposed" until confirmed), its move and its why |
| **Hour 2** | **The first brief:** at most 3 items, each with its evidence and its coverage (Atlas A.10) | the first day's only interruption (D-P5-17) |
| **Later on day 1** | Wave 2 reading up to 365 days | versions with "what changed and why"; older history as closed rows or reopened versions (like `i6`, `s1`, `s2`) |
| **Day 2, 08:00** | The morning brief: Needs you, Handled without you, Checked and quiet | the normal interruption budget starts |

**Honest progress,** never "Ready" before the first intelligence exists or a reason why there is none (the film; P1 06). Today the screen said "Ready" at 3 h 39 min with 14 old-lane cards, 3 files reviewed and no goal.

## 3 · What happens once, during Onboard

- **Wave 1** (the last 30 days) makes the first cards from judged pages and from the first goals' gaps (07 §2.1). A page whose frame refers to events before the window is at most a question or a "checking" line until wave 2 reads them; a card resting only on the window read is never held back (07 §2.6).
- **Proposed goals organise the first cards:** every card on a goal the founder has not confirmed is labelled "proposed". Confirming a goal removes the label at once; dropping one moves its cards to "Not linked to a goal yet" and re-ranks them; editing one re-judges its linked cards once.
- **Wave 2** (up to 365 days) changes cards only by versioning them, with "what changed and why"; it never hides a card while it re-judges, and it interrupts only when a version raises the lane or the severity (07 §6.4).
- **The first day's interruptions are the brief.** A backfill can raise many cards at once (the ideal's twenty, ages up to seven months); they are all listed and ranked, and none drops on the Mac until day 2's budget, except containment (D-P5-17).
- **No card is dated in UTC:** with the time zone unconfirmed, no card says "today", "now" or "overdue" (07 §4.9).
- **The packs that fit switch on with no hand:** the Founder Office for a founder; Sales and Support only when the company sells or supports; the old rule lanes never raise cards on a founder's mailbox (P1 06; P5-14).

## 4 · Fitting this company, with no prompt and no rule

- **Its own patterns:** "Three updates in 20 days, 0 replies" is counted from its own mail and shown as "yours", with n, beside the domain's pattern (07 §4.7).
- **Its own feedback:** "Not worth a card" with a reason lowers the rank of similar cards for this company, through the company pattern `recommendation_acceptance`; a single click teaches nothing beyond that thread's next review (07 §14).
- **Its own budgets:** L6 proposes per-person changes to the starting budgets from the person's judgments, in shadow; a person arms them (07 §6.3).
- **Its own words:** a correction locks the field it sets; "how we work" becomes an Organisation proposal the owner confirms.

## 5 · The four loops, for every customer's data

| Loop | Cards for a new customer |
|---|---|
| **Onboard** | the first intelligence within 2 hours; proposed labels; the first brief; wave 2's versions |
| **Evolve** | a new mail on a live situation moves its card within 30 minutes for 9 in 10; a date wakes a judgment, never a card; a quiet day costs 0 calls |
| **Act** | every press is a founder act and a wake-up; Done is reported until proof; nothing is sent before approval of the exact bytes |
| **Maintain** | nightly check-in states, waiting cards on their stated dates, predictions scored, the census; weekly roll-ups and usefulness |

## 6 · Teams, more departments, more tools

- **A team:** each seat sees the cards routed to it, with why ("assigned to you", "your responsibility: support"); a card is built for its reader, quote by quote; a shared card has one state; a seat that leaves passes its cards on with the reason (07 §15).
- **A new seat's first screen** shows its cards, or "Nothing for you yet: reading your mail", never an empty frame or the owner's queue.
- **A second mailbox** joins the company's existing situations: one card per situation stays one card, with the new seat's evidence under its visibility (P1-10).
- **A department head** sees the cards of the goals the department owns, grouped by goal, with the seats working each.
- **More departments:** a domain switched on adds cards through the same anatomy; a locked domain is counted in one line, never drawn; a situation spanning a live and a shadow department takes its card from the live one and says "knowledge missing: <department>" (07 §2.2).
- **More tools:** a newly connected tool (chat, documents, a CRM) adds evidence to existing situations through one onboarding wave for that source; a card that now rests on it shows the tool among its sources, and no second card is made.

## 7 · Gaps today, for a new customer

| Gap | What a new customer would get today | Fixed by |
|---|---|---|
| Cards from signals | the old rules' cards on a founder's mailbox, many of them about dates months old | P5-1, P5-14 |
| No goal on any card | every card "not linked"; the goals stuck at proposed | P5-3 |
| No kind, a utility band | about one card in five critical | P5-5 |
| The machine's words | "We held the one we found" and "Needs a decision —" headlines | P5-7 |
| No closing on proof | every card expiring within a week, unread | P5-4 |
| Nothing delivered | no email, no phone; Mac popups in shadow | P5-9 |
| Delegate locked | no hand-over to a person or an agent | P5-8 |
| Owner-only cards | a team member's cards in the owner's queue | P5-10 |
| "Ready" too early | "Ready" at 3 h 39 min with old-lane cards | P5-15, P1-3 |
| A switch by hand | the design partner's brain works because a person switched it on | P5-14, P1 R6 |

## 8 · Ready when

- P1-10's onboarding drill passes on a fresh fixture tenant on the card side: the first cards at 2 hours or before, each with a kind, a proposed goal and a move; no placeholder card; no card dated in UTC; dropping and confirming a goal change the cards at once (P5-15);
- the drill's second seat sees only its own cards, and the private item stays private (P5-10);
- the second-tenant fixture passes every P5 test with no code change;
- the acceptance set holds on the design partner's org: at least 15 of 17 in-copy ideal cards same or close, 0 opposite, at most 30 open, none lost;
- the onboarding report shows the time to first intelligence and the cost within P1's onboarding budget.
