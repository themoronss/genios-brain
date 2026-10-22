# 05 · Screen: what the screen caught, and what became of it

**Written for:** Harsh (to wire it in) and Rohit (to review it). The step-by-step wiring — every field, every route, every brain change, the checks — is in **[`01-INTEGRATION.md`](01-INTEGRATION.md)**.

**Status, 22 Oct 2026:**
- Built on the dashboard branch `rohit/nav-grouping`, in three rounds: `9130f84` (the page), `972d122` (by category, tags, the screen rebuilt, kept or temporary), `9a13d87` (the goal each item moves; cards that stand out by fill, not borders). With `f151019` (the shared card parts) and `5c0504f` (Agents locked). **Not merged, so not live.**
- **Route:** `/dashboard/moments`, Intelligence ▸ **Screen**. Members can open it too.
- **Preview** (the full target, labelled "Preview — not your data"): `/dashboard/moments?demo=1`.
- `tsc --noEmit` and `next build` are green at `9a13d87`. Checked in the preview at 1440 and 1024 wide, and signed in against the stand-in brain (`../02-DASHBOARD-HOME/tools/mock_brain.py`): Draft a reply and Done ran end to end. The Goals page is unchanged by the shared-part changes (all 10 of its small cards keep their hairline).
- It replaces `../02-DASHBOARD-HOME/04-SCREEN.md` (the first, two-lane version).

**What Rohit asked, 22 Oct, in three rounds:**
1. *"Screen wale part mein thodi details daal do: kaise, kya, kis tareeke se hoga. Isi tarah ek dummy dikhayein."* and *"Screen aur cards … ek saath ho jaayein, lekin alag-alag rahein."* — and lock Agents.
2. On the built page: tag every row; *"categories honi chahiye ki Thursday ko kaun-kaun si cheezein kis-kis category mein aayi hain — reminder, update, risk, promise"*; show what was on screen; *"NLP ki madad se one-liner, clear cut"*; where and when properly; *"kuch important hoga to … context graph mein save ho jaayega; temporary rahega to wahin miss ho jaayega"*; *"customer ke hisaab se UX"*.
3. *"Ye kaun se goal ke saath connected hai … isse goal help ho raha hai aur ye cheezein ho rahi hain"*; and the look: *"kuch cards ko dark kar do, kuch ko white … border mat do; uski jagah thoda sa color idhar-udhar"*.

**Screenshots** (in `screens/`):

| File | What it shows |
|---|---|
| `screen-preview-top.png` | The preview as it opens: the week as a dark band, How Screen works. |
| `screen-preview-how-and-rules.png` | How Screen works with **The rules** open. |
| `screen-preview-by-category.png` | What your screen caught: the filters, Thursday's items under their categories, every row with its tags (the goal tag in accent). |
| `screen-preview-item-open.png` | An item open: the screen rebuilt (due words marked), in one line (dark), who · where · when · due. |
| `screen-preview-item-goal.png` | The same item: **the goal it moves**, what GeniOS did right away, and what happens next. |
| `screen-preview-item-card.png` | The card it fed, open inside the item. |
| `screen-preview-temporary.png` | A temporary item: no goal, not saved to the graph, and why. |
| `screen-preview-cards-popups.png` | Cards your screen fed, and the popups. |
| `screen-signed-in.png` | A signed-in seat against the stand-in brain: real items by category, one open; the goal block says the link is not served yet. |

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

## 4 · An item, opened

```
SCREEN ITEM #S-9E07B3 · seen on WhatsApp, Thursday 11:40         [Done][Snooze▾][Draft a reply][Done elsewhere][Dismiss]
ON YOUR SCREEN
 ┌ WhatsApp · chat with Mohit Rao ──────── 11:40 ┐  ┌█ IN ONE LINE (dark) ████████████████████████████████████┐
 │ ┌ Mohit Rao ───────────────────────────────┐   │  █ Mohit wants your traction one-pager before Northgate's  █
 │ │ Partners meet Monday — one-pager on       │   │  █ partner meeting on Monday, 9:00.                         █
 │ │ traction bhej doge _before that_?         │   │  └██████████████████████████████████████████████████████████┘
 │ Rebuilt from the words GeniOS kept — the screen itself is never stored.
 [Who: Mohit Rao · Northgate Capital] [Where: WhatsApp · a chat] [When: Today, 11:40] [Due: Mon 26 Oct, 09:00 · read from "before that"]
THE GOAL IT MOVES  (accent tint)
 (40%)  GOAL #G-3F2A9C ● On track   Raise the seed round · 2 of 5 funds in diligence · due 31 Dec      [Open the goal →]
 [How this item bears on it: ↑ Advances. This helps the goal: Northgate moving to a partner discussion.]
 [What is happening on the goal: 2 of 5 funds in diligence. Next · Reply to Rahul today; send Mohit the one-pager …]
WHAT GENIOS DID RIGHT AWAY · IN SECONDS     [Saved as: Deadline] [How it was read] [Reminders] [Popup]
WHAT HAPPENS TO IT NEXT · WITHIN THE HOUR
 [Kept or temporary: Important — saved to your context graph, on Mohit Rao at 12:00 …
   ✓ Follow-up › ✓ Context graph · Mohit Rao › ✓ Reasoning › ✓ Card G-3F2A9C · C02]    [Reasoned with] [Outcome]
THE CARD IT FED     [02] DECISION  Email Mohit a one-page traction summary …   (opens on its own: scenario · reasoning)
```

- **The screen, rebuilt.** The screen is never stored, so there is no screenshot to show. The page rebuilds what was seen from what *is* kept — the app, the person, the time and the ≤ 12 words — as a chat bubble (WhatsApp, Slack, LinkedIn …; your own message on the right, dark), a mail line (Outlook, Gmail) or a page line (a browser). The words that set the due date are marked.
- **In one line.** The instant read writes each item as one line (`text`, ≤ 140 characters) from the words on screen; the page shows it with the due it resolved. In the preview the lines read as who · what · by when.
- **The goal it moves.** See §5.
- **Kept or temporary.** Important → *saved to your context graph* on the person or company, private to you, reasoned over; the steps show how far it got. Temporary → *not saved to the graph*, with the reason, and the steps follow-up › reminders › closes › removed 90 days after. A temporary item has no "reasoned with" or "outcome": nothing reasons over it.

## 5 · The goal it moves (round three)

**What it shows, in an accent-tinted block right after "On your screen":**

| Part | Says | From (preview) | From (live, once served) |
|---|---|---|---|
| The goal | GOAL · `G-XXXXXX` · status dot and word · statement · progress · due · a ring with its % | the Goals preview's own goal | `GET /v1/goals` (GeniOS-009 G1 + G5) |
| How this item bears on it | **↑ Advances** / **↓ Threatens** / **↔ Depends on**, said plainly: "This helps the goal: …", "This puts the goal at risk: …", "The goal waits on this: …" — and *through what* | the card's own `reasoning.impact`, or set on the item | the G4 link of the card the item fed (`relation`, `through`) |
| What is happening on the goal | the goal's progress line, and its next move | the goal's `progress` and `nextMove` | `GET /v1/goals` (`progress`, `next_move`) |
| Open the goal | a link to Goals | `/dashboard/goals?demo=1` | `/dashboard/goals` |

- **On the row**, a connected item carries the goal as an accent tag: `↑ Raise the seed round`.
- **An item with no goal** says so in a grey line: "Not connected to a goal — nothing on your goal list depends on it." Temporary items have none.
- **An item can be connected without a card yet** — the preview's Anil item (two angel intros) advances the seed round before any card exists.
- **Live today** the block says: "Which goal it moves shows once goals and cards are linked (GeniOS-009 G4)." Nothing is guessed.

In the preview: Mohit, Rahul and Anil → *Raise the seed round* (↑); Northwind → *Every vendor renewal decided before its notice date* (↓); Meera → *Hire the founding engineer* (↔); the StartupSetu portal → *StartupSetu recognition (DPIIT) certificate in hand* (↑); Priya, Harsh, Sameer and Cloudline → no goal.

## 6 · The look: fill, not borders (round three)

Rohit: *"kuch cards ko dark kar do, kuch ko white … border mat do; uski jagah thoda sa color idhar-udhar kar do, taaki cheezein zyada ubhar ke nikhar ke aayengi."* On the Screen page, cards have **no hairlines**; they stand out by fill and shadow:

| Fill | Used for | Why |
|---|---|---|
| **Dark** (`bg-ink`, white text) | the week band at the top · "In one line" in an open item · your own message in the rebuilt chat · the `Card …` tag | what must be read first |
| **White** with a soft shadow | sections · item rows · the rebuilt screen · "right away" small cards · "reasoned with" · "outcome" · popups · the cards inside an item and in "Cards your screen fed" | the content itself |
| **Grey tint** (`bg-surface/70`) | who · where · when · due · Read and Sort tiles · the "Right away" lane · the rules · a temporary item's keep box · the box around a nested card | facts and framing, one step back |
| **Accent tint** (`bg-accent/[0.06]`) | the goal block · the "Next" lane · the goal tag on a row | what ties to a goal |
| **Ink tint** (`bg-ink/[0.05]`) | the keep box of an item saved to the graph | kept, quietly marked |

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
                  · ItemDetails · ScreenSnippet (Marked) · GoalLink · KeepBox · ItemActionsBar · FedBy · PopupRow · FilterChip
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
