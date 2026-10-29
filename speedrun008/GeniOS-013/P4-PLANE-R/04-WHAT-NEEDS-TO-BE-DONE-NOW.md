# P4 · Plane R · 04 · What needs to be done now

Proved in the notebook first. A step is done only when:
- its tests pass;
- its done-when holds;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing worse.

The principle is Rohit's own: **the model is the expert; code is memory, calculator and checker; patterns, not rigid rules.**

---

## Decisions for Rohit

| # | Question | Recommendation |
|---|---|---|
| D-P4-1 | **Where do reasoning patterns live?** | In a written library, `Plane R/patterns/`. Each pattern has the same shape as Plane D's rules of thumb: statement, why, applies when, breaks down when, failure modes, sources, review state. Never in prompt text |
| D-P4-2 | **What wins when two things disagree?** | 1 the founder's own word and decisions → 2 what the mail states (dates, asks, answers) → 3 a rule's conditions → 4 the rule → 5 typical durations (priors) → 6 the model's general knowledge. "The playbook is a prior", everywhere |
| D-P4-3 | **Does the model do arithmetic?** | No. Calculators print time since, whose turn, due dates in the company's time, counts and gaps, each with a citable id |
| D-P4-4 | **How is a goal's status set?** | By rule in code, from facts (the rule below). The model writes only the reason line |
| D-P4-5 | **Must every conclusion say which pattern it used?** | Yes: the ids of the patterns and expertise it relied on. Code checks each one's conditions where it can |

## The first patterns (D-P4-1)

These are taken from what already exists: the product's rules, the notebook's prompt lines, Plane D's cross-domain rules, and the ideal's reasoning. Each gets its conditions and two golden cases before it is used.

| Pattern | Applies when | Breaks down when |
|---|---|---|
| **Whose move is it** | Always | A third party (a platform, an assistant) holds the move |
| **The follow-up after any meeting is ours** | A call or meeting happened with someone outside | They wrote first after it, or a next step and date were agreed in writing |
| **An answer must answer** | They asked a specific question | The reply gives what was asked (a projection is not the current number) |
| **Silence counts only if the source was read** | Judging an absence | The source was cut, archived or not connected |
| **Unknown is not zero** | Progress, counts | A count exists |
| **A renewal or charge is a decision** | Something we pay for renews or charges within 7 days | Already decided in writing |
| **Three unanswered messages is a decision** | We sent three or more with no reply | They replied, or a stated date is still ahead |
| **A new, checkable fact before re-contact** | Re-contacting someone who went quiet after our updates | They asked for something specific |
| **A pass is a date, not a verdict** | A rejection on timing, stage or traction | A thesis or team pass |
| **A promise is kept only by a later delivery** | Our or their promise | The promise was released or superseded |
| **One blocker for many goals goes first** | One open item blocks two or more goals | Each goal has another path |
| **Same situation, same card** | Raising a card | Never |

## Steps

### P4-1 · The pattern library
- **What:** the patterns above, written as items with ids, conditions, sources and review state. They are loaded like Plane D's items, and selected per situation by the same index (P3-1).
- **Test:** each pattern's two golden cases, one where it must apply and one where it must not.
- **Done when:** all patterns pass their cases, and the judge prompt holds **no** rule text of its own, only the selected items.

### P4-2 · Precedence, written and enforced
- **What:** D-P4-2 goes into the prompt's frame, as one ordered list. Where code can see the conflict, it checks it: a rule cited against a stated date in the mail is noted, and the stated date wins.
- **Done when:** on re-judging, `i2` and `i3` match the ideal, together with P3-2.

### P4-3 · The calculators
- **What:** port the product's tool gateway (`reason/l2/tools.py`) to the notebook and extend it. It prints, with tool ids:
  - time since the last mail each way, in the company's time zone;
  - **whose turn it is**, from the last ask and the last answer;
  - the nearest stated date and whether it has passed;
  - how many of their messages wait behind our last one;
  - quiet against this counterparty's usual reply time;
  - days in the current stage, ours beside the playbook's prior;
  - the counts a goal needs (applications live, intros answered, offers).
- **Done when:** `f1` (the clock) and `b3` (whose turn) are re-judged as the ideal calls them, and every number on a page cites a tool or a quote.

### P4-4 · A goal's status and progress, in code
- **Progress:**
  - an outcome counted against the target (nothing committed of the round's target; 0 of 1 engineer);
  - or verified plan steps;
  - otherwise **unknown, with the reason**.

  Activity counts (intros booked, mails sent) are shown as words, never as a percentage.
- **Status:**
  - **blocked:** progress can't be measured **and** the next step needs a missing source or the founder's decision;
  - **on track:** measured ≥ 50% (or steps on pace) **and** nothing we owe is more than 2 days late;
  - **at risk:** everything else.
- **Test:** the ideal's 9 in-copy goals, as fixtures, produce the ideal's status, or a written reason for the difference.
- **Done when:** the fixtures pass and the rule's tests and mutation check are green.

### P4-5 · Citations and checks
- **What:** each page lists the ids of the patterns and expertise it used, beside its evidence ids. Code checks the conditions it can see:
  - "silence reads by stage" cited while the whose-turn tool says it's ours → **held**;
  - "answered" while the reply lacks what was asked → a note;
  - "the follow-up is ours" cited with no meeting in the dossier → **held**.
- **Done when:** these checks exist with tests, and a deliberately wrong page is held with the right reason.

### P4-6 · Reasoning about goals
- **What:** one judgment per goal. Its dossier holds:
  - the goal's captured moment;
  - its situations' pages (status, whose move, next expected, open items, cards);
  - **news from the same goal** (P2-6);
  - the expertise and patterns selected.

  It writes the goal page (P2-1): target, plan, scenario, next move (from its own cards), gaps. Where a "doing" plan step has no card behind it, it raises a **gap card** anchored to a real situation and mail (P5-2).
- **Done when:**
  - status and next move equal the ideal on **at least 7 of 9** in-copy goals;
  - `i1` comes back as "one update with the new milestone, then stop";
  - `f3` comes back as "ask about the referral".

### P4-7 · Patterns across pages: correlate and analyse
- **What:** a weekly pass over the pages, not the mail. It finds:
  - repeats ("15 follow-ups after calls never sent" becomes one pattern card, and the 15 situations stay quiet);
  - mistakes (numbers told two ways, bounces, broken promises);
  - progress and performance per goal (trends, reply times, intros → calls → partners).

  It writes **company patterns** (this company's usual reply times, which moves worked) as priors marked "yours", beside the playbook's.
- **Done when:** the follow-up repeats become one card, and a weekly summary reads well to Rohit.

### P4-8 · One prompt per task, built from the library
- **What:** the situation judge, the goal judge and the analyse pass each get one prompt. Each is built from:
  - the role;
  - the order of judging;
  - the precedence;
  - the selected patterns and expertise;
  - the calculators;
  - the dossier.

  No rule text is written by hand into a prompt. Any new field in an answer is probed against the API's grammar limit first (a failed probe costs nothing).
- **Done when:** the three prompts are generated, and a test fails if a prompt holds rule text that isn't in the library.

## Order and dependencies

```
P4-1 patterns ─► P4-2 precedence ─┐
P4-3 calculators ─────────────────┼─► P4-5 citations and checks ─► re-judge (i2, i3, f1, b3, b2, c2)
(P3-1 index, P3-2 render) ────────┘
P4-4 goal state ─► P4-6 goal reasoning (needs P2-1, P2-2, P2-6) ─► i1, f3 and gap cards (P5-2)
P4-7 correlate and analyse (needs P1-6 maintain)
P4-8 throughout
```
