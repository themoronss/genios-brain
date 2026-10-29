# P5 · Cards · 05 · How it will be done at production level

**Owner:** Harsh and the agents Harsh assigns, for the engine. The dashboard and Mac app owners for the screens. Rohit approves each tenant's activation.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)).

---

## 1 · One card maker

- **Cards come only from pages and goals.** The situation page and the goal page (P2, P4) are the only sources of cards, through one module, `deliver/cards_from_pages.py`. It applies P5-1's four reasons and P5-2's gap cards.
- **The old makers are switched off per tenant** at the parity gate (P1 §4): the legacy signal rules, the old situation rules and the expert pass's file reviews. Until then the founder sees only the old cards, and the new ones are written in shadow.
- **Held results are never cards.** A held change is admission's business (P2). The checker's internal text never reaches a renderer: a test fails if it does.

## 2 · The card record and its contract

- **The card table** gains the ideal's fields:
  - goal, relation and through (`cards.goal_refs` exists, migration 0256);
  - kind (reactive, proactive, predictive, prescriptive);
  - rank;
  - done-when and if-not;
  - sides (for conflicts);
  - quotes with source and date;
  - version.
- **The contract is GeniOS-010/06-CARDS** `02-CARD-DEFINITION.md`, extended with these fields. Every screen reads it, and nothing else.

## 3 · Screens

- **Dashboard:** merge the Cards page rebuild (`rohit/cards-ux`), then add the goal on each card and group by goal (decision → conflict → question → waiting within a goal), with "not linked to a goal" counted.
- **Mac app:** read the same contract. Its "Not useful" goes to the same feedback API as the dashboard.
- **Phone:** a notification for the top-ranked new card, at the founder's local morning hour, never at night.
- **The same card everywhere:** one renderer of the contract, shared, so a card can't look three ways (P5 F8).

## 4 · Delegation and approval

- **Delegate to a person:** the card moves to that person's queue, with the founder still able to see it.
- **Delegate to an agent:** the agent (for example a reply drafter) prepares the draft. **The founder approves before anything is sent.** Through the existing execution path (L4/L5, `delegation.py`): propose → approve → dispatch → result.
- **An agent's "done" counts only as reported,** until the evidence arrives (P1 A3, the check-in states).

## 5 · What the founder does comes back

- Done, Later, Feedback, Answer and Delegate are written to `card_events` and **decisions** (P2 §1) as evidence on the situation. The tenant's Act loop picks them up (P1).
- **Feedback is learning (L6):** "not useful" with its reason lowers the rank of similar cards for this company, through company patterns (P4 §6). It never deletes knowledge.

## 6 · Health

**Per tenant per day:**
- open cards by kind and goal;
- new, updated and closed;
- cards without a goal (counted);
- the founder's actions;
- delegations waiting for approval.

**An alert** fires on:
- any card showing held or internal text;
- a card on a dormant or done situation;
- a surge of new cards (more than twice the tenant's usual day).

## 7 · What must never happen

- **Two cards about one situation.**
- **A card the founder sees with the machine's internal text, or that talks about the founder in the third person.**
- **A card that names no goal and isn't counted as unlinked.**
- **A message sent by an agent without the founder's approval.**
- **A founder's action that changes nothing.**
