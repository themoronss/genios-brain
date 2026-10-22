# 06.1 · Cards: wiring it in

**Written for:** Harsh. Everything needed to take the Cards page live and make every part of it real, without asking:
- how to run it;
- what feeds each part;
- what each button calls;
- the brain changes in order, with where they go and the dashboard change each one needs;
- the checks;
- the merge notes.

Code facts are at dashboard `rohit/cards-ux` `25553ab` and brain `21b7ae10` (`harsh/mvp`). Line numbers are at those commits.

---

## 1 · Run it

```bash
# the dashboard branch (it sits on top of rohit/nav-grouping)
git fetch origin && git checkout rohit/cards-ux && npm ci

# A. signed in, against the stand-in brain — real card shapes, every button
python3 speedrun008/GeniOS-010/06-CARDS/tools/mock_cards.py          # 127.0.0.1:8031, CORS for :3931
NEXT_PUBLIC_API_URL=http://localhost:8031 NEXT_PUBLIC_V2_BRAIN_URL=http://localhost:8031 npx next dev -p 3931
#   plant a session in the browser console (02-DASHBOARD-HOME/06-RUN-AND-TEST.md §4), then open /dashboard/cards
#   or render it: node speedrun008/GeniOS-010/06-CARDS/tools/shoot_cards.mjs <out-dir>

# B. signed in, against the live brain — your own cards
GENIOS_DEV_API_PROXY=https://api.thegenios.com \
NEXT_PUBLIC_API_URL=http://localhost:3002/brain-api NEXT_PUBLIC_V2_BRAIN_URL=http://localhost:3002/brain-api \
npx next dev -p 3002
#   sign in at http://localhost:3002/auth/login, open Cards

# checks
npx tsc --noEmit -p .
npx next build
```

**Two traps:**
- **A linked `node_modules` (a git worktree that symlinks it)** makes Turbopack refuse with *"Symlink … points out of the filesystem root"*. Use `next dev --webpack` and `next build --webpack` there. A plain clone with its own `npm ci` needs neither.
- **One `next dev` per checkout.** Stop the one on :3002 before starting :3931 in the same folder.

## 2 · How data flows

```
 brain (L5 Delivery, deliver/ + api/routes.py)                     dashboard
 ────────────────────────────────────────────                      ─────────
 GET /cards                     the queue (card_id, headline,  ─┐
                                situation, urgency, state,      │
                                render_mode, domain, …)         │
 GET /cards/{id}  ×≤40          card.v1 + context +             ├─► lib/card-read.ts  readCard()
                                actionability + decision        │      ↓ sharedTexts / sharedLines
 GET /cards/{id}/timeline       the card's events (versions,    │      ↓ ownCard()  (only this card's own)
                                who acted where)                │   app/dashboard/cards/page.tsx
 GET /cards/history             closed cards                   ─┘      list · panel · buttons
 GET /api/org/{org}/members     the team (owner/admin)        ───► Delegate ▸ A person
 GET /v1/agents                 the agent registry            ───► Delegate ▸ An agent
 POST /cards/{id}/action        do_it_myself · snooze · requeue · wrong · answer
```

**What happens when the page loads:**
1. It reads `/cards` and `/cards/history`.
2. It reads `/cards/{id}` for up to 40 open cards in parallel (`MAX_DETAILS`), for the tags, who and the lane. C3 removes that.
3. It reads a card's timeline when the card is opened.
4. It polls every 45 s while visible, and refreshes on return to the tab.

## 3 · What feeds each part

| Part | Field(s) | Brain source (L5 unless said) | Today |
|---|---|---|---|
| Group (Decide · Answer · Waiting · Two sources disagree) | `render_mode === "question"`, `output_lane` | queue row; `card_builder` (`output_lane` from `reason/output_lane.route`) | live |
| Tool tags (Gmail · mail thread, Calendar · N meetings, CRM) | `context_tags`, `why[].source`, `context.interactions` | `card_builder._context_tags`; `_card_intelligence` | live |
| Subject | `headline` (a question card: `why[0].question`) | `card_builder` (expert: `gold_headline`, the move cut at a clause) | live; clarity → **C1** |
| Two lines: what to do · how | `recommended.what` · first step | gold lines (`reason/expert/decide._render`) · `decision.recommendation.steps` | expert cards; formula cards get the projection → **C1** |
| Recommendation | `recommended{who,what,for_whom,by_when}`, `decision.recommendation{objective,steps,avoid}`, `actionability` | gold; `api/routes._decision_projection` (`:5107`); `_actionability` | live; stock steps hidden by the guard → **C1** |
| What · Why · How | `situation`; `why_now` → else the question's why → else `do_nothing_consequence` → else what remains; the first step | `card_builder.build_draft` | live |
| What doing it gets you | `success_signal`, `do_nothing_consequence`, `alternative`, `wait_or_stop` | `card_builder._play_success`; the capability manifest; gold | live, often stock → **C2**, **C1** |
| Goal it moves | none | none | "Not linked to a goal yet" → **C1** (suggested), **C8** (linked) |
| Deadline | `recommended.by_when`, `outcome_window_days`, `context.commitments[].due_at`, upcoming `context.interactions[].start_at` | gold; `card_builder`; `_commitment_neighbors` / `_meeting_neighbors` | live |
| Details | `business_subject`, `relationship_role` (engine words mapped: `intro` → "introduced to you", `connector` → "made the introduction", `watched` → hidden); `why[]` | gold / `party.role`; `card_builder._why`, `_sentence_sources`, `_window_receipt`; `_card_intelligence` | live; quotes lack sender and date → **C4** |
| Where the data came from | tools; dated `thread.last_inbound` / `last_outbound`, meetings, promise due dates | as above | live |
| Version | count of `card.rebuilt` events + 1 | `card_events` via `/cards/{id}/timeline` | live; what changed → C9 (later) |
| What happened to this card | timeline events | `CardStore.timeline` | live |

**How `why[]` rows are read** (`readCard`; each row becomes one line, or none):

| Row shape | Line |
|---|---|
| `{sentence:"headline", quotes:[…], source:"expert_check"}` | each quote, in quotes, from the card's tool |
| `{sentence:"headline", question, because}` | the question card's ask and its "why we ask" |
| `{sentence, inference}` | **not shown.** It is a label ("an inference, not a quote"), not proof |
| `{field, value, source}` | a plain line: "Divya last wrote — 13 Sep, 3:42 pm", "The next reply is yours", "Promised: '…'" |
| `{statement, source:"expertise"}` | the doctrine line, labelled "{Domain} expertise" |
| `{window, days}`, `{evidence_id}`, `{review}` | not shown; the window is shown under Deadline |

## 4 · What each button calls

| Button | Call | Body | Shown when |
|---|---|---|---|
| Done | `POST /cards/{id}/action` | `{action:"do_it_myself", surface:"web"}` | the card offers `do_it_myself`; never on a question card |
| Answer → Send answer | same | `{action:"answer", words}` | the card offers `answer` |
| Later → 4 hours / tomorrow 9:00 / 3 days | same | `{action:"snooze", snooze_option}` | the card offers `snooze` (its own options, `custom` aside) |
| Later → a day you pick | same | `{action:"snooze", snooze_option:"custom", custom_until:"<that day 09:00 local, ISO>"}` | same |
| Bring back | same | `{action:"requeue"}` | a put-off card |
| Feedback → Send | same | `{action:"wrong", reason, words, scope:"file"\|"kind"\|"company"}` (`words` = *"It is wrong because …. It should be: …"*) | always; `kind`/`company` refused for non-owners (`owner_only`, shown as a sentence) |
| Delegate → Hand over / Ask it | **locked** (`DELEGATE_LIVE = false` in `page.tsx`) | — | lists `/api/org/{org}/members` (active, yourself left out) and `/v1/agents` (active) |

**On errors:**
- Every error code the brain returns is turned into a sentence: `not_offered`, `answer_says_nothing`, `answer_too_long`, `invalid_wrong_reason`, `invalid_correction`, `owner_only`, `unknown_action`, `assigned_to_different_seat`.
- The sentence stays in the panel's footer until the next press.

## 5 · Brain changes, in order — each one makes a part real

Every change below is L5 Delivery (`deliver/`, `api/routes.py`) unless marked otherwise. Each one takes:
- its own tests and mutation proof;
- CI;
- Harsh's deploy.

**Order:** C6 and C2 (small, and they end the "same details" and "no result" complaints) → C1 → C4 → C3 → C5 → C7 → C8.

### C6 · Context scoped to the card, not to the person

- **Why:**
  - `_card_intelligence` attaches the subject node's last four meetings (`_meeting_neighbors`, `routes.py:5253`) and three promises (`_commitment_neighbors`, `:5228`).
  - Cards anchored on one node all show the same ones. Rohit: *"poora Y har card mein hi same hai"*.
- **Change:** keep only meetings and commitments tied to **this card's** thread or evidence:
  - the same thread id;
  - or an event among the card's evidence or sentence sources.
- **Test:** two cards on one person with different threads show different context.
- **Dashboard:** none. The guard (`sharedLines`) stays as a safety net.
- **Also verify on production first:** do live cards anchor on one node (the founder's)? This needs Rohit's OK for a read-only query.

### C2 · The expert's result reaches the card

- **Why:**
  - The expert review writes `scenarios.act` ("if you act now") and `done_when`.
  - Neither is in the gold block, which `reason/expert/decide._render` builds at `decide.py:323`. So the card has no "what doing it gets you" of its own.
- **Change:**
  - Add `act` and `done_when` to `gold`, as **checked** words. `done_when` is already in `CheckedReview.words`; `act` must be held by the check (`reason/expert/verify`) like the other sentences.
  - `card_builder` writes a new `result` key from `gold.act`, and `success_signal` from `gold.done_when`.
- **Dashboard:** `readCard` reads `result` into "What doing it gets you · Result" (one line in `card-read.ts`).

### C1 · The card writer

**Why:** the subject, the two lines, the steps, the result and the goal must be clear and specific to each card. Rohit:
- *"subject line bhi spasht"*;
- *"NLP ki madad se headline ko clear karo"*;
- *"isko karne se kya hoga"*;
- *"kaun sa goal effect hoga"*.

**Where:** a new `deliver/card_copy.py`.
- **When it is called:** from where `deliver/pipeline.py` builds or versions a card, after `card_builder.build_draft` and the claim check.
- **How often:** one call per **new card version**, never per view.

**What it reads (only this card's own):**
- the quoted lines;
- the thread facts;
- the gold lines;
- the expert review (`scenarios.act`, `done_when`, `appraisal`);
- the company brief's accepted goals (`company_brief_lines`, section `goals`).

**What it writes:**

```json
{"subject": "verb first, ≤ 10 words, names the person or thing",
 "summary": "≤ 2 lines: what to do and how",
 "steps": ["2–4 steps"],
 "result": "what doing it gets you",
 "goal": {"line_id": "cbl_…", "how": "advances | threatens | depends_on", "why": "one line"} ,
 "rests_on": {"subject": ["fact ids"], "summary": [...], "steps": [...], "result": [...], "goal": [...]}}
```

- `goal` is `null` when no accepted goal is served.
- **Each sentence is checked like the expert's words.** A sentence that rests on nothing is dropped, never shipped.
- **Stored:** a new `cards.copy jsonb` (migration), versioned with the card.
- **Served:**
  - `CardStore.queue` (`store.py:772`) returns `copy.subject` and `copy.summary`;
  - `get_card` returns all of it.
- **Model site:** its own budget, like R-9 (`reason/l2`).
- **Fails closed:** no copy → today's fields.
- **Before any paid pass:**
  - one or two live test calls;
  - watch max tokens with thinking on (memory: Claude 5 thinks by default);
  - a golden replay with the ideal reader for every case F01–F67.

**Dashboard change** (`card-read.ts`):
- `headline ← copy.subject`;
- the two lines ← `copy.summary`;
- steps ← `copy.steps`;
- result ← `copy.result`;
- Goal row ← `copy.goal`, labelled "suggested" until C8.

### C4 · Each quote with its sender and date

- **Why:** a quote row holds only `evidence` ids and bare strings (`card_builder._sentence_sources`). The panel cannot say "— Divya Raman, 13 Sep".
- **Change:** resolve each quoted id to `{text, from, at, event_id}` from its source event.
- **Dashboard:** detail lines show the sender and date. `readCard` reads `quotes[i]` as an object when it is one.

### C3 · The queue carries what the list draws

- **Why:** the list reads `/cards/{id}` for every card, up to 40, just for the tags, who, the lane and the due date.
- **Change:** `CardStore.queue` (`store.py:772`, and the two other doors at `:779`, `:785`) adds:
  - `output_lane`;
  - `business_subject`, `relationship_role`;
  - `recommended->>'by_when'`;
  - the version (a count of `card.rebuilt`);
  - `context_tags`;
  - a `from_screen` flag (evidence kind `screen.*`; shared with Screen B8).
- **Dashboard:** `loadDetails` runs only for the opened card. `readCard` reads these fields off the row.

### C5 · Delegate a card

- **Change:** `POST /cards/{card_id}/delegate`.
- **To a person:** `{to_seat}`.
  - Set `cards.assignee`.
  - Record a card event (`human.card_action`, cause `delegate`, `detail.to`) and the L1 human event.
  - The card then reaches that seat's queue (`deliver/seat_access`).
  - Owner/admin only.
- **To an agent:** `{agent_id}`.
  - Build the play's parameters **server-side** from the card. Example: `email.follow_up_draft` with the card's thread and draft.
  - Call `executive/delegation.create_proposal(card_id=…)`.
  - The founder approves the proposal on the dashboard before anything runs (`/v1/delegations/{id}/approve`).
  - `NO_AGENT` becomes a sentence.
- **Dashboard:**
  - set `DELEGATE_LIVE = true`;
  - Hand over → `{to_seat: member.seat_id}`;
  - Ask it → `{agent_id}`;
  - the card leaves the list with "Handed to Harsh" / "Waiting for your approval".

### C7 · A "this is right" verdict

- **Why:** Rohit wants Feedback to say *"kya galat hai, kya sahi hai"*. The card's action set (`deliver/actions.BUTTONS`) has `wrong` but nothing positive.
- **Change:** a `right` action, recorded to the same learning ledger as `wrong` and with the same words and scope.
- **Dashboard:** Feedback gains "This is right", with the same two blanks.

### C8 · The goal link (GeniOS-009 G4 / G6)

- **Change:** `goal_situation_links` (G4), and `goal_refs` on the card (G6).
- **Dashboard:** the Goal row reads `goal_refs`. Goals ▸ a goal's cards and Cards ▸ a card's goal become the same link.

### C9 (later) · What changed in each version

`card.rebuilt` events carry the old and new move, so the panel can say "v3 — updated: 13 days quiet" instead of "Updated from newer mail".

## 6 · Checks before you call a part done

1. `npx tsc --noEmit -p .` and `npx next build` are green.
2. Against the stand-in brain (§1 A):
   - every section of `card-open-top/bottom.png` is drawn;
   - the question card offers Answer and no Done;
   - Feedback with words sends `reason`, `words` and `scope`;
   - Later with a picked day sends `custom_until`;
   - the panel says "4 lines read the same on your other cards".
3. Against the live brain (§1 B), for each change C1–C8: open at least three real cards. Each must show its own subject, its own lines and its own details. **No two cards may read the same.**
4. For each brain change: its own tests, a mutation that the tests catch, the golden replay unchanged except where intended, and CI green.

## 7 · Merge notes

- **Branch stack:** `main` ← `rohit/nav-grouping` (navigation, home, Goals, Screen) ← `rohit/cards-ux` (Cards).
  - Merge Cards after, or together with, `rohit/nav-grouping`.
  - It touches only `cards/page.tsx`, `lib/card-read.ts` and `lib/api-cards.ts`.
- **The other pages using `lib/api-cards.ts`** (`goals/live.ts`, `goals-page.tsx`) still type-check. The widened types are supersets.
- **Cards opens in a side panel; Goals and Screen open in place.** This is deliberate: Rohit asked for the side panel on Cards in round 4. The shared `intel/parts.tsx` is imported, not edited.
- **The Goals page should read cards through `readCard`.** Its own mapper has two faults, recorded in `03-WHAT-WAS-THERE.md` G1/G2:
  - "What to do" shows the projection's **verdict code** (`reply`, `review_source`) on live cards (`goals/live.ts:94`);
  - `proofOf` drops the quotes and shows inference labels as proof (`:74`).

  Switching it to `readCard` fixes both, and Goals and Cards then say the same thing about a card.
- **`globals.css` `.btn-blue` / `.btn-ghost`** set `font-size: 1rem` and padding outside any CSS layer, which beats Tailwind v4 utilities. Every page that sizes these buttons with utilities gets 16px buttons. The Cards page uses its own button classes and does not touch `globals.css`. Fix it once, with the home/Goals/Screen owner.
- **The Mac app shows the same cards in its own way.** These are `03-WHAT-WAS-THERE.md` M1–M6 (read from the code):
  - "Not useful" sends no reason, so the brain refuses it and the error is swallowed;
  - Done on a question card;
  - no `surface` is sent;
  - who is guessed from the headline.

  It should read cards the way `card-read.ts` does. That work is separate, with the Mac release.
