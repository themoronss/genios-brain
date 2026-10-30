# 10 · The acceptance set: how every part knows it worked

**Written for:** everyone who builds or checks GeniOS.
**Rule:** every step in every part runs this set before and after, and writes the numbers in [08-LOG](08-LOG.md). A step that makes any line worse is not done, however green its own tests are.
**Measured on:**
- the local copy of the design partner's org (cut from production on 28 Oct, 12:45 UTC);
- the notebook build `b2`, which knows the mailbox as of **23 Oct 2026, 01:40 UTC (07:10 IST)**, the morning the ideal dashboard was written.

**No names:** cases go by their ids in the private ideal file. The private notebook folder holds the mapping to real threads.

---

## 1 · The 20 ideal cards

The mail copy starts on 25 Apr, so 17 of the 20 can be seen; `i6`, `s1` and `s2` are older. For each card the table gives:
- the call GeniOS must make;
- what the live product does today ([01](01-WHAT-IS-HAPPENING.md) §7);
- what the notebook `b2` does today (hand reads in the private `notes.json`);
- the part that owns the fix.

| Id | The call GeniOS must make | Live product today | Notebook `b2` today | Fix owned by |
|---|---|---|---|---|
| `p1` | Four different traction numbers went to different people: pick one verified number before today's review | Lost: numbers stored as plain amounts, never compared | ✅ Same call (raised twice) | P4, P5 |
| `f1` | The incubator's final review is today: join early, lead with one number | Card points the wrong way | 🟡 Close: read 07:10 IST as "the panel is now", asked "did you attend?" | P1 (clock), P4 |
| `f2` | An application is incomplete: finish it or drop it this week | Its reminders were archived | ✅ Same call | P2 |
| `f3` | A scout's referral promised by the intro platform is silent after 24 days: ask about it | The intro platform's file is too big to judge | ❌ Missed: buried among 30 intro offers | P2, P4, P5 |
| `f4` | Waiting on a founder's review of the application doc: nothing to do until Monday | Held by the checker | 🟡 Close: a dated card where none was needed | P5 |
| `i1` | **The film's example.** Accelerator reconsideration: one update with a new, checkable fact, then stop | Right reading held; old rule card says "71 days late" | ↔️ Opposite: "stop, wait for the next intake" | P4, P2, P5 |
| `i2` | An investor asked for current traction and got a projection: answer in three lines | Dormant, never judged | ❌ Missed: counted as answered | P4 |
| `i3` | The follow-up after an investor call was never sent: send it today | Held | ❌ Missed: the playbook's "silence = soft no" won | P3, P4 |
| `i4` | One update went to 12 investors with no replies in 10 weeks: which still matter? | Partly, late | ◐ Partly: became the numbers-conflict card | P4, P5 |
| `i5` | Six mails never arrived, three of them to investors: resend to working addresses | The bounce stays on the address | ◐ Partly: card covers only the registration complaint | P4, P5 |
| `b1` | Two new introductions are waiting for a yes or no | One held, one never judged | ◐ Partly: one has a card | P2, P5 |
| `b2` | Two partner calls, no written next step: send the collaboration note | The brain chose a decision; no card was made | ❌ Missed: marked "done" | P3, P4 |
| `b3` | A stalled introduction: the ball is in their court, let it close | Dormant, never judged | ↔️ Opposite: "you owe them times" | P4 |
| `c1` | A registration complaint reached only one inbox: call the helpline | Filed as an investor, held, and the correction was not saved | ◐ Partly: two cards say the complaint is bouncing | P2, P5 |
| `c2` | A tool subscription renews within the week: keep or downgrade, ask for credits | Read, nothing recognised | ❌ Missed: filed as noise | P3, P4 |
| `h1` | Did the candidate accept the offer? Ask the founder | Filed as an investor contact; held | ✅ Same call | none |
| `l1` | A programme's round-2 result is outstanding: wait until a set date | A good question card was left in the queue | ✅ Same reading | none |
| `i6`, `s1`, `s2` | Older investor and prospect threads | Before the capture window | Before the copy's window | P2 (365 days at onboarding) |

**Scores today:**

| | Same | Close | Partly | Opposite | Missed | Outside the copy |
|---|---|---|---|---|---|---|
| Live product (stricter reading, 28 Oct) | 0 | – | 9 (partial or wrong) | – | 11 | – |
| Notebook `b2` | 4 | 2 | 4 | 2 | 5 | 3 |

## 2 · The 10 ideal goals

The goal "win paying design partners" rests on mail from before 25 Apr, so 9 of the 10 can be rebuilt from the copy.

| Ideal goal (described) | Notebook `b2` today | Fix owned by |
|---|---|---|
| Raise the pre-seed round | ✅ Matched (23 situations) | P2, P4 (target, plan, progress) |
| Get the accelerator to reconsider (`i1`) | ✅ Matched, just as specific | P4 (next move) |
| Complete the incubation programme | ✅ Matched | P4 |
| Get into an accelerator this cycle | ❌ Split into one goal per programme; 18 applications have no goal | P2, P4 |
| Win paying design partners | ❌ Outside the copy | P2 (inputs) |
| One verified traction number everywhere | ❌ Exists only as two cards | P4 |
| Submit a reviewed application to the main accelerator | ≈ Same goal in other words | P4 (matching) |
| Turn platform intros into partners and referrals | ✅ Matched, but 163 situations, too broad | P2, P4 |
| Correct the company's registration profile | ✅ Matched | none |
| Onboard a founding engineer | ✅ Matched | none |

## 3 · The replay: 23 → 28 Oct, one day at a time

Start from the notebook as of 23 Oct, 07:10 IST, and move it forward one day per run. Each real event must move the right situation, goal and card on the day it happens:

| Day | What happened in the mail | What GeniOS must do |
|---|---|---|
| 23 Oct | The incubator's final review was held; the founder sent two update mails after it | `f1` closes; the incubator goal moves a step; the new milestone becomes available to `i1` as a new checkable fact |
| 23–28 Oct | New intro offers and calls booked by the intro platform | Each new introduction is a situation with a yes/no, and they never pile into one |
| 24 Oct | The application deadline (`f2`) passes | `f2` closes verified on its confirmation or on the person's word; with no confirmation it goes to verify ("No confirmation by that day") and is missed only on the person's word (P5 07 §8.7); the goal records which |
| 27 Oct | The incubation letter arrives | The incubator goal is reached, and a "goal reached, confirm" card appears |
| 27 Oct | A broadcast states a new traction figure to about 33 recipients | `p1` grows with the new figure; no new card is made for each recipient |
| 29 Oct (ahead) | The tool subscription renews | `c2` stays open until decided, then closes |

## 4 · What must always hold

- **Data checks:** every database invariant of the notebook passes. There are 7 today: member mails exist; every thread is in a situation or noise; settled questions and promises were settled by the right side's later mail; claims are word for word and ours; open cards sit on live situations with real quotes; goals and links point at things that exist; spend is under the cap.
- **Tests:** all unit tests pass (353 today), plus every new test a step adds.
- **No held text:** the founder never sees a "held" card or the checker's internal text.
- **Cost:** within the agreed cap.
  - Onboarding a company of this size costs about **$8–9** at today's model (`b2` cost $8.41).
  - One Evolve day must stay under **$0.50**.

## 5 · Targets: when the whole plan is done

| Measure | Today (`b2`) | Target |
|---|---|---|
| In-copy ideal cards, same or close | 6 of 17 | **≥ 15 of 17** |
| Opposite calls | 2 | **0** |
| Open cards (whole company) | 63 | **≤ 30**, with no ideal card lost |
| In-copy ideal goals matched, each with target, plan, progress and next move | 6 of 9, with none of those four | **≥ 8 of 9**, all with them |
| Goal status and next move equal to the ideal | not measured (goals have neither) | **≥ 7 of 9** |
| Replay events handled on the right day | not run | **all** |
| Evolve cost per day | not run | **< $0.50** |

**How it is measured:**
- `nb.cli scorecard` and `nb.cli compare` produce the side-by-side page;
- the private `notes.json` holds the reads by hand;
- this file is updated only by a step that re-measures.
