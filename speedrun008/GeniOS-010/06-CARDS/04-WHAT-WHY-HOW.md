# 06.4 · Cards: what we built, why, how, and in which ways

**Written for:** Rohit and Harsh, to analyse the Cards work in one read before moving on.

| You want | Read |
|---|---|
| What the page is today | `README.md` |
| How to wire it | `01-INTEGRATION.md` |
| What a card is, field by field | `02-CARD-DEFINITION.md` |
| The story | this file |

This file covers what was there, what we built, why, how, the five rounds that shaped it, how it was checked, how it integrates, what to do next, and what is still open.

**State, 22 Oct 2026:**
- Dashboard `rohit/cards-ux` is three commits on top of `rohit/nav-grouping` `847eeac`: `b5527dc` · `9d565e6` · `25553ab`.
- **Not merged.** brain.thegenios.com serves `main`.
- No brain code changed.

---

## 0 · In one page

| | Before (`origin/main`) | Now (`rohit/cards-ux`) |
|---|---|---|
| The list | one list; every row the same: urgency, age, headline, situation, Done · Snooze · Not useful at 16px | grouped by what each card asks (Decide · Two sources disagree · Answer · Waiting); each row: tool tags, subject, what to do + how, who, due, one fitting button |
| Opening a card | a drawer: What to do · Why · Timeline | a side panel in Rohit's order: subject + two lines → Recommendation → What · Why · How → What doing it gets you → Goal → Deadline → Details → Where the data came from |
| What to do | the request-time projection, a stock sentence (*"Reply to what they actually asked"*) | the card's own move (who · what · for whom · by when) and its steps; the projection only when it is not stock |
| Why / proof | expert rows drew as empty boxes ("· expert_check"), raw ISO dates, no quotes | one line per point with tool and date; the quoted mail; GeniOS's own reading never shown as proof |
| Repeated text | the same "done when", steps, meetings and promises on every card | left out of every card that repeats it, and counted |
| Question cards | question hidden; Done offered and refused silently | the question, why it is asked, an answer box; no Done |
| Buttons | Done · Snooze (3) · Not useful (3 reasons) | Done · Delegate (a person / an agent: listed, locked) · Later (3 + a day you pick) · Feedback (reasons in groups, two blanks, scope) · Answer |
| Errors | wiped by the next refresh within 100 ms | kept on the card until the next press |
| Live today | the queue and the history | everything above. Waits for the brain: a clear subject per card, the result, the goal, the quote's sender/date, Delegate |

**Size:** 3 files, +1,675 / −687.
- `src/lib/card-read.ts`: 599 lines, new.
- `src/app/dashboard/cards/page.tsx`: 1,329 lines, rewritten.
- `src/lib/api-cards.ts`: +28.

## 1 · What was there

The full analysis is in `03-WHAT-WAS-THERE.md`, with each finding's status.

**The Cards page read three of the card's fields.** It read headline, situation and urgency. The engine sends seventeen.

**Two defects made the card look broken:**
- the "Why" list was blank on every expert card (56 of 57 golden cards);
- "What to do" was a stock sentence produced at request time, while the card's real move sat unread in the same response.

**A question card could not be answered.** It offered Done, the brain refused Done, and the page's own refresh wiped the error in under 100 ms. The card just stayed.

**The same card looked three ways:**
- in Cards (a drawer);
- in Goals (small cards; its own mapper shows a verdict code as "What to do" on live cards);
- in the Mac app (its own reader, whose "Not useful" never reaches the brain).

## 2 · What we built, and what each part is for

| Part | What it is for |
|---|---|
| **`card-read.ts` — one reader** | The one place that turns what the brain sends into a card. It reads both card generations the brain sends today: formula cards (graph readings, the projection) and expert cards (the move, quotes, why now). It never shows a dash, an empty box, a code or an ISO date. Goals, Screen and the Mac app should read cards through it too (`02-CARD-DEFINITION.md` §5). |
| **The list, grouped by what a card asks** | You see at once what needs a decision, what needs an answer, and what is only waiting. A waiting card has no button, because there is nothing to press. |
| **The row: subject + two lines** | Rohit: *"Subject line spasht, uske neeche ek-do line mein … kya karna hai aur kaise."* |
| **The side panel, in his order** | Everything he listed is visible when a card is open (no tabs), each section one line per field, and the buttons always at the bottom. |
| **Only this card's own details** | No card shows a sentence another open card repeats. This is the page-side guard for a brain fault (`02` §4). |
| **The buttons he named** | Done · Delegate (person / agent) · Later (all options) · Feedback (what is wrong, in your words, to the reasoning) · Answer on a question card. Only what the brain takes on that card is drawn. |
| **Errors that stay** | A refused press says why, in a sentence, until the next press. A refusal nobody sees is a silent stop. |

## 3 · Why: what Rohit asked, round by round

| Round | His words | What it meant |
|---|---|---|
| 1 | *"Ek baar proper UI/UX identify karna hai … card wala portion hi karna hai."* | Analyse the card part only; another session owns home, Goals and Screen. |
| 2 | *"Show karna: kaisa card dikhta hai, kaisa card dikh raha hai."* | Show the card as it is and as it should be. |
| 3 | *"Maine card mein jo bola tha, wahi maanga tha … card ka wo hissa, jo app par dikh raha hai, mujhe fix karna hai."* Upar tool ka naam, details tag ke roop mein; headline *"NLP ki madad se"* clear; do-teen line description; "what to do" proper recommendation; "why" ek-ek line mein: scenario, kahaan se aaya, kya aaya. | Fix the real page, with the real data, in that structure. |
| 4 | *"Isko side mein hi kholo na, jaise pehle khul raha tha."* Subject clear call-to-action. *"Y wale part mein … har card mein hi same hai."* Buttons: Delegate (People / Agent), Feedback (fill-in-the-blanks → reasoning), Later (all snooze options). | A side panel, a call-to-action subject, no repeated "why", his buttons. |
| 5 | *"Define karna ki kya achha, kya theek hai, yeh card hai, iske andar kya hai."* Opened: what · why · how, *"isko karne se kya hoga"*, *"kaun sa goal effect hoga"*, deadline, details, *"kahan se data aaya"*, recommendation. *"Sabhi kardon ke vivaran alag-alag hon."* | Write the definition; show exactly those points; no two cards the same. |

## 4 · How: the decisions, and the reason for each

| Decision | Reason |
|---|---|
| Fix the dashboard first, with what the brain already sends | Rohit wanted his cards fixed now. Most of what was wrong was the page not reading fields that were already there. |
| One reader (`readCard`), defensive on every field | The live brain sends two card generations at once. An object in a field that is typed as a string once took the whole dashboard down (`api-cards.ts` `displayValue`). |
| Draw only the buttons the card's `actions[]` offers | The brain refuses anything else. A question card offering Done was a silent failure. |
| Delegate listed from real data, the press locked | The brain has no route to hand a card over. A button the brain refuses is worse than a locked one that says why. |
| Feedback sends `wrong` + `words` + `scope` | That is the brain's existing correction path (STEP-16). The words are kept on the thread and the next review reads them first. This is "it goes to the reasoning" without a new route. |
| Leave out text other open cards repeat | Both causes are in the brain (stock sentences, person-level context). Until C1 and C6, the page must not show one card's details on every card. |
| No sample mode on Cards | Rohit reviews his real cards. The stand-in brain covers the no-account look. |
| Its own button classes; `intel/parts.tsx` and `globals.css` untouched | Those files are shared with Goals and Screen (another session). One writer per file. |
| "Goal: Not linked to a goal yet" and "Deadline: No date in the thread" always shown | He asked for both on every card. Unknown is said, never hidden and never invented. |
| Inference labels never shown as proof | *"An inference, not a quote"* is a label, not evidence. Proof is the mail's own words or a dated record. |

## 5 · In which ways: the five rounds

| Round | Commit | What changed | What was dropped | Screenshot (`rounds/`) |
|---|---|---|---|---|
| 1 | — | The analysis: 23 findings, each traced to code, rendered against a stand-in brain | — | `1-6ddc4db-before.png` |
| 2 | — | A claude.ai design canvas: today's screenshots next to a proposed page with sample golden cards | **The canvas.** He wanted the real page and his real cards, not a picture | — |
| 3 | `b5527dc` | The reader; tool tags; the move; one line per Why point; quotes shown; only offered buttons; errors that stay; the card opening **in place** | **In-place opening:** too long to take in | `3-b5527dc-in-place.png` |
| 4 | `9d565e6` | The **side panel** with tabs (What to do · Why · History); Delegate / Later / Feedback; Why lines shared across cards left out | **Tabs:** everything he lists must show when the card is open | `4-9d565e6-side-panel-tabs.png` |
| 5 | `25553ab` | One scroll in his order; the two lines under the subject (row and panel); **every field** that another card repeats left out, and counted; Goal and Deadline always present | — | `5-25553ab-own-details-in-order.png` |

## 6 · How it was checked

1. `npx tsc --noEmit -p .` is green, and `npx next build --webpack` is green with `/dashboard/cards` built, at `25553ab` rebased on `847eeac`.
2. **Stand-in brain** (`tools/mock_cards.py`, the real shapes, six cards, three of them sharing the same meetings and promise on purpose), rendered by `tools/shoot_cards.mjs`. All of these held:
   - each group drawn;
   - the panel's sections in order;
   - the question card showed the answer box and no Done;
   - Feedback sent the reason, words and scope;
   - the shared meetings left every card and were counted;
   - Delegate listed the team without yourself, and the agents.
3. **Before the rewrite, measured:** Done on a question card returned 422, and no banner appeared at 0.1 / 0.4 / 1.5 / 4 s (`03` C3).
4. **Rohit's own live cards:** he opened them on a local copy of the branch pointed at the live brain (localhost:3002). Rounds 4 and 5 are his findings from that look.
5. **Not checked:**
   - production data directly (reads need his OK);
   - the Mac app (not run).

## 7 · How it integrates

`01-INTEGRATION.md` has the full detail.

- **Data:** `/cards` and `/cards/history` are read on load. `/cards/{id}` is read for up to 40 open cards (C3 removes this). `/cards/{id}/timeline` is read when a card is opened. All presses go to `POST /cards/{id}/action`, and Delegate reads `/api/org/{org}/members` and `/v1/agents`.
- **Branch:** `rohit/cards-ux` merges after, or with, `rohit/nav-grouping`. It touches three files and none of the other session's.
- **The brain, in order:**

  | # | Change |
  |---|---|
  | C6 | context scoped to the card |
  | C2 | the expert's "if you act now" reaches the card |
  | C1 | the card writer: subject, two lines, steps, result, suggested goal |
  | C4 | quotes with sender and date |
  | C3 | queue fields for the list |
  | C5 | delegate |
  | C7 | "this is right" |
  | C8 | goal links (GeniOS-009) |

  Each one has its dashboard change written next to it.

## 8 · What to do next, and who

| # | What | Who |
|---|---|---|
| 1 | Review this folder and the page on his own cards (localhost:3002, or once merged). | Rohit |
| 2 | Allow one read-only look at the live cards, to confirm why the details repeated (C6) and to write the card writer's prompt against real cards (C1). | Rohit (permission) |
| 3 | Merge `rohit/nav-grouping` then `rohit/cards-ux` into `main`, and check against the live brain (`01` §1 B, §6). | Harsh |
| 4 | Build C6 and C2, then C1, in the brain; deploy each. | Claude builds (on Rohit's go), Harsh deploys |
| 5 | Move the Goals page and the Mac app onto `readCard` (`03` G1/G2, M1–M6). | Next unit, with the owners of those surfaces |

## 9 · Open points, for the analysis

1. **The subject's clarity is still the brain's words** until C1. The page only tidies them (spacing, a capital, an address as a name, no dangling last word).
2. **The repeated-details guard compares open cards only.** A stock sentence on the only open card is shown, because there is nothing to compare it with.
3. **Goal is "Not linked to a goal yet" on every card** until C1 (suggested) or C8 (linked).
4. **Delegate is locked** until C5.
5. **No "this is right"** until C7.
6. **Confidence is not shown** until GeniOS-008 L2-9 gives named dimensions. `confidence_vector` mixes confidence, impact and urgency (`03` C10).
7. **`globals.css` `.btn-*` at 1rem** still enlarges buttons on other pages (`03` C5).
