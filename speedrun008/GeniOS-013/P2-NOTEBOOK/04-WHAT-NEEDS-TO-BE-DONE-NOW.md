# P2 · Notebook · 04 · What needs to be done now

**The full specification is [07](07-THE-NOTEBOOK-SPEC.md).** This file holds the decisions and the step-by-step build. Every step cites the section of 07 it builds. [08](08-REQUIREMENTS-TRACE.md) shows that the 309 requirements from the ideal dashboard, the expected outcomes, Atlas v2 and the film each land in a step. Work another part owes is listed at the end, under **Owed by other parts**.

There are two tracks, as in P1:
- **The notebook track (P2-0 to P2-26).** It builds the Notebook locally and proves it on the copy.
- **The relief track (Q1 to Q3).** These are small changes to today's product that stop it filling its database with a department the company doesn't have. They need Rohit's approval and Harsh's hands.

A step is done only when:
- its tests pass;
- its done-when holds;
- the invariants of 07 §15 pass;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing worse.

---

## Decisions for Rohit

Each has a recommendation. Saying "go" accepts all of them.

| # | Question | Recommendation |
|---|---|---|
| D-P2-1 | **Is the business situation the unit of work?** | Yes: one application, one conversation, one introduction, one renewal, one hire. Not a sender, not a thread |
| D-P2-2 | **What does a goal hold?** | The object in 07 §6.1, starting from migration 0254's fields. One optional parent level (an umbrella goal with sub-goals), then plan steps, then situations. No OKR or key-result objects for now |
| D-P2-3 | **May archived mail be read?** | In the notebook, yes (it is, now). In the product, read an archived mail in two cases. **(a)** Code classes it as obligation-bearing from its headers and a code-only scan of its text: deadline, reminder, incomplete, renewal, charge, invoice, decision or rejection, application received, portal status. **(b)** It belongs to a live situation, or L2 raises an EvidenceNeed for it. No model sees it before that. Bulk mail stays unread (07 §2.3) |
| D-P2-4 | **How far back at onboarding?** | 365 days, so the March–April ideal items are reachable (GeniOS-013 Step 7) |
| D-P2-5 | **May proposed goals be used before you confirm them?** | Yes, labelled "proposed". They never appear on a card as confirmed. See D-P2-13 for how they are printed |
| D-P2-6 | **Which inputs come next?** | Screen first (already captured), then the founder's actions, answers and executions, then documents (Drive), then other tools as they connect |
| D-P2-7 | **How long is the text of evidence kept?** | **While any situation that is not closed cites it**, including quiet ones. At least 365 days after the last message of any thread we wrote in. 180 days after capture only for mail no situation holds. A page keeps its admitted quotes until the tenant is erased. Evidence cited only by closed work is kept `after_close_days` after the close (180 by default, per tenant). Raw copies are kept only until clean text exists and promotion is decided, and while a fact or provenance row points at them. Today every text is deleted 180 days after capture, whatever cites it (F11; 07 §14) |
| D-P2-8 | **Readings for a department the company hasn't switched on?** | **Stop them now** (Q1). The support desk alone is 63% of the active situations and 21% of the facts (F9) |
| D-P2-9 | **The database plan** | Move production to a **larger database plan before the second customer**, and cut the churn first (Q1, P1 R2), then move Screen captures and raw bodies to object storage (07 §14). One tenant is already over the ceiling (F12) |
| D-P2-10 | **Teams** | Single founders first. A team is onboarded only after visibility on pages is built and tested (P2-10) |
| D-P2-11 | **Money for P2's notebook steps** | About **$5 more** for the notebook, on top of P1's $15, so its cap goes from $35 to $40. Most steps are code; the model cost is re-judging what they touch, and the placement drill |
| D-P2-12 | **Where does the business situation live in production?** | **One chain, headed by a new `work_items` table**, with `work_item_versions` as its append-only interpretations. Decisions, executions and outcomes hang off it. It runs beside today's `context_situations`, so the nine old situation writers can never touch a situation L2 formed. At each tenant's cutover, `context_situations` stops being written for that tenant, and its rule-born rows retire one type at a time. This amends Atlas III.4 ("the Intelligence Graph has no tables of its own") and needs your yes. The alternative, extending `context_situations` in place, is rejected: every old writer would need a guard, and one missed guard would let the old pipeline rewrite L2's situations |
| D-P2-13 | **How are proposed goals printed to the model?** | In **two separate blocks**: "the company's goals" (live only) and "goals GeniOS thinks you are pursuing; not confirmed". Links to a proposed goal carry `confirmed = false`. This amends 00-ARCHITECTURE §Goals, which today prints only live goals, so it needs your yes. If you decline it, proposed goals are not printed, and a link to one is refused (A-10) |
| D-P2-14 | **Does the Notebook keep L1's qualified signals?** | **Yes.** They are L1's output. The evidence side keeps them append-only, and each member carries its signal type and signal ids. The Notebook also reads clean text, as the notebook does. Whether L1's per-mail extraction is still worth its cost is measured in P2-22 (P1 06 §4) |
| D-P2-15 | **"Your data stays with you": what does it bind today?** | **A portability rule now.** No Notebook table, check or invariant depends on a cross-tenant join or a hosted-only feature, and a tenant's Notebook exports whole. Running it on the customer's own device stays a later product decision (07 §14) |
| D-P2-16 | **May the local copy reach 365 days?** | Yes. A read-only re-cut of this org's Gmail for the 365 days before the cut, kept in the private local folder only. It makes `i6`, `s1`, `s2` and "win paying design partners" provable (P2-22) |
| D-P2-17 | **How big is a goal?** | Follow the ideal: an umbrella goal when any of several counterparties can satisfy the end, and a separate goal only for one counterparty's own decision door (07 §6.2). This amends the architecture's D10 ("one goal per piece of work") and needs your yes. If yes, that requirement is superseded by this decision; if no, the fallback of 07 §6.2 applies |
| D-P2-18 | **Does your "Done" close a situation without evidence?** | No. It is stored as *reported*, and the situation stays open until a source shows the outcome. When no connected source can show it, your word closes it, marked `founder_word` (07 §5.1) |
| D-P2-19 | **"Blocks" or "depends on"?** | Store only `depends_on`. "X blocks Y" is accepted and stored as Y depends on X. `causes` and `related_to` are refused; a causal claim belongs in the page, as a hypothesis (07 §4.6) |
| D-P2-20 | **May activity show a percentage?** | Yes, always with the count beside it ("1 of 28 · 4%"), and never as a goal's progress (07 §6.1) |
| D-P2-21 | **What is one wave?** | The same text to 3 or more recipients within one local day. Later sends of the same template to an overlapping audience join as new rounds (07 §4.8) |

---

## The plan at a glance

| Step | What | Builds 07 | Needs | Model cost |
|---|---|---|---|---|
| P2-0 | The company page and its milestones; stable situation ids | §3.4, §4.1 | — | ≈$0.10 |
| P2-1 | The goal object, grain and proposal admission | §6 | P2-0 | $0 |
| P2-2 | One link set, goal ↔ goal links, meaning links | §4.6, §6.3 | P2-1 | $0 |
| P2-3 | The lifecycle: Atlas's states, status, attention, quiet work, leases, recurring work | §5; §4.2 (status, check-in) | P3's stop rules | ≈$0.50 |
| P2-4 | Versions: typed parts, what changed and why, caused-by, provenance, confidence | §4.7, §9.4 | — | $0 |
| P2-5 | New kinds of evidence: Screen, founder acts, executions, documents, chat, tickets | §2.1–2.2, §7.3 | P1-4 | ≈$0.50 |
| P2-6 | Facts travel: five audiences, along parties, dependents | §10 | P2-2 | ≈$1 |
| P2-7 | The founder's word: decisions, answers, locks, suppressions, delegation, attributions | §7.2–7.4 | P2-5 | $0 |
| P2-8 | The admission laws, the invariants and the guards | §11, §15, §17 | each step | $0 |
| P2-9 | One copy of the grouping rules (placement is L2's, P4) | §4.1, §4.4 | P1-4; P4's placement call (owed) | $0 |
| P2-10 | Visibility on evidence and pages; tenant isolation | §14, §17 (guard 5) | — | $0 |
| P2-11 | Retention that follows the work | §14 | D-P2-7 | $0 |
| P2-12 | Placement at scale (the drill) | §4.1, §18 | P2-9 | ≈$3 |
| P2-13 | The evidence contract: envelope, authority, bitemporal facts, coverage, temporary and obligation-class mail, signals, joins | §1 (evidence rows), §2, §10.1 | — | $0 |
| P2-14 | Parties and identity: profiles, roles, affiliations, addresses, doubt, team and agents | §3.1–3.3 | P2-13 | ≈$0.30 |
| P2-15 | The read API and the snapshot; receipts, lineage, caches | §12, §13, §7.3 | P2-13 | $0 |
| P2-16 | Absence, unknowns, EvidenceNeeds and the DecisionObject | §7.1, §9.1–9.3 | P2-15 | $0 |
| P2-17 | Admission per candidate and structural changes; the situation row; ledger and receipts | §4.1, §4.2, §11, §13 | P2-8 | $0 |
| P2-18 | Loops as code knows them: whose move, dates, waves, bounces, meeting follow-through, conditions, expectations | §4.2, §4.3, §4.4, §4.8 | P2-13 | $0 |
| P2-19 | Claims, conflicts and verified figures | §4.5 | P2-7 | $0 |
| P2-20 | The brains: Behavior, Adaptive, Persona; patterns, cadence, predictions | §7.5, §8 | P2-7 | ≈$0.20 |
| P2-21 | The reads that need no model: timelines, status, changes, performance, metrics, checks, health, stages, meetings, agents | §12, §4.10 | P2-15 | $0 |
| P2-22 | Reach 365 days in the copy | §2, §14 | D-P2-16 | ≈$4 (L1-style reading measured) |
| P2-23 | Correct data: Indian units and currencies, a reliable "later", one message captured twice, secrets redacted | §20.1, §20.6, §20.7, §20.12 | P2-13 | $0 |
| P2-24 | Safe operations: withdraw one item, revert a run, upgrade old conclusions, erase and export a tenant | §20.2, §20.3, §20.9, §14 | P2-17 | ≈$0.50 |
| P2-25 | Measure ourselves: the Notebook's own accuracy, calibration, our numbers over time | §20.4, §20.5, §20.11 | P2-20 | $0 (a private hand-labelled sample) |
| P2-26 | The company's rules: working week and holidays, decision rights | §20.8, §20.10 | P2-0 | $0 |
| Q1 | Stop readings for departments that are off | — | D-P2-8 | saves |
| Q2 | Measure production's table sizes and dead rows | — | — | $0 |
| Q3 | Keep the text that live work cites | — | D-P2-7 | $0 |

---

## The notebook track

### P2-0 · The company page, and stable ids
- **What:**
  - The company page as fact rows (07 §3.4): legal and product names, our addresses and domains, the time zone (from `orgs.timezone`, never guessed), founders and team, departments switched on, what we do, positioning versions, verified claims, the fixed list of needed facts, and `customer_kind` and `jurisdiction` (each confirmed by the founder).
  - **Company milestones** (07 §3.4), with `told_to`, so a milestone is known to be new to a party.
  - **Stable situation ids:** minted once from (tenant, first member evidence id). On regrouping, the id of the old situation holding most of the members is kept (07 §4.1).
- **Tests:**
  - every phase reads "us" from the page;
  - a rebuild keeps every id of `b2` whose members did not change;
  - a needed fact no mail states is stored as "not stated anywhere";
  - a founder confirm writes a `founder_decisions` row (scope `company_page`, `scope_ref` the field) and sets the row `accepted`, with `accepted_by` and `accepted_at`; a correction sets the value with basis `founder` and locks it; block A prints it on the next run; a later model proposal for it is held (A-11);
  - a test tenant marked `team` in another country gets its `customer_kind` and `jurisdiction` rows, each accepted by the founder;
  - approval lead times, critical vendors and owners per area are stored as `unknown: not stated anywhere` until the founder states them, and a stated one is accepted with basis `founder`;
  - the 23 Oct review is new to the accelerator partner, whose August updates carried only traction figures.
- **Done when:** the page round-trips with every field, and the time zone is printed beside UTC in every dossier (with P1-1).

### P2-1 · The goal object, its grain and its proposal admission
- **What:**
  - the object of 07 §6.1;
  - the grain rules of §6.2;
  - proposal admission (§6.4): duplicates (a dropped or rejected goal never returns), the cap, and evidence of our own act;
  - `goal_kind` (umbrella or door), `goal_progress` rows, and goal versions with the columns of a page version (§6.1).
- **Tests:**
  - the ideal's 9 in-copy goals, typed in as a fixture, are stored and read back with no field lost;
  - the holds: a duplicate is held; a fourth proposal in one week is held (the eleventh in the first onboarding week); a proposal with no act of ours is held; one naming an unprinted object is rejected; an admitted proposal writes only a pending brief line, never an approved goal;
  - grain: 18 application situations propose one `umbrella` goal, not 18; the reconsideration is a `door` child; a nesting depth of 2 is refused;
  - the fallback fixture, run only if you decline D-P2-17: 18 application situations give 18 `door` goals under the optional accelerator parent; the raise is one goal; the engineer hire is one goal; a goal whose parent has a parent is refused;
  - the 27 Oct incubation letter sets the incubator goal to `reached_pending`, with the event id and cause `verified_outcome`; only a `confirm_goal` decision sets `achieved`, with `confirmed_by`; a causeless model change is rejected (A-28);
  - progress loads with its basis: the raise as a count ("nothing committed"), registration as unknown with `missing_source` the portal, the incubator as 4 of 5 steps, the engineer hire as unknown with reason `not_counted` (the answer may be off-mail, and the sources that could show a start are partial); a reading as of 28 Oct is a new `goal_progress` row, and the 23 Oct reading still reads back.
- **Done when:**
  - the 18 programme applications sit under "get into an accelerator this cycle", with `i1`'s reconsideration as its child;
  - the raise is one goal, not three;
  - the intro platform's 163 situations are activity, not one goal;
  - the goal invariants hold (I-10, I-25), and no goal change is without its cause (A-28);
  - if you decline D-P2-17, the fallback fixture replaces the first done-when line and the first grain test: one goal per application, with the umbrella optional (07 §6.2).

### P2-2 · One link set, goal ↔ goal links and meaning links
- **What:**
  - `goal_situation_links` as 07 §6.3, written by both the page and relate (one row per link), in the same transaction as the admitted situation; `through` required unless the relation is `unclear`; links to a proposed goal kept with `confirmed = false` and never counted;
  - `goal_links` (goal → goal); on a goal merge or drop, links end and a merge re-creates them on the survivor;
  - `intelligence_links` (07 §4.6): the closed vocabulary (A-26: `causes` and `related_to` refused; "X blocks Y" stored as Y `depends_on` X), writer, `writer_ref`, `evidence_ids`, `epistemic_status`, `valid_from` and `valid_to`.
- **Done when:**
  - there are 0 disagreements (53 today);
  - at most 5 live situations are "not linked" (21 on `b2`), each listed with its age, never hidden; `c2` is among them; a situation whose only links are `unclear` counts as not linked;
  - every goal whose situations state traction depends on "one verified number everywhere";
  - one fixture per link word passes; an ended link keeps its row; a link naming an unprinted goal (A-10), or with a relation outside the list (A-26), is refused;
  - an invoice blocked by a missing contract (two departments, two owners) is stored as `depends_on`, and the invoice's page prints "blocked by" it since its date, with why;
  - when the founder picks the true traction number, `p1`'s `contradicts` links end that day, and a read as of an earlier date still shows them;
  - in `b2`, the three per-investor goals merge into one, and no situation loses its goal;
  - a link to a proposed goal is stored `confirmed = false`, is not counted in a live goal's progress or shown on a card, and is confirmed in the same transaction as the goal's approval.

### P2-3 · The lifecycle
- **What:**
  - Atlas's 14 states, with the transition table (07 §5.1), including the resolutions the plan needs (a `done_when` match, a passed deadline, a timer close, the founder's drop) and reopening only from an L2 `reopen` mutation;
  - `status`, `check_in` and `state_reason` (§4.2);
  - attention (prioritise, decay, ignore, improve) as its own field (§5.2);
  - the quiet-work rule (§5.3): **no timer while we owe something or the other side left a door open in writing**, with Maintain's review for goal-linked work;
  - the open door stored as a loop (§5.3); `lower_now` (§5.2);
  - leases (§5.4), recurring work with code's proposal and `recurring_work()` (§5.6), and staleness of facts, claims, addresses, stages and slots (§5.5, §2.5).
- **Tests:**
  - `s1` (once in the copy) stays live with its card;
  - `f2` resolves on the first pass after 24 Oct, as submitted or missed;
  - a resolved situation reopens on contradicting evidence through an L2 `reopen` mutation; with no mutation it stays resolved, with a wake-up queued;
  - a meeting alone cannot resolve `b2`: an L2 `resolved` resting on the calls alone is held (A-6); a founder `drop` citing its decision row resolves it as `withdrawn`;
  - `b3` closes on its date (`if_missed = close`); when the introduced person writes, `wake_on` wakes it and an L2 `reopen` mutation reopens it;
  - every allowed transition passes, and a sampled set of disallowed ones is refused (A-6);
  - an expectation passes its date with nothing matching: the state moves to its `on_miss_state` by rule, with 0 model calls, and `escalate_to` is recorded; a recorded decision that meets it closes the watch (`closed_by`);
  - status reads `waiting_on_them` for `f4` since 21 Oct, `put_off` for `l1` since 20 Oct, and `done` for `i6` since 26 Mar (once in the copy); `f2` dropped by the founder reads `dropped` since the decision; `i2` reads `waiting_on_us` since 8 Aug; a situation with nothing owed that the quiet rule quiets reads `quiet` since that day; an invoice with an open `depends_on` on an unsigned contract's situation reads `blocked` since the link began, and a founder put-off on the same invoice reads `put_off` (precedence); `f3`, owed a referral by a third party, reads `waiting_on_them` since the day it was promised (the loop's `opened_at`); a monitoring situation with no open loop and an expectation ahead reads `waiting_on_them` since that expectation's `set_at`; a live situation with nothing owed, nothing expected and attention not quiet reads `unknown {nothing owed}`; a blocked situation with a live loop owed by them reads `blocked` (precedence over waiting);
  - a founder Done on `f1` sets `check_in = reported` and leaves it `verifying`; the held review plus our mail after it resolves it with `outcome_ref`; with no source, the founder's word closes it as `founder_word`, with a reason;
  - `i1` never goes quiet at 45 days: its open door keeps it `monitoring`, with an expectation; no open card stands on a quiet situation (I-28);
  - other programmes rise, and the accelerator's papers move to `lower_now` with their next date, then rise again when the expectation is missed;
  - a weekly report becomes one recurring situation; a skipped week sets `missed_since`; `recurring_work()` lists it;
  - recovering `f2`'s archived reminders clears `judged_through`, and the next version says the text was recovered;
  - a May traction figure prints as stale in October, and a July slot opens no expectation in October;
  - the stale July cards are gone (with P5-1).
- **Done when:** no in-copy ideal card is lost, and invariants I-9, I-14, I-15 and I-28 hold.

### P2-4 · Versions: typed parts, what changed and why
- **What:** every version holds the typed parts of 07 §4.7:
  - facts, inferences, hypotheses and unknowns;
  - frames and expected-versus-actual;
  - decision need, surface, expertise refs and tools;
  - `why_changed`, `caused_by_at`, `trigger`, `as_of` and provenance (with pack hashes, tool versions and the model-call count);
  - `confidence`: the six dimensions of §9.4, each with the tool id that computed it (P4-3's calculators) and a reason when not strong. The situation's confidence is the weakest, by code; the model's answer schema has no confidence field (N8);
  - `changed_fields` as `{field, from, to}`, `fields_after`, `decision_need {state, reason}`, `evidence_need_ids`, `best_next_move`, `plan_candidate`, and `expertise_refs` that include company patterns; the size cap.

  Stage history is read from versions. Goal versions carry the same columns (§6.1). Card versions are kept (with P5).
- **Done when:**
  - the replay report (P1-8) lists each day's changes from version rows alone;
  - `i1`'s history (6 Aug, 7 Aug, 26 Aug, 23 Oct) lists from versions;
  - a ReasoningResult fixture round-trips with no field lost, listing every part of §4.7, `confidence` included;
  - `p1` stores Authority medium and Coverage weak, so its situation's confidence is weak, never a blend; a dimension that is not strong with no reason, or any dimension with no tool id, is held (A-8);
  - `page(work_id, 2)` reads v2's expectation after v3 edits it, and `page_diff` from v2 to v3 reads a moved deadline's old and new dates;
  - the incubator goal's step history (done, dated 23 Oct) lists from goal version rows alone;
  - `i1`'s next move, delegated to an agent, is done when our mail carrying the milestone is in the thread, and reads overdue past its date;
  - `i3`'s verdict lists the playbook stage it relied on, and `item_uses` returns it with later founder corrections;
  - a below-gate finding appended by `rule:p5-surface` is stored with `resurface_when`, and `why_no_card` returns it;
  - a version over the size cap fails I-27.

### P2-5 · New kinds of evidence
- **What:** Screen moments (kept or temporary; seat-private), founder acts, execution results, documents, chat and tickets (07 §2.2). Each one:
  - goes in the one envelope (§2.1);
  - has an as-of rule;
  - is placed, and can be cited by id.

  An execution's "done" is reported until its item is seen. What a delegation brings back is evidence, and passes the mail checks (§7.3). `executions` carry `work_id`, `page_version`, `goal_version` and `approval_ref` (07 §1, §7.3).
- **Done when:**
  - a founder act and an execution outcome appear in their situation's dossier and are cited;
  - a synthetic document comment closes `f4`'s `done_when`;
  - one situation holds a mail, a calendar event, a chat message and a ticket, each cited by `evidence_id`;
  - an agent's send of the `i1` update stays reported until the mail is seen in the thread; the page then moves to waiting on them, with an answer due within 14 days, and the goal shows the step done with its date; a returned execution never closes a loop alone;
  - a `my_promise` Screen moment becomes a member visible only to its seat; a 13-word quote is cut to 12; nothing beyond the hash and the quotes is stored; with the semantic lane off, the moment is not promoted.

### P2-6 · Facts travel
- **What:** the five audiences of 07 §10.2:
  - the same goal;
  - linked situations;
  - goals that depend on it;
  - by need (update owed, re-contact with a new fact);
  - company-level changes.

  Also: travel along parties (a bounce, on leave, a role change) and `dependents()` for P1's dirty set.
- **Done when:**
  - the incubator's review appears in the accelerator page's dossier (`i1`), dated, with its source, and the receiving version records `evidence_for`;
  - a newer positioning re-raises `s1` (once in the copy);
  - `i5`: each situation holding a bounced address learns which address failed and which works; a contact on leave shows on every live situation they are in;
  - `dependents()` returns, by id, the linked, same-goal and shared-blocker situations for a three-step chain and for a cycle fixture, and never the situation itself.

### P2-7 · The founder's word
- **What:** `founder_decisions` (07 §7.2):
  - answers apply to the situation and its goals, and are never asked again;
  - corrections lock fields, on situations, parties, goals, links and founder company-page rows; a founder-placed member is never moved by placement (A-11);
  - suppressions with scope, `scope_ref` and date, listed by `suppressions(viewer)` and ended by `undo`;
  - delegation states, with `due_at` and `done_when`; agent and delegate sends checked against their approval (§7.3, I-20);
  - feedback against the card version, with a closed reason and `feedback_scope`;
  - `state_goal` for a goal the founder states; `attributions` for L6 codes aimed at L3 (§7.4).
- **Tests:** one per action:
  - confirm changes the label in the next run;
  - edit is a founder version the model cannot overwrite;
  - "not now until a date" makes no gap card until then, then the goal wakes; `l1` put off until 1 Nov makes no card until then, then wakes;
  - drop: `f2` dropped stops its reminders; a dropped goal proposal proposed again is held, with the dropped goal as `duplicate_of`;
  - an answered question settles its loop;
  - a model change to a locked field is held and becomes a question;
  - approve and choose_option write who, when and the option, mark the DecisionObject decided, and move the situation `decision_ready` → `decided`; an L4 ExecutionObject fixture sets `exe_id` and moves it to `executing`;
  - done sets `check_in = reported`; a hand-over runs `proposed` → `verified`; ignore a sender domain, list it in `suppressions`, undo it, and its cards return;
  - feedback `bad_timing` with scope `this_thread` is stored against the card version and `evidence_ids_shown`; "Already done elsewhere" on `i3` writes `already_handled` against the situation version shown;
  - after the founder moves a mail between works, a re-placement leaves it in place and writes a question;
  - confirming a goal with "by when" unanswered moves it to G-live on the next run as `approved`, not `active`, with the open question as its next move and "not yet active" as its progress; answering the last question makes it `active`, and its progress counts; a founder-stated goal is cited by evidence id, is in G-live, and the next run links situations to it;
  - the `already_handled` attribution on `i3` is admitted from writer `l6_record`; the same row from writer `x` is refused;
  - after the founder says `c1`'s portal is not an investor, a model proposal of investor is held as a question, and the kind stays government;
  - I-20 fails on a send with no approval, and on text that differs from the approved digest; a teammate's send needs an approval from the right seat (§20.10).

### P2-8 · The admission laws, the invariants and the guards
- **What:**
  - laws A-1 to A-32 (07 §11.2), each with a positive and a negative fixture;
  - invariants I-1 to I-28 (§15), run at the end of every build, Evolve day and replay day. A failure fails the day;
  - the CI guards of §17 (1 to 10), each proved by a seeded mutation that makes it fail: a write to `graph_facts` from `work_store` (guard 1); a model-client import in `context/` (guard 3); the field registry, one entry per column with its writer and consumer, and its two-way totality check (guard 6); seam tests from an L2 result through admission to the snapshot and the card, and from an L1 signal to evidence (guard 7); dossier or answer text in a column (guard 8); a cache read as a source (guard 10).
- **Done when:**
  - every phase that admits model output writes a held row for each refused item;
  - nothing is filtered silently;
  - the fixtures include: `causes` and `related_to` refused (A-26); a pattern sentence with no evidence held, a reference to the unit admitted (A-29); an uncited "the vendor is blocking the launch" held, "approval may consume the window" with `based_on` admitted (A-21); a chat line "probably renewing" writes no owner (A-30); a fact citing only a prior case held, the same fact also citing a current member admitted (A-31); a projected figure restated as reached (`p1`) held (A-2);
  - the regression fixtures stay green: a change naming a known party's first name, our product name or "UTC" is admitted, and so is one whose dates match its quoted lines;
  - a Screen moment or a meeting left unplaced fails I-3;
  - every guard fails on its mutation and passes on the clean tree.

### P2-9 · One copy of the grouping rules
- **What:** placement (grouping threads into situations) is L2's judgment. **It moves to P4** as the placement call, run by P1 and admitted here. P4 has no such step yet; it is listed under **Owed by other parts**.
  - Code's clustering only proposes candidate bundles: registrable domain, one per introduction, system mail about what it names, and a first mail from an awaited party, proposed to its waiting situation first.
  - `update.py` and `works.py` share one copy of those proposals.
  - Continuation adds a mail to a situation only when it brings no new party, by 07 §4.4's code check: no new address or domain, no introduction cue in `body_new`, no L1 introduction signal.
  - Each introducing platform has a channel work for its housekeeping, with each introduction as its own child (§4.1).
- **Done when:**
  - a test proves both paths propose the same bundles;
  - a fresh build has no situation whose version 1 was written by code;
  - a second introduction offer inside an older introduction's thread lands in its own child work (`b1`);
  - `f3`'s scout's first mail is proposed to `f3`'s work;
  - a platform housekeeping mail joins the channel work, not an introduction; the channel has one child per introduction with `parent_work_id` set; housekeeping raises no introduction card;
  - a reply from a known party in a known thread joins its situation with 0 model calls; a mail with a new address or an introduction cue goes to placement; a placement result with no reason or no printed ids is held (A-10).

### P2-10 · Visibility and tenant isolation (07 §14)
- **What:** every conclusion stores the narrowest audience of its evidence. Pages are built per reader; withheld evidence is counted. A Screen moment stays with its seat. Every table of 07 §1 carries `org_id` with row-level security on it; guard 5 fails on SQL without an `org_id` predicate; no read crosses tenants.
- **Tests:**
  - a synthetic second seat with one private thread in a shared situation. The founder's page never quotes it; the seat's page does. A task asks the seat to share or act;
  - a seat's Screen moment never appears on the founder's page;
  - two tenants: tenant A's session reads zero rows of tenant B in every table, and a query without `org_id` fails the guard.
- **Done when:** I-11 holds.

### P2-11 · Retention that follows the work (D-P2-7)
- **What:** `evidence_citations` holds every live member of a situation that is not closed (quiet included), and every id cited by a goal that has not ended. Evidence cited only by closed situations or ended goals is kept `after_close_days` after the close (07 §14), then expires, and its citations are marked `quoted_only`. A report lists what today's rule would delete that live work still cites.
- **Done when:** the report runs on `b2`, every item on it is explained, and a quiet situation's text is protected; `i1`'s history stays readable past 180 days while its goal is live; after the close plus the policy days, only admitted quotes remain; a raw copy with clean text, a decided promotion and no provenance row is purged, and one a provenance row points at is kept.

### P2-12 · Placement at scale
- **What:** the placement drill (with P4) on the copy's six months, with every thread cloned twice under new ids and shifted dates: about 5,400 mails. Measured:
  - cost and time;
  - the largest bundle the prompt was given;
  - the share placed by continuation and by the model;
  - whether the 17 in-copy ideal items are still each one situation.
- **Done when:** the cost grows no faster than the mail, no bundle is cut short, and the 17 are still found.

### P2-13 · The evidence contract
- **What:**
  - the envelope of 07 §2.1 (`known_at`, `authority_class`, `signal_type`, `addr_raw`, `content_digest`), with the closed noise reasons;
  - the authority ladder (§2.4), set by code, and the class derived from the rank;
  - bitemporal, epistemic facts with `last_confirmed_at` and span references `{evidence_id, start, end, quote}`; a conflict row whatever the ranks (§2.5);
  - per-source and per-situation coverage, with each source's date span (§2.6);
  - temporary evidence never kept (a sign-in code from a live situation's party joins it header-only), and obligation-class mail kept (§2.3);
  - meetings with each attendee's response and `when_class`; `delivery` on every outbound mail (§2.2);
  - node types as data, each node with a label, a cluster and receipts; `qualified_signals` with all ten L1 fields (§1);
  - the six correlation joins of §10.1, as join rows with `derived_from`.
- **Tests:**
  - `c2`'s renewal notices are not noise, and sit on the vendor's situation;
  - one-time codes are counted and never cited;
  - the coverage of a situation lists its unread items with reasons;
  - a meeting rescheduled after 23 Oct shows its old time in a build as of 23 Oct;
  - `p1` reads 6 mail threads from May to Aug plus a calendar item; `i1` reads 6 messages in full; `i4` 12 threads; `i5` 6 bounce notices; the counts and date spans reproduce from rows;
  - `b2` holds the tenant node and the six other node types, each with a label, a cluster and receipts;
  - a signed document outranks a mail summary, and its class is printed;
  - a published-signal fixture reads back with all ten fields (seam test, guard 7), and its `importance_bp` is never used as materiality;
  - a meeting and the threads with the same attendees within a window are joined; joins create no situation and no conclusion (I-22);
  - the incubator's portfolio-call invite reads `needs_action` as of 23 Oct, and the incubator goal lists it in `gaps`;
  - a portal's sign-in code mail joins the registration work header-only, and is never quoted.

### P2-14 · Parties and identity
- **What:**
  - party profiles (07 §3.1): kind from the frozen list (data, from Plane D's vocabulary), cluster, relationship to us, affiliations, identity strength with raw identifiers, `introduced_by`, relationship state with the cooling and cold rule, cadence, typed facts and `availability`;
  - addresses with deliverability;
  - roles per situation;
  - identity doubt and reversible merges (§3.2);
  - team members and agents (§3.3);
  - the reads `party`, `alternate_addresses` and `delegates` (§12).
- **Tests:**
  - `f3`'s scout holds two affiliations, each with its source mail;
  - `i2`'s investor has `introduced_by` from the forward;
  - a probable link stays a doubt;
  - a merge undoes cleanly;
  - an address with dots and capitals is reused unchanged;
  - the intro platform is in network, the registration portal in compliance & vendors, the candidate in team; every `b2` party has one kind, one cluster, a relationship line and a role in each live situation it is in (I-24); `c1`'s portal is government, never investor; `h1`'s candidate is a candidate, with role `awaited`;
  - `party()` returns the accelerator partner's title (rank 2, 4 Aug), ball in court (rank 4, derived), 9 receipts and 4 versions; the `s1` prospect uses a competing tool (rank 2, 13 Apr; once in the copy);
  - a fixture pack that adds a party kind, a kind of work and a stage word (a ladder or `pursuit_stage` word) passes with no migration and no code change (guard 9);
  - a party silent for 28 days during an active raise becomes `cooling`, dated when it crossed; a fast replier (75th-percentile gap under a week) turns `cooling` at 14 days and `cold` at 28;
  - `i5`'s bounced partner address lists the three working addresses; a `dead` address is never offered as working;
  - a member on leave is unavailable before the return date and available after it; an agent is returned with its approver.

### P2-15 · The read API and the snapshot
- **What:** `context/notebook_api` (07 §12) in the notebook as `nb/api.py`:
  - `snapshot` with its blocks and caps, blocks S and V included, the anchor's facts in block P, and authority classes (§12.1);
  - `page`, `still_open`, `due_dates` (with `wake_on.at`), `lineage`, `why_no_card`, `citations`, `claim_recipients`, `party_appearances`, `open_situations_sharing`, `waiting_for` and `receipt`;
  - `model_call_evidence` and the run receipt's fields (§12.4); the `trace_id` chain (§0 rule 5); the re-check of a result that returns after the page changed (§7.3).

  `judge.build_dossier` becomes the snapshot's caller. No other module reads the tables (guard). Tools take the snapshot only: no database handle, no clock.
- **Done when:**
  - the `i1` dossier is built from the snapshot alone, with an empty-block reason where a block is empty;
  - the snapshot read p95 is under 2 s on `b2`;
  - the `i1` snapshot is rooted at its anchor, the accelerator partner, and prints the `works_at` affiliation, our commitments, the open loop, the programme party's edges and the sibling open situations;
  - a snapshot at revision R, rebuilt at R after 10 more admissions, is byte-identical; dropping and rebuilding every cache gives identical pages and wake-ups;
  - the `i1` dossier prints in full exactly the members newer than `judged_through`;
  - `i1`'s judgment stores every id printed, including ones the answer did not cite, and a founder read lists them by situation and date;
  - `lineage` of three ideal cards returns the full chain under one `trace_id`, with the footer (trace, pack hashes, model calls); `lineage` of a date-woken card (`f3`) returns one `trace_id` too;
  - the `i1` snapshot's block G lists each open goal with its linked situations;
  - a receipt fixture shaped like the ideal's `i1` receipt (9 units ran, 1 declined, 2 calls, verdict update v4) round-trips, and `receipt(run_id)` joins it to the situation and card versions;
  - seven open situations with one `approver_party` return seven rows, with wait age and nearest date;
  - `f4` wakes on the reviewer's reply or at Mon 26 Oct 10:00, whichever comes first; `still_open` on a renewal already signed returns not open, with its `outcome_ref`;
  - an agent drafts the `i1` update from the 23 Oct page; its task row holds that page version and the goal version it was given; the incubation letter arrives on 27 Oct; the returned draft is held as "page changed since the task was given" and re-checked.

### P2-16 · Absence, unknowns, EvidenceNeeds and the DecisionObject
- **What:**
  - `situation_absences` keyed by `work_id` (07 §9.1): the four states, the scope read and the coverage receipt; a `verified_absence` is refused unless every source in scope is full;
  - `unknown {reason}` and `checked_absent {scope}` stored as typed values on every nullable conclusion field (§0 rule 6, §9.2);
  - `evidence_needs` linked to situations (07 §9.3): a HOLD raises one; a matching new member meets it and wakes the situation;
  - `decision_objects` minted when `decision_need = required` (§7.1).
- **Tests:**
  - `i3` is a verified absence; `h1` is partial coverage and becomes a question; real MRR is unknown; the four traction numbers are conflicted;
  - `f2`'s archived reminders, and the pre-window mail behind `i6`, `s1` and `s2`, appear as unread, with reasons;
  - a held loop closure raises a need, and the next matching mail meets it;
  - an investigation page shows a recommended owner, and only an execution or a founder decision makes an assigned one;
  - `decision_need = none` mints nothing; `required` mints one with all its fields; an unchanged re-run mints no second one; passing the decision deadline moves it to `expired` by rule;
  - the renewal fixture (`c2`) shows the situation, an unknown, an expectation, a hypothesis, a decision, a commitment, a plan and an outcome, each with its own id.

### P2-17 · Admission per candidate, structural changes, ledger
- **What:**
  - a "new situation" mutation gets one verdict (07 §4.1, §11);
  - duplicates are held as `possible_duplicate_of`, and L2 chooses;
  - merges, splits, parents, reopens and higher-order situations are applied only from a named L2 mutation;
  - the admission ledger has one row per candidate and per change, admitted ones included (§11.4);
  - every pass writes a receipt;
  - compare-and-set on the version read; idempotent on request id and bundle hash;
  - the situation row's fields (07 §4.2), with `anchor`, `primary_party`, `matter_key`, `topic_key`, `about`, `materiality` and `aspects`, and `domain` with `domain_state` stamped from the tenant's activation at judgment time;
  - the writer list of §11.1 (any other writer is refused and ledgered); completeness (A-27); a department that is off is rejected (A-32); the effect of every L2 outcome (§11.1);
  - a failed run admits nothing (§11.3); the `fingerprint` computed on every admitted version;
  - a merge moves members to the survivor, and `history_of` reads both chains (§4.1); `replay_run(run_id)` re-admits a stored answer with no model call;
  - receipts with declared silences `{kind, reason, mover, since}` and the ids of situations formed, decisions emitted and situations resolved.
- **Tests:**
  - two concurrent judgments of one situation: one writes, the other writes nothing and queues a wake-up; judgments of two different situations at once both write;
  - a replayed mutation writes no second version;
  - a run that times out, and one with malformed output, leave the situation byte-identical and write one receipt each;
  - a write with writer `x` is refused and ledgered; one fixture per L2 outcome (all 14) writes the effect of §11.1;
  - `i1` stores its type, path, stage, anchor (the accelerator partner), `about` (the partner and the reconsideration deal) and materiality `high`; `f1` and `p1` are `critical`, each with its reason line; `p1` is about the traction-claims group; new evidence on `i1` is admitted as update v4, and duplicate open cards stay 0 (I-23);
  - two filings with one government portal coexist; two threads on one renewal are held as duplicates;
  - `c1`'s two situations (two cards today) merge into one, with members from each; three customers' same complaint becomes one higher-order situation, only from an L2 mutation, and each member gets a `part_of` link to it while staying live with its own state; `f2`'s two sender files merge, with both histories;
  - an ordinary-looking signal gains materiality from a deadline already in the graph, while its `importance_bp` is unchanged; a vendor and a contract node are referenced by an Admin and a Finance situation, with a different owner per aspect;
  - a candidate from a shadow domain is admitted with `domain_state = shadow`; a candidate for a support desk that is off is rejected;
  - a re-sent mail and a re-uploaded identical file leave the fingerprint unchanged; `replay_run` reproduces the same rows with zero model calls;
  - a pass over zero candidates writes `asked = true, candidates = 0`; a pass never asked writes `asked = false`; a bad receipt row fails alone: the other rows are written, and exactly one error row records it.
- **Done when:** admission p95 is under 1 s on `b2`, and I-12, I-23, I-25 and I-26 hold.

### P2-18 · Loops as code knows them
- **What:**
  - **Waves** (07 §4.8): the same `template_key`, 3 or more recipients, the same local day; `sent_on`, `body_digest` and rounds stored. Recipients are members, with delivery and reply.
  - **Bounces** (§2.2, §4.4): the bounce joins every situation holding the send; the waiting loops go `moot`; a re-send loop opens; the address is marked.
  - **Meeting follow-through** (§4.4), with its `fulfils` link and "a decision recorded"; **conditions** with `set_by` and the met rule; **delivery** on every outbound mail, and `thread_state` (§2.2, §4.4).
  - **Expectations** (§4.3): several per situation, past dates kept as `missed_since`, every open loop with an `expected_by`.
  - **Whose move, by code** (§4.2): `whose_move`, `awaited_party`, `whose_move_since`, `next_actor` and `next_check` on every admission; a differing L2 value is held (A-5).
  - **Dates** (§4.2): the six deadline-like dates, each with its basis (A-7), and `stated_dates` with `valid_to` and `replaced_by`.
- **Tests:**
  - `i5` leaves 0 waiting loops on bounced recipients and 6 re-send loops;
  - `c1` reads "sent 16 Oct · 1 of 2 delivered" from `delivery` rows;
  - a thread is `awaiting_them` after our ask, `answered` after their reply, `closed` when its loop closes and `bounced` after a notice, each with `since` and loop ids; the nightly pass recomputes them; a send with no notice after 24 hours moves from sent to delivered;
  - `i3`'s call opens a follow-through owed by us;
  - `f3` is missed since its promised date in a fresh build as of 23 Oct, and stays so on a re-judgment with no new mail;
  - `i4`'s wave stores its date, digest and 12 recipients, each with reply and last exchange, and counts 12 sent and 0 replies;
  - whose move: `i1` reads them since 26 Aug; `i2` us since 8 Aug; `f3` a third party; `b3` them, with its auto-close date; an L2 "us" on `b3` with no newer cited event is held;
  - `i1`'s page reads waiting on them since 26 Aug, stage reconsideration requested, their decision expected within 14 days of our next update, if missed close;
  - `f4` (waiting on a review, check Monday 10:00): `next_actor = geniOS`, `notify = false`, and no dated card;
  - a fixture with an expiry, a 7-day notice and a decision deadline before the notice date: each date has its basis, and a `decision_deadline` copied from `formal_deadline` is held;
  - an investor's "come back once enterprise traction is visible" is met by a later signed-pilot member, and `met_by` points at it;
  - a July slot replaced by a later confirmation raises no overdue expectation and no conflict;
  - an expectation "before the 11:30 slot" (the anchor minus 10 minutes) moves when the slot moves; one anchored on a future event of ours closes when the event arrives; a stated date with no time is the end of the local day;
  - a second send of one template adds a round; a second broadcast to 33 recipients adds a round and opens no situation per recipient; `s2`'s 28 mails in three batches (13, 8, 7) form one wave with three rounds, the last marked `tailored` (once in the copy).

### P2-19 · Claims, conflicts and verified figures
- **What:**
  - claims with modality, speaker, normalised amount and recipients (07 §4.5);
  - comparison within a metric family;
  - conflicts as `discrepancies` with sides, `ranked` when the sides' authority differs (§2.5); a metric with two or more values told and no verified value is `conflict_open` for drafts and checks;
  - one "one number everywhere" situation that grows on every run;
  - the founder's pick becomes the verified figure;
  - drafts use only settled values: `settle_text(text, as_of)` for cards and drafts; `depends_on_fact` links written by admission; a conflict offered as news to the one-number goal;
  - the asked-for metric on a question;
  - `claim_recipients` with every value received, positioning and documents with dates, milestones told and repeated paragraphs.
- **Tests:**
  - `p1`'s four statements carry modality and recipients;
  - the 27 Oct broadcast joins the record;
  - a draft with a conflicted number gets the placeholder;
  - `i2` stays `replied_not_answered`;
  - `p1`'s four statements leave traction `conflict_open`, and a draft shows the placeholder; `i1`'s card and draft text, passed through `settle_text`, show it too;
  - the founder picks one of `p1`'s values: it becomes current with founder authority; the other three are superseded and linked to the decision; `verified_claims` records `picked_by`, `picked_at` and the decision id; `i1`, `i2`, `i3` and `f1` are marked for re-judging and their drafts stale, and their next versions cite the chosen value; an L2 or agent change to `verified_claims` is held (A-14, A-20);
  - `claim_recipients` for the accelerator partner returns the expected range, then the reached figure, with dates; the vision paragraph shows 3 sends;
  - a checklist says complete while a ticket and a courier say not dispatched: both sides appear in the snapshot (`ranked`);
  - the 27 Oct broadcast grows the one-number goal's evidence and leaves it `blocked`;
  - opening the traction conflict creates one news item addressed to the one-number goal.

### P2-20 · The brains, patterns and predictions
- **What:**
  - Behavior patterns counted by code, with numerator, denominator and ids, printed as "observed, n of m" until promoted past the threshold, and demoted when later evidence contradicts them;
  - Adaptive leases that always expire;
  - Persona preferences (candidate until confirmed);
  - party cadence, and `company_patterns` with the fields of §8;
  - predictions scored by Maintain, with `prediction_actual` rows for L6;
  - card outcomes with the date of each part, and the resolution `{path, reason, rightly_founders}`, written by rule when a situation resolves (07 §7.5, §8).
- **Tests:**
  - "you book intro calls the same day (6 of 6)" is a counted pattern with its thread ids;
  - the intro platform's "prefers text" note stays a candidate until confirmed;
  - a prediction with `if_missed` is scored on its date;
  - `i4` reads 0 of 12 replies in 10 weeks, and the evaluator's usual reply time, from `company_patterns` rows;
  - a verified-outcome fixture resolves its situation with `outcome_ref` and writes `prediction_actual` (approval took 6 days against a predicted 17), and L6's reader sees it;
  - the `i1` card closes into one `card_outcomes` row: one update with a new fact recommended, delegated and approved, then answered or silent past the expected date, each part dated;
  - resolutions derived from event fixtures, one per path (`agent_proven`: a verified execution outcome, step not edited; `agent_fixed_by_founder`: the draft edited before approval; `one_tap`: approve, choose-option or done with no edit or answer; `founder_work`: otherwise) and one per reason; `rightly_founders` is true for a send, pay, sign, submit, accept-offer or declare-fact act and false otherwise; `aer_hir` over them returns the same counts as P2-21's stored fixture.

### P2-21 · The reads that need no model
- **What:** `goal_timeline`, `company_status(as_of)`, `changes`, `performance`, `meetings_without_followup`, `meetings_without_decision`, `meetings`, `stale_pages`, `stage_counts`, `metrics`, `company_checks`, `aer_hir`, `agent_track` and `context_health` (07 §12), with the line kinds, departments, `not_linked`, grade rules and counts that §12 names. Every count is a named query with its inputs (I-17).
- **Tests:**
  - "1 reply of 28" and "6 of 11" reproduce from rows;
  - `company_status` as of 23 Oct lists every goal with its health and next move, per department with owners (the Founder Office goals and situations), the accelerator goal at risk with its next move, and `not_linked`; as of 27 Oct the incubator goal reads `reached_pending`;
  - the ideal's context-health tiles reproduce from rows;
  - at 23 Oct 07:10 local, the 11:30 review is `today`, earlier calls are `past`, a cancelled invite is `cancelled`; `meetings()` for 23 Oct returns `f1`'s review with its situation, goal and 6 attendees, and the two partner calls link to `b2`;
  - the tiles reproduce from `stage_counts`: "Intros 11: booked 6, open 2, stalled 3" (`b3` stalled since 24 Jul); "Programmes applied to 15: in 2, live 4, rejected 5, other 4" (`f2` incomplete after the 8 and 9 Oct reminders); "Investors written to 21: talked 6, passed 2, silent 13"; "Prospects pitched 28: replied 1, silent 27" (once in the copy); the accelerator goal reads 4 live, 1 incomplete, 5 rejected; the pre-seed goal reads 6 conversations, 2 passes, 0 in diligence;
  - the pre-seed goal returns `happened`, gaps with since-dates, and `did` entries with card ids;
  - `i1`'s timeline lists the rounds, the rejection, "keep us posted" on 7 Aug, our updates of 11, 13 and 26 Aug, then silent since 26 Aug, every line cited;
  - the company checks grade the ideal's way: the four traction numbers `broken`; bounces not re-sent, unanswered questions and the missing billing source `needs_attention`; accepted intros all booked `working`; the ideal's fixture of ten checks grades 6 working, 3 needs attention and 1 broken (60% working), with instance ids;
  - `aer_hir` reproduces "HIR 7 of 17 (3, 2, 1, 1)" and "AER 13 of 38" from a fixture of the ideal's resolutions;
  - `performance(1 Aug, 31 Oct)` returns promises kept, broken and late with loop ids, the median days to answer, follow-ups within 7 days of a meeting (`i3` and `b2` missed) and goal steps on time;
  - `meetings_without_decision` lists `b2`'s calls; `agent_track` for the agent that drafted the `i1` update shows 1 task, its draft approved or edited, and the outcome, with ids;
  - human touches per resolved situation, and calls and cost per admitted situation, reproduce from rows;
  - a new reply on a resolved thread lists it in `stale_pages`, and an L2 `reopen` reopens it on contradicting evidence.

### P2-22 · Reach 365 days in the copy (D-P2-16)
- **What:** a read-only re-cut of this org's Gmail for the 365 days before the cut, into the private local folder. Then rebuild. Also measure what L1-style per-mail reading would cost on it, for D-P2-14.
- **Done when:** `i6`, `s1`, `s2` and "win paying design partners" are found with the right call.

### P2-23 · Correct data
- **What:**
  - claims parse Indian units and currencies (§20.1);
  - every mail stores `sent_at`, `received_at` and its thread position, and "later" means by `received_at`, then position (§20.7);
  - `canonical_item_id` deduplicates an item captured twice (§20.6);
  - a code redaction pass removes secrets before any text reaches a model or a quote (§20.12).
- **Tests:** synthetic strings only; two mails with the same timestamp close a loop in the right order; a mail to two seats gives one member; a synthetic key never appears in a dossier.

### P2-24 · Safe operations
- **What:** `evidence_withdrawals` and its job (§20.2); `revert_run(run_id)` (§20.3); `contract_version` on every version, with upgrade functions (§20.9). Tenant erasure over every table of 07 §1; `export_tenant(org_id)`, which writes every §1 table to one bundle, and `import_check`, which loads it into an empty scratch database and runs every invariant and guard (§14). Running on the customer's own device stays deferred (D-P2-15).
- **Tests:** withdrawing one mail leaves no quote from it; reverting a seeded bad run restores every page exactly; every `b2` version reads under a new contract; erasing a test tenant leaves 0 rows over every table; the `b2` export, loaded into a second empty database, passes every invariant and guard.

### P2-25 · Measure ourselves
- **What:**
  - a private hand-labelled sample (§20.4), scored on every build into [08-LOG](../08-LOG.md), with the recall of important situations;
  - a lint that fails if a tracked file holds a name, address or amount from the private mapping; the scorecard reads the mapping from the private path only;
  - weekly calibration of confidence and predictions (§20.5);
  - `series(metric)` and `projection_accuracy` (§20.11).
- **Done when:** `b2`'s precision and recall (important situations included) are recorded, no later step lowers them, and the lint passes on every tracked file.

### P2-26 · The company's rules
- **What:** `working_week`, `holidays` and `decision_rights` on the company page (§20.8, §20.10). The date tools and admission use them.
- **Tests:** a follow-up after a Friday meeting is due Monday; a teammate's approval of a send to an investor is refused when only the founder holds that right.

## The relief track (today's product)

Owner: Harsh, with the agents Harsh assigns. Each goes live per tenant behind a row, and is measured before and after.

### Q1 · Stop the readings for departments that are off (D-P2-8)
- **What:** every reading pass in `context/runner.process_pending` declares its domain. The runner skips any pass whose domain is off for the tenant: the support desk first, then outreach, spend and the rest. A test lists the passes and fails if one has no domain. This widens GeniOS-013 U13-31.
- **Done when:**
  - for this org, 730 fewer active situations and about 3,590 fewer facts after a week;
  - the chain is shorter (measured with P1 R1);
  - no card the founder acted on is lost;
  - daily health counts the situations and facts whose domain is off (it should be 0).

### Q2 · Read production's table sizes and dead rows
- **What:** one read-only query on production for each table's size, its live rows and its dead rows. It is run by a person with production access; the coding sessions don't read production.
- **Done when:** the gap between 570 MB and the 280 MB of live rows is explained table by table, and a clean-up plan is written. The plan covers vacuum, moving Screen captures and raw bodies to object storage, and provenance trimming.

### Q3 · Keep the text that live work cites (after D-P2-7)
- **What:** until the notebook's rule is ported, a mail's clean-text expiry is extended while its thread has an open question or promise, or a date ahead. It is applied by a platform job from a hold list, not by `capture/`.
- **Done when:** no thread with open work loses its text, measured weekly.

---

## Order and dependencies

```
P2-0 company page, stable ids ─► P2-13 evidence contract ─► P2-14 parties ─► P2-15 read API ─► P2-16 absence, needs + decisions
                                       │                                         └► P2-21 reads with no model
                                       └► P2-18 loops by code (whose move, dates, waves, bounces, meetings, expectations)
P2-1 goal object ─► P2-2 one link set, meaning links ─► P2-6 facts travel ─► (P4-6 goal reasoning)
P2-3 lifecycle ───────────────────────────────────────────► (P5-1 when a card is raised)
P2-4 versions ─► (P1-4 evolve, P1-8 replay)
P2-5 evidence kinds ─► P2-7 founder's word ─► P2-19 claims ─► P2-20 brains ─► (P1-5 act, P4-7 analyse)
P2-8 laws, invariants + guards grow with each step;  P2-17 admission per candidate (with P2-8)
P2-9 one copy of the proposals (placement call owed by P4) ─► P2-12 placement at scale ─► (P1-10 onboarding drill)
P2-10 visibility + isolation ─► (teams, D-P2-10)   P2-11 retention ─► Q3          P2-22 365 days (D-P2-16)
P2-23 correct data (with P2-13)   P2-24 safe operations, erase + export (after P2-17)   P2-25 measure ourselves (after P2-20)   P2-26 company rules (with P2-0)
product:  Q2 measure ─► Q1 departments off ─► (P1 R2)
```

## How P2 lines up with the 28 Oct plan (GeniOS-013 [03](../03-HOW-IT-GETS-FIXED.md))

| P2 step | 28 Oct units it proves, replaces or corrects |
|---|---|
| D-P2-12, P2-17 | **replaces** U13-05 to U13-07's separate tables with the Atlas chain; keeps the one-writer rule (`work_store`) |
| P2-1, P2-2 | U13-27 (block G), with D-P2-13's two blocks |
| P2-3 | U13-24 (the stop rule instead of a default window), now inside Atlas's state machine |
| P2-18 | U13-22 (`work_clock`) with expectations; U13-36 (bounces reach their work) |
| P2-19 | the claims of 05 §6, completed |
| Q1 | U13-31 (readings only for activated departments), widened to every domain |
| D-P2-4, P2-22 | U13-38 |
| D-P2-3 | the promotion path, with the obligation class |

## Owed by other parts

The reviewers' fixes below belong to another part, so P2 does not edit that part; it records what the part must do. Where P2 needs a field, a read or a stored row for it, that side is in the steps above.

| Requirement | What the other part must do | Part and step |
|---|---|---|
| ATLAS-41 | When an expectation is missed, let the Notebook's rule transition run first (0 calls); wake a judgment afterwards only if the new state needs reasoning | P1-4 |
| ATLAS-48 | After each admitted version, mark `dependents(work_id)` dirty and re-run until no version changes, at most 3 passes; write a non-convergence receipt in the run ledger. Test a three-step chain (it converges in 3) and a cyclic fixture (it stops at the cap, with a receipt) | P1-4 |
| ATLAS-23 | Compare the situation's `fingerprint` before waking a judgment; a re-sent mail or an identical file costs 0 calls | P1-4 |
| ATLAS-68 | Call `still_open(work_id, since_version)` before every rung and every send; when it is not open or has changed, drop the rung with the why-not "already handled: outcome evidence exists". On resolution, cancel the situation's pending wake-ups. Test: a reminder about a renewal already signed is dropped with that reason | P1-4; P5-6 at send |
| IDEAL-74, EXP-13 | Wake on `due_dates()` (it now includes `wake_on.at`), and place a first mail from an awaited party through `waiting_for` | P1-4 |
| EXP-03, FILM-17 | A new step for the placement call: one prompt that places a new thread or tool item into an existing or a new situation, and returns a reason and the evidence ids printed; its schema probed against the grammar limit; golden cases `b1`, `b3`, the intro platform's other offers, and a platform housekeeping mail, which must be placed in the channel work (never in an introduction child) with a reason and printed ids, and makes no introduction card. P2-9 and P2-12 depend on it | P4 (a new step, after P4-8) |
| EXP-03, FILM-17 | Call that placement call at step 4b.2, instead of placing with code | P1-4 |
| IDEAL-28 | Pass every draft through `settle_text` before approval and send | P1-5 (A3) |
| ATLAS-80 | Measure the time to the first admitted situation, and to held relationships, commitments and conditions, against the 1-hour and 40-minute targets; or record the gap as an open decision for the owner | P1-10 |
| IDEAL-33, IDEAL-34, IDEAL-35 | Author the introduction, application and investor stage ladders with exactly the words of 07 §4.10 (P3 07 §2.5 holds the same list), and rename the existing playbooks' stages to them | P3-3 |
| ATLAS-32, ATLAS-57 | Hold party kinds, their clusters, A-9's kind-fit table and the node types in the Plane D vocabulary the index compiles, so a new domain adds them as content | P3-1 |
| IDEAL-78, ATLAS-60, EXP-66 | Six confidence calculators (evidence, frame, temporal, causal, authority, coverage) with 07 §9.4's rules, each printing its tool id. Fixtures: `i1` timing medium (the next cohort date is not in the mail), `i3` frame medium, `p1` authority medium, `c1` coverage medium | P4-3 |
| ATLAS-42 | The calculators `notice_date`, `decision_deadline` (from the company's approval lead time and the observed 75th-percentile latency), `escalation_at` and `verify_by` | P4-3 |
| EXP-32 | Align activity with D-P2-20 (a percentage may sit beside the count, never as progress), and use 07 §6.1's closed progress reasons; never count the engineer hire as 0 of 1 while its coverage is partial (it is unknown, `not_counted`) | P4-4 |
| ATLAS-51 | When a higher-order situation exists, suppress its members' separate escalations with why-not `rolled_up` | P5-1 |
| EXP-39 | A news wake-up: when the Notebook offers a milestone or an opened conflict as news (07 §10.2), wake the receiving situations and goals once per item | P1-4 |
| EXP-33, EXP-39 | The rule also yields `unmeasured` (progress unknown, no missing source, no pending founder decision) and `done` (outcome achieved), and keeps the one-number goal `blocked` until its metric has a verified value and a verifying source in state `full`. P4-4's fixtures stay the test | P4-4 |
| EXP-39 | On a conflict's news, form or join the "one verified number everywhere" goal | P4-6 |
| ATLAS-11 | Store `work_id`, `page_version` and `trace_id` on the card record, so `lineage` starts from the card | P5-1 |
| ATLAS-29, EXP-08 | A newer situation version makes a new version of the same card, never an edit and never a second card; a broadcast to 33 recipients grows the one-number situation and makes no card per recipient (tests) | P5-1 |
| ATLAS-30 | After each card decision, append `surface {lane, why_not, resurface_when}` through admission, as `rule:p5-surface` | P5-1 |
| ATLAS-31 | No card on a shadow situation (test) | P5-1 |
| EXP-09 | A situation with `next_actor = geniOS` and `notify = false` is listed under "waiting" with its next check, and raises no notification | P5-1 |
| EXP-36 | A fifth reason: a goal is `reached_pending` (one card per goal); the founder's confirm closes that goal's other cards | P5-1 |
| IDEAL-28 | Pass card text through `settle_text` before it is shown | P5-1 |
