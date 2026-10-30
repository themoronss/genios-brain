# P5 · Cards · 02 · What's failing, and why

"Us" means the AI sessions that built the product and the notebook; "mine" means this notebook's own code. None of these is a misunderstanding by Rohit. The numbers are [01](01-WHATS-EXACTLY-THERE.md)'s; the fix for each is in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).

---

## F1 · Cards come from signals, through six writers, not from judgments

- **Evidence:** one card for every open signal that passes L4's authority predicate (`deliver/pipeline.py:52-135`); six writers feed it (legacy rules 41, the compiled lane 36, the L2 path 33, the team emitter 1); 73 of the 77 unit-lane cards were decided by the test-mode decider, outside the model register (3,695 calls in a week). One counterparty owns 25 to 31 of the 111 cards; 9 cards sit on 9 condition nodes of one company.
- **Cause:** every new path added a writer and none was retired (P1 F1). The `cards_from_situations` switch was meant to change the source and only relabels a counter (`pipeline.py:900-902`).
- **Whose:** us (architecture).

## F2 · No rule says when a person is needed

- **Evidence:** there is no card-level "is a person needed" rule in the product: a signal is enough. In the notebook, 23 of 63 cards come from dates alone, 17 of them on our move and 6 on theirs; 52 of 63 rest on a date more than 30 days old; 30 of 36 product cards resting on a commitment's due date were raised more than 30 days after it (median 114 days).
- **Cause:** in the product, the card is a view over whatever signals exist. In the notebook, `nb/cards.py` raises a "clock card" for every passed or near date, whoever owes the move and however stale; there is no lifecycle to put stale work to sleep (P2 N4). The 29 Oct review confirmed this behaviour as designed; the design was the mistake.
- **Whose:** us (product); **mine** (notebook design).

## F3 · The lane is decided twice, and the wrong one wins

- **Evidence:** the card's lane comes from `output_lane.route` at three deciders; L2's lane, computed from the judgment, reaches the card only as a hold. They agree on 16 of 33 judged cards; L2 said "conflict" on 23 results, while 1 card is a conflict. The card builder then downgrades cards with its own gates (`card_builder.py:1200-1302`). In the notebook, only 2 of 8 matched pairs share the ideal's lane; its "waiting" means the opposite of the ideal's, and it has a "deadline" lane the ideal does not.
- **Cause:** the card layer kept a lane function of its own after L2 began to judge, and the card builder judges as well as builds.
- **Whose:** us (product); **mine** (notebook lanes).

## F4 · The person sees the machine's own words

- **Evidence:** "What is the next step with <them>? We held the one we found: <why>." on 13 open question cards (`reason/expert/verify.py:812`); 40 headlines start "Needs a decision —"; 20 L2 headlines are over 90 characters and cut mid-sentence; 77 cards carry a template consequence, 33 of which print an internal key (`dependency_stated`); `success_signal` holds codes (`commitment_met`); the Mac app draws ": undefined"; the Goals page shows verdict codes (`review_source`) as "What to do".
- **Cause:** the held-file question was written in engineer's words; the lane was put into the headline as a prefix; stock sentences and codes from plays and capabilities were passed through; each screen built its own text.
- **Whose:** us (code).

## F5 · The person is spoken of in the third person

- **Evidence:** 23 product cards name the founder by first name in the headline, situation or why-now (9 in the headline); 19 draft bodies do; in `b2`, 17 of 63 cards say "the founder", although the judge is told to say "you".
- **Cause:** the prompts and the gold lines refer to the founder as a party; the contract's "us" rule refuses only a card that names the tenant as subject or recipient, and nothing renders the reader's own party as "you".
- **Whose:** us (prompts and contract); **mine** (notebook prompt).

## F6 · No card says which goal it moves

- **Evidence:** 0 of 111 product cards carry a goal; 11 goals exist, all proposed, with 0 links; `goal_refs` is refreshed from approved goals only; no screen reads it; the Cards page hard-codes "Not linked to a goal yet"; the Goals page lists every card as unlinked, numbers cards by position, and hides 14 of 65 visible cards as a "locked domain". In the notebook, cards carry the page's goal links (55 of 63) but no "through" phrase and no primary goal; 40 cards link one broad activity goal.
- **Cause:** goals are stuck at proposed, and the card layer shows only approved ones (P2 F5); the screens were built before the brain served the goal; in the notebook, goals are only sentences (P2 N1).
- **Whose:** unfinished work.

## F7 · No goal raises a card

- **Evidence:** `f3` (a referral the intro platform promised, silent for 24 days) has no card in the notebook, because its pile's page said "not needed"; `i1`'s "one update with today's new fact" exists only when the accelerator goal is seen together with the incubator's milestone; no "goal reached, confirm" card exists anywhere.
- **Cause:** cards are raised only from a situation's own page; a goal has no plan and no page that can raise one (P2 N1, P4 F5).
- **Whose:** **mine** (design order: cards before goals, P1 F8).

## F8 · No kind, no real severity, no real rank

- **Evidence:** no kind is stored; the urgency band is a utility score cut at 70 and 85, so 22 of 103 open cards are critical and the stored bands overlap; all 24 question cards are written at score 0, rank last and are never pushed; legacy and compiled cards (score 38 to 72) outrank the 9 expert decisions; 20 critical "pushes" in 7 days, against the Atlas's start of about 1 critical a week. The notebook has no severity and no rank beyond an export order.
- **Cause:** severity was taken from the decision maker's utility instead of from stakes and time; the question lane was given a literal score of 0.
- **Whose:** us (code); **mine** (notebook).

## F9 · Done is a click, and nothing closes on proof

- **Evidence:** 0 cards resolved in the week; `success_signal` is a play's text or a code; verified closing exists for one path only; every open card expires within a week because the card window is cut to the decision's 168-hour authority window, while the builder's comment says cards "effectively never" expire; Done marks a card acted at once, and an agent's "done" does the same. The notebook has no done-when, no "if not", no closing reason (a card closes when a run stops producing it).
- **Cause:** the living card was built around the founder's press, not the outcome's evidence; the authority window of the decision was reused as the card's clock.
- **Whose:** us (code); **mine** (notebook).

## F10 · What a person can do is fragmentary, and some of it fails silently

- **Evidence:** Done is offered on 34 of 103 open cards, and 33 of 64 decision cards offer only Later and Feedback; Delegate is drawn on every card and locked, waiting for a route that does not exist while the real one goes unused; the Mac app's "Not useful" is refused (no reason) and the refusal is swallowed; Done on a question card is refused and swallowed the same way; there is no "this is right"; 3 presses in a week, all Done.
- **Cause:** the card's actions follow the old plays (a card without a play has no Done); the Delegate screen was built against an imagined route; the shipped Mac app does not check responses.
- **Whose:** us (code and front end).

## F11 · Delegation and approval are built, and wired to nothing

- **Evidence:** `/v1/delegations` with frozen bytes and a 24-hour approval exists, with 0 agents and 0 delegations; 59 open cards carry a draft that no screen shows; `approval_routes.enqueue` has no caller; `push_card_to_agents` is wired to nothing; what an agent would receive lacks the Atlas's task contract (intent, goal, `may`, `may_not`, done-when, `verified_by`); an agent's report is taken as the outcome.
- **Cause:** the agent lane was built ahead of the card's Delegate action and of any registered agent.
- **Whose:** unfinished work.

## F12 · Nothing reaches the person outside the app

- **Evidence:** 0 outbox rows ever; the org has only `in_app`; email has no transport; there is no phone push code; every one of 526 moments is stored as shadow; "pushed" means a state flip; the timing, gate and rate-limit code is built and never used on a delivery.
- **Cause:** the delivery stack was built and tested in isolation, and the switch to a real channel was never made.
- **Whose:** unfinished work.

## F13 · Each screen reads a card its own way

- **Evidence:** about ten button sets across the shipped screens; the Goals page's own mapper and the Mac app's own reader; the version tag counts the wrong event and never shows; the lane is lost past the 40th card; 38 open cards are withheld from the app queue; the `agent` surface is never set because `card_builder.py:779` reads `action` instead of `type`.
- **Cause:** each screen was built against its own reading of the card; one reader exists (`card-read.ts`) and only the Cards page and the dummy use it.
- **Whose:** us (front end and code).

## F14 · No trace and no why-not on the card

- **Evidence:** the card's `why` is a list of field names and values (894 entries); quotes on 8 of 111 cards; no trace id; no per-card why-not; the 5,837 suppression rows are all from legacy rules and use a list of their own; "why no card" is computed at read for one file.
- **Cause:** the card predates the receipts of L2, and the suppression log predates the Atlas's why-not list.
- **Whose:** us (code).

## F15 · The card writer is built, and off

- **Evidence:** R-10 (`deliver/card_copy.py`) writes a cited, fact-checked face for each new version, at most $0.02 a call; `copy` is on 0 of 111 cards; the feature is not switched on for this org; no screen reads `copy`.
- **Cause:** it waited on the screens, and the screens waited on it.
- **Whose:** unfinished work.

## F16 · No card is for anyone but the owner

- **Evidence:** all 111 cards are assigned to the owner's seat; `card_recipients` has 0 rows; no audience is shown; the routing and visibility code (`deliver/router.py`, `seat_access.py`) exists.
- **Cause:** one seat in the design partner's org; nothing has exercised the team path.
- **Whose:** unfinished work.

## F17 · Nothing measures whether a card helped

- **Evidence:** no resolved card; no verified execution outcome; AER is a hard-coded 0 and HIR shows only in sample mode; the bell shows sample notices; the Cards page's counts are computed in the browser.
- **Cause:** the outcome side of the card (F9) does not exist, so there is nothing to count.
- **Whose:** unfinished work.

---

## Summary

| Failure | Whose | Kind |
|---|---|---|
| F1 six writers, cards from signals | us | architecture |
| F2 no "a person is needed" rule; date cards | us; mine | design |
| F3 the lane decided twice | us; mine | code |
| F4 the machine's words | us | code |
| F5 the third person | us; mine | prompts and contract |
| F6 no goal on cards | unfinished | depends on P2 |
| F7 no card from a goal | mine | design order |
| F8 no kind, severity or rank | us; mine | code |
| F9 no closing on proof; a week's clock | us; mine | code |
| F10 fragmentary actions, silent failures | us | code and front end |
| F11 delegation wired to nothing | unfinished | agent lane |
| F12 nothing delivered | unfinished | channels |
| F13 one card, many readers | us | front end |
| F14 no trace, no why-not | us | code |
| F15 the card writer off | unfinished | switch |
| F16 owner-only cards | unfinished | team path |
| F17 no outcome measures | unfinished | depends on F9 |
