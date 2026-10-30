# P3 · Plane D · 04 · What needs to be done now

**The full specification is [07](07-THE-PLANE-D-SPEC.md).** This file holds the decisions and the step-by-step build. Every step cites the section of 07 it builds. [08](08-REQUIREMENTS-TRACE.md) shows that each requirement from the Atlas v2, the ideal dashboard, the expected outcomes and the film lands in a step.

**The principle:** the knowledge is mostly right, and the compiler that selects it is already built. So:
1. join the compiler to the model;
2. make the knowledge arrive whole, with its conditions, adapted by the company's brains;
3. write what's missing;
4. get it reviewed, tested and measured.

Rewrite nothing that is right.

Every step is proved in the notebook first. A step is done only when:
- its tests pass;
- its done-when holds;
- the guards it owns (07 §15) pass;
- the acceptance set ([10](../10-ACCEPTANCE.md)) shows nothing worse.

---

## Decisions for Rohit

Each has a recommendation. Saying "go" accepts all of them.

| # | Question | Recommendation |
|---|---|---|
| D-P3-1 | **How is knowledge chosen for a situation?** | By what the situation **is and holds**, across every live domain: its kind of work, stage and qualifier, and its events (a meeting held, a renewal date, a registration, a promise, a rejection). Several units and several situation types per situation are allowed. Not by one key from one domain |
| D-P3-2 | **Is unreviewed knowledge used?** | Yes, labelled "not yet reviewed", on the model's path too: the compiler carries it labelled instead of dropping it. A card whose grounding is unreviewed is an observation, never a recommendation (07 §6.1). A unit you have rejected is never used |
| D-P3-3 | **How does the review happen?** | One sitting per capability (20–40 minutes). Founder Office first, then the Admin units the founder's work uses. Accept, edit or reject each line; the reviewer's name, the date and the content hash are recorded. **The reviewer's one act both approves and switches on**, so "approved but never switched on" cannot happen again |
| D-P3-4 | **In what order is the missing knowledge written?** | The ideal's missing knowledge first (P3-10). Then external meetings → introductions → registrations (Admin's units re-pointed) → renewals (Admin's units re-pointed) → offers and joining → events → partners → design-partner outreach. Events (71 of the notebook's 421 situations) and partners (38) come before the target of 85% can be reached. Every line is sourced, AI-drafted, and reviewed by you |
| D-P3-5 | **Where does the Founder Office live?** | **Keep it as its own domain in the corpus** (your D2 of 9 Oct: its ids, review and activation stay), and **show it as "Admin › Founder office"**, as the ideal does, through display paths. For a founder tenant, Admin and the Founder Office switch on together. The alternative, folding it into Admin as an 11th group, changes 35 ids and gains nothing the founder sees |
| D-P3-6 | **Adopt the Atlas's D-Unit contract?** | Yes, unit by unit, never as one big rewrite. The lint warns first, and fails only for units that instruct (live). The Founder Office and the Admin units the founder's work uses go first |
| D-P3-7 | **The 165 units approved but never switched on** | Their reviewer (Harsh, for all of Admin's) re-reads each against its current bytes in one sitting, and switches on what still holds. Renewal management, statutory filing and licence and registration go first: `c1` and `c2` stand on them. `obligation_falls_due` is rebound to the situation page before it is switched on (P3-10) |
| D-P3-8 | **The bar before a department judges for a tenant** | **Reliable:** at least 70% of the 19-item checklist, the six tests shown, all four kinds of intelligence suppliable, and its goals' knowledge authored. Below that, **shadow:** it runs and writes receipts, and makes no cards. The Founder Office and Admin's founder units are held to it first |
| D-P3-9 | **Where and until when a rule holds** | Every unit about law, tax, compliance or a programme carries a jurisdiction, a valid-from date and a review-by date. India first. A unit past its review date is shown labelled, and never grounds an authoritative card. A tenant elsewhere is told which local knowledge is missing |
| D-P3-10 | **Departments beyond Admin** | Sales and Support stay off for founder tenants (a recorded departure from the base plan's contents) and go live per tenant only after passing D-P3-8's bar in shadow. New domains, in this order, each authored before it is sold: Finance (cash, invoicing and collections, spend approval) → People and hiring → Projects → Marketing and Product → Engineering, Legal and Operations. Admin's finance administration group stays in Admin |
| D-P3-11 | **Where the ideal's situations live** | Where its traces place them. Wave gone silent, conditional deferral and information conflict under investor relations, and application deadline under programme applications: all `founder_office.sit.*`, per D-P3-5. Delivery failure under Admin's inbox and correspondence. The ideal's other shapes become **qualifiers** on existing situations rather than new ids: answered but not the question asked (`reply_owed`), a late follow-up (`meeting_without_follow_through`), a promise by them (`promise_past_its_date`), our decision (`decision_waiting_on_a_person`). The wave gone silent narrows Admin's campaign going quiet instead of duplicating it |
| D-P3-12 | **Re-home Admin into the Atlas's 17 expertise areas?** | Yes, after the founder units are done (the Atlas says depth before breadth). A mechanical move that changes no content, with ids kept stable through aliases (P3-22) |
| D-P3-13 | **Learning across companies** | Only from tenants that opt in. A cross-company review item carries counts, unit ids and redacted structure only: no names, quotes, amounts, addresses or tenant ids. The shared packs stay identical for every tenant |
| D-P3-14 | **Prospect outreach for a founder** | A small "design-partner outreach" capability in the Founder Office, rather than switching on Sales for founders. It covers `s2` (a prospect wave with one reply) |

## The plan at a glance

| Step | What | Builds 07 | Needs | Model cost |
|---|---|---|---|---|
| P3-0 | Make Plane D measurable: one baseline report | §11, §15 | — | $0 |
| P3-1 | One build: the vocabulary, the unit graph, the index, per-domain packs; selection stages 2 to 9 | §1.1, §3, §4.0, §4.1 | — | $0 |
| P3-2 | Show it whole: the bridge renders the package | §5 | P3-1, P3-7 | $0 |
| P3-3 | Fill the founder's missing kinds of work | §2.1, §2.5, §2.6, §13 | D-P3-4, P3-10 | ≈$4 (drafting with sources) |
| P3-4 | Your review | §6.1, §6.3 | D-P3-3 | $0 |
| P3-5 | Fix the two known wrong items | §7 | — | $0 |
| P3-6 | A test for every unit | §7 | P3-1, P4-5 | $0 in CI (recorded judgments); ≈$0.50 per live re-judge of the acceptance set |
| P3-7 | Join the compiler to the model's path; the package contract | §0c, §4.0, §4.2, §4.4, §6.1 | P3-1, P2-15 | $0 |
| P3-8 | Choose knowledge without an accepted brief line | §4.1 | P2's `kind` field | $0 |
| P3-9 | Read every playbook, staged or not | §5 | P3-2 | $0 |
| P3-10 | Carry the ideal's knowledge into the corpus | §2.1, §2.2, §3.2 | D-P3-11 | ≈$1 |
| P3-11 | The D-Unit contract: every field, the lint, the vocabulary's writers | §1.3, §3.2, §14 | D-P3-6 | ≈$2 (Founder Office and Admin's founder units) |
| P3-12 | Admit every kind of unit; one act approves and switches on | §6.1 | D-P3-7 | $0 |
| P3-13 | Versions, pinning, object storage, shadow and rollback | §3.1, §8 | P3-1, P3-6 | ≈$0.50 per shadow comparison |
| P3-14 | Maturity score, the six tests and the four kinds of intelligence | §1.2, §6.2, §7 | P3-6, P3-11 | $0 |
| P3-15 | Measure each unit's use; the gap backlog | §11 | P3-7, P4-5 | $0 |
| P3-16 | The brains and the person's preferences reach the package | §4.3, §10 | P2-20, P2-0 | $0 |
| P3-17 | Entitlement, activation by kind of customer; live, shadow or off | §9 | D-P3-5, D-P3-8 | $0 |
| P3-18 | Learning reaches Plane D only as review items | §12 | P3-15, L6 | $0 |
| P3-19 | Where and until when a rule holds | §2.4 | D-P3-9, P3-11 | $0 |
| P3-20 | The data behind the Expertise and Brain pages | §1.1, §9, §11 | P3-15 | $0 |
| P3-21 | Each new department proves itself in shadow | §2.3, §9 | P3-14, P3-17 | ≈$1 per department per shadow week |
| P3-22 | Re-home Admin into the Atlas's 17 expertise areas | §1.1 | D-P3-12, P3-3 | $0 |
| P3-23 | Author the next department, in D-P3-10's order | §2.3, §13 | D-P3-10, P3-11, P3-14 | ≈$3 per department (drafting with sources) |

---

## The steps

### P3-0 · Make Plane D measurable
- **What:** one command, pointed at the corpus and at any build (the notebook, the local copy, or production read-only), prints:
  - the corpus: units by kind, live, half-state and unreviewed; capabilities admissible; fact paths named by no unit;
  - coverage: the share of judged situations with at least one **reviewed** unit behind them, and with any unit at all; the uncovered kinds, stages and events;
  - for each in-copy ideal card: the units the compiler selected, the units the judgment cited, and the units 07 §2.2 says it needs;
  - expertise tokens per judgment (mean and p95), units cut, the cache share, and package build time (p50, p95);
  - each guard D-1 to D-26 as built or not built; CI fails if a guard listed in 07 §15 has no test.
- **Test:** on today's copy it prints the numbers in [01](01-WHATS-EXACTLY-THERE.md): 0 of 138 judgments with expertise, 165 units in the half-state, 68 of 141 paths named by no unit.
- **Done when:** every other step writes this report's numbers before and after in [08-LOG](../08-LOG.md).
- **Size:** S.

### P3-1 · One build: the vocabulary, the graph, the index, the packs
- **What** (07 §3, §4.0, §4.1), reusing `packs/compiler/` (the eight components) rather than building a second selector:
  - **the vocabulary** gains closed lists: kinds of work, stages per kind (07 §2.5), events (from the 20 cards: acceptance or selection letters, a send that restates a figure to many, a bounce, an application submitted or missed, an invitation …), qualifiers per situation type, categories, party kinds with their clusters, the allowed kinds of work per party kind (P2's A-9) and node types. `KIND_CAPABILITY` is deleted;
  - **one build command:** validate the schema and every reference; compile the unit graph (a dangling edge fails the build); build the indexes; hash; admit; write **one pack per domain** and a cross-domain index with its own hash;
  - **the index** by kind, stage, event, qualifier and category, across all domains, with the Plane R patterns beside it (`plane = R`, P4-1);
  - **selection stages 2 to 9:** routing by the index; conditions evaluated with the predicate grammar (a failing `not_when` goes to `skipped`; an unknown fact says what it needs); expansion over typed edges, at most 2 hops, each unit tagged `via`; cases, advisory, at most 4; the caps (6 capabilities, 40 units, 12 patterns, 4 cases), with every cut recorded by stage; several situation types per page; aspects of shared objects.
- **Guards:** D-16 (no corpus-wide search), D-17 (no domain noun or kind map in code).
- **Test:** for each in-copy ideal card, the index returns the units 07 §2.2 lists and no unit from a domain that is off. For example:
  - `c2` → renewal management;
  - `b2`, `i3` → follow-up coordination, plus "before an investor call";
  - `c1` → statutory filing, licence and registration, and the Founder Office's registrations;
  - `i1` → "investors do not chase", "a pass is a date, not a verdict", and the conditional deferral;
  - `s1` → both situation types' units; `i2` → the `answered_not_the_question` units;
  - "silence reads by stage" is skipped, with its reason, when the move is ours; a rule that needs another kind of work, or the other side's turn, is skipped with `applies_when failed`;
  - each combinator (`all`, `any`, `not`) returns true, false and unknown correctly, including with unknown inputs;
  - a founder tenant's index returns the eight categories, each with its note, and a default category for each capability of 07 §2.1 (investor relations → investment; programme applications → funding and programmes; introductions → business and network; registrations and recognition → process and compliance; offers and joining → hiring); a situation or goal naming another category is refused by P2's check;
  - for each of the six replay days (a review held, intro offers, an application deadline, an acceptance letter, a new-figure broadcast, a renewal), the index returns the event-keyed units; the figure broadcast selects the one-number units;
  - a renewal package pulls the spend-approval unit through `requires`;
  - when the wave gone silent holds, Admin's campaign going quiet is absent from the units and listed in `skipped` as narrowed by it; when it does not hold, campaign going quiet stays.
- **Done when:** all 17 in-copy ideal cards get the right units, no wrong domain's unit, and the same commit builds the same hashes twice.
- **Size:** L.

### P3-2 · Show it whole: the bridge
- **What:** one renderer, `packs/compiler/expertise_view.py` (07 §5), used by the product's L2 and expert paths and by the notebook. It renders the package:
  - stages with their typical durations (with unit and source), "quiet means", "ends when", the stop rule and the escalation condition (when, and to which role); the expected states and the time model's dates;
  - **every step of every move**, with its actor, the move's stop rule and escalation, and the options with each one's benefit, failure mode and what it gives up;
  - **every rule with its conditions** (applies when, not when, with their results), counter-patterns, rival frames and failure modes;
  - the outcome definition whole (`done_when`, its verifying evidence, the window, what follows if not, the success signal, what doing nothing costs) and the consequences, the authority boundary and the questions;
  - cases in their own block, labelled "a similar past episode, advisory";
  - when two selected units pull opposite ways;
  - the four brains as four labelled blocks, and the person's confirmed preferences;
  - review labels and the ids the model must cite;
  - a size budget (start: 6,000 tokens), where every cut is counted, never silent;
  - the coverage state: with `none`, "No authored knowledge for <kind>, <stage>, <event>", and no recommendation.
- **Guards:** D-1 to D-4, D-14 (with P3-7), D-26.
- **Test:**
  - the investor dossier contains "write the same day", "it reads their quiet, never ours", the success signal and the cost of doing nothing; a staged file shows its stage's stop rule and escalation; an application file shows its `done_when` event and its verifying evidence;
  - a case renders in its own block with the advisory label, and never inside the evidence list;
  - every non-empty rendered field of the package appears in the bridge text (D-14);
  - a situation with no matching unit says so, by kind, stage and event, rather than showing nothing;
  - no rejected unit appears; every unreviewed one is labelled.
- **Done when:** on re-judging, `i3` comes back as "send the follow-up" and `i2` as "answer the question", or each has a stated reason why not. This also needs P4-2's precedence. The old renderers (`playbook_reader`'s claims, the dossier's playbook block, `nb/common.playbook_text`) are deleted.
- **Size:** M.

### P3-3 · Fill the founder's missing kinds of work
- **What:** author, in the same shape as investor relations (07 §2.1, §2.5):
  - **external meetings, introductions, registrations and recognition, offers and joining, events and invitations, partners, design-partner outreach,** and the founder side of **renewals**;
  - for each: stages with sourced typical durations, quiet means, a stop rule and an escalation condition; moves with their steps and actor roles; options and an exit; rules of thumb with their checkable conditions and counter-patterns; outcome definitions; expected states;
  - **stop rules and options for the existing playbooks too:** the investor and programme playbooks, and Admin's follow-up and renewal units;
  - **the stage ladders** of 07 §2.5 (P2 §4.10 mirrors them), including the investor stage `reconsideration` and the application stages `started` and `incomplete`;
  - **the first tool-knowledge and case units** (07 §2.6);
  - **the stage renames** to the ladder words (07 §2.5), and options with benefit and failure mode, first for the renewal, application and reconsideration units.

  Re-use Admin's approved units wherever they already say it. AI drafts each line with its source; nothing is invented. A line with no source is marked "practitioner judgement, unverified".
- **Test:** each new unit has its cases (P3-6), including at least one where it must speak and one where it must stay silent.
- **Done when:** the share of the notebook's situations with expertise behind them rises from 29% to **at least 85%**, and `b1`, `b3`, `f3`, `f4`, `h1` and `s2` are re-judged as the ideal calls them (`s2` citing "Triage a silent prospect wave" and "A tailored proposal earns one second note", and not "Silence reads by stage").
- **Size:** L (authoring), S (code).

### P3-4 · Your review
- **What:** a review sheet per capability, as a local page or a pull request. Each line shows its source, its cases and your three buttons (accept, edit, reject), and asks whether it is knowledge or a way of thinking (07 §0 rule 11). Your acceptance records your name, the date and the content hash, and switches the unit on (D-P3-3). Rejected lines are never shown to the model again. An edit lands with the case that would have caught the problem.
- **Done when:** the Founder Office is reviewed, and the Admin units the founder's work uses have been re-read and switched on by their reviewer (D-P3-7).
- **Size:** S (code), and your sittings.

### P3-5 · Fix the two known wrong items
- **What:** narrow `money-owed-either-way` to real money owed, and make `dependency-stated` keep its quote. Each fix gets a case from the 4 Oct live cards that fails before and passes after.
- **Done when:** both cases pass, and no false "payment obligation" card appears on the copy.
- **Size:** S.

### P3-6 · A test for every unit
- **What** (07 §7): each unit lists its cases, and each case says which of the six tests it shows:
  - **must cite** (recognition); **must not cite** against a near miss (discrimination); **exception** (a counter-pattern flips the reading); **explanation** (the causal unit is supplied); **outcome** (projection); **decision** (the unknowns that change the decision); **must abstain** (coverage none, or an unknown condition: no recommendation); **negative** (the 4 Oct incubator card);
  - **at least 10 cases per capability the founder uses,** at least 2 of them must-abstain and one per coverage state (full, thin, none), with `i1` first (the film's example); cases follow 07 §7's schema;
  - `f2.must_cite` and `f2.rolling_no_date` (the deadline units must not be cited without a date); `s2.must_cite` and `s2.must_not_cite`;
  - **a second tranche:** a golden case for every Admin situation (34 today);
  - every production fix to a unit lands with its case.

  CI runs selection (P3-1) and the citation check (P4-5) over recorded judgments on every change to the YAML, the compiler or the bridge. The 40 routing cases are kept. Cases refer to the copy by card id and thread id only.
- **Guards:** D-9, D-10.
- **Done when:** every Founder Office unit and every Admin unit the founder's work uses has its cases and they pass; the Admin tranche's count is in the P3-0 report. A change that makes a unit fire where it must not, or stay silent where it must speak, fails the build.
- **Size:** M.

### P3-7 · Join the compiler to the model's path; the package contract
- **What:**
  - **every run L2 makes on a situation** (and every expert review, and every goal judgment through the goal package, 07 §4.4) builds an **ExpertiseRequest** from the situation page (07 §4.0), prints it in its receipt, and gets a package, **with or without a model call**;
  - **the package contract grows** (`contracts/domain_expertise.py`): `producer_version`, `eval_time`, the pack and index hashes, situation types, stage and qualifier, expected states (or `none: <reason>`), time model, counter-patterns and rival frames, questions, evidence requirements, outcome definition, options, reasoning bindings, authority boundary, the person's preferences, the condition result per unit, and `coverage_state`. The check that refuses an empty package is relaxed. `schema_version` is bumped;
  - **visibility:** a package is never wider than its situation's audience; narrower entries are left out and counted;
  - **grounding:** each version's grounding is derived from its `expertise_refs`; P5-1 renders a card with grounding `unreviewed` as an observation;
  - the package is written to `expertise_packages`, and its unit ids, versions and hashes go into the version (`expertise_refs`, P2 §4.7, and the goal version, P2 §6.1);
  - unreviewed units are carried labelled, not dropped (D-P3-2);
  - the compiled lane keeps running as today until each situation type passes the parity gate (P1 §4), then retires per type and per tenant.
- **Guards:** D-5, D-13, D-14, D-15, D-20 (with P5-1).
- **Test:**
  - a run's receipt names its request and its package; replaying it with the same packs, at a later date, gives the same package;
  - the `f1` and `i4` runs, which make no model call, have a package row and unit ids on their receipts;
  - a restricted situation's package holds nothing its reader may not see;
  - grounding: a draft situation citing a reviewed rule gives an observation; a reviewed situation citing only draft units gives an observation; a reviewed situation with a reviewed rule gives a recommendation;
  - coverage: a thin or empty package gives an investigation or an observation, never a recommendation;
  - the renewal fixture yields the four-rung expected-state schedule, and the situation's expectation cites the unit in `expertise_refs`;
  - every package field reaches the rendered text, the receipt or a named reader.
- **Done when:** 100% of the copy's runs carry a package; the 138-judgment replay shows no "No playbook for this file"; the raise goal is judged with the investor stage counts and "only an offer counts".
- **Size:** L.

### P3-8 · Choose knowledge without an accepted brief line
- **What:** the kind of work comes from the situation page: the founder's word first, then an accepted brief line, then L2's own reading, labelled "GeniOS's reading of the kind, not confirmed" (GeniOS-013 [07](../07-DECISIONS.md) D1). This is U13-26, widened from the playbook to the whole package.
- **Guard:** D-11.
- **Test:** a file with no accepted line still gets its package; the label shows when the kind is L2's reading.
- **Done when:** on the copy, the share of judgments with expertise does not depend on accepted brief lines.
- **Size:** S.

### P3-9 · Read every playbook, staged or not
- **What:** the bridge renders a move without stages (Admin's 58 playbooks, 315 steps), and a staged playbook's stages beside it. A capability may have several moves and no spine.
- **Test:** a vendor renewal shows "Renewals as annual re-decisions" with all its steps.
- **Done when:** `c2` is re-judged as the ideal calls it (keep or downgrade, ask for credits).
- **Size:** S.

### P3-10 · Carry the ideal's knowledge into the corpus
- **What** (07 §2.1, §2.2):
  - **5 situations,** each with its L2 situation type made live in the vocabulary before the situation is switched on (D-23): conditional deferral, wave gone silent (narrowing Admin's campaign going quiet, with qualifiers raise, update and prospect), information conflict, application deadline (dated or rolling), delivery failure;
  - **the qualifiers,** each `{id, applies_when, replaces_base}` (07 §1.3): `answered_not_the_question` (reply owed, `i2`: our latest reply exists, their ask named a specific item, the reply lacks it; judged by L2, checked by P4-5); `late` (a meeting without follow-through, `i3`, `b2`); `theirs` (a promise past its date, `f3`); `ours` (a decision waiting on a person, `b1`); `renewal` and `registration_status` (`c2`, `c1`);
  - **the outcome definitions:** an application (confirmation mail → `submitted`; none by the deadline → `missed`), a programme (acceptance letter → reached, the founder confirms) and a renewal (a decision recorded, or the date passed);
  - **`obligation_falls_due` rebound** to the situation page's dates, given its L2 type, and routable;
  - **new rules:** one number, everywhere (a figure names its basis and date; only a billing record proves it; declaring the true figure is the founder's); investors compare updates; prepare one number, one story, one ask; a dormant thread reopens with news (any kind of work); a message that bounced was never received (general; the complaint form under registrations); the real deadline is the notice date; a reviewer's favour gets one nudge;
  - **rules lifted out** of the units that hold them today: a warm intro beats a cold application; answer the question that was asked; an update must carry a new fact (with its counter-pattern); startup recognition gates the seed fund and the tax holiday (`jurisdiction: IN`);
  - **counter-pattern on "investors do not chase":** one update with a new checkable fact, after a written invitation to send news, is not chasing;
  - **moves:** pick the number billing proves; triage a silent update wave; chase a promised introduction; escalate a portal complaint; re-send to a working address; check usage before the notice date; ask for credits before renewing; the conditional deferral's two branches; follow an application's finish-by-reuse and withdraw steps.
- **Test:** P3-1's test finds each of them for its card; stage 5 returns `held` for the qualifiers of `i2`, `i3`, `b2`, `f3` and `b1`; the must-not-cite cases hold (`p1` restatement; `i4` raise-wave move; `b3` "you owe them").
- **Done when:** `p1`, `f2`, `i1`, `i2`, `i4`, `i5`, `s1`, `c1` and `c2` are re-judged as the ideal calls them, each citing these units.
- **Size:** M (authoring).

### P3-11 · The D-Unit contract
- **What** (07 §1.3), unit by unit (D-P3-6):
  - **every field of the contract,** each from its source in today's files where one exists and with its reader (07 §1.3's "Read by"): `path`, `kind`, `owner`, `display_path` and the situations' display aliases (the Founder Office first, its registrations shown under "Admin › Compliance & governance"), `category`, checkable `applies_when` and `not_when` (migrating today's `when_to_use.conditions`), `counter_patterns`, `rival_frames`, `salience`, `questions`, `facts_required`, `derivation` (tool ids from P4-3's gateway), `time_model`, `expected_state`, `stages` with stop rules and escalation, `consequences`, `moves` with actor roles, `options` and `exit`, `evidence_requirements`, `outcome_definition`, `authority_boundary` (from the new `_schema/authority_actions.yaml`), `relationships` (with `contradicts`), `reasoning_bindings`, `qualifiers`, `specialises`, `aspect`, `jurisdiction`, `valid_from`, `review_by`, `learnable`, `provenance`, `evaluation_cases`; the corpus's `variants`, `metrics` and `limits` mapped;
  - **each domain's** `display_name`, `categories` (with notes), `unlocks` and `authoring_state`, and a `coming_next` stub for each department of 07 §2.3 with no corpus;
  - **the vocabulary's path families,** each with its writer: `situation.*`, `loops.*`, `coverage.*`, `org.*` (with the working week, holidays and time zone), `behavior.*`, `adaptive.*`, `persona.*`. Admin's `document.*` and `derived.history.*` get a consumer or are retired;
  - **`_tools/validate.py` lints** every field: a warning first, an error for any live unit. Every `facts_required` path must have a writer. An absence unit names its coverage condition. A number with no derivation is refused unless it is a labelled prior. Durations say working or calendar days.
- **Guards:** D-6, D-7, D-8 (no customer data, over the corpus and its cases, with the public-bodies list), D-21 (authority), D-22 (tool names only in tool knowledge). The D-8 lint is first run on today's Founder Office corpus: every hit is listed, and cleared or allowlisted as a sourced public body or term.
- **Test:** a unit missing `not_when` with no stated reason fails the lint once it is live; a unit naming a path nothing writes cannot be admitted; a "two working days" rule from a Friday is due on Tuesday; a seeded person name and a seeded address fail D-8; a unit whose `human_only` list omits send, or a move step with an agent performing submit, fails D-21, and every boundary word maps to an L4 action class; every existing file maps to exactly one kind; a field with no reader fails D-14.
- **Done when:** every Founder Office unit and every Admin unit the founder's work uses carries the contract; unconsumed Admin paths are 0.
- **Size:** L.

### P3-12 · Admit every kind of unit
- **What** (07 §6.1): every unit carries an accepted content hash, as capabilities do today. The resolver gates every kind: a live unit needs `stable`, approval, a named reviewer and a matching hash. The review tool's one act sets them together. A situation with a pending L2 type cannot be `stable`. The daily health row lists any unit approved but not live, with its reviewer named.
- **Guards:** D-12, D-23.
- **Test:** editing a live unit's bytes without a new review makes it unreviewed, and it is labelled at once.
- **Done when:** the half-state count is 0 and stays 0.
- **Size:** S.

### P3-13 · Versions, pinning, object storage, shadow and rollback
- **What** (07 §3.1, §8):
  - every unit has a semver and every pack a content hash; every run records the pack hashes, the index hash and the unit versions it used;
  - the packs are written to object storage named by hash, loaded by hash on replay, and kept while any retained judgment cites them. The build is reproducible. Once this is in place, no YAML is read after a process starts;
  - P2's fingerprint uses the versions of the units the last judgment cited, not the pack hash;
  - a new pack runs in shadow on the acceptance set and the golden cases beside the live one, and goes live only when it is at least as good on must-cite, must-not-cite, must-abstain and the ideal cards; a change to the caps needs the same run;
  - the pointer per tenant per domain records the hash, `activated_at` and `activated_by`; L4's input gate reads it; rollback moves it back, logged.
- **Guard:** D-18.
- **Done when:** a deliberately worse pack is refused by the shadow comparison; a rollback restores the previous answers on replay; a replay after a new deploy loads the old packs by hash; a deploy with an unrelated unit change re-judges nothing.
- **Size:** M.

### P3-14 · Maturity score, the six tests and the four kinds of intelligence
- **What** (07 §6.2, §1.2, §7): `_tools/` computes each capability's score on the 19-item checklist, item by item from the field or case that shows it (an item with no evidence scores 0). It shows which of the six tests has a passing case, and which kinds of intelligence (reactive, proactive, predictive, prescriptive) the capability can supply. At Reliable, the frame dimension of the confidence vector (P2 07 §9.4) stays at medium or below for a judgment whose frame rests on the capability, and that judgment never grounds an authoritative card (P4-3's frame calculator reads the maturity level; P5-1's lane enforces it).
- **Test:** fixtures score as 07 §6.2's rule says, item by item, over each item's "Counted over": a full capability scores 1 on every item; a one-unit capability scores what its one unit carries; one counter-pattern among twenty patterns scores item 6 at 0 (one in twenty, rounded down to a quarter); a judgment resting only on a Reliable capability has its frame at medium or below and cannot ground an authoritative card.
- **Done when:** every capability shows its level and its missing items on the review queue, and the activation of a domain checks it (D-P3-8).
- **Size:** S.

### P3-15 · Measure each unit's use; the gap backlog
- **What** (07 §11): `expertise_unit_stats` per unit, per week, per tenant: selected, cited, conditions failed (P4-5), cut by stage, the founder's verdicts on the cards resting on it, and outcomes when its advice was followed. The gap backlog from every "No authored knowledge" line, joined to `deferrals.yaml`. The uncovered report. Expertise tokens and build time. Review throughput (reviewed, case-backed units per week; minutes per unit). A unit never selected for 90 days, or always contradicted, goes to review.
- **Done when:** the report shows coverage against the 85% target, lists the units that earn nothing and the top gaps, and feeds the authoring order.
- **Size:** M.

### P3-16 · The brains and the person's preferences reach the package
- **What** (07 §4.3, §10): units name brain paths in `facts_required`; the compiler's existing readers fill them from the brains P2 stores (P2 §8). Every brain entry carries its class; the compiler resolves brain against brain, and Plane R (P4-2) resolves a unit against a brain entry, in the Atlas's order. An observed-only Behaviour entry adapts a unit as a labelled prior. The person's confirmed preferences (`persona.*`) reach the package; a unit never stores one.
- **Guard:** D-19.
- **Test:** an investor's usual reply time from the Behaviour brain reaches "silence reads by stage" without editing the unit; an organisation policy overrides a unit; a behaviour entry does not override a law or safety unit; a confirmed text preference changes the "book the call" move's channel.
- **Done when:** the ideal's traces' Organisation, Behaviour and Adaptive entries (for example for `p1`, `i1`, `i4`) appear in the packages on the copy, each in its own labelled block.
- **Size:** S here; the writers are P2-20's and L6's.

### P3-17 · Entitlement, and activation by kind of customer
- **What** (07 §9): `l3_activation` gains the plan (entitled domains), a state (live, shadow, off) within it, the pack pointer, and defaults by kind of customer (`customer_kind` from P2 §3.4, `founder` until confirmed): for a founder, the Founder Office and Admin together (D-P3-5); for a team, each department's domain as it is switched on, after the bar (D-P3-8). The request reads the tenant's mutes and pack configuration at `eval_time`. No row is made by hand.
- **Test:** flipping a row changes the next package's domains in the same sweep; a domain with no row contributes no unit; a muted unit is absent and counted `muted`; a down-ranked unit ranks below unmuted ones; the receipt carries `pack_config_version`.
- **Done when:** a new founder tenant is onboarded with the right rows and no hand step (P1 [06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md)).
- **Size:** S.

### P3-18 · Learning reaches Plane D only as review items
- **What** (07 §12): verdicts are attributed to every unit the card cited and routed by reason and scope (07 §12's table). A Plane D candidate becomes a draft unit diff, opened as a pull request from a bot branch no code merges, after at least 3 independent companies or a reviewer's flag, the privacy lint and a duplicate check. Only opted-in tenants contribute across companies (D-P3-13), with redacted structure only. Mutes are staged; `learnable: false` units are never muted.
- **Guards:** D-24, D-25.
- **Done when:** a test feedback produces a review item on the queue and no corpus write; repeated dismissals leave a compliance unit selected; the shared packs are byte-identical for two tenants; and by reason and scope: "not how we work" for this kind of work adds a Behaviour or Adaptive entry that appears in the next package for that kind, and for how we work an Organisation proposal awaiting the founder; for this thread nothing changes in Plane D; "not relevant" charges a selection defect to every unit the card cited; "bad timing" opens a stage-duration review item; the corpus hash is identical before and after. An item built from three opted-in fixture tenants holds only counts, unit ids and redacted structure, and a tenant that did not opt in adds nothing.
- **Size:** S.

### P3-19 · Where and until when a rule holds
- **What** (07 §2.4): law, tax, compliance and programme units carry `jurisdiction`, `valid_from` and `review_by`. The compiler selects by the tenant's jurisdiction (P2 §3.4). A unit past its review date at `eval_time` is labelled. When a jurisdiction has no local unit for a kind, the package and the bridge say so, and the Expertise data lists the gap.
- **Done when:** the Indian registration and programme units carry them; a test tenant in another jurisdiction gets none of them and is told what is missing.
- **Size:** S.

### P3-20 · The data behind the Expertise and Brain pages
- **What:** the data the ideal's pages show, as one read for P5's pages: per domain, its state, counts, `unlocks` line and `authoring_state`; the areas, capabilities and situations by `display_path`; the capabilities used on the company's mail, the situations recognised and the rules used on its cards, each with its review state; the categories; the four brains with their entries and the person's confirmed preferences; the local-knowledge gaps; and the `domain_requests` a "Request" writes.
- **Test:** the Admin tile's counts equal the sum of the Admin and Founder Office packs (65 capabilities and 36 situations on today's corpus; 67 and 41 after P3-3 and P3-10), each capability under its `display_path`; a founder tenant's package shows one "Admin" pack label and two hashes; every domain (live, off, or a `coming_next` stub) returns its state, counts, `unlocks` line and `authoring_state`; a "Request" writes one `domain_requests` row that appears in the authoring queue.
- **Done when:** the pages' numbers match the P3-0 report.
- **Size:** S here; P5-11 builds the pages.

### P3-21 · Each new department proves itself in shadow
- **What:** a department's domain, authored in D-P3-10's order, runs in shadow for a tenant (P3-17) and is compared with what the team actually did, until it reaches Reliable (D-P3-8). For Finance, a case checks that it judges only the spend-approval aspect of a vendor renewal while Admin keeps the notice window.
- **Done when:** a department goes live for a tenant only with its shadow report and its maturity level on record.
- **Size:** S per department.

### P3-22 · Re-home Admin into the Atlas's 17 expertise areas
- **What** (07 §1.1, D-P3-12): after the founder units, move Admin's 59 capabilities from today's 10 groups into the Atlas's 17 areas. No content changes; ids stay stable through aliases.
- **Done when:** every Admin capability has an area, a skill and an owner, and every test still passes.
- **Size:** S.

### P3-23 · Author the next department
- **What:** in D-P3-10's order (Finance first), run 07 §13's pipeline for that department's first capabilities (07 §2.3), with its named reviewer's sittings: the brief, an AI draft with a source for every line, the lint, the cases, the review, a shadow run. Its domain replaces its `coming_next` stub.
- **Done when:** its `domain.yaml` passes D-7 with no code change, the Expertise data shows it authored, and P3-21 can start its shadow weeks.
- **Size:** L per department.

---

## Order and dependencies

```
P3-0 baseline ─► every step writes its numbers before and after
P3-1 one build (vocabulary, graph, index, packs, stages 2–9) ─► P3-7 join the compiler to the model ─► P3-2 the bridge ─► P3-9 every playbook
          │                                                        └► P3-8 kind without a brief line (U13-26)
          │                                                                  └► (P4-2 precedence, P4-5 citations) ─► re-judge i2, i3
          └► P3-10 the ideal's knowledge ─► P3-3 the founder's missing kinds ─► P3-6 tests
                                                └► re-judge p1, f2, f3, f4, i1, i4, i5, s1, s2, b1, b2, b3, c1, c2, h1
P3-11 D-Unit contract ─► P3-19 jurisdiction;  P3-6 + P3-11 ─► P3-14 maturity ─► P3-21 departments in shadow
D-P3-7 ─► P3-12 admit every kind;  P3-4 your review runs alongside, from now
P3-13 pins, object storage, shadow, rollback (after P3-1, P3-6)
P3-15 measure each unit (after P3-7, P4-5) ─► P3-18 learning as review items ─► P3-20 the pages' data
P3-16 brains (after P2-20);  P3-17 activation (after D-P3-5, D-P3-8);  P3-5 independent;  P3-22 after P3-3
P3-23 next department (after P3-11, P3-14) ─► P3-21 its shadow weeks
```

## How P3 lines up with the 28 Oct plan (GeniOS-013 [03](../03-HOW-IT-GETS-FIXED.md))

| P3 step | 28 Oct units it proves, replaces or corrects |
|---|---|
| P3-8 | U13-26 (the work's kind for the playbook), widened to the whole package |
| P3-2, P3-7 | U13-18 (`l2-dossier.v7`): the dossier's playbook block is replaced by the bridge over the package |
| P3-3, P3-9 | U13-24 (the stop rule instead of a default window): every kind and stage gets its stop rule |
| P3-2 | U13-11 (`l2-judgment.v8`): the judgment cites the printed unit ids |

## Owed by other parts

Plane D needs these from the other parts. Where Plane D has its own side (a field, a test), it is in the steps above.

| What the other part must do | Why Plane D needs it | Part and step |
|---|---|---|
| Hold `customer_kind` and `jurisdiction` on the company page, confirmed by the founder (done in P2 07 §3.4) | Default domains; local units | P2-0 |
| Hold approval lead times, critical vendors and subscriptions, and an owner per area on the company page (done in P2 07 §3.4) | Units name them as `org.*` paths; without a writer they cannot be admitted | P2-0, P2-26 |
| Start the Behaviour brain observe-only ("observed, n of m"), and add a demotion rule when later evidence contradicts a promoted entry (done in P2 07 §8) | A unit adapts to an observed entry only as a labelled prior | P2-20 |
| Mirror Plane D's stage ladders (done in P2 07 §4.10); carry `also_types[]` and `qualifier` on the situation (done in P2 07 §4.2); record the goal package's units on goal versions (done in P2 07 §6.1) | Selection by type, stage and qualifier; goal knowledge | P2-14, P2-1 |
| Replace D-P4-2's order with the Atlas's precedence, and resolve a unit against a brain entry by it | One precedence, in one place | P4-2 (done in P4 07 §4) |
| Build each plan from the package's `reasoning_bindings`, and keep only domain-free methods in the pattern library, referring to Plane D units by id (remove the three rules that repeat Plane D's) | One owner per rule (07 §0 rule 11) | P4-1, P4-8 (done in P4 07 §1.4, §1.6, §2.3) |
| Evaluate each selected unit's `derivation` in the tool gateway, printing the result with its tool id and inputs; build `notice_date` and `decision_deadline` | The model never computes a date | P4-3 (done in P4 07 §3.2) |
| Check a proof claim against the unit's `evidence_requirements` | What never counts as proof | P4-5 (done in P4 07 §6.2, RC-6) |
| When the package says `expected_states: none`, a hypothesiser may propose expected states labelled "not authored", which never ground an authoritative card | The Atlas's fallback for missing knowledge | P4-8 (done in P4 07 §13.5) |
| Include the goal package in the goal dossier | Goals reasoned with knowledge | P4-6 (done in P4 07 §9.2) |
| Show what Plane R lists on the Expertise page (units or the pattern library) | The ideal's Expertise page | P4-1 (done in P4 07 §1.8) |
| Render a card with grounding `unreviewed` as an observation; take "done when" and "if you don't" from the outcome definition; take delegation rights from the authority boundary; add "wrong rule" and "missing step" to the feedback menu | Review states and the knowledge reach the card | P5-1, P5-4, P5-6, P5-8 |
| Build the Expertise, Brain and Reasoning-receipts pages on P3-20's data, with the locked domains and "Request" | The ideal's pages | P5-11 |
| Capture the founder's first-screen priorities as Adaptive leases, and confirm `customer_kind` in the onboarding drill | Day-one adaptation; default domains | P1-3, P1-10 |
| Compare each activation row with the packages produced (the switch registry) | A switch must change behaviour | P1 §4 |
| Read the active pack pointer before planning an execution | Execution only from a run under the active pack | L4 (input gate) |
| Read `_schema/authority_actions.yaml` as the one action vocabulary, map `ActionKind` and `EXTERNAL_EFFECT_KINDS` to it, and publish the authority rule table in it; P2's `rightly_founders` reads the package's `human_only` list | One list, so D-21 has a table to agree with | L4 (`contracts/execution.py`), P2-20, P5-8 |
| Record a situation's expectations from the package's `expected_states`, with the unit id; set `if_missed = escalate` and `escalate_to` from a stage's `escalate_when` | Reality compared with an expectation; escalation has a reader | P2 (expectations, P2 07 §4.3), P4-8 (P4's part done in P4 07 §1.4, `r.expected_actual`) |
| Hold a page that cites a Case unit as evidence; check a qualifier judged by L2 (`answered_not_the_question`) against the quoted ask and reply | A case is never proof; a judged qualifier is checked | P4-5 (done in P4 07 §6.2, RC-7, RC-8) |
| Cap the lane at investigation or observation when coverage is `none` or `thin`, and make no recommendation | No recommendation without knowledge | P4-8, P5-1 (P4's part done in P4 07 §7.3, RC-10) |
| The frame calculator reads the capability's maturity level, and keeps the frame at medium or below below Senior-grade; and no judgment resting on a capability below Senior-grade grounds an authoritative card | The maturity cap | P4-3, P5-1 (P4's part done in P4 07 §7.1) |
| Write unit mutes and pack configuration as data, staged | Learning reaches selection only through data | L6 |
