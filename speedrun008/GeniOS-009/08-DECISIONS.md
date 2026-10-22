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
| D7 | May GeniOS propose goals it infers? | **yes, as `proposed`, shown for approval; never `active` without a human** | the brief drafter already proposes and the founder accepts — same door | G1 |
| D8 | How are cards grouped on the board? | **by goal, then by lane** (decision · investigation · conflict · monitor); a card with no goal sits under "Not linked to a goal", counted | the document's thesis — the goal organises the work — while never hiding a card | G6 |
