# 03 · How it gets fixed: eight steps, what to do and how

**Written for:** Harsh and the coding agents. Rohit reads the opening paragraph of each step: the **Why** and the **Done when**.
**The rule for every step:**
1. Build it beside what runs today.
2. Switch it on with an activation row, never a global flag.
3. Gate it on the local copy first.
4. Only then switch it on for this org in production and measure again, read-only, the next day.

Rohit opens each step (GeniOS-008 `01-RULES`).

**How each step is built.** Follow the CLAUDE.md pipeline:
- decompose into `tree.yaml`;
- build bottom-up, one unit at a time;
- crosscheck;
- deterministic QA;
- ship.

Every unit gets its own tests and a mutation proof. The repo-wide guards run once per group of 2–3 coupled units. The full suites run in CI.

**Sizes:** S = one unit group · M = two or three groups · L = four or more.

## The map: each problem in [01](01-WHAT-IS-HAPPENING.md) and the step that fixes it

| Where it breaks today (01) | What should happen instead (02) | Fixed in |
|---|---|---|
| No single number says whether the cards got better | Every change is scored against the ideal cards | Step 0 |
| Mail is filed by sender: one piece of work is split, many pieces of work are lumped together | Mail is filed by piece of work, across senders and tools | Steps 1, 2, 5 |
| Notes contradict each other and are never closed | One current state per piece of work, updated with evidence | Steps 1, 2 |
| L2's conclusions are logged, not saved | L2's conclusions become the saved state, after code checks them | Step 2 |
| Every judgment re-reads ~70k characters; 16 of 20 re-reads had no new mail | Read the saved state plus only what is new; think only on a real change | Step 3 |
| Only new mail wakes L2, so silence is never noticed | Every piece of work has an expected-by date; the clock wakes L2 when it passes | Step 4 |
| ~$2/day goes to the newest mail first | The budget goes to overdue and goal-linked work first | Steps 3, 4 |
| No brief, no playbook, no goals, no "who we are" | Identity proposed at connect; kinds and goals usable while unconfirmed; first pass on day one | Step 5 |
| The checker throws out correct answers; "We held…" cards | Checks each change against evidence; when unsure, fetch evidence or ask one plain question | Steps 2, 6 |
| Three card makers; 71 of 103 cards from old rules; duplicates | One card per piece of work, updated in place | Step 6 |
| A third of mail archived by sender or tab; bounces don't reach the waiting work; attachments unread; 180-day window | Mail from people in active work is kept; bounces join their work; attachments retried; 365 days at onboarding | Step 7 |

---

## Step 0 · Make "good" measurable — S

**Why.** Since 23 Oct, about 28 fixes have each passed their own tests. No single number said whether the founder's cards got better, so nobody could see that the trunk was missing ([06 §11](06-MEASUREMENTS.md)).

**What.** One command, pointed at any database (the local copy, or production read-only), prints three things:
1. the **card score**: `scripts/ideal_card_gap.py`, which already exists. Today: 8/20 found, 28/220 fields;
2. the **work score**: for each in-window ideal item, is there one work holding the right mail, with the right status, whose move, loops, next step and goal?
3. the **stage of loss**: for each ideal item, the layer where it died. This uses the tracer used for 01.

**How.**

| Unit | Where | What |
|---|---|---|
| U13-01 | outside the repo, next to the private ideal file | **The expected-works sheet**, one entry for each of the 17 in-window ideal items. Each entry lists the member thread and event ids (taken from the copy), kind, status, whose move, each loop and the state it should be in, the type of next step, and the goal. Claude drafts it from the local copy; Rohit confirms it, because it is his truth. Names stay out of the repo |
| U13-02 | `scripts/ideal_work_gap.py` | Compares the sheet with `work_items` once Step 2 exists. Before that, it compares the sheet with today's files (`context/workstreams.files_for`) and situations, to set the baseline. Per item it prints: work found · members precision and recall · status · whose move · loops · next step · goal |
| U13-03 | `scripts/ideal_trace.py` | The stage-of-loss tracer: gate → signal → file → situation → L2 → check → card. It reads item definitions from the private sheet |
| U13-04 | `scripts/parity.sh` | Runs all three against one database URL, writes a dated report outside the repo, and prints the line to add to [08-LOG](08-LOG.md) |

**Done when.** One command prints the three numbers on the local copy, and the baseline is in 08-LOG.
**Cost.** No model calls.

---

## Step 1 · The piece-of-work contract and tables — M

**Why.** Today the unit is the counterparty. One intro-platform node holds 500 events and 61 people, and one application is split across two files. Nothing stores a conclusion ([06 §4–§6](06-MEASUREMENTS.md)).

**What.** The work item, exactly as [05](05-THE-WORK-OBJECT.md) specifies it. It is built beside `context_situations` and changes nothing that runs today.

**How.**

| Unit | Where | What |
|---|---|---|
| U13-05 | `contracts/work_item.py` | The dataclasses: `WorkItem`, `WorkMember`, `WorkLoop`, `IntelligenceLink`, `CompanyClaim`, `WorkVerdict`. Also the enums, the table of allowed status transitions (05 §7), and validation |
| U13-06 | `migrations/0257_work_items.sql`, `0258_loops_promises.sql` | The tables of 05 §11; the extension of `open_loops`; the 87 commitment nodes copied in as `promise` loops; everything erased with its org, as in 0256 |
| U13-07 | `context/work_store.py` | The only writer for these tables. Reads; writes a version with compare-and-set; attaches and detaches members; closes loops; writes links and claims |
| U13-08 | `platform/` | The activation row for works, per org. The existing rule applies: "activation is a table" |
| U13-09 | `tests/` CI guard | Fails the build if anything other than `context/work_store.py` writes the new tables, like the situation-writer ratchet does today |
| U13-10 | `scripts/` fixture | Loads the 17 expected works from Step 0 into a copy and validates them. This proves the contract can hold every ideal card before any model is involved |

**Done when.** The 17 expected works load and validate, and every field the ideal cards need has a home (05 §13).
**Risks.** Over-design. Keep to 03; anything new waits for a measured need.

---

## Step 2 · L2 writes the work: from shadow to applied — L

**Why.** This is the trunk. L2 already reaches the right conclusion, but admission only logs it. 0 of 16,792 facts come from L2, and merging or linking two works has no code that would apply it ([06 §7](06-MEASUREMENTS.md)).

**What.**
- L2's judgment returns a **work block**. It is part of the same single call, not an extra one.
- **Work admission** checks the block change by change and applies what passes, in one transaction.

**How.**

| Unit | Where | What |
|---|---|---|
| U13-11 | `reason/l2/prompt.py` (`l2-judgment.v8`) | The output gains `work`: title, kind, status, stage, whose move, next expected, importance, summary, members to add or remove, loops to close (loop, basis, closing event), links (relation, from, to), merge with, split into. Every item cites printed ids. The review fields stay, because they feed the card: facts, frames, next move, draft |
| U13-12 | `contracts/reasoning_result.py` | Parse, prune and validate the work block, listing problems the way it does for judgment lines today. Today's five mutation ops (`MUTATION_OPS`, line 94) map onto it |
| U13-13 | `context/work_admission.py` (new, beside `l2_admission`) | A pure `decide(before, block, catalogue, locks)` returns, for each change, ADMIT, HOLD or REJECT with a reason (05 §10). `apply(conn, …)` writes the admitted changes through `work_store` with compare-and-set. **One bad line no longer holds the whole judgment** |
| U13-14 | `reason/l2/sweep.py` (`l2_pass`) | When the org's work activation row is on, call work admission in the **same** transaction that writes `reasoning_results` (today's rule: G1, one transaction). `l2_admission` keeps logging for the old seeds until Step 6 |
| U13-15 | `reason/l2/inputs.py` (`read_subjects`) | The subject becomes the work. A new bundle's events are mapped to their works through `work_members`. Events with no work become a "which work, or a new one?" subject, carrying the candidate works that share a thread or counterparty |
| U13-16 | `context/work_store.py` | Membership by continuation, in code with 0 calls. A new event in a member thread becomes a member. A calendar event joins through its invite thread |
| U13-17 | `scripts/` offline | Replay the 86 stored L2 results through a converter and work admission, with no model calls. This shows what would have been written, and whether the checks are too strict or too loose, before any money is spent |

**Done when.** On the local copy, with production's models:
- **≥ 15 of 17 works are right** on members, status, whose move and loops, measured by Step 0's work score;
- **0 writes without printed evidence** (mutation-proven).

**Risks and rollback.**
- A wrong merge or closure: every change is a version, so undo means restoring the earlier version. Founder locks stop repeats. Code checks gate closures.
- In production, works are written before any card reads them (cards stay on today's path until Step 6), so for a week nothing changes for the founder.
- Rollback is the activation row off. No migration is destructive.

**Cost.** The same calls as today. The work block adds output, but Step 3 removes most of the input.

---

## Step 3 · Read the work first, then only what is new — M

**Why.** A judgment reads about 70,000 characters of raw evidence on average (up to 280,000). 16 of 20 re-judgments happened with no new mail, and only one line of L2's own last judgment ("valid, mode act") reaches the next one ([06 §6](06-MEASUREMENTS.md)).

**What.** A new dossier, built in this order:

| Block | Content |
|---|---|
| **W** | the work as GeniOS last understood it: verdict, status, stage, whose move, loops, claims, next expected, goals |
| **N** | what is new since the verdict: full text of the new member events |
| **P** | the playbook for this kind and stage, labelled "unconfirmed" when the kind is GeniOS's own reading |
| **G** | goals |
| **E** | tools |
| **F** | coverage |
| index | older evidence, one line per item with its id; the full text comes on request |

The work is re-judged only when something real changes.

**How.**

| Unit | Where | What |
|---|---|---|
| U13-18 | `reason/l2/dossier.py` (`l2-dossier.v7`; today's is v6, line 35) | Blocks W, N and P. From `reason/expert/dossier.py`, keep the people and the numbers; drop the telemetry sections (`derived.history.*` counters, prior-card verdicts) from the prompt |
| U13-19 | `reason/l2/sweep.py` (`fingerprint_of`) | The fingerprint is built from: the work's version, the ids of member events after the verdict, settled needs, the rung of `next_expected`, the goal-set hash, and founder corrections. It is never built from dossier text or day counters |
| U13-20 | `capture/acquire/need_fetchers.py` | A **stored-event fetcher**. It reads `prepared_content` for the event ids L2 asks for, from our own database, with no Gmail call. It is armed by default and separate from `GENIOS_NEED_FETCHERS` (D6). This is what makes "the full text on request" real |
| U13-21 | `reason/l2/dossier.py` | A hard size bound of about 16k characters. Block N is trimmed oldest-first, and what is trimmed becomes index lines. A work that grows past the bound is a sign it should split (Step 5) |

**Done when.**
- The median dossier is ≤ 12k characters, and p90 ≤ 20k.
- A three-day replay of the copy shows **0 re-judgments without new input**.
- The Step 0 card score is not below the baseline.

**Cost.** Input tokens per judgment drop from about 17k to about 3–5k, so the same $2 a day buys several times more judgments. Measure it before re-setting the budget (D2).

---

## Step 4 · The clock: silence wakes L2 — M

**Why.**
- 138 of 138 judgments were woken by new mail, while 13 of the 20 ideal cards are about something that did **not** happen.
- Situations fall asleep after a 45-day default.
- Newest-first priority lets a high-volume intro platform push important quiet work out of the daily budget ([06 §6](06-MEASUREMENTS.md)).

**What.**
- Every active work has an expected-by date (05 §8).
- A code sweep, with 0 calls, finds the ones that are overdue.
- The budget goes to important work first.

**How.**

| Unit | Where | What |
|---|---|---|
| U13-22 | `context/work_clock.py` (new) | Each sweep: find works where now is past `next_expected.by` and no member event came after `set_at`. Each becomes an L2 subject with trigger `expected_reply_absent`, or `deadline_crossed` for a stated date. Both triggers already exist in `contracts/reasoning_result.py` |
| U13-23 | `reason/l2/sweep.py` (`_priority`, line 80; `MAX_PER_PASS`, line 64) | Priority bands: (1) clock-due works; (2) works linked to a goal (live, or proposed) whose stakes are high; (3) new evidence on other works; (4) the rest. Inside a band: stakes, then urgency (L2's own words), then age. Bands 1–2 get a reserved share of the day's budget (start at 60%) |
| U13-24 | `context/work_clock.py` + `packs/` | No work goes dormant by a default window. When the playbook's stop rule for the kind and stage passes, the clock asks L2 one question: "close, or one last move?" |

**Done when.**
- **≥ 10 of the 11 in-window silence items** are raised within one clock pass on the copy (as of 28 Oct). The 11 are: `f3`, `f4`, `i1`, `i2`, `i3`, `i4`, `b2`, `b3`, `c1`, `h1`, `l1`.
- A flood test shows a sender of 60 mails a week cannot push a goal-linked, clock-due work out of the day.

**Risks.** Nagging. Each work has an `if_missed` action, the playbook's stop rules, and the founder's snooze, which is a version that locks the date.

---

## Step 5 · Cold start: who we are, kinds and goals, and the first pass — M

**Why.**
- 138 of 138 dossiers say "No company brief is accepted", and 38 of 38 current ones say "No playbook for this file".
- The table that says who "we" are is empty.
- 7 goals have been waiting, all unapproved.
- Kinds, goals and identity are conclusions too. Today nothing may use them until the founder approves dozens of lines ([06 §6, §9](06-MEASUREMENTS.md)).

**What.**
- Identity is proposed at connect.
- Kinds and goals are usable while still unconfirmed, labelled as such (D1).
- A one-time onboarding pass turns history into works (D2).

**How.**

| Unit | Where | What |
|---|---|---|
| U13-25 | `platform/self_identity.py` + `org_self_identities` | Propose identity rows from: the org's email, the connected accounts, the From addresses of sent mail, signature and legal names, and the product name. The founder confirms with one click. The claim check's list of our names reads them, which ends the 15 lines dropped for our own product name |
| U13-26 | `reason/expert/dossier.py` (playbook source, line 501) | When no accepted line names a kind, use the **work's kind** (L2's reading) for the playbook, labelled "GeniOS's reading, not confirmed". The brief's accepted line and the founder's word still win. `kind_proposal.py` keeps proposing lines for confirmation (D1) |
| U13-27 | block G in `reason/l2/dossier.py`; `context/goals.py` | Proposed goals are printed **with ids** as "proposed, not confirmed", so works can link to them with `confirmed = false`. Priority weighs live goals above proposed ones. Approving them stays the founder's, as Atlas requires. During onboarding the weekly cap is 10 (D3) |
| U13-28 | `reason/onboarding.py` (new) | **The onboarding pass, run once per tenant and on any large backfill.** Input: one line per thread (`thread.objective`, already written for 603 threads), with parties, last touch and open loops, grouped by counterparty. L2 proposes works in batches: title, kind, members, status, and a parent for introduction children. Admission creates the works. Each work then waits for its first full judgment in priority order. The intro platform becomes one channel work plus one child work per introduction |
| U13-29 | `context/work_store.py` + code | **The claims backfill.** The 80 amounts from our own outbound mail become `company_claims`. L2 sets topic and `quoted` during each first judgment. A code comparison then opens the "one number everywhere" work when the claims differ (`p1`) |

**Done when.**
- Identity rows are present and confirmed.
- **≥ 8 of 10 ideal goals** are proposed and linked to the right works.
- A playbook is present in ≥ 90% of dossiers.
- ≥ 90% of in-window ideal threads belong to the right work.

**Cost.** One-time. On 23 Oct Harsh estimated about $17 for 169 files at about $0.10 each, under today's dossier size. After Step 3 it costs less (D2).

---

## Step 6 · One card path — M

**Why.**
- 71 of the 103 live cards come from the rule lanes.
- The same subject appears up to 9 times.
- About 13 cards show the claim check's internal text.
- 0 carry a goal.
- The old flow spent 10.75M input tokens since 21 Oct, against R-9's 2.33M ([06 §8, §10](06-MEASUREMENTS.md)).

**What.**
- A card is a living view of one work, as Atlas v2 says: one card per work, with versions instead of new cards.
- The old lanes stop delivering for this org.
- A held result never becomes a card.

**How.**

| Unit | Where | What |
|---|---|---|
| U13-30 | `deliver/card_builder.py` (`card_from_work`, new) | One card per work that needs the founder, with lanes decision, conflict, question, and waiting (no notification). The card id is the work id, and a new verdict is a new version. The card's fields come from the work and the latest review: recommendation, steps, draft, quotes, goal, people |
| U13-31 | activation rows, `reason/runner.py` (`run_all`, line 1943) | For this org: the legacy-lane and compiled-lane cards stop delivering. The old LLM decision maker is switched off (remove the org from `GENIOS_L4_LLM_DECISION_MAKER_ORGS`), and so is R-1. Support readings stop while Support is not activated (`context/runner.py:882` runs them for every tenant). The old lanes may keep computing in shadow for comparison |
| U13-32 | `reason/l2/evidence.py` + the need executor | A held change raises an EvidenceNeed, tried first with the stored-event fetcher. Only something only the founder can know (e.g. `h1`) becomes one question card, written as a human question. No card ever prints the check's text |
| U13-33 | `reason/expert/verify.py` | The check is pointed at the work: it checks work changes and the card's quotes against printed evidence, normalises dates, and takes our names from identity. Check v8's rules stay |
| U13-34 | dashboard (private repo, Harsh) | The Cards page shows the work's card and its versions. The Goals page shows works by goal |

**Done when.**
- **≥ 15 of 17 in-window ideal cards** carry the right recommendation (the Step 0 score with the stricter match).
- 0 duplicate cards for one work.
- 0 cards showing check text.
- Daily model tokens are at or below today's.

**Risks.** A card the old lanes would have made could be lost. Run both paths on the copy and in production for at least three days, with the old one not delivering, and compare. Switch only on D5.

---

## Step 7 · Input fixes, in parallel with Steps 1–6 — S to M

**Why.**
- 636 of 1,829 mails were archived by sender or Gmail tab, including all 5 of an application's "still incomplete" reminders (`f2`).
- Bounces are written onto the failed address but never reach the work that was waiting.
- PDF and image attachments that failed to download were never retried.
- Mail older than 180 days is not captured (`i6`, `s1`, `s2`).

**How.**

| Unit | Where | What |
|---|---|---|
| U13-35 | `capture/gate/rules.py` (`noise_rule`) | A sender who is a party to an active work, or whose domain is, is judged by content, not archived by Gmail tab or bulk headers. This extends W-07's rescue from brief-named senders to work parties |
| U13-36 | `context/delivery.py` | Today a bounce is written on the failed address's node and on its thread. Add: the bounce becomes a member of the original mail's work, so the next judgment sees "not delivered" and can mark the loop `moot` (`i5`, `c1`) |
| U13-37 | `capture/gate/rules.py`, `capture/acquire/` | A calendar invite attachment is marked "covered by the calendar event" instead of parked. Failed PDF and image downloads go on a retry ladder, and PDFs on active works are read |
| U13-38 | `connections.capture_scope.backfill_days` + the resync runbook (GeniOS-012 `04`) | The onboarding window becomes 365 days (D4) |

**Done when.**
- `f2`'s reminders reach their work.
- `i5` and `c1` bounces show on their works.
- With D4, `i6`, `s1` and `s2` become reachable.

---

## After each step: switching it on in production for this org

1. The local-copy gate passes, and its line is in 08-LOG.
2. Harsh deploys with the step's activation row on for this org only.
3. The next day, run `scripts/parity.sh` read-only against production. Record the three numbers.
4. If a number fell, switch the row off. Nothing else needs to be undone.

## What the whole plan changes in spend

| Item | Today | After |
|---|---|---|
| One judgment's input | ~17k tokens | ~3–5k (Step 3) |
| Re-judgments with no new mail | 16 of 20 | 0 (Step 3) |
| Detecting silence | impossible | code, 0 calls (Step 4) |
| Old-flow model input since 21 Oct | 10.75M tokens | 0 for this org once Step 6 is switched |
| New storage | — | ~1 MB for 264 works, in the same database |

These are expected values, not measured savings. They are measured after Steps 3 and 6 and recorded in 08-LOG.
