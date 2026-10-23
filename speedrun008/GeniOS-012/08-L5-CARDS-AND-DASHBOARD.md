# 08 · L5 Delivery and the dashboard: the card a human can act on in ten seconds (D32)

**Written for:** coding agents (brain `deliver/` and the dashboard repo) and Rohit (who approves every UI change on a render first).
**Fixes:** D32 (a)–(g) of [02](02-THE-PATH-OF-ONE-MAIL.md), and fields 1, 2, 5, 10, 11, 12, 14, 15 of the card contract ([01 §3](01-WHAT-THE-LOCAL-SESSION-DID.md)).
**Atlas v2 target for L5:** L5 decides who receives the card, where, when and in what words. It **never authors a fact**: every sentence on the card comes from the L2 judgment or the L3 graph, and is validated.
**UI rule (standing, Rohit 22 Oct):** dummy first, then real files. `/preview` **is** the dummy for the Cards, Goals and Home pages. Rohit confirms "make the real pages like /preview" before real dashboard files change, and confirms again on a local render. **Rohit, 23 Oct: `/preview` stays** (07's N6 "retire /preview" is not to be done).

---

## Part A · How a card is written today

### (a) The subject

| Step | Where | What it does |
|---|---|---|
| 1 | `deliver/card_builder.py` `gold_headline` (`:886`), `_gold`, `_gold_template` (`:909`, called from `build_draft` `:1142`) | For an expert card: the expert's move, kept whole if ≤ 60 characters, else cut at the last clause boundary that fits (`_GOLD_CUT`), else at a word, never ending on a word in `FUNCTION_WORDS`. |
| 2 | `deliver/render.py` `HEADLINE_CAP = 60` (`:26`), `_cap` (`:163`), `_fallback` (`:323-338`), V-01 in `render_copy` (`:611-627`) | For other cards: the LLM render or a raw-slot fallback, capped at 60. |
| 3 | `deliver/pipeline.py:1001-1003` → `render.state_not_command` (`:217-256`), `_LEVEL_FRAME` (`:209-214`) | For **every** card whose level is not actionable, a prefix: review → "Needs a decision — ", observation → "Unresolved — ", wait → "Waiting — ", suppress → "Closed — ". It strips a trailing now/today/asap. The body then has 60 − prefix ≈ **42 characters**. |

Result: headlines like "Needs a decision — Send calendar invites with meeting link to". No step writes a subject that starts with a verb and names the person.

### (b) What the judgment said that never reaches the card

`reason/expert/decide.py` `_render` (`:305-333`) passes on only: `fallback.headline`/`.situation`, `draft`, `sources`, and `gold` (subject, company, kind_of_work, role, why_now, what_remains, recommended{who, what, for_whom, by_when, to}, alternative, wait_or_stop, window).
- `scenarios.act` / `.best` / `.worst` / `.signals_to_watch` (on `ExpertReview`, `contracts/expert_review.py:262-279`) are **never passed**. Their only reader checks numbers (`reason/expert/verify.py:1069`). `scenarios.do_nothing` does reach the card, as `do_nothing_consequence`.
- `ExpertReview` has **no steps field**. `_play` (`:274-302`) builds the steps as `(words.headline,)`: one step, the headline again.
- The **draft survives**: `render.review_copy` (`:548`) puts it in `copy.artifact.body`, stored in `cards.artifact`. The dashboard never renders `artifact`.

### (c) The "why"

`api/routes.py` `_card_intelligence` (`:5376-5442`), with `_commitment_neighbors` (`:5284-5306`, first 3) and `_meeting_neighbors` (`:5309-5333`, first 4), called only from `get_card` (`:5769-5799`). It is computed **when the card is read**, from the signal's `subject_node_id`: the person's active facts, observation counts, up to 4 one-hop meetings and 3 one-hop commitments. One node, no quotes, no thread bodies. So every card on the same person shows the same "why". The card's own `why` column is written at build time (`card_builder.py:1372`: `_review_label` + `_sentence_sources` + `_window_receipt`).

### (d) What the API returns

- `GET /cards` (`routes.py:5656` → `CardStore.queue`, `deliver/store.py:855-989`): `card_id, signal_id, assignee, domain, urgency_band, headline, subject_node_id, situation, score, state, render_mode, created_at, expires_at` (+ `your_part`). **No goal, no category, no draft, no steps.**
- `GET /cards/{id}`: every card column (`k.*`) plus candidate steps, rejected candidates, uncertainty, `context`, `actionability`, the card.v2 `decision` projection (recommendation verdict/objective/steps/avoid, confidence, grounding), annotated `actions`, `screen_items`.
- Card columns today include headline, situation, level, domain, urgency_band, `why`, `artifact`, `recommended`, `alternative`, `wait_or_stop`, `success_signal`, `do_nothing_consequence`, `confidence_vector`, `file_id`, `version`, `output_lane`, `lane_reason`. **No goal column. No category column.**

### (e)–(g) The dashboard (`themoronss/genios-brain-dashbaord`, `origin/main`)

| Page | File | What it reads | What is missing |
|---|---|---|---|
| Cards | `src/app/dashboard/cards/page.tsx` (1,329 lines), mapping in `src/lib/card-read.ts` (`readCard` 300+, `laneOf` 285), API in `src/lib/api-cards.ts:213-250` | `/cards`, `/cards/{id}`, `/cards/history`, `/cards/{id}/timeline`, `/cards/{id}/action`. Lanes Decide / Two sources disagree / Answer / Waiting (`GROUPS` 91-95) from `output_lane`. Renders headline after `clearHeadline`, domain tag, urgency, recommendation, avoid, What/Why/How, done when, if you don't, alternative, wait/stop, deadlines, details, sources. | **goal hard-coded "Not linked to a goal yet"** (~`:925`); `artifact` (the draft) never rendered; `copy` not read; category only as the domain tag |
| Goals | `src/product/internal/dashboard/goals/{goals-page.tsx, live.ts, sample.ts, types.ts}`, `src/lib/api-goals.ts` | `GET /v1/company-brief` + `/cards` + each card's detail | goals are brief lines; target "Not set yet"; progress unknown; `cards: []`; `tags: []`; every card "unlinked" |
| Home | `homepage/sections/genios-at-work.tsx` (804 lines) | `const goals = sample ? SAMPLE_GOALS : []` (`:658`) | live goals always empty; shows "Goals are coming next" over a greyed sample |
| Preview | `src/app/preview/page.tsx`, `src/app/api/preview/route.ts`, `src/server/ideal-preview-html.ts` (`ff13896`) | a static, owner-only copy of the ideal dashboard | stays, as the dummy and for the pitch |

---

## Part B · The units

### Brain (`deliver/`, `reason/expert/`)

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S34.U3** | Claude (another session is building it) | C1: the card writer, `deliver/card_copy.py` | **State on 23 Oct:** uncommitted files in the `.claude/worktrees/g011-S34U3` worktree; branch `g011-S34U3` has no commits of its own. New: `deliver/card_copy.py` (497 lines), `migrations/0252_cards_copy.sql` (`cards.copy jsonb`), `scripts/card_copy_probe.py`, two tests. Modified: `deliver/pipeline.py` (`_word_the_card`; `CopyWriter.for_pass` built once per pass), `deliver/store.py` (`SET_COPY_SQL`, `set_copy`, `copy=null` on version/refresh, `QUEUE_COPY_SQL` serving `copy.subject`/`copy.summary` in `queue()`), `platform/l4_activation.py` (feature `card_copy`), `reason/bundle/sites.py`/`budget.py` (new site R-10), `platform/intelligence_onboarding.py`. **What it does:** one model call per new card version writing subject, summary, how, steps, result, avoid, done_when, if_not, alternative and goal (from accepted brief goals lines); every sentence must cite fact ids; unsupported sentences are dropped. Off by default (`FEATURE_CARD_COPY`); live probe not yet run. **To finish:** commit, merge, apply 0252, run the probe (Rohit's spend yes), switch on per tenant; `get_card` already serves `copy` through `k.*`. | a card's `copy.subject` starts with a verb, names the person and is never cut mid-clause (the length limit is the writer's own, checked in its tests); the probe's dropped-sentence share and cost are logged | 🔨 |
| **S34.U2** | Claude | C2: the expert's result and steps reach the card | 1. Add `steps: list[str]` (2–5, each citing ids) to `ExpertReview` and to the R-7/R-9 output schema; the claim check covers them. 2. `decide._play`: use the review's steps, not `(headline,)`. 3. `decide._render`: pass `scenarios.act` (the result of doing it) and `scenarios.worst` into `gold`. 4. `card_builder.build_draft` (~`:1336`): store them in card columns (`result`, `steps`). | an expert card's `GET /cards/{id}` has 2–5 steps and a `result` line; the old single-step tuple is gone. Mutation: restore `(headline,)` → red | ⬜ |
| **S34.U1** | Claude | C6: context belongs to this card's thread | Build the "why" at **build time** from the card's own `file_id` and the judgment's `sources` (quotes from the counterparty's own words, up to 3 threads), not from the subject node's last 4 meetings at read time. `_card_intelligence` becomes a fallback for legacy cards only. | two cards on the same person show different "why"s; each quote is the counterparty's words with its thread and date | ⬜ |
| **U12-18** | Claude | The lane is a chip, not a prefix | Stop `state_not_command` from prefixing the headline; return the level as a field (`state_label`) the surfaces show as a chip ("Needs your decision", "Waiting"). The 60-character cap applies only to legacy cards without `copy`. Files: `deliver/render.py`, `deliver/pipeline.py`, tests; the Mac app and dashboard read `state_label`. | no new card's headline starts with "Needs a decision —" | ⬜ |
| **U12-19** | Claude | The list carries what the card page needs | `queue()` returns `category`, `goal_refs` (once S31.U1 lands), `copy.subject`, `copy.summary`, `label` (unreviewed playbook) and `state_label`, so the Cards list never needs one detail call per card | `GET /cards` has these fields; the dashboard's list renders without N+1 calls | ⬜ (part of S35.U1) |
| **N2** | Claude | `category` on cards | from [07](07-GOALS.md): code-derived from the capability or work kind; `cards.category` column (same migration as S31.U1's `goal_refs`, or the next free) | `GET /cards` carries `category`; an unmapped capability gives `null` | ⬜ |
| **S31.U1** | Claude | `goal_refs` and a goal line on cards | from [07](07-GOALS.md) | — | ⬜ |
| **S35.U1–U4** | Claude | queue carries what the list draws (C3), quote objects (C4) and "this is right" (C7), delegate (C5), Cards page catches up | as in GeniOS-011 02-PLAN | — | ⬜ |
| **S39.U1** | Claude | No made-up numbers on any surface | brain numbers are measured or say so | — | ⬜ |

### Dashboard (`genios-brain-dashbaord`), after Rohit's go on the render

| Unit | What | Exactly how | Done when | Status |
|---|---|---|---|---|
| **N3a** · Cards | the Cards page reads what the brain now gives | `src/lib/card-read.ts`: read `copy` (subject, summary, how, steps, result, avoid, done_when, if_not, alternative), `artifact.body` (the draft, with a Copy button), `category`, `goal_refs`, `state_label`, `label`. `page.tsx`: replace the hard-coded goal row with the goal line; add category filter chips; lanes in the preview's order (conflict, decide, answer, waiting); show "playbook not yet reviewed" when `label` says so. Legacy cards without `copy` keep today's rendering. | a local render against a stand-in brain matches `/preview`'s Cards page; `tsc --noEmit` and `next build` green; Rohit approves | ⬜ |
| **N3b** · Goals | the Goals page reads goals | `live.ts`: read `GET /v1/goals` (S28.U2); group Admin → category → goal → its cards; proposals with one-click approve through the brief door; progress with its basis (counted / unknown / blocked); other domains shown locked. Drop the `AdminTag` fixed list for the brain's `category`. | matches `/preview`'s Goals page on the stand-in | ⬜ after S28.U2 |
| **N3c** · Home | Home shows goals | `genios-at-work.tsx:658`: read `getCompanyBrief` now (S27.U3), then `GET /v1/goals` | Home shows accepted goals and "goals waiting" | ⬜ |
| **N3d** · Cards page detail | the draft and the quotes | the opened card shows: subject, summary, the goal it moves, steps, the draft (copyable), done when / if not, alternative, and "Show more" tabs with quotes and sources (standing visual rule: essentials first, details in tabs) | per `/preview` | ⬜ |

---

## Part C · Measuring the card against the ideal, after every deploy

| Tool | What it measures | Where | Status |
|---|---|---|---|
| `scripts/ideal_card_gap.py` (S44.U1) | each product card against the ideal card, **field by field** (15 fields: subject verb-led and not cut, quotes are the counterparty's own words, text repeated across cards does not count) | Rohit's machine only: `--from-dashboard <02-data.js>` plus `--product` (an API dump) or a read-only `--database-url`. Nothing from his mail enters the repo. | ✅ |
| `scripts/preview_parity.py` (N5, from 07) | **whether** each `/preview` card and goal exists live; for a missing card, the file's `why_no_card` | reads the expected list from `PREVIEW_EXPECTED_PATH`, outside the repo; exit 0 only at ≥ 18/20 cards and 10/10 goals | ⬜ |
| `daily_health` (S05.U1) | cards by builder and lane per day; alerts when cards drop | production | ✅ |

---

## After this file: what should be true

1. Every new card has a human subject, steps, a result, a draft, the goal it moves, its category and its own quotes.
2. The Cards, Goals and Home pages show them, matching `/preview`.
3. After each deploy, parity and the field-by-field gap are measured and logged.

**Expected after Step 7:** all 20 `/preview` cards readable as on the preview, or each missing one with a named reason Rohit accepts. Record what actually appears in [13-LOG](13-LOG.md).
