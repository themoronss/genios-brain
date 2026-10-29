# P1 · Orchestrator · 02 · What's failing, and why

Each failure lists its evidence, its cause, and whose it is. "Us" means the AI sessions that built the product and the notebook under Rohit's direction. None of these comes from a misunderstanding by Rohit.

---

## F1 · Three reasoning paths run in one sweep, so there are three card makers

**Evidence:** `reason/runner.run_all` runs the expert pass, the L2 pass (shadow), the domain compiler (shadow) and the legacy pack lanes, one after the other. The live cards come from three makers: 38 from old signal rules, 33 from old situation rules, 31 from the brain. The same subject repeats up to 9 times.

**Cause:** each programme step added a new pass beside the old one and planned to retire the old one later; the old ones were never retired.
- STEP-12 added the expert pass.
- GeniOS-008 added the L2 pass, in shadow.
- The legacy lanes were never switched off for this tenant.

**Whose:** us, through architecture and process: a strangler migration that was never finished.

## F2 · GeniOS wakes up when mail arrives, not when something should have happened

**Evidence:** **138 of 138** L2 runs were started by new mail. Yet **13 of the 20** ideal cards are about something that did *not* happen: an evaluator who went quiet, a question left unanswered, a follow-up never sent, a referral that never came.

The expert pass does have date and silence triggers (`date_closing_in`, `reply_overdue`, `past_normal`). But it is bounded by its own small budget, and it judges files, not business situations.

**Cause:** the L2 pass's request step (R1) reads only "bundles stored since this pass's watermark". No stored expected-by date exists to wake it (see P2), so silence can't be noticed.

**Whose:** us, through design. The L2 pass was built new-evidence-first, and the clock was left for later.

## F3 · Re-reading everything makes it expensive, so it is capped and most work is never judged

**Evidence:**
- every judgment re-reads about 70,000 characters (up to 280,000);
- the budget of about $2 a day allows about 12 files a day;
- only 80 of 264 files have ever been judged;
- 16 of 20 re-judgments had no new mail.

**Cause:** nothing the brain concludes is saved (P2 F1), so the Orchestrator has no small "page plus what changed" to send. It can only send the whole file again.

**Whose:** us, through architecture: the Intelligence Graph was never built. The Orchestrator inherits this problem.

## F4 · Switches that report success while nothing happens

**Evidence:**
- `reason/cutover.py` lists seven switches.
- `runner.py` records that `l3_activation` once had **no reader**: "`POST /v1/admin/l3/activate` wrote a row, the console showed the tenant as on … and the sweep ran a SHADOW pass that published nothing."
- The activation of the L1 to L3 seam was a global boolean "set in no environment".

**Cause:** every step added its own switch, and nothing lists the switches together or checks them against what actually ran.

**Whose:** us, through process.

## F5 · The four loops don't exist as loops

**Evidence:**
- **Onboard:** there is no first-day pass. Goals come only from accepted brief lines (`sync_from_brief`), and none are accepted (7 proposed, 0 approved).
- **Evolve:** only the L2 R1 step (new bundles) and the expert pass's triggers. No step places new evidence into a business situation.
- **Act:** card actions (211 `card_events`), executions (105, with 55 outcomes) and decisions (0 rows in `decisions`) are stored. No pass reads them back into the situations or the goals.
- **Maintain:** only card expiry (`card_lifecycle.expire_lapsed`) and the maintenance sweep. There is no correlate, analyse or decay pass over the conclusions.

**Cause:** the sweep was designed around signals → situations → cards. The loops are newer requirements (GeniOS-009, 013 and Rohit's 29 Oct message) with no runner yet.

**Whose:** unfinished work.

## F6 · The clock is UTC-only in the notebook, and no clock-driven work exists in L2

**Evidence:** in the notebook build `b2`, the model was told "the mailbox was read through 2026-10-23 01:40 UTC". It read a panel slot of "11:30–12:00" as happening now. In fact 01:40 UTC is 07:10 in India, so the panel was four hours away. The resulting card said "Confirm whether you attended the panel today" (`f1`).

**Cause:** the notebook's judge prints UTC only. It never states the company's time zone, although the company page holds it.

**Whose:** **mine** (the notebook's judge, 29 Oct).

## F7 · The notebook has no runner, only commands

**Evidence:**
- Every phase is run by hand (`nb.cli all`, then single phases).
- `update.py` keeps its own older copy of the grouping rules: `org_key` clustering, the old archived-noise rule, the channel rule weighted by count only, and `thread:<id>` singletons. The works agent listed these on 29 Oct.
- Each process seeds its own budget, so two runs at once don't see each other's reservations.

**Cause:** the notebook was built phase by phase to prove the page-per-situation idea, not yet to run as a loop.

**Whose:** **mine**, and known: it is the next step by design.

## F8 · The notebook's order makes cards before goals

**Evidence:** `all` runs judge (each page decides on its own card) → relate (goals formed, links made) → judge again (only the merged and linked situations) → cards. So:
- a card is decided before its goal exists;
- no card comes from a goal's missing step. Two ideal cards were missed this way: `f3` (a referral silent for 24 days) and `i1` (one update carrying the new milestone).

**Cause:** the page-first order of GeniOS-013 Step 2, with goals added as a later phase.

**Whose:** **mine**, from design. It is fixed by the loop order in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).

---

## Summary: whose fault

| Failure | Whose | Kind |
|---|---|---|
| F1 three paths | us | architecture: an unfinished migration |
| F2 new mail only | us | design |
| F3 re-read and cap | us | architecture (P2's missing notebook) |
| F4 switches | us | process |
| F5 no loops | unfinished | planned, not built |
| F6 UTC only | me (notebook) | code |
| F7 no runner | me (notebook) | not built yet |
| F8 cards before goals | me (notebook) | design order |
