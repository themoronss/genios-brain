# P5 · Cards (the intelligence) · 01 · What's exactly there

**What this file answers:** what exists today for what reaches a person, in the product, on the screens and in the notebook, measured, with file paths. [02](02-WHATS-FAILING-AND-WHY.md) says what fails and why; [07](07-THE-CARDS-SPEC.md) is the target.

**The part:** what reaches a person:
- **when** intelligence is raised, and when it is held back and why;
- **what** it says: what to do and why, for which goal, by when, how we'll know it's done, the evidence;
- **which** of the four kinds it is: reactive, proactive, predictive, prescriptive;
- how it is ranked, limited, versioned and closed, and when it interrupts;
- what a person can do with it: Done, Delegate (to a person or an agent), Later, Feedback, Answer;
- the same card on the web, the Mac app and the phone.

Cards never judge the situation behind them: P4 judges, P2 keeps, P5 shows.

**Read at:** product code `a729b968` (29 Oct); the dashboard's `origin/main` `ff13896b` (23 Oct); the desktop dummy and its build `0.3.0` on `rohit/desktop-ux`. **Measured on:** the local copy of the design partner's org, cut from production on 28 Oct at 12:45 UTC (production restarted this org on 21 Oct, so 22–28 Oct is a real first week), and the notebook build `b2`, as of 23 Oct 07:10 IST. Every number has its query in the measurement notes (private; no names).

---

## 1 · P5's functions, one by one

**Key:** ✅ built and on the card path · 🟡 partly, or built and not yet reached · ⬜ built, no caller · ❌ missing.

| Function (Atlas, Rohit's card work) | In the product | State | Measured in the first week |
|---|---|---|---|
| **Raise only when a person is needed** | None. L5 builds one card for every open signal that passes L4's authority predicate (`deliver/pipeline.py:52-135, 911-1183`) | ❌ | 111 cards, 103 open |
| **One source of cards** | Six writers (§2) | ❌ | 33 / 36 / 41 / 1 by writer |
| **One card per situation** | One card per signal (`cards_one_per_signal`), and one open card per file for expert and question cards (`cards_one_open_card_per_file`) | 🟡 | Per subject node at most 2; one counterparty owns 25–31 of 111 |
| **The living card (versions)** | `contracts/card_version.py`, `platform/card_lifecycle.py`: words before and after, material changes, quiet versions never pushed | ✅ for file cards | 16 versioned, all from the L2 path; 95 at v1 |
| **The card record** | The `cards` table, 47 columns; `contracts/card_contract.py` is a refusal contract, not a field schema | 🟡 | §3 |
| **Words written for the card** | R-10, the card writer (`deliver/card_copy.py`): built, fact-checked, switched off | ⬜ | `copy` on 0 of 111 |
| **The lane from the reasoning** | `output_lane.route` at three deciders; L2's `lane_for` reaches the card only as a hold | 🟡 | The two agree on 16 of 33 judged cards |
| **The four kinds** | None on cards; `executive/modes.py` has reactive, proactive, predictive and *preventive*, used only by the executive brief | ❌ | — |
| **Severity and rank** | An urgency band cut from a utility score (`deliver/bands.py`: high 70, critical 85); the queue ordered by utility | 🟡 | 22 of 103 open are critical; all 24 question cards at score 0 |
| **A goal on every card** | `goal_refs` refreshed every pass (`deliver/goal_line.py`, migration `0255`), from approved or active goals only | ⬜ | 0 of 111; 11 goals, all proposed; 0 links |
| **Done when, closing on proof** | `success_signal` text; one verified-close path (`resolve_cards`, `verified`) | 🟡 | 0 resolved; every open card expires within a week |
| **Actions** | `POST /cards/{id}/action`: `run_play`, `do_it_myself`, `snooze`, `wrong`, `requeue`, `answer` (`deliver/actions.py:36`) | ✅ | 3 presses, all Done |
| **Delegate to a person** | No route | ❌ | — |
| **Delegate to an agent, approve before sending** | `/v1/delegations`: propose, approve with frozen bytes, reject, record the result (`executive/delegation.py`) | ⬜ | 0 agents, 0 delegations |
| **Interruption budgets, quiet hours, timing** | `deliver/timing.py`, `gate.py`, `policy.py`, `rate_limiter.py`: built and tested | ⬜ | Never used on a delivery |
| **Delivery beyond the app** | The outbox and adapters (Slack, agent push; email with no transport) | ⬜ | 0 outbox rows; `in_app` only; 526 moments, all shadow |
| **The morning brief** | A separate brief (6 rows) and an on-demand digest | 🟡 | — |
| **Why-not receipts** | `signal_suppression_log` for legacy rules; card refusals; a "why no card" line derived at read | 🟡 | 5,837 suppression rows, all legacy |
| **The trace on the card** | A `why` list of field names and values; card events | 🟡 | Quotes on 8 of 111 |
| **Feedback that teaches** | Verdicts, answers and corrections enter the file's fingerprint (`reason/expert/fingerprint.py:91-104`); calibration in shadow | 🟡 | 3 verdicts (Done), 0 "wrong", 0 answers |
| **Teams and visibility** | Assignment, seat reach, evidence filtered per recipient (`deliver/router.py`, `seat_access.py`) | ✅ built, 🟡 used | All 111 to the owner's seat; 0 recipients |
| **One reader on every surface** | The web's `card-read.ts`; the Goals page and the Mac app have their own | 🟡 | About ten button sets |
| **Measurement** | Per-pass counters; no outcome measure; AER hard-coded 0 | 🟡 | — |

## 2 · Who made the 111 cards of the first week

| Writer | What it does | Cards (all / open) |
|---|---|---|
| **Legacy pack rules** (`reason/runner.py:828-880`, `composer.py`, `publication.py`) | One signal per (pack, rule, node), e.g. `commitment_overdue`, `unanswered_email`; a narrator call or a raw-slot fallback | 41 / 38 |
| **The compiled lane** (`reason/domain_shadow.py:221-433`) | The compiled brain's decision as a signal; level prescriptive only if its package is accepted | 36 / 33 |
| **The expert file decisions** (`reason/expert/decide.py:522-575`) | A covered file's stored review, decided with no model; one decision per file | 9 open |
| **Question signals** (`reason/expert/asks.py:252`) | A held or find-out file asks one question, at score 0 | 24 / 22 |
| **The team emitter** (`reason/team/emit.py:138-312`) | Writes a signal and a card directly, with a fixed score | 1 / 1 |
| **The L2 judge** (`reason/l2/sweep.py`) | Writes the file's review; the expert path then decides it. It makes no card itself | (the 33 file cards above) |

- **77 of the 111 came from the unit lanes,** and 73 of those trace to the test-mode decider (`score_components.llm_utility`), which runs outside the model register: 3,695 calls over 21–28 Oct (about $12 at list price, an estimate).
- **Live, not acted or expired,** the split is 31 / 33 / 38 / 1 (the L2 path, the compiled lane, the legacy lane, the team card); the 29 Oct tables used both bases without saying so.

## 3 · What a card holds today

- **The record:** the `cards` table, 47 columns: headline, situation, why-now, unresolved item, `recommended` (who, what, for whom, to, by when), alternative, wait-or-stop, `success_signal`, `do_nothing_consequence`, outcome window, confidence vector, `why` (evidence), `artifact` (a draft), actions, `goal_refs`, `copy`, `file_id`, version, lane and its reason, urgency band, score, level, surfaces, builder version, capability fields.
- **Refused by code:** a blank headline or situation; a decision card without its authority proof; and, by `card_contract.py`, a card that names us as subject or recipient, shows an internal field or slot, claims money without money evidence, quotes words not in its quotes, or states a number or date its corpus lacks. 9 refusals in the week (quote 6, number 2, money 1).
- **Fill on the 103 open cards:** why-now 74; `success_signal` 63; `do_nothing_consequence` 102; `recommended` 9; alternative 9; wait-or-stop 8; a draft body 59; copy 0. The "gold" lines exist only on the 9 expert decisions.
- **Template text:** `do_nothing_consequence` is a template on 77 cards ("The commitment overdue condition may remain unresolved." 25; "The unanswered email condition may remain unresolved." 16; "The <unit key> situation is left unaddressed while its evidence compounds." 36, of which 33 print an internal key such as `dependency_stated`). `success_signal` holds codes (`commitment_met` 23, `outbound_sent` 12).
- **Headlines:** median 55 characters, 90th percentile 129, the longest 216; 20 over 90 characters, all on the L2 path, cut mid-sentence ("… Send a short message"); 40 start "Needs a decision —".
- **Held text:** "What is the next step with <them>? We held the one we found: <why>." (`reason/expert/verify.py:812`) on 13 open question cards (15 in all); 5 more cards say "we could not confirm what it rests on".
- **The founder in the third person:** 23 cards name the founder by first name in the headline, situation or why-now, 9 in the headline; a stricter pattern ("waiting on", "'s decision") finds 5. The 29 Oct count of 6 depends on its definition.
- **Evidence:** only 8 of 111 cards carry a verbatim quote (8 of the 9 L2 decision cards); 73 carry a Gmail field (a date) but no quote.
- **Staleness:** of 36 cards resting on a commitment's due date, 30 were raised more than 30 days after it (median 114 days); legacy cards with a last-inbound date, 13 of 16 (median 77 days).

## 4 · Lane, kind, severity and rank today

- **The lane** comes from `output_lane.route` (`reason/output_lane.py:71-120`), called by the formula decider, the test-mode decider and the expert decider: conflict first, then failed or blocked, insufficient context, defer (monitor), no action (suppress), a decision under 6,000 basis points (monitor), else decision. Open cards: decision 64, investigation (questions) 22, monitor 16, conflict 1.
- **L2's lane** (`lane_for`, in `contracts/reasoning_result.py:497-539`) is stored with the result and never read by `deliver/`: L2 said conflict on 23 results and investigation on 45, while one card is a conflict.
- **After the lane,** `card_builder` applies its own judgments that downgrade a card (the clarity, absence and no-quote gates, `1200-1302`), setting it to observation or review and stripping its actions.
- **No kind** is stored; `level` holds review 64, prescriptive 38, observation 9.
- **Severity** is the urgency band of a score: a decision's utility, a fixed number for team cards (40, 55, 75, 90), 0 for questions. Stored bands overlap on score (standard 0–51, high 52–75, critical 62–72).
- **The order** is utility then age, the other doors merged and re-sorted by score; question cards sort last; the one team card (score 75) tops the list. The dashboard groups by lane and keeps the brain's order inside a group.

## 5 · Attention today

- **The budget** is per person per day (`scoring.budget_per_user_day`, default 7), checked in the card pass; it only blocks the move to "surfaced". A second, upstream cap limits signals per day.
- **"Surfaced"** is a state flip (`pipeline.py:1172`), not a delivery: 36 "push" events in 7 days (8, 5, 4, 1, 5, 3, 10 a day), 20 of them critical (the Atlas starts at about 1 critical a week).
- **Nothing was delivered:** `delivery_outbox`, `delivery_events` and `delivery_attempts` have 0 rows; the org has only an `in_app` channel; email is registered with no transport; there is no APNs, FCM or web-push code (`deliver/units.py:39-48` lists the phone as "integration required").
- **Moments** (the Mac's popups) are separate from cards: 526 in the week, every one stored with `suppressed_reason = shadow`; only 1 links a card.
- **Timing** is built and never used: quiet hours 21:00–08:00 local, 3 interruptions per rolling hour, critical breaking quiet hours, kill switches and floors.
- **Dedupe and flood limits:** one card per signal; one open card per file; at most 3 cards of one reason code surfaced per pass; a cohort card absorbs its per-person cards.
- **Suppression:** 5,837 rows in `signal_suppression_log` (covered by a review 4,188, deferred 1,207, budget 373, no new evidence 60, cooldown 9), all from legacy rules; `rule_mutes` 0 rows.

## 6 · Identity, versions and closing today

- **Identity** is the signal; a file's cards are one card across signals, re-pointed by `version_card`. A legacy or compiled card has no file: a new signal for the same subject replaces the old card.
- **Versions** exist only on the L2 path: 16 cards at v2 (9 questions reworded, 7 questions that became decisions), each event holding the words before and after and `material = true`. Non-file cards are rebuilt in place when the builder changes (`card.rebuilt`).
- **States:** built, queued, surfaced, snoozed, claimed, delivered (open); acted, resolved, expired. Open 103 (queued 72, surfaced 31), acted 3, expired 5, resolved 0.
- **Every open card expires within a week:** the card window is cut to the decision's authority window (`EXPIRY_HOURS = 168`, `reason/expert/decide.py:154`; 7 days for team cards), while `card_builder.py:57` sets `EXPIRY_DAYS = 3650  # effectively "never"`. All 103 expire between 29 Oct and 4 Nov.
- **Closing on proof** exists for one path: a cleared file decision whose ask closed answered is resolved `verified`. `success.detected` has no writer. 0 cards resolved.
- **No code closes cards when a situation ends;** a card closes when its signal is retired or its window lapses.

## 7 · Actions, feedback and delegation today

- **What each press writes:** the card's state, the signal's status, a human event, a card event, a verdict row for `run_play`, `do_it_myself` and `wrong`, a correction for `wrong` with words, the answer for `answer`, and an execution moved to running for `run_play` and `do_it_myself`.
- **Offered on open cards:** Later (`snooze`) and Feedback (`wrong`) 102; Done (`do_it_myself`) and "Draft reply" (`run_play`) 34; Answer 22. 33 of 64 decision cards offer no Done. "Draft reply" only marks the card acted; GeniOS sends nothing.
- **Pressed in the week:** 3, all Done, in the desktop app on 22 Oct between 17:28 and 17:30, 11 to 13 minutes after the first cards. 0 Later, 0 Feedback, 0 answers (40 founder questions: 22 open, 18 retired, 0 answered).
- **Later** offers 4 hours, tomorrow 09:00, 3 days and a picked day, capped at the card's window; it is never a verdict.
- **Feedback** is `wrong` with one of 11 reasons in 4 groups ("the facts are wrong", "the conclusion is wrong", "this is not how we work", "right card, wrong delivery"), optional words that become a correction, and a scope (file, kind of work, company; the last two owner only). There is no "this is right" on a card.
- **Read back:** verdicts, answers and corrections are inputs to the file's fingerprint and the compiled lane's change gate, so a new one makes the next sweep re-review the file. With 3 verdicts, it has barely happened.
- **Delegate to a person** has no route; the only person-side pieces are `card_recipients` (0 rows) and the play `task.reassign`.
- **Delegate to an agent** is a sound four-verb ledger: propose (a typed play, strict parameters, idempotent), approve and enqueue (a named person; the request bytes frozen with sha256; one outbox row; 24-hour expiry), reject, record the agent's result once. Three plays (`email.reschedule`, `task.reassign`, `email.follow_up_draft` with send fixed false). What the agent receives is not the Atlas's task contract: no intent, goal, `may` or `may_not`, done-when, deadline or `verified_by`. An agent's "succeeded" is its own report.
- **Drafts:** 86 cards carry an artifact, 64 with a body; 3 bodies hold placeholder text; 19 name the founder in the third person; 0 approved. The dashboard never renders a card's draft.
- **Executions:** 105 (pending 50, expired 35, cancelled 20); 308 execution actions, 0 completed.

## 8 · The screens today

**The web Cards page** (`src/app/dashboard/cards/page.tsx`, 1,329 lines). The GeniOS-010 06-CARDS rebuild **is merged** on `origin/main` (its commits `b5527dc`, `9d565e6` and `25553ab` are ancestors of `ff13896b`; whether production serves it was not checked):
- four groups in a fixed order (Decide, Two sources disagree, Answer, Waiting), three tabs (Open, Put off, History), the brain's order inside a group;
- a list row with tool tags, a domain tag, the age, the headline (tidied by regular expressions), up to two lines, who, the due date, the urgency dot and one button (Done, Answer, Bring back, or none);
- a 600-pixel side panel in Rohit's order, with the buttons in a fixed footer and a folded event list;
- Done (`do_it_myself`), Later (snooze, with a picked day at 09:00), Feedback (11 reasons, two blanks, scope), Answer, Bring back; refusals mapped to sentences for 10 codes and kept on screen;
- **Delegate is drawn on every card and locked** (`DELEGATE_LIVE = false`, `page.tsx:81-85`): its comment waits for `POST /cards/{id}/delegate`, which the brain does not have, while the brain's `POST /v1/delegations` already takes a `card_id`;
- "Goal it moves" is a fixed "Not linked to a goal yet" on every card; `goal_refs` and `copy` are never read;
- the version tag counts `card.rebuilt` events while the brain writes `card.versioned`, so it never shows;
- the lane comes from the card's body, fetched for the first 40 cards only.

**What a person can see:** of 103 open cards, 38 carry no `app` surface and are withheld from the queue (25 legacy and 13 compiled, all at level review), so at most 65 are listed. The `agent` surface is never set, because `card_builder.py:779` reads the key `action` while actions carry `type`.

**The Goals page** reads the company brief, the cards and each card's body, with its own mapper: `goal.cards` is always empty; every card sits under "Cards not linked to a goal yet", numbered by position; "What to do" shows a verdict code (`reply`, `review_source`); cards of domain `general` and `verify` (14 of the 65) are hidden as "locked"; an opened card has no buttons; it waits for `GET /v1/goals`, which the brain does not serve.

**Home** shows one real card fact ("Cards raised this week" by band, from `home-summary.cards_7d`); goals, AER and HIR are fixed strings or sample values; the bell is a fixed list of sample notices.

**The shipped Mac app** (`origin/main`) lists cards with its own reader, in one scroll list; its "Not useful" sends `wrong` with no reason, the brain refuses it (`invalid_wrong_reason`, 422), and the app swallows the refusal (`api.ts:371-381`) while removing the row, which returns on the next poll; Done on a question card fails the same way; no surface is sent; expert why rows draw ": undefined"; only the first 12 bodies are fetched. Its popups are moments, not cards.

**The approved desktop dummy** (GeniOS-010 07): one black card drops from the menu bar with Done or Answer, Delegate, Later, Feedback and Show more; a menu with Card, Goals, Pending and Account; a 5-second Undo; a refusal sentence; `surface = desktop`; it reads cards through a byte-identical copy of the web's `card-read.ts`. Its build (`0.3.0`, `e04b1ae`) is on `rohit/desktop-ux`, not merged.

## 9 · In the notebook (`b2`, as of 23 Oct 07:10 IST)

- **When a card is raised** (`nb/cards.py:21-49`, `card_for`): the page says the founder is needed (40 of 63), the page's expected-by date has passed (19), or that date is within 7 days (4). Nothing else is read: not whose move it is, not the date's age, not goals.
- **Dates alone:** the 23 date-only cards carry code-template headlines ("Overdue: …" 19, "Due 28 Oct: …" 4) with no why-now, recommendation or steps; 17 of them are on our move and 6 on theirs; the 19 "date passed" cards are 59 to 168 days past their date. 11 were raised for a date the page itself says needs no action if missed.
- **Old dates:** 52 of 63 open cards rest on a move-since date more than 30 days before the instant (median 87 days); only 7 are within a week.
- **Lanes:** decision 12, question 24, deadline 8, waiting 17, conflict 2. The notebook's "waiting" means "a reply we owe is due" (15 of 17 on our move, 15 with a draft); the ideal's means "GeniOS waits, nothing to do". "deadline" is a notebook-only lane.
- **Duplicates across works,** though each work has at most one card: the traction conflict on two works; the registration complaint on three works with two cards; the 11 Aug broadcast as three cards on works that share its mails.
- **The body:** title, kind (of work), status, stage, whose move and since, summary, why now, recommendation, steps, draft, quotes, question and options, next expected, importance, goal links, why it was raised. Fill: why-now 40, recommendation 40, steps 40, draft 19, quotes 29, question and options 26, goal links 55; `confidence` is copied from a field the judge no longer writes, so it is empty on all 63.
- **Words:** the 40 page-written headlines are verb-first and checked only for their quotes; 12 start "Confirm whether …"; 17 of 63 cards say "the founder"; no engine words were found.
- **Not in the notebook:** a kind, severity, a budget, a cooldown, a mute, a done-when, a "through" phrase, a primary goal, delegation, any action, any record of why a work got no card (except a list of works that only wait).
- **Against the ideal:** 17 of 20 ideal cards match a work (the other 3 are older than the copy); 8 of them have an open card on that work (7 cards, as `p1` and `i4` share one); by the hand reads 10 of 63 open cards answer an ideal card and 53 answer none. Of the 8 matched pairs, 2 share a lane.

## 10 · The ideal's cards against today, card by card (the ones P5 owns)

| Card | The call | Live product | Notebook `b2` | What P5 must do |
|---|---|---|---|---|
| `p1` | Four traction numbers went out: pick one before today's review (conflict, critical, the banner) | Lost | The same call, raised twice on two works | One card per conflict; every side pressable; never pick; the banner by rule |
| `f3` | Ask the intro platform about the scout's promised referral, silent 24 days (a gap card, high) | The platform's file is too big to judge | No card: a pile of 30 threads whose page said "not needed" | A gap card from the goal, with its anchor |
| `f4` | Waiting on the reviewer's comments: nothing to do until Monday (waiting) | Held by the checker | A "Due 28 Oct" deadline card raised by the date rule | A waiting card with its next check, asking nothing |
| `i1` | One update with a new, checkable fact, then stop (decision, high; the film's example) | The right reading held; an old rule's card says "71 days late" | No card (the page concluded "wait"); the opposite call is on the page | Version 4 of the same card, from the page or the goal's gap |
| `i4` | One update to 12 investors, 0 replies in 10 weeks: which still matter? (question) | Partly, late | Became the numbers-conflict card; two more cards on works sharing its mails | One question over the wave, every member listed |
| `i5` | Six mails never arrived: resend to working addresses (decision) | The bounce stays on the address | The card covers only the registration complaint | One card, a row per bounce, `c1`'s bounce as "see `c1`" |
| `b1` | Two new introductions waiting for a yes or no (decision) | One held, one never judged | One offer has a scheduling card; four stale offers have yes-or-no cards | One card, a row per offer, each with its recommended answer |
| `c1` | The registration complaint reached one inbox: call the helpline (decision, high) | Filed as an investor, held | Two cards on two works, a later date | One card; the portal "not verifiable" |
| `c2` | A tool renews within the week: keep or downgrade (decision, standard, no goal) | Nothing recognised | Filed as noise | A card with no goal, counted, with its own number |

## 11 · Corrections to the 29 Oct P5 documents

- **The dashboard rebuild is merged:** the 29 Oct files said `rohit/cards-ux` was not merged as of 22 Oct. It is on `origin/main` (§8), and Delegate is there, locked. It is the Mac app's approved design that is not merged.
- **`goal_refs` is migration `0255`,** not `0256` (which ties the goal tables to their org's erasure), and it is not absent: it is refreshed every pass and empty because every goal is proposed and no screen reads it.
- **"103 live cards"** is the open count; at most 65 reach the app queue (§8).
- **"Held results were turned into cards"** is too broad: a held file asking one question is a designed lane (STEP-13 D60) that the Answer button depends on. The leak is one sentence template on 13 open cards, plus headlines over the cap.
- **"Nothing reads the founder's actions back"** is wrong in code (they enter the file's fingerprint, §7) and true in practice (3 verdicts). The 133 `moment_feedback` rows describe moments, not cards.
- **The Mac's "Not useful" does reach the brain,** with no reason, and is refused and hidden (§8).
- **"The same subject repeats up to 9 times"** holds for the displayed subject only: the 9 cards sit on 9 condition nodes of one company; by subject node the maximum is 2.
- **"6 cards name the founder in the third person"** depends on the definition: 23 by first name, 9 in the headline, 5 by a strict pattern (§3); in `b2`, 17 of 63.
- **"22 of the expert pass's 31 live cards are held"** was not reproduced: 19 cards had a held review at some time, 15 have their latest review held.
- **The phone** is not a surface today: no mobile or push client exists.
- **"56 open cards answer none of the ideal's cards"** counts cards on works the scorecard did not match; by the hand reads it is 53, and 7 open cards already answer 8 ideal cards.
- **`f1`'s wrong tense** was written by the judge, which saw the instant in UTC only (`nb/judge.py:357, 458`); the date rule did not make that card. The date rule is the cause for `f4` only.
- **"One reading per situation, one card at most" in the notebook** holds per work, not per matter (§9).
- **The 29 Oct P5-1 done-when** ("every raised ideal card still raised") conflicts with its own decision ("a date on something they owe makes no card"): `f4` was raised only by the date rule on a work whose move is theirs. Under the new D-P5-1, `f4` is a waiting card from its page's lane.
- **`i1` has no notebook card at all;** the opposite call is on its page.
- **A new module `deliver/cards_from_pages.py`** was proposed as the one maker; the existing single door is `deliver/pipeline.build_cards_for_org`, which P5-1 adapts.
