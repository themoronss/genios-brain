# 05.1 · Screen: wiring it in

**Written for:** Harsh. Everything needed to take the Screen page live and make every part of it real, without asking: how to run it, what feeds each part, what each button calls, the brain changes in order (with where they go), the dashboard change each one needs, and the checks.

**State:** dashboard `9a13d87` on `rohit/nav-grouping` (not merged). What the page is and why: `README.md`.

---

## 1 · Run it

```bash
# the dashboard branch
git fetch origin && git checkout rohit/nav-grouping            # genios-brain-dashbaord

# A. the preview — every part filled with labelled sample data, no account needed
NEXT_PUBLIC_DEV_SKIP_LOGIN=1 npx next dev -p 3000
open "http://localhost:3000/dashboard/moments?demo=1"

# B. signed in, against the stand-in brain — real shapes, real buttons
python3 speedrun008/GeniOS-010/02-DASHBOARD-HOME/tools/mock_brain.py      # 127.0.0.1:8000, CORS for :3917
NEXT_PUBLIC_API_URL=http://localhost:8000 NEXT_PUBLIC_V2_BRAIN_URL=http://localhost:8000 npx next dev -p 3917
# plant a session in the browser console (02-DASHBOARD-HOME/06-RUN-AND-TEST.md §4), then open /dashboard/moments

# C. signed in, against a deployed brain
GENIOS_DEV_API_PROXY=https://api.thegenios.com NEXT_PUBLIC_DEV_SKIP_LOGIN=1 \
NEXT_PUBLIC_API_URL=http://localhost:3000/brain-api NEXT_PUBLIC_V2_BRAIN_URL=http://localhost:3000/brain-api npx next dev -p 3000

# checks
npx tsc --noEmit -p .   &&   npx next build
```

The stand-in brain serves `GET /v1/followups`, `GET /v1/moments`, the weekly report, and the writes: resolve, snooze, draft, popup feedback — in memory. One follow-up names a person not in the graph (no `subject_node_id`), one is answered, one done.

## 2 · How data flows

```
 brain (seat routes, Bearer, no cookies)              dashboard
 ─────────────────────────────────────                ───────────────────────────────────────────────────────────
 GET /v1/followups?status=all&limit=100  ─┐
 GET /v1/seats/me/weekly-report          ─┼─► screen-page.tsx (load) ─► live.ts · liveScreenView ─► ScreenView ─► the page
 GET /v1/moments?limit=50                ─┘     Promise.allSettled: one failing route never blanks the page
                                                 sample mode (?demo=1) ─► sample.ts · SAMPLE_SCREEN_VIEW ─► the same ScreenView
 POST /v1/followups/{id}/resolve|snooze|draft  ◄── item actions
 POST /v1/moments/{id}/feedback                ◄── popup Useful / Wrong
```

- **One shape, two sources.** `ScreenView` (in `screen/types.ts`) is filled by `sample.ts` in the preview and by `live.ts` when signed in. The components never know which. To make a part real, change `live.ts` only.
- The client calls are in `src/lib/api-followups.ts` and `src/lib/api-moments.ts` (`seatCall`: Bearer token, `X-GeniOS-Source: dashboard`, no cookies).

## 3 · What feeds each part

`✓` live today · `◐` live, partly · `✗` sample only until the brain change in §5.

| Part on screen | `ScreenView` field | Brain source | Live |
|---|---|---|---|
| **Week band**: donut by category | `week.byKind` | this week's follow-ups (by `created_at` ≥ Monday local), counted by `kind` | ✓ |
| promises kept · asks answered | `week.promises`, `week.asks` | weekly report `promises_caught/kept`, `asks_flagged/answered` | ✓ |
| open now | `items[].state` | follow-ups with no `resolution` | ✓ |
| **Stage 1 Read**, **Stage 2 Sort** counts | `week.read`, `week.skipped` | — | ✗ S8 |
| Stage 3 Save count | `week.saved` | this week's follow-ups | ✓ |
| Stage 4 popups shown · held back · closed after a reminder | `week.popups`, `week.wouldHaveMissed` | weekly report `popups_shown`, `nudged_then_closed`; held back = moments with `display: false` | ✓ |
| Stage 5 saved to graph | `week.memory` | this week's follow-ups with `subject_node_id` | ◐ (temporary not counted: S3) |
| Stage 6 cards | `week.cards` | — | ✗ S6 |
| **Row**: category tag | `kind` → `CATEGORY_OF` | follow-up `kind` | ✓ |
| title · who · app · time · due · how it ended | `text`, `who`, `app`, `seenAt`, `due`, `state`, `closed` | `text`, `who`, `app`, `created_at`, `due_at`, `resolution`, `resolved_at` | ✓ |
| tag: next reminder | `instant.reminders[0]` | `remind_at[]` | ✓ |
| tag: popup shown | `instant.popup` | — | ✗ S5 |
| tag: saved to graph / temporary | `keep.saved` | `subject_node_id` | ◐ S3 |
| tag: card · tag: goal | `reasoning.cardNumber`, `goal` | — | ✗ S6, S7 |
| **Open item**: the screen rebuilt | `quote`, `app`, `who`, `seenAt` | `quote`, `app`, `who`, `created_at` | ✓ |
| due words marked | `dueFrom` | — | ✗ S4 |
| In one line | `summary` | `text` + `due_at` (`live.ts`) | ✓ |
| Who · Where · When · Due | `who`, `app`, `day`, `seenAt`, `due` | as above | ✓ |
| The goal it moves | `goal` + `goals[]` | — | ✗ S7 |
| Saved as · Reminders | `kind`, `instant.reminders` | `kind`, `remind_at[]` | ✓ |
| How it was read | `instant.readBy` | — | ✗ S2 |
| Popup | `instant.popup` | — | ✗ S5 |
| Kept or temporary (+ at, + why) | `keep` | `subject_node_id` | ◐ S1, S3 |
| Reasoned with · Outcome · the card it fed | `reasoning` | — | ✗ S6 |
| **Cards your screen fed** | `cards[]` | — | ✗ S6 |
| **Popups** | `popups[]` | `GET /v1/moments`: headline, body, kind, display, suppressed reason, feedback | ✓ (link to item: S5) |

## 4 · What each button calls

| Button | Client | Route | Body | Brain | Page after |
|---|---|---|---|---|---|
| Done | `resolveFollowup(id, "done")` | `POST /v1/followups/{id}/resolve` | `{resolution:"done"}` | `followups.resolve` | row closes, "S-… done." |
| Done elsewhere | `resolveFollowup(id, "handled")` | same | `{resolution:"handled"}` | counted as `handled_elsewhere` | row closes |
| Dismiss | `resolveFollowup(id, "dismissed")` | same | `{resolution:"dismissed"}` | | row closes |
| Snooze ▾ | `snoozeFollowup(id, "1h" \| "tonight" \| "tomorrow")` | `POST /v1/followups/{id}/snooze` | `{preset}` | `followups.snooze` (seat's zone) | "the next reminder moved to …" |
| Draft a reply | `draftFollowupReply(id)` | `POST /v1/followups/{id}/draft` | — | `reply_draft.draft` — in the quote's language; never stored or sent; 204 when no model | the draft, with Copy |
| Useful / Wrong ▾ | `sendMomentFeedback(id, "acted", "useful")` / `(id, "wrong", reason)` | `POST /v1/moments/{id}/feedback` | `{action, reason, at}` | `record_feedback`; on a screen popup, "Wrong" mutes that thread's popups for 7 days (`followups.learn_from_feedback`) | "Noted" |

All are disabled in the preview. A failed call shows its message and changes nothing.

## 5 · Brain changes, in order — each one makes a part real

Each is small and independent. After each, change `screen/live.ts` as shown; no component changes.

**S1 · Memory time.** `graph_written_at` and `observation_id` are already columns on `screen_followups` (0162, 0211).
- *Brain:* add both to `followups.item_out`.
- *Dashboard (`live.ts · itemOf`):* `keep.at = hhmm(local(f.graph_written_at))`.

**S2 · How it was read.** New column `screen_followups.read_by text` (`rule` · `quick_read` · `hourly_batch`).
- *Brain:* set it where `followups.upsert` is called — `screen_rules` (rule), `screen_insight` (quick read), `screen_memory_batch` (hourly batch). Add to `item_out`.
- *Dashboard:* `instant.readBy = f.read_by`.

**S3 · Kept or temporary, and why.** The keep decision exists per thread: `screen_thread_verdicts.memory` (0160), keyed `(org_id, seat_id, thread_key)`.
- *Brain:* in `followups.listing`, left-join the verdict on `thread_key` and return `remember` (true / false / null) and a short `keep_reason`: `person_unknown` (remember true, no `subject_node_id` after promotion), `not_memory` (remember false), `personal` (work false).
- *Dashboard:* `keep.saved = f.subject_node_id ? true : f.remember === false ? false : null`, and `keep.why` from `keep_reason`.

**S4 · The due words.** New column `screen_followups.due_phrase text` (e.g. "kal tak").
- *Brain:* `screen_rules` already has the date marker it matched; for the quick read, add `due_phrase` to the model's item JSON (v5) and keep it only if it is inside the quote (the same grounding as the quote).
- *Dashboard:* `dueFrom = f.due_phrase ? \`read from “${f.due_phrase}”\` : undefined` — the snippet then marks it.

**S5 · The popup for an item.** New column `screen_followups.moment_id text`.
- *Brain:* `POST /v1/moments/evaluate` computes `moment_id = M.server_moment_id(...)` before it saves the items — write it on the items it upserts in that call.
- *Dashboard:* join `followups` to `moments` by `moment_id` in `liveScreenView` → `instant.popup = {shown, text: headline, why}` and `popups[].item = code`.

**S6 · The card an item fed.** Needs a stored link; nothing joins a card to a follow-up today.
- *Brain:* when the card builder reads a `screen.<kind>` observation as evidence, record it — e.g. a table `card_screen_items(org_id, card_id, followup_id)` written beside the card (the follow-up names its observation: `observation_id`, 0211). Serve `card_ids[]` on each follow-up and `screen_items[] {followup_id, app}` on `GET /cards/{id}`; and weekly `cards_from_screen`.
- *Dashboard:* `reasoning = {cardNumber, with}`; `cards[]` from `GET /cards/{id}` of those ids, mapped with `goals/live.ts · cardItem`; set `linked: true`. The "Fed a card" filter turns on by itself.

**S7 · The goal an item moves.** Waits on GeniOS-009 G4 (goal ↔ situation links: `relation`, and a `through` line) and G1 + G5 (`GET /v1/goals`).
- *Default rule:* an item's goal is the goal of the card it fed (S6 + G4). An item with no card has no goal.
- *Dashboard:* `goals[]` from `GET /v1/goals` (code, statement, status, pct, progress, due, next move — the fields in `03-GOALS/01-GOALS-PAGE.md` §5); `item.goal = {code, relation, through}` from the card's link.

**S8 · Read and skipped counts.** Already counted in `rate_counters` per seat per UTC day: kind `screen_insight` (judged) and `screen_insight_skipped` (refused by triage, `screen_insight.SKIPPED_KIND`).
- *Brain:* add `screens_read` (judged + skipped + rule-answered) and `screens_skipped` to `followups.weekly_report`, and `threads_to_memory` (promoted `screen_session` events, or `screen_memory_batch` jobs).
- *Dashboard:* `week.read`, `week.skipped` from the report.

## 6 · Checks before you call a part done

1. `npx tsc --noEmit -p .` and `npx next build` green.
2. **Preview** (`?demo=1`) at 1440 and 1024 wide: no horizontal scroll; Mohit's item (S-9E07B3) opens by itself, with its goal and the card it fed.
3. **Signed in** against the stand-in brain: 5 items over three days; Priya's item shows the rebuilt chat, the line with its due, "Saved to graph"; **Draft a reply** shows "Hi Priya, on it …"; **Done** closes it and the stand-in brain's `GET /v1/followups` returns `"resolution": "done"` for it.
4. **After each brain change S1–S8**, the matching "not served yet" text is gone from a signed-in page, and nothing else changed (compare against `screens/screen-signed-in.png`).
5. Goals is untouched: on `/dashboard/goals?demo=1` every small card still has its hairline.

## 7 · Merge notes

- **Files touched for Screen:** `app/dashboard/moments/page.tsx` (now one line), `product/internal/dashboard/screen/*` (new), `product/internal/dashboard/intel/parts.tsx` (new, shared with Goals), `lib/api-followups.ts` (additive). Removed: `components/moments/screen-lanes.tsx`, `this-week-card.tsx`, `open-followups.tsx` (nothing else imported them).
- **No change to** `globals.css`, `lib/api-moments.ts` or any brain code.
- **Shared parts:** `intel/parts.tsx` is what Goals draws with, and what the Cards page should use next. New options are additive with defaults (`tone="line"`, `flat=false`), so Goals is unchanged. The other session working on Cards should build on it rather than a second card component.
- **Privacy, kept as it was:** the page only ever reads the seat's own follow-ups and moments (`seatCall`); owners and admins see their own, never a teammate's.
