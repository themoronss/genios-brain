# P5 · Cards · 04 · What needs to be done now

Proved in the notebook first. A step is done only when:
- its tests pass;
- its done-when holds;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing worse.

---

## Decisions for Rohit

| # | Question | Recommendation |
|---|---|---|
| D-P5-1 | **When is a card raised?** | Four reasons only: (1) the page says a person is needed now (a decision only they can make, a conflict, a fact only they know, our own deadline within 7 days, something we owe that is due or late); (2) a goal's plan step has nobody working it (a gap card); (3) a **stated** deadline of ours is near; (4) a promise **we** made is late. A date alone, on something **they** owe, makes no card: it wakes the situation (P1) |
| D-P5-2 | **How many cards at once?** | No fixed cap. Rank them by the goal's status (blocked, at risk), the deadline, the stakes, and whether we owe it. Show the top ones; the rest sit in "later" with a count, never hidden |
| D-P5-3 | **The four kinds** | Show each card's kind: **reactive** (something happened), **proactive** (something should happen and hasn't), **predictive** (something will go wrong if nothing changes), **prescriptive** (the next move to reach a goal) |
| D-P5-4 | **Delegation** | Delegate to a person or an agent. An agent drafts and a person approves before anything is sent (the film's "you approve before anything is sent") |

## Steps

### P5-1 · Raise cards only for the four reasons
- **What:** rewrite `card_for` to raise cards only for D-P5-1's four reasons. A card can't stand on a dormant, done or history situation (P2-3). A "they owe" date makes no card; it becomes a wake-up (P1-4).
- **Test:**
  - a stale July "confirm a slot" card is not raised;
  - our own deadline tomorrow is raised;
  - their reply overdue wakes the situation, and makes no card.
- **Done when:** open cards are at most 30 (from 63), **with every in-copy ideal card that was raised still raised**.

### P5-2 · Gap cards from goals
- **What:** when a goal's "doing" step has no card behind it (P4-6), the goal raises one, anchored to a real situation and a real mail. Examples: the referral that is 24 days silent (`f3`); the update carrying today's milestone (`i1`). The same situation keeps the same card.
- **Done when:** `f3` and `i1` come back as cards that match the ideal, and no gap card exists without a printed anchor.

### P5-3 · Every card names its goal
- **What:** each card shows its main goal, how it moves it (advances / threatens / depends on / unclear), the "through" phrase from P2-2, and its other goals. A card with no goal says so, and is counted.
- **Done when:** every open card has a goal or is counted as "not linked to a goal", and the comparison page shows the card × goal grid.

### P5-4 · Done-when and if-not
- **What:** each card says how we'll know it's done: their reply, a document, a meeting held, a status on a portal, a payment, or the founder's word. It also says what happens if it isn't done. These drive the check-in states (P1-5, A2/A3).
- **Done when:** every open card has a done-when, and a test closes a card when its evidence arrives.

### P5-5 · The four kinds, and a rank
- **What:** each card has its kind (D-P5-3) and a rank (D-P5-2). The comparison page orders by rank within each goal.
- **Done when:** the top 10 cards on `b2`'s rebuild include the ideal's critical and high cards (`p1`, `f1`, `i1`, `i3`, `c1`).

### P5-6 · What the founder does comes back
- **What:** Done, Delegate (a person or an agent), Later (with a date), Feedback (good or bad, with a reason) and Answer are recorded as evidence on the situation (P2-7) and wake it (P1-5).
  - A delegated agent's draft waits for the founder's approval.
  - "Not useful" changes how similar cards are ranked for this company (P4-7, company patterns).
- **Done when:** in the replay, each action moves its situation, and its goal where it should.

### P5-7 · The comparison page shows goals the ideal's way
- **What:** `nb/compare.py` gains a goals view for each goal:
  - target, status, progress (or "?"), plan and next move;
  - its cards;
  - the card × goal grid;
  - the before (live product) and after (notebook) lines;
  - the hand reads.
- **Done when:** the page shows all of it for the rebuilt build.

## Order and dependencies

```
(P2-3 lifecycle) ─► P5-1 four reasons ─► P5-5 kinds and rank
(P4-6 goal reasoning) ─► P5-2 gap cards
(P2-2 one link set) ─► P5-3 goal on every card ─► P5-7 comparison page
P5-4 done-when ─► (P1-5 act) ─► P5-6 actions come back
```
