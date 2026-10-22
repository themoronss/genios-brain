# 06.2 · A GeniOS card — the definition

**Written for:**
- **Rohit**, to agree what a card is;
- **Harsh and every coding agent**, to build it the same way in the brain and on every screen: Cards, Goals, Screen, the Mac app.

**Rohit, 22 Oct:** *"define karna ki kya achha, kya theek hai, yeh card hai, iske andar kya hai, aur in steps ko follow karne se kya results milenge."*

Code facts are at brain `21b7ae10` and dashboard `rohit/cards-ux` `25553ab`.

---

## 1 · What a card is

**One card is one situation in your business that needs you.** It asks you to do one of three things:
- decide;
- answer one question;
- wait while GeniOS watches.

It carries everything you need to act:
- the recommendation;
- what doing it gets you;
- the goal it moves;
- the deadline;
- the details;
- where the data came from.

Every word on it is about **this** situation. A sentence that reads the same on another card was written for a kind of card, not this one, and does not belong on it.

## 2 · What makes a card good

1. **The subject is an action.**
   - It starts with a verb, is about ten words at most, and names the person or the thing.
   - Example: *"Confirm Thursday 4 pm with Ananya (Evokoa)"*.
   - Never a cut sentence, a code or a placeholder (*"…to body"*).
2. **Under the subject, one or two lines say what to do and how.**
3. **Each field is one line, two at most, and specific to this card.** No stock sentence shared with other cards. No two cards read the same.
4. **Every claim points to its source:** the tool, the mail or meeting, and the date. A quote is the mail's own words; GeniOS's own reading is never shown as proof.
5. **A field the card does not have is left out.** Two fields always say what is known, even when it is nothing yet:
   - **Goal:** "Not linked to a goal yet".
   - **Deadline:** "No date in the thread".
6. **Following the steps leads to the stated result.** The card says what done looks like and how GeniOS will see it happen.
7. **Only the buttons the brain takes on that card.** A question takes an answer, never Done. A refused press says why, in a sentence, and stays until the next press.

## 3 · The fields, in the order the opened card shows them

`F` marks a field that is on the card's face in the list too. Fill rates are from the golden measurement (GeniOS-009 `01-AS-IS-CARDS.md`, 57 cards).

### 1 · Subject (F)

- **From the brain:** `headline`.
  - Expert card: the move cut at a clause (`card_builder.gold_headline`).
  - Formula card: the template or model render.
  - Question card: the question (`why[0].question`).
- **Today:** always filled, but not always a clear action.
- **To make it right:** C1, the card writer.

### 2 · What to do, and how: 1–2 lines (F)

- **From the brain:** `recommended.what` and the first step.
- **Today:** the move is filled on 48/57 cards. Formula cards carry only the projection.
- **To make it right:** C1.

### 3 · Recommendation: who · what · for whom · by when · steps · avoid

- **From the brain:**
  - `recommended{who, what, for_whom, by_when}`;
  - `decision.recommendation.steps` / `avoid`;
  - `actionability`.
- **Today:** complete on expert cards. Formula cards get stock steps, which the page now hides.
- **To make it right:** C1.

### 4 · What

- **From the brain:** `situation`.
- **Today:** 57/57.

### 5 · Why

- **From the brain:** `why_now`; else the question's "why we ask"; else `do_nothing_consequence`; else what remains (`unresolved_item`).
- **Today:** why now 57/57; what remains 38/57.

### 6 · How

- **From the brain:** the steps.
- **Today:** an expert card has none; a formula card has stock ones.
- **To make it right:** C1.

### 7 · What doing it gets you: done when · if you don't · if it can't be done · wait or stop

- **From the brain:** `success_signal`, `do_nothing_consequence`, `alternative`, `wait_or_stop`.
- **Today:**
  - Often stock: the play's success line and the capability's do-nothing line.
  - The expert's `scenarios.act` never reaches the card.
- **To make it right:** C2, then C1.

### 8 · Goal it moves

- **From the brain:** nothing yet.
- **Today:** 0/57.
- **To make it right:** C1 (a suggested goal from the brief's accepted goals), then C8 (GeniOS-009 G4/G6).

### 9 · Deadline

- **From the brain:** `recommended.by_when`, `outcome_window_days`, promise due dates, upcoming meetings.
- **Today:** partly filled.

### 10 · Details: who · role · what was said · what the records show · how this is handled · what was promised

- **From the brain:**
  - `business_subject`, `relationship_role`;
  - `why[]`: the quotes, graph readings and doctrine;
  - `context.commitments`.
- **Today:** role is filled on 25/57.
- **To make it right:**
  - C4, each quote with its sender and date;
  - C6, context that belongs to this card.

### 11 · Where the data came from

- **From the brain:** `context_tags`, `why[].source`, the meetings, and dated thread facts.
- **Today:** filled.
- **To make it right:** C4.

### 12 · Buttons: Done · Delegate · Later · Feedback (or Answer)

- **From the brain:** `actions[]`.
- **Today:**
  - Done, Later, Feedback and Answer work.
  - Delegate is listed from real data and locked.
- **To make it right:** C5 (delegate) and C7 ("this is right").

The C-numbers are the brain changes in [`01-INTEGRATION.md`](01-INTEGRATION.md) §5.

## 4 · Why the details read the same on every card

There are two causes, both in the brain.

**1 · Stock sentences per kind of card.** The same words appear on every card of a kind:

| Field | Comes from |
|---|---|
| Done when (`success_signal`) | the play (`card_builder._play_success`) |
| If you do nothing (`do_nothing_consequence`) | the capability manifest |
| The steps | the projection's fallback (`api/routes._ASK_STEP`) |

**2 · Person-level context attached to every card about that person.**
- `_card_intelligence` adds the subject node's last four meetings (`_meeting_neighbors`, `routes.py:5253`) and three promises (`_commitment_neighbors`, `:5228`).
- When cards anchor on the same node, every card gets the same ones.
- **Not yet verified on live cards.** The check needs a read-only query, which needs Rohit's OK.

**What the page does now:** it leaves out any text another open card repeats in the same field, and says how many lines it left (`card-read.ts` `ownCard`). The cure is C6 and C1.

## 5 · One reader, every screen

`src/lib/card-read.ts` `readCard()` is the one place that turns what the brain sends into a card. It should be the only one:

| Screen | Today |
|---|---|
| Cards | Reads through `readCard`. |
| Goals | Has its own mapper, with two faults (`03-WHAT-WAS-THERE.md` G1/G2). |
| Screen ▸ "the card it fed" | Sample only until the brain serves the item → card link (Screen B8). When it goes live, read it through `readCard`. |
| The Mac app | Has its own reader, with faults M1–M6. |

Moving every screen onto `readCard` is how one card stops looking like four.
