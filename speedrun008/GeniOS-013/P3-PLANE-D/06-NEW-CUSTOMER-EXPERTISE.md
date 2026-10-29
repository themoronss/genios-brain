# P3 · Plane D · 06 · A new customer's expertise

**What this file answers:**
- which knowledge a new customer's GeniOS judges with on day one, and why;
- what is done once for the customer, and what is never done per customer;
- how the knowledge fits this company without anyone editing the corpus;
- how it stays right as the customer's data evolves, through the four loops;
- what changes for teams, other departments and other countries;
- when Plane D is ready for customers beyond the design partner.

The loop that onboards a customer, phase by phase, is P1's Onboard ([P1 06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md) §3). The Notebook it leaves behind is [P2 06](../P2-NOTEBOOK/06-NEW-CUSTOMER-NOTEBOOK.md). This file is about the knowledge.

---

## 1 · The rule that makes Plane D scale

**The corpus is the same for every customer.** It is compiled once per deploy, reviewed once per unit, and tested once per change. Nothing in Plane D is built, edited or reviewed per customer.

What differs per customer is only:
1. **which domains judge** (the activation rows, §2);
2. **what the company's own brains say** (its rules, behaviour and current priorities, §4), which fill the units' adaptation points;
3. **where it is** (its jurisdiction, §5).

So a tenth customer costs Plane D nothing new, and a fix to a unit reaches every customer at the next deploy, after its shadow run.

## 2 · Day one: which knowledge judges

| Kind of customer | Live domains (default rows) | In shadow | Off |
|---|---|---|---|
| **A founder** (the design partner's kind) | The Founder Office and Admin, together, shown as "Admin › Founder office" (D-P3-5). Admin's founder units are selected through the index | — | Sales, Support, and every domain not yet authored |
| **A team with departments** | The Founder Office and Admin, and each department's domain **that has passed the bar** (D-P3-8) | A department whose domain has not yet passed the bar runs in shadow for that tenant: receipts, no cards (P3-21) | Departments the company doesn't have |
| **A department not yet authored** (Finance as its own domain, Projects, Marketing, Product) | — | — | Off. The Expertise page shows it locked, with what it would unlock (the ideal's "Request") |

**No row is made by hand** (P3-17). The kind of customer comes from the signup and the company page (P2 §3.4), and the founder confirms it on the first screen. Today the design partner's Founder Office row was made by hand on 21 Oct; that is what the defaults replace.

**An off domain contributes facts, never judgment.** A support ticket in a founder's mailbox is still read as evidence; it is never judged by the support desk's knowledge.

## 3 · What happens once, during Onboard

| Phase (P1 06 §3) | What Plane D does | Cost |
|---|---|---|
| Company page | Takes the kind of customer, its departments and its jurisdiction from the page (P2 §3.4), for the activation rows and for the units that depend on jurisdiction | $0 |
| Situations and pages | The compiler builds a package for each situation L2 judges (P3-7), pinned to the deploy's pack. Each page records which units it used (P2 §4.7) | $0 in Plane D. The judgments' tokens are P1's onboarding budget: about $10–15 once for a founder with 365 days ([P1 06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md) §4) |
| Brains, first fill | The Organisation brain starts from the company page the founder confirms. The Behaviour brain starts from counts over the backfilled mail (reply times, cadences), each promoted only on enough evidence. The Adaptive brain starts empty, with the first screen's priorities as leases (P2 §8) | $0 (counts by code) |
| Goals | Each proposed goal gets its goal package (07 §4.4): its kind's stage ladder as the plan template, its outcome definitions and its department's measures, pinned to the deploy's packs | $0 in Plane D |
| First screen | The founder confirms the kind of customer and the jurisdiction (P2 §3.4) and states the current priorities, which become Adaptive leases (P1-3). The Expertise page shows which domains judge, which units were used on the customer's mail, and what each locked domain would unlock (P3-20) | $0 |

**Never done per customer:** authoring, reviewing, compiling or testing the corpus.

## 4 · Fitting this company, without editing the corpus

A unit's adaptation points (`facts_required` brain paths, 07 §10) are filled from the company's brains:

| Brain | What it gives a unit | Example | Changed by |
|---|---|---|---|
| **Organisation** | What the company officially requires | Who must approve a vendor renewal; the one verified traction number | Only the founder (P2 §8) |
| **Behaviour** | How the company actually works, counted | This investor usually replies in about five days; this founder answers rejections within a week | Code, promoted only on enough independent evidence |
| **Adaptive** | What matters now | This quarter: the pre-seed round and one accelerator; a snooze until a date | Leases that expire |
| **Persona** | The founder's own preferences, set by the founder | Prefers text, keeps calls short | The founder |

**The precedence when they conflict** is the Atlas's (07 §4.3), applied by Plane R. **When the company's way contradicts a unit,** the contradiction is recorded against the unit (07 §11). A recurring one across companies opens a review item (07 §12). One company's habit never edits the corpus.

## 5 · Where the customer is

- **The jurisdiction comes from the company page** (P2 §3.4): the country, and the state where it matters.
- **Units about law, tax, compliance and programmes** carry `jurisdiction`, `valid_from` and `review_by` (P3-19). The compiler selects only those that hold for the customer.
- **India first.** The corpus already cites Indian sources (startup recognition, the seed fund, programme portals).
- **A customer in another country** gets every general unit and none of India's. The Expertise page says which local knowledge is missing, so nobody mistakes silence for "no obligation".
- **Units past their review date** are labelled, for every customer, until re-reviewed.

## 6 · The four loops, for every customer's data

| Loop | What Plane D does for the customer | What the customer sees |
|---|---|---|
| **Onboard** (once) | The activation rows by kind (§2). A package for every situation judged, pinned to the deploy's pack. The brains' first fill (§3) | The Expertise page: what judges, what was used, what is locked |
| **Evolve** (on every wake-up) | For each situation and goal L2 judges, with or without a model call, the compiler selects the units that apply from every live domain, by kind, stage, qualifier and events, adapted by the brains. The package is pinned per run. When nothing applies, the run says so, makes no recommendation, and the gap is logged | Cards whose trace names the units used, each with its review state; an observation, never a recommendation, where no reviewed knowledge stands behind it |
| **Act** (on every founder act and result) | A verdict is attributed to every unit the card cited and routed by its reason and scope (07 §12): "not how we work" for this kind of work or for the company goes to the company's brains; "wrong rule" or "missing step" becomes a review item; a verified outcome is checked against the unit's outcome definition | The founder's correction takes effect for this company at once, through the brains |
| **Maintain** (nightly and weekly, in the tenant's time zone) | Usage per unit (selected, cited, contradicted, outcomes). Coverage against the 85% target. Units past their review date. A new pack runs in shadow before it goes live, and is rolled back by a pointer if it is worse | The weekly view says which knowledge helped, and which situations ran without any |

## 7 · Teams, more departments, more tools

| Customer | What changes for Plane D | Proved by |
|---|---|---|
| **A team with several mailboxes** | Nothing in the corpus. Situations and their audiences are P2's (P2-10); each judgment still gets one package | P2-10, P3-7 |
| **A team switching on a department** | The department's domain runs in shadow for that tenant, then goes live at the bar | P3-21, D-P3-8 |
| **A department GeniOS has not authored** | Locked (a `coming_next` stub) until its domain is authored, reviewed and passes the bar in shadow on a design partner | D-P3-10, P3-23, 07 §13 |
| **Other tools** (a CRM, a ticket desk, a calendar beyond Google) | New kinds of evidence and events for the index (a deal stage, a ticket opened). Units name the events they speak to; no unit names a vendor's tool unless it is tool knowledge | P2-5, P3-1 |

## 8 · Gaps today, for a new customer

| # | Gap | Fixed by |
|---|---|---|
| D-G1 | The model's paths receive no expertise at all (0 of 138 judgments) | P3-7, P3-8 |
| D-G2 | The founder's domain is unreviewed, so the compiler drops it | P3-4, D-P3-2 |
| D-G3 | Its activation row was made by hand; a new customer gets Admin only | P3-17 |
| D-G4 | The knowledge is generic: the brains are empty for every customer | P3-16, with P2-20 and L6 |
| D-G5 | 5 of the situations and 4 of the rules the ideal stands on do not exist; 4 founder kinds are stubs | P3-10, P3-3 |
| D-G6 | Nothing says where a rule holds; a non-Indian customer would get Indian programme rules | P3-19 |
| D-G7 | Nothing measures whether the knowledge helped a customer | P3-15 |
| D-G8 | A pack change reaches every customer with no shadow run and no rollback | P3-13 |
| D-G9 | No knowledge is selected for a goal | P3-7 (07 §4.4) |
| D-G10 | Several existing situations cannot describe the ideal's cases (a reply that missed the question, a late follow-up, a promise by them) | P3-10 |
| D-G11 | "Nothing applies" cannot be recorded as a package, so a recommendation can be made with no knowledge behind it | P3-7, P3-2 |

## 9 · Ready when

All of these must hold, each checked by a test or a measurement:

0. **The specification is built, not approximated:** every guard D-1 to D-26 (07 §15) passes; every requirement in [08](08-REQUIREMENTS-TRACE.md) is built or explicitly owned elsewhere.
1. **The golden tenant's judgments carry their packages:** 100% of judgments name a package, and coverage by reviewed units is at least 85%.
2. **The ideal cards' knowledge is there and cited:** every unit in 07 §2.2 exists, is reviewed, and is cited by its card on re-judging.
3. **No hand step:** a new test tenant gets its activation rows from its kind, and a non-Indian test tenant gets no Indian units.
4. **Review is closed:** the half-state count is 0, and the Founder Office is reviewed.
5. **Change is safe:** a deliberately worse pack is refused in shadow, and a rollback restores the previous answers on replay.
6. **The brains adapt the units:** a Behaviour brain entry reaches a unit's adaptation point on the copy, and a founder's "not how we work" changes that company's next judgment without editing the corpus.
7. **No recommendation without knowledge:** a run with coverage `none` produces an investigation or an observation, and its gap is logged.
8. **Goals are judged with knowledge:** every goal judgment carries its goal package, and the raise goal reads its progress by the investor stage ladder.
