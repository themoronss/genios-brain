# P5 · Cards · 02 · What's failing, and why

"Us" means the AI sessions that built the product and the notebook; "mine" means this notebook's own code. None of these is a misunderstanding by Rohit.

---

## F1 · Three makers, so duplicates and contradictions

- **Evidence:** in the product, cards come from old signal rules (38), old situation rules (33) and the brain (31). A subject repeats up to 9 times. On the accelerator, the rule card "you are 71 days late" stood beside the brain's held answer.
- **Cause:** P1 F1. Every new path added a maker, and none was retired.
- **Whose:** us (architecture).

## F2 · The founder sees the machine's own text

- **Evidence:** 22 brain cards are "held", and about 13 show the checker's internal text ("We held the one we found …"). 6 talk about the founder in the third person.
- **Cause:** a held result was turned into a card instead of staying internal (P2 F1), and the renderer passed internal fields through.
- **Whose:** us (code).

## F3 · No card says which goal it moves

- **Evidence:** 0 of 111 product cards carry a goal. In the notebook, cards carry the page's goal links, but no relation phrase ("through") and no goal-first ordering.
- **Cause:** goals are stuck (P2 F5). In the notebook, goals are only sentences (P2 N1).
- **Whose:** unfinished work.

## F4 · Any date makes a card

- **Evidence:** in the notebook, 19 cards were raised only because an expected-by date had passed, and 4 because one was within a week. **37 of 63** open cards sit on situations whose expected-by date is more than a month old, such as "Overdue: confirm a Monday slot in July". Against the ideal's 20 there are 56 extra cards.
- **Cause:** `nb/cards.py` raises a "clock card" for every passed or near date, whoever owes the move and however stale. There is no lifecycle to put stale work to sleep (P2 N4). The review on 29 Oct confirmed this behaviour as designed and tested; the design was the mistake.
- **Whose:** **mine** (design).

## F5 · No card comes from a goal's missing step

- **Evidence:**
  - `f3`: a referral promised by the intro platform has been silent for 24 days, and no situation's page asks for anything, so there is no card.
  - `i1`: the "one update with today's new fact" exists only when the accelerator goal is seen together with the incubator's milestone.
- **Cause:** cards are raised only from a situation's own page. A goal can't raise a card because it has no plan and no page (P2 N1, P4 F5).
- **Whose:** **mine** (design order: cards before goals, P1 F8).

## F6 · A card that is right in substance, with the wrong lane or tense

- **Evidence:**
  - `f1` became "confirm whether you attended" (the clock, P1 F6);
  - `f4` became a dated deadline card where the ideal says "nothing to do until Monday";
  - `i4` became the numbers-conflict card instead of "which of these still matter".
- **Cause:** the lane is partly the page's choice and partly the clock's rule. Nothing checks the lane against the situation.
- **Whose:** **mine** (cards rule), plus P1 and P4.

## F7 · What the founder does with a card never comes back

- **Evidence:** 211 card events and 133 feedback rows are stored in the product, and nothing reads them back (P2 F6). The Mac app's "Not useful" never reaches the brain. The notebook has no actions at all.
- **Cause:** the Act loop doesn't exist (P1 F5).
- **Whose:** unfinished work.

## F8 · Each screen reads a card its own way

- **Evidence:** the same card looks three ways: in the Cards page (a drawer), in Goals (small cards whose mapper shows a verdict code as "What to do") and in the Mac app (its own reader). The dashboard rebuild that fixes this (`rohit/cards-ux`) was not merged as of 22 Oct.
- **Cause:** each screen was built against its own reading of the card.
- **Whose:** us (front end), with a fix waiting to merge.

---

## Summary

| Failure | Whose | Kind |
|---|---|---|
| F1 three makers | us | architecture |
| F2 machine text shown | us | code |
| F3 no goal on cards | unfinished | depends on P2 |
| F4 any date makes a card | mine | design |
| F5 no card from a goal gap | mine | design order |
| F6 lane and tense | mine | rule, plus P1 and P4 |
| F7 actions never come back | unfinished | Act loop |
| F8 three readers | us | front end, fix not merged |
