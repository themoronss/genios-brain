# P3 · Plane D (domain expertise) · 01 · What's exactly there

**The part:** what a seasoned professional *knows*, per department and per kind of work:
- the situations each capability owns;
- playbooks: the stages, their typical durations, what quiet means at each stage, the moves and their steps;
- rules of thumb, each with **its conditions** (when it applies, when it breaks down, how it is misused);
- the objects, models and frameworks a professional reads the work with;
- the review state of all of it;
- the compiler that selects it for a situation, and the bridge that shows it to the model.

Plane D never reasons. P4 does that, with it. In the architecture's words, Plane D "concludes, reasons or chooses an action: never". It knows.

**Measured on:**
- **the corpus:** `Domain Expertise/` at `speedrun008` `a729b968`, 29 Oct. The corpus and `genios_engine/packs/` are unchanged since `71c50f56`. The counts come from the repo's own report (`python scripts/l2_refusal_report.py --corpus-only`, no database needed) and from reading every YAML file;
- **the product:** the local copy of the design partner's org, cut on 28 Oct at 12:45 UTC. This is one tenant's first week ([P1 01](../P1-ORCHESTRATOR/01-WHATS-EXACTLY-THERE.md));
- **the notebook:** build `b2`, as of 23 Oct 01:40 UTC.

The queries are in this part's log line in [08](../08-LOG.md).

**Status key:** ✅ works · 🟡 partly works · ❌ doesn't work · ⬜ not built.

---

## 1 · Every function of Plane D, and whether it works

| Function (Atlas "L2 · D") | Product | Notebook |
|---|---|---|
| **Hold the knowledge in one meta-schema** for every domain | ✅ 4 domains, 160 capabilities and 957 authored units, in the same tree, with 10 JSON schemas, a closed vocabulary and a validator | Reads the same corpus |
| **Cover the founder's work** | 🟡 Founder Office authors 2 of its 6 kinds of work. Admin holds approved items for meetings, renewals, registrations, commitments and correspondence (§4) | 🟡 The same 2 kinds |
| **Carry each rule's conditions** | 🟡 156 of 291 rules of thumb have both "applies when" and "breaks down when", written as prose. Only 50 of 291 rules and 78 of 238 playbooks also carry conditions code can check (`when_to_use.conditions`, the vocabulary's predicate grammar), and nothing evaluates them when knowledge is chosen | ❌ Conditions not shown |
| **Reviewed by a named human** | 🟡 228 of 957 units are live (`stable`, approved, reviewer named). **165 were approved by a named reviewer and never switched on.** Founder Office: 0 reviewed | Same corpus |
| **Admit only reviewed knowledge** | 🟡 Capabilities need a reviewer's accepted content hash (154 of 160 pass). A `draft` situation is flagged, and its card is downgraded to an observation. Rules of thumb, playbooks and objects are **reported, not gated** | ⬜ |
| **Compile a package for a situation** (the Domain Compiler) | ✅ Built: eight components in `packs/compiler/`. **100 packages** in the first week, one per rule-born situation, all Admin (§5) | ⬜ It reads one playbook by kind |
| **Select by what the situation is and holds** | ❌ The model's paths select by the kind of work from an **accepted** brief line, and 0 of 29 lines are accepted. So **0 of 138 L2 judgments and 0 of 50 expert reviews got any expertise** (§6) | 🟡 By kind only: 29% of situations got expertise |
| **Show it to the model whole** | ❌ Nothing reached the model. When something does, the reader drops every rule's conditions | ❌ Only the first step of each move; no conditions |
| **Adapt it with the company's brains** (organisation, behaviour, adaptive) | ❌ **0 entries.** All 100 packages carry 0 organisation rules, 0 behaviour patterns and 0 adaptive preferences; `learned_brain_entries` has 0 rows | ❌ |
| **Pin the knowledge each judgment used** | 🟡 Compiled lane: each package pins an expert snapshot and a brain snapshot (12 distinct). The model's paths record nothing, because they were given nothing | ⬜ |
| **Test the knowledge** | 🟡 40 evaluation cases, all of one kind: route a kind of work to a playbook, or abstain | ⬜ |
| **Measure each unit's use** (selected, cited, contradicted, outcome) | ⬜ | ⬜ |
| **Switch on per tenant and per department** | ✅ One row per tenant per domain (`l3_activation`): Admin on at onboarding (`default_on`), Founder Office on by hand for this tenant on 21 Oct | — |
| **Hold where and until when a rule is true** (jurisdiction, validity, review date) | ⬜ Indian programme and registration rules appear only as sources inside prose | ⬜ |
| **Learn only through review** | 🟡 The review queue is generated from the corpus (`_review/QUEUE.md`). Nothing from feedback reaches it yet | ⬜ |

## 2 · The corpus

### 2.1 · Capabilities and situations

| Domain | Capabilities | Admissible | Situations | Still `draft` | For this tenant |
|---|---|---|---|---|---|
| Admin | 59 (in 10 groups) | 59 | 34 | 4 | On (onboarding default) |
| Sales | 46 | 46 | 13 | 0 | Off |
| Customer Support | 49 | 49 | 20 | 16 | Off |
| **Founder Office** | **6** | **0** | **2** | **2** | On by hand (21 Oct) |
| **All** | **160** | **154** | **69** | **22** | |

- **Founder Office's six capabilities are inadmissible** ("unreadable" in the report). They are `draft`, `unreviewed` and name no reviewer, so the compiler drops them.
- **A card built from a `draft` situation is downgraded to an observation:** "it describes, and it does not instruct."

### 2.2 · The units, by kind and review state

"Live" means `stable`, approved, with a named reviewer. "Half-state" means approved by a named reviewer, but never switched to `stable`.

| Kind | Units | Live | Half-state | Unreviewed | Notes |
|---|---|---|---|---|---|
| Rules of thumb (`heuristics/`) | 291 | 65 | **80** | 146 | 156 carry both conditions as prose; 50 also carry checkable ones. Admin: all 60, all approved, 44 never switched on |
| Playbooks (`playbooks/`) | 238 | 62 | **80** | 96 | 976 steps in all. Only **2** declare stages (Founder Office's investor conversation and application) |
| Situations | 69 | 47 | **5** | 17 | The 5 half-state ones are named in the review queue's alarm |
| Objects | 102 | 6 | 0 | 96 | |
| Models | 88 | 0 | 0 | 88 | |
| Rules | 49 | 48 | 0 | 1 | |
| Mental models | 61 | 0 | 0 | 61 | Support 49, Sales 12 |
| Decision frameworks | 59 | 0 | 0 | 59 | Support 53, Sales 6 |
| **All** | **957** | **228** | **165** | **564** | |

**Per domain** (rules of thumb · playbooks · situations):

| Domain | Live | Half-state | Unreviewed |
|---|---|---|---|
| Admin | 16 · 14 · 30 | **44 · 44 · 4** | 0 · 0 · 0 |
| Customer Support | 8 · 8 · 4 | 32 · 32 · 1 | 114 · 71 · 15 |
| Founder Office | 0 · 0 · 0 | 0 · 0 · 0 | **10 · 11 · 2** |
| Sales | 41 · 40 · 13 | 4 · 4 · 0 | 22 · 14 · 0 |

### 2.3 · The tree, the same for every domain

`Domain Expertise/<Domain>/` holds:
- `domain.yaml`;
- `capabilities/<NN-group>/<capability>/`, with `capability.yaml` (purpose, outcomes, failure modes, KPIs, handoffs), `objects.yaml`, `knowledge.yaml` and `situations/`;
- `playbooks/`, `heuristics/` and `objects/`, plus `models/`, `rules/`, `mental-models/`, `decision-frameworks/` and `offerings/` where the domain has them;
- `registry/situation-capability-map.yaml`;
- `deferrals.yaml`: why a capability has no runtime door.

### 2.4 · The tooling around the corpus

| Folder | What it holds |
|---|---|
| `_schema/` | 10 JSON schemas, and `vocabulary.yaml`, the contract between authored knowledge and the running engine: **141 fact paths** (68 named by no unit), 51 observation kinds, **41 live L2 situation types** and 45 planned |
| `_tools/` | `validate.py`, `admit.py`, `index.py`, `plan.py`, `render.py`, `backlog.py` |
| `_eval/` | **40 routing cases:** Founder 25 (14 resolve, 11 abstain), Admin 9 (3 · 6), Support 3 (0 · 3), Sales 3 (1 · 2). Each says which playbook a kind of work must read, or that it must read none |
| `_review/` | `QUEUE.md`, generated by `scripts/dx_review_queue.py`: **15 situations waiting**, 10 of which fire on their L2 type alone with no further condition. `review.html` |
| `_book/` | The written book for Admin, Support and Sales |
| `_AUTHORING-BRIEF.md` | How a unit is written |

## 3 · Founder Office: the founder's own domain (STEP-11, 9 Oct)

**Its question:** "How would a seasoned chief of staff to a founder read this situation?"

**Its state:**
- `identity.status: draft`;
- `created_by: ai`, `reviewed_by: ""`, `review_status: unreviewed`, `confidence: provisional`;
- switched on for this tenant by hand (`default_on: false`).

| Capability (folder) | State | What is authored |
|---|---|---|
| Investor relations (`01-fundraising/investor-relations`) | Authored (capability 160 lines, knowledge 38) | 2 situations (`founder_office.sit.live_investor_relationship`, `founder_office.sit.live_investor_contact`). 6 playbooks. 5 rules of thumb |
| Programme applications (`02-programs-and-applications/program-applications`) | Authored (166 lines) | 5 playbooks, 5 rules of thumb. **No situation**, so it is read only "for a file whose kind of work is `program`" |
| Introductions (`03-networking-and-intros/introductions`) | **Stub** (23 + 17 lines) | Only the question: "Has each introduction been followed through on both sides?" |
| Registrations and recognition (`04-compliance/registrations-and-recognition`) | **Stub** | Only the question |
| Offers and joining (`05-hiring/offers-and-joining`) | **Stub** | Only the question |
| External meetings (`06-meetings/external-meetings`) | **Stub** ("Filled by STEP-11 M31") | Only the question: "Is each external meeting prepared for, and followed through after?" |

### 3.1 · The playbooks, as written

**Investor relations** (`playbooks/investor_relations/`):
- a warm intro to an investor;
- before an investor call;
- run an investor conversation. This one is 450 lines. Its stages are first contact → first call → partner meeting → diligence → term sheet → closed or passed. Each stage has a typical duration (a labelled prior with its source), what quiet means at that stage, and what ends it;
- the wave gone silent;
- reopen after a pass;
- the conditional deferral.

**Programme applications:**
- follow an application. 520 lines, with the stages applied → under review → interview → decision → onboarding → in programme or declined;
- work back from the deadline;
- prepare for the interview;
- read the decision mail;
- documents after acceptance.

Each playbook has `when_to_use` (situations, conditions code can check such as `has_obs: meeting_scheduled`, signals, and `do_not_use_when`), its steps (each with actor, produces and done when), a success signal, an outcome window, the cost of doing nothing, failure modes, limits and references.

### 3.2 · The rules of thumb, as written

Each has: a statement; a sourced why (Graham, Dixon, Gompers et al. and others); `confidence_bp`; **applies when**; **breaks down when**; **failure modes**; limits; metrics; references.

| Investor relations | Programme applications |
|---|---|
| Investors do not chase | The deadline is the only fixed point |
| Silence reads by stage | A rejection carries a reapplication date |
| Only an offer counts | A batch is silent until it decides |
| Momentum is a parallel process | The portal is the record |
| A pass is a date, not a verdict | A programme is not an investor |

**Example: the conditions are written down.** "Silence reads by stage" applies "when an investor conversation is open, **the turn is theirs**, and the stage is known". Its failure mode reads: "Using it to excuse our own silence. **It reads their quiet, never ours.**"

**And the move that answers our silence is written too.** "Before an investor call", step 6 of 6: "**Write the same day:** thank them, confirm the next step and its date in writing, and send anything promised on the call."

## 4 · Admin: approved knowledge the founder's work needs

All of these are approved by Harsh as a named reviewer. "Half-state" means approved and never switched to `stable`, so wherever it is shown it is labelled "not yet reviewed". The last column uses the situation each ideal card's trace names.

| Capability | Its rule of thumb and playbook | Situations it owns (corpus ids) | Ideal cards whose trace uses it |
|---|---|---|---|
| Meeting operations → **follow-up coordination**, with action-item tracking and meeting scheduling | "Momentum decays in days"; "The follow-through relay" (live) | `admin.sit.meeting_without_follow_through`; `admin.sit.meeting_left_open` (action items); `admin.sit.meeting_cancelled_not_rebooked` (scheduling) | `b2` (two partner calls, no written next step), `i3` (the follow-up after an investor call) |
| Executive support → **briefing and preparation** | "The brief is the meeting's first half"; "One page, the evening before" (live) | `admin.sit.meeting_ahead` | `f1` (prepare for a panel) |
| Contract and vendor administration → **renewal management** | "Vendors price your inertia"; "Renewals as annual re-decisions" (**half-state**). Its capability says: "Auto-renewal is the default that costs the most money precisely because it requires nobody to do anything" | `admin.sit.vendor_relationship_live` | `c2` (a tool subscription renews within the week; the ideal's situation is `obligation_falls_due`) |
| Compliance and governance → **statutory filing**, with **licence and registration** | "Late filings compound beyond the fine"; "Filing calendar worked backwards"; "Lapse gaps are retroactively expensive"; "Licence register with renewal runway" (all **half-state**) | `admin.sit.obligation_falls_due`, owned by statutory filing (**half-state**) | `c1` (the registration complaint), `c2` |
| Executive support → **commitment tracking** | "Forgotten beats broken for damage"; "The executive's promise ledger" (live) | `admin.sit.promise_past_its_date`, `admin.sit.dependency_stated`, `admin.sit.blocked_on_unnamed`, `admin.sit.analytic_movement`, `admin.sit.live_account_admin` | `f3` (a referral promised and silent) |
| Executive support → **inbox and correspondence** | "Response speed is reputation"; "Triage to five outcomes" (live) | `admin.sit.reply_owed`, `admin.sit.outbound_awaiting_reply`, `admin.sit.organization_gone_quiet`, `admin.sit.campaign_awaiting_reply`, `admin.sit.campaign_going_quiet`, `admin.sit.attention_unreported`, `admin.sit.outreach_reworded`, `admin.sit.live_admin_contact` | `reply_owed`: `i2`, `i6`, `s1`. `outbound_awaiting_reply`: `f4`, `b3`, `h1`, `l1`. The ideal's `i5` names a delivery-failure situation here, which does not exist |
| Executive support → **opportunity tracking** | "A satisfied condition has a short half-life"; "Reopen with the evidence named" (live) | `admin.sit.condition_awaiting_review`, `admin.sit.condition_now_satisfied`, `admin.sit.dormant_commitment_reopenable` | `s1` (a dormant thread reopens with news). Close cousins of `i1`'s conditional deferral |
| Executive support → **approval coordination**, with gatekeeping | "Slow approvals teach workarounds"; "Approvals as a fast lane" (live) | `admin.sit.decision_waiting_on_a_person`; `admin.sit.approvals_converging_on_one_person` (gatekeeping) | `b1` (two introductions waiting for a yes or no) |

## 5 · The compiler that already exists

The Atlas's Domain Compiler is built: `packs/compiler/domain_compiler.py`, "the eight Atlas compiler components composed into one deterministic Layer 3 service". It resolves, retrieves, binds, gathers evidence, builds and optionally publishes, and it "never decides".

| Component | What it does |
|---|---|
| `capability_resolver.py` | Routes a situation to capabilities. Applies admission: drops an unadmitted capability; flags a `draft` situation; reports unreviewed units |
| `object_resolver.py` | Resolves the required and optional objects |
| `knowledge_retriever.py` | Retrieves only the playbooks, rules of thumb, mental models, rules and decision frameworks a route names |
| `brain_resolver.py` | "Pin the Expert and three tenant brains into one reproducible snapshot" |
| `runtime_brains.py` | Reads the organisation, behaviour and adaptive brains (`learned_brain_entries`), explicitly by capability and subject |
| `evidence_aggregator.py` | The evidence behind the package |
| `expertise_builder.py` | Builds the `ExpertisePackage` (contract in `contracts/domain_expertise.py`) |
| `expertise_publisher.py` | Writes it to `expertise_packages` |

**What it produced in the first week:**
- **100 packages**, one per situation, for 100 situations. Each holds 2 to 8 capabilities (2.96 on average). All 296 capability entries are Admin's.
- 846 rule entries (36 distinct), 789 objects, 2,728 evidence items.
- **0** organisation rules, **0** behaviour patterns, **0** adaptive preferences in every package.
- Pinned to 12 distinct brain snapshots. All 100 are `review_state: accepted`. 12 unreviewed units (6 rules of thumb, 6 playbooks) appear in them 70 times, and are listed in each package's metadata.
- Each package's metadata also names what was skipped and missing: `skipped_capability_ids`, `missing_artifact_ids`, `admission_gaps`, `unresolved_route_predicates` and others.

**Who uses it:** the compiled lane (`reason/runner.py` and `context/`) only. `reason/l2/` and `reason/expert/`, the two paths where the model judges, **import none of it**.

## 6 · How the knowledge reaches the model today

| Path | What selects the knowledge | What is shown | What is lost |
|---|---|---|---|
| **Product: L2 judgment** (`reason/l2/`) and **expert review** (`reason/expert/dossier.py` + `packs/compiler/playbook_reader.py`) | The **kind of work, from an accepted brief line**, mapped to one Founder Office capability (`KIND_CAPABILITY`: investor, program, compliance, hiring, intro; vendor → Admin's renewal management; partner → none). The reader needs **exactly one playbook with stages**, which only investor and programme have | Stages (typical, yours, quiet means, ends when); every step of up to 10 moves; up to 20 rules as statement + why; the stop rule; "playbook not yet reviewed" | **Every rule's conditions** (applies when, breaks down when, failure modes). **All of Admin.** And in the first week, everything: no brief line was accepted |
| **Product: compiled lane** | The rule-born situation's L2 type, through the capability resolver | A package rendered by templates (`render_hint`, a fallback headline), not words for a model | Founder Office (inadmissible). The model never sees the package |
| **Notebook** (`nb/common.playbook_text`) | The kind of work, through the same reader | Stages and quiet means; **only the first step of each move**; rules as statements | Conditions; steps 2 onward (including "write the same day" after a call); all of Admin |

**Measured in the product's first week:**

| What | Count |
|---|---|
| L2 judgments (`reasoning_results`) | **138**. All 138 dossiers say "No company brief is accepted". **105** say "No playbook for this file"; the other **33** say "No file holds this subject". **0** carry a stage's "quiet means" or any rule's condition |
| Expert reviews (`expert_reviews`) | **50**, all 50 "No playbook for this file" |
| Cards from the compiled lane, by situation | 36, all Admin: dependency stated 13, condition in review 9, cohort outreach gap 4, analytic movement 3, account admin 2, reply owed 2, organisation gone quiet 1, campaign awaiting reply 1, commitment overdue 1 |
| Cards from expert file reviews | 33 (Admin 22, Founder Office 11), none with a playbook behind it |

## 7 · The ideal's knowledge, against the corpus

The ideal dashboard cites Plane D by name on every card's trace. Measured against the corpus:

**The 14 situations its cards and its Expertise page name:**

| Exists and live | Exists, not live | Missing |
|---|---|---|
| `decision_waiting_on_a_person`, `meeting_ahead`, `meeting_without_follow_through`, `organization_gone_quiet`, `outbound_awaiting_reply`, `promise_past_its_date`, `reply_owed` | `obligation_falls_due` (half-state); `live_investor_relationship` (Founder Office, unreviewed) | **`application_deadline`**, **`conditional_deferral`**, **`wave_gone_silent`**, **`information_conflict`**, **`delivery_failure`** |

`conditional_deferral` and `wave_gone_silent` exist as Founder Office **playbooks**, but not as situations.

**Existing is not the same as fitting.** As authored, several existing situations cannot describe the ideal's case:
- `reply_owed` fires when they wrote last (`outreach.days_owed` ≥ 2); in `i2` we replied, but without what was asked;
- `meeting_without_follow_through` fires 20 to 240 hours after a meeting; `i3`'s call was 15 days old, and `b2`'s 23 and 64;
- `promise_past_its_date` is our promise with our date (`commitment.days_overdue` > 0); `f3` is a third party's promise with no date;
- `decision_waiting_on_a_person` is defined on the ball being theirs; in `b1` the decision is the founder's;
- "the wave gone silent" says not to use it for an update to existing investors, which is exactly `i4`; Admin's `campaign_going_quiet` already detects a silent run of outreach;
- `obligation_falls_due` has no L2 type yet (its type is pending, waiting for `obligation.*` facts nothing writes), so it routes nothing for `c1` and `c2`.

**The rules and moves its cards and its Expertise page cite** (each card's trace also names an Organisation, Behaviour or Adaptive entry beside the Expert one):

| In the corpus | Only inside another unit | Missing |
|---|---|---|
| A pass is a date, not a verdict · Investors do not chase · Silence reads by stage · Only an offer counts · Follow an application · Work back from the deadline · Reopen after a pass · The wave gone silent | A warm intro beats a cold application (inside a playbook and a rule) · Answer the question that was asked (inside the investor conversation playbook) · An update must carry a new fact (inside "the wave gone silent") · Startup recognition gates the seed fund and the tax holiday (named only in the registrations stub's purpose and in programme rules' prose) | **One number, everywhere** · **Investors compare updates** · **Prepare one number, one story, one ask** · **A dormant thread reopens with news** |

**Its counts and paths:** the ideal counts Admin as 65 capabilities and 36 situations, which is Admin plus the Founder Office. It shows the founder's knowledge as **"Admin › Founder office › …"** (investor relations, programme applications, introductions, offers and joining), beside "Admin › Compliance & governance › registrations and recognition", "Admin › Contracts & vendors › renewal management", "Admin › Executive support › inbox and correspondence" and "Admin › Meeting operations › briefing and preparation". In the corpus, the Founder Office is its own domain (Rohit's decision D2, 9 Oct).

## 8 · The notebook (`b2`)

The 421 business situations by kind: intro 104, programme 92, event 71, other 42, partner 38, investor 29, vendor 15, compliance 13, internal 11, hiring 5, customer 1.
- **Only investor and programme (121, 29%) had any expertise behind them.**
- **300 (71%) were judged with none.**
