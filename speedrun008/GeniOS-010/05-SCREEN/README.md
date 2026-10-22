# 05 · Screen: what the screen caught, and what became of it

**Written for:** Harsh (to wire it in) and Rohit (to review it). Three files:
- this one — what the page is;
- **[`01-INTEGRATION.md`](01-INTEGRATION.md)** — the wiring: every field, every route, every brain change, the checks;
- **[`02-WHAT-WHY-HOW.md`](02-WHAT-WHY-HOW.md)** — the story for analysis: what was there, what we built, why, how, the five rounds with a screenshot each (`rounds/`), and what is open.

**Status, 22 Oct 2026:**
- Built on the dashboard branch `rohit/nav-grouping`, in four rounds: `9130f84` (the page), `972d122` (by category, tags, the screen rebuilt, kept or temporary), `9a13d87` (the goal each item moves; cards that stand out by fill, not borders), `847eeac` (an opened item shows what matters first; the rest under Show more). With `f151019` (the shared card parts) and `5c0504f` (Agents locked). **Not merged, so not live.**
- **Route:** `/dashboard/moments`, Intelligence ▸ **Screen**. Members can open it too.
- **Preview** (the full target, labelled "Preview — not your data"): `/dashboard/moments?demo=1`.
- `tsc --noEmit` and `next build` are green at `847eeac`. Checked in the preview at 1440 and 1024 wide, and signed in against the stand-in brain (`../02-DASHBOARD-HOME/tools/mock_brain.py`): Draft a reply and Done ran end to end. The Goals page is unchanged by the shared-part changes (all 10 of its small cards keep their hairline).
- It replaces `../02-DASHBOARD-HOME/04-SCREEN.md` (the first, two-lane version).

**What Rohit asked, 22 Oct, in four rounds:**
1. *"Screen wale part mein thodi details daal do: kaise, kya, kis tareeke se hoga. Isi tarah ek dummy dikhayein."* and *"Screen aur cards … ek saath ho jaayein, lekin alag-alag rahein."* — and lock Agents.
2. On the built page: tag every row; *"categories honi chahiye ki Thursday ko kaun-kaun si cheezein kis-kis category mein aayi hain — reminder, update, risk, promise"*; show what was on screen; *"NLP ki madad se one-liner, clear cut"*; where and when properly; *"kuch important hoga to … context graph mein save ho jaayega; temporary rahega to wahin miss ho jaayega"*; *"customer ke hisaab se UX"*.
3. *"Ye kaun se goal ke saath connected hai … isse goal help ho raha hai aur ye cheezein ho rahi hain"*; and the look: *"kuch cards ko dark kar do, kuch ko white … border mat do; uski jagah thoda sa color idhar-udhar"*.
4. *"Card ke andar ki details bahut cluttered … zaroori information hi dikhai de; baaki cheezein Show More ke through … clearly segregated."*

**Screenshots** (in `screens/`):

| File | What it shows |
|---|---|
| `screen-preview-top.png` | The preview as it opens: the week as a dark band, How Screen works. |
| `screen-preview-how-and-rules.png` | How Screen works with **The rules** open. |
| `screen-preview-by-category.png` | What your screen caught: the filters, Thursday's items under their categories, rows with their tags. |
| `screen-preview-item-open.png` | An item opened: only what matters — the line, who and due, the screen rebuilt, the goal strip, the kept strip, Show more. |
| `screen-preview-show-more.png` | Show more open on *What GeniOS did*. |
| `screen-preview-item-goal.png` | Show more on *The goal*. |
| `screen-preview-item-card.png` | Show more on *The card it fed*, the card open. |
| `screen-preview-temporary.png` | A temporary item: no goal, a follow-up only. |
| `screen-preview-cards-popups.png` | Cards your screen fed, and the popups. |
| `screen-signed-in.png` | A signed-in seat against the stand-in brain: real items, one open; the goal strip says the link is not served yet. |

---

## 1 · How Screen works (what the page explains, and what the brain does)

Every **work** screen takes **both** paths. The instant path saves what to do now; the memory path lets reasoning join it with everything else.

```
 1 Read ─────► 2 Sort ──┬─► RIGHT AWAY (seconds) ── 3 Save ── follow-ups ──► 4 Remind · popup (only if it adds)
 a few seconds   free   │
                        └─► NEXT (hourly) ───────── 5 Keep or let go ── important: context graph ──► 6 Reason → card → its goal
                                                      temporary: stays a follow-up, removed 90 days after it closes
```

| # | Stage | What happens | Brain |
|---|---|---|---|
| 1 | **Read** | You stay on a chat, a mail or a page for a few seconds; the desktop app reads what is visible. Never-read apps, a diff, the 24 h verdict and dwell are checked first. | desktop app; router checks 1–4 (`reason/moments/screen_rules.py` docstring) |
| 2 | **Sort** | Free. A conversation is always judged; a page only if it names someone in the graph, has a participant with an email or LinkedIn, or is a work app or site. The rest is skipped — counted (`rate_counters`, kind `screen_insight_skipped`) — and still reaches the hourly batch, late and cheap. | `reason/moments/screen_triage.py`; `POST /v1/moments/evaluate` |
| 3 | **Save** | A **rule** answers when a sender writes a clear ask or promise with a date (free; the quote is the item). Otherwise **one quick read** (one model call) returns `work`, `remember` and up to 3 items: kind, text, who, due, quote. An item whose quote is not on screen is dropped. Saved as `screen_followups`. | `screen_rules.py`, `screen_insight.py`, `followups.upsert` |
| 4 | **Remind · popup** | Reminders before each due time (heads-up → final → overdue). A popup **only** when it adds something the screen does not say: a repeat ask, a promise owed, a calendar clash, the same ask elsewhere, an urgent risk. Held back by popups-off, the hourly cap, do-not-disturb or a duplicate — and still listed. | `screen_insight.py` (the product rule), `moments` |
| 5 | **Keep or let go** | **Important** → saved to the context graph: at most once an hour per thread, the thread becomes a seat-private source event, and each item is written as an observation (`screen.<kind>`) on the person or company it is about — **only one GeniOS already knows**; a screen never creates a person. **Temporary** (the model's `remember: false`, a throwaway thread, or a person not in the graph) → stays a follow-up, removed 90 days after it closes. The hourly batch (half price) catches what the instant read never saw. | `screen_thread_verdicts.memory`, `platform/screen_promoter.py`, `screen_memory.py`, `screen_memory_batch.py`, `followups.purge` |
| 6 | **Reason → card → goal** | What is saved is reasoned over with mail, calendar and documents, like any other evidence. A situation that needs you becomes a **card** — in Cards, and under the goal it moves. | L1 → L3 → L2 → cards; GeniOS-009 G4 for goal links |

**The rules** (a toggle on the page): never read · what is kept (never the screen; a fingerprint and ≤ 12 words; the hourly text is encrypted and deleted once done) · important or temporary · when a popup shows · who sees it (only you; owners and admins never) · what it costs.

## 2 · The page, top to bottom

1. **Header:** Intelligence · Screen, one line, and "Only you see this page."
2. **The week, a dark band:** a donut of items by category, then open now · promises kept · asks answered.
3. **How Screen works:** the six stages, each with this week's count, and **The rules**.
4. **What your screen caught:**
   - **Filters:** *Category* (All · Asked of you · Deadlines & reminders · Risks · Promises · Updates & next steps) and *Show* (Everything · Open · Closed · Saved to graph · Temporary · Fed a card), each with a count.
   - **By day, newest first.** The day line says how many came in each category ("1 asked of you · 1 deadline · 1 risk · 1 promise").
   - **Inside a day, by category,** in a fixed order, each with its count and what it means ("someone is waiting on your answer").
5. **Cards your screen fed:** each card once, with the screen items that fed it.
6. **Popups:** shown and held back, with Useful / Wrong.

## 3 · Categories and tags

**Five categories, from the six kinds the brain saves:**

| Category | Kinds (`followups.KINDS`) | Row tag | Means |
|---|---|---|---|
| Asked of you | `ask` | Asked of you | someone is waiting on your answer |
| Deadlines & reminders | `deadline` | Deadline | a date GeniOS reminds you before |
| Risks | `risk` | Risk | it costs you if it is missed |
| Promises | `my_promise`, `their_promise` | Your promise · Their promise | yours to keep, or theirs to watch |
| Updates & next steps | `next_step` | Update | something changed, and a step follows |

**Tags on every row:** the category tag first, then — after who · app · time — the next reminder (`Reminder Fri 10:00`), `Popup shown`, `Saved to graph` or `Temporary`, the card it fed (`Card G-3F2A9C · C02`, dark), and **the goal it moves** (`↑ Raise the seed round`, accent). On the right: when it is due, or how it ended.

## 4 · An item, opened (round four: what matters first, the rest under Show more)

Rohit: *"card ke andar ki details bahut cluttered, messed up, aur over-detailed … zaroori information hi dikhai de; baaki Show More … clearly segregated."*

**What a customer sees first** — five things, nothing else:

```
Seen on WhatsApp · today, 11:40                                   [Done] [Snooze ▾] [Draft a reply] [⋯]
┌█ IN ONE LINE ███████████████████████████████████████┐ ┌ WhatsApp · chat with Mohit Rao ── 11:40 ┐
█ Mohit wants your traction one-pager before            █ │ ┌ Mohit Rao ─────────────────────────┐ │
█ Northgate's partner meeting on Monday, 9:00.          █ │ │ Partners meet Monday — one-pager … │ │
█ ─────────────────────────────────────────────────────█ │ │ bhej doge _before that_?            │ │
█ 👤 Mohit Rao · Northgate Capital   ⏰ Due Mon 26 Oct, 09:00 · Reminder Fri 16:00 █ │ Rebuilt from the kept words … │
└██████████████████████████████████████████████████████┘ └──────────────────────────────────────────┘
┌ ↑ HELPS THE GOAL (accent) ──────────────────────────┐ ┌ KEPT (ink tint) ────────────────────────┐
│ Raise the seed round                              › │ │ Saved to your context graph · Mohit Rao › │
│ ● On track · 40% · through Northgate moving …       │ │ Fed card G-3F2A9C · C02                   │
└─────────────────────────────────────────────────────┘ └───────────────────────────────────────────┘
Show more ▾ — What GeniOS did · Where it goes · The goal · The card it fed
```

1. **Where and when it was seen**, and the actions. Done, Snooze and Draft a reply are up front; Done elsewhere and Dismiss sit under **⋯**.
2. **In one line** (dark), with **who** and **when it is due** (and the next reminder) underneath — the old Who / Where / When / Due boxes are gone; where and when are in the first line.
3. **What was on screen**, rebuilt from the kept words.
4. **The goal it moves**, one strip: helps / puts at risk / waits on · the goal · status · % · through what. Or "Not connected to a goal".
5. **Where it went**, one strip: kept (saved to your context graph on whom, and the card it fed) or temporary (a follow-up only, removed 90 days after it closes).

**Show more** opens a panel with **one section at a time** (tabs), so it never all shows at once:

| Tab | Holds |
|---|---|
| What GeniOS did | saved as (category) · how it was read · reminders (and the words the due was read from) · popup |
| Where it goes | kept or temporary, with the steps (follow-up › context graph › reasoning › card) · reasoned with · outcome |
| The goal | the goal with its ring, how this item bears on it, what is happening on the goal, Open the goal — only when there is a goal |
| The card it fed | the card itself, opening on its own — only when there is one |

- Clicking a strip opens Show more at its tab: the goal strip → *The goal*; the kept strip → *The card it fed* (or *Where it goes*).
- The item's ids (`S-XXXXXX`, `fu_…`) sit at the foot of the panel.
- An **open row hides its tags** — the item says the same things below, in words.
- **The screen, rebuilt.** The screen is never stored, so there is no screenshot to show. The page rebuilds what was seen from what *is* kept — the app, the person, the time and the ≤ 12 words — as a chat bubble (your own message on the right, dark), a mail line or a page line. The words that set the due date are marked.
- **In one line.** The instant read writes each item as one line (`text`, ≤ 140 characters); the page shows it with the due it resolved.

## 5 · The goal it moves (round three)

**What it shows.** First, as a strip in the opened item (helps / puts at risk / waits on · the goal · status · % · through what). In full under Show more › *The goal*:

| Part | Says | From (preview) | From (live, once served) |
|---|---|---|---|
| The goal | GOAL · `G-XXXXXX` · status dot and word · statement · progress · due · a ring with its % | the Goals preview's own goal | `GET /v1/goals` (GeniOS-009 G1 + G5) |
| How this item bears on it | **↑ Advances** / **↓ Threatens** / **↔ Depends on**, said plainly: "This helps the goal: …", "This puts the goal at risk: …", "The goal waits on this: …" — and *through what* | the card's own `reasoning.impact`, or set on the item | the G4 link of the card the item fed (`relation`, `through`) |
| What is happening on the goal | the goal's progress line, and its next move | the goal's `progress` and `nextMove` | `GET /v1/goals` (`progress`, `next_move`) |
| Open the goal | a link to Goals | `/dashboard/goals?demo=1` | `/dashboard/goals` |

- **On the row** (closed), a connected item carries the goal as an accent tag: `↑ Raise the seed round`.
- **An item with no goal** says so in a grey line: "Not connected to a goal — nothing on your goal list depends on it." Temporary items have none.
- **An item can be connected without a card yet** — the preview's Anil item (two angel intros) advances the seed round before any card exists.
- **Live today** the block says: "Which goal it moves shows once goals and cards are linked (GeniOS-009 G4)." Nothing is guessed.

In the preview: Mohit, Rahul and Anil → *Raise the seed round* (↑); Northwind → *Every vendor renewal decided before its notice date* (↓); Meera → *Hire the founding engineer* (↔); the StartupSetu portal → *StartupSetu recognition (DPIIT) certificate in hand* (↑); Priya, Harsh, Sameer and Cloudline → no goal.

## 6 · The look: fill, not borders (round three)

Rohit: *"kuch cards ko dark kar do, kuch ko white … border mat do; uski jagah thoda sa color idhar-udhar kar do, taaki cheezein zyada ubhar ke nikhar ke aayengi."* On the Screen page, cards have **no hairlines**; they stand out by fill and shadow:

| Fill | Used for | Why |
|---|---|---|
| **Dark** (`bg-ink`, white text) | the week band at the top · "In one line" (with who and due) in an open item · your own message in the rebuilt chat · the `Card …` tag | what must be read first |
| **White** with a soft shadow | sections · item rows · the rebuilt screen · "right away" small cards · "reasoned with" · "outcome" · popups · the cards inside an item and in "Cards your screen fed" | the content itself |
| **Grey tint** (`bg-surface/70`) | Read and Sort tiles · the "Right away" lane · the rules · the Show more tab bar and its small cards · a temporary item's strip · the box around a nested card | facts and framing, one step back |
| **Accent tint** (`bg-accent/[0.06]`) | the goal block · the "Next" lane · the goal tag on a row | what ties to a goal |
| **Ink tint** (`bg-ink/[0.05]`) | the kept strip and keep box of an item saved to the graph | kept, quietly marked |

- Controls keep a hairline (buttons, filter chips, menus): a button should look pressable.
- **How:** `intel/parts.tsx` · `Mini` takes `tone` — `line` (the default, the Goals look), `white`, `tint`, `accent`; `CardItem`, `CardDeck` and `CardBody` take `flat` (no hairline, white small cards inside). **Goals passes nothing, so Goals is unchanged.** If Rohit likes this look, Goals can switch by passing the same props.

## 7 · Screen and card: two things, linked both ways

| | Screen item | Card |
|---|---|---|
| What it is | what the screen **saw**: the words, who, where, when | what reasoning **concluded** needs you |
| Id | `S-XXXXXX` (the follow-up's `fu_…`) | `G-XXXXXX · C0N` under its goal, or `C-XXXXXX` |
| Leading mark | the app's mark (WA, SL, OL, IN, CH …) and its category tag | its number in a box (02) |
| Edge when open | ink | burgundy accent |
| Opens into | on your screen · the goal it moves · right away · what happens next | scenario · reasoning (the same `CardBody` as Goals) |
| Link | the dark `Card …` tag; "Outcome: fed card …"; the nested card | "Fed by S-… + other sources" |
| Where else | Screen only (private to you) | Cards, and under its goal on Goals |

- One item can feed one card; one card can be fed by many items (and by mail, calendar, documents). So the cards section lists each card once with all that fed it.
- The preview's five cards are the Goals preview's own, each with the screen quote added to its proof (`Screen · WhatsApp · S-9E07B3`), so a card reads the same on Goals, on Screen and — next — in Cards.

## 8 · Live vs preview, in one table

| | Preview (`?demo=1`, or localhost signed out) | Live, signed in, today |
|---|---|---|
| Items, categories, tags | 10 items over 3 days in all five categories, every tag | **real** (`GET /v1/followups?status=all`) |
| The screen, rebuilt | bubble / mail line / page line, due words marked | **real** from quote, app, who, time; nothing marked |
| In one line | who · what · by when | **real**: the item's `text` with its due |
| The goal it moves | 6 of 10 connected, with how and what is happening | "shows once goals and cards are linked (G4)" |
| Kept or temporary | 7 saved · 3 temporary, each with why | "saved" when `subject_node_id` is set; else "not in your context graph yet" |
| How it was read · popup per item · card it fed | all shown | "not served yet" |
| Week band, stages 3–5 | sample | **real** (weekly report, follow-ups, moments) |
| Stages 1–2, 6 counts | sample | "not served to this page yet" |
| Actions | disabled | **work** (Done · Snooze · Draft a reply · Done elsewhere · Dismiss; popup Useful / Wrong) |

Every "not served yet" is a brain change in `01-INTEGRATION.md` §5, with where it goes.

## 9 · Files

All paths are under `src/` in the dashboard repo.

```
app/dashboard/moments/page.tsx                renders ScreenPage (route kept)
product/internal/dashboard/screen/
  types.ts        Category · ScreenItem (kind, text, summary, state, words, who, app, due, instant, keep, reasoning, goal)
                  · GoalBrief · ScreenCard (fedBy) · ScreenPopup · ScreenWeek · ScreenView (items, cards, popups, goals, linked)
  sample.ts       SAMPLE_SCREEN_VIEW — 10 items, 5 cards and 6 goals (the Goals preview's own), 5 popups
  live.ts         liveScreenView(followups, report, moments) · appName
  screen-page.tsx ScreenPage · Overview (ON_DARK) · HowItWorks (Stage, RULES) · CATEGORY · ItemRow · ItemTags · CategoryTag
                  · ItemDetails (essentials + Show more tabs) · ScreenSnippet (Marked) · GoalStrip · KeepStrip · DidPanel
                  · GoesPanel · GoalLink · KeepBox · ItemActionsBar (⋯ menu) · FedBy · PopupRow · FilterChip
product/internal/dashboard/intel/parts.tsx    shared with Goals: CardItem (+ note, flat) · CardDeck (+ noteOf, flat)
                                              · CardBody (+ tone) · Mini (+ tone, MINI_TONE) · GroupLabel · Sub · Code
                                              · Toggle · RelationTag · RELATION · L1/L2/L3
lib/api-followups.ts                           listFollowups(status) · snoozeFollowup · draftFollowupReply; Followup gains
                                              quote, subject_node_id, remind_at, resolution, resolved_at; WeeklyReport gains
                                              nudged_then_closed, handled_elsewhere; resolution "handled"
```

Removed: `components/moments/screen-lanes.tsx`, `this-week-card.tsx`, `open-followups.tsx`.

## 10 · Agents, locked

- The **Agents** menu item shows a lock and "Locked", like Database or Custom tool.
- `/dashboard/agents` shows a locked panel instead of the registry. Agents already connected stay connected — nothing in the brain changes.
- Home: AER's locked overlay no longer links to Agents, and the "no agent" check has no link.
- To unlock: render `AgentsRegistryPage` in `app/dashboard/agents/page.tsx` again and drop `locked` on the Agents item in `sidebar.tsx`.
- Screenshot: `../01-NAVIGATION/agents-locked.png`.
