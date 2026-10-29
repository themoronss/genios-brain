# P5 · Cards (the intelligence) · 01 · What's exactly there

**The part:** what reaches a person:
- **when** intelligence is raised: the founder is needed, a goal has a missing step, or a date of our own is near;
- **what** it says: what to do and why, for which goal, by when, how we'll know it's done, the evidence;
- **which** of the four kinds it is: reactive, proactive, predictive, prescriptive;
- how it is versioned, ranked, limited and closed;
- what a person can do with it: Done, Delegate (to a person or an agent), Later, Feedback, Answer.

Cards never judge the situation behind them. That is P4.

**Read at:** `speedrun008` `71c50f56`, the dashboard's GeniOS-010 Cards work, and the notebook.

---

## 1 · In the product

### Who makes cards: three makers in one sweep (measured 28 Oct, [01](../01-WHAT-IS-HAPPENING.md) stage 9)

| Maker | Live cards |
|---|---|
| Old signal rules (legacy pack lanes) | 38 |
| Old situation rules (compiled lane) | 33 |
| The brain (expert pass, `expert.file_review`), **22 of them "held"** | 31 |
| Other | 1 |

On top of that:
- the same subject repeats up to **9 times**;
- about **13** cards show the checker's internal text ("We held the one we found …");
- **6** name the founder in the third person;
- **0 of 111** cards carry a goal (`cards.goal_refs`).

### What a card holds and how it lives

- The engine sends 17 fields per card. Their lifecycle is in `platform/card_lifecycle.py`; `expire_lapsed` is the cron's half.
- The founder's actions are stored: `card_events` 211, `card_feedback_verdicts` 3, `moment_feedback` 133. No reasoning step reads them back (P2 F6).

### Where a card is shown

- **The dashboard's Cards page.** GeniOS-010/06-CARDS rebuilt it on the branch `rohit/cards-ux`, which was not merged as of 22 Oct:
  - cards grouped by what each asks (decide · two sources disagree · answer · waiting);
  - a side panel in Rohit's order: subject + two lines → recommendation → what, why, how → what doing it gets you → **goal** → deadline → details → where the data came from;
  - buttons: Done · **Delegate** (a person or an agent) · Later (with a day you pick) · Feedback · Answer;
  - question cards can be answered.
- **The Mac app** has its own reader. Its "Not useful" never reaches the brain.
- **The phone:** a notification, as the film shows.
- **Delegation:** in the film, "Handed to Reply Drafter, you approve before anything is sent".

## 2 · The card the ideal dashboard shows (the target's anatomy)

From the ideal file and the film's "Intelligence on this goal" panel:

| Field | What it is |
|---|---|
| number | The goal's code plus a count ("G-… · C01"); a card with no goal gets its own code |
| goal, relation, through | The goal it moves, how (advances / threatens / depends on / unclear), and through what step. Plus any other goals it touches |
| lane | Decision, conflict, question or waiting |
| urgency, age, version | Critical / high / standard; how old it is; the same situation keeps the same card in a new version |
| headline | Verb first, specific |
| summary | Two lines of the situation |
| why now | One line |
| recommendation, steps | One sentence; at most 4 steps |
| who, by | Who acts, by when |
| sides | For a conflict: each side with its source and date |
| quotes | Verbatim, each with tool, sender and date |
| done when, if not | How we'll know it's done; what happens if it isn't |
| confidence | Evidence, frame, timing, cause, authority, coverage |
| tools | The sources it was read from |

## 3 · In the notebook

- **When a card is raised** (`nb/cards.py`, `card_for`): when the page says the founder is needed, **or** when the page's expected-by date has passed, **or** when that date is within 7 days. The work must be live (not noise, done, dropped or merged).
- **The lane** comes from the page, or from the clock: a date within the week makes a deadline card; a date passed makes a decision or question card.
- **Each situation has at most one card.** A changed card gets a new version; an unchanged one keeps its version. A card closes when its situation is done, dropped, noise or merged.
- **The body:** title, kind, status, stage, whose move and since when, summary, why now, recommendation, steps, draft, quotes, question and options, next expected, importance, goal links, why it was raised.

**Measured on `b2`:** 63 open cards (decision 12, question 24, deadline 8, waiting 17, conflict 2), raised for these reasons:

| Raised because | Cards |
|---|---|
| The page says the founder is needed | 40 |
| An expected-by date has passed | 19 |
| A date is within a week | 4 |

**37 of the 63 sit on situations whose expected-by date is more than a month old.** Of the ideal's 17 in-copy cards:
- 8 have a notebook card on the same situation;
- 9 have the situation but no card;
- 56 open cards answer none of the ideal's cards.

**The comparison page** (`nb/compare.py`, `output/b2/compare.html`) shows Claude's ideal and the notebook side by side. For each card it adds what live GeniOS showed before and a hand-written read. It is local only: it holds real mail.
