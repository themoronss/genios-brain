# STEP-14 · TO BUILD · the card — one file, one living card, in the gold shape

**Owner:** Claude. **Depends on:** `STEP-13`. **Decision:** `06` D8 (screen reminders). **Moves:**
duplicate cards per subject **→ 0**; every card passes the contract check.

---

## 1 · What is true now

| | Evidence |
|---|---|
| A card per **signal**, not per subject | `[CODE]` `deliver/pipeline.py:46-131, 381`; the per-situation grouping (`:134-179`) is measurement only and `cards_from_situations` sets a label only (`:374-378`). `[PROD]` the offer to Khushi became six cards; nine `dependency_stated` cards for related asks |
| The copy prompt is contaminated | `[CODE]` `deliver/render.py:750` hard-codes *"Send Titan Capital your traction metrics"*, *"Answer Divyanshu's pricing question"*; `:767` writes *"for a salesperson"* |
| The copy never sees the reasoning | `[CODE]` `render_copy` receives facts and quotes — not the decider's rationale, the rejected options, the unit findings or any history (`deliver/render.py:787-904`) |
| False claims from fallbacks | `[PROD]` *"nsrcel — a dated payment obligation is open"* (`money-owed-either-way.yaml`'s gate is any `commitment.due_at`); internal field names on cards — *"party.role"*, *"8 data points, 1 unreadable"* |
| Screen reminders hidden | `[CODE]` `reason/moments/guards.py:68-71`; `capture_policies.moments_display` defaults false (`platform/capture_policy.py:254, 498`). `[PROD]` 65 hidden |
| Already right on `harsh/mvp` | expired cards are rebuilt, human-decided ones never (`c22d0f00`, `2c42722d`); the drawer no longer crashes on structured values (`2f595277`) |

## 2 · Why

The card is the only part you see. Everything upstream is wasted if the card is one of six, names
the wrong person, or invents a payment.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | one file, one card | `deliver/pipeline.py`, `deliver/card_builder.py` | cards are built per **workstream** (`situation_id` carried end to end); signals of the same file merge into its card |
| 3.2 | a living card | `deliver/store.py`; `card_events` | a material change updates the card — a new version and a `card.updated` event naming what changed — never a second card. Its versions are visible |
| 3.3 | the gold shape | `deliver/card_builder.py` | **situation** · **subject and role** · **what remains** · **why now** · **recommended** (who, what, for whom, by when) · **alternative** · **wait or stop** · **done when** · outcome window · evidence receipts · the confidence vector · *"playbook not yet reviewed"* when that is true (D3) — the Atlas's gold card and the Secret War audit's actionable contract |
| 3.4 | clean copy | `deliver/render.py:698-784` | synthetic examples only; the persona *"a founder's chief of staff"*; the expert's explanation and scenarios passed in as the render hint, under the existing V-01/V-02 validators |
| 3.5 | the contract check | new `deliver/card_contract.py`, before insert | refuse — to Investigation, or abstain with a reason — when: the subject or recipient is us · no dated fact · the value is a quote and no quote is present · an internal field name appears · money is claimed with no money in the evidence |
| 3.6 | screen reminders | D8 | shown inside the morning brief (`STEP-15`) first, then in the moment |

## 4 · What will happen

| Today | After |
|---|---|
| Six cards about Khushi's offer | **one**: *"Khushi — offer sent 5 Aug. Waiting on: her acceptance and the signed documents. Blocked on: the ESOP board approval (yours)."* |
| *"nsrcel — a dated payment obligation is open"* | refused by the contract check; NSRCEL's real item — the assignment due — on the program's card |
| *"Which is right? Maria Exconde: party.role"* | gone — an internal field name; the real item is *"Maria replied 11 Aug; your reply is owed"* on her intro card |

## 5 · Expected

- duplicate cards per subject: **0**;
- contract-check failures reaching the dashboard: **0**;
- cards with you as the subject: **0**;
- the copy prompt holds no real names.

## 6 · Verify

```
.venv/bin/python -m pytest tests/deliver -q
#   one workstream with five signals → one card; a change → a new version, not a new card;
#   each contract rule refuses its case — by mutation; render.py contains no real names (AST check of the literals)
```

---

## 8 · The check of 2026-10-12 — what the 5 Oct plan got right, and wrong

Re-checked claim by claim against `yc2w27-s14-plan` @ `fbd0aeaa` — STEP-13 built but for its question card
(M36.C2 U05), the Answer (U06), its acceptance and the replays — and measured by replaying **31 of the 58 golden
cases**, one at a time from their cassettes (no spend), each run on a fresh scratch database (pg2: `s14_f02`,
`s14_f05`, `s14_f06`, `s14_f12`, `s14_f24`, `s14_f25`, `s14_f50`, `s14_batch1` = F19 F01 F52, `s14_batch2` = the
21 must-detect passes). Production was not read. Since 5 Oct, STEP-12 made one review per changed file decide it,
so a covered file holds one decision — and shows one card — at a time; STEP-13 checks every line of the review and
gives the card its sentences' sources; a held file asks one question, and its card (`deliver/store.
QUESTION_CARD_BUILDER` "founder_question.v1", the queue's third door `QUESTION_CARD_SQL`, `deliver/pipeline.
_build_question_cards`; the writer moved to `reason/expert/asks.py`) is landing on the s13 line as this is
written — planned against as the lead describes it, its code not yet read. What does not exist is the card this
step promised: **every new decision on a file is a new card and the old one is replaced**; the gold shape's middle
is empty; nothing checks a card's contract; and the board counts cards the app never shows.

In the product's words: the card is L5 Delivery (`deliver/`). It should compose — with no model — what L2's Plane R
judged and checked (`reason/expert`), what the L3 Context Graph holds of the file (`context/workstreams`, the
timeline, the open asks), and the playbook of L2's Plane D (`packs/`) — so whichever model reviewed the file
(Haiku or Sonnet, Opus only when needed), the card has the same shape and every fact on it is the data's.

### 8.1 · Measured — 31 cases, 39 cards

| | |
|---|---|
| whose cards | **39 of 39 the expert's** (`file_review`) — no legacy or compiled-lane card on any replayed case |
| a second card about one file | **10 replacements over 9 cases**, each `card.expired cause=replaced` and a new card: the advice changed as the file moved — F02, F05, F06, F19, F24 (twice); the same advice in other words — F25; the same advice after its 7-day window lapsed — F12 (a new review, the move word for word), F50 (the SAME review, re-decided 14 days on). Eight must-detect cases lost: F176's four and F02, F19, F24, F50 |
| demoted by the formula lane's quote gate | **10 of 39** — `review`, *"Needs a decision — …"*, Run Play removed, surfaces `{ask, api}`: on no app |
| the board, counted on the app | **6 of the 21 must-detect passes are cards the app never shows** (F03, F07, F16, F47, F48, F49) — **15/45** on the app |
| the gold shape | why now **0/39** · what remains **0/39** · role **0/39** · subject a bare domain **21/39** · done when 39/39 · do-nothing 39/39, unchecked · window the 7-day default **20/39** (every move with no date) · confidence R = 50 (a default) 39/39 · who, for whom, by when, to whom, the alternative, the stop rule: on no card column |
| the headline | **38 of 39** moves are longer than 60 characters; 10 are cut mid-phrase (*"…cohort folder by the"*, *"…answers before the"*, *"…pricing call on"*) and their date is then on no field |
| a held file | F01, F52: the question signal is open (Investigation, binding 0), no card yet (U05) |
| F19 (`06` D58) | its second card names Naveen, Ritika and Ekta — one card meets the case as written |

### 8.2 · The claims

| # | Claim (§1) | Now | Evidence |
|---|---|---|---|
| 1 | a card per signal, not per subject | **true, and the duplicates moved from fan-out to time** — still one card per signal and a loop over signals; the per-situation grouping measures only and the flag sets a label. Since STEP-12 a covered file has one open decision, so within a sweep one card; across sweeps a card per decision (§8.1). `[PROD]` Khushi's six cards not re-measured; the golden F25 now shows two, both app-hidden | `deliver/pipeline.py:48-143, 388-390, 408-409, 412`; `migrations/0008_l5_delivery.sql:31`; `reason/domain_shadow.py:300-330` |
| 2 | the copy prompt is contaminated | **true** — moved to `:500-501` (*Titan Capital*, *Divyanshu*, *Leslie*) and `:521` (*"for a salesperson"*); Titan Capital is a `REAL_NAMES` token | `deliver/render.py:496-521`; `tests/replays/founder_case.py:76-93` |
| 3 | the copy never sees the reasoning | **false for an expert card, true for the rest** — a covered file's card has no narrator: its words are the checked review's (STEP-12 M33, STEP-13 U03); a narrated card still gets facts and quotes only | `deliver/pipeline.py:503-527`; `reason/expert/decide.py:255-285`; `deliver/render.py:448-538` |
| 4 | false claims from fallbacks | **true in the code** — the money situation gates on any `commitment.due_at` and says *"a dated payment obligation is open"*; a discrepancy card prints its field (`party.role`); V-02 grounds a fact's KEY, so a field name passes it. Stood down on a covered file; live everywhere else. `[PROD]` not re-measured | `money-owed-either-way.yaml:35, 85`; `reason/verify/passes.py:103`; `deliver/render.py:63-81` |
| 5 | screen reminders hidden | **true** — `decide` answers SHADOW first; `moments_display` defaults false. `[PROD]` 65 not re-measured | `reason/moments/guards.py:86-87`; `platform/capture_policy.py:254, 498` |
| 6 | already right on `harsh/mvp` | **true** — `c22d0f00`, `2c42722d`, `2f595277` are ancestors of HEAD | `git merge-base --is-ancestor` |

The units of §3, against what exists:

| | Unit | Now |
|---|---|---|
| 3.1 | one file, one card | **partly** — STEP-12 gives a covered file one decision at a time; the card is still the signal's, so each decision is a new card |
| 3.2 | a living card | **not built** — no `card.updated`, no versions; the P4 emitter alone refreshes a card in place, keyed on its situation (`reason/team/emit.py:186-213`) — the precedent |
| 3.3 | the gold shape | **partly** — situation, done when, receipts (STEP-13's sentence sources), confidence, *"playbook not yet reviewed"* (D3), do-nothing; empty or absent: subject (a domain on 21/39), role, what remains, why now, the move's who/for whom/by when/to, alternative, stop rule; the window a default on 20/39 (F179) |
| 3.4 | clean copy | **not built**, and half moot — *"the expert's explanation and scenarios passed in as the render hint"* has nothing to pass to: an expert card has no narrator. The persona and the names remain for narrated cards |
| 3.5 | the contract check | **not built** — subject is us is refused (STEP-04, `card_builder.py:987-988`) and the expert's claims are checked (STEP-13); field names, money, quotes are not, and the second card writer (`reason/team/emit`) runs no validator at all |
| 3.6 | screen reminders | **not STEP-14's** — a screen item is one seat's (D22, D53) and never reaches a file's card; the brief is STEP-15's |

§4's three outcomes: Khushi's one card — partly (one file, two cards, neither on the app); nsrcel refused —
not yet; *"party.role"* gone — not yet. §5: duplicates 0 — measured 10; contract failures 0 — no check; cards about
you 0 — **holds** on the golden set (STEP-04); the copy prompt's real names — false. §6: none of its tests exist.

### 8.3 · New — not in the plan

Provisional ids; the lead assigns F-numbers. (A separate `baseline/yc2w27-s14/findings.md` was refused by this
session's guard on report files written by a worker; the table is here.)

| Id | Finding | Evidence | Owner |
|---|---|---|---|
| s14-F1 | **An expert card is graded by the formula lane's quote gate**: no counterparty quote → `review`, no Run Play, no app. Wrong for an expert card, whose move rests on facts the check verified and is often OURS (write to the person introduced, find a working address, accept an invite). 10/39 demoted | `deliver/card_builder.py:1153-1166, 1251-1253`; §8.1 | M42.C3.L-logic.V0.U01 |
| s14-F2 | **The board counts cards the app never shows**: `_open_cards` reads `cards.state` only — not the app surface, not the queue's door. 6 of 21 passes app-hidden; 15/45 on the app. `check_cards_reach_the_app` passes while one card of the org does | `tests/replays/engine_runner.py:579-613`; `tests/replays/marking.py:116-158`; `scripts/pipeline_health.py:200-215` | M42.C4 (s14-D4) |
| s14-F3 | **F176's mechanism**: the file branch retires the decision, expires its card `REPLACED` and inserts a signal; `cards_one_per_signal` makes it a new card. Three causes — advice changed, reworded (`_advice` compares the headline's text), the same advice after its window | `reason/domain_shadow.py:300-330, 573-596`; `deliver/store.py:223` | M42 |
| s14-F4 | **`06` D58's premise is false**: F19 is met by one card naming the three people — its second card does; only the first (Naveen alone) makes two | `s14_batch1` | D58 restated (s14-D7) |
| s14-F5 | **A standing file decision is never renewed, only replaced** (`03` F52, F53 on the expert's path): `RENEW_MARGIN` = 0, and while the window holds the file branch answers "standing"; in production the cron lapses the card first | `reason/change_gate.py:38, 75-77`; `reason/domain_shadow.py:319-325`; `deliver/store.py:342-374` | M42.C2 |
| s14-F6 | **The gold shape's middle is empty**: `_why_now` knows legacy reason codes only; `unresolved_item` and `relationship_role` read `commitment.action` and `party.role`; the move's who/for whom/by when/to, alternative and stop rule sit in the audited play's metadata only; 21/39 subjects are domains (`03` F64). The review's triggers, from which a why-now is built, are machine text (*"new since the last review: evt_bcd6…"*, *"the next meeting: <=336 → <=48"*) | `deliver/card_builder.py:159-211, 1208-1218`; `reason/expert/decide.py:230-252`; `expert_reviews.triggers` | M43.C2, M43.C3 |
| s14-F7 | **The move is cut to 60 characters and its date is lost**: 38/39 longer, 10 cut mid-phrase; `by_when` on no field | `deliver/render.py:323`; `reason/expert/decide.py:255-265` | M43.C3.L-interface.V3.U01 (s14-D8) |
| s14-F8 | **The do-nothing scenario reaches every expert card unchecked**: on the decision, the signal and `cards.do_nothing_consequence` (39/39, served by `GET /cards/{id}`), while the check lists it with the alternative and the stop rule as *"text no founder is shown"* | `reason/expert/decide.py:305`; `reason/expert/verify.py:332-339` | M43.C1.L-contract.V0.U02, M43.C2.L-logic.V1.U01 |
| s14-F9 | **Two defaults read as measurements**: the 7-day window on 20/39 (every move with no date, F179); R = 50 on 39/39 — the 5,000 bp fallback, since the expert's reader publishes no recency | `reason/expert/decide.py:144, 216-219`; `reason/authority.py:111-113` | M43.C2.L-logic.V0.U02, M43.C3.L-interface.V3.U01 |
| s14-F10 | **A second card writer runs no validator**: P4 team/verify cards go straight into `cards` (`_write_card`) — the *"party.role"* card is one; a contract "before insert" in `deliver/` would miss it, and `reason/` may not import `deliver/` — so the contract lives in `contracts/` | `reason/team/emit.py:10-21, 179-252`; `reason/verify/passes.py:103`; `genios_engine/LAYERS.py` | M43.C4 |
| s14-F11 | **The false money claim is still authored** — any dated commitment becomes *"a dated payment obligation"*; stood down only on a covered file | `money-owed-either-way.yaml:35, 85` | M43.C4 (the corpus line: its authors) |
| s14-F12 | **A question's authority had no reader in delivery** at this commit; STEP-13's third door adds the queue and the card detail — `ingest_action` and `surface_context_match` are not on the lead's list. A living card turning from question to decision changes doors | `reason/authority.py:350-370`; `deliver/store.py:452-554`; `deliver/actions.py:83-106` | STEP-13 U05/U06; M42.C3.L-interface.V3.U04, V4.U05 |
| s14-F13 | **A question and the decision after it are two cards**: `retire_question` expires the question card `REPLACED`; U06 (planned) RESOLVES it on your answer | `reason/domain_shadow.py:640-700` (→ `reason/expert/asks.py`); `yc2_w27_s13/M36.C2.L-interface.V4.U06` | M42.C2.L-integration.V2.U05, M42.C3.L-interface.V4.U05 (s14-D3) |
| s14-F14 | **The board judges a card's last words only**: a card rewritten in place — today's stale refresh, P4's refresh, every version of a living card — is judged on its final text | `tests/replays/engine_runner.py:589-613` | M42.C4 |
| s14-F15 | **`06` D34's premise has moved**: every replayed card is the expert's; a pack rule on a covered file stands down (STEP-12) | `reason/runner.py:900-993` | D34 answered for covered files |
| s14-F16 | **D8 is STEP-15's**: screen items are one seat's and never reach a file's card | `reason/moments/guards.py:86-87`; `reason/moments/followups.py` | STEP-15 (s14-D6) |
| s14-F17 | **The narrator still writes for a salesperson with real names** — now only on cards no review wrote | `deliver/render.py:496-521` | M43.C5 |
| s14-F18 | **The compiled lane's replacement expiry has no behavioural test**: when a compiled decision past its window is replaced, `_emit_capability_signal` expires the old signal's cards REPLACED — and a mutant that skips it survives tests/reason/expert, tests/reason/adapters, `tests/test_admin_support_packs.py` and the situation-card test (found by M42.C2.L-integration.V2.U02's mutation run, 12 Oct; the branch was only moved, not changed) | `reason/domain_shadow.py` (`replace_unless_from is None` branch) | the lead (a guard unit) |
| s14-F19 | **No card ever reaches the agent surface**: `card_builder._surfaces` grants `agent` when an action's `action` is `run_play`, but `build_draft` writes its actions as `{"type": "run_play"}` — and its one test (`tests/test_open_loops.py:455`) feeds `{"action": "run_play"}`, the shape no card has. Found reading the expert grade (M42.C3.L-logic.V0.U01, 12 Oct); not changed — granting it would start agent pushes (`deliver/outbox.enqueue_agent_push`) on every Run Play card | `deliver/card_builder.py` `_surfaces`; `tests/test_open_loops.py:441-455` | the lead / Rohit (a behaviour to switch on deliberately) |
| s14-F20 | **The team writer's card contract refused every meeting follow-up** (our own regression, M43.C4.L-integration.V1.U03 at `a3be2ec2`): a follow-up's evidence names its facts (node, field) and holds none of their values, and *"— 1 for you"* is a count code computed — so the number rule refused *"Follow-ups from ISO audit — 1 for you"* and *"(due 20 Sep)"*. A readiness card's *"1 away"* was held only when the milestone's id happened to carry the digit. Found by the root guard (`tests/test_meetings_pg.py`), 13 Oct; fixed the same day: the writer hands the contract what its words were composed from (`emit_situation(corpus=…)`; `meetings/passes.compose_followup` returns the facts' values and the count, never its words), and the readiness evidence carries its away count | `reason/team/emit.py` `refusals`; `reason/meetings/passes.py` `compose_followup`; `reason/team/readiness.py` | M43.C4.L-integration.V1.U03 (fix) |
| s14-F21 | **The card contract refused 19 golden expert cards for their gold lines** (our regression, found re-recording 14 Oct): why now and what remains are code's lines from the dossier (a meeting's title in quotes, its days away), the move whole, the alternative and the stop rule the check's — none were in an expert card's corpus, so *"number: 12"*, *"quote: Ferngrove x Nimbus Labs"*. F01, F02, F48, F52, F63 lost their card; that re-record was discarded | `deliver/pipeline._contract_refusals` | M43.C4.L-integration.V1.U02 (fix, `dfb2e169`) |
| s14-F22 | **The connector became the subject of the file it introduced**: its nudges sit on the person's file, and the card lines took the last of the file's people to write — Introly — as its person (F03) | `reason/expert/card_lines._person` | M43.C2.L-logic.V0.U02 (fix, `836f17f1`) |
| s14-F23 | **A titled meeting lost "(memory holds no words for it)"**: the dossier printed the title in its place, so F54's find-out reviews (authored on that line) were never served and the held file asked nothing; the second fix wave's unworded-meeting mutation stopped reaching a card | `reason/expert/dossier._timeline` | M42.C2.L-interface.V3.U04 (fix, `b8b4804d`) |
| s14-F24 | **The statement census counts a bare string literal that opens on a SQL word**: `FUNCTION_WORDS`' "with" moved the pin 3,183 → 3,184 with no SQL added (the instrument's over-count, `03` F100's kind) | `platform/table_coverage._statements`; `deliver/card_builder.FUNCTION_WORDS` | left — the literal is one string now (`fc9ab5d5`); the census rule is the lead's |

### 8.4 · What changes in the design

1. **The card's identity is its file, not its signal.** A file's card (`cards.file_id`, `0220`) carries the file's
   current decision or question; each new one is a VERSION of it — the card re-pointed at the new signal, its words
   rewritten, one version event naming what changed and keeping the words before — never a second card. At most one
   card per file the founder has not decided. A card the clock, a replacement or a clearing closed is reopened by the
   file's next version (s14-D2); one the founder decided (acted, resolved, dismissed) stays decided. One writer of
   `cards.signal_id` (`platform/card_lifecycle.version_card`), as there is one of `expired`.
2. **Reason hands the file on; delivery versions it.** The file branch of `_emit_capability_signal` and the question
   writer (`reason/expert/asks`) retire the old signal but no longer expire its card `REPLACED`; the pipeline versions
   it. The same advice is RENEWED, not replaced: the change gate re-decides a standing decision 12 hours before its
   window closes (`RENEW_MARGIN`, more than a 6-hourly sweep), and a renewal is a quiet version — nothing pushed.
   A version is pushed only when it is material: another ask, recipient, date, lane or mode (s14-D1).
3. **The question card is the file's card, asking.** STEP-13's question card keeps its builder, door, surfaces (app,
   api) and actions (answer, snooze); when a held file asks, the file's card becomes that question (a version);
   when you answer, the card is versioned again — *"your answer is in; the file is read again"* — rather than
   resolved (s14-D3); the next review's decision versions it once more. Decision → question → answer → decision is
   ONE card. The doors agree on the card's current version (a version stamps the builder its door reads).
4. **An expert card is graded by its check**, not by the formula lane's quote gate: shown → prescriptive, held or
   find-out → a question. The quote gate stays for every other card.
5. **The gold shape is code's, from the checked review and the file** — no model writes it, so it is the same
   whichever model reviewed. Lines written at review time, from the dossier's parts (`reason/expert/card_lines`,
   kept beside the check so a replay needs no dossier): **why now** from the review's triggers as a sentence; **what
   remains** from the file's open asks, ours and theirs; **subject and role** — the file's person and company
   (`03` F64) and the brief's kind of work; **the window** — the move's date, else the playbook stage's prior, else
   the file's measured reply time, else 7 days labelled a default (F179). The move whole under *recommended* (who,
   what, for whom, by when, to whom); the headline cut at a clause, never on *"…by the"*. The alternative, the stop
   rule and the do-nothing line are founder-shown, so the check holds them like the situation (`check.v2`). Only
   measured confidence axes are shown.
6. **The contract is a contract** (`contracts/card_contract`), run by BOTH card writers — the pipeline (decision and
   question cards, new or a version) and `reason/team/emit` — before anything is written: us as subject or
   recipient, a field name or an unfilled slot, money with no money field in the evidence, a quote not in the
   quotes, a number or date outside the card's corpus. Refused, counted per rule, never shown. A discrepancy card
   names its field in words.
7. **Clean copy only where a narrator still writes** (cards no review wrote): the chief-of-staff persona, *"you"*,
   the golden set's invented names as examples.
8. **The board counts what you see** (s14-D4): a must-detect card counts once the app queue showed it, at each
   sweep's instant; forbidden phrases and *"about us"* are judged over every surface and every version.
9. **Out of this step**: D8 → STEP-15 (s14-D6); D34 answered by STEP-12's stand-down; D58 moot for the board (s14-D7).
   Replay 02's introductions (D54) become six founder cases (s14-D5).

### 8.5 · What will be built — tree block `yc2_w27_s14` (M42, M43), proposed

**M42 — one file, one living card** (18 units): C1 the identity — `0220_the_living_card`, what a version is, the one
writer of a card's signal · C2 reason hands the file on — the renewal margin, what was judged before reads versions,
the dossier prints them (and a meeting's title, `03` F164), the decision's hand-over, the question's hand-over ·
C3 delivery versions it — an expert card graded by its check, `CardStore.version_card`, both builders version, the
doors agree on a version, an answer keeps the card · C4 the board counts what you see — the queue at an instant,
the runner records what the app showed and every version, the marking, one re-record, the acceptance with a
negative control.

**M43 — the gold shape, and nothing false** (27 units): C1 `0221_the_gold_card` and `check.v2` · C2 the card lines
(why now, what remains, subject and role, the window), the check widened, the authored answers, the review run
writes the lines, the decision carries them (`DECIDE_VERSION` 1.2.0, no model) · C3 the expert card and the
question card in the gold shape, the store writes them · C4 the contract, at both writers, a discrepancy in words,
the health check · C5 the narrator's persona and names, an AST guard · C6 six founder cases for replay 02 (F59–F64,
each a unit), their expression, one more re-record, the acceptance with a negative control.

**45 units (18 in M42, 27 in M43), critical path 9** — after STEP-13's U05 and U06: `0220` → the one writer →
`CardStore.version_card` → both builders version → the doors agree → re-record → M42's acceptance → re-record → M43's
acceptance. Migrations `0220`, `0221`. Two re-records, one per milestone, each restating the board in its five
places. The block, its units, artifacts and verify commands: `baseline/yc2w27-s14/tree_s14.yaml`, for the lead to
merge into `tree.yaml` (the tree guard then names nineteen blocks).

**The number, restated.** On what the app shows: **15 → 29 of 45** after M42 (the six app-hidden passes reach the
app; F02, F05, F06, F12, F19, F24, F25, F50 pass — each case's `mentions` read on the card's final words, measured
on today's cards), **31** with STEP-13's question card if it passes F01 and F52. **≥ 90% (41/45) is not STEP-14's
to reach**: twelve cases are not expressible until STEP-15 (eleven brief-only, F30 the screen door), F15 waits on
D57 and F56 on the gate. STEP-14's own target: every must-detect case whose loss is the card's passes; no file has
two open cards; must-abstain 13/13; forbidden outputs 0 over every version.

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| s14-D1 | Which change of a file's card pushes you again? | **a material one** — another ask, recipient, date, lane or mode; a rewording or a renewal is a quiet version, kept in its history | every version pushed as a new card would be |
| s14-D2 | A file's card the clock or a clearing closed — does the file's next decision reopen it? | **yes** — one file, one card; its history shows the gap. A card you decided stays decided | the same |
| s14-D3 | When you answer a held file's question, does its card close? | **no** — it becomes *"your answer is in; the file is read again"*, and the next review's decision is its next version (one card from question to move) | it closes, as STEP-13 U06 plans; the move is a second card |
| s14-D4 | Does the board count a card the app never showed? | **no** — must-detect counts what the app queue showed; forbidden is judged everywhere. 15/45 today, said | as today: 21/45, six of them never shown |
| s14-D5 | Replay 02's introductions (`06` D54) — six new founder cases in STEP-14? | **yes** — F59–F64 for m00, m01, m02, m03, m05, m07; m06, m08, m09 stay declared | D54 as written (STEP-14 authors them) |
| s14-D6 | D8, screen reminders — in STEP-14? | **move to STEP-15** — seat-private items never reach a file's card; the brief shows them first | they stay hidden |
| s14-D7 | `06` D58 — one card per file naming each ask? | **yes** — and the case needs no edit: one card naming the three people meets it (s14-F4) | the case as written, which now passes too |
| s14-D8 | The headline — cut the move at a clause, or ask the expert for a ≤ 60-character headline? | **cut by code** and show the move whole under *recommended*: no prompt change, no re-record, the same on any model | the same |

### 8.7 · Risks

- **Learning reads the card's current signal.** A version re-points the card; `AUDITED_CARD_JUDGMENTS_CTES` joins a
  card to its signal now, so a verdict on version 1 would be credited to version 2's capability. Every version event
  names the signal it carried; STEP-16 must read a judgment by the version it was given on (calibration stays in
  shadow, D13).
- **Rows keyed by signal.** `agent_claims` and `executions` are keyed by `signal_id`: a card an agent holds is never
  versioned (it waits); an execution follows the version it was claimed on.
- **A card that never closes.** The same advice renews weekly; the review's own stop rule and D57's rungs decide when
  a file stops advising — a renewal must never be a push.
- **A one-time churn at switch-on.** On the first expert sweep of a tenant, every open legacy or compiled card on a
  covered file is still replaced by the file's card — not carried over. Said in the deploy notes (`08`).
- **The order is load-bearing.** If the board counts the app (M42.C4.U03) before an expert card is graded by its check
  (M42.C3.U01), six passes fall; the tree orders them.
- **STEP-13's question card is planned against, not read** — its door's key (the builder stamp) is the lead's
  description; M42.C3.U04 adapts to what lands.
- **Two re-records** on a load-sensitive machine, each restating the board in its five places.

### 8.8 · Built — 12 to 14 Oct, branch `yc2w27-s14` (worktree `s14-build`)

All 45 units of `yc2_w27_s14` (M42, M43), one commit each with its evidence, every code unit mutation-tested (each
mutant run against a baseline that exited 0, survivors closed with tests); s14-D1…D8 taken at their recommended
answers and recorded in `06` (Rohit took them, D66). Merged the integration line twice (`360766a3`, `8c89fe3c` — STEP-13's
second fix wave and STEP-18's Claude 5 thinking fix), each conflict resolved keeping both intents.

**The board** (`03` §F.1, `073da2ad`; `scripts/golden_score.py --assert-recorded` exits 0): must-detect 22/45 → **36/50**,
must-abstain 13/13 → **14/14**, forbidden outputs 0, Atlas passing 6/80 → **12/80**. F176's eight cases pass — one
card each, versioned as its file moved; replay 02 has six founder cases (F59–F64). Lost: F15 (`06` D57, the outreach
wave) and F56 (a vendor's notice at the gate).

**What changed in what you see.** A file has one card; its next decision or question versions it, saying what changed
and keeping the words before; a renewal or a rewording is quiet. Answering a question keeps the card (s14-D3). The
card says who and what the file is, why now, what remains, the move whole, its alternative and when to stop, and its
window with where it came from; its headline is the move cut at a clause. Neither card writer writes a card that names
us, prints a field's name, claims money with none in its evidence, quotes words nobody said or a number nothing
holds — and what it refused is kept (`card_refusals`, 0222) and said by the health check.

**Defects found in our own build and fixed in it**: s14-F20 (the team writer refused every meeting follow-up), F21 (the
contract refused the gold lines), F22 (the connector as a file's subject), F23 (a titled meeting lost its "no words"
line); and the merge's own (`531e1ec3`: the contract pulled `capture` into `contracts/`).

**Waits for others**: the push and the merge to the integration line (the lead); s14-F18 and F19 (the lead, Rohit);
F24 (the statement census counting a bare SQL word, the lead); `08`'s deploy notes for 0220–0222 and the one-time
churn at switch-on (§8.7, Harsh's list).

### 8.9 · The crosscheck of 16 Oct, and its fix wave — branch `yc2w27-s14-fix` (from `9d469efb`)

The crosscheck (`.yc2w27-helpers/reports/step14-crosscheck.md`; five lenses, 70 rows) said **fix first**: two blocking
defects reached the founder. Both are fixed, with the fragile findings the brief named, one unit and one commit each
(failing test first, a mutation run against a baseline that exited 0, guards per group of two or three units).

| Finding | Unit | What it is now |
|---|---|---|
| 1 ⛔ B2 survived versioning | M42.C2.L-interface.V3.U06 (+ its fix) | a card whose ANY version asked you is ours to blank: each version line that asked, and the card's own line while it asks — a decision version still grounds what it says (golden F07); the dossier text unchanged |
| 2 ⛔ the answered card vanished | M42.C3.L-interface.V4.U06 | the question's door admits the answered version (`store.QUESTION_CARD_SQL`, the Monitor lane the answer writes); it offers snooze and requeue only; `doors()` is the health check *every open file card passes one door* |
| 3 a refused version expired the card REPLACED | M43.C4.L-integration.V1.U06 | the file's card is left as it was (`file_cards_kept_on_refusal`); a refusal is kept once per writer, card and rule; the refusals check names the cards waiting behind one. Bound: such a card is on no door while it waits |
| 4 money, quote, number vacuous on an expert card | M43.C4.L-integration.V1.U07 (+ its fix) | an expert decision's card is held to the evidence its move rests on — the check's quotes, the whole retained mails they come from, the facts, code's own lines — for money and quotes; its numbers to the words its check let stand (the check holds every figure); success and do-nothing are read |
| 6 a claimed card held forever | M42.C1.L-data.V1.U04 | held only by a live claim; a card claimed by nobody comes back surfaced; health check *no card is claimed by nobody* |
| 7 a rewording was pushed | M42.C3.L-integration.V2.U07 | `card_version.one_ask`: the same recipient, date, lane and mode and ≥ 0.8 of the shorter move's content stems — one ask, `reworded`, quiet. Bound measured: F25 0.89, F21 0.88 one ask; F24 0.73 another |
| 8 the quiet-push acceptance could not fail | M42.C4.L-integration.V4.U06 | the runner orders a card's history by the sweep that wrote each event; the pushing mutant is its negative control |
| 9 the board's judge skipped the gold lines | M43.C6.L-integration.V3.U11 | `CardView.shown_lines`, read by the forbidden judge (never for what a card is about); P4 events keep their words |
| 10 F63 / m05 passed on the wrong question | M43.C6.L-integration.V2.U12 | `headline_says`: F63 and m05 need the address in the card's headline — blocked (strict xfail): asking a noun-phrase unknown reverses STEP-13 G8's pinned design, a decision for STEP-13b (M37) |
| 11 a renewal spent the day's cap | M42.C2.L-integration.V2.U07 | a renewal is not held to the cap and spends none of the pass's allowance. Bound: its signal still counts in `_budget_used` |
| 13 the health gate red by design | M43.C4.L-integration.V2.U08 | `question_settled`, `left_coverage` (the closed vocabulary +2); REPLACED counted over 7 days |
| 12 a version push spent no budget | M42.C3.L-integration.V2.U08 | a material version pushed today counts in the seat's daily push budget. Bound: no push CHANNEL carries a version (the outbox's key; latent, in-app only) — STEP-15 |
| 14 a refused card rebuilt every pass | M43.C4.L-integration.V1.U09 | a signal refused within a day is skipped (`skipped_refused_recently`), its file's card kept; the refusal's one row says when it last was |
| 7 + 13 | M43.C6.L-integration.V3.U13 | ONE re-record (ideal reader, house order): only F25's answers moved; the board restated |
| docs | — | `08` §0c, §1.15, §3.15 (finding 23); `06` s14-D6, s14-D7; `03` §F.1's mechanisms for F12, F50, F19 corrected |

**The board** (`03` §F.1; `golden_score.py --assert-recorded` exits 0): must-detect 36/50 → **35/50** (F63 now judged on
what its card asks — blocked, STEP-13b), must-abstain **14/14**, forbidden outputs **0**, Atlas passing 12/80 → **11/80**,
blocked 1 → 2 (replay 02 m05, the same card).

**§8.8 restated.** *"A rewording is quiet"* holds now (F25 `reworded`; M42's acceptance requires it). *"Answering a question
keeps the card"* holds now — on the queue, its detail and its one action. *"Neither card writer … claims money with none in
its evidence, quotes words nobody said or a number nothing holds"* holds now for an expert card too. *"A refused version
leaves the card as it was"* holds — as it was, and on no door while it waits (declared).

**Not built in the fix wave — each with its owner** (the crosscheck's findings 15–31; `report_full.md` §4 has the
evidence and the proposed fix of each):

| # | Finding | Owner |
|---|---|---|
| 15 | check.v3 withholds honest alternatives and stop rules that open with an ordinary word (Instead, Rather, Only, Pause… 19 of 42 openers) | STEP-13b `s13b-F4` → M37.C4.L-logic.V8.U02 |
| 16 | a discrepancy on a field outside the 20-entry map is no longer asked (`compose` → None), counted only in its test | STEP-15 (the brief reads `/v1/discrepancies`), with `M43.C4.L-logic.V0.U04`'s map — the lead |
| 17 | gold headlines that are only a condition (F15, F53) or end on a dangling verb or possessive (F05, F06, F61) | `M43.C3.L-interface.V3.U01` (s14-D8) — the lead, next STEP-14 follow-up |
| 18 | a decision's co-recipients carry over into the file's question version (`_stamp_recipients` returns early on an empty set) | `M42.C3.L-data.V1.U02` — the lead, next STEP-14 follow-up |
| 19 | the daily brief counts a living card's versions as staleness (500 bp per version) | STEP-15 (`reason/brief_ranking`) |
| 20 | a version keeps no draft and never names a draft change (the drafts survive in `expert_reviews`) | STEP-16 (learning reads a judgment by its version) |
| 21 | a card the founder called wrong through the feedback route is versioned onto new advice, its verdict printed beside the new headline | STEP-16 — Rohit's decision: does a *wrong* decide the card? |
| 22 | live cards the contract would refuse survive the deploy unchanged | Rohit: a read-only contract probe of production's open cards (`08` §3.15) |
| 23 | `08` said nothing Harsh needs for STEP-14 | **done here** — `08` §0c, §1.15, §3.15 |
| 24 | *what the card contract refused* says NO DATA on zero refusals, so `--require-data` exits 2 on a healthy tenant | `M43.C4.L-integration.V2.U05` follow-up — the lead (said to Harsh in `08` §1.15) |
| 25 | role is the file-kind enum; the file's company and kind of work never reach a card | `M43.C2.L-logic.V0.U02` — STEP-15 with the brief's kind of work |
| 26 | a connector's move replaced by the alternative shows that sentence as both | `M43.C2.L-logic.V1.U01` — the lead, next STEP-14 follow-up |
| 27 | the two writers test money differently; neither knows the graph's value and currency fields | `M43.C4.L-integration.V1.U03` — the lead (one money-evidence function in `contracts/`) |
| 28 | the internal-field rule refuses honest domains whose first label is a namespace word (loop.so, signal.vc) | `M43.C4.L-contract.V0.U01` — the lead, next STEP-14 follow-up |
| 29 | F64 is authored outside the prompt's closed sets and never has a card to clear | `M43.C6.L-data.V1.U07` — the golden set's next re-record (the lead) |
| 30 | replay 02's erased `blocked_on` reasons; m06, m08, m09 without owners | `M43.C6.L-integration.V2.U08` — the lead, with `03` §F.1's notes |
| 31 | F56's stated cause is stale and its loss has no owner | STEP-18 (B26, the junk filter's prompt) — the lead names it |
