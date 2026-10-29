# P3 · Plane D · 07 · Domain expertise, specified for production

**Written for:** Harsh and the agents Harsh assigns, who build the code; the reviewers of the knowledge (the founder for the Founder Office, Harsh for Admin, and later GeniOS's named domain reviewers). Rohit decides the open questions in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).

**What this file is:** the complete specification of Plane D. It covers:
- what domain knowledge is, unit by unit, and what each unit must say;
- what the corpus must contain for a founder and for each department;
- how it is compiled, selected, adapted to the company, shown to the model, reviewed, tested, versioned and activated per tenant;
- how its use is measured and how it learns.

[08](08-REQUIREMENTS-TRACE.md) traces every requirement from the four references to a section here and a step in 04.

**Sources, in order of authority:**
1. GeniOS-008 `00-ARCHITECTURE.md` and the Design Atlas v2: "L2 · D · Plane D", the storage map and Part IV (Admin), including the D-Unit anatomy, the six tests of proper expertise, the 19-item maturity checklist and the ten mechanisms of seniority.
2. GeniOS-008 `01-RULES.md` and `02-MIGRATION-PLAN.md`.
3. The ideal dashboard's Expertise and Brain pages and every card's trace; the expected outcomes ([10](../10-ACCEPTANCE.md)); the launch film ([09](../09-WHAT-WHY-HOW.md)).

**Status:** a specification. Nothing in it is built.

---

## §0 · Eleven rules Plane D never breaks

1. **It knows; it never reasons, decides or chooses** (Atlas: "Model: never. Never: concludes, reasons or chooses an action").
2. **It is not an answer book.** It never says "renew the vendor". It says what to examine, what normally matters, what could explain the facts, what would prove the explanation wrong, and which moves exist with what each gives up.
3. **Git is the source of truth.** The YAML in `Domain Expertise/` is reviewed by humans and compiled into pinned packs (today when a process starts; in the target at build time, §3.1). No reasoning path reads it raw, and the model never reads YAML.
4. **One meta-schema for every domain.** The hierarchy, the unit contract, provenance, review, admission and the evaluation format are identical for Admin, the Founder Office, Sales, Support and every future domain. Only content differs.
5. **No company facts in Plane D.** Company numbers (approval lead times, reply latencies, this quarter's priority) come from the brains (P2 §8). Every threshold in a unit is a brain path with a labelled default prior, so every unit stays true for every company.
6. **A unit instructs only once a named human has reviewed it.** Unreviewed knowledge may be shown, labelled, and never grounds an authoritative card. Rejected knowledge is never shown.
7. **A rule never travels without its conditions.** Whatever shows a unit to a model shows its "applies when", "not when", counter-patterns and failure modes.
8. **Every package is pinned and replayable.** A run records the pack hashes, every unit version it was given, and the brain snapshot. Plane D reads no clock: time arrives as `eval_time`, so the same run replays with the same knowledge and the same labels.
9. **Knowledge earns its place.** Every unit has cases where it must speak, must stay silent and must abstain, and its use is measured.
10. **Learning never writes here.** L6 may open a review item; only a human edits the corpus.
11. **Plane D holds what a professional knows; Plane R (P4) holds how to think.** No reasoning method lives in a domain file, and no domain-only rule lives in Plane R. Every review sheet asks this question of each line.

## §0b · Plane D in each loop, for every customer

| Loop | What Plane D does | For a new customer |
|---|---|---|
| **Onboard** | The tenant's entitlement and activation rows decide which domains judge (§9). The packs are compiled once per deploy, never per tenant. Every situation judged in either onboarding wave, and every goal, gets a pinned package (§4) | A founder tenant starts with the Founder Office and Admin together. A team adds each department's domain as it is switched on. **No row is ever made by hand** |
| **Evolve** | For every situation L2 judges, with or without a model call, the compiler selects the units that apply from every live domain, by what the situation is and holds (§4). A package is pinned per run. When nothing applies, the run says so and the gap is logged (§11) | The same code and knowledge for every tenant; only the brains (company facts, behaviour, priorities) differ |
| **Act** | A verdict with a knowledge reason is attributed to every unit the card cited, and routed by its reason and scope (§12): a company-specific difference to that company's brains, a knowledge defect to the review queue | Feedback never edits the corpus |
| **Maintain** | Weekly usage per unit, the gap backlog and coverage (§11). Units never selected, always contradicted or past their review date go to the review queue. A new pack runs in shadow against the golden set before it goes live, and is rolled back by a pointer if it is worse (§8) | A new domain goes live for a tenant only after it passes the bar in shadow (§6.2, §9) |

## §0c · The map: what exists, what is adapted, what is built

| Piece | Today | Target | Verdict |
|---|---|---|---|
| The corpus (`Domain Expertise/`: 4 domains, 160 capabilities, 957 units) | Git YAML, one tree, 10 schemas, a closed vocabulary, a validator | The same, with the D-Unit fields (§1.3) added unit by unit | **ADAPT** |
| `_tools/validate.py`, `_tools/admit.py` | Schema and vocabulary checks; capability admission | A lint for every D-Unit field; every kind of unit admitted (§6) | **ADAPT** |
| `_schema/vocabulary.yaml` | 141 fact paths, 51 observation kinds, 41 live L2 situation types and a predicate grammar | Plus closed lists of kinds of work, stages, events, qualifiers, categories and party kinds, and the path families of the situation page and the brains, each with its writer (§3.2) | **ADAPT** |
| `_schema/authority_actions.yaml` | — | The closed list of actions a unit's authority boundary may name, shared with L4 (§1.3) | **BUILD** |
| `_eval/` (40 routing cases) | A kind of work → a playbook, resolve or abstain | Kept. Plus must-cite, must-not-cite, must-abstain, negative and outcome cases per unit (§7) | **ADAPT** |
| `_review/QUEUE.md`, `scripts/dx_review_queue.py` | 15 situations waiting | Every kind of unit, the half-state alarm, a usefulness line per unit, the gap backlog (§6.3, §11) | **ADAPT** |
| `packs/compiler/authoring.py` (`ExpertBrainCatalog`) | Parses the deployed YAML when a process starts | The same, plus the pack files and their hashes written at build (§3.1) | **ADAPT** |
| `packs/compiler/domain_compiler.py` and its eight components | Builds an ExpertisePackage for each rule-born situation: 100 in the first week, all rendered by templates | Builds one for **every run L2 makes on a situation or a goal**, from the request (§4) | **REUSE**, re-pointed |
| `contracts/domain_expertise.py` (`ExpertisePackage`) | Envelope, capabilities, rules and playbooks, objects, evidence, three brains, brain snapshot, what was skipped. Refuses a package with no capability or no object | Plus the lenses of §4.2 and the pack hashes; an empty package is allowed with its reasons (`coverage_state: none`) | **ADAPT** |
| `expertise_packages` (table) | 100 rows in the first week | One row per run, cited by its version (P2 §4.7, `expertise_refs`) | **REUSE** |
| `packs/compiler/capability_resolver.py` (admission) | Capabilities by hash; situations flagged; other kinds only reported | Every kind gated by its review state and hash (§6.1) | **ADAPT** |
| `packs/compiler/brain_resolver.py`, `runtime_brains.py` | Pin the expert snapshot and three brain snapshots; resolve brain-against-brain conflicts; read `learned_brain_entries` (0 rows) | The same readers, over brains P2 §8 and L6 fill; each entry carries its class (§4.3) | **REUSE** |
| `packs/compiler/playbook_reader.py` (with `KIND_CAPABILITY`, a map of kinds of work in code) | One staged playbook per kind, Founder Office only; rules as statement and why | Deleted; the bridge (§5) and the index (§3.1) replace it | **REPLACE** |
| The playbook block of `reason/expert/dossier.py`; `nb/common.playbook_text` | One renderer per path | Replaced by the bridge (§5) | **REPLACE** |
| `packs/compiler/expertise_view.py` (the bridge) | — | One renderer of the package for every model path (§5) | **BUILD** |
| The selection index by kind, stage, event, qualifier and category | — (routing is by the L2 situation type) | Built with the packs (§3.1, §4.1) | **BUILD** |
| The goal package | — | §4.4 | **BUILD** |
| Maturity score; `expertise_unit_stats`; the gap backlog; `domain_requests` | — | §6.2, §11, §9 | **BUILD** |
| `platform/l3_activation` | On or off, per tenant per domain | Plus entitlement by plan, a `shadow` state, defaults by kind of customer, and the pack pointer per domain (§8, §9) | **ADAPT** |

## §1 · The unit of knowledge (the D-Unit)

### 1.1 · The hierarchy: an address, with relationships across it

`domain` → `expertise` (area) → `skill` (capability) → `function` → `component` (a lens) → `subcomponent` → **D-Unit** (atomic knowledge).

- **The tree says where a unit lives and who owns it.** Every unit has a `path` whose levels exist, and every capability and skill names an `owner` (a role, never a person's name).
- **The typed edges between units** are what reasoning follows across areas: `relates_to`, `depends_on`, `requires`, `affects`, and `contradicts` (two units that pull opposite ways in some conditions; 158 corpus files already use the word). The corpus's `pattern_ref` maps to `relates_to`.
- **Depth is flexible** (a simple function may skip components), but the meaning of each level never changes.
- **Today's corpus maps onto it without rewriting content:** `domain → group (NN-group) → capability → situations, playbooks, rules of thumb, objects, models and frameworks`. The domain stays the domain, a group is an expertise area, a capability is a skill, and each file is a D-Unit (§13).
- **The Atlas's 17 expertise areas for Admin** replace today's 10 groups after the founder units are done (D-P3-12). It is a mechanical move: no content changes, and ids stay stable through aliases.

**What the founder sees is separate from where a unit lives:**
- **`display_path`** on every capability, and a display alias on every situation id. The Founder Office's investor relations shows as "Admin › Founder office › investor relations"; its registrations and recognition as "Admin › Compliance & governance › registrations and recognition" (D-P3-5). Corpus ids never change for display.
- **Categories:** a tenant-facing domain declares its `categories` (`{id, name, note}`), and every capability and situation declares a default `category`. Admin's eight are the ideal's: investment, funding and programmes, business and network, sales, projects, progress, process and compliance, hiring. P2 checks a situation's and a goal's `category` against this list (P2 §4.2, §6.1).
- **A domain declares** a tenant-facing `display_name` (the Founder Office's is "Admin", so the pack label reads "Admin pack" while the package pins both hashes), `unlocks` (one line on what it would add) and `authoring_state` (`authored` or `coming_next`), for the Expertise page's locked cards (§9). A `coming_next` domain is a stub `domain.yaml` holding only its identity, `display_name`, `unlocks` and `authoring_state`; there is one for each department of §2.3 with no corpus yet.

### 1.2 · The thirteen kinds of unit

| Kind | What it holds | Founder example | Where it lives in the corpus today |
|---|---|---|---|
| Knowledge | A definition, or a fact of the trade | "The real deadline is the notice date, not the expiry" | `objects/`, `models/`, a capability's `knowledge.yaml` |
| Experience | What usually happens | The typical duration from a first call to a partner meeting | A staged playbook's typical durations (labelled priors) |
| Pattern | A recognised configuration of facts | "A wave gone silent": the same update to many funds, no replies | `situations/`, with their `matches` predicates |
| Case | A structurally similar past episode, de-identified (advisory only) | A reconsideration that worked after a new milestone | — (**BUILD**, §2.6) |
| Heuristic | A rule of thumb, with its conditions | "Investors do not chase" | `heuristics/`; `rules/` (cross-object rules: `when` → `applies_when`, `exceptions` → `counter_patterns`) |
| Causal | Why something happens | A rejected application's silence is the batch, not a verdict | A rule's "why"; `mental-models/` |
| Exception | When the pattern does not hold | A rolling month-to-month term has no notice window | A rule's "breaks down when"; a playbook's `do_not_use_when` |
| Failure mode | How the knowledge is misused | "Silence reads by stage" used to excuse our own silence | `failure_modes` on rules and playbooks |
| Trade-off | Which objective wins, and what is given up | Speed against a cleaner number | `decision-frameworks/` |
| Resource | What the work needs | The documents a programme asks for after acceptance | A playbook step's `produces` (an object file is Knowledge) |
| Tool knowledge | How a tool or portal behaves (the only kind that may name a vendor or tool) | A government portal's correction workflow | — (inside prose; **BUILD**, §2.6) |
| Action knowledge | A move, with every step | "Before an investor call": six steps, the last being "write the same day" | `playbooks/`: steps with actor, produces and done when |
| Outcome | What "done" means, and how it is verified | An application is done when the confirmation mail is a member | A playbook's `success_signal`, `outcome_window_days`, `do_nothing_consequence` |

Every existing file maps to exactly one kind (a lint, P3-11).

**What each kind of intelligence needs** (the film's four kinds). A capability is Reliable only if it can supply all four (§6.2):

| Kind of intelligence | Needs these units |
|---|---|
| **Reactive** (something happened) | Patterns, with their counter-patterns and rival frames |
| **Proactive** (something should have happened) | Expected states, stages with durations, stop rules |
| **Predictive** (what will follow) | Causal units and consequences |
| **Prescriptive** (what to do) | Action knowledge with options and trade-offs, the authority boundary, the outcome definition |

### 1.3 · The unit contract

Every unit, of every kind, has these fields. "Source today" says where a migrated unit takes the value from (§13).

| Field | Meaning | Source today | Read by |
|---|---|---|---|
| `id`, `path`, `kind` | Stable id; its address in the hierarchy (§1.1); one of the 13 kinds | `identity.id`; the folder tree; the folder (`heuristics/` → heuristic …) | The index (§3.1); receipts; the lint |
| `version` | Semver. Content changes bump it | `identity.version` | Pinning and replay (§8) |
| `display_path`, `category` | For a capability: the path the founder sees, and its default category; for a situation: its display alias and default category (§1.1) | — | The Expertise data (P3-20); P2's category check |
| `statement` / `definition` | What it says, in plain words. A figure names its basis and date (a monthly or yearly figure, as of when) | `heuristic.statement`, `purpose.statement` | The bridge (§5) |
| `why`, `sources` | Why it is true, with its sources (practitioner, literature, regulation), each dated | `heuristic.why`, `references` | The bridge; the review sheet |
| `applies_when`, `not_when` | **Conditions code can check**, written in the vocabulary's predicate grammar over registered fact paths (§3.2), beside the prose. The grammar's forms (`exists`, `absent`, `has_obs`, `no_obs`, path–operator–value …) gain three combinators, `all`, `any` and `not`, each three-valued: `all` is false if one item is false, true only if all are true, otherwise unknown; `any` is true if one item is true, false only if all are false, otherwise unknown. An unknown fact evaluates to unknown, never to true or false | Prose: `heuristic.applies_when`, `breaks_down_when`. Checkable today: `when_to_use.conditions` on 50 of 291 rules and 78 of 238 playbooks; `do_not_use_when` | Stage 5 (§4.1); the bridge, with each result |
| `counter_patterns` | `[{description, look_for (the evidence), effect}]`: what would show the pattern does not hold here ("a signed order form exists") | `rules/` `exceptions` (partly) | Stage 5; the bridge; P4's frame |
| `rival_frames` | For a pattern: `[{frame, indicators, do_not_confuse_with}]`, what else could explain the facts | — | The bridge; P4's frame and alternatives |
| `failure_modes` | How it is misused ("it reads their quiet, never ours") | `failure_modes` | The bridge |
| `salience` | What normally makes this matter, with the facts that show it (irreversible, a shrinking window, no owner, conflicting sources) | — | The bridge; P4 and P5's ranking |
| `questions` | A question bank by concern (facts, ownership, timing, dependency, exception, outcome), each tied to the fact path or evidence that answers it. Always including "what evidence would show there is no problem" and "what state proves it resolved" | `purpose.answers` (what it answers, not what to ask) | The bridge; P4, which asks the few that change the decision |
| `facts_required` | Registered paths it needs, including brain paths (`org.*`, `behavior.*`, `adaptive.*`, `persona.*`). Every path must have a writer (§3.2) | `heuristic.reads` (objects only) | The build's writer check (D-6); stage 5 |
| `derivation` | Any computed value, as a formula **for a tool**: `{tool (an id in P4-3's tool gateway), inputs (paths)}`. A number in a statement or a move with no derivation is refused unless it is marked a labelled prior | — | P4-3's tool gateway |
| `time_model` | The dates this kind of work has, each a derivation: formal deadline, notice date, decision deadline, preparation lead time, recovery window, escalation trigger, verification deadline | — | P4-3, which fills P2's `dates` (P2 §4.2); the bridge |
| `expected_state` | A schedule: `[{state, by (an offset from an anchor event, in working or calendar days), when (criticality), basis (stated, prior, cadence)}]`. For a renewal: review started and owner named by T−90; alternatives by T−60; path chosen by T−30; signed or a contingency by T−15. Offsets read brain paths with a labelled prior, so a company's own lead time replaces the prior | One prose line at most | The bridge; P2's expectations (P2 §4.3), which record the unit that supplied each |
| `stages` | For a staged playbook: `[{id, name, typical (duration, unit: working_days or calendar_days, source), quiet_means, ends_when, done_when, counts_as_progress, stop_rule, escalate_when}]` | Two staged playbooks (14 stages) | The bridge; P2's stage and ladder (§2.5); the goal package (§4.4) |
| `stop_rule` | On a stage or a move: `{clock (what it reads), maximum (days, unit), on_stop (close or one_last_move), reopen_on}` | `stop.dormant_after_days` on the two staged playbooks | The bridge; P2's clock (P2 §4.3, §5.3) |
| `escalate_when` | On a stage or a move: when the work should go to someone more senior, and to which role | — | The bridge; P2's expectation (`if_missed = escalate`, `escalate_to`) |
| `consequences` | What follows if nothing is done, as a short chain, labelled advisory | `do_nothing_consequence` | The bridge ("if nothing is done"); P5's "if you don't" line |
| `moves` | For action knowledge: every step in order, each with `actor_role` (founder, assistant, owner, agent, third party), produces and done when | `steps` (actor: human or agent) | The bridge; P5's steps; L4's plan |
| `options` | For action and trade-off units: `[{move, when, benefit, effort, time, dependencies, risk, reversibility, authority, evidence, failure_mode, gives_up}]`, always including one that keeps options open; and an `exit` (how to drop the work cleanly) | `variants` (partly) | The bridge; P5's alternative line |
| `evidence_requirements` | What counts as proof and what never does: `{required: [{fact, authority (the L3 ladder's names, P2 §2.4), sources (the vocabulary's evidence sources)}], unacceptable_as_proof: [...]}`. The bar may rise with irreversibility (moderate, high, very high) | — | The bridge; P2's EvidenceNeeds; P4-5 |
| `outcome_definition` | What "done" means for this kind of work: `{done_when (event kind, party), evidence, window (days), if_not, success_signal, do_nothing_consequence}` | `success_signal`, `outcome_window_days`, `do_nothing_consequence` | The bridge; P2's `done_when`; P5-4 |
| `authority_boundary` | `{geniOS_may, human_only}`, each a list of words from `_schema/authority_actions.yaml`: draft, remind, prepare, schedule_check, hold_calendar, book, send, pay, sign, submit, accept_offer, declare_company_fact, resend. Each word maps to an L4 action class (`ActionKind`). A send, a payment, a signature, a submission, accepting an offer and declaring what is true about the company's numbers are always `human_only`. **Defaults by kind of work:** investor mail, GeniOS drafts only; company numbers, GeniOS collects and compares only; applications and registrations, the founder submits; offers, the founder accepts | — | The bridge; P5's delegation; L4's task contract; D-21 |
| `relationships` | `relates_to`, `depends_on`, `requires`, `affects`, `contradicts` → unit ids | `contradicts`, `pattern_ref` (partly) | Stage 6 (expansion); the bridge (units that pull opposite ways) |
| `reasoning_bindings` | The Plane R units or patterns it expects (P4) | — | P4-1 and P4-8, to plan the run |
| `qualifiers` | For a situation: its closed list, each `{id, applies_when (checkable, or "judged by L2, checked by P4-5" for a test of meaning), replaces_base}`. When `replaces_base` is true, the situation's own `matches` are not evaluated for that qualifier (`answered_not_the_question`: our latest reply exists, their ask named a specific item, and the reply lacks it) | — | Stage 2 and stage 5; P4-5 |
| `specialises` | For a situation that narrows another (the wave gone silent narrows Admin's campaign going quiet) | — | Stage 5: when the narrower one holds, the general one is left out |
| `pending_l2_types` | For a situation whose L2 type is not live yet. Such a situation cannot be `stable` (§6.1) | `matches.pending_l2_situation_types` | Admission (D-23) |
| `aspect` | For a resource or knowledge unit about a shared object: which aspect it owns (`notice_window`, `owner`, `spend_approval` …) | — | Stage 6 and the shared-object rule (§4.1) |
| `jurisdiction`, `valid_from`, `review_by` | For law, tax, compliance and programme units: where and from when it holds, and when it must be re-reviewed | References' dates (partly) | Stage 1 (selection by jurisdiction); the bridge's labels |
| `learnable` | `false` for safety, legal, compliance and authority units: no mute or dismissal ever down-ranks them (§12) | — | Stage 1 and L6's mutes (D-24) |
| `provenance` | `{created_by: human or ai_drafted, source, basis}` | `metadata.created_by`, `references` | The review sheet; the bridge's labels |
| `review` | `{state, reviewer (a role or a name in the private review record), reviewed_at, content_hash}` (§6) | `identity.status`, `metadata.review_status`, `reviewed_by`; a hash for capabilities only | Admission; the bridge's labels; grounding (§6.1) |
| `maturity` | The capability's checklist score (§6.2), on capabilities | — | Activation (D-P3-8); the confidence cap |
| `evaluation_cases` | Case ids (§7's schema) where it must be cited, must not be cited, must abstain, and outcome cases, each saying which of the six tests it shows | `_eval/` routing cases (40) | CI (P3-6); the maturity score |
| Corpus extras | `variants` (company-size variants) map to `options`; `metrics` map to the capability's measures (§6.2); `limits` map to `not_when` prose | — | The field each maps to (`options`, the capability's measures, `not_when`) |

**What the lint checks:**
- Every field above is present, or explicitly `none` with a reason. A warning first; an error once the unit is live (D-P3-6).
- A pattern or rule of thumb needs a checkable `applies_when` or `not_when`, a non-empty `counter_patterns`, and at least one negative case before it is live.
- A unit whose conclusion is an absence ("no reply", "silence", "nothing arrived") names a coverage condition in `applies_when` (`coverage.<source>.read == full`), because unknown is not zero.
- A `facts_required` path with no writer cannot be admitted.
- A vendor or tool name appears only in a tool-knowledge unit (D-22).
- **No customer data (D-8):** no name, address or figure of a tenant's own people, companies or numbers (matched against fixture parties and the brains, plus patterns for emails, phone numbers and money), and no money amount that is not a dated, sourced public term. Public institutions, regulators and programmes are allowed when listed in `_schema/public_bodies.yaml`, each public figure with its source and date.
- Every field above names who reads it ("Read by"); a field nobody reads is removed (D-14).
- Every file maps to exactly one of the 13 kinds.

### 1.4 · An example: a rule of thumb, whole

```yaml
id: founder_office.heu.investor_relations.silence_reads_by_stage
path: founder_office › fundraising › investor_relations › heuristic
kind: heuristic
version: 1.1.0
statement: Silence after a stage reads according to that stage.
why: The cadence of a fund's process is set by its stage; quiet in diligence differs from quiet after a first call.
applies_when:
  all:
    - { path: situation.kind, op: "=", value: investor }
    - { path: situation.whose_move, op: "=", value: them }      # the turn is theirs
    - { exists: situation.stage }
    - { path: coverage.gmail.read, op: "=", value: full }       # silence counts only if the mail was fully read
not_when:
  any:
    - { path: situation.whose_move, op: "=", value: us }        # our silence is never explained by theirs
    - { exists: loops.open_owed_by_us }                          # e.g. a follow-up after a call
counter_patterns:
  - { description: "a written offer to reconsider exists", look_for: "a quote inviting an update", effect: "read as reconsideration, not as silence" }
failure_modes: ["Using it to excuse our own silence. It reads their quiet, never ours."]
salience: "a stage past its typical duration with no reply; a live round"
questions:
  timing: ["How long has it been since their last message, against this stage's typical duration?"]
  ownership: ["Whose move is it, by the newest open loop?"]
  outcome: ["What reply would show the conversation is alive?"]
facts_required: [situation.stage, situation.whose_move, loops.open_owed_by_us, coverage.gmail.read, behavior.reply_days.party]
evidence_requirements:
  required: [{ fact: situation.stage, authority: first_hand, sources: [mail, calendar] }]
  unacceptable_as_proof: [third_party_summary]
authority_boundary: { geniOS_may: [draft, schedule_check], human_only: [send, declare_company_fact] }
relationships: { relates_to: [founder_office.heu.investor_relations.investors_do_not_chase], requires: [founder_office.pb.investor_relations.before_an_investor_call] }
learnable: true
review: { state: reviewed, reviewer: <founder>, reviewed_at: <date>, content_hash: <sha> }
evaluation_cases: [i4.must_cite (recognition), i3.must_not_cite (discrimination), i2.must_not_cite, h1.partial_coverage.must_abstain]
```

## §2 · What the corpus must contain

### 2.1 · For a founder (the Founder Office, plus Admin's founder units)

Ids follow the corpus. The ideal writes every id as `admin.sit.*`, because it shows the Founder Office inside Admin; in the corpus the Founder Office is its own domain, so its new situations are `founder_office.sit.*` and the founder sees them under "Admin › Founder office" (D-P3-5, D-P3-11). **New** = to author; **lifted out** = today only inside another unit, to become a unit of its own; **qualifier** = a new word in an existing situation's closed list (a content edit, so it is re-reviewed).

| Capability (where it lives) | Situations (Plane D ids) | Rules of thumb | Moves (playbooks) | State today |
|---|---|---|---|---|
| Investor relations (Founder Office) | `founder_office.sit.live_investor_relationship`, `founder_office.sit.live_investor_contact`. **New:** `founder_office.sit.conditional_deferral` (related to Admin's `condition_awaiting_review` and `condition_now_satisfied`); `founder_office.sit.wave_gone_silent`, which **specialises** Admin's `campaign_going_quiet`, with qualifiers `raise`, `update` and `prospect`; `founder_office.sit.information_conflict` | Investors do not chase (**new counter-pattern:** one update that carries a new checkable fact, after a written invitation to send news, is not chasing) · Silence reads by stage · Only an offer counts · A pass is a date, not a verdict · Momentum is a parallel process. **New:** One number, everywhere (a figure names its basis and date; only a billing record proves it) · Investors compare updates · **Lifted out:** An update must carry a new fact (counter-pattern: restating the pitch or the same traction is not new) | A warm intro to an investor · Before an investor call (6 steps) · Run an investor conversation (staged; **new stage** `reconsideration`, entered on a written offer to reconsider, with the stop rule "one update with a new checkable fact, then pause until they reply") · The wave gone silent (raise) · Reopen after a pass · The conditional deferral (branches: "send me updates" keeps the monthly update; "reconsider on news" follows the `reconsideration` stage and its stop rule, with "close the loop and re-apply next intake" as its alternative). **New:** Triage a silent update wave (keep the few that matter, one personal line each citing the last real conversation, close the rest with a reason, never re-send the same text) · Pick the number billing proves, and re-draft what cites it | Authored, unreviewed. 3 situations, 3 rules, 2 moves and 1 stage to add; 1 rule to lift out |
| Programme applications (Founder Office) | **New:** `founder_office.sit.application_deadline`, with qualifiers `dated` (a stated deadline) and `rolling` (an incomplete-application reminder; the clock runs from receipt). Uses Admin's `outbound_awaiting_reply` | The deadline is the only fixed point · A rejection carries a reapplication date · A batch is silent until it decides · The portal is the record · A programme is not an investor. **Lifted out:** A warm intro beats a cold application. **New:** A reviewer's favour gets one nudge (an informal review request is usually answered in a few working days; one nudge after that, then wait; a labelled prior) | Follow an application (staged; **new steps:** finish by reusing the closest completed application; withdraw, with the reason recorded; for a rolling programme, the response clock runs from receipt) · Work back from the deadline (dated only) · Prepare for the interview · Read the decision mail · Documents after acceptance. **Outcomes:** an application is done on its confirmation mail (`submitted`) or, with none by the deadline, `missed`; a programme on its acceptance letter (reached: ask the founder to confirm) | Authored, unreviewed. 1 situation and 1 rule to add |
| Introductions (Founder Office) | Uses Admin's `decision_waiting_on_a_person` (**qualifier** `ours`: the founder owes the yes or no), `outbound_awaiting_reply`, and `promise_past_its_date` (**qualifier** `theirs`: a third party promised an introduction) | **New:** A yes or no within two working days (counted in the company's working days) · An introduction made is a promise on both sides · A channel's activity is not progress | **New:** Accept or decline an intro · Book the call · Follow through after the call · Chase a promised introduction (ask the introducer for status, offer a three-line forwardable blurb, set a next check) · Close a stalled intro (once our part is done the move is theirs; close on the stop-rule date; reopen on their mail) | **Stub** |
| External meetings (Founder Office) | Uses Admin's `meeting_ahead`, `meeting_without_follow_through` (**qualifier** `late`: more than 10 days after the meeting, until the stop rule; the move becomes a fresh contact with a new reason, with no apology), `meeting_left_open` | Admin's "The brief is the meeting's first half" and "Momentum decays in days". **New:** Prepare one number, one story, one ask · Every external meeting owes a written next step (`not_when`: a cohort session with no counterparty) | Admin's "One page, the evening before" and "The follow-through relay". **New:** Write the same day after any external call | **Stub**; Admin's units live |
| Registrations and recognition (Founder Office) | Uses Admin's `obligation_falls_due`, **rebound** to the situation page (§3.2), with qualifiers `renewal` and `registration_status` | The Founder Office's "The portal is the record"; Admin's "Late filings compound beyond the fine" and "Lapse gaps are retroactively expensive" (half-state). **Lifted out, India:** Startup recognition gates the seed fund and the tax holiday (`jurisdiction: IN`). **New:** A complaint that bounced was not made (the registration form of the general bounce rule below) | Admin's "Filing calendar worked backwards" and "Licence register with renewal runway" (half-state). **New:** Escalate a portal complaint (the helpline, then the grievance route, with the portal's own steps as tool knowledge, §2.6) | **Stub**; Admin's units in the half-state |
| Offers and joining (Founder Office) | Uses Admin's `outbound_awaiting_reply`, `promise_past_its_date` | **New:** Only a signed acceptance counts · Coverage decides what "no reply" means | **New:** Make an offer · Close an offer · Prepare the first day | **Stub** |
| Events and invitations (Admin's event coordination, re-pointed) | Uses Admin's `date_bound_logistics`, `meeting_ahead` | **New:** An invitation is a decision with a date (attend, decline or ignore, by the RSVP date) · The people met are the event's output | **New:** Decide on an invitation · Follow up with the people met | Admin's event coordination live; founder units to author |
| Partners (Founder Office, **new capability**) | Uses `meeting_without_follow_through`, `outbound_awaiting_reply` | **New:** A partnership is a pilot with a date and an owner on each side · A call is not a partnership until a written next step exists | **New:** Turn a partner call into a written pilot proposal | **Missing** (38 of the notebook's 421 situations) |
| Design-partner outreach (Founder Office, **new capability**, D-P3-14) | Uses `founder_office.sit.wave_gone_silent` (qualifier `prospect`) and the prospect stages of P2 §4.8 | **New:** A tailored proposal earns one second note; a cold list does not · A reply older than the pitch's last change reopens with the new positioning | **New:** Triage a silent prospect wave (reopen the proposal threads with what changed, close the cold list) | **Missing**; Sales stays off for founders |
| Renewal management (Admin) | `admin.sit.vendor_relationship_live`. Uses `obligation_falls_due` (qualifier `renewal`; a card-billed subscription's renewal date is its cancel-by date) | "Vendors price your inertia" (half-state). **New:** The real deadline is the notice date | "Renewals as annual re-decisions" (half-state). **New:** Check usage before the notice date · Ask for credits before renewing. **Outcome:** a decision recorded, or the date passed | Approved, half-state |
| Inbox and correspondence (Admin) | `admin.sit.reply_owed` (**qualifier** `answered_not_the_question`: our reply went back without what was asked), `admin.sit.outbound_awaiting_reply`, `admin.sit.organization_gone_quiet` and five more. **New:** `admin.sit.delivery_failure` | "Response speed is reputation". **Lifted out:** Answer the question that was asked, in the form it was asked (`not_when`: the reply gives what was asked). **New, general:** A message that bounced was never received (its follow-up was not made, no reply can come, and every clock on the thread restarts; `not_when`: a no-reply address) | "Triage to five outcomes". **New:** Re-send to a working address (find the address in other threads, approve, send as `human_only`, mark the dead address) | Live; 1 situation, 1 qualifier and 2 rules to add |
| Commitment tracking, opportunity tracking, approval coordination (Admin) | `promise_past_its_date`, `condition_awaiting_review`, `condition_now_satisfied`, `dormant_commitment_reopenable`, `decision_waiting_on_a_person` | "Forgotten beats broken for damage" · "A satisfied condition has a short half-life" · "Slow approvals teach workarounds". **New, any kind of work:** A dormant thread reopens with news (`not_when`: the other side asked us to stop) | "The executive's promise ledger" · "Reopen with the evidence named" · "Approvals as a fast lane" | Live |

**Every move above gets** at least one alternative or an exit (drop the application; close the loop and re-apply next intake; downgrade the plan), and every stage a stop rule and an escalation condition. The existing investor and programme playbooks and Admin's follow-up and renewal units get them too (P3-3).

### 2.2 · The ideal cards, and the knowledge each one needs

The situation in each row is the one the ideal card's trace names.

| Card | Situation (qualifier) | Units that must be selected and cited | In the corpus today |
|---|---|---|---|
| `p1` | information conflict (investor relations) | One number, everywhere · Investors compare updates · Pick the number billing proves. Must **not** fire on a restatement: an older, lower figure on another basis or date is not a conflict | Situation, rules and move missing |
| `f1` | `meeting_ahead` | The brief is the meeting's first half · One page, the evening before · Prepare one number, one story, one ask | Situation and Admin's units live; the last rule missing |
| `f2` | application deadline (`rolling`) | Follow an application (response clock from receipt; finish by reuse, or withdraw with the reason). "The deadline is the only fixed point" and "Work back from the deadline" apply to the `dated` qualifier only, and must **not** be cited without a date | Rules and moves authored, unreviewed; the situation and the two steps missing |
| `f3` | `promise_past_its_date` (`theirs`) | Forgotten beats broken for damage · A warm intro beats a cold application · An introduction made is a promise on both sides · Chase a promised introduction | Situation and Admin's rule live; the qualifier, the intro units and the move missing |
| `f4` | `outbound_awaiting_reply` (programme applications) | A reviewer's favour gets one nudge; a next check, no card | Situation live; the rule missing |
| `i1` | conditional deferral (stage: `reconsideration`) | The conditional deferral (reconsider-on-news branch) · Reopen after a pass · A pass is a date, not a verdict · Investors do not chase, with its counter-pattern · An update must carry a new fact | Moves and rules authored, unreviewed; the stage, the branch, the counter-pattern and the situation missing; the last rule only inside "the wave gone silent" |
| `i2` | `reply_owed` (`answered_not_the_question`) | Response speed is reputation · Answer the question that was asked | Situation live; the qualifier missing; the second rule only inside a playbook |
| `i3` | `meeting_without_follow_through` (`late`) | Before an investor call, step 6 · Momentum decays in days · The follow-through relay · Silence reads by stage, **not when** the move is ours | All authored, Admin's live; the qualifier missing; the condition is dropped by today's reader |
| `i4` | wave gone silent (`update`) | Triage a silent update wave · Silence reads by stage. Must **not** cite the raise-wave move | Rule authored; the situation, the qualifier and the move missing |
| `i5` | delivery failure (inbox and correspondence) | A message that bounced was never received · Re-send to a working address | All missing |
| `i6` | `reply_owed`, resolved | Response speed is reputation | Live |
| `s1` | `reply_owed` · `dormant_commitment_reopenable` (two types) | Answer the question that was asked · A dormant thread reopens with news · Reopen with the evidence named | Situations live; the first rule only inside a playbook; the second missing |
| `s2` | wave gone silent (`prospect`) | Triage a silent prospect wave · A tailored proposal earns one second note. Must **not** cite "silence reads by stage" | All missing |
| `b1` | `decision_waiting_on_a_person` (`ours`, introductions) | Slow approvals teach workarounds · A yes or no within two working days · Accept or decline an intro | Situation live; the qualifier and the intro units missing |
| `b2` | `meeting_without_follow_through` (`late`) | Momentum decays in days · The follow-through relay · Every external meeting owes a written next step | Situation and Admin's units live; the qualifier and the last rule missing |
| `b3` | `outbound_awaiting_reply` (introductions) | A channel's activity is not progress · Close a stalled intro. Must **not** produce "you owe them" | Situation live; the intro units missing |
| `c1` | `obligation_falls_due` (`registration_status`) | Startup recognition gates the seed fund and the tax holiday · The portal is the record · A complaint that bounced was not made · Escalate a portal complaint | Situation in the half-state and unrouted; recognition only in prose; the rest missing |
| `c2` | `obligation_falls_due` (`renewal`) | Vendors price your inertia · Renewals as annual re-decisions · The real deadline is the notice date · Ask for credits before renewing | Situation, rule and move in the half-state and unrouted; the last two missing |
| `h1` | `outbound_awaiting_reply` (offers and joining) | Only a signed acceptance counts · Coverage decides what "no reply" means | Situation live; hiring a stub |
| `l1` | `outbound_awaiting_reply` (programme applications) | A batch is silent until it decides | Rule authored, unreviewed |

Each ideal trace also names an Organisation, Behaviour or Adaptive entry beside the Expert one (for `p1`: the round size from the brief, the count of updates that restated traction, today's review). Those come from the brains (§4.3), never from the corpus.

### 2.3 · For each department

| Department | Domain | Depth today | First capabilities to author | Reviewer (role) | Bar before it judges for a tenant |
|---|---|---|---|---|---|
| Founder's office | Founder Office | 2 of its kinds authored | §2.1 | The founder | Reliable (§6.2) |
| Admin | Admin | 59 capabilities, 34 situations (30 live) | Re-home into the Atlas's 17 areas (D-P3-12) | Harsh | Reliable |
| Sales | Sales | 46 capabilities, 13 situations (live) | — | GeniOS's sales reviewer | Shadow until it passes the bar |
| Customer support | Customer Support | 49 capabilities, 20 situations (16 draft) | — | GeniOS's support reviewer | Shadow until it passes the bar |
| Finance | — (Admin's finance administration group only) | none as a domain | Cash and runway, invoicing and collections, spend approval (the aspect Admin does not own) | A finance reviewer | Authored as a domain before it is sold |
| People and hiring | Founder Office's offers and joining | stub | Hiring pipeline, onboarding, leave and payroll inputs | A people reviewer | Authored before it is sold |
| Projects | — | none | Delivery commitments, milestones, dependencies | A delivery reviewer | Authored before it is sold |
| Marketing, Product | — | none | Launches, content and campaigns; roadmap and feedback | Named reviewers | Authored before they are sold |
| Engineering, Legal, Operations | — | none | Incidents and releases; contracts and disputes; facilities and suppliers | Named reviewers | Authored before they are sold |

**A department with no corpus** is shown locked on the Expertise page, and its situations are judged with the line "No authored knowledge" (§5). The order beyond the founder's units is D-P3-10's.

### 2.4 · Where and when knowledge holds (localisation)

- **Compliance, registrations, filings, tax and programmes are local.** Each such unit carries `jurisdiction`, `valid_from` and a `review_by` date. Examples include Indian startup recognition, company filings, tax registrations, and incubator and accelerator norms.
- **A tenant's jurisdiction** comes from its company page (P2 §3.4: `jurisdiction`, the country and, where it matters, the state).
- **Two units that differ only by jurisdiction** are separate units. The compiler selects by the tenant's jurisdiction.
- **A unit whose `review_by` has passed** (judged against `eval_time`, never the wall clock) is shown labelled "due for review", and never grounds an authoritative card.
- **When a tenant's jurisdiction has no local unit** for a compliance or programme kind, the package and the bridge say "No local knowledge for <jurisdiction>, <kind>", and the Expertise data lists the gap, so nobody mistakes silence for "no obligation".
- **Example:** "Startup recognition gates the seed fund and the tax holiday" carries `jurisdiction: IN`, a `valid_from`, a `review_by` date and its government sources.

### 2.5 · Stage ladders (owned here; P2 §4.10 mirrors them)

A situation's `stage` is a word from its kind's ladder. Ladders live in the staged playbooks, are compiled into the vocabulary, and are printed to L2, so a stage can only be one of these words. Each stage carries the §1.3 stage fields: typical duration with its unit and source, quiet means, ends when, done when, counts as progress, stop rule and escalation.

| Kind | Ladder | Notes |
|---|---|---|
| Investor | `first_contact` · `first_call` · `partner_meeting` · `diligence` · `term_sheet` · `committed` · `passed` · `reconsideration` · `silent` | `committed` replaces the corpus's ambiguous `closed`; `reconsideration` is entered only on a written offer to reconsider; `silent` after the stage's stop rule. Progress counts conversations, passes and diligence; "only an offer counts" |
| Application | `started` · `incomplete` · `submitted` · `under_review` · `interview` · `accepted` · `rejected` · `withdrawn` · `in_programme` | `started` and `incomplete` cover the ideal's unfinished application; the corpus ladder begins at `submitted` (applied) |
| Introduction | `offered` · `accepted` · `booked` · `held` · `followed_through` · `stalled` · `declined` | Each stage with a sourced typical duration and a stop rule |
| Hiring (offers and joining) | `offered` · `negotiating` · `accepted_signed` · `declined` · `joined` | "Only a signed acceptance counts" |
| Prospect (design-partner outreach) | P2 §4.8's `pursuit_stage`: `pitched` · `replied` · `in_conversation` · `pilot` · `paying` · `silent` · `closed` | Owned by the design-partner outreach capability |

A goal's plan and its progress read the ladder of the goal's kind (§4.4).

**These words are the contract with P2** (P2 07 §4.10 holds the same list). P3-3 renames the existing playbooks' stages to them (`closed` → `committed`; `applied` → `submitted`; `decision` → `accepted` or `rejected`; `onboarding` → `accepted`; `declined` → `rejected`) and adds the missing ones. Admission checks a stage word against the loaded pack.

### 2.6 · The first tool-knowledge and case units

- **Tool knowledge** (the only units that may name a tool or portal): a regulator portal's correction and grievance workflow (`c1`); how a mail system reports a bounce and how to read it (`i5`); a booking page's confirmation and reschedule notices (meetings).
- **Cases** (by id, advisory only, at most 4 per package, never in a card's evidence): a reconsideration that worked after a new milestone; a renewal decided before its notice date; an introduction that stalled and was closed cleanly. A Case unit in the shared corpus is synthetic or from a published source. A tenant's episode may become one only if that tenant opted in, redacted like a cross-company review item (D-25).

## §3 · Compile: from YAML to pinned packs

### 3.1 · The build

**One command** (`_tools/build_pack`), run in CI on every change and at deploy:
1. validate the schema, the contract fields and every reference;
2. compile the unit graph from `relationships`; a dangling edge fails the build;
3. build the indexes;
4. hash and admit;
5. write the packs.

**What it produces:**
- **One pack per domain** (`admin@sha256:…`, `founder_office@sha256:…`), each immutable, and one **cross-domain index** with its own hash. A package pins all of them: `packs: [{domain, hash}]` and `index_hash`. A domain can be released and rolled back on its own (§8).
- **The build is reproducible:** the same commit gives the same hashes and the same packages.
- **Today** the catalog is parsed from the deployed YAML when a process starts, and hashed into an expert snapshot id. **The target** writes the pack files at build into object storage, named by their hashes, so a replay loads the exact packs a run used (§8). Once that is in place, no YAML is read after a process starts (D-18).
- The packs are loaded into in-memory registries and rebuilt on deploy. They are never edited by hand or by a model.

**The indexes:**
- signal type → capability; object → unit; cue → pattern;
- **(kind of work, stage, event, qualifier) → unit**, the one the founder's work needs most;
- category → capability and situation; `display_path` → capability (§1.1);
- the Plane R patterns (P4-1), with `plane = R`, so there is one selector for both planes.

**When a unit fails admission:**
- A capability that fails admission is dropped from judgment, with a receipt.
- A situation or any other unit that fails is flagged. It is shown labelled, and a card resting on it is an observation (§6.1).
- On the model's path, an unreviewed unit is carried labelled rather than dropped (D-P3-2), so the founder's draft knowledge is not lost before its review.
- Today only capabilities are hash-checked; situations are flagged; rules of thumb, playbooks and objects are only reported. The target is a version, a hash, a reviewer, tests, a shadow run and a rollback for every kind (§6, §8).

**Speed:** a package is built at run time by lookups only, with a target of p95 under 100 ms on the copy (measured, §11).

### 3.2 · The vocabulary

`_schema/vocabulary.yaml` is the contract between the knowledge and the running engine. It holds:
- **closed lists** of kinds of work, stages per kind (§2.5), events, qualifiers per situation type, categories, party kinds with their clusters, the table of allowed kinds of work per party kind (P2's law A-9) and node types. These are content: a new domain adds its own with no code or schema change (P2 07 §0);
- **the events the cards need:** a meeting held; a deadline; a renewal or notice date; a rejection; an acceptance or selection letter; a promise past its date; an introduction made or promised; a send that restates a figure to many recipients; a bounce; an application submitted or missed; an invitation;
- **the path families,** each with its named writer, before any unit may name them:
  - `situation.*` (the page: kind, stage, whose move, `dates.*`, expectations): P2 §4.2;
  - `loops.*` (open asks, questions, promises and their owners): P2 §4.4;
  - `coverage.<connector>.read`, with P2 §2.6's values and connector names (`full`, `partial`, `unknown`, `not_connected`; for example `coverage.gmail.read`). A unit whose conclusion is an absence needs `full`: P2 §2.6;
  - `org.*` (including `org.working_week`, `org.holidays`, `org.time_zone`, approval lead times, critical vendors, owners per area, `org.milestones.new_since_last_update`): P2 §3.4, §20.8;
  - `behavior.*`, `adaptive.*`: P2 §8, L6;
  - `persona.*` (the person's confirmed preferences, such as channel and call length): P2 §8 (`preferences`, confirmed only);
- **the predicate grammar** for conditions, transcribed from the engine, plus the three-valued combinators `all`, `any` and `not` (§1.3), added to `predicate_forms`, to `_tools/validate.py` and to the compiler's condition evaluator, each tested with unknown inputs.

**Rules:**
- Every path a unit names must have a writer. A unit naming a path with no writer is not admitted (D-6).
- A path no unit consumes is reported each build. Measured on 29 Oct: 68 of 141 substrate paths are named by no unit (the Atlas counted 61). Admin's `document.*` and `derived.history.*` paths get a consumer or are retired, so unconsumed Admin paths reach 0.
- `obligation_falls_due` waits today for `obligation.*` facts that nothing writes. It is **rebound to the situation page** (`situation.dates.formal_deadline`, `situation.dates.notice_date`, `situation.expectations`), given its L2 situation type, and then becomes routable (P3-10).
- Kinds of work live here, never in code: `KIND_CAPABILITY` is deleted (P3-1, D-17).

## §4 · Select: the Domain Compiler builds an ExpertisePackage

### 4.0 · The ExpertiseRequest

Every run that needs knowledge builds one request, printed in its receipt:

| Field | From |
|---|---|
| `org_id`, `trace_id` | The run |
| `subject` | The situation page id and version, or the goal id and version (§4.4) |
| `kind` (with its basis), `stage`, `events`, `objects`, `open_loops` | The page (P2 §4.2, §4.4) |
| `situation_type`, `also_types[]`, `qualifier` | The page (P2 §4.2) |
| `customer_kind`, `jurisdiction` | The company page (P2 §3.4) |
| `entitled_domains`, `live_domains`, `shadow_domains` | The activation rows (§9) |
| `mutes`, `pack_config_version` | L6's data for the tenant (§12), read at `eval_time` |
| `visibility` | The page's audience (P2 §14) |
| `eval_time` | The run's as-of instant. Plane D reads no clock (D-15) |
| `budget` | The caps of §4.1 stage 9 and the token budget of §5 |

The same request with the same pinned packs gives the same package.

### 4.1 · The nine stages (Atlas L2 · D), mostly lookups

| # | Stage | What it does | Today |
|---|---|---|---|
| 1 | Entitlement | Only domains live for the tenant may judge; other domains contribute facts, never judgment. A muted unit is left out, except a `learnable: false` one | ✅ The resolver takes the tenant's activated domains |
| 2 | Structural routing | Kind, stage, events, qualifier, situation types, signal and entity types and domain hints → candidate capabilities. An index lookup | 🟡 By the L2 situation type only. The index is **BUILD** |
| 3 | Capability gating | Are the capability's required objects present? If not, it is skipped, with a receipt | ✅ Skipped and missing ids are in each package |
| 4 | Object resolution | Required and high-value optional objects | ✅ `object_resolver.py` |
| 5 | Cue and pattern match | Exact features first. Every unit's checkable `applies_when` and `not_when` is evaluated over the page's facts with the vocabulary's grammar. A unit stays only when each `applies_when` is held or unknown and no `not_when` holds; a failing `applies_when` or a holding `not_when` moves it to `skipped` with its reason; an unknown fact shows "condition unknown: needs <path>". A qualifier's own condition is evaluated the same way (when `replaces_base`, instead of the situation's `matches`). When a narrower situation holds, the one it `specialises` is left out. The result per unit is in the package | 🟡 Situations' `matches.when` predicates only |
| 6 | Bounded expansion | Typed edges only, at most 2 hops, inside the unit budget; each unit pulled in is tagged with the edge that brought it (`via`). An investor call pulls meeting follow-through; a vendor renewal pulls the spend approval Finance owns | ⬜ No typed edges between units yet |
| 7 | Cases | Structurally similar episodes, advisory only, at most 4, never cited as evidence | ⬜ |
| 8 | Semantic fallback | Embeddings, gated by domain, capability and object; never a corpus-wide search (D-16). Built only when the trigger fires: the index returns no unit for more than 10% of judged situations whose kind has authored knowledge | ⬜ Not yet needed |
| 9 | Top-K slice | At most 6 capabilities, 40 units, 12 patterns and 4 cases, ranked by match strength. Every cut is written to `skipped` with its stage and reason, and cuts per stage are reported. The numbers change only after a tuning run on the acceptance set (§8) | 🟡 Bounded by the route (2 to 8 capabilities in the first week) |

**Selection is by what the situation is and holds, across every live domain** (D-P3-1): its kind, stage, events, qualifier, objects and loops. It is never by one key from one domain. Several capabilities per situation are normal: an investor call needs investor relations **and** meeting follow-through.

**Several situation types can match one page** (the ideal's `s1`: reply owed and a dormant thread). The compiler takes the union of their units within the budget, and tags each unit with the type that selected it.

**Shared objects split by aspect** (Atlas IV.1): when two live domains own different aspects of one object, each contributes only its own (Admin the notice window and the owner; Finance the spend approval).

**Selection needs no accepted brief line.** The kind of work comes from the situation page (P2 §4.2, `kind` with its basis). A kind that is L2's own reading selects the same knowledge, labelled "GeniOS's reading of the kind, not confirmed" (GeniOS-013 [07](../07-DECISIONS.md) D1).

**Every run builds and pins a package, with or without a model call.** A run that makes no model call (the ideal's `f1`, `i4`) records the same `expertise_refs`, and its card cites its units from the package, not from a model answer.

### 4.2 · The ExpertisePackage (Plane D → L2)

| Field | Meaning | Today |
|---|---|---|
| **Envelope:** `id`, `org_id`, `trace_id`, `visibility`, `schema_version`, `producer_version`, `eval_time` | Kept as today; `producer_version` and `eval_time` added. A new field bumps `schema_version` | 🟡 All but the last two |
| `packs`, `index_hash`, `brain_snapshot`, `request` | Pinned (§3.1, §4.0) | 🟡 The brain snapshot, and an expert snapshot id in place of the pack hashes |
| `situation_types`, `stage`, `qualifier` | What selected the knowledge | ⬜ |
| `capabilities` | Selected | ✅ |
| `units` | Every unit, whole (§1.3), with its review state, version, the type that selected it, `via` for expanded units, and its condition result (held, failed, unknown) | 🟡 `expert_rules` (rules of thumb and playbooks) and `objects`, with versions |
| `expected_states` | The schedule of what should be true by when, or `none: <reason>` so P4 knows nothing authored covers it | ⬜ |
| `time_model` | The dates this work has, as tool derivations (filling P2's `dates`) | ⬜ |
| `patterns`, `exceptions`, `counter_patterns`, `rival_frames` | With the conditions that held, failed or were unknown | 🟡 Situations' predicates; exceptions as prose |
| `questions` | The question bank for the selected units | ⬜ |
| `evidence_requirements` | `{required, unacceptable_as_proof}`. Read by P2's EvidenceNeeds (acceptable and unacceptable sources) and by P4-5 when it checks a proof claim | ⬜ |
| `outcome_definition` | What "done" means and how it is verified, with the success signal, window and cost of doing nothing. P2's `done_when` and P5's done-when line read it first; the model proposes one only where none is authored | 🟡 In playbooks, not a package field |
| `options` | The moves with what each gives up, and the exit | ⬜ |
| `reasoning_bindings` | `{required, conditional}` Plane R units; read by P4-1 and P4-8 to plan the run | ⬜ |
| `authority_boundary` | `{geniOS_may, human_only}`; read by P5's delegation step and L4's task contract | ⬜ |
| `organization_rules`, `behavior_patterns`, `adaptive_preferences`, `persona_preferences` | The company's brains (§4.3), each entry with its class and state | 🟡 The first three exist; all empty |
| `skipped` | Each capability or unit not included, and why: no entitlement, muted, a required object missing, `applies_when` failed, `not_when` held, narrowed by <the situation it specialises>, over budget (with its stage), narrower visibility, rejected, past its review date | ✅ In the package's metadata |
| `coverage_state` | `none`: no unit selected for the kind, stage and event. `thin`: units were selected, but none is reviewed and live, or neither a stage nor an outcome definition is among them. `full`: otherwise (§5) | ⬜ |
| — | **No decision, ever** | ✅ |

**Visibility:** a package is never wider than the situation's audience. A brain entry or unit narrower than that is left out and counted in `skipped` (D-13).

**An empty package is allowed:** `coverage_state: none`, with its `skipped` reasons. Today's contract refuses a package with no capability or object; that check is relaxed (P3-7).

**Every field has a consumer:** the rendered text, the receipt or a named reader. A field nobody reads is removed from the contract (D-14).

### 4.3 · The four brains behind every package

**The precedence when they conflict** (Atlas L2 · D):
1. law and safety;
2. approved organisation policy;
3. an explicit authority decision;
4. an active constraint;
5. domain expertise;
6. observed behaviour;
7. a generic heuristic.

**Who resolves which conflict:**
- Every Organisation, Behaviour and Adaptive entry carries its class: `law_safety`, `policy`, `authority_decision`, `constraint`, `behaviour` or `heuristic`.
- **Brain against brain:** the compiler resolves it, as it does today by conflict key (the permission axis: the Organisation wins; the preference axis: Adaptive over Organisation over Behaviour).
- **A unit against a brain entry:** Plane R (P4-2) resolves it, with this order. An organisation policy overrides a unit; a behaviour entry never overrides a law or safety unit.

**How the brains reach a unit:**
- Units name brain paths in `facts_required`, so a company's own numbers adapt the unit without editing it.
- The brains are stored in P2 (§8 there) and pinned per run.
- A Behaviour entry that is only observed (not yet promoted) adapts a unit as a labelled prior ("observed, 3 of 4"), never as a company rule.
- **Persona** is a profile of the person's confirmed preferences (channel, call length), not a fifth brain. A unit may name `persona.*` paths; it never stores a preference.

### 4.4 · The goal package

A goal is judged with knowledge too (P4-6). Its package is selected by:
- the goal's department and category;
- the kinds, stages and events of its linked situations.

**It returns:**
- the stage ladder of the goal's kind (the plan template, §2.5);
- the outcome definitions of its kinds of work;
- the capability measures (KPIs) for its department;
- the rules that govern the goal's progress (for the raise: "only an offer counts", "investors do not chase", "the deadline is the only fixed point").

It is rendered by the same bridge, within its own budget, and recorded in the goal version's `expertise_refs` (P2 §6.1). It is built in both onboarding waves, and pinned to the deploy's packs.

## §5 · Show it to the model: one bridge, whole and labelled

One module, `packs/compiler/expertise_view.py`, replaces every per-path renderer: the expert dossier's playbook block, `playbook_reader`'s claim list, and the notebook's `common.playbook_text`. It renders the ExpertisePackage (§4.2), so the model sees exactly what the compiler selected, and the judgment cites the package's unit ids.

**What it shows:**
- **every unit whole:** statement, why, `applies_when` and `not_when` with their results (held, failed, unknown), counter-patterns, rival frames, failure modes, salience, evidence requirements;
- **every stage**, with its typical duration (labelled a prior, with its source and its unit), what quiet means, what ends it, its stop rule, and its escalation condition (when, and to which role);
- **the expected states of this work,** each with its offset from the anchor event, its criticality and a prior label, and the time model's dates as tool results;
- **every step of every move**, with its actor, the move's stop rule and escalation, and the options with each one's benefit, failure mode and what it gives up;
- **the outcome definition, whole:** `done_when` (the event and the party), the evidence that verifies it, the window, what follows if not, the success signal and what doing nothing costs, each labelled a prior; and the consequences ("if nothing is done"), labelled advisory;
- **the authority boundary:** what GeniOS may do, and what only a person may do;
- **the questions** that would change the decision;
- **when two selected units pull opposite ways**, it says so, with both ids;
- **the four brains as four labelled blocks,** each entry with its state: Organisation rules (accepted by the founder), Behaviour patterns (n of N, and the window), Adaptive leases (with their expiry), and the person's confirmed preferences. No brain entry is ever rendered as a unit (D-19);
- **cases in their own block,** after the units, each labelled "a similar past episode, advisory" (at most 4), never inside the evidence (D-26);
- **the review state of each unit,** and its id, which the model must cite (P4-5);
- **a size budget, with every cut counted** ("3 more units not shown: …"), never silent. The start budget is 6,000 tokens of expertise per judgment, measured (§11);
- **the coverage state:**
  - `full`: as above;
  - `thin`: the card says the knowledge behind it is thin, and the lane is capped at investigation or observation, as for `none`;
  - `none`: "No authored knowledge for <kind>, <stage>, <event>", said out loud. The lane is capped at investigation or observation, and no recommendation is made (P4-8, P5-1). The gap is logged (§11).

**What it never shows:**
- a rejected unit;
- a unit past its `review_by` without the label;
- raw YAML.

**Where it sits:** in the cached part of the prompt, so the same units repeat cheaply across situations. It reads no clock: labels are judged against `eval_time`.

## §6 · Review and maturity

### 6.1 · The review states

| State | Shown to the model | May ground an authoritative card |
|---|---|---|
| `draft` (AI-drafted, not reviewed) | yes, labelled "not yet reviewed" | no |
| `reviewed` (a named human accepted it; content hash recorded) | yes | if its capability's maturity allows (§6.2) |
| `edited` (the reviewer changed it) | yes, as the edited version | as reviewed |
| `rejected` | **never** | no |
| `due_for_review` (`review_by` passed at `eval_time`) | yes, labelled | no |

**Grounding.** Each judgment's version derives its grounding from the review states in its `expertise_refs` (P2 §4.7). It is `reviewed` only if the situation type, when one matched, is reviewed and live **and** at least one cited unit is reviewed and live; when no situation type matched, one reviewed unit suffices. Otherwise it is `unreviewed`. A card with grounding `unreviewed` is an observation: it describes, and it does not instruct (P5-1, D-20). This is the ideal's "only stable, approved situations instruct L2".

**The rules:**
- **The validator refuses `stable`** without a reviewer and a review date, and a hash matching the current bytes.
- **Only the reviewer's acceptance flips a unit.** A model never decides a review state (D-12).
- **A situation declaring a pending L2 type cannot be `stable`** until that type is live in the vocabulary (D-23). The Atlas found 4 of Admin's 7 draft situations in this trap; P3-10's new situations are checked for it.
- **An edit to a unit lands with the case that would have caught the problem** (§7). The review sheet refuses an edit with no new case.
- **The "approved but not stable" half-state is an alarm.** Daily health lists it, with the reviewer named. On 29 October **165 units** sat in it: 80 rules of thumb, 80 playbooks and 5 situations (Admin alone: 44, 44 and 4).
- **How the states are stored.** Every unit carries what capabilities carry today: `identity.status` (`draft` · `review` · `stable` · `deprecated`), `metadata.review_status`, `metadata.reviewed_by` and `admission.accepted_content_hash`. "Reviewed" means approved, a named reviewer, and a hash of the current bytes. The reviewer's one act sets all of them **and** `stable` together, so the half-state cannot arise again. "Rejected" is `deprecated` with a reason. "Due for review" is computed from `review_by` and `eval_time`.

### 6.2 · Maturity: the 19-item checklist (Atlas IV.3)

Each capability is scored on 19 items. **An item scores 1** when every live unit of the kinds it applies to carries the field and passes the lint (for the case items, when §7's minimums are met); otherwise the share of those units that do, rounded down to a quarter; an item with no evidence scores 0. The score is the sum over the 19 items, as a share. `_tools/` computes it from the files and the cases, and prints each item with its numerator and denominator on the review queue:

| # | Item | Shown by | Counted over |
|---|---|---|---|
| 1 | Typed objects and relationships | `objects.yaml`; `relationships` on its units | The capability (its objects exist) and its live units (relationships) |
| 2 | Object state machines | The vocabulary's object states for its objects | Its objects |
| 3 | Expected-state definitions | `expected_state` on its units | Its Action and Outcome units |
| 4 | Signal and cue mappings | The index entries routing to it | The capability (at least one route) |
| 5 | Managerial patterns | Pattern units | The capability (at least one live Pattern unit) |
| 6 | Counter-patterns and exceptions | `counter_patterns`, `not_when` | Its Pattern and Heuristic units |
| 7 | Temporal models | `stages`, `time_model`, `stop_rule` | Its Action units |
| 8 | Dependency and consequence models | `depends_on`, `requires`, `consequences` | Its Pattern, Causal and Action units |
| 9 | Metrics and thresholds | The capability's measures; thresholds as brain paths | The capability (measures) and its units that state a threshold |
| 10 | Evidence requirements | `evidence_requirements` | Its Pattern, Heuristic and Outcome units |
| 11 | Organisation adaptation points | `org.*` paths in `facts_required` | Its units that state a threshold or a company-specific fact |
| 12 | Behaviour-history bindings | `behavior.*` paths in `facts_required` | Its units that read a cadence, a latency or a pattern |
| 13 | Reasoning-unit bindings | `reasoning_bindings` | Its Pattern and Action units |
| 14 | Available interventions | `moves`, `options` | Its Action units |
| 15 | Authority boundaries | `authority_boundary` | Its Action units |
| 16 | Verification criteria | `outcome_definition` | Its Action and Outcome units |
| 17 | Golden cases | The must-cite count | Each live unit, against §7's minimums |
| 18 | Negative and false-positive cases | The negative and must-not-cite count | Its Pattern and Heuristic units |
| 19 | Outcome metrics | Outcome cases and the usage line (§11) | Its Action and Outcome units |

| Score | Level | What it may do |
|---|---|---|
| below 40% | Draft | Nothing reaches a customer |
| 40–69% | Shadow | Runs silently on real signals, compared with what people actually did |
| 70–89% | Reliable | Cards for design partners, with evidence shown. **Confidence is capped:** the frame dimension of the confidence vector (P2 §9.4) stays at medium or below for a judgment whose frame rests on the capability, and such a judgment never grounds an authoritative card (P4-3's frame calculator reads the maturity level; P5's lane enforces it) |
| 90% and above | Senior-grade | Proven by golden, negative and outcome cases; may ground authoritative cards |

**Reliable also needs:** the six tests shown (§7), all four kinds of intelligence suppliable (§1.2), and, for a department, the knowledge its goals need (§4.4).

### 6.3 · The review session

- **The corpus is shared by every tenant,** so a review is a product act. During the design-partner stage, the founder reviews the Founder Office and Harsh reviews Admin. At scale, GeniOS's named domain reviewers own each domain. A customer never edits the corpus: its "not how we work" goes to its own brains (§10), and becomes a review item only through §12.
- **One sitting per capability** (20–40 minutes).
- **A review sheet** (a page or a pull request) shows each unit with its sources and its cases. The reviewer accepts, edits or rejects each line. The name, the date and the content hash are recorded, and an accepted unit switches to `stable` in the same act (§6.1).
- **Every sheet also asks:** is this what a professional knows, or how to think (§0 rule 11)?
- **The order:** the Founder Office first, then the Admin units the founder's work uses, then each department as it is sold.
- **The queue** (`_review/QUEUE.md`, generated by `scripts/dx_review_queue.py`) lists what waits: units that fire unconditionally first, then by usage and harm (§11).
- **Throughput is measured:** reviewed, case-backed units per week, and review minutes per unit (§11).

## §7 · Tests: knowledge is tested like code

Every unit has `evaluation_cases`. Each case says which of the six tests it shows (`shows`).

| Case kind | Asserts | Shows | Example |
|---|---|---|---|
| **Must cite** | The unit is selected and cited | Recognition | `b2` cites "every external meeting owes a written next step" |
| **Must not cite** | The unit is not used here, against a near miss, and why | Discrimination | `i3` must not cite "silence reads by stage": the move is ours |
| **Exception** | A counter-pattern holds, and the unit's reading flips | Exception awareness | `i1`: a written offer to reconsider makes one update not chasing |
| **Explanation** | The package supplies the causal unit behind the call | Explanation | `l1`: "a batch is silent until it decides" explains the quiet |
| **Outcome** | When the advice is followed, the outcome is what the unit says | Projection | A renewal decided before the notice date leaves no auto-renewal |
| **Decision** | The package names the unknowns that change the decision | Decision usefulness | `p1`: the billing record is the missing proof |
| **Must abstain** | Coverage is `none` or a condition is unknown: no recommendation | (abstention) | `h1`: partial coverage, so "no reply" is not a finding |
| **Negative** | A near miss must not fire | Discrimination | "Money owed either way" must not fire on an incubator's dated commitment (the 4 October wrong card) |
| **Routing** (today's `_eval/` format) | `resolve` to a capability, or `abstain` with its reason | Recognition | `founder.program.reads_its_spine` |

**The case schema:** `{case_id, unit_ids, kind (must_cite, must_not_cite, exception, explanation, outcome, decision, must_abstain, negative, routing), shows, card_id, thread_id, expect (units cited, units not cited, coverage_state), why}`. No free-text field may hold a name, an email address or an amount (the D-8 lint).

**The bar:**
- Every capability the founder uses has **at least 10 cases**, at least 2 of them must-abstain, and one case per coverage state (full, thin, none).
- A pattern or rule of thumb needs a counter-pattern and a negative case before it is live.
- Every Admin situation gets at least one passing golden case (a second tranche, after the founder units).
- **A production fix to a unit lands with a case** that failed before and passes after; card text is never patched instead.
- **Cases refer to the copy by card id and thread id only.** No name, address or amount appears in a case (D-8).

**When the tests run:** CI runs them over recorded judgments on every change to the YAML, the compiler or the bridge.
- A change that makes a unit fire where it must not, or stay silent where it must speak, fails the build.
- Today's 40 routing cases (Admin 9, Support 3, Founder 25, Sales 3) are kept and extended.

## §8 · Versions, pinning, shadow and rollback

- **Every unit has a semver,** and every pack a content hash.
- **Every run records** the pack hashes, the index hash, the versions of the units it was given, and the `brain_snapshot` (P2 §4.7, `expertise_refs`).
- **The packs live in object storage, named by hash.** A replay loads the exact packs by hash. A pack is kept while any retained judgment cites it.
- **Re-judging after a deploy:** P2's fingerprint uses the versions of the units the last judgment cited, not the pack hash. A deploy that changes none of them re-judges nothing. A changed or rejected cited unit re-judges that situation once.
- **A new pack runs in shadow first,** on the golden set and the acceptance set, beside the live one. It goes live only when it is at least as good on must-cite, must-not-cite, must-abstain and the ideal cards. A change to the stage-9 caps needs the same tuning run.
- **The pointer per tenant per domain** records the pack hash, `activated_at` and `activated_by`. L4's input gate reads it: a run older than the active pack is re-checked before anything is executed.
- **Rollback** is the pointer moved back, per tenant and per domain, logged. It changes no stored judgment; the next runs use the old pack.

## §9 · Activation and entitlement per tenant

**Entitlement and state are separate:**
- **The plan sets the entitled domains** (what was bought). A row's state lies within entitlement.
- **The state per tenant per domain:**

| State | Facts captured | Judgment | Example |
|---|---|---|---|
| **Live** | yes | full: situations, decisions, cards | the Founder Office for a founder |
| **Shadow** | yes | receipts only, no cards | Sales until it passes the bar |
| **Off** | only when a live domain needs them | none | Marketing |

- **One activation row per tenant per domain** (`platform/l3_activation`), never a global flag. The row gains the plan, the state and the pack pointer (§8); today it is only on or off.
- **Defaults by kind of customer** (`customer_kind` on the company page, P2 §3.4; `founder` until the founder confirms it):
  - **founder:** the Founder Office and Admin together, shown as Admin; Admin's founder units are selected by the index whichever domain wrote them. Sales and Support are off by default, a recorded departure from the base plan's contents (D-P3-10);
  - **team:** plus each department's domain as it is switched on, after the bar.
- **The switch must change behaviour:** flipping a row changes the next package's domains in the same sweep, and a domain with no row contributes no unit. P1's switch registry compares each row with the packages produced.
- **The old rule packs that do not fit the tenant** (sales and support for a founder) are not active by default (P1 F10).
- **Locked domains:** the Expertise page shows every domain with its state, counts, `unlocks` line and `authoring_state` (`coming_next` when there is no corpus). A "Request" writes `domain_requests(tenant, domain, user, at)`, which feeds the authoring queue and D-P3-10.

## §10 · Company adaptation without polluting the corpus

- **Adaptation points** are `facts_required` paths into the brains:
  - `org.*`: what the company officially requires;
  - `behavior.*`: how it actually operates, counted from its history;
  - `adaptive.*`: what matters now;
  - `persona.*`: the person's confirmed preferences.
- **Every threshold in a unit is an adaptation point** with a labelled default prior, never a constant: a reply window, an approval lead time, a materiality bar that scales with the company's size.
- **Time is local:** durations say whether they count working or calendar days, and derivations take `org.working_week`, `org.holidays` and `org.time_zone`. A two-working-day reply owed from a Friday is due on Tuesday.
- **A company's own practice never edits a unit.** It fills the unit's adaptation points: this company's approval lead time, this investor's usual reply time.
- **When a company's practice contradicts a unit,** the precedence (§4.3) decides at reasoning time. The contradiction is recorded against the unit (§11), and may become a review item (§12).

## §11 · Measurement: does each unit earn its place?

**Per unit, per week, per tenant** (`expertise_unit_stats`: tenant, unit, version, week), built nightly from `expertise_packages` and the judgments' citations:
- times selected; times cited;
- times its conditions failed the check (P4-5);
- times cut by the budget, by stage;
- the founder's verdicts on the cards that rested on it (good, wrong, not how we work);
- outcomes when its advice was followed.

**The gap backlog:** every "No authored knowledge for <kind>, <stage>, <event>" writes a gap row (tenant, kind, stage, event, count, first and last seen, an example id). The weekly report lists the top gaps; they feed the review queue and the authoring order (D-P3-4). `deferrals.yaml` (the named reason a capability has no door) is joined to it.

**Coverage:** the share of judged situations with at least one reviewed unit behind them, and with any unit at all. The target is at least 85% for a founder tenant (today 0% in the product's first week; 29% in the notebook). For a team tenant, the target is set per live department. An **uncovered report** lists the kind, stage and event combinations with their counts, so the rest has a path to authoring.

**Cost and speed:** expertise tokens per judgment (mean and p95), units cut, the cache share, and the cost change against the cap before and after each step. Package build time (p50, p95), against the 100 ms target.

**Throughput of authoring and review:** reviewed, case-backed units per week, and review minutes per unit, against the D-P3-4 order.

**What follows from the counts:**
- A **usefulness line** per unit appears on the review queue.
- A unit **never selected for 90 days,** or **always contradicted,** goes to review.
- A unit that is **cited where its conditions fail** is a P4 defect, not a Plane D one, and is reported there.

## §12 · Learning closes the loop through review only

**Feedback is attributed and routed by its reason and its scope.** Every unit the card cited is charged, with the card as the case:

| Reason (the card's menu) | Scope | Goes to |
|---|---|---|
| Not how we work | This thread | The situation (P2), nothing in Plane D |
| Not how we work | This kind of work | A Behaviour or Adaptive entry for that kind (P2 §8) |
| Not how we work | How we work | An Organisation proposal for the founder to accept (P2 §8) |
| Wrong rule; missing step | any | A Plane D review item |
| Not relevant | any | A selection defect against the cited units (§11) |
| Bad timing | any | The stage-duration prior, as a review item |
| Wrong facts, misread source, stale data, wrong person | any | Not Plane D (P2 and P4) |

**A review item for Plane D** is a draft unit diff: the statement, the why, the proposed `applies_when` and `not_when`, the count of cases that triggered it and the nearest existing unit. The cases themselves stay in each originating tenant's private record and never enter the pull request. It is opened as a pull request from a bot branch that no code path merges.
- It needs at least 3 independent companies, or a named reviewer's flag.
- It passes the privacy lint and a duplicate check.

**Across companies, privacy first:**
- Only tenants that opted in contribute to a cross-company item (D-P3-13).
- Such an item carries only counts, unit ids and redacted structure: no names, quotes, amounts, addresses or tenant ids, and never a case, thread or card id (D-25).
- The shared packs stay byte-identical for every tenant.

**Mutes are data, staged and limited:**
- L6 writes unit mutes and pack configuration as data. The request reads them at `eval_time`, and the configuration version (`pack_config_version`) is pinned in the receipt beside the pack hashes. A unit's mute stage decides what selection does with it:

  | Stage | Effect |
  |---|---|
  | live | as normal |
  | down-ranked | ranked below unmuted units at stage 9, and flagged in the bridge |
  | shadow | selected and recorded in the receipt, not rendered |
  | review | rendered with the label "under review" |
  | muted | left out, and counted in `skipped` as `muted` |

- The pack configuration holds per-unit score offsets and cap overrides within the stage-9 maximums; it is empty until L6 writes one.
- A `learnable: false` unit (safety, legal, compliance, authority) is never muted or down-ranked by dismissals (D-24).

## §13 · Authoring at scale

- **The authoring brief** (`Domain Expertise/_AUTHORING-BRIEF.md`), the book (`_book/`) and the schema (`_schema/`) define how a unit is written.
- **The pipeline for every new unit:**
  1. the brief;
  2. an AI draft with a source for every line (nothing invented; a line with no source is marked "practitioner judgement, unverified");
  3. the lint;
  4. its cases;
  5. a named review;
  6. a shadow run;
  7. live.
- **A new domain needs no code.** It needs content in the meta-schema, its golden cases, a review and a shadow run.
- **The migration of today's corpus** onto the D-Unit contract (§1.3) is mechanical for the fields the table's last column names. The new fields are added unit by unit, starting with the Founder Office and Admin's founder units, and each added field is reviewed.

## §14 · Safety and limits

- **Every unit states its authority boundary** from the closed action list. A unit can never move a `human_only` action into GeniOS's hands, and no move step with actor GeniOS performs one (D-21).
- **Legal, tax and compliance units** carry jurisdiction, `valid_from` and `review_by`, are `learnable: false`, and are labelled "general guidance, not legal advice" where a person sees them.
- **No personal data in the corpus.** Examples are synthetic or de-identified. Cases refer to copies by id.
- **A unit can never instruct a send, a payment, a signature or a submission.** Those are `human_only` (P5's delegation rules apply).

## §15 · Invariants and guards (CI)

Each guard is built and tested by one step; P3-0 lists each as built or not built.

| # | Must always hold | Built by |
|---|---|---|
| D-1 | The model never receives raw YAML; only the bridge renders units | P3-2 |
| D-2 | Every rendered rule carries its `applies_when`, `not_when`, counter-patterns and failure modes | P3-2 |
| D-3 | Every cut by the budget is counted in the rendered text | P3-2 |
| D-4 | No rejected unit is ever rendered; every unreviewed or overdue unit is labelled | P3-2 |
| D-5 | Every run records its pack hashes, the index hash and the unit versions it was given | P3-7 |
| D-6 | Every `facts_required` path has a writer; no unit names an unwritten path | P3-11 |
| D-7 | The meta-schema is identical for every domain (a schema test across domains) | P3-11 |
| D-8 | No customer data in the corpus, its cases or a review item: no tenant's people, companies, addresses or figures, and no money amount that is not a dated, sourced public term; public bodies only from `_schema/public_bodies.yaml` | P3-11 |
| D-9 | Every unit has at least one must-cite and one must-not-cite case before it is `reviewed`; a pattern or rule also a negative case | P3-6 |
| D-10 | A YAML, compiler or bridge change runs the cases, and a regression fails the build | P3-6 |
| D-11 | Selection never depends on an accepted brief line to find the kind of work | P3-8 |
| D-12 | No model writes or edits a corpus file, or decides a review state | P3-12 |
| D-13 | A package is never wider than its situation's visibility; narrower entries are left out and counted | P3-7 |
| D-14 | Every package field, and every unit field of §1.3, has a named reader; a non-empty value of a rendered field appears in the bridge text | P3-7, P3-2 |
| D-15 | Plane D reads no clock: compile and the bridge take `eval_time` from the request | P3-7 |
| D-16 | No corpus-wide search; the semantic fallback is gated by domain, capability and object | P3-1 |
| D-17 | No domain noun, threshold, duration or kind-of-work map in `reason/` or `packs/compiler` logic (an AST check) | P3-1 |
| D-18 | No YAML is read after a process starts (once the pack files replace start-up parsing) | P3-13 |
| D-19 | Every brain entry in a rendered package carries its brain label and state; none is rendered as a unit | P3-16 |
| D-20 | No recommendation card rests on grounding `unreviewed`, or on coverage `none` or `thin` | P3-7, with P5-1 |
| D-21 | No move step with actor GeniOS performs a `human_only` action; every boundary uses the closed list and agrees with L4's rule table | P3-11 |
| D-22 | A vendor or tool name appears only in a tool-knowledge unit | P3-11 |
| D-23 | A situation declaring a pending L2 type is not `stable` until the type is live | P3-12 |
| D-24 | No `learnable: false` unit is muted or down-ranked | P3-18 |
| D-25 | No cross-company review item carries a name, quote, amount, address, tenant id, or a case, thread or card id | P3-18 |
| D-26 | No Case unit appears among a card's evidence ids | P3-2 |

## §16 · What changes against today

| Today | Target | Why |
|---|---|---|
| Knowledge is chosen by the kind of work from an accepted brief line, so in the first week 0 of 138 judgments got any | Chosen by what the situation is and holds, from the page, across domains (§4.1) | Without it, Plane D never reaches the model |
| The compiler builds packages only for rule-born situations, rendered by templates | It builds the package for every run L2 makes, and the bridge renders it for the model (§0c, §4, §5) | The lane with the knowledge has no model; the lane with the model has no knowledge |
| One playbook by kind, Founder Office only; kinds of work mapped in code | Several units per situation, from every live domain; kinds of work in the vocabulary | An investor call needs investor relations and meeting follow-through |
| The reader reads only a capability's one staged playbook, and a rule's statement and why | Every unit that applies, staged or not, whole, with its conditions (§5) | Admin's 58 playbooks have no stages; "it reads their quiet, never ours" was lost |
| Only capabilities are hash-checked; situations are flagged; other kinds are only reported. 165 units approved and never switched on | Every unit versioned, hashed, reviewed and tested; one act sets reviewed and live together (§6) | Atlas admission; the half-state labels approved knowledge "not yet reviewed" |
| Conditions mostly prose (50 of 291 rules and 78 of 238 playbooks also carry checkable ones) | Every rule's conditions checkable, evaluated at selection (§1.3, §4.1) | A unit whose conditions fail is never shown as applying |
| 40 routing cases | At least 10 cases per founder capability, with must-abstain, negative and outcome cases and the six tests (§7) | Knowledge earns its place |
| The brains are empty | Brain paths in units, filled by P2 and L6, with classes and precedence (§4.3) | Without them, GeniOS gives consulting advice, correct and generic |
| Founder Office: 2 of its kinds authored, none reviewed; 5 of the ideal's 14 situations and 4 of its rules missing | Every founder kind authored, reviewed and tested (§2.1, §2.2) | 71% of situations had no knowledge behind them; the ideal's cards stand on it |
| No package for a goal | A goal package (§4.4) | The film's "every departmental goal" |
