# P4 · Plane R · 06 · A new customer's reasoning

**What this file answers:**
- how a new customer's GeniOS thinks on day one, and why the same reasoning serves every customer;
- what is done once for the customer, and what is never done per customer;
- how the reasoning fits this company without anyone writing a prompt or a rule;
- how it stays right as the customer's data evolves, through the four loops;
- what changes for teams, other departments and other tools;
- when Plane R is ready for customers beyond the design partner.

The loop that onboards a customer, phase by phase, is P1's Onboard ([P1 06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md)). The Notebook it leaves behind is [P2 06](../P2-NOTEBOOK/06-NEW-CUSTOMER-NOTEBOOK.md), and the knowledge is [P3 06](../P3-PLANE-D/06-NEW-CUSTOMER-EXPERTISE.md). This file is about the thinking.

---

## 1 · The rule that makes Plane R scale

**The reasoning is the same for every customer.** The fifteen units, the laws, the precedence, the tools and the prompt generator are compiled once per deploy, reviewed once per unit and tested once per change. Nothing in Plane R is written, edited or reviewed per customer, and **no customer gets a prompt of their own**.

What differs per customer is only data:
1. **the company's own patterns** (reply times, stage durations, which moves worked), computed from its pages (07 §12.3);
2. **its brains and its page:** its policies, its decisions, its current priorities, its time zone and working week (P2 §3.4, §8);
3. **its knowledge**, through the domains it has switched on (P3 06);
4. **its model policy and budgets** (07 §14).

So a tenth customer costs Plane R nothing new, and a fix to a unit reaches every customer at the next deploy, after its shadow run.

## 2 · Day one: how a new customer's GeniOS thinks

| What | On day one |
|---|---|
| **The reasoning units** | All fifteen, the same as for every customer |
| **The company's patterns** | None yet. Every dossier says "no company pattern yet" and uses the profession's priors, labelled as priors. A pattern becomes "yours" only from this customer's own data, and "usual" only at 5 or more independent instances |
| **Time** | The company's time zone from the signup; until it is confirmed, every instant says "time zone unconfirmed" and nothing is "today", "now" or "overdue" from UTC alone |
| **The precedence** | The same order. The founder's first-screen priorities arrive as Adaptive leases, which rank 4 (07 §4.2) |
| **Knowledge** | What P3 switches on for this kind of customer; where none is authored, the result is an investigation or an observation, never invented advice |
| **The model** | The default policy row: production parity |

## 3 · What happens once, during Onboard

| Phase (P1 06 §3) | What Plane R does | Cost |
|---|---|---|
| Items placed into pieces of work | P2's continuation places what code can; the placement call (07 §10) places the rest, wave 1 (the last 30 days) first | Inside P1's onboarding budget |
| First pages | One judgment per live situation. While only wave 1 is read, no page concludes anything about before the window ("never contacted", "first approach") | The bulk of the one-time onboarding cost (P1: about $8–9 for a founder with six months of mail, at today's model; up to $15 for 365 days), **once** |
| Goals | Goal proposals at the right grain, at most 10 in the first week; each judged with its goal package; all labelled "proposed" until the founder confirms | Small |
| Wave 2 (up to 365 days) | Older history placed; only the pages it changes are judged again, each with what changed and why. It never holds back a card that rests only on the window read; a wave-1 page whose frame refers to events before the window stays at most an investigation until wave 2 reads them (07 §7.3) | Inside the same budget |
| Company patterns | The first counts, all observe-only ("sparse") | $0 (code) |
| First screen | The founder confirms the kind of customer, the time zone and the current priorities | $0 |

**Never done per customer:** writing a unit, a law, a precedence line or a prompt.

## 4 · Fitting this company, without a prompt or a rule

| Source | What it gives the reasoning | Example | Changed by |
|---|---|---|---|
| **Company patterns** (computed) | This company's own pace beside the profession's prior | "This investor usually replies in about five days (5 of 5)"; "your intro calls are booked the same day" | Code, from the pages |
| **The Organisation brain** | What the company officially requires; rank 2 in the precedence | Who approves a renewal; the one verified number | The founder |
| **The founder's decisions and answers** | Rank 3; a correction is followed, or answered in an inference that cites it | "This portal is the government, not an investor" | The founder |
| **The Adaptive brain** | What matters now; rank 4 | "This quarter: the pre-seed round"; a snooze to a date | Leases that expire |
| **Confirmed preferences** | How the person likes things done | Prefers a call to a mail | The person |

A recurring "your logic doesn't follow" on one unit across companies opens one review item, with counts and redacted structure only, from tenants that opted in (D-P3-13). One company's habit never changes the reasoning for another.

## 5 · The four loops, for every customer's data

| Loop | What Plane R does for the customer | What the customer sees |
|---|---|---|
| **Onboard** (once) | Placement, first pages, goal proposals and their judgments, first company counts (§3) | Situations and goals within about two hours of connecting (P1), each with its reasons |
| **Evolve** (on every wake-up) | The material-change gate first; an exact change by a deterministic unit with no call; a material change by one bounded pass on the page plus only what is new; a goal re-judged when its linked set moves | Cards that name the units, rules and tools they rest on; "nothing to do until <date>" as an answer, not a card |
| **Act** (on every founder act and result) | The act re-enters as evidence; `r.monitoring` checks a reported outcome against its `done_when`; a delegated agent's send is verified only when the sent mail is seen; predictions are scored; "wrong because …" is attributed to the layer and unit | A correction takes effect at the next run; a Done that really happened teaches the next run of that kind of work |
| **Maintain** (nightly and weekly, in the tenant's time) | Nightly counts and candidates with no call; the weekly analyse pass over pages: repeats as one pattern, mistakes, progress per goal, competing goals, company patterns with n | Fewer, sharper cards; one weekly view of what is working and what is not |

## 6 · Teams, more departments, more tools

| Customer | What changes for Plane R | Proved by |
|---|---|---|
| **A team with several mailboxes** | Nothing in the units. Each page is built for its reader: a conclusion is never wider than its evidence, and an absence is never claimed over evidence the reader cannot see (RC-11) | P2-10, P4-5 |
| **A teammate connects a mailbox, or a new tool connects** | An Onboard run for that seat or source: its history is placed into the existing situations with the seat's visibility, only the pages it touches are judged, and the company patterns gain n instead of restarting | P1 06 §7, P4-9 |
| **A correction from a team member** | It applies to that member's files and department; it becomes company-wide only when an owner accepts it, and the dossier shows whose word it is (D-P4-16) | P4-15 |
| **A department switched on** | Its knowledge runs in shadow until it passes P3's bar; the units are the same | P3-21 |
| **A department not yet authored** | Its situations get no recommendation, and the page says which knowledge is missing | RC-10 |
| **Delegation** | The judge proposes who: a team member by department, role and availability (never one on leave before the return date), or an agent with its approver; anything sent is approved first | `r.planning`, RC-13, L4 |
| **Other tools** (a CRM, a ticket desk) | New evidence kinds and events reach the same units; new tools may need new calculators, never new units | P2-5, P4-3 |

## 7 · Gaps today, for a new customer

| # | Gap | Fixed by |
|---|---|---|
| R-G1 | A new tenant gets no judge by default (`l2_reasoning` and `l2_cards` are not default-on) and the old rule lanes, decided by a test-mode model | P4-17, with P1 |
| R-G2 | Every instant is UTC; the company's time zone is never read by the judge | P4-3 |
| R-G3 | Ways of thinking live in prompt copies, so a fix reaches one path and not the others | P4-1, P4-8 |
| R-G4 | Confidence is the model's word; coverage is never measured | P4-3 |
| R-G5 | No company pattern reaches a judgment; a new customer would get none, and nothing labels the priors | P4-7 |
| R-G6 | No goal is judged as a goal; the first-week goals have no plan, progress or next move | P4-4, P4-6 |
| R-G7 | Placement is not a task, so a new customer's mail is grouped by sender | P4-9, with P2 |
| R-G8 | A third of the judge's money buys nothing, and the daily cap starves the rest | P4-13, P4-16 |
| R-G9 | Questions raised to fill a gap are never answered | P4-11 |
| R-G10 | Nothing learns from what happened: no prediction, no outcome loop for the judge's cards | P4-15 |
| R-G11 | A day with nothing new still runs the judge on every bundle | P4-12 |

## 8 · Ready when

All of these must hold, each checked by a test or a measurement:

0. **The specification is built, not approximated:** every guard RG-1 to RG-34 (07 §20) passes; every requirement in [08](08-REQUIREMENTS-TRACE.md) is built or explicitly owned elsewhere.
1. **The golden tenant's cards hold:** at least 15 of 17 in-copy ideal cards same or close, 0 opposite, at most 30 open cards ([10](../10-ACCEPTANCE.md) §5), with one judge making every card.
2. **The goals hold:** at least 8 of 9 in-copy goals proposed with target, plan, progress and next move; health and next move equal to the ideal on at least 7.
3. **No hand step, no hand prompt:** a new test tenant is reasoned for with the default rows; a prompt module with hand rule text fails CI.
4. **Time is local:** a test tenant in another time zone gets every instant in its own time; with the zone unconfirmed, nothing says "today" from UTC.
5. **Change is safe:** a deliberately worse unit is refused in shadow; replaying a day's receipts gives identical results with no model call.
6. **Cost holds:** Evolve under $0.50 a day and Maintain under $1 a week on the golden tenant; the judge's waste under 10%.
7. **A new customer starts clean:** a fresh test tenant shows "no company pattern yet" everywhere and no pattern from another tenant.
8. **Learning is safe:** a "your logic doesn't follow" verdict opens a review item on the units used, and the library's hash is unchanged.
