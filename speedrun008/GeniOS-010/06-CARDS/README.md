# 06 · Cards: what needs you, one card at a time

**Written for:**
- **Harsh**, to wire it in. The step-by-step wiring is in **[`01-INTEGRATION.md`](01-INTEGRATION.md)**: every field, every route, every brain change, the checks.
- **Rohit**, to review it.

**The files:**

| File | What it is |
|---|---|
| this README | the page as it is today |
| [`04-WHAT-WHY-HOW.md`](04-WHAT-WHY-HOW.md) | **the story, for analysis:** what was there, what we built, why, how, the five rounds (a screenshot each in `rounds/`), how it was checked, how it integrates, what to do next |
| [`02-CARD-DEFINITION.md`](02-CARD-DEFINITION.md) | what a card is: every field, where it comes from in the brain, what is missing |
| [`01-INTEGRATION.md`](01-INTEGRATION.md) | the wiring for Harsh: run it, what feeds each part, every button, brain changes C1–C9 in order, the checks, merge notes |
| [`03-WHAT-WAS-THERE.md`](03-WHAT-WAS-THERE.md) | the analysis the work started from, each finding with its status |

**Read order:** 04 → this README → 02 → 01 → 03.

---

## Status, 22 Oct 2026

- **Built** on the dashboard branch **`rohit/cards-ux`** (`github.com/themoronss/genios-brain-dashbaord`): three commits on top of `rohit/nav-grouping` `847eeac`.

  | Commit | What it did |
  |---|---|
  | `b5527dc` | The card says where it came from, what to do and why. It opened in place (round 3). |
  | `9d565e6` | It opens in a side panel again. Buttons: Done · Delegate · Later · Feedback (round 4). |
  | `25553ab` | Every card shows only its own details, in the order Rohit set (round 5). |

- **Files:** three, +1,675 / −687.
  - `src/app/dashboard/cards/page.tsx` (rewritten);
  - `src/lib/card-read.ts` (new, the reader);
  - `src/lib/api-cards.ts` (small additions).
  - **No brain code changed.**
- **Not merged, so not live.** brain.thegenios.com serves `main`.
- **Route:** `/dashboard/cards`, under Intelligence ▸ **Cards**. Members see their own cards; owners see the workspace's.
- **Checks:**
  - `tsc --noEmit` green; `next build --webpack` green at `25553ab`.
  - **Stand-in brain:** checked signed in against it ([`tools/mock_cards.py`](tools/mock_cards.py)), which serves the real card shapes.
  - **Rohit's own cards:** he opened them on a local copy of this branch pointed at the live brain (localhost:3002). Rounds 4 and 5 came from that look.
- **There is no sample mode (`?demo=1`) on this page.** It shows real cards or none. To look without an account, run the stand-in brain (`01-INTEGRATION.md` §1).

## What Rohit asked, 22 Oct, in five rounds

1. **Analyse first.** *"Ek baar proper UI/UX identify karna hai … cards ke liye, jo cards generate ho rahe hain … card wala portion hi karna hai."* Another session owns the dashboard home, Goals and Screen; this folder owns the cards. The analysis is [`03-WHAT-WAS-THERE.md`](03-WHAT-WAS-THERE.md).
2. **Show how the card looks, and how it should look.** I answered with a design canvas of sample cards. **Dropped:** he wanted the real page fixed with his real cards, not a picture.
3. **The card's content.** He asked for:
   - the tool it came from, with the details as tags;
   - a headline made clear *"NLP ki madad se"*;
   - a two- or three-line description;
   - "What to do" with a real recommendation and its body, and what was committed;
   - "Why" as one line per point: the scenario, where it came from, what came.

   He also said the timeline of system events at the bottom is not a timeline. Things must be connected.
4. **On his live cards.**
   - *"Isko side mein hi kholo na, jaise pehle khul raha tha"*: the card was too long in place.
   - The subject must be a clear call to action.
   - The Why was the same on every card.
   - **Buttons:**
     - **Delegate**, to a person on the team or to an agent;
     - **Feedback**, saying what is wrong or right, with fill-in-the-blank words that go to the reasoning;
     - **Later**, holding every snooze option.
5. **Define the card.** *"Define karna ki kya achha, kya theek hai, yeh card hai, iske andar kya hai, aur in steps ko follow karne se kya results milenge."*
   - **On the face:** a clear subject, then one or two lines on what to do and how.
   - **Opened:**
     - what, why, how;
     - what doing it gets you;
     - the goal it moves;
     - the deadline;
     - the details;
     - where the data came from;
     - the recommendation.
   - And, said again: *"sabhi kardon ke vivaran alag-alag hon"* — every card's details and scenario are its own.

## Screenshots (`screens/`)

The `before-*` files are the page as it was on `origin/main`. The rest are this branch, signed in against the stand-in brain.

| File | What it shows |
|---|---|
| `before-list.png` | Before: every row the same; three 16px buttons on each; a question card offered Done. |
| `before-card-decision.png` | Before: "What to do" a stock sentence, "Why" five empty boxes, a raw ISO date, a timeline of system events. |
| `before-card-question.png` | Before: the question not shown, no answer box, Done offered (the server refuses it). |
| `cards-list.png` | The list, grouped by what each card asks (Decide · Answer · Waiting). Each row has its tool, subject, what to do and how, who, and the due date. |
| `card-open-top.png` | A card opened in the side panel: tools, subject, the two lines, then the recommendation and What · Why · How. |
| `card-open-bottom.png` | The same card further down: details, and where the data came from; "4 lines read the same on your other cards". |
| `card-open-expert.png` | An expert card: the move whole, who · for whom · by when, the quoted mail. |
| `card-open-question.png` | A question card: the question, why it is asked, and the answer box. No Done. |
| `card-feedback.png` | Feedback: what is off, then two blanks in your words, and what it applies to. |
| `card-delegate.png` | Delegate: a person (the real team) or an agent. The hand-over is locked until the brain serves it. |
| `card-later.png` | Later: 4 hours, tomorrow 9:00, 3 days, or a day you pick. |

---

## 1 · What a card is

One card is **one situation in your business that needs you**. It asks you to decide, to answer one question, or to wait while GeniOS watches.

It carries everything you need to act, and every word is about *this* situation. The full definition is [`02-CARD-DEFINITION.md`](02-CARD-DEFINITION.md): every field, where it comes from in the brain, how often it is filled today, and what is missing.

## 2 · The page, top to bottom

1. **Header.**
   - "What needs you, and what happened to each one".
   - Three counts: need you · put off · closed in 30 days.
   - Refresh. The shared `Topbar` renders nothing, so Refresh lives here.
2. **Tabs:** Open · Put off · History, each with its count.
3. **Open, grouped by what the card asks of you,** in the code's order:
   - **Decide:** "A move is yours, and the evidence holds."
   - **Two sources disagree.**
   - **Answer:** "One fact decides the move, so GeniOS asks before it advises."
   - **Waiting:** "Nothing to do now. GeniOS watches and brings it back."

   A group with no cards is not drawn.
4. **A row (the card's face):**
   - the tool it came from (Gmail, Calendar · as tags), the domain and its age;
   - the **subject**;
   - **one or two lines: what to do, and how**;
   - who it is about, and the due date;
   - the urgency (a dot and a word), one button that fits the card, and **Open**:
     - **Done** for a decision;
     - **Answer** for a question;
     - none for a waiting card.
5. **Put off:** the cards you snoozed, with Bring back.
6. **History:** closed cards with how each closed and who closed it where ("Marked done · You in the desktop app"). Filters: Done · Not right · Outcome confirmed · Expired. A closed card opens in the same panel, read-only.

## 3 · The opened card (the side panel)

The order is Rohit's, round 5. The panel is 600px wide and opens over the list.

**Top:**
1. The tools it came from, with how the data came ("Gmail · mail thread", "Calendar · 1 meeting"), the domain, the version ("version 3", from how often the card was rebuilt) and the age.
2. The urgency · what it asks (Decide / Answer / Waiting) · "by 28 Sep" when there is a date.
3. The **subject**.
4. **What to do, and how**, in two lines.

**Body, one scroll.** A section the card has nothing for is left out, except Goal and Deadline, which always say what is known.

| # | Section | What it holds |
|---|---|---|
| 1 | **Recommendation** (or, on a question card, **GeniOS asks you**) | The move; who · for whom · by when; the numbered steps; what to avoid; a quiet note if part of it could not be checked. On a question card: the question, why it is asked, an answer box and **Send answer**. |
| 2 | **What · Why · How** | What is going on; why now; the first step. |
| 3 | **What doing it gets you** | Done when · If you don't · If it can't be done · Wait or stop. |
| 4 | **Goal it moves** | "Not linked to a goal yet". No card carries a goal today; see 02 §3 field 8 and `01-INTEGRATION.md` C1/C8. |
| 5 | **Deadline** | Do it by · Window · Promise due · Coming up (a meeting or due date ahead); otherwise "No date in the thread". |
| 6 | **Details** | Who and their role, then one line per point with its tool and date: what was said (the quoted mail), what the records show ("Divya last wrote — Gmail, 13 Sep"), the meeting, how this kind of thing is handled (doctrine, labelled "Admin expertise"), what was promised. |
| 7 | **Where the data came from** | Each tool and how, then the dated mails, meetings and promises in order. |
| — | **What happened to this card** | Folded away: created, shown, refreshed, who acted where. |

**Footer: the buttons.** Only what the server offers on that card is drawn.

- **Done** (`do_it_myself`): not on a question card.
- **Delegate:** **A person**, the workspace's active members, yourself left out; or **An agent**, the active agents. **Hand over / Ask it are locked** until the brain serves a delegate route (`01-INTEGRATION.md` C5). The panel says so in one line, never a button the server refuses.
- **Later:**
  - In 4 hours · Tomorrow, 9:00 · In 3 days — the card's own snooze options;
  - or **a day you pick**, which puts it off to 9:00 that day (`snooze` + `custom_until`).
- **Feedback:**
  1. What is off: the reasons the card offers, in its four groups when it sends them, otherwise three.
  2. Two blanks: *"This card is wrong because ___"* and *"It should be ___"*.
  3. Apply it to this thread · this kind of work · how we work (owner only).
  4. **Send** posts `wrong` with the reason, your words and the scope. The brain keeps the words on the thread, and its next review reads them first (STEP-16 corrections).
- **Answer** (question cards, in the body) posts `answer` with your words. The card stays, versioned: "Your answer is in; GeniOS reads the thread again."

A refused press shows its reason in the footer and stays until the next press. Before, the refresh wiped it in under 100 ms.

## 4 · Only this card's own details

Rohit, round 4 and round 5: the Why, and then the details, read the same on every card. There are two causes, both in the brain (02 §4):

1. **Stock sentences per kind of card:**
   - the play's "done when";
   - the capability's "if you do nothing";
   - the projection's fallback steps (*"Reply to what they actually asked"*, *"Answer their open question"*).
2. **Person-level context attached to every card about the same person.** The subject node's last four meetings and three promises, `api/routes._card_intelligence`. When cards anchor on the same node, they all carry the same ones.

**What the page does (`card-read.ts`):**
- `sharedTexts` and `sharedLines` find any text that **more than one open card carries in the same field**.
- `ownCard` leaves it out of each of those cards, field by field: description, why now, how, the move, steps, avoid, done when, if you don't, otherwise, wait or stop, detail lines, promises, the dated entries.
- The panel says how many lines it left: *"4 lines read the same on your other cards, so they are left out here: written for a kind of card, not this one."*
- A Calendar tag counts only the card's own meetings, and goes when it has none.

**This hides the symptom.** The cure is brain changes C1 (the card writer) and C6 (card-scoped context). With them, the guard simply finds nothing to hide.

The before → after of every part, and the rounds, are in [`04-WHAT-WHY-HOW.md`](04-WHAT-WHY-HOW.md).

## 5 · Live today, and what waits for the brain

**Works with what the brain sends today:**
- the grouping;
- the tool tags;
- the subject (the brain's headline, tidied: spacing, a capital, an address shown as a name, no dangling last word);
- the two lines;
- the recommendation on expert cards;
- What · Why · How;
- done when and if you don't;
- the deadline from `by_when`, the window and promise dates;
- the details and the sources;
- the own-details guard;
- Done, Later, Feedback and Answer.

**Waits for the brain** (`01-INTEGRATION.md` §5):

| # | What it makes real |
|---|---|
| C1 | A **clear subject**, the two lines, steps, the result and a suggested goal, written per card |
| C2 | The expert's **"if you act now"**, as the result |
| C3 | The list without one detail call per card |
| C4 | Each quote with its sender and date |
| C5 | **Delegate** to a person or an agent |
| C6 | Context scoped to the card, so the guard finds nothing |
| C7 | A "this is right" verdict |
| C8 | The **goal link** (GeniOS-009 G4/G6) |

## 6 · The code

| File | What it is |
|---|---|
| `src/lib/card-read.ts` | **The reader.** `readCard(card, detail, timeline)` turns what `/cards`, `/cards/{id}` and `/cards/{id}/timeline` send into one `CardRead`, reading both card generations: formula cards (`why` = graph readings, `decision` = the projection) and expert cards (`recommended`, `why_now`, quoted lines). It also holds `clearHeadline`, `day` and `ago`, plus `sharedTexts`, `sharedLines`, `ownCard` and `ownTools` (§4), and `versionOf`. **No field is ever a dash or an empty box.** |
| `src/app/dashboard/cards/page.tsx` | **The page:** list, tabs, groups, `CardRow`, `Summary`, `CardPanel`, `LaterMenu`, `FeedbackMenu`, `DelegateMenu`, `HistoryRow` and an error boundary per opened card. It polls every 45 s while visible. `?card=<id>` (the desktop app's "Open card") opens that card's panel. |
| `src/lib/api-cards.ts` | `OpenCard` gains `domain`, `render_mode` and `subject_node_id`. `WrongReason` and `SnoozeOption` are any string the card offers. `actOnCard` sends `custom_until`, `words` and `scope`. New: `getMembers(orgId)`. |
| `../intel/parts.tsx` | Imported for `GCARD`, `L1`–`L3` only; **not edited** (Goals and Screen own it). |
