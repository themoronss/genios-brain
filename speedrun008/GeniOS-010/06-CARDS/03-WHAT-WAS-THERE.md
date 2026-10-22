# 06.3 · What was there: the analysis the Cards work started from

**Written for:**
- **Rohit**, for the record of what was wrong;
- **Harsh**, to see which findings the Cards branch fixes and which wait for the brain.

**How it was measured, 22 Oct:**
- **Code:** dashboard `origin/main` `6ddc4db` and `rohit/nav-grouping` `cc1b58f`; brain `21b7ae10`.
- **Render check:** the page drawn signed in against a stand-in brain that serves the real card shapes. The screenshots are `screens/before-*.png`.
- **Not read:** production cards (reads need Rohit's OK).
- **Not run:** the Mac app. Its findings are read from the code.

**Status column:** **Fixed** = fixed on `rohit/cards-ux`; **Brain** = waits for a brain change in `01-INTEGRATION.md` §5; **Open** = not yet taken.

---

## The Cards page (`/dashboard/cards`)

### C1 · The "Why" list was blank on every expert card — **Fixed** `b5527dc`

- **What was wrong:** expert `why` rows (`{sentence, quotes}`, `{sentence, inference}`, `{window, days}`) have no `field`/`value`. Each drew as an empty box labelled "· expert_check" or "· card_lines".
- **Who it hit:** 56 of the 57 golden cards are expert cards.
- **Now:** one line per point. Quotes are shown; inference labels are never shown as proof.

### C2 · "What to do" was a stock sentence, not the card's move — **Fixed** `b5527dc` (+ C1 in the brain for formula cards)

- **What was wrong:** the page read `decision.recommendation`, the request-time projection (`api/routes._decision_projection`). It shows lines like *"Reply to what they actually asked"*.
- **What it missed:** the expert's move, `recommended{who, what, for_whom, by_when}`. It was in the same response and unread.
- **Now:** the move first; the projection only when it is not stock.

### C3 · A question card could not be answered, and Done failed silently — **Fixed** `b5527dc`

- **What was wrong:** the brain takes only `answer`/`snooze`/`requeue`/`wrong` on a question card (`deliver/actions.py:43`, `:201`, 422 `not_offered`).
- **Measured:** the page offered Done. Pressing it got a 422, no message appeared at 0.1 / 0.4 / 1.5 / 4 s, and the card stayed. The refresh in `finally` wiped the error.
- **Now:** the question, why it is asked, and an answer box. Only the offered buttons are drawn, and errors stay.

### C4 · A row did not say what the card asks — **Fixed** `b5527dc`

- **What was wrong:** every row had the same chip, headline, situation and three buttons. A monitor card (*"Send Dev Malhotra the pricing sheet"*) read as an order.
- **Now:** cards are grouped Decide · Answer · Waiting. Each row shows its tools, subject, two lines, who, the due date and one fitting button.

### C5 · The buttons outweighed the card — **Fixed on Cards** `b5527dc`; **Open** for the rest

- **What was wrong:**
  - `.btn-blue`/`.btn-ghost` (`globals.css:309`, `:340`) set `1rem` outside any CSS layer, which beats Tailwind v4 utilities. So the buttons rendered at 16px, larger than the 13px headline.
  - The labels were 9–11px.
  - Error, notice and warning states used coloured washes.
- **Now:** the Cards page uses its own button classes. `globals.css` is untouched and needs one shared fix.

### C6 · The same card looked different in Cards and in Goals — **Fixed for Cards**; Goals **Open** (move it to `readCard`)

### C7 · Raw values reached the reader — **Fixed** `b5527dc`

ISO timestamps and source codes (`expert_check`, `card_lines`, `reasoning_trace`) were shown as they came. Dates now read "13 Sep, 3:42 pm", and codes are never shown.

### C8 · Most of what a card offers could not be pressed — **Fixed** `9d565e6`; Delegate **Brain** C5

- **What was wrong:**
  - "Not useful" offered three legacy reasons. The card itself offers 11, in 4 groups.
  - Your-words corrections with a scope were not reachable.
  - A custom snooze date was not reachable.
- **Now:** Feedback, Later (with a picked day) and Answer all work. Delegate is listed and locked.

### C9 · Versions were invisible — **Fixed** (version number) `b5527dc`; what changed **Brain** C9

### C10 · "How sure" must not be three confidences — **Open**

`confidence_vector` holds C = confidence, I = impact and U = urgency (`reason/authority.py:105–115`). The page shows urgency only, as a dot and a word. Confidence waits for GeniOS-008 L2-9's six named dimensions.

### C11 · Every card's details read the same — **Fixed (guard)** `9d565e6`, `25553ab`; cure **Brain** C6 + C1

- **What was wrong (found on Rohit's live cards, rounds 4–5):** stock sentences per kind, and person-level meetings and promises attached to every card about the same node.
- **Now:** text another open card repeats is left out, and counted.

## The Goals page's card (other session; recorded, not changed)

### G1 · "What to do" shows a code on live cards — **Open**

`goals/live.ts:94` reads `rec.verdict`, which is a code (`reply`, `review_source`, a play id). The stand-in brain in `02-DASHBOARD-HOME/tools/mock_brain.py` puts a sentence there, so the preview hides it.

### G2 · `proofOf` drops the quotes and shows inference labels as proof — **Open**

`goals/live.ts:74`.

**Fix for both:** read cards through `readCard`.

## The same cards in the Mac app (`Extension/src/desktop`)

| # | Finding | Status |
|---|---|---|
| M1 | "Not useful" sends `wrong` with no reason (`api.ts:372–380`). The brain refuses it (`invalid_wrong_reason`); the error is swallowed; the card vanishes and comes back on refresh. | Open |
| M2 | Done on a question card: refused (`not_offered`) and swallowed. | Open |
| M3 | No `surface` is sent, so web History cannot say "in the desktop app". | Open |
| M4 | Who is guessed from the headline by regex (`entityOf`) instead of read from `business_subject`. | Open |
| M5 | Expert `why` rows read ": undefined" (`whyLine`). | Open |
| M6 | It shows the profile, meetings and "What was said", which the web did not. Two dialects of one card. | Open (move to the reader) |

## What started the work

Rohit, 22 Oct: *"Ek baar proper UI/UX identify karna hai … cards ke liye, jo cards generate ho rahe hain … card wala portion hi karna hai."*

This file is that analysis, kept with each finding's status. `README.md` §5 has the before → after, and §6 the rounds.
