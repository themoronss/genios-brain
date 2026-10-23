# 07 · The loopholes: why the website does not make the ideal cards

**Written for:** Rohit and Harsh (and every coding agent that builds a fix).

On 23 Oct Rohit opened the local ideal-state dashboard (`GeniOS-Ideal-Dashboard/index.html`, outside this repo) and asked: *"ye cards locally bane hain, website pe kyu nahi ban pa rahe?"*

**The short answer.**
- The local cards were written by a **Claude session**. It read his whole Gmail and Calendar through connectors (all threads since Nov 2025), joined facts across threads, and wrote each card itself, with no budget and no check.
- The product has to do the same job through the pipeline: **L1 Signals → L3 Context Graph → L2 Qualification → L5 Delivery**.
- That pipeline has **23 loopholes**, listed below. Each one is enough on its own to stop, thin or garble a card like the ideal one.

The running example is the ideal dashboard's **Theresa / Antler card (`i1`)**. Its fields:
- **head:** one action;
- **sum:** two lines;
- **how;**
- **who / for whom / by when;**
- **steps;**
- **avoid;**
- **done when / if not;**
- **alternative;**
- **draft;**
- **the goal it moves;**
- **verbatim quotes from 3 threads;**
- **one new fact taken from another thread** (today's NSRCEL review).

> ⚠ No text from that dashboard is copied into this repository. It holds Rohit's real mail. The field names are what we measure against. S44.U1 (`scripts/ideal_card_gap.py`) scores product cards against it field by field, on his machine only.

**See also [07-IDEAL-PREVIEW-LIVE](07-IDEAL-PREVIEW-LIVE.md)**, written by another session on 23 Oct. It covers the same target card by card, at `brain.thegenios.com/preview` (owner-only), and adds units N1–N6. This file is the layer-by-layer view. S44.U1 (`ideal_card_gap.py`, field by field) is the field-level complement to 07's N5 (`preview_parity.py`, whether each card is present).

Status key:
- ✅ fixed in GeniOS-011 (on `origin/speedrun008`, not yet deployed);
- ⏸ built and held;
- 🔨 being built now;
- ⬜ open;
- 🔒 blocked on someone (named).

## A · Is the product running at all for Rohit's org?

| # | Loophole | Evidence | What it does to the card | Status · fix |
|---|---|---|---|---|
| A1 | **A lapsed trial stops the whole chain.** Since `7075014c` (4 Oct) the scheduled sweep skips L1 → L5 for an expired org, and the warm lane refuses its events. That commit measured Rohit's grace as closed on 21 Sep. Only a manual **Sync now** still reasons. | `api/routes.py` `_plan_expired` (≈983-1018, 1152-1167, 1228-1232); `platform/warm_lane.py:171-176` | No new card at all, or only after Sync now. Fits "fewer, and sometimes". | 🔒 **Harsh: S02.U1**, put his org on a non-expiring internal plan. ⏸ S02.U5 (every skip becomes a visible row) waits for that, because it makes Sync now refuse an expired org too. |
| A2 | **The switches that arm the expert and L2 are all off by default.** These are `expert_review`, `l2_reasoning`, `l2_cards` and the Founder Office domain. The golden set turns them on for its tenants; production has them only if Harsh flipped them. | `platform/l4_activation.py:100-122`; `Domain Expertise/Founder Office Expertise/domain.yaml:45`; `tests/replays/engine_runner.py:345, 395-427` | With `expert_review` off, no file is ever judged. With Founder Office off, investor and programme work has no playbook. | 🔒 **Harsh: S02.U3**, read the production state (SQL in [04](04-FOR-HARSH.md)) and switch them on for Rohit's org. |
| A3 | **Nobody can see what is deployed.** `/health` did not name the SHA, and no daily production number exists. | audit `process-live-sha-not-observable`, `process-no-production-number-after-deploy` | Nobody notices that cards stopped. | ✅ S03.U1 (`/health` has `build_sha` and `schema_head`); ✅ S05.U1 (`daily_health` row and alerts); 🔒 Harsh sets `GENIOS_BUILD_SHA` at deploy. |

## B · L1 Signals: the mail never arrives, or arrives as a stub

| # | Loophole | Evidence | What it does to the card | Status · fix |
|---|---|---|---|---|
| B1 | **The history window is 60 days.** Theresa's last mail (7 Aug) was 77 days old on 23 Oct. The thread may never have entered memory. | `capture/connectors/backfill.py:34-37` `DEFAULT_BACKFILL_DAYS = 60` | The ideal card's three quotes do not exist in the product. | 🔨 S09.U1 (the window the founder picks is the window captured); 🔒 **Harsh: S09.U4**, a 365-day resync for his connections. |
| B2 | **A refused or failed Gmail full fetch fell back to the list snippet**, so a 200-character preview was treated as the body. | `capture/connectors/composio.py` (`_full_message` returned `{}`, `src = full or m`) | The model reasons over a fragment and the quotes don't match, so the card is held. | ✅ S06.U2 (retry once, then park as DOC-05, never pass a snippet off as the body). ⬜ A message re-fetch rung for DOC-05 email parks. |
| B3 | **A junk verdict didn't stand.** The drain re-admitted `llm_junk` archives on their snippet every heartbeat. | `capture/parked/drain.py:166-247` (before) | Newsletters are extracted as if they were work, and real work is crowded out. | ✅ S06.U1. ⬜ Wiring the whole-message reader (`composio.whole_message_reader`) into `api/routes._reread_unread`. |
| B4 | **The junk gate judges "is a human writing?" without seeing who sent it.** There is no sender name, no domain and no "reply to us" flag. | `capture/gate/relevance.py:108, 279-286, 339` | A stranger who is a real investor or fund can be archived (golden F18 still is). | ⬜ S08.U1, then measure with the live key (S07). |
| B5 | **The 16-type signal vocabulary has no word for an intro, a meeting, a fundraise, an application or a request.** The open lane has 698 candidates and 0 promoted. | `contracts/signal.py:239-300`; migration 0176; `context/lane_health.py:75` | Founder work is typed wrong (a fund outreach became `contract_renewal`), or not at all, so the L2 pass never triggers on it. | 🔒 **Rohit: S12.U1** (the contract decision), then S12.U2. |
| B6 | **The evidence fetchers are built but unarmed.** `build_fetchers` returns `{}` unless `GENIOS_NEED_FETCHERS` is set. | `capture/acquire/need_executor.py:224-246` | When L2 says "I need the earlier mail", nobody fetches it, so the hold never resolves. | 🔒 **Harsh: S13.U4** (arm it), plus the HOLD → need → resolve wiring. |

## C · L3 Context Graph: the work is never filed together

| # | Loophole | Evidence | What it does to the card | Status · fix |
|---|---|---|---|---|
| C1 | **A reply after a reading joined the reading's synthetic id, which is no file.** The 'filed' count also counted it. | `context/correlation.py` `thread_correlations`; `context/workstreams.py` `_NAMED_MAIL` | The reply is not in Theresa's file, so the judgment never sees it. | ✅ S14.U1 |
| C2 | **Many events never reach any file, silently:** noise, archived, held, parked, anchorless and private events. The funnel has no "filed" stage. | `context/pipeline.py:2326`; `context/runner.py:179-183, 419-443` | Evidence is missing with no trace of why. | ⬜ S14.U4 (a filed count on the funnel), S17.U1 |
| C3 | **L3 creates situations before any reasoning**, through nine writers. "L2 proposes, L3 admits" runs in shadow and gates nothing. | `api/routes.py:797-823`; `context/l2_admission.py:1-26` | Old keyword rules decide what exists, and the expert judges whatever they made. | ✅ S04.U1 (a guard: the nine writers may only shrink); ⬜ S24 (admission decides existence, first type) |
| C4 | **Admission sees only situations anchored on the file's own node.** Every reading situation (awaiting reply, overdue promise, meeting, document) is invisible to it. | `reason/l2/sweep.py:373-375`; `context/workstreams.py:314-325` | The judgment can't admit or close the real open loop. | ⬜ S15.U1 (reading situations name their file) |
| C5 | **One counterparty holds several live situations:** one per keyword domain and one per 45-day generation. | audit `l3-one-subject-many-situations` | The L2 judgment holds, and the file falls back to the old lane. | ⬜ S15.U2 (one live situation per file) |
| C6 | **A history rebuild deletes situations and re-mints random ids.** | audit `l3-rebuild-deletes-situations-and-ids` | Admissions, resolutions and human closes are orphaned, and closed cards come back. | ⬜ S14.U2 (deterministic ids) |

## D · L2 Qualification: the judgment is skipped, capped, held or lost

| # | Loophole | Evidence | What it does to the card | Status · fix |
|---|---|---|---|---|
| D1 | **A valid judgment made no card unless L3 had already filed a situation on the file, in an activated domain.** `general` (the fallback domain) is shadow-only. | `reason/domain_shadow.py:546-561, 741-756, 796-798, 952-1000` | The judgment is right and no card appears. | ✅ S18.U1 (judged files are decided first, and every no-card reason is counted and logged); ⬜ S18.U4 (bind the decision to the file itself) |
| D2 | **The formula lanes spent the 7-a-day card cap before the judged files were decided.** | same | Template cards take the slots, and the expert's card is dropped. | ✅ S18.U1 |
| D3 | **`l2_cards` without `l2_reasoning` or an R-9 client** handed every file to a pass that silently skipped. One oversized file stopped the whole pass. | `reason/expert/sweep.py:171, 307-309` | No review at all. | ✅ S18.U2 |
| D4 | **Every skip was invisible:** budget, refusal, truncation, hold and no situation. | audit `l2-skips-invisible` | Nobody can say why a card is missing. | ✅ S18.U3 (8 counts on the sweep outcomes, `pipeline_health`, and `why_no_card` on the file page) |
| D5 | **The claim check holds most real-model answers, and the founder gets an engineer's sentence.** Real model, 12 Oct: 68 of 86 held. The fix that cut it to 18.5% (STEP-13b) sits on an unmerged branch. | `contracts/claim_check.py:38` (check.v4); `reason/expert/verify.py:787-793`; branches `yc2w27-int13b` / `yc2w27-s13b` | "We held the one we found: a fact your move rests on quotes nothing…" replaces the advice. This is the weird card. | 🔒 **Rohit: S20.U1** (go for STEP-13b), then S20.U2–U4 |
| D6 | **The founder playbooks are unreviewed.** The investor sheet has 146 lines and the programme sheet 121, all with decision `''`. The compiled lane refuses every Founder Office situation. | `speedrun008/YC-II W27/review/*.review.yaml`; Founder Office `capability.yaml` `status: draft` | Investor and programme work, exactly the Theresa case, gets no compiled card. | 🔒 **Rohit: S23.U1** (accept the default "label and use"), then S23.U2 |
| D7 | **A quiet file with no reply pattern is never looked at again.** A one-touch outreach has no "usual gap". | `reason/expert/triggers.py:24-30, 150-173` | Silent investor threads never resurface (golden F15). | 🔒 **Rohit: D57**, then S21.U2 |
| D8 | **One file at a time.** The judgment reads only its own file's dossier. A fact from another thread or the calendar is not there. | `reason/expert/dossier.py`; `reason/l2/dossier.py` | The ideal card's "today's NSRCEL review is a new fact" cannot be written. | ⬜ S22.U2 (Plane D package), S29 (goals in the judgment); 🔨 S16.U3 (snapshot unknowns and contradictions, held, see E4) |
| D9 | **A subject with no file, such as a first mail, can never become a card.** | `reason/l2/sweep.py:381`; `context/l2_admission.py:97-102` | New work is invisible until L3 files it. | ⬜ S21.U3 |
| D10 | **The production models have never been measured.** Every golden answer is pre-written by the ideal reader. | 67 of 67 cassettes `source=ideal_reader` | "Green" never meant good cards. | ✅ S07.U1 (the harness asks R-9 on its real model, with a 2-call probe); 🔒 **Rohit: S07.U2** (key and ~$5 cap) |

## E · L5 Delivery: the card is cut, repeated or never shown

| # | Loophole | Evidence | What it does to the card | Status · fix |
|---|---|---|---|---|
| E1 | **There is no card writer.** The subject is the model's move cut at 60 characters at a preposition. "Needs a decision —" leaves 41 characters. | `deliver/card_builder.py:868-916`; `deliver/render.py:26`; `deliver/pipeline.py:1003` | Garbled headlines, for example "Send calendar invites with meeting link to body". | 🔨 **S34.U3** (`deliver/card_copy.py`: one checked model call per new card version that writes your fields, behind a switch, off) |
| E2 | **The expert's "if you act now" (`scenarios.act`) and its step never reach the card.** | `reason/expert/decide.py:323-330` | "What doing it gets you" is stock text or empty. | ⬜ S34.U2 |
| E3 | **Card context is the person's last 4 meetings and 3 promises, for every card on that person.** | `api/routes.py:5225-5372` | The same "why" appears on every card. The dashboard then hides repeats, so cards look thin. | ⬜ S34.U1 |
| E4 | **Question, team and meeting follow-up cards reached only the Cards page**, and follow-ups gave a 404. | `deliver/store.py:28-31, 767-788` | Home, MCP, Ask and push never showed them. | ✅ S36.U1 + S36.U2 |
| E5 | **No goal on any card.** No goal object, no goal field, and the drafter never saw the work in motion. | audit `goals-*` | "The goal it moves" is blank. | ✅ S27.U1 (the drafter sees files, situations and in-motion lines and proposes one goal per piece of work); ✅ S26.U3 (plan: L2 proposes, you approve in one click); ⬜ S28–S31 (the goal object, the goal in the judgment, the goal on the card) |

## F · Process: why we kept not noticing

| # | Loophole | What it did | Status · fix |
|---|---|---|---|
| F1 | 823 commits reached the prod branch in one push (21 Oct), with CI red on 4, 9, 11 and 21 Oct. | Cause and effect can't be separated. | 🔒 **Rohit + Harsh: S03.U2** (branch protection, deploy only green SHAs) |
| F2 | Golden runs share one scratch DB, and the runner's connection id is global. Overlapping runs steal each other's mailbox. | False CassetteMiss, and wasted hours (23 Oct). | ⬜ new unit: per-run connection ids in `tests/replays/engine_runner.py` |
| F3 | Replays judge at past instants, but `recorded_at` is wall-clock. | S16.U3's correct as-of read empties every L2 replay snapshot. | ⏸ S16.U3 held; ⬜ new unit: the harness pins knowledge time |

## What closes the gap fastest (recommended order)

1. **Harsh, in production, this week:**
   - A1: the internal plan;
   - A2: the switches;
   - B1: the 365-day resync;
   - B6: the fetchers;
   - deploy `origin/speedrun008` with migration 0251.
   See [04-FOR-HARSH](04-FOR-HARSH.md).
2. **Rohit, decisions (one line each in [06](06-DECISIONS.md)):**
   - D5: STEP-13b go;
   - D6: playbooks "label and use";
   - D10: ~$5 for one real-model pass;
   - B5: L1 contract words;
   - D7: D57.
3. **Claude, code, in this order:**
   - S34.U3 card writer (🔨);
   - S09.U1 window (🔨);
   - S44.U1 scorecard (🔨);
   - S34.U1/U2;
   - S15.U1/U2;
   - S20 (after D5);
   - S28–S31 goals.
4. **Measure on Rohit's real data:** `scripts/ideal_card_gap.py` against the ideal dashboard, after each deploy. A green CI is never the measure.
