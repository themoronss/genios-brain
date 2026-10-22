# 05 · Screen: what the screen caught, and what became of it

**Written for:** Harsh (to wire it in) and Rohit (to review it).

**Status, 22 Oct 2026:**
- Built on the dashboard branch `rohit/nav-grouping`: `9130f84` (the page), `972d122` (by category, tags, the screen rebuilt, kept or temporary), with `f151019` (the shared card parts) and `5c0504f` (Agents locked). Not merged, so not live.
- **Route:** `/dashboard/moments`, Intelligence ▸ **Screen**. Members can open it too.
- **Preview** (the full target, labelled "Preview — not your data"): `/dashboard/moments?demo=1`.
- `tsc --noEmit` and `next build` are green. The page was checked signed in against the stand-in brain (`../02-DASHBOARD-HOME/tools/mock_brain.py`): Draft a reply and Done ran against it end to end.
- This replaces `../02-DASHBOARD-HOME/04-SCREEN.md` (the first, two-lane version).

**Rohit's ask, 22 Oct:**
- *"Screen wale part mein thodi details daal do: kaise, kya, kis tareeke se hoga. Isi tarah ek dummy dikhayein ki screen ka part kaise kaam karega."*
- *"Screen aur cards dono lagbhag ek hi tareeke se similar type mein dikhne wale hain, isliye dono ko smartly play karein taaki screen aur card ek saath ho jaayein, lekin alag-alag rahein."*
- And: lock the Agents part.

**Second round, same day** (on the built page): *"What your screen caught … tag lagana chahiye tha … categories honi chahiye ki Thursday ko kaun-kaun si cheezein kis-kis category mein aayi hain — reminder, update, risk, promise"*; when an item opens, show what was on screen; *"the words that caused it — NLP ki madad se one-liner, clear cut"*; where / when properly; and *"kuch important hoga to memory mein, reasoning mein, context graph mein save ho jaayega; temporary rahega to wahin miss ho jaayega"*. *"Customer ke hisaab se UX."* All of it is in `972d122`, below.

**Screenshots** (in `screens/`):

| File | What it shows |
|---|---|
| `screen-preview-top.png` | The preview as it opens: the week by category, How Screen works. |
| `screen-preview-how-and-rules.png` | How Screen works with **The rules** open. |
| `screen-preview-by-category.png` | What your screen caught: the category and "show" filters, Thursday's items under their categories, every row with its tags. |
| `screen-preview-item-open.png` | An item open: the screen rebuilt (the due words marked), in one line, who · where · when · due, what GeniOS did right away. |
| `screen-preview-item-next.png` | The same item: kept (saved to the context graph on Mohit Rao, reasoned over) and the card it fed, open. |
| `screen-preview-temporary.png` | A temporary item: a follow-up that is not saved to the graph, and why. |
| `screen-preview-cards-popups.png` | Cards your screen fed, and the popups. |
| `screen-signed-in.png` | A signed-in seat against the stand-in brain: real items by category, one open. |

---

## 1 · How Screen works (what the page explains, and what the brain does)

Every **work** screen takes **both** paths. The instant path saves what to do now; the memory path lets reasoning join it with everything else.

```
 1 Read ─────► 2 Sort ──┬─► AT ONCE (seconds) ── 3 Save ── follow-ups ──► 4 Remind · popup (only if it adds)
 a few seconds   free   │
                        └─► NEXT (hourly) ────── 5 Keep or let go ── important: context graph ──► 6 Reason → card (under its goal)
                                             temporary: stays a follow-up, removed 90 days after it closes
```

| # | Stage | What happens | Brain |
|---|---|---|---|
| 1 | **Read** | You stay on a chat, a mail or a page for a few seconds; the desktop app reads what is visible. Never-read apps, a diff, the 24 h verdict and dwell are checked first. | desktop app; router checks 1–4 (`reason/moments/screen_rules.py` docstring) |
| 2 | **Sort** | Free. A conversation is always judged; a page is judged only if it names someone in the graph, has a participant with an email/LinkedIn, or is a work app or site. The rest is skipped, counted with its reason — and still reaches the hourly batch, late and cheap. | `reason/moments/screen_triage.py` |
| 3 | **Save** | A **rule** answers when a sender writes a clear ask or promise with a date (free; the quote is the item). Otherwise **one quick read** (one model call) returns `work`, `remember` and up to 3 items: kind, text, who, due, quote. An item whose quote is not on screen is dropped. Saved as `screen_followups`. | `screen_rules.py`, `screen_insight.py`, `followups.upsert` |
| 4 | **Remind · popup** | Reminders before each due time (heads-up → final → overdue). A popup **only** when it adds something the screen does not say: a repeat ask, a promise owed, a calendar clash, the same ask elsewhere, an urgent risk. Held back by popups-off, the hourly cap, do-not-disturb or a duplicate — and still listed. | `screen_insight.py` (the product rule), `moments` |
| 5 | **Keep or let go** | **Important** items are saved to the context graph: at most once an hour per thread, the thread becomes a seat-private source event, and each item is written as an observation (`screen.<kind>`) on the person or company it is about — **only one GeniOS already knows**; a screen never creates a person. **Temporary** items (the model's `remember: false`, a throwaway thread, or a person not in the graph) stay follow-ups and are removed 90 days after they close. The hourly batch (half price) catches what the instant read never saw. | `screen_insight.py` (`remember`), `platform/screen_promoter.py`, `screen_memory.py`, `screen_memory_batch.py`, `followups.purge` |
| 6 | **Reason → card** | From memory, the item is reasoned over with mail, calendar and documents, like any other evidence. A situation that needs you becomes a **card** — in Cards, and under its goal. | L1 → L3 → L2 → cards |

**The rules** (a toggle on the page): never read · what is kept (never the screen; a fingerprint and ≤ 12 words; the hourly text is encrypted and deleted once done) · when a popup shows · who sees it (only you; owners and admins never) · what it costs · where it ends up (follow-ups here, as reminders and in your morning brief; cards in Cards and under their goal).

## 2 · The page, top to bottom

1. **Header:** Intelligence · Screen, one line, and "Only you see this page."
2. **The week on one strip:** a donut of items **by category**, then open now · promises kept · asks answered.
3. **How Screen works:** the six stages above, each with this week's count, and **The rules** (never read · what is kept · important or temporary · when a popup shows · who sees it · what it costs).
4. **What your screen caught:**
   - **Filters:** *Category* (All · Asked of you · Deadlines & reminders · Risks · Promises · Updates & next steps) and *Show* (Everything · Open · Closed · Saved to graph · Temporary · Fed a card), each with a count.
   - **By day, newest first.** The day line says how many came in each category ("1 asked of you · 1 deadline · 1 risk · 1 promise").
   - **Inside a day, by category,** in a fixed order, each with its count and one line of what it means ("someone is waiting on your answer").
5. **Cards your screen fed:** each card once, with the screen items that fed it.
6. **Popups:** shown and held back, with Useful / Wrong.

## 3 · Categories, tags, and an item

**Five categories, from the six kinds the brain saves:**

| Category | Kinds (`followups.KINDS`) | Row tag | Means |
|---|---|---|---|
| Asked of you | `ask` | Asked of you | someone is waiting on your answer |
| Deadlines & reminders | `deadline` | Deadline | a date GeniOS reminds you before |
| Risks | `risk` | Risk | it costs you if it is missed |
| Promises | `my_promise`, `their_promise` | Your promise · Their promise | yours to keep, or theirs to watch |
| Updates & next steps | `next_step` | Update | something changed, and a step follows |

**Tags on every row:** the category tag first, then — after who · app · time — the next reminder (`Reminder Fri 10:00`), `Popup shown`, `Saved to graph` or `Temporary` (dashed), and the card it fed (`Card G-3F2A9C · C02`, dark). On the right: when it is due, or how it ended.

**An item, opened:**

```
SCREEN ITEM #S-9E07B3 · seen on WhatsApp, Thursday 11:40      [Done][Snooze▾][Draft a reply][Done elsewhere][Dismiss]
ON YOUR SCREEN
 ┌ WhatsApp · chat with Mohit Rao ──────────── 11:40 ┐  ┌ IN ONE LINE ─────────────────────────────────────┐
 │ ┌ Mohit Rao ───────────────────────────────────┐  │  │ Mohit wants your traction one-pager before        │
 │ │ Partners meet Monday — one-pager on traction  │  │  │ Northgate's partner meeting on Monday, 9:00.      │
 │ │ bhej doge _before that_?                      │  │  │ Written from the words on screen: who, what, when │
 │ └───────────────────────────────────────────────┘  │  └───────────────────────────────────────────────────┘
 │ Rebuilt from the words GeniOS kept — your screen itself is never stored.
 [Who: Mohit Rao, Northgate Capital] [Where: WhatsApp, a chat] [When: Today, 11:40] [Due: Mon 26 Oct, 09:00 — read from "before that"]
WHAT GENIOS DID RIGHT AWAY · IN SECONDS    [Saved as: Deadline] [How it was read] [Reminders] [Popup]
WHAT HAPPENS TO IT NEXT · WITHIN THE HOUR
 [Kept or temporary: Important — saved to your context graph, on Mohit Rao at 12:00 …
   ✓ Follow-up › ✓ Context graph · Mohit Rao › ✓ Reasoning › ✓ Card G-3F2A9C · C02]   [Reasoned with] [Outcome]
THE CARD IT FED   ┌┄ [02] DECISION  Email Mohit a one-page traction summary …   (opens on its own: scenario · reasoning) ┄┐
```

- **The screen, rebuilt.** The screen is never stored, so there is no screenshot to show. The page rebuilds what was seen from what *is* kept — the app, the person, the time and the ≤ 12 words — as a chat bubble (WhatsApp, Slack, LinkedIn …; "You" on the right for your own promise), a mail line (Outlook, Gmail) or a page line (a browser). The words that set the due date are marked.
- **In one line.** The instant read writes each item as one line (`text`, ≤ 140 characters) from the words on screen; the page shows it with the due it resolved. In the preview the lines are written to read as who · what · by when.
- **Kept or temporary.** Important → *saved to your context graph* on the person or company, private to you, and reasoned over; the steps show how far it got (follow-up › context graph › reasoning › card). Temporary → *not saved to the graph*, with the reason, and the steps follow-up › reminders › closes › removed 90 days after. A temporary item has no "reasoned with" or "outcome": nothing reasons over it.

**Screen and card are two different things, drawn as two different things, linked both ways.**

| | Screen item | Card |
|---|---|---|
| What it is | what the screen **saw**: the words, who, where, when | what reasoning **concluded** needs you |
| Id | `S-XXXXXX` (the follow-up's `fu_…`) | `G-XXXXXX · C0N` under its goal, or `C-XXXXXX` |
| Leading mark | the app's mark (WA, SL, OL, IN, CH …) and its category tag | its number in a box (02) |
| Edge when open | ink | burgundy accent |
| Opens into | on your screen · right away · what happens next | scenario · reasoning (the same `CardBody` as Goals) |
| Link | the dark `Card …` tag; "Outcome: fed card …"; the nested card | "Fed by S-… + other sources" |
| Where else | Screen only (private to you) | Cards, and under its goal on Goals |

- One item can feed one card; one card can be fed by many items (and by mail, calendar, documents). So the cards section lists each card once with all that fed it.
- The card is drawn with the **same component** Goals uses (`intel/parts.tsx` · `CardItem`, `CardBody`), so a card reads the same on Goals, on Screen and — next — in Cards.
- The preview's five cards are the Goals preview's own cards, each with the screen quote added to its proof (`Screen · WhatsApp · S-9E07B3`).

## 4 · Live vs preview

| | Preview (`?demo=1`, or localhost signed out) | Live, signed in, today |
|---|---|---|
| Items, categories, tags | 10 items over 3 days in all five categories, every tag | **real** — `GET /v1/followups?status=all`: kind (→ category), text, who, app, due, the quote, reminders, how it ended |
| The screen, rebuilt | the quote as a bubble / mail line / page line, due words marked | **real** from the quote, app, who and time; nothing is marked (the due's source words are not served) |
| In one line | written as who · what · by when | **real**: the item's `text` with its due |
| Kept or temporary | 7 saved (on whom, at what time, why) · 3 temporary (why) | **real** "saved" when `subject_node_id` is set; otherwise "not in your context graph yet" — temporary vs not-yet is not served |
| How it was read | rule · one quick read · hourly batch | "not served yet" |
| Popup per item | which popup, shown or held and why | not linked to items yet (popups are listed below, live) |
| Card it fed · Cards your screen fed | the card, nested, and the five cards | "linked once the brain serves it" (B8) |
| Week strip | from the sample | **real**: this week's items by kind; promises kept and asks answered from the weekly report |
| Stages 1–2 counts | 64 read · 27 skipped | "counted in the brain — not served to this page yet" |
| Stages 3–5 counts | sample | **real**: items saved, popups shown/held, items in memory |
| Actions | disabled | **work**: Done · Snooze (in an hour / tonight / tomorrow) · Draft a reply (shown, not sent, not stored) · Done elsewhere · Dismiss; popups Useful / Wrong |

## 5 · What the brain should serve so every part is real (B8, expanded)

| On screen | Field (proposal) | Where it comes from |
|---|---|---|
| How it was read | `read_by` on each follow-up: `rule` · `quick_read` · `hourly_batch` | which path called `followups.upsert` (`screen_rules`, `screen_insight`, `screen_memory_batch`) |
| Kept or temporary, and why | `remember` (the verdict's `memory`) and a short `keep_reason` on each follow-up | the instant judge's `remember`; `subject_node_id` null with `remember: true` = the person is not known |
| The due words to mark | `due_phrase` on each follow-up (e.g. "kal tak") | the rule or the model that resolved the due |
| Memory · at | `graph_written_at` on each follow-up | already a column — add it to `item_out` |
| Popup for this item | `moment_id` on each follow-up (or `followup_id` on the moment) | the insight call that produced both |
| The card it fed | `card_ids[]` on each follow-up | cards whose evidence includes the follow-up's `observation_id` (0211) |
| Fed by (on a card) | `screen_items[] {followup_id, app}` on `GET /cards/{id}` | the same join, the other way |
| Stage 1–2 counts | `screens_read`, `screens_skipped` on the weekly report | triage counts with reasons (`screen_triage`; already surfaced in `GET /v1/capture/policy`) |
| Stage 5–6 counts | `threads_to_memory`, `cards_from_screen` on the weekly report | promoted `screen_session` events / `screen_memory_batch` jobs; the card join above |

**How the dashboard uses it:** `screen/live.ts` maps each field when it appears, and `liveScreenView` sets `linked: true` once `card_ids` arrive. The components do not change — the preview already draws this shape.

## 6 · Files

All paths are under `src/` in the dashboard repo.

```
app/dashboard/moments/page.tsx                renders ScreenPage (route kept)
product/internal/dashboard/screen/
  types.ts        Category · ScreenItem (kind, text, summary, state, words, who, app, due, instant, keep, reasoning)
                  · ScreenCard (fedBy)
                  · ScreenPopup · ScreenWeek · ScreenView
  sample.ts       SAMPLE_SCREEN_VIEW — 10 items, 5 cards (the Goals preview's own), 5 popups
  live.ts         liveScreenView(followups, report, moments) · appName
  screen-page.tsx ScreenPage · Overview · HowItWorks (Stage, RULES) · CATEGORY · ItemRow · ItemTags · CategoryTag
                  · ItemDetails · ScreenSnippet (Marked) · KeepBox · ItemActionsBar · FedBy · PopupRow · FilterChip
product/internal/dashboard/intel/parts.tsx    shared with Goals: CardItem (+ note) · CardDeck (+ noteOf) · CardBody · Mini
                                              · GroupLabel · Sub · Code · Toggle · RelationTag · L1/L2/L3
lib/api-followups.ts                           + listFollowups(status) · snoozeFollowup · draftFollowupReply; Followup gains
                                              quote, subject_node_id, remind_at, resolution, resolved_at; WeeklyReport gains
                                              nudged_then_closed, handled_elsewhere; resolution "handled"
```

Removed: `components/moments/screen-lanes.tsx`, `this-week-card.tsx`, `open-followups.tsx` — the page's items, week strip and stages replace them.

## 7 · Agents, locked (same round)

- The **Agents** menu item shows a lock and "Locked", like Database or Custom tool.
- `/dashboard/agents` shows a locked panel instead of the registry. Agents already connected stay connected — nothing in the brain changes.
- Home: AER's locked overlay no longer links to Agents ("Agents are locked for this release …"), and the "no agent" check has no link.
- To unlock: render `AgentsRegistryPage` in `app/dashboard/agents/page.tsx` again and drop `locked` on the Agents item in `sidebar.tsx`.
- Screenshot: `../01-NAVIGATION/agents-locked.png`.
