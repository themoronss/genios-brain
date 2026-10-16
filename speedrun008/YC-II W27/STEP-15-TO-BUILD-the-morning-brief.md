# STEP-15 · TO BUILD · the morning brief — what a chief of staff tells you at 8

**Owner:** Claude. **Depends on:** `STEP-12`, `STEP-13`, `STEP-14`. **Decisions:** `06` D1 (who orders
the day), D9 (where and when). **Moves:** one brief a day, read in under three minutes, with a
feedback mark on every line.

---

## 1 · What is true now `[CODE]`

| What exists | Where | What it does today |
|---|---|---|
| The executive summary ladder — one line, one minute, five minutes | `executive/summary.py` | deterministic composition; *"an empty morning says 'nothing needs you'"*; sent as the daily digest from the outbox on the heavy tick (`deliver/outbox.py:308-324`; `api/routes.py:1268`) |
| The book-level daily re-rank | `reason/brief_ranking.py:412` `daily_brief_ranking` | compares the day's decisions against each other — concentration, staleness, coverage — as **penalties** on `final_utility_bp`; on-demand API only (`api/l4_seam_routes.py:184-195`) |
| The decision brief, per signal | `executive/brief.py` `compose_brief` | situation, why, recommendation, evidence, risks, alternatives, confidence, do-nothing; no model |
| Meeting prep, per attendee | `reason/meetings/prep.py` | last touch, open commitments both ways, the previous meeting's open items, screen items — precomputed by the post-pass, served by an API |
| Attention | `context/attention.py` → `context_attention` | a deterministic *"look here first"* per node, read by the digest |

The pieces exist; none of them sees a workstream, the expert's judgment, your calendar for the day
and your promises together.

## 2 · Why

A chief of staff's most valuable minute is the first one of your day: *what changed, what is stuck,
what is due, what I would do — and the drafts are ready.*

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the day's inputs | new `executive/morning.py` | every live workstream's latest **validated** expert result; today's and tomorrow's meetings with their prep (`reason/meetings/prep.py`); your promises due (screen `my_promise`, commitments); what changed since yesterday's brief |
| 3.2 | the ordering | one Sonnet-class pass over the day — or `daily_brief_ranking` if D1 = B | the top items with **one reason each**, drawn from the files' appraisals. Guard rails the pass cannot override: a hard deadline within 48 hours and any meeting today are always in; nothing appears without a validated result; every number comes from the calculators |
| 3.3 | the shape | the existing summary ladder | **one line** (*"3 things need you; Insight call Wednesday"*) · **one minute** (the top five with the move and the draft) · **five minutes** (changed · stuck · your promises · meetings with prep · what I am watching and why) |
| 3.4 | delivery | D9 | the dashboard's Today view (Atlas A.10 has the wireframe) at 08:00 IST; e-mail or WhatsApp later, through the existing outbox |
| 3.5 | feedback | `STEP-16` | *useful · not useful because ___* on every line |

## 4 · What will happen — a Monday `[MODELLED]`

```
GeniOS · Monday 6 Oct · 3 things need you

1  Insight Partners, Wed 8 Oct — send Neel the pre-read by Tuesday            draft ready
2  Pankaj (saka.vc), introduced by Boardy 3 Sep — 33 days, nobody has written   draft ready
   (I asked you on Friday whether saka.vc is a fund — still open)
3  Startup India — your DPIIT application moved to ___; ___ is due by ___       steps listed

Changed since Friday   Hub71 wrote · Khushi (247VC) is now 18 days unanswered
Stuck                  the 11 Aug investor wave — 0 of 11, follow-up plan ready
Your promises due      2 from WhatsApp (to ___, to ___)
Meetings               Wed Insight · Wed Noveum (Aditi) · Thu Tryclean (Tejas) — prep in each card
Watching               Theresa (Antler) — waiting for a real milestone before the next update
```

## 5 · Expected

- one brief a day at the set time, empty mornings saying so;
- every line traceable to a validated file;
- your feedback recorded on at least some lines in the first week — the input `STEP-16` needs.

## 6 · Verify

```
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest tests/executive tests/deliver/test_the_digest_is_the_brief.py tests/reason/expert/test_a_small_move_is_a_brief_line.py tests/replays/test_the_morning_brief_is_judged.py -q
#   a deadline within 48 h is always present; a file with no validated result is never present;
#   numbers equal the calculators; an empty day renders "nothing needs you"
#   (restated 16 Oct: the one file this plan named became the files above — the build's tests)
```

---

## 8 · The check of 2026-10-12 — what the 5 Oct plan got right, and wrong

Re-checked claim by claim against `fbd0aeaa` (STEP-13 at 24 of its 29 units) by a read-only worker, and
measured on fresh scratch databases: the twelve *brief-only* golden cases and ten must-abstain cases
replayed from their cassettes (no spend), and the existing morning surfaces called on four of the kept
tenants. The two scripts are in `baseline/yc2w27-s15/`. Production was not read.

Since 5 Oct, STEP-12 gave every changed file one review that decides it, and STEP-13 checks every line of
it and asks you the one question a held file needs. So for the first time the brief has something worth
reading: each file's checked judgment, its question, its numbers. What does not exist is anything that
reads them together. The L4 Executive layer (`executive/`) reads no file, no review, no question, no
promise and no meeting. Its summary ladder still counts signals, and it says *"Nothing needs you right
now."* on mornings when the expert is holding something for you.

### 8.1 · Measured

**The twelve brief-only cases** — what the engine holds after each case's last sweep, and where the brief
would find the line:

| Case | The line the case expects | What the engine holds today | Its section in the brief |
|---|---|---|---|
| F08 | a monitor line, then closed after two weeks | two intro files, both *wait* (low, low), quiet 14.2 and 16.2 days — no card | watching; "closed" waits on the intro playbook's stop rule (`STEP-11` M31) and `06` D57 |
| F14 | wait: send only on a material milestone | one investor file, *wait* at each of three sweeps, quiet 25.1 days — no card | watching |
| F18 | a round closing 31 Oct | **no file**: the notice is archived at the gate (junk gate `drop`, relevance `not_business`) | none — blocked on `06` D29 |
| F20 | a meetup on 27 Sep | *act*, low stakes, low urgency → a Decision card | today |
| F21 | a programme you could apply to | *find out* → an open question | asked |
| F22 | a grant closing 30 Sep, if you are eligible | *find out* (medium, medium) → an open question | asked |
| F23 | your registration is complete (SSM-2026-3381) | *wait, wait, act* (low, low) → a Decision card | changed |
| F30 | your promises, each in its file | *act* decided in **shadow** (a Sales `opportunity`) → nothing; your promise is in L3 (`commitment` "send the pilot proposal", due 25 Sep, from your own sent mail) | promises |
| F45 | how fast you answer Bluepeak: 1.5 days (n=6) | *act* (high, high) → a Decision card; the reply time is computed (`context/workstream_numbers`) and shown nowhere | today, with the pattern |
| F53 | Larkspur quiet after four exchanges in March — six months | *wait → act* (high stakes) decided in **shadow** (Sales) → nothing; quiet 188 days | stuck — only on s15-D2 |
| F54 | the Bluebay mixer, no follow-up to anyone you met | two *find out* files (open questions), one *nothing*; the meeting of 20 Aug | meetings, with the two questions |
| F55 | nothing sent for 28 days while three people wait | three *act* (medium, high) → two Decision cards and a Monitor card; one *wait*; "your last mail" is computed nowhere | your desk |

**What exists says, on the same tenants** — `executive/summary.build_summary`, which is also the Slack
digest's body:

| Tenant, at its last sweep | The ladder's one line | What the expert holds |
|---|---|---|
| F14, 20 Sep | *"Nothing needs you right now."* | a wait rule: stop the weekly updates to Tara |
| F22, 7 Sep | *"Nothing needs you right now."* | a question: are you incubated on campus? The grant closes on the 30th |
| F45, 30 Sep | *"1 open item(s), 0 high-band — top: bluepeak.test, file review."* | introduce Meera to the two pilot leads, as you wrote you would |
| F55, 11 Sep | *"3 open item(s), 0 high-band — top: Dev Malhotra, unanswered email."* | three people waiting on you for 17–26 days; nothing sent for 28 |

The decision brief (`executive/brief.load_briefs`) on F45 prints *"bluepeak.test: file review"*, *"score 64
(critical band), confidence 100"* and the verb *"escalate"*. The ladder calls the same 64 *not* high-band
(s15-F3).

**The golden set's arithmetic.** 12 of the 45 must-detect cases are brief-only and counted not expressible
(`03` §F.1: *21/45 (12 not expressible)*). Without a brief the ceiling is **33/45 (73%)**: STEP-12's
*≥ 90%* needs this step.

**The expert's answers** — 94, over 53 cases:

- the modes: *act* 58, *wait* 20, *find out* 8, *nothing* 8;
- an *act* appraised low stakes and low urgency: **2** — F20 and F23, both brief-only;
- the must-abstain cases hold 7 *act* or *wait* answers. Three of the *wait* answers (F39, F40, F43) are
  about the very subject their case forbids, and those files are quiet 0.3–2.2 days. The brief-only *wait*
  files are quiet 14–25 days.

**F37 failed on the board's own path at `fbd0aeaa`** (must-abstain 12/13): the expert card's `why` quoted
*"Arjun, Introly connected us"*, and the judge read the quote as the card being about the connector.
STEP-13 has since mended the judge (`eb2b0486`: a card's quoted sources are read apart from its words).
The brief's judge must do the same (s15-F7).

### 8.2 · The claims

| # | Claim (§1) | Now | Evidence |
|---|---|---|---|
| 1 | the summary ladder — one line, one minute, five minutes; deterministic; an empty morning says *"nothing needs you"* | **true, and it reads signals, not files**: it is empty when the expert holds a wait or a question (F14, F22), and prints a domain and a reason code when it is not (F45) | `executive/summary.py:25-85` (`:71`); §8.1 |
| 1b | sent as the daily digest from the outbox on the heavy tick | **partly**: only to a *push* channel, and Slack is the only human one; a tenant with only the pull surface (`in_app`) never gets it — the outbox's own note found production's channels were two `in_app` rows (29 Aug). It goes once per UTC day, at whatever hour the 6-hour tick runs; the call has moved to `routes.py:1487` | `deliver/outbox.py:308-324, 330-366, 768-822, 1325-1470`; `deliver/channels/base.py:23-32` |
| 2 | the book-level daily re-rank — concentration, staleness, coverage as penalties; on-demand API only | **true**, with a fourth penalty (role mismatch, `book_ranking@2`). It ranks **carded** decisions only, so a watched file, a question with no card and a shadow-lane file are invisible to it; its day is the UTC date; on for the pilot org (`brief`) | `reason/brief_ranking.py:63-95, 182-185, 297-315, 412-436`; `api/l4_seam_routes.py:183-215` |
| 3 | the decision brief, per signal — situation, why, recommendation, evidence, risks, alternatives, confidence, do-nothing; no model | **partly**: there are no alternatives; for an expert file it prints *"bluepeak.test: file review"*; it is pulled only — `PULL_ONLY` records that whether it should arrive each morning *"is a product question nobody has answered"* | `executive/brief.py:45-148`; `executive/unreached.py:210-216` |
| 4 | meeting prep, per attendee — precomputed by the post-pass, served by an API | **partly**: the prep is what it says. It is precomputed only for a seat with a live device and a meeting in the next **3 hours**, and served as that device's moment; nothing composes the day's meetings | `reason/meetings/passes.py:45, 57-98`; `reason/meetings/prep.py:1-25`; `api/moment_routes.py:146, 198` |
| 5 | attention — a deterministic "look here first" per node, read by the digest | **true**: per node, not per file; the ladder reads one count of it | `context/attention.py:1-21`; `executive/summary.py:50-54` |
| 6 | none of them sees a workstream, the expert's judgment, your calendar for the day and your promises together | **true**: `executive/` reads none of the five (0 modules each) | `grep -rl` over `genios_engine/executive/` |

The units of §3, against what exists:

| | Unit | Now |
|---|---|---|
| 3.1 | the day's inputs | **partly**: each input exists, but one file or one meeting at a time. A file's latest valid review (`reason/expert/store.py:206-217`) returns an older valid review when the newest was refused. A file's open question is read one file at a time (`context/founder_questions.py:70`); STEP-13 now gives it a card of its own (`06` D60), and D60 says the brief lists it too. One meeting's prep at a time. Your commitments are in L3; your screen `my_promise` items are hidden (`06` D8). "Validated" now means **checked** (STEP-13: the fate, the checked words, the question, `0200`). No brief is kept, so "since yesterday" has nothing to compare with — but every review keeps what triggered it, in words (`0199`) |
| 3.2 | the ordering: one Sonnet-class pass over the day, or `daily_brief_ranking` if D1 = B | **overtaken by what was built**: D1 has been A since 10 Oct, and M33 already turns each file's appraisal into its importance and urgency (`reason/expert/decide.py`). Code can order the day from the expert's own judgment without asking a model to judge it again. The guard rails are buildable. *"Nothing appears without a validated result"* would hide your promises, your meetings and your desk, which have no review — restated in §8.4 |
| 3.3 | the shape: the existing ladder | **partly**: its three horizons and its empty morning are worth keeping; its composition is not (s15-F2) |
| 3.4 | the dashboard's Today view at 08:00 IST; e-mail or WhatsApp later, through the outbox | **not as written**: the dashboard is its own repository (`genios-dashboard`) and this one serves routes; nothing in the engine runs at a local hour (s15-F12); no e-mail or WhatsApp adapter exists (s15-F4) |
| 3.5 | a mark on every line (`STEP-16`) | **not built**: nothing stores a mark on a brief line |
| §5 | every line traceable to a validated file | **restated**: every line names its source — a checked review, an open question, the mail a promise was made in, a meeting's event, a calculator with its n |
| §6 | `tests/executive/test_morning_brief.py` | does not exist; replaced by M44's and M45's acceptances (§8.5) |

### 8.3 · New — not in the 5 Oct plan

Proposed for `03`. The ids are provisional; the lead gives them their numbers.

| # | Finding | Evidence | Owner |
|---|---|---|---|
| s15-F1 | **Twelve must-detect cases are the brief's, and the plan's headline number needs them.** F08, F14, F18, F20, F21, F22, F23, F30, F45, F53, F54 and F55 are labelled *brief only* (`06` D12d) and counted not expressible — inside the 45. Without a brief the ceiling is 33/45 | `tests/replays/founder_case.py:65`; each case's `not_expressible.cards`; `scripts/golden_score.py:62-66`; `03` §F.1 | `STEP-15` (M44.C5) |
| s15-F2 | **The engine already says "nothing needs you" when something does.** The ladder (`GET /v1/executive/summary`, the Slack digest) counts signals: *"Nothing needs you right now."* at F14 (a wait rule held) and F22 (a question open); *"top: bluepeak.test, file review."* at F45 | `[TEST]` `existing_surfaces.py`; `executive/summary.py:25-85` | `STEP-15` (M44.C3: an empty morning only when nothing is open, asked, due or watched) |
| s15-F3 | **Two band scales disagree on one decision.** The ladder counts *high* as 70 or more and says *"0 high-band"*; the decision brief calls the same 64 *critical* and says *"escalate"* (F45; F55 likewise) | `executive/summary.py:34`; `executive/brief.py:60` | `STEP-18` — the brief uses neither |
| s15-F4 | **The daily digest reaches a Slack tenant only, once per UTC day, at whatever hour the heavy tick runs.** It is queued per push channel; the only human push adapter is Slack; `in_app` is excluded; production's channels were two `in_app` rows (the outbox's note, 29 Aug). No e-mail or WhatsApp adapter exists | `deliver/outbox.py:308-324, 330-366, 768-822`; `deliver/channels/base.py:23-32` | `STEP-15` (M45.C3: the digest is the brief); e-mail and WhatsApp: `06` D9 |
| s15-F5 | **A file decided on the shadow lane reaches nobody.** F53 (Larkspur, *act*, high stakes) and F30 are reviewed, valid and shown by the check, but each file's home situation is a Sales `opportunity` (Sales off, `06` D2), so the decision is taken in shadow: no signal, no card, no question | `[TEST]` the pass's counters (`expert_shadow 1`, `decided {}`) and `context_situations`; `reason/domain_shadow.py:769-812` | `STEP-15` (s15-D2: a line, never a card); cards stay D2's |
| s15-F6 | **F18 cannot be in any brief.** The round's notice is archived at the gate (`drop`, `not_business`): no file, no review, no words read | `tests/replays/specs/founder/F18.json`; the replay: 0 files | `06` D29 — STEP-15 declares F18 `blocked_on` it |
| s15-F7 | **F37 failed at `fbd0aeaa` — must-abstain 12/13 — and STEP-13 has mended it.** The expert card's `why` quoted *"Arjun, Introly connected us"* and the judge read the quote as the card's own words. The merge `35ec7106` joined two halves that were each green (`593916f1`, `c83a5a63`); `eb2b0486` reads a card's sources apart | `[TEST]` `pytest tests/replays/test_founder_cases.py::test_founder_case -k F37` on a fresh database at `fbd0aeaa`; `git log --graph 593916f1^..fbd0aeaa` | ✅ `STEP-13` (`eb2b0486`); the brief's judge reads a line's quotes apart too (M44.C5) |
| s15-F8 | **The file page shows the expert's unchecked words.** `GET /v1/workstreams/{file_id}` returns the review as the model wrote it (`row.review`), never its check (`row.checked`) | `api/workstream_routes.py:62-71, 97-98` | `STEP-13` (*nothing the expert says reaches you unchecked*) |
| s15-F9 | **Not every waiting file is news.** F39, F40 and F43 (must-abstain) hold a *wait* review about the very subject they forbid; a brief listing every waiting file would surface them. They are quiet 2.2, 2.1 and 0.3 days; the brief-only waits F08 and F14 are quiet 14–25 | `[TEST]` the replays; `golden-labels.md` (*`no` — never surfaced*) | `STEP-15` (watching from the 7-day rung — s15-D4) |
| s15-F10 | **A small move is the brief's shape.** An *act* appraised low and low occurs twice in the 94 authored answers — F20 and F23 — and both are brief-only; today each makes a card | `[TEST]` the authored answers; the replays | `STEP-15` (s15-D3) |
| s15-F11 | **Meeting prep is a desktop moment** — precomputed only for a seat with a live device, 3 hours ahead; nothing composes the day's meetings | `reason/meetings/passes.py:45, 57-98` | `STEP-15` (M44.C2, M44.C3) |
| s15-F12 | **Nothing in the engine runs at a local hour.** Heavy tick every 6 h from process start, light every 15 min; the re-rank's day is UTC; `GET /digest` leaves its 08:30 to the client | `platform/scheduler.py:85-120`; `platform/config.py:136, 143`; `reason/brief_ranking.py:182-185`; `deliver/digest.py:1-5` | `STEP-15` (M44.C4) |
| s15-F13 | **No reader gives every file's current judgment, or every open question.** Both are read one file at a time; `latest_valid` returns an older valid review when the newest standing one was refused | `reason/expert/store.py:206-217`; `context/founder_questions.py:70-86` | `STEP-15` (M44.C2) |
| s15-F14 | **Four morning surfaces exist and none reads a file:** `GET /digest` (the card queue's one line), `GET /v1/executive/summary`, the Slack digest, `GET /v1/intelligence/brief` (carded decisions only) | `deliver/digest.py:8-24`; `api/routes.py:5536-5547`; `api/executive_routes.py:40-55`; `api/l4_seam_routes.py:183-215` | `STEP-15` (one brief; the digest sends it) |
| s15-F15 | **"You have sent nothing for N days" has no calculator** — only each person's `thread.last_outbound`; F55 needs your last mail across every mailbox, with the receipt that proves the silence | `context/waiting.py:133-190`; `context/coverage_receipt.py` | `STEP-15` (M44.C2) |
| s15-F16 | **The decision brief has no alternatives, and for an expert file it speaks codes** | `executive/brief.py:45-148`; `executive/unreached.py:210-216` | `STEP-18`, or retire it once the brief stands |
| s15-F17 | **Your desk read a file's raw open ask, never the expert's own judgment of it.** F38 (must-abstain, *"a question answered on another channel is not owed again"*) failed M44's acceptance on its first run: the brief's desk line named Pooja Iyer as still waiting, two days — the case forbids it. The review's own facts and `wait_or_stop` already read her WhatsApp reply and say nothing is owed; the raw loop stays open regardless | `[TEST]` `tests/replays/test_the_morning_brief_is_judged.py::test_a_must_abstain_brief_names_nothing_its_case_forbids[F38]`, first run; `context/your_desk.py:128-137` | ✅ `STEP-15` (M44.C5) — `executive/morning_day._resolved_nothing`, read-only of `reason/expert/decide.mode_of` |
| s15-F18 | **`run_case`'s own default (`brief=True`, M44.C5.L-integration.V0.U03, `06fbb2c8`) silently composes and keeps a brief for every `keep=True` call** — two tests written before that default existed then read back their own kept-already brief instead of writing one: `test_one_brief_a_day.py::test_compose_reads_the_day_of_a_golden_tenant` (F45, `wrote` false) and `test_what_changed_since_the_last_brief.py` (its whole `world` fixture, F21's "first brief" case saw 0 changes, not 1) | `[TEST]` the M44.C5-closing repo-wide guard on `tests/executive`, first run (2 failed, 230 passed); both call `run_case(..., keep=True)` with no `brief=` | ✅ `STEP-15` (M44.C5) — both calls now pass `brief=False`, restoring each test's own compose/read_day as the day's only composer |

### 8.4 · What changes in the design

1. **The day is read, not judged.** For your seat, at the brief's hour, code reads the day in one pass
   (`executive/morning_day.py`). It reads:
   - every file's current judgment — the newest review that stands, through its check, never an older
     valid one standing in for a newer refusal;
   - the questions your files ask, each with the card that asks it (`06` D60, STEP-13's question card);
   - your desk: your last mail, and who has waited on you since when (F55);
   - today's and tomorrow's meetings with their prep, composed for the day; and the external meetings of
     the last two weeks with no follow-up within a week (F54);
   - your promises due within a week or overdue (F30);
   - your reply time beside a waiting file, where it holds (n ≥ 5, F45), and a file gone cold after real
     exchanges (F53's shape);
   - what changed since your last brief: each review since, with what triggered it.

   Every item carries its material — the checked words, each number with its calculator and n, dates,
   names — and its sources. No model.
2. **Code orders it; the expert has already judged each file.** Under D1 as built, a file's importance and
   urgency are its appraisal, mapped by code. So the day is ordered from them, not by a second model asked
   what matters (the 5 Oct plan's Sonnet pass).
   - Today's five: a meeting today and a dated deadline or promise within 48 hours are always in. Then the
     open decisions by `reason/brief_ranking.book_rank` — the re-rank already on for your org, so the
     brief and `GET /v1/intelligence/brief` agree on #1. Then the questions.
   - Watching lists a waiting file once it is quiet past the first rung, 7 days (s15-F9). Stuck lists a
     file whose move is yours, quiet past 14.
   - Each section is capped, and the brief fits 600 words — three minutes.
3. **A cheap model writes it; the check holds it; a strong model only when the cheap one fails.** This is
   your 12 Oct direction, and the site machinery already has its pattern (R-6's own note: *"the
   deterministic validator is what makes a cheap model safe … Sonnet is the ESCALATION"*).
   - The writer (R-8, Haiku-class) gets the ordered day. It writes the one line, each line from its item's
     material, one reason for each of today's five drawn from that file's appraisal, and at most one
     observation across files — labelled as its own reading: the 30-year chief of staff speaking.
   - It may not add, drop or move an item, or state a name, number or date it was not handed.
   - The check holds each line to its own item with STEP-13's one invention rule
     (`platform/grounding.invention_ok`): you are "you", never "the founder"; a connector is never the one
     to act. A line that fails gets code's words back; the item stays.
   - Two failed lines, or an answer malformed after its one repair, and the brief is asked once of Sonnet
     (R-8E). If that fails too, the template stands, and the brief says so. Never Opus.
   - About a cent a day on Haiku, two on Sonnet `[MODELLED]`. Model-agnostic: the tier is configuration,
     the prompt names no model, and both models are measured on the same briefs (the live look).
4. **Every line says where it came from, and takes your mark.** A line keeps its sources. The brief is kept
   once per seat per local day (`0230`), with how it was written and what it cost. Each line takes
   *useful*, or *not useful, because ___* — recorded, never learned from here: STEP-16 turns marks into
   proposals you accept.
5. **08:00 in your timezone, on any tick.** Every sweep — the 6-hour tick, the 15-minute tick,
   `/ingest/all` — ends by composing the briefs that are due (the local time past the hour, none kept
   today). The row is the claim, so two replicas compose once. `GET /v1/executive/morning` serves it, and
   composes on read if no tick did. The Today view is `genios-dashboard`'s screen; until it is built the
   brief is a route, as STEP-07's brief still is.
6. **One morning surface.** The Slack digest becomes the kept brief (its one line and today's five), not
   the signal count. The ladder, the decision brief and the re-rank stay as pull routes. An empty morning
   says *"Nothing needs you today"* — and only when nothing is open, asked, due or watched.
7. **The golden set judges the content; the live look judges the words.** The runner composes the brief
   after each case's last sweep with **no model** — its selection, order, numbers and names are code's.
   The marking judges the brief-only cases on their lines, every must-abstain case on naming nothing it
   forbids, and every case's forbidden phrases over every line. The writer's words are judged by the check,
   by mutation, and by a live look on Haiku and Sonnet before the writer reaches your account. This is
   STEP-12 §8.3 N8's split: the board measures the plumbing, the live pass the model.
8. **Three things stay yours** (§8.6): a file on the shadow lane (F53, F30), a small move (F20, F23), and
   your screen reminders (`06` D8). Each is a unit built only on your answer.

### 8.5 · What will be built — tree block `yc2_w27_s15` (M44, M45), proposed

**M44 — the brief's content, read and ordered by code, at 08:00** (20 units, no model):

- C1, what a brief is: the contract; `0230_morning_briefs`;
- C2, the day's material: every file's current judgment, every open question with its card, your desk,
  the meetings of a day, your promises due;
- C3, the day assembled and ordered: the order, the day, the template, what changed;
- C4, where it runs and arrives: the store; compose and `compose_due`; the tick; `GET /v1/executive/morning`;
- C5, the golden set judges it: the case contract, the twelve cases restated, the runner, the marking, the
  acceptance.

**M45 — the brief in a chief of staff's words** (14 units):

- C1: the writer's sites (R-8 Haiku, R-8E Sonnet, never Opus), its own budget, its switch `morning_brief`;
- C2: the prompt, the line check, the writer;
- C3: compose through the writer, your mark, the digest as the brief;
- C4: your three decisions, one unit each;
- C5: the live look, and the acceptance.

**34 units (20 in M44, 14 in M45), critical path 9:** the contract → `0230` → the store → what changed →
compose → the runner → the marking → M44's acceptance → M45's acceptance (or the small-move unit). Each
unit, its artifact and its verify command are in `baseline/yc2w27-s15/tree_s15.yaml`, for the lead to merge
into `tree.yaml` — the tree guard then counts one more block.

**The board this moves:** must-detect **21 → 31 of 45** at M44 (ten brief-only cases), **32** with s15-D2
(F53). F18 stays blocked at the gate (`06` D29). Must-abstain holds; forbidden outputs stay 0, now over
cards *and* brief lines. With STEP-14's living card the ceiling is **44 of 45**.

**Order:** STEP-13 closed first — its question card is where an asked line leads. STEP-14 is not a
precondition: the brief is built per file, from reviews, not from cards. s15-D3's unit edits
`reason/domain_shadow.py`, not `deliver/`, so it does not collide with STEP-14's rewrite of the card
pipeline.

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| s15-D1 | Who orders the day, and who writes it? | code orders from the expert's appraisals (D1 as built); Haiku writes from the checked material; Sonnet once when Haiku fails the check; never Opus; a live look on both models first (58 briefs, under $1 `[MODELLED]`) | code orders and the template writes — no model, nothing spent |
| s15-D2 | A file decided on the shadow lane — its domain switched off (F53 Larkspur, F30): a line in your brief? | yes — labelled "outside your switched-on work", never a card; D2 still governs cards | no — the brief shows only what the live lane decided |
| s15-D3 | A move appraised low stakes and low urgency (F20, F23): a card, or only a line in the brief? | only the brief — your labels' answer | a card too, as today |
| s15-D4 | Which waiting files does *Watching* list? | those quiet past 7 days, with the expert's wait rule (F39, F40, F43 stay unsurfaced) | the same |
| `06` D8 | Screen reminders out of hiding? | yes — in your brief first, beside the file whose person they name; the popups stay hidden | hidden |
| `06` D9 | Where and when? | the engine composes at 08:00 in your org's timezone (set it at deploy, do not leave it inferred) and serves the route; the Today view is `genios-dashboard`'s to build; a Slack tenant gets the brief as its digest; e-mail and WhatsApp need a new channel — later | dashboard only, 08:00 |
| `06` D29 | (open) the filter, with the brief, keeps a fund's round notice? | decides F18 — not this step's | F18 stays blocked |

### 8.7 · Risks

- **The template reads like a report.** Code's own words are correct and plain. Whether Haiku's are
  better is what the live look measures; until you say yes (s15-D1), the template is what you read.
- **A sparse rule.** *Watching after 7 days* rests on five measured files (two in, three out). The live
  look and your marks say whether it holds.
- **A brief that surfaces what you said never to surface.** The acceptance holds every must-abstain case's
  brief to its forbidden subjects. A quote that names a connector is how F37 broke (s15-F7); the template
  carries no quotes, and the judge reads a quote apart from a line's words.
- **Two green halves, one red merge.** STEP-13 lost F37 that way. The brief's golden acceptance runs after
  every merge into the step's branch, not only on each half.
- **Seen by nobody.** Without the dashboard's Today view the brief is a route, as STEP-07's brief still
  is. And until the expert is switched on for your org (STEP-12's deploy and live pass), the brief has no
  judgments to show — only your promises, your meetings and your desk.
- **The wrong hour.** `orgs.timezone` is inferred from your send hours when unset; set it once at deploy.
- **A neighbour's plan.** STEP-16's plan may draw the same store for a line's mark; one of the two stands.

### 8.8 · Built — 16 Oct (`yc2_w27_s15`, branch `yc2w27-s15`, merged with STEP-14's `yc2w27-int14` 9d469efb)

**What was built — 34 units (20 in M44, 14 in M45), every code unit mutation-tested.** The brief is read, ordered and
worded by code from the expert's own judgment of each file: `contracts/morning_brief` (items, sections, lines, frozen),
`0230_morning_briefs` (one brief per seat per local day; your mark on a line), `executive/morning_day` (the day: files,
questions, desk, meetings, promises, screen reminders, what changed), `morning_order`, `morning_template` (code's words;
the fallback), `morning_prompt` / `morning_check` / `morning_writer` (R-8 Haiku-class, R-8E Sonnet-class once, then the
template; never Opus; its own budget $0.25/day and $0.03/call each; behind the feature `morning_brief`, off), `morning`
(compose once per seat per local day at 08:00 in the org's timezone; `compose_due` ends every sweep), `GET
/v1/executive/morning[/{day}]`, `POST /v1/executive/morning/lines/{line_id}/mark`, and `scripts/golden_eval.py --site
brief` (the live look). The last two units: **the Slack digest is the kept brief** (its one line and today's five, claimed
once the brief is kept, for the org's LOCAL day, read at the drain by the day it was queued for; a pull-only tenant reads
the same brief on the dashboard) and **a small move is a line, never a card** (s15-D3).

**The board** (merged with STEP-14, a new measurement): must-detect **47/50** (36 STEP-14 + F08 F14 F20 F21 F22 F23 F30 F45
F53 F54 F55), must-abstain 14/14, forbidden 0, Atlas 12/80; the three left are F15 (`06` D57), F18 (`06` D29, the gate)
and F56 (the gate). `--assert-recorded` exits 0. Guard round on fresh databases: root, platform, replays and every other
folder exit 0 (03 §F.1 has the numbers).

**What you see** — a brief, in code's words (golden tenants, no model):

    F55   Today   Pinegrove: Reply to Rhea with an apology for the delay and new times for the call.
                  Tanglewood: Send Dev the pricing sheet with a short apology for the delay. — outside your switched-on work.
          Desk    You have sent nothing for 28 days while 3 people wait on you: Dev Malhotra (26 days), Rhea Thomas (22 …).
    F45   Today   Bluepeak: Introduce Meera Shah to the two pilot leads … You usually answer Meera Shah in 1.5 days (n=6).
          Changed Bluepeak: Meera Shah wrote; their move, quiet 15 days — past the file's usual gap of 4 days.
    F22   Today   University Startup Cell: A university cell's notice of a seed grant closing on the thirtieth … Can you
                  tell us whether you are a startup incubated on the university's campus? By 30 Sep.
    F23   Today   State Startup Mission: File the registration number … (a line; no card — a small move)

**What was found** (provisional numbers, for 03): s15-F19 a question line that is only the ask no longer says what it is
for (STEP-14 reworded F22's) — it now carries the review's situation; s15-F20 F64 — the changed section reopened a closed
introduction — a file whose review found nothing owed has no change line; s15-F21 `store._CURRENT` drifted from `_stored`
in a textually clean merge (a pure guard now joins them); s15-F22 F53's `stuck` was authored before any line existed —
restated to `today`; s15-F23 pins on authored words moved with STEP-14's rewording (F55's Meadow rule); s15-F24 D66's words
alone would have taken STEP-14's F61 (low/low introductions labelled a card each) — the small move is narrowed to a move
that writes to no one. Also: the digest was a count of signals at the heavy tick's UTC day (s15-F4) — and `summary.
build_summary` is pull-only again (`unreached.PULL_ONLY`).

**What waits.** *Rohit / the lead:* **s15-D5** — should a decision outside your switched-on work, quiet six months (F53),
leave today's five for `stuck`? (today: it stays, `morning_order`); **s15-D6** — did D66 mean "writes to no one"? (built
so; F61 forces it); `06` D29 (F18). *Before arming the writer:* run `scripts/golden_eval.py --site brief --dry-run`, then
the live look with a key and `--spend-ok` on Haiku and Sonnet (≈ $1) and read it; only then switch `morning_brief` on.
*The digest rides the heavy tick* (every six hours), so it leaves up to six hours after the brief is kept; calling the
distribution pass from `routes._compose_due_briefs` would land it at 08:00 — a one-line follow-up in `api/routes.py`, not
made. *Front-end:* the Today view reads the route; the mark control. *Later:* e-mail and WhatsApp channels (`06` D9).

**For Harsh — deploy** (`08` §0c, §1.15): apply `0230_morning_briefs` (two new tables; additive); **set `orgs.timezone`
for Rohit's org** (08:00 is read from it, else inferred from his send hours); `morning_brief` stays off until the live look;
nothing else changes at boot. A Slack tenant's digest changes from the signal count to the brief.

