# 09 · The steps: what to do, in what order, who does it, and how to know it worked

**Written for:** Harsh (he runs the order) and the coding agents he assigns.
**How to read:** eight steps, each ending in a gate. A step is done when its gate passes **in production on Rohit's org**, not when CI is green. Each unit's detail is in files 03–08; each new unit's agent brief is in [10](10-UNIT-BRIEFS.md).

## The rules every step follows

1. **One unit, one commit, its own tests, one mutation proof** (revert the change → its test goes red → restore → green). Full suites run in CI ([memory rule, 18 Oct]).
2. **Only CI-green SHAs reach `harsh/mvp`.** After each deploy: `GET /health` shows the SHA; tomorrow's `daily_health` row exists and its card count did not fall below half the 14-day median.
3. **No production read without Rohit's yes, and no paid model pass without his spend yes.** Every paid pass starts with a 1–2 call probe.
4. **Beside, not instead** (GeniOS-008 Rule 2): a new path runs beside the old one, and a switch flips only when the new path is at least as good, measured.
5. **No real names in the repo.** Golden cases are synthetic analogues. The `/preview` content stays outside the repo.
6. **One writer per file.** The table at the end lists which units share files; give them to one agent in sequence.
7. **After every step:** run `scripts/preview_parity.py` (N5, once built) and `scripts/ideal_card_gap.py` (S44.U1, on Rohit's machine), and write one line in [13-LOG](13-LOG.md): which `/preview` cards appeared, which are missing, and each missing card's `why_no_card`. Never edit the "expected" lines of this file to match.

---

## Step 0 · Know what is deployed and what production holds (no code)

| # | Unit | Owner | Do |
|---|---|---|---|
| 0.1 | S01.U3 | Harsh | Write in 13-LOG: deployed SHA and date, migrations ≥ 0191 applied, env switches set (`GENIOS_NEED_FETCHERS`, `GENIOS_L4_LLM_DECISION_MAKER`, `GENIOS_BUILD_SHA`) |
| 0.2 | S01.U2 | Rohit's yes, Harsh runs | `python scripts/g011_prod_readings.py --org <ORG> --show-sql`, then `--out readings.json`. Never commit it. |
| 0.3 | H-check ([03 Part C](03-RUN-GATE-AND-SWITCHES.md)) | Harsh | `l3_activation` and `l1_semantic_activation` rows for the org |

**Gate 0:** the readings exist; the org's plan state, switch state and the 4 Oct funnel's current numbers are known.

---

## Step 1 · Make the chain run, and switch the expert on

| # | Unit | Owner | Depends on |
|---|---|---|---|
| 1.1 | S02.U1 non-expiring internal plan | Harsh | Gate 0 |
| 1.2 | Deploy `origin/speedrun008` to `harsh/mvp` (fast-forward; migration 0251 applies at boot; set `GENIOS_BUILD_SHA`) | Harsh | CI green on that SHA |
| 1.3 | S02.U5 merge (every door asks one gate) | Claude | 1.1 confirmed |
| 1.4 | U12-01 an expired org is never silent | Claude | — |
| 1.5 | U12-02 `activate_tenant.py` applies what it says | Claude | — |
| 1.6 | U12-03 a judged file is always decided | Claude | — |
| 1.7 | S02.U3 expert_review + l2_reasoning + founder_office on (admin routes until U12-02 ships); `l2_cards` stays off | Rohit's yes, Harsh | 1.2 |
| 1.8 | S02.U4 brief lines and self identity | Rohit accepts | — |
| 1.9 | S03.U2 branch protection | Rohit + Harsh | — |

**Gate 1:** no `l1_skipped_plan_expired` for the org for 2 days; `daily_health` rows for both days; `expert_reviews` rows for the org exist; `why_no_card` counts are visible in the sweep log.
**Expected cards:** `f4`.

---

## Step 2 · Bring the mail in: 365 days, the founder's senders, the fetchers

| # | Unit | Owner | Depends on |
|---|---|---|---|
| 2.1 | S09.U3 window decision (default 365) | Rohit | — |
| 2.2 | S09.U1 the window the founder picks is captured | Claude (🔨) | — |
| 2.3 | U12-04 fetchers use the real window | Claude | — |
| 2.4 | S08.U1 the gate sees who wrote | Claude | — |
| 2.5 | U12-05 founder mail classes in the gate | Claude | — |
| 2.6 | wire the whole-message reader into `_reread_unread`; DOC-05 re-fetch rung | Claude | 1.3 (routes free) |
| 2.7 | S07.U3 L1 live pass (gate + extraction on the production model), probe first | Claude, Rohit's spend yes | 2.4, 2.5 |
| 2.8 | Deploy 2.2–2.6 | Harsh | CI green |
| 2.9 | S09.U4 the 365-day resync, by the runbook in [04 Part A](04-L1-SIGNALS.md), cost estimate first | Harsh, Rohit's spend yes | 2.8 |
| 2.10 | S06.U4 promote archived Boardy and portal mail (dry run → Rohit → apply) | Harsh | 2.8 |
| 2.11 | U12-10 a promoted archive is filed (can ship with 2.8) | Claude | — |
| 2.12 | S13.U4 `GENIOS_NEED_FETCHERS=on`, and the HOLD → need → resolve wiring | Harsh + Claude | 2.8 |
| 2.13 | S09.U2 business facts for old mail | Claude | 2.9 |
| 2.14 | U12-17 the catch-up budget after the resync | Claude, Rohit's spend yes | before 2.9 |

**Gate 2:** `pipeline_health` passes ("every Gmail message in the window has its content, or a stated reason"); the funnel's events-in rose by the resync's count; the oldest filed mail is ≥ 300 days old; Boardy intros and portal mail are kept on new arrivals (gate trace `W-07` or the new class); `evidence_needs` move off `open`.
**Expected cards (old lanes):** `f4`, `i6`, `b1`, `b3`, `l1`.

---

## Step 3 · Founder words, meetings and the founder's own claims (L1)

| # | Unit | Owner | Depends on |
|---|---|---|---|
| 3.1 | S12.U1 the words (default: introduction, meeting, investor_interest, application_status) | Rohit | — |
| 3.2 | S12.U2 the new types end to end | Claude | 3.1 |
| 3.3 | U12-06 the open lane is read | Claude | — |
| 3.4 | U12-07 a meeting is an event the chain can use | Claude | 3.2 |
| 3.5 | N1a extract the founder's self-claims from sent mail | Claude | S12.U4 metric definitions |
| 3.6 | S13.U1–U3 the bundle (entities, doubt, conversation) | Claude, Rohit's road decision S13.U2 | 3.2 |

**Gate 3:** of the founder's past external meetings in the window, ≥ 90% are events in an attendee's file; each new type fires on its synthetic case and on at least one real mail of the org (counted, not read); self-claims exist as tenant facts.
**Expected cards (old lanes + new words):** add `f1`, `f2`, `i3`, `b2`.

---

## Step 4 · File the work as one piece (L3)

| # | Unit | Owner | Depends on |
|---|---|---|---|
| 4.1 | S14.U2 deterministic situation ids; a rebuild keeps human decisions | Claude | — |
| 4.2 | U12-11 the automatic replay never rebuilds destructively | Claude | 4.1 |
| 4.3 | S14.U3, S14.U4 rebuild re-derives correlations; "filed" on the funnel | Claude | 4.1 |
| 4.4 | S15.U1 every reading names its file | Claude | — |
| 4.5 | S15.U2 one live situation per file; admission targets it | Claude | 4.4 |
| 4.6 | S15.U3 re-anchor when the company appears | Claude | 4.5 |
| 4.7 | S21.U1 (L3 half) a wave is a file | Claude | 4.4 |
| 4.8 | U12-08 an ask closed only by "replied" stays open for judgment | Claude | — |
| 4.9 | N1b conflicting own claims are one conflict | Claude | 3.5 |
| 4.10 | N4 a bounce is "never arrived" | Claude | 4.4 |
| 4.11 | S16.U1, S16.U2 promises and quotes in memory | Claude | — |
| 4.12 | U12-09 the replay harness pins knowledge time, then merge S16.U3 | Claude | — |

**Gate 4:** on Rohit's org, the multi-live HOLD count from `l2_admissions` falls to near 0; a rebuild run twice changes no situation id; the unfiled-by-reason numbers are on `daily_health`.
**Expected cards:** add `i5`, and `i4`/`s2`/`p1`/`i2` as situations (their cards need Step 5).

---

## Step 5 · Judge like the expert (L2)

| # | Unit | Owner | Depends on |
|---|---|---|---|
| 5.1 | S20.U1 STEP-13b go | Rohit | — |
| 5.2 | S20.U2 port 13b (renumber its migration) | Claude | 5.1 |
| 5.3 | S20.U3, S20.U4 held cards repaired, then in the founder's words; uncertainty to a lane | Claude | 5.2 |
| 5.4 | S07.U2 key and cap · S07.U4 R-7/R-9 live pass on Sonnet 5 | Rohit, then Claude | 5.2 |
| 5.5 | S23.U1 playbook decision ("label and use") · S23.U2 compiled lane admits labelled drafts | Rohit, then Claude | — |
| 5.6 | U12-12 the five deferred capabilities get triggers · U12-13 a customer kind | Claude | 3.2 |
| 5.7 | S21.U2 a quiet file comes back (after D57) | Rohit, then Claude | — |
| 5.8 | S18.U4 decide a file on itself · U12-14 judged files keep their slots | Claude | 1.6 |
| 5.9 | U12-15 the "what else is true today" block · U12-16 reply-vs-ask check | Claude | 4.8 |
| 5.10 | S21.U1 (L2 half) a wave judged once · S21.U3 seeds re-key | Claude | 4.7 |
| 5.11 | S22.U2 the ExpertisePackage in block D | Claude | — |
| 5.12 | S24.U1–U4 admission decides existence, first type | Claude | 4.5 |
| 5.13 | S25.U1–U2 per-type gate for `l2_cards`; board in CI | Claude | 5.4, 5.12 |
| 5.14 | S25.U3 first types on Rohit's org (investor outreach, awaiting reply); one week side by side with `l2_shadow_report` | Rohit + Harsh | 5.13 |
| 5.15 | S25.U4 retire the old lane for each switched type | Claude | 5.14 |

**Gate 5:** live pass held share ≤ 25% on Sonnet 5; no card text contains "We held the one we found"; `covered_without_situation` and `expert_shadow` (for `general`) near 0; the side-by-side week shows the L2 cards at least as good as the old lane on Rohit's own verdicts.
**Expected cards:** add `i1` (without its goal line until Step 6), `i2`, `i4`, `s1`, `s2`, `f3`, `c1`, `c2`, `h1`.

---

## Step 6 · Goals

| # | Unit | Owner | Depends on |
|---|---|---|---|
| 6.1 | S26.U1 goal decisions (default: L2 proposes, one click) | Rohit | — |
| 6.2 | S27.U3, S27.U4 the drafter's proposals visible and decided | Claude (dummy first), Rohit | — |
| 6.3 | S28.U1–U3 the goal object, read routes, F72 | Claude | 6.1 |
| 6.4 | S29.U1–U4 goals in the judgment; L2 proposes, L3 admits | Claude | 6.3, 5.2 |
| 6.5 | S30.U1–U2 links and progress | Claude | 6.4, 4.5 |
| 6.6 | S31.U1 goal on the card · N2 categories (architecture amended first, Rohit's yes) | Claude | 6.5 |

**Gate 6:** `GET /v1/goals` returns 10 goals on Rohit's org (after he approves the proposals), each with a category and a progress basis; the cards on linked work carry `goal_refs`.
**Expected:** the 10 goals, the 2 proposals, and `i1` with its goal line.

---

## Step 7 · The card and the website match `/preview`

| # | Unit | Owner | Depends on |
|---|---|---|---|
| 7.1 | S34.U3 the card writer: commit, merge, apply 0252, probe, switch on per tenant | Claude (🔨), Rohit's spend yes for the probe | 5.2 |
| 7.2 | S34.U2 result and steps reach the card · S34.U1 context from the card's own thread | Claude | — |
| 7.3 | U12-18 the lane is a chip · U12-19 the list carries what the page needs | Claude | 7.1 |
| 7.4 | N3a–N3d dashboard Cards, Goals, Home, card detail (Rohit approves a local render first) | Claude | 6.6, 7.1 |
| 7.5 | S35, S39 queue, quotes, delegate; no made-up numbers | Claude | 7.1 |
| 7.6 | N5 `preview_parity.py` | Claude | — |

**Gate 7 (the finish line):** `preview_parity.py` shows **≥ 18 of 20** `/preview` cards and **10 of 10** goals live on Rohit's org, or each missing one has a named reason Rohit accepts; `ideal_card_gap.py` shows the subject, steps, draft, goal and category fields present on every matched card.

---

## Step 8 · Ready for every customer, not only Rohit

The detail is in [12-PRODUCTION-READY](12-PRODUCTION-READY.md): onboarding that sets what was set by hand for Rohit, the release gate, per-customer parity, cost per customer, privacy. Scenario coverage is in [11-SCENARIOS](11-SCENARIOS.md).

| # | Unit | Owner | Depends on |
|---|---|---|---|
| 8.1 | U12-21 self identity at connect | Claude | S08.U2 |
| 8.2 | the setup form: the people, programmes and customers the company works with, as brief lines; the window with its cost estimate | Claude (dashboard, dummy first), Rohit approves | S09.U1 |
| 8.3 | S05.U3 `release_gate.py`, S10.U4 alert webhook, S03.U3 one push owner | Claude, Harsh | — |
| 8.4 | Gate 7 on two more design partners | Harsh | Gate 7 |
| 8.5 | U12-20 founder defaults on | Claude | 8.4 |
| 8.6 | S43.U3 the blind P1–P5 benchmark re-run on the deployed models | Claude, Rohit's spend yes | 8.4 |

**Gate 8:** the checklist of [12 §G](12-PRODUCTION-READY.md), every line measured.

---

## Which units share files (give them to one agent, in order)

| File | Units, in order |
|---|---|
| `api/routes.py` | S02.U5 → U12-01 → U12-04 → whole-message reader wiring → S10.U2 |
| `reason/domain_shadow.py`, `reason/runner.py` | U12-03 → S18.U4 → U12-14 → S24 → S25.U1 |
| `reason/expert/dossier.py`, `reason/l2/dossier.py` | U12-08 (dossier part) → U12-15 → S29.U1 |
| `reason/expert/decide.py`, `contracts/expert_review.py` | S34.U2 → U12-16 → S29.U2 |
| `context/outreach_situations.py` | S15.U1 → N4 → S21.U1 (L3 half) |
| `context/situations.py`, `context/backfill.py` | S14.U2 → U12-11 → S15.U2 |
| `context/graph_store.py`, `context/pipeline.py` | N1b (after N1a) |
| `capture/gate/*` | S08.U1 → U12-05 |
| `contracts/signal.py`, `capture/esqe/*`, `capture/structured/*` | S12.U2 → U12-07 |
| `deliver/pipeline.py`, `deliver/render.py`, `deliver/store.py` | S34.U3 → U12-18 → U12-19 → S35.U1 |
| `migrations/` | take the next free number **at merge time**; 0252 is S34.U3's; 13b and goals come after |
| dashboard `src/lib/card-read.ts`, `src/app/dashboard/cards/page.tsx` | N3a → N3d → S35.U4 |
| dashboard `src/product/internal/dashboard/goals/*`, `genios-at-work.tsx` | S27.U3 → N3b → N3c |
