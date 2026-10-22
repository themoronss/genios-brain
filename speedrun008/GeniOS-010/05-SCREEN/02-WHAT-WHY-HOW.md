# 05.2 · Screen: what we built, why, how, and in which ways

**Written for:** Rohit and Harsh — to analyse the Screen work in one read before moving on. What the page is today: `README.md`. How to wire it: `01-INTEGRATION.md`. This file is the story: what was there, what we built, why, how, the five rounds that shaped it, how it was checked, and what is still open.

**State, 22 Oct 2026:** dashboard `847eeac` on `rohit/nav-grouping`, pushed, **not merged** (brain.thegenios.com serves `main`). Preview: `/dashboard/moments?demo=1`.

---

## 0 · In one page

| | Before | Now |
|---|---|---|
| Where | Desktop ▸ **Moments** | Intelligence ▸ **Screen** (same route, `/dashboard/moments`) |
| What it showed | the popups the desktop app raised, a week of counts, a separate list of open follow-ups — three boxes that did not refer to each other | one page that tells the whole story of each thing the screen caught: what was seen, what was done at once, the goal it moves, where it went, and the card it fed |
| How it was sorted | by time | by day, then by **category** (asked of you · deadlines & reminders · risks · promises · updates & next steps), with filters |
| Explained how it works | no | six stages, with this week's counts, and the rules (privacy, cost, popups) |
| Opened item | — | five essentials first; the rest under **Show more**, one tab at a time |
| Tied to goals and cards | no | the goal each item moves (and how), and the card it fed — nested, and listed |
| Look | bordered boxes | the dashboard's theme; fill instead of borders (dark · white · grey tint · accent tint) |
| Live today | the counts and the popups | every item with its words, who, due, reminders, how it ended and whether it is saved; all actions (Done · Snooze · Draft a reply · Done elsewhere · Dismiss · popup feedback) |

**Size:** 5 Screen commits (+ 1 shared-parts commit, + 1 that locked Agents). 9 files: +2,713 / −702. `screen/` is 4 files (`types` 169 lines · `sample` 375 · `live` 161 · `screen-page` 1,551); the shared `intel/parts.tsx` 406.

## 1 · What was there

1. **On `main` (and live today):** Desktop ▸ Moments.
   - A header with Loaded / Shown / Wrong counters and Refresh.
   - *This week*: promises caught, asks flagged, deadlines, risks, popups shown, % useful.
   - *Open follow-ups*: a flat list with Done / Dismiss.
   - *Moments*: every popup, shown or held back, with Useful / Wrong.
   - Nothing said how any of it worked, which popup came from which follow-up, or whether anything led to a card or a goal.
2. **First version on this branch (`0ab7b03`)** — screenshot `rounds/1-0ab7b03-two-lanes.png`:
   - moved to Intelligence ▸ Screen;
   - two lanes on top: *Done instantly* (the week's counts) and *Sent for reasoning* ("—" and a link to Cards);
   - Rohit's question *"iska koi alag part banana padega ki nahi"* answered **no**: what reasoning produces is a card, and cards live in Cards.

## 2 · What we built

Top to bottom, and what each part is for, for the customer:

| Part | What it shows | For the customer |
|---|---|---|
| **Week band** (dark) | items by category, open now, promises kept, asks answered | "how did my week go" in one glance |
| **How Screen works** | Read → Sort → *right away* (Save · Remind/popup) and *next* (Keep or let go · Reason → card), each with this week's count; **The rules** | trust: what is read, what is kept, what it costs, who sees it |
| **What your screen caught** | by day, then by category; filters by category and by state (open · closed · saved to graph · temporary · fed a card); each row tagged | find anything fast; see what kind of day it was |
| **An opened item** | first: seen where/when + actions · the line with who and due · the screen rebuilt · the goal strip · the kept strip; then **Show more** tabs: What GeniOS did · Where it goes · The goal · The card it fed | act on it, and understand it, without reading everything |
| **Cards your screen fed** | each card once, with the items that fed it | the screen's contribution to real work |
| **Popups** | shown and held back, why, and Useful / Wrong | teach GeniOS when to interrupt |

## 3 · Why — what Rohit asked, round by round

| Round | Rohit, 22 Oct | What it answered |
|---|---|---|
| 1 | *"Screen wale part mein thodi details daal do: kaise, kya, kis tareeke se hoga. Isi tarah ek dummy dikhayein."* · *"Screen aur cards … ek saath ho jaayein, lekin alag-alag rahein."* · lock Agents | How Screen works on the page; a full preview; items and cards as two linked things; Agents locked |
| 2 | *"Tag lagana chahiye tha … categories honi chahiye ki Thursday ko kaun-kaun si cheezein kis-kis category mein aayi hain — reminder, update, risk, promise"* · show what was on screen · *"NLP ki madad se one-liner, clear cut"* · where / when properly · *"important hoga to … context graph mein save; temporary rahega to wahin miss"* · *"customer ke hisaab se UX … aadha adhoora kyun"* | Categories inside each day; tags on every row; the screen rebuilt; the one clear line; who · where · when · due; kept vs temporary |
| 3 | *"Ye kaun se goal ke saath connected hai … isse goal help ho raha hai"* · *"kuch cards dark, kuch white … border mat do; color idhar-udhar"* | The goal it moves (and how); fill instead of borders |
| 4 | *"Card ke andar ki details bahut cluttered … zaroori information hi dikhai de; baaki Show More … clearly segregated"* | Five essentials first; Show more as tabs, one section at a time |
| 5 | *"Theek hai, yeh better hai"* — document it in detail and push everything | this file, the round screenshots, and one push |

## 4 · How — the decisions, and the reason for each

**Two things, not one: a screen item and a card.** An item is what the screen *saw* (`S-XXXXXX`, the follow-up); a card is what reasoning *concluded* needs you (`G-XXXXXX · C0N`). They are drawn differently (the app's mark and an ink edge vs a numbered box and an accent edge) and linked both ways: the item says which card it fed, the card says which items fed it. One card can be fed by many items, so the cards section lists each card once. *Why:* "ek saath, lekin alag-alag" — together on one page, never confused.

**Categories from the brain's own kinds.** The brain saves six kinds (`followups.KINDS`); the page groups them into five categories a founder thinks in (promises keep "yours / theirs" as a tag). *Why:* no new brain field needed, and the words are the customer's ("asked of you", not `ask`).

**The screen, rebuilt — never stored.** The brain never keeps the screen: only a fingerprint and the ≤ 12 words that caused an item. So the page *rebuilds* what was seen from what is kept — a chat bubble, a mail line or a page line — and marks the words that set the due date. *Why:* Rohit wanted to see the screen; privacy says no screenshot exists. This shows the moment without storing it.

**One clear line.** The instant read already writes each item as one line (`text`, ≤ 140 characters); the page adds the due it resolved. *Why:* "NLP se one-liner" — the model did it once, at capture time, for free.

**Kept or temporary, said plainly.** Important → saved to the context graph on the person or company (only one GeniOS knows), reasoned over, maybe a card. Temporary → a follow-up only, removed 90 days after it closes. *Why:* Rohit's own model of it — "important → context graph; temporary → missed" — and it is exactly what the brain does (`screen_thread_verdicts.memory`, `screen_memory`, `followups.purge`).

**The goal it moves.** An item's goal is the goal of the card it fed; the page says how it bears on it (advances / threatens / depends on, and through what) and what is happening on the goal. *Why:* every screen item should be seen against what the company is trying to do. *Live:* waits on GeniOS-009 G4; the page says so instead of guessing.

**Essentials first, Show more as tabs.** An opened item shows five things; everything else sits in four tabs, one at a time; the strips jump to their tab; an open row hides its tags. *Why:* round 4 — the customer reads the top, and opens more only when they want it.

**Fill, not borders.** Dark for what must be read first (the week band, the one line); white with a soft shadow for content; grey tint for facts and framing; accent tint for anything tied to a goal. Controls keep a hairline so they still look pressable. *Why:* round 3 — things stand out by colour, not by lines.

**Honest when live.** Every part the brain does not serve yet says "not served yet" (or "shows once goals and cards are linked") — never a made-up value, never a 0 for unknown. *Why:* the dashboard's first rule: no invented number reaches a signed-in customer.

**Engineering choices.**
- *One shape, two sources:* `ScreenView` is filled by `sample.ts` in the preview and `live.ts` when signed in; components never know which. Making a part real is a change to `live.ts` only.
- *One card component everywhere:* the card on Screen is Goals' own (`intel/parts.tsx`), so a card reads the same on Goals, on Screen and — next — in Cards. New options are additive (`Mini tone`, `flat`) with defaults that keep Goals unchanged (checked: 10 of 10 small cards keep their hairline).
- *The preview is the Goals preview's world:* the same founder, the same five cards (each with the screen quote added to its proof), the same goals — so the three pages agree.
- *Nothing outside the page moved:* no `globals.css` change, no brain code change, additive changes to `lib/api-followups.ts`.

## 5 · In which ways — the five rounds

| # | Commit | What the page became | Dropped | Screenshot |
|---|---|---|---|---|
| 1 | `0ab7b03` | Screen under Intelligence; two lanes (done instantly · sent for reasoning) on top of Moments | — | `rounds/1-0ab7b03-two-lanes.png` |
| 2 | `9130f84` | How Screen works (six stages + rules); every item with its path (at once → memory → card), opening into on your screen · at once · next; the card nested; cards fed; popups; the preview | the two lanes, This week and Open follow-ups as separate boxes | `rounds/2-9130f84-items-and-their-path.png` |
| 3 | `972d122` | by day, then by category; category + state filters; tags on every row; the screen rebuilt; the one clear line; who · where · when · due; kept or temporary | the path track on the row; the bare quote box | `rounds/3-972d122-categories-and-tags.png` |
| 4 | `9a13d87` | the goal it moves (block + row tag); fill instead of borders | hairlines on Screen's cards | `rounds/4-9a13d87-goal-and-fill.png` |
| 5 | `847eeac` | five essentials first; Show more as tabs; ⋯ for rare actions; open rows without tags | the Who / Where / When / Due boxes; every section open at once | `rounds/5-847eeac-essentials-first.png` |

Alongside: `f151019` moved the card parts into `intel/parts.tsx` (shared with Goals); `5c0504f` locked Agents (menu, page, home links).

## 6 · How it was checked

- `tsc --noEmit` and `next build` green after every round (and on each intermediate commit of round 2).
- The preview rendered at 1440 and 1024 wide after every round: no horizontal scroll; long lines wrap instead of cutting off.
- Signed in against the stand-in brain (`02-DASHBOARD-HOME/tools/mock_brain.py`, which serves the follow-ups, popups and their writes): items group by day and category; **Draft a reply** returned a draft; **Done** closed the item and the stand-in brain recorded `"resolution": "done"`.
- Goals checked after every shared-part change: unchanged.

## 7 · How it integrates

Live today with no brain change: items, categories, tags (except popup / card / goal), the rebuilt screen, the line, who and due, reminders, saved-to-graph, every action, the popups, the week band.

What makes the rest real — brain changes in order, each small and independent, each with the one `live.ts` change it needs (full detail: `01-INTEGRATION.md` §5):

| | Brain | Makes real |
|---|---|---|
| S1 | `graph_written_at`, `observation_id` in `followups.item_out` (columns exist) | "saved at 12:00" |
| S2 | `read_by` on each follow-up | "how it was read" |
| S3 | `remember` + `keep_reason` (join `screen_thread_verdicts`) | kept vs temporary, and why |
| S4 | `due_phrase` | the marked words |
| S5 | `moment_id` on each follow-up | the item's popup |
| S6 | a stored card ↔ follow-up link | the card it fed; cards your screen fed |
| S7 | GeniOS-009 G4 (+ G1/G5 `GET /v1/goals`) | the goal it moves |
| S8 | read / skipped / threads counts on the weekly report | stages 1, 2 and 5 counts |

To go live: merge `rohit/nav-grouping` into `main` (Rohit approves). Nothing in the brain has to change first.

## 8 · Open points, for the analysis

- **Not live** until the branch is merged.
- **S1–S8** decide how much of the page is real for a customer; S6 and S7 carry the most meaning (card and goal).
- **The look on Goals:** Goals still uses hairlines; it can take the Screen look (fill, not borders) by passing `tone` / `flat`, if wanted.
- **Cards** is the next page in the order (another session owns it); it should build on `intel/parts.tsx`, so a card reads the same everywhere.
- **Phones:** the app shell does not collapse below ~700 px (true before this branch; `04-BUILD-REVIEW.md` R10).
