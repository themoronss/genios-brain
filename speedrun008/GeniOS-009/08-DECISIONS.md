# 08 · Decisions — asked once, each with a default

**Written for:** Rohit.

A question that is not answered takes its default (GeniOS-008 `01-RULES`: "questions asked once").
Rohit's answer replaces the default here, with the date, and the change is logged in [`03-LOG.md`](03-LOG.md).

| # | Question | Default | Why the default | Blocks |
|---|---|---|---|---|
| D1 | What is a "department" for a tenant? | **the live domain** (today Admin + Founder Office for Rohit's org) | the router already knows the domains per tenant (`platform/l3_activation`); a separate department table would be a second truth | G1, G6 |
| D2 | Where does a goal live? | **L3 holds the goal object** (`company_goals`); Plane D's organisation brain reads a pinned copy at compile time | the goal changes and is linked to situations — that is L3's job; the brain must stay hash-pinned per run | G1 |
| D3 | Persona brain (individual preferences) | **later** — not in this folder's scope | not in the Atlas; it needs a consent and visibility model first | — |
| D4 | What counts as recovered value in `macv_ledger` (the North Star)? | **no writer until Rohit decides**; G9 writes goal progress, not money value | a product definition ("distinct-deal SUM + non-deal COUNT") nobody has specified in code | G9 (value part only) |
| D5 | Order | **G0 first** (CI green → `l2_cards` on one tenant → admission gates one type), then G1→G9 | a goal link on top of a red head or a shadow-only card path cannot be judged | all |
| D6 | Which tenant gets `l2_cards` first? | **Rohit's own org** (Admin + Founder Office live) | it is the design-partner org and the golden set is built from founder cases | G0.2 |
| D7 | May GeniOS propose goals it infers? | **Rohit, 23 Oct 2026: yes. Two sources propose: the brief drafter (weekly, built; it reads the work in motion since GeniOS-011 S27.U1) and the L2 judgment (R-9, G3.5 → G4.5).** Each proposal is `proposed`, shown for approval, never `active` without a human | Rohit, 23 Oct, in chat: *"aise bar bar goals manually nhi dal sakte na"* (we cannot keep adding goals by hand); the Antler Singapore admission should have become a goal from the context already in the graph. The drafter alone never reads one subject's whole dossier | G1, G1.6, G3.5, G4.5 |
| D8 | How are cards grouped on the board? | **by goal, then by lane** (decision · investigation · conflict · monitor); a card with no goal sits under "Not linked to a goal", counted | the document's thesis — the goal organises the work — while never hiding a card | G6 |
| D9 | May the L2 judgment propose goals? | **Rohit, 23 Oct 2026: yes**, as a `GoalProposal` that L3 admits as a pending brief line (`00-ARCHITECTURE` Goals) | Rohit's words under D7 | G3.5, G4.5 |
| D10 | At what grain? | **one goal per piece of work** (an application, one raise, one hire, one partner). A broad goal stays; a goal for one piece of work may name a live broad goal as its parent (`parent_goal_id`), never required | Rohit's Antler case is one piece of work. Default from GeniOS-011 `06-DECISIONS` (`goals-decision-goal-granularity-and-door`) | G1.6, G3.5 |
| D11 | Through which door? | **the company brief's proposal door**: a pending `goals` line, accepted in one click on `POST /v1/company-brief/proposals/{line_id}/decide`; the structured fields ride on the line (G1.6) and `sync_from_brief` copies them to `company_goals` | one door and one approval path, as G1 §2.1 already designs; the door GeniOS-011 S26.U1 records with Rohit's decision (23 Oct). GeniOS-011 `06` had recommended `company_goals` direct with `POST /v1/goals/{id}/approve`; that option is not taken | G1.6, G4.5, G6.8 |
| D12 | A cap on new proposals? | **3 a week per tenant from the L2 judgment**; the drafter keeps its own bound (`MAX_PER_SECTION = 8` lines per section per weekly draft, `reason/brief_drafter.py:49`) | the recommended default; nothing else bounds an L2 proposer | G4.5 |
