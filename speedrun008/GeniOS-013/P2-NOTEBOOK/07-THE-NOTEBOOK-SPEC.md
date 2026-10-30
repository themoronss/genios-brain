# P2 · Notebook · 07 · The Notebook, specified for production

**Written for:** Harsh and the coding agents Harsh assigns, who build it. Rohit decides the open questions in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md) (D-P2-12 to D-P2-21).

**What this file is:** the complete specification of the Notebook (L3, `context/`). It covers:
- every object and field;
- where each one lives in the product, and whether today's code is reused, adapted or built new;
- the admission laws, the lifecycle, time, identity, correlation, goals, decisions and the four brains;
- the read and write APIs;
- the invariants, the tests and the guards.

**Sources, in order of authority:**
1. GeniOS-008 `00-ARCHITECTURE.md` (Design Atlas v2): §L3; §II.1 contracts; §II.3 storage; §III.3 lifecycle; §III.4 storage rules; §A.4 confidence.
2. GeniOS-008 `02-MIGRATION-PLAN.md`, items L3-1 to L3-7, and `01-RULES.md`.
3. GeniOS-013 [05](../05-THE-WORK-OBJECT.md), the work object. **This file supersedes it where the two differ;** the differences are listed in §19.
4. The four references checked on 29 Oct: the ideal dashboard, the expected outcomes ([10](../10-ACCEPTANCE.md) and the card-by-card trace), Atlas v2, and the launch film with Rohit's description of the loops. That makes 309 requirements; the line-by-line trace is [08](08-REQUIREMENTS-TRACE.md).

**Status:** a specification. Nothing in it is built.

**Words.**
- "Situation" means the business situation: the piece of work, Atlas's BusinessSituationObject (BSO).
- "Page" means a situation's current interpretation.
- "We" and "us" mean the tenant company.

---

## §0 · Eight rules the Notebook never breaks

1. **It remembers; it never reasons.**
   - L3 makes no model call (Atlas §L3 "Model: none in the target"; GeniOS-008 L3-7).
   - Grouping threads into situations, judging, placing and correlating meaning are L2's (P4).
   - The Notebook admits what L2 proposes, and keeps it.
2. **Two halves, never mixed.**
   - **Evidence** (what the sources said) is written only by L1's graph writer.
   - **Intelligence** (what GeniOS concluded) is written only by admission: of an L2 result, an L4 record, or a human act.
   - The evidence half never holds a conclusion. The intelligence half never holds an unsourced fact.
3. **One door in, one door out.**
   - Every write goes through `context/work_store` (admission, §11). Every read goes through `context/notebook_api` (§12).
   - No other module selects from or writes to the Notebook's tables, and L1 never reads them. Both are CI guards (§17).
4. **Append-first.**
   - Nothing that evidence points at is hard-deleted. A change is a new row (a version, `valid_to`, `superseded_by`).
   - Only tenant erasure deletes.
5. **Every row knows itself.** It carries:
   - `org_id` and `trace_id`. L1 mints the `trace_id` with the evidence; a run takes the `trace_id` of the evidence that woke it (the newest, when several), and every row the run writes keeps it. A run woken by no new evidence (a date rung, the Maintain schedule, a goal change) takes the `trace_id` of the newest member evidence its version rests on (`caused_by_at`). A founder act or an L4 result is given its `trace_id` when it is admitted;
   - `audience`, never wider than its evidence;
   - `schema_version` and `producer` (code SHA, prompt version);
   - `writer` and `writer_ref`;
   - the times it needs: `occurred_at`, `known_at`, `valid_from`, `valid_to`, `as_of`.
6. **Unknown is not zero.** Every field holds one of three things:
   - a value;
   - `unknown {reason}`;
   - `checked_absent {scope}`.

   An absence is a finding only when the scope was fully read (§9).
7. **Numbers and dates are code's.**
   - Every number and date the Notebook serves is computed by a named query or tool from stored rows, and stored with its inputs.
   - The model words things; it never counts and never picks a date of its own.
8. **Domain-independent.**
   - Kinds of work, stages, categories, situation types, party kinds and their clusters, and node types are data, read from Plane D's index (P3-1) for the tenant's active packs.
   - Adding a domain adds content, never Notebook code or schema.

## §0b · The Notebook in each loop, for every customer's data

The same code serves every customer. What differs is rows: each tenant's own evidence, conclusions, policies and budgets, isolated by `org_id`. This is what each of P1's four loops asks of the Notebook.

### Onboard: once per customer, in waves (P1 [06](../P1-ORCHESTRATOR/06-NEW-CUSTOMER-ONBOARDING.md))

| Arrives | The Notebook does | Reads it serves |
|---|---|---|
| The window's evidence (wave 1: the last 30 days; wave 2: up to 365) | Evidence envelope rows with `known_at`; coverage per source; temporary items counted and dropped; obligation-class mail kept (§2) | Coverage, the first snapshot |
| The signup and our sent mail | The company page as proposed lines, with the time zone from the signup (§3.4) | Block A of every dossier |
| Headers, signatures | Party profiles, identity links (§3) | Block P |
| L2 placement of code's bundles | Admission creates `work_items` with stable ids; a re-run of a wave never duplicates (§4.1, §11.3) | Pages |
| First judgments | Version 1 of each page; loops by code (follow-throughs, bounces, waves); claims and conflicts (§4) | Cards (P5), the date index (P1) |
| Goal proposals | Admitted at the right grain, at most 10 in the first week, printed apart as proposed (§6) | The Goals page and the founder's four questions |

**Guarantees:**
- Every phase is idempotent and resumable: stable ids, an idempotent door, checkpoints in P1's ledger.
- Nothing is confirmed without the founder.
- A new customer needs no hand-made rows: every default comes from policy rows.

### Evolve: on every wake-up

- New evidence is written with `known_at`.
- A mail in a known thread with no new party joins by continuation (0 calls). Everything else goes to placement (L2).
- `stale_pages()` names the work to judge. The snapshot carries the page plus only what is new.
- Admission keeps each passing change and writes a version.
- Facts travel to the five audiences (§10.2), and dependents are marked dirty for P1.
- `due_dates()` feeds P1's clock.
- **A day with nothing new and no date crossing costs 0 model calls.**

### Act: on every founder act and execution result

- `founder_decisions` rows: answers settle their loops and are never asked again; corrections lock fields; suppressions apply within their scope (§7.2).
- A decision moves the work to `decided`, an execution to `executing`. A verified outcome resolves it with `outcome_ref` (§5.1).
- An agent's send links to the approval of its exact draft (I-20). A result that returns after the page changed is re-checked first.
- `card_outcomes` keep recommendation, action and outcome together (§7.5).

### Maintain: nightly and weekly, in each tenant's local time

- **Lifecycle:** the quiet-work rule; staleness; leases expiring; deadline-bound work resolved (§5).
- **Retention holds** from citations (§14), and evidence withdrawals processed (§20.2).
- **Patterns and predictions:** company patterns counted and promoted to the Behavior brain; predictions scored (§7.5, §8).
- **Self-checks:** the Notebook's own accuracy and calibration (§20.4, §20.5); the invariants (§15); context health and company checks (§12).
- **Size per tenant**, and contract upgrades (§20.9).

### Across customers

- No read crosses tenants.
- Budgets, retention and decision rights are per tenant.
- Erasure and export are per tenant.
- A team is onboarded only after visibility is proved (P2-10).
- The same invariants run for every tenant, every day.

## §1 · The map: every object, where it lives, what is reused

**Decision D-P2-12** (recommended, [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)): **one chain, headed by `work_items`.**
- `work_items` is the situation (the BSO).
- `work_item_versions` holds its append-only interpretations.
- Decisions, executions and outcomes hang off it by foreign key.

During migration, `work_items` runs **beside** today's `context_situations` (GeniOS-008 Rule 2). That keeps the nine old situation writers from ever touching a row L2 formed. At each tenant's cutover, `context_situations` stops being written for that tenant, and its rule-born rows retire one type at a time (GeniOS-008 L3-2, the ratchet). After the cutover there is one chain again, as Atlas intends.

Because `work_items` is a new head table, this amends Atlas III.4 ("the Intelligence Graph has no tables of its own"), which needs Rohit's yes. The alternative is to extend `context_situations` and `situation_interpretations` in place. That is rejected because every old writer would then need a guard, and one missed guard would let the old pipeline rewrite L2's situations.

| Object | Half | Production home | Verdict | Today |
|---|---|---|---|---|
| Evidence item (every kind) | evidence | `source_events` + `prepared_content` + object storage for raw bodies | ADAPT: one envelope (§2.1), `known_at` | 4,784 events, encrypted raw copies in `raw_payloads` |
| Entities: the tenant itself, person, company, deal, meeting, document, commitment, and more types as data from the active packs (contract, invoice, asset …) | evidence | `graph_nodes`, `graph_aliases` | REUSE + every node has a label, a cluster and receipts (its distinct evidence). A party's cluster comes from `party_profiles`, a deal's from its counterparty, a meeting's or document's from its anchor, a commitment's from its promisor; the tenant is `core`. One node per real object per tenant, referenced by any domain's situations | 2,268 nodes |
| Facts and evidence edges | evidence | `graph_facts`, `graph_edges` | ADAPT: epistemic status, authority class, bitemporal discipline (§2.5) | 16,792 facts; ~8 derived writers bypass `analytic/publish` (GeniOS-008 L3-5) |
| Qualified signals (L1's output, D-P2-14) | evidence | `qualified_signals`, append-only | ADAPT: all ten L1 fields kept (signal id, `signal_type`, `subject_key`, `domain_hints`, `confidence_bp`, `importance_bp`, `occurred_at`, `expires_at`, `secondary_types`, `extraction_ref`). `importance_bp` is L1's salience, never a situation's materiality | the envelope keeps only the type and ids |
| Correlation joins (§10.1) | evidence | join rows with `derived_from` | ADAPT: the six joins only; a join makes no situation and no conclusion | membership lives in correlations |
| Coverage per source | evidence | `source_coverage`, `coverage_epochs`, `context/coverage_receipt.py` | REUSE + per-thread receipt | 4 rows |
| Delivery notices (bounces) | evidence | `source_events` + `context/delivery.py` | ADAPT: parse the original send (§2.2) | bounce on the address and the thread only |
| Party profile (what a party is to us) | intelligence | **`party_profiles`** (versioned) | BUILD | roles rarely stored |
| Identity doubt and merges | intelligence | **`party_identity_links`** + `merge_history` | BUILD + REUSE | `resolve_alias_candidates` has no caller (L3-6) |
| Addresses and deliverability | intelligence | **`party_addresses`** | BUILD | — |
| Company page (Organization brain) | intelligence | `company_brief_lines` (accepted) + `org_self_identities` + `learned_brain_entries` (`brain = organization`) | ADAPT | 29 lines proposed, 0 accepted; 0 identity rows |
| The situation (BSO) | intelligence | **`work_items`**, the head of the chain; replaces `context_situations` per tenant at cutover | BUILD: columns of §4.2; admission gates existence (L3-1) | 1,528 rule-born `context_situations` rows, retired by type |
| Versions (interpretations) | intelligence | **`work_item_versions`** (Atlas's interpretations, append-only) | BUILD: typed parts of §4.7 | `situation_interpretations`: 30 rows, unread |
| Members | intelligence | **`work_members`** | BUILD | membership lives in correlations (evidence joins) |
| Loops (question, ask, promise, condition) | intelligence | `open_loops` | ADAPT (§4.4) | 212 rows, 208 open; 87 commitments as nodes |
| Claims (what we told people) | intelligence | **`company_claims`** | BUILD | amounts as `financial.amount` facts on a person node |
| Conflicts between values | intelligence | `discrepancies` | ADAPT: sides, held, founder resolution (§4.5) | 9 rows |
| Meaning links | intelligence | **`intelligence_links`** | BUILD (§4.6) | — |
| Absence findings | intelligence | `situation_absences` | ADAPT: four kinds (§9.1); keyed by `work_id` | 341 rows |
| Evidence needs | intelligence | `evidence_needs` | ADAPT: situation, owner, met-by (§9.3) | 115 rows; `hold_needs.py` has no caller |
| Admission ledger | intelligence | `situation_admission_decisions` | ADAPT: per candidate and per change; law ids; keyed by `work_id` (§11.4) | 985 rows (old admission) |
| Goals | intelligence | `company_goals` (0254) | ADAPT: fields of §6.1 | 7 proposed, 0 approved |
| Goal progress readings | intelligence | **`goal_progress`**, one row per change | BUILD (§6.1) | — |
| Goal ↔ situation links | intelligence | `goal_situation_links` (0254) | ADAPT: `work_id`, through, size basis, confirmed, writer, validity | 0 rows |
| Goal ↔ goal links | intelligence | **`goal_links`** | BUILD | — |
| DecisionObject (L3 → L4) | intelligence | **`decision_objects`** | BUILD (L3-4) | does not exist |
| The founder's acts | intelligence | **`founder_decisions`** + `founder_questions` (answers) + `founder_corrections` | BUILD + ADAPT | 40 questions asked, 0 answered |
| L6 attributions aimed at L3 | intelligence | **`attributions`** | BUILD (§7.4) | — |
| Executions and outcomes | L4 | `executions`, `execution_outcomes` | REUSE; add `work_id`, `page_version`, `goal_version`, `approval_ref` | 105 executions |
| Behavior and Adaptive brains | intelligence | `learned_brain_entries` + `learning_objects` | ADAPT: expiry on Adaptive leases; counts on Behavior (§8) | 0 entries, 7 learning objects |
| Persona (preferences) | intelligence | **`preferences`** (beside `seat_profiles`) | BUILD | — |
| Company milestones | intelligence | **`company_milestones`** | BUILD | — |
| Company patterns, party cadence | intelligence | **`company_patterns`** | BUILD (written by P4-7's weekly pass, through admission) | — |
| Predictions, and prediction versus actual | intelligence | **`predictions`**, **`prediction_actual`** | BUILD (§7.5) | — |
| Citations (what keeps evidence alive) | intelligence | **`evidence_citations`** | BUILD (§14) | — |
| Retention policy | platform | **`tenant_retention_policy`** | BUILD | per table, by capture date |
| Revision | both | `graph_versions` (one counter per org) | REUSE as the tenant-wide revision (§13) | 2,128 for this org |
| Run receipts | L2/L1 | `reasoning_runs` (snapshot ids, input hash, replay link) | REUSE (§12.4) | 153 rows |
| The bounded read | read | `context/bounded_read.py` → `context/notebook_api.py` | ADAPT (L3-3): as-of, unknowns, contradictions, viewer | no caller |
| The admission door | write | `context/situation_publisher.py`, `context/l2_admission.py` → `context/work_store.py` | ADAPT (L3-1): gates existence; one writer | called after the row exists |

Every table here carries `org_id`, `trace_id`, `audience`, `schema_version`, `producer`, `writer` and `writer_ref`. It is covered by row-level security on `org_id`, and joins the erasure path.

## §2 · Evidence

### 2.1 · One envelope for every kind of evidence

Every item, of every kind, has:

| Field | Meaning |
|---|---|
| `evidence_id` | Stable. The id every conclusion cites |
| `kind` | `mail` · `meeting` · `document` · `screen_moment` · `execution_result` · `founder_act` · `delivery_notice` · `system_notice` · `chat` · `ticket` (more kinds come with more tools, as data) |
| `source_tool`, `connection_id`, `permission_scope` | Which connector, under which grant |
| `occurred_at` | When it happened in the world (UTC) |
| `known_at` | When GeniOS first captured it. Never backfilled |
| `audience` | `visibility_scope` and `visibility_principals`, from capture |
| `text_ref`, `text_state` | Where its clean text is, and `read` · `recovered` · `archived_unread` · `failed` · `none` |
| `authority_class` | `authoritative` (signed, system of record) · `operational` · `first_hand` (the party's own mail) · `reported` (forwards, chat, summaries) |
| `signal_type` | L1's type when capture gave one (`deadline_stated`, `commitment_made`, `decision_pending`, `decision_made`, `relationship_change`, `opportunity_signal`, `escalation`, `delivery_failure`, `contract_renewal`, `information_conflict`), else `none` |
| `qualified_signal_ids` | The L1 signals read from it (D-P2-14) |
| `addr_raw` / `addr_key` | Every address exactly as written, beside a lower-cased match key. Drafts copy `addr_raw` |
| `content_digest` | A digest of the content. A re-sent mail or a re-uploaded identical file has the same digest, and is not a material change (§4.2 `fingerprint`) |

**Coverage is closed.** After every run, each item known by the run's instant is one of two things (invariant I-3):
- a live member of at least one situation;
- on the noise list, with a reason from a closed list: `bulk` · `temporary` · `automated_no_obligation` · `not_work`. Bulk items, and temporary items that join no work (§2.3), sit on this list.

### 2.2 · The kinds, each with its rules

- **Mail.** Direction, sender, every recipient (to, cc) and the thread. Also `body_new`: the new text above the quoted history. Claims and quotes about us use only `body_new`. Every outbound mail has a `delivery` state: `sent` · `delivered` (no delivery notice 24 hours after the send) · `bounced` (with the notice), recomputed by code on each event and nightly.
- **Meeting.** Each meeting stores:
  - start and end, as instants with the event's zone;
  - organiser and attendees as party ids: `attendees [{party, role (us, team, counterparty, channel), response}]`, each response (`accepted`, `needs_action`, `declined`, `tentative`) as of `known_at`;
  - the founder's own response, and the count of attendees;
  - `cancelled_at` and booking answers (quotable);
  - `known_at`, read field by field at the run's instant (a build as of T sees the time the meeting had at T);
  - `held`: `unknown` · `corroborated(evidence_id)` · `founder_confirmed` · `cancelled`. A meeting counts as held only with corroboration;
  - `when_class(as_of)`: `past` · `today` · `upcoming` · `cancelled`, by code in the company's time zone. It is separate from `held`.
- **Document.** Kind (`attachment`, `link`, `shared_doc`, `signed_doc`), name, the mail that carried it, sender, recipients, date, and text when read.
  - Its comments and revisions are events of their own once the drive is connected.
  - A document can satisfy a situation's `done_when`.
- **Screen moment.** Seat, app, window, captured and known times, kind (`ask`, `deadline`, `risk`, `my_promise`, `their_promise`, `next_step`) and a who·what·by-when line.
  - Its verdict is `kept` or `temporary`. Only kept moments become members or can be cited.
  - Its audience is the capturing seat. Only a content hash and quotes of at most 12 words are stored.
  - It is promoted only for orgs whose semantic lane is live.
- **Execution result** (from L4). It settles a loop only through the item it produced, such as the sent mail. Its "done" alone is *reported*, never *verified*.
- **Founder act.** Every answer, approval, edit, snooze, drop and delegation. It is evidence with founder authority (§7.2).
- **Delivery notice.** Parsed into:
  - the bounced address;
  - the original send: the notice's quoted Message-ID, else its subject and date, else our latest outbound to that address before the notice in any thread;
  - the date and the reason.

  It becomes a member of every situation holding the original send (§4.4 moot rule).
- **System and portal notice.** Attached to the organisation it is **about** (the product, vendor, programme or attendee it names), with its sender kept as the channel (§2.3).

### 2.3 · Archived, system and temporary mail

- **Obligation-class mail is kept with its text.** Code inside L1 (capture) classes a mail as obligation-bearing from its headers, subject and a code-only scan of its decrypted text. The classes are:
  - deadline, reminder, incomplete;
  - renewal, charge, invoice;
  - decision, rejection;
  - application received, portal status.

  No model sees it before this class is set. Such mail is promoted (with `text_state = recovered`) even when it is the only trace of its work. This keeps `f2`'s reminders, `c2`'s renewal notices and `c1`'s portal reminder.
- **Other archived mail** is promoted only when one of three things holds:
  - its thread already holds a member of a live situation;
  - its sender's address or registrable domain is a party of a live situation;
  - L2 raises an EvidenceNeed for it (D-P2-3).

  Bulk and newsletters stay archived and unread.
- **About, not from.** A system mail is clustered by sender only as a first proposal. The placement judgment (P4) puts it in the situation it is about. A page may not set `noise` on a thread holding an obligation-class mail: that is held, with the reason "states an obligation".
- **Temporary evidence is never kept as memory.** This covers one-time codes, verification mail, sign-in, password resets, and Screen moments judged temporary.
  - Code classes them by sender, subject and a digit-code pattern.
  - They are never quotes, claims or facts; a citation of one is held (A-16).
  - One from a party of a live situation (a portal's sign-in code) joins that work as a **header-only member**: sender, time and subject class, with no text. It shows the activity, and is never cited.
  - Their text is dropped after 7 days, and the count let go is reported (`memory_temporary_count`).

### 2.4 · Authority: one ladder, set by code

| Rank | What |
|---|---|
| founder | the founder's own word (a decision, a correction, an answer) |
| 6 | a signed document |
| 5 | company canon (an accepted brief line, a canon document) |
| 4 | a derived thread state or identity (computed by code) |
| 3 | system mail, attachments, links |
| 2 | a statement in an email by its author |
| 1 | a third party's paraphrase (an introducer describing us) |
| 0 | derived by a reasoning unit |

- The model never sets a rank.
- The envelope's `authority_class` is derived from the rank by code, never typed: founder, 6 and 5 → `authoritative`; 4 and 3 → `operational`; 2 → `first_hand`; 1 and 0 → `reported`. The snapshot prints the class beside every fact and member (§12.1).
- The legacy `authority_rank = 100` rows (two scales in one column) move to their own column (`is_canon`).
- Every stored score is an integer in basis points, from 0 to 10,000, under a check constraint. Words stay words, and no float crosses a boundary.

### 2.5 · Facts and edges: what each one carries

Every fact and edge carries:
- `subject`, `relation` and `object`;
- `epistemic_status`: `verified` · `reported` · `inferred` · `hypothesised`;
- `evidence_refs`, never empty, each `{evidence_id, start, end, quote}`: the exact span it rests on (A-2), and `source_authority` (§2.4);
- `occurred_at`, `observed_at` (when GeniOS learned it), `valid_from` and `valid_until` (set when superseded, never deleted);
- `lifecycle` (`new`, `updated`, `superseded`, `retracted`, `expired`) with its `since`;
- `last_confirmed_at` (the newest evidence that restated it) and `stale_after` (by kind: a claimed number 60 days, a role or address 180 days, a stage its playbook's window);
- `audience`.

**Staleness reaches every value that ages.** The same `last_confirmed_at` and `stale_after` sit on company claims (§4.5), affiliations and addresses (§3.1), a situation's stage (`stage_confirmed_at`, §4.2) and stated dates. Maintain marks them stale (§5.5), and the snapshot prints each one's age. A past `slot` that no later mail restated is stale: it opens no expectation and makes no card.

**One value per fact.**
- For each (subject, field), the current value is the single highest-ranked one. The others get `superseded_by`.
- When the top ranks are equal, the fact is `conflict_open`. Every value is kept, none is current, and a conflict row exists (§4.5).
- A stale or superseded fact never outranks a fresh one, and the snapshot shows each fact's age.
- When two sources give different values for the same (subject, field), and neither `replaces` or supersedes the other (a newer value from the same source is an update), a `contradicts` link and a conflict row are written **whatever the ranks**. The higher rank stays current, the conflict's state is `ranked` (§4.5), and the snapshot shows both sides with their authority and date.

**Evidence edges** (closed list; the check refuses any other word): `works_at`, `introduced`, `owns`, `involves`, `attended`, `raised_in`, `concerns`, `edited`, `assigned`, `corresponded_with`.

**Clock-dependent values are not facts.** Days waiting, overdue hours and age are computed by L2's tools on the snapshot, never written into the graph every sweep (GeniOS-008 L3-5). This also ends most of the database churn (P1 F9, P2 F12).

### 2.6 · Coverage: what was read, and what could not be

**Per source:** `sources` rows (adapting `source_coverage`) hold:
- the source and its kind (`gmail`, `calendar`, `screen`, `drive`, `billing`, `portal`, `linkedin`, and more);
- `connected` and the scope;
- the history window (from, to) and `last_complete_sync`;
- `coverage_bp`, computed by code (for example, mail with readable text ÷ mail in the window);
- `state`: `full` · `partial` · `unknown` · `not_connected`;
- `cannot_see`, one line.

**Per situation:** each version stores `coverage` with three parts:
- the sources read, how many items from each, and their date span (the first and last `occurred_at`, by code);
- `unread`: a list of items or ranges, each with its reason (`attachment_not_parsed`, `archived_without_text`, `outside_capture_window`, `tool_not_connected`);
- for each member printed, its read state (`full`, `shortened`, `header_only`, `no_text`).

**When a connection is revoked:** no new evidence is admitted from it. Every live situation with members from it records "source disconnected since <date>". Any absence resting on it becomes `unknown`.

## §3 · Parties, identity and the company itself

### 3.1 · The party profile (`party_profiles`, versioned)

| Field | Meaning |
|---|---|
| `party_id` | Points at the evidence node(s): a person or company in `graph_nodes` |
| `kind` | Closed list, held as data in Plane D's vocabulary (P3-1): P2-14 freezes today's list, and admission checks the word against the loaded one, with no schema check on the words. `service` covers automated senders (no-reply, mailer-daemon, booking and payment tools). Today's list: `team`, `founder`, `agent`, `candidate`, `investor`, `accelerator`, `incubator`, `connector`, `intro_platform`, `peer`, `partner`, `event`, `media`, `prospect`, `customer`, `government`, `vendor`, `service`, `other` |
| `cluster` | One of the graph's clusters, from a fixed table (data, with the kinds): team ← team, founder, agent, candidate · investors ← investor · programmes ← accelerator, incubator · network ← connector, intro_platform, peer, partner, event, media, other · prospects ← prospect, customer · compliance & vendors ← government, vendor, service. Every kind is in exactly one cluster |
| `relationship` | One line: what it is **to us** |
| `affiliations` | `[{org party, relation (works_at, founder_of, scout_for, advisor_to, role_for), role line, evidence, since, until}]`. A person may hold several at once |
| `identity_strength` | `strong` (an address) · `medium` (a domain plus a name) · `weak` (a name only), with the identifiers that prove it, raw as written |
| `introduced_by` | The party and the mail that introduced them, with the kind of introduction (`forward`, `platform`, `ours`) |
| `state` | `active` · `waiting_on_them` · `waiting_on_us` · `cooling` · `cold`, with `since` and the rule id. Recomputed by code on each event and nightly. With `g` = the larger of twice the party's own 75th-percentile gap and 14 days (the playbook's default while `n` is under 4): `cooling` after more than `g` of no contact either way; `cold` after more than 2 × `g` |
| `cadence` | Median and 75th-percentile reply hours each way, and delivery time for a promiser, with `n` and the window. Computed by code from member mail |
| `typed_facts` | Title, relationship nature, stage, `introduced_by`, open question, ball in court, what they use, last touch: each `{value, authority_rank, evidence_ids, since}`. Ball in court and last touch are derived by code (rank 4). Receipts are the distinct evidence ids; versions are the profile's versions (`party`, §12) |
| `availability` | `available` · `on_leave(until)` · `gone`, with its evidence, for every party. `gone` ends its affiliations (`until` set) |
| `basis` | `code` · `l2_result` · `founder`, plus evidence ids |

**Addresses** (`party_addresses`):
- the address raw and keyed;
- its status: `working` (they wrote from it, or our send was not bounced), `bounced(date, notice)` or `dead` (a founder decision);
- `last_delivered_at`.

For a bounced address, code lists working addresses at the same organisation, each with its source thread (`alternate_addresses`, §12). A `dead` mark is a founder decision of kind `correct` whose `scope_ref` is the address (§7.2); a dead address is never offered as working.

**Roles in a situation** (on `work_members`, kind `party`): `decides` · `contact` · `introducer` · `awaited` · `owner` · `approver` · `promisor` · `us` · `other`.
- A mention is never ownership. An owner or approver needs a quote that assigns the role, or a founder act (A-30). The member role and its `owned_by` or `approved_by` link are written together, in one transaction.
- Without one, the page says "no accountable owner found".

### 3.2 · Identity with doubt

`party_identity_links` hold:
- the two parties;
- a status: `probable` · `confirmed` · `rejected`;
- the evidence;
- who decided it (`l1`, `l2_result`, `founder`) and when.

The rules:
- A merge is a confirmed link, logged in `merge_history` with its reason. It is undone by setting the link to `rejected`; rows are never rewritten.
- The snapshot prints probable links as doubts.
- L6's attribution `wrong_entity_resolution` points at the link.
- Identifiers are never normalised into a "plausible" variant.

### 3.3 · Our team and our agents

- **Team members** are parties of kind `team`, with:
  - department, role and seat;
  - availability: `available`, `on_leave until <date>` or `gone`, with its evidence.
- **Agents** are parties of kind `agent` (in-house or third party), with:
  - capabilities;
  - the departments and goal ids served;
  - the approver;
  - their track record (§7.4).

### 3.4 · The company page (the Organization brain)

The company page is stored as **fact rows**, not one document. Each row has a field, a value, evidence ids and a state (`proposed` · `accepted` · `held` · `rejected`), with `accepted_by` and `accepted_at`. It is built from accepted brief lines, `org_self_identities` and `learned_brain_entries(brain = organization)`.

| Field | Notes |
|---|---|
| legal name, product name, other names | — |
| our addresses and domains | the "us" every phase reads (placement, whose move, admission, dossiers) |
| `time_zone` | An IANA name, from the signup or `orgs.timezone` and confirmed by the founder. Never guessed |
| `customer_kind` | `founder` or `team`, from the signup, confirmed by the founder on the first screen. It sets the default domain rows (P3 [07](../P3-PLANE-D/07-THE-PLANE-D-SPEC.md) §9) |
| `jurisdiction` | The country (ISO code) and, where it matters, the state, from the signup or the registered address, confirmed by the founder. Plane D selects law, tax, compliance and programme units by it (P3 [07](../P3-PLANE-D/07-THE-PLANE-D-SPEC.md) §2.4) |
| founders and team | party ids |
| departments switched on | each with its owner |
| what we do | — |
| `positioning_versions` | A statement quoted from our sent mail, with from and to dates. Each pitch mail links to the version in force on its date |
| `verified_claims` | Per metric: the amount, currency, period, verifying source (billing, a document, or the founder's word), `picked_at`, `picked_by` and the decision id. Only a founder decision can set it (§4.5) |
| needed facts | A fixed list (legal entity, product line, round size, closing date, traction, backers, team). Each is filled, or stored as `unknown: not stated anywhere` |
| `approval_lead_times` | Per kind of approval (spend, contract, hire): the company's usual lead time, from the founder or counted from history (labelled as counted). Plane D's units read it as `org.*` (P3 [07](../P3-PLANE-D/07-THE-PLANE-D-SPEC.md) §3.2) |
| `critical_vendors` | The vendors and subscriptions the company depends on, each with its renewal date and owner |
| owners per area | For each area (finance, legal, hiring, vendors …), the person who owns it |

**Company milestones** (`company_milestones`) hold:
- the kind: `selected`, `review_held`, `letter_received`, `hire_joined`, `launch`, `award`, `other`;
- what happened, and the local date;
- the source evidence and the quote that states it;
- the proof (`public page`, `letter`, `portal status`, `none`);
- the state: `proposed` or `confirmed`;
- `told_to [{party, evidence_id, said_at}]`, written by code when our mail carries the milestone.

Milestones are what P2-6 offers to other situations (§10.2). A milestone is **new to a party** when it has no `told_to` row for that party.

**Rule:** an Organization fact about a company number changes only by a founder decision.

## §4 · The business situation (the BSO)

### 4.1 · Identity, birth and uniqueness

- A `work_items` row exists only after admission ADMITs an L2 "new situation" mutation (L3-1).
  - Code clustering only proposes candidate bundles.
  - L2's deterministic units (0 model calls) may propose a new situation: a wave, the one-number record, a delivery failure. Such a proposal passes the same door.
  - The Notebook's store never creates a situation itself.
- **`work_id` is stable.**
  - It is minted once, from (tenant, first member evidence id).
  - It never comes from a build or a model key.
  - On regrouping (a rebuild, Evolve placement, onboarding wave 2), each new group keeps the id of the old situation holding most of its members.
- **One open situation per real matter.** A candidate that shares a member thread, or the same anchor, situation type and `matter_key`, with an open situation is held as `possible_duplicate_of [ids]`. L2 is woken to choose update, merge or new.
  - No two live situations share (anchor, situation type, `matter_key`) unless one is `part_of` the other. `matter_key` names the specific subject (a filing or contract id, a programme cohort, a thread family), so two filings with one portal can both be open. This is invariant I-12.
- **An introducing channel has its own work.** Each introducing platform has one channel work that holds its housekeeping mail. Each introduction is its own situation, with the channel work as its parent; housekeeping never makes an introduction card.
- **Structural changes** (merge, split, reopen, parent, higher-order situation) are applied only from an L2 mutation that names them. Each is recorded with its result id. The Notebook offers candidates read-only (§10.3).
  - On a merge the survivor takes the absorbed members (`left_reason = merged_into <id>`, `joined_by = l2_result`), the absorbed row keeps `merged_into`, and `history_of(work_id)` reads both version chains. A split is defined in §11.1.

### 4.2 · The fields on the situation row (current values; history in §4.7)

| Field | Meaning | Written by |
|---|---|---|
| `title` | The work in the founder's words, at most 120 characters | L2 · founder |
| `kind`, `kind_basis` | Kind of work (from Plane D's vocabulary), with its basis: `l2` · `brief` · `founder`. L2 never overwrites a founder value | L2 · founder |
| `situation_type`, `expertise_path` | The Plane D situation id (for example `founder_office.sit.conditional_deferral`, shown to the founder as "Admin › Founder office") and domain › area › capability, or null with "no authored type". Optional: `also_types[]` (further Plane D situation ids that also match, as in `s1`: reply owed and a dormant thread) and `qualifier` (a word from that type's closed list in Plane D, as in `i2`: answered, but not the question asked). Plane D selects knowledge for all of them (P3 07 §4.1) | L2 (must be printed index ids) |
| `anchor`, `primary_party` | The node the work is rooted at (a party, or the claim group for the one-number record), set at birth; and the main counterparty, or null. The snapshot is rooted at the anchor | L2, checked: printed ids |
| `matter_key`, `topic_key` | The specific subject, part of the uniqueness key (§4.1, I-12); and a topic shared across anchors, for same-topic candidates (§4.9) | L2, checked by code |
| `about` | The evidence nodes the work is about (parties, a deal, a document), stored as `about` links (§4.6) | L2, checked: printed ids |
| `materiality` | `{band: critical · high · medium · low, score_bp, reason, basis tool ids}`: how much the work matters, shown on the page as its importance (the ideal's urgency level). L1's salience stays on the signal (`importance_bp`), action priority on the L4 execution and delivery urgency on the card; the Notebook copies none of them here | L2, checked against tool inputs |
| `aspects` | `[{aspect, department, owner}]`, when parts of one work have different owners (a notice window, a spend approval) | L2 with evidence; L4 or the founder assigns |
| `category` | One of the tenant's categories (Admin: investment, funding, business, sales, projects, progress, process, hiring), set independently of its goals | L2, checked against the list |
| `department`, `owner` | The department it belongs to; the accountable owner (a party, the founder by default), only from evidence or a founder act | L2 recommends; L4 or the founder assigns |
| `stage`, `stage_since`, `stage_confirmed_at` | A stage from the kind's ladder (§4.10), when it began, and the newest evidence that restated it. Every change writes stage history (§4.7) | L2, checked against the list |
| `state`, `state_since`, `state_reason` | Atlas's lifecycle (§5.1), with one line saying why | admission, from mutations |
| `whose_move`, `awaited_party`, `whose_move_since` | `us` · `them` · `third_party` · `none`. **Derived by code** (the rule below); an L2 value that differs is held unless it cites a newer member event | code |
| `next_actor`, `next_check` | `us` · `them` · `geniOS`. When nothing open is owed by us and an expectation's date is ahead, the next actor is GeniOS, with `next_check = {at, what, notify: false}` | code |
| `status`, `status_since` | The founder's word for where it stands, derived by code from state, whose move, attention and suppressions: `waiting_on_them` · `waiting_on_us` · `put_off (until)` · `blocked` · `done` · `dropped` · `quiet`. The rule, in this order of precedence: `dropped` = resolved by a founder drop (outcome `withdrawn`); `done` = resolved with any other outcome; `put_off` = an active not-now, later or snooze; `blocked` = state `blocked`, or an open `depends_on` on an open situation; `waiting_on_them` or `waiting_on_us` = `whose_move`; `whose_move = third_party` reads `waiting_on_them`; `whose_move = none` with an open expectation ahead reads `waiting_on_them` (its `status_since` is the earliest such expectation's `set_at`, because with no open loop there is no `whose_move_since`); `quiet` = attention `quiet`; `whose_move = none` with nothing expected and attention not quiet is stored as `unknown {nothing owed}`. `status_since` is the `since` of the rule that fired: `whose_move_since` for waiting, the decision instant for `put_off`, `dropped` and `done`, the `depends_on` link's `valid_from` (or `state_since`) for `blocked`, and `attention.since` for `quiet`. Card ages are read from `status_since` | code |
| `check_in`, `check_in_since` | `reported` · `verified` · `founder_word`: a "done" from the founder or an agent, and what proved it (§5.1) | admission |
| `expectations` | `exp_` objects (§4.3) | L2 · founder; dates by tools |
| `dates` | `{formal_deadline, notice_date, decision_deadline, prep_lead_days, escalation_at, verify_by}`, each `{date or instant, basis: stated \| tool, quote and evidence id, or tool id}`. Indexed for P1's clock | tools; stated dates quoted |
| `stated_dates` | Every date said in the evidence: `[{what (deadline, renewal, window, slot, cohort), at, quote, evidence_id, said_at, valid_to, replaced_by}]`. When a later mail restates the same event with a new date, code proposes a `replaces` link; once L2 confirms it, the old entry's `valid_to` is set, and it is never overdue or a conflict | L2, checked verbatim |
| `done_when` | The closing condition in evidence terms: `[{event kind (mail_from, meeting_held, document, portal_status, payment, our_sent_mail, founder), party, source}]`, plus text | L2, checked: each named party was printed |
| `outcome`, `outcome_ref` | `succeeded` · `failed` · `missed` · `declined` · `withdrawn`. `outcome_ref` is a member event id matching `done_when`, a DecisionObject or founder decision id, a verified execution outcome's id, or `{exp_id, coverage_ref}` for a missed or closed expectation | admission |
| `wake_on` | `[{mail_from: party, address or domain}, {at: local instant}, {event: meeting end, situation change}]`. P1 reads it | L2 · code |
| `attention` | `{band: now · soon · quiet · ignored, score_bp, reason, since}` (§5.2) | code · founder |
| `recurrence` | For repeating work: `{cadence, anchor, last_occurrence, next_due}` (§5.6) | L2 · code |
| `approver_party`, `blocked_on` | Who must approve; what it waits on (party or decision ids). Both queryable across situations | L2 with evidence |
| `parent_work_id`, `merged_into` | — | admission |
| `fingerprint` | A hash of material member ids since the verdict, expertise versions, the live goal set, founder corrections, settled needs, the expectation rung, the company-page version and the accepted claim ids. A member whose `content_digest` equals an existing member's is not material. P1 compares it before waking a judgment | code |
| `judged_at`, `judged_through` | When it was last judged, and the newest member evidence that judgment saw | code |
| `last_inbound_at`, `last_outbound_at` | — | code |
| `version`, `revision` | Compare-and-set version; the tenant revision it was written in | code |
| `born_by` | `l2_model` (a judgment) · `l2_unit` (a deterministic L2 unit, 0 model calls: a wave, the one-number record, a delivery failure) · `founder` | code |
| `domain`, `domain_state` | The domain that judged it, and `live` or `shadow` from the tenant's activation at judgment time. A shadow situation makes receipts, never cards | code |
| `locked_fields` | `[{field, until}]`, set by founder corrections (§7.2) | founder |

**Whose move, by code.** `whose_move` is the side that owes the newest open ask, question or promise (by `opened_at`). An overdue promise of ours wins: `us`. With no open loop it is `none`. `awaited_party` is that loop's party, and `whose_move_since` its `opened_at`. An L2 value that differs is held (A-5).

### 4.3 · Expectations (`exp_`)

A situation may hold several expectations. Each has:

| Field | Meaning |
|---|---|
| `exp_id` | — |
| `what`, `from_party` | What should happen, and from whom |
| `by` | An **instant** with a time of day. A stated deadline with no time is the end of that local day |
| `basis` | `stated` (with quote and evidence) · `playbook` · `cadence` (cites the party's cadence row) · `founder` · `relative` (with `anchor {event, offset}`; code recomputes `by` when the anchor moves) |
| `if_missed` | `nudge` · `close` · `ask_founder` · `escalate` |
| `on_miss_state` | `investigating` or `decision_ready` |
| `escalate_to` | Party ids |
| `set_at` | — |
| `missed_since` | Set when `by` passes with nothing matching |
| `closed_by` | Evidence id or decision id |

**Rules:**
- **A `by` may already be past when first set.** It is then stored with `missed_since = by`. This keeps `f3`, `i3`, `c1`, `i2` and `b3`: the silences 13 of the 20 ideal cards rest on.
- A later judgment may not move a missed date forward without a new member event or the founder's word. Otherwise the change is held.
- A `by` with basis `playbook` is no later than the playbook's maximum for the stage.
- Every live situation has at least one open expectation, or an explicit `nothing expected: <reason>` (invariant I-14).

### 4.4 · Members and loops

**Members** (`work_members`):
- The member kinds follow the envelope's evidence kinds (§2.1: `mail`, `meeting`, `document`, `screen_moment`, `execution`, `founder_act`, `delivery_notice`, `system_notice`, `chat`, `ticket`), plus `thread`, `party`, `recipient` (for waves) and `claim`. A new evidence kind is data, not a schema change.
- Each member records:
  - `joined_at` and `joined_by` (`seed`, `continuation`, `l2_result`, `founder`), with `writer_ref` and evidence;
  - `left_at` and `left_reason`;
  - `signal_type`, `read_state` and `audience`;
  - for a `thread` member, `thread_state`: `awaiting_us` · `awaiting_them` · `answered` · `closed` · `bounced`, with `since` and the loop ids it rests on, derived by code on each event and nightly.
- **Continuation:** a new mail joins the situations holding its thread only if code finds all three: every outside address or domain in its headers and `body_new` is already a party of that situation; `body_new` holds no introduction cue ("introduce", "intro", "meet", a new cc); and L1 gave it no `relationship_change` or introduction signal. Otherwise it goes to placement (L2). That is how a new introduction inside an old thread becomes its own situation.
- **A mail may belong to several situations.** Each situation keeps its own reading as separate links (§4.6), so no reading overwrites another.
- **A first mail from an awaited party** (an address or domain named as `awaited_party`, or in `wake_on`, of an open situation) goes to placement with that situation proposed first (`waiting_for`, §12).
- **A placement result** carries a reason and the evidence ids printed. One without a reason is held (A-10).

**Loops** (`open_loops`, adapted):

| Field | Meaning |
|---|---|
| `loop_id` | Stable; the id a commitment is cited by |
| `kind` | `question` · `ask` · `promise` · `condition` ("come back when…") |
| `owed_by`, `owed_by_party`, `awaited_party` | `us` · `them` · `third_party`. **Code checks it against the opening event:** a question or ask opened by their inbound is owed by us; one opened by our outbound is owed by them; a promise is owed by its sender. A disagreement is held |
| `promisor`, `counterparty` | Party ids |
| `text`, `quote`, `span` | The words copied from the opening item's new text, checked verbatim, with offsets. A paraphrase is held |
| `due_text`, `due_at`, `due_basis` | The due date as stated, resolved by a tool with its basis |
| `expected_by`, `expected_basis` | Every open loop has one: stated, or computed from the party's cadence or the playbook |
| `asks_for` | For a question: `{metric, wants: current \| projection \| any}` |
| `repeat_of` | An earlier loop asking the same thing |
| `condition_text`, `set_by`, `satisfied_when`, `met_by`, `met_at` | For a condition: the party that set it, what would satisfy it, and the evidence when met |
| `status` | `open` → `answered` · `replied_not_answered` · `kept` · `kept_late` · `released` · `broken` · `superseded` · `moot` · `met` · `lapsed` |
| `opened_by_event`, `opened_at` | — |
| `closed_by_event`, `closed_by_result`, `closed_at` | — |
| `coverage_ref` | Required for `broken` or a miss: the sources, mailboxes, window and completeness |
| `work_id` | — |

**Who settles a loop:**
- **A mail settles it only when it is:**
  - a member of the same situation;
  - later than the opening;
  - from the side that owed it.
- **A question is `answered` only when** the closing mail's quoted span holds what was asked, through an `answers` link with the span. A question with `asks_for.metric` is answered only by an admitted **achieved** claim of that metric. Otherwise the status is `replied_not_answered`. This is `i2`.
- **A founder decision** may settle a loop. So may an execution outcome in state *verified*, never *reported*.
- **A condition is `met`** only through an L2 result that cites a member event dated after the opening and matching `satisfied_when`. Company-level facts (§10.2, audience 5) wake the situations holding open conditions on their topic.
- **Nothing else settles a loop:** a meeting, a bounce, an unread archived mail, or "a reply exists" (that last one is only a hint).
- **A bounce makes the loops waiting on that recipient from that send `moot`.** The bounce notice is cited, and a loop owed by us opens: "re-send to a working address" (`i5`, `c1`), except for an address of kind service or no-reply, or a send older than the situation's `stale_after`, which are recorded on the party only (P4 07 §11).
- **Meetings owe a follow-through.** For every meeting that is past, not cancelled and has an outside attendee, code opens an `ask` owed by us: "follow-up after <meeting, local date>". It is due one working day after the meeting ends.
  - It is `kept` only by our outbound to an attendee, or their domain, after the meeting ends. It is released by the founder. A `fulfils` link joins it to what kept it: the mail, the decision or the task.
  - **A decision is recorded** after a meeting when a founder decision of kind `approve`, `choose_option` or `answer`, or a decided DecisionObject, is dated after it (`meetings_without_decision`).
  - A meeting alone cannot make a situation `resolved`. This is `i3` and `b2`.
- **A renewal or any decision owed by us** is a loop due on the decision date (the day before the renewal). A passed due date never closes a loop owed by us (`c2`).

### 4.5 · Claims, numbers and conflicts

**Claims** (`company_claims`):

| Field | Meaning |
|---|---|
| `text` | Verbatim, from `body_new` of the mail that said it |
| `said_by` | `us`, or the introducer's party id when a third party said it for us |
| `topic` | `traction` · `customers` · `team` · `funding` · `product` · `positioning` · `milestone` · `other` |
| `metric`, `value_text` | — |
| `amount_minor`, `currency`, `period` | Normalised by code: `month` · `year` · `total` · `none` |
| `modality` | `achieved` · `projected` · `target` · `unknown`. Proposed by L2, checked by code against cue words in the quote ("expected", "projected", "nearing", "target", "reached"); a disagreement is held |
| `said_in`, `said_to`, `said_at`, `quoted` | `said_to` holds every recipient |
| `work_id`, `writer` | — |

**Comparing claims (code):**
- Compare within a metric family; MRR and ARR are one family, with ARR ÷ 12 noted. Include third-party paraphrases.
- Each pair is one of four things:
  - `same`;
  - `growth`: a later actual above an earlier actual;
  - `projection`: either side projected or a target;
  - `contradiction`: the same tense and period, with values that differ beyond rounding.
- Only a contradiction opens a conflict.
- **For drafts and checks, a metric is also `conflict_open`** when two or more distinct values of its family were told (growths and projections included) and `verified_claims` holds none. Drafts get the placeholder, and `company_checks` counts it, until the founder picks; the pick ends both.

**Conflicts** (`discrepancies`, adapted):
- Each conflict holds its sides: the value, quote, evidence id, recipients, date and authority of each.
- Its state is `open`, `ranked` (sides of unequal authority, §2.5) or `resolved_by(decision)`. On resolution its `contradicts` links get `valid_to` = the decision time, with the reason `resolved_by <dec_id>`.
- **GeniOS never picks a side.** The founder's answer becomes the current value with founder authority. The other values are superseded and linked to the decision. The company page's `verified_claims` updates.
- Every situation whose next step or draft needs that number has a `depends_on_fact` link to the conflict. Admission writes it when a page's next step or draft names a `conflict_open` metric (the placeholder), or when L2 names the conflict. When the conflict is settled, code marks those situations for re-judging and their open drafts as stale.

**One "one number everywhere" situation per tenant,** with a stable id.
- Every newly admitted claim of a metric joins it as a member, on every run, Evolve included. No card is made per recipient. This is `p1`, which grows on 27 Oct.
- Opening a conflict is offered as news to the one-number goal (P1's `news` trigger, §10.2), so goal reasoning (P4-6) forms or joins that goal.

**Drafts use only settled facts.** Any company number in a card's headline, recommendation, steps or draft must equal that metric's current settled value. If the metric is `conflict_open` or has no value, code puts in the placeholder `[one verified <metric>]`.

**What they already have from us:** `claim_recipients(party)` returns, for any party, each item with its dates:
- every claim value received (metric, value, modality, `said_at`, `said_in`), the latest per metric first;
- each positioning statement sent, with its send dates and count;
- the documents sent, the waves the party was in, and the milestones told (§3.4 `told_to`);
- repeated content: a paragraph of 40 or more words found in two or more of our mails to the party, with dates and count (by code).

**`settle_text(text, as_of)`** returns the text with every company number that differs from its metric's settled value replaced by the placeholder. Cards (P5) and drafts (P1-5) call it before anything is shown or sent.

### 4.6 · Meaning links (`intelligence_links`)

**The closed vocabulary.** It is Atlas's list plus the work object's:
- `depends_on` · `affects` · `owned_by` · `approved_by` · `committed_to` · `due_on`;
- `supersedes` · `contradicts` · `supported_by` · `derived_from` · `part_of`;
- `competes_with` · `resolved_by` · `verified_by`;
- `answers` (with `answered` or `not_answered` and a reason) · `fulfils` · `replaces`;
- `evidence_for` · `serves` · `duplicate_of` · `same_topic` · `depends_on_fact` · `moot` · `about` (a situation → an evidence node it is about).

Admission refuses any other word (A-26), including `causes` and `related_to`; a causal claim belongs in the interpretation, as a hypothesis. `blocks` is accepted as an input word and stored as `depends_on`, reversed (D-P2-19).

Each link carries:
- `from_ref` and `to_ref`, over events, loops, claims, values, situations, goals and parties;
- `writer` (a rule name, an L2 result, a correlate run, or the founder) and `writer_ref`;
- `evidence_ids`, never empty;
- `epistemic_status`;
- `valid_from` and `valid_to`.

A link is ended with `valid_to` and a reason, never deleted. Links are kept apart from `graph_edges`: conclusions never share a column or a scale with evidence.

**Typical links:**
- `fulfils`: our update → the promise loop (`i1`).
- `answers` with `not_answered`: our generic update → the investor's traction question (`i2`).
- `replaces`: a moved meeting's new time → its old time. The old value's `valid_to` is set, so it never becomes a conflict or an overdue card.
- `evidence_for`: the incubator's review → the accelerator situation (`i1`).
- `depends_on` (written from "X blocks Y" as Y depends on X): across departments and owners. The dependent situation's dossier prints "blocked by <situation> since <date>: <why>".

### 4.7 · Versions: what a page holds (`work_item_versions`, append-only)

Each admitted change writes **one** interpretation row. Nothing updates a version row.

| Part | Content |
|---|---|
| `summary` | What is true now, at most 3 sentences, for the founder |
| `facts` | `[{text, refs [{evidence_id, start, end, quote}], status: observed}]`: each fact points at its exact span (A-2) |
| `inferences` | `[{text, based_on (fact or evidence ids)}]` |
| `hypotheses` | `[{hyp_id, text, status open · confirmed · refuted, needs}]`. Changes status only with new evidence |
| `unknowns` | `[{unk_id, text, changes (the decision or field it changes), settling_source (a source from the list, or "the founder"), owner (party, or "not visible to GeniOS"), by, need_id}]` |
| `frame`, `rival_frames` | The reading the verdict rests on, and the alternatives |
| `expected_vs_actual` | `[{expected: {item_id, pack_hash, label}, actual: fact or evidence id, gap}]`. The expected side is a reference, never the norm's text (A-29) |
| `consequences`, `intervention_mode` | As Atlas's ReasoningResult |
| `best_next_move` | `{what, owner (founder · team party · agent), due {at, basis}, done_when [{event kind, party, source}], state (open · done · overdue), delegated_to, handover_state}`. Code sets `overdue` past `due.at`, and `done` only on matching evidence or `founder_word` |
| `plan_candidate` | `{plan_id, steps, owner_recommended}` for L4. It creates no obligation, and links to the L4 `exe_id` once executed |
| `decision_need` | `{state: none · required, reason}`. When required, a DecisionObject is minted (§7.1) |
| `evidence_need_ids` | The EvidenceNeeds this version raised or still waits on (§9.3) |
| `confidence` | Six dimensions (§9.4), **computed by units**, each with the tool id that computed it and a reason when not strong |
| `surface` | `{lane: decision · investigation · conflict · question · waiting · monitor · suppress, why_not, resurface_when}`. `why_not` is closed: `below_gate` · `shadow` · `rolled_up` · `waiting_on_them` · `snoozed` · `duplicate` · `already_handled` (set by L2, P4 07 §7.3) · `budget` · `cooldown` · `muted` (set by L5 on every card it does not deliver). Appended by P5-1 through admission, as `rule:p5-surface` |
| `prediction_ids` | Predictions made (§7.5) |
| `expertise_refs` | `[{item_id, plane D, R or company (a pattern or Behavior id, with `computed_at`), version or pack hash, review_state}]` printed and cited |
| `tools` | `[{tool_id, name, version, value, input evidence ids}]`, exactly as printed in the dossier |
| `evidence_ids` | Everything it cites. Each id was printed to the run that wrote it |
| `changed_fields`, `why_changed` | `[{field, from, to}]` for every field that changed, and one line saying what changed and why |
| `fields_after` | The typed fields of §4.2 as they stood after this change (expectations, dates, stated dates, `done_when`, whose move, stage, state, materiality), so `page(work_id, v)` reads any earlier version whole |
| `caused_by_at`, `trigger` | The instant of the newest evidence the change rests on; what woke the run (`new_evidence`, `date_rung`, `goal_changed`, `founder`, `news`) |
| `as_of`, `known_at` | The instant judged for (`judged_through`); the run's eval instant. Never the wall clock |
| `provenance` | `{run_id, model_id, prompt_version, schema_version, snapshot_revision, code_sha, pack_hashes, model_calls}`. A version's validity (its `as_of` to the next version's) is a derived read, never written to the row |
| `writer`, `writer_ref` | `l2_result` · `founder` · `l4_record` · `rule:<name>` |

**Stage history** (`changed_fields` includes `stage` or `state`) is readable as a list from version rows alone. So is each replay day's changes.

**An unchanged answer writes a receipt and no version.** So does an abstain. A delta updates only its named fields and inherits the rest (Atlas's 14 outcomes, §11.1).

**Size.** A version row holds conclusions only: at most 8 KB, evidence ids excluded (I-27).

### 4.8 · Waves: one send to many

A broadcast is one situation of kind `wave`, made **by an L2 deterministic unit from code's proposal**.
- Code proposes it when the same `template_key` goes to 3 or more recipients within one local day. `template_key` is a digest of `body_new` with the greeting line, the signature, recipient and company names, links and quoted text removed, lower-cased; personalised copies of one template share it.
- Later sends of the same template to an overlapping audience join the wave as new **rounds**, so a prospect wave sent in three batches stays one wave (`s2`; D-P2-21).
- Its members are recipients: `work_members(kind = recipient)`, each with:
  - `delivery`: `delivered` or `bounced` (with the notice);
  - `reply`: the reply event, or none;
  - `last_personal_exchange`;
  - `recipient_work_id`.
- Its counts (sent, delivered, replied, days since) are code facts.
- A later broadcast with the same template adds to the same record.
- An answer per recipient (which still matter, `i4` and `s2`) is written onto each recipient member, and onto that recipient's own situation.
- The wave stores `sent_on`, `body_digest`, `template_key`, its size and `rounds [{date, template_key or tailored, size}]`. L2's placement may also join a batch to the wave as a round: a later batch of the template to a new audience, or tailored sends from one sender with one intent within 3 days (marked `tailored`). Code's own proposal stays D-P2-21's.
- Each prospect party gets a `pursuit_stage` (`pitched`, `replied`, `in_conversation`, `pilot`, `paying`, `silent`, `closed`) with `stage_since`. These words are Plane D vocabulary like the ladders of §4.10 (P3 07 §2.5): admission checks the word against the loaded pack, with no schema check. Company-milestone kinds (§3.4) and claim topics (§4.5) stay Notebook-generic, because they describe the company whatever its domains.

### 4.9 · Higher-order situations

The Notebook answers `open_situations_sharing(field, value)` for an approver, a blocker, a party, a goal, a `topic_key` or a situation type, returning each situation's wait age and nearest date. When two or more live situations with different anchors share both a `topic_key` and a situation type, code offers them as `same_topic` candidates.
- Only L2 may create a higher-order situation from these candidates. Its members link `part_of` and keep their own state.
- With P5, the members' duplicate escalations are suppressed, with `why_not = rolled_up`.

### 4.10 · Stage ladders

A situation's `stage` is a word from its kind's ladder. Ladders are data owned by Plane D (P3 [07](../P3-PLANE-D/07-THE-PLANE-D-SPEC.md) §2.5, authored in P3-3), never Notebook code; admission checks the word against the loaded pack. The founder office's three, as P3 defines them:
- **introduction:** `offered` · `accepted` · `booked` · `held` · `followed_through` · `stalled` · `declined`;
- **application:** `started` · `incomplete` · `submitted` · `under_review` · `interview` · `accepted` · `rejected` · `withdrawn` · `in_programme`;
- **investor:** `first_contact` · `first_call` · `partner_meeting` · `diligence` · `term_sheet` · `committed` · `passed` · `reconsideration` · `silent`.

Every stage keeps `stage_since`. `stage_counts(scope, as_of)` counts situations by stage, with ids (§12). A tile may group stages under one display word, as data beside the ladder: "talked" = `first_call` to `term_sheet`; "live" = `under_review` or `interview`; "in" = `accepted` or `in_programme`; "booked" = `booked`, `held` or `followed_through`; "open" = `offered` or `accepted`; "other" = every stage the tile does not name. **These names are the contract between P2 and P3:** P3-3 authors the ladders with exactly these words and renames the existing playbooks' stages to them. Prospects use `pursuit_stage` (§4.8).

## §5 · The lifecycle

### 5.1 · States (Atlas III.3, owned by L3)

`candidate` · `held` · `rejected` · `investigating` · `awaiting_evidence` · `monitoring` · `decision_ready` · `decided` · `executing` · `blocked` · `verifying` · `resolved` · `reopened` · `superseded`.

`candidate`, `held` and `rejected` are states of a proposal in the admission ledger (§11.4); a `work_items` row exists only once admitted (§4.1). **Live** means a `work_items` row that is not `resolved` or `superseded`; quiet work is live. The founder's five words map onto these: **live** is a live state that is neither waiting nor dormant; **waiting** is `monitoring` with `whose_move = them` or a date ahead; **dormant** is a live state with `attention = quiet`; **done** is `resolved`; **history** is `resolved` or `superseded`, read as past cases (block H).

| Transition | Caused by |
|---|---|
| candidate → held / rejected / investigating | admission's verdict on a new-situation mutation |
| held → candidate | new evidence (a HOLD raises an EvidenceNeed) |
| investigating ⇄ awaiting_evidence | an EvidenceNeed raised; met or unavailable |
| investigating → monitoring | nothing to decide yet: waiting on them, or on a date |
| monitoring → investigating / decision_ready | an expectation missed (the rung's `on_miss_state`, applied by rule with 0 model calls) |
| investigating → decision_ready | terms known; L2's `decision_need = required` |
| decision_ready → decided | a founder decision (§7.2) |
| decided → executing | L4 writes the ExecutionObject |
| executing ⇄ blocked | a dependency fails; unblocked |
| executing → verifying | actions done |
| verifying → resolved | `outcome_ref` is evidence: a member event matching `done_when`, a decision, or a *verified* execution outcome |
| verifying → executing | the outcome is not evidenced |
| investigating · awaiting_evidence · monitoring → resolved | a member event matches `done_when`; or a stated deadline passed (the deadline rule below) |
| monitoring → resolved | an `if_missed = close` expectation passed: outcome `missed` or `withdrawn`, `outcome_ref = {exp_id, coverage_ref}` |
| any live state → resolved | the founder's `drop` (outcome `withdrawn`), or the founder's word where no connected source can show the outcome (`founder_word`); `outcome_ref` is the founder decision id |
| decision_ready → monitoring / investigating | the founder's `later` or `not_now`; new evidence that changes the terms |
| decided → investigating | the founder withdraws the decision |
| resolved → reopened → investigating | an L2 `reopen` mutation citing the contradicting member (never a new situation) |
| any → superseded | merged into another (admission, from L2) |

**The rules:**
- **Admission refuses any transition not in this table** (A-6).
- **Reopening is L2's.** A contradicting mail, or the awaited party writing after an auto-close, joins as a member and wakes the situation (`wake_on`). Only an L2 `reopen` mutation reopens it.
- **`resolved` needs `outcome_ref`.** A status click or activity alone never resolves. This is invariant I-15.
- **Whose move is separate from state.** "Waiting on us" and "waiting on them" are `monitoring` or `investigating` with `whose_move`.
- **A founder's "done" tap writes `check_in = reported`.** It waits for proof before `resolved`. When no connected source can show the outcome, the founder's word closes it, marked `founder_word`, with a reason (D-P2-18).
- **A situation bound to a stated deadline is resolved on the first pass after it.** It is `succeeded` if a member matches `done_when` by the deadline. It is `missed` if the source that would hold it was read in full. Otherwise it becomes a founder question. This is `f2` on 24 Oct.

### 5.2 · Attention: prioritise, decay, ignore (Rohit's lifecycle words)

`attention.band` is one of four values:
- `now`: needs a person today;
- `soon`: this week;
- `quiet`: live, no card;
- `ignored`: the founder said so, within the suppression's scope.

**What moves it:**
- **Prioritise.** Code wakes a re-judgment of importance when:
  - a linked goal becomes at risk or blocked;
  - the situation gains 3 or more members since importance was set;
  - an `evidence_for` or `blocks` link arrives.
- **Decay.** Attention falls with time since the last material change, but only where nothing is owed by us. A read, `lower_now(viewer, as_of)` (§12), lists "lower now, still open", each with its next date and reason.
- **Ignore.** The founder's suppressions (§7.2) set `ignored` within their scope, until their date. Materially new inbound evidence ends a suppression early, and says so.
- **Improve (refresh).** Code clears `judged_through` when:
  - a member's text is recovered or promoted;
  - a founder answer cites the situation;
  - a newly connected source places items in it;
  - it absorbs a merge.

  The next version says what improved.

### 5.3 · Quiet work (what used to be "dormant")

A timer **never** quiets a situation while either of these holds:
- **We owe it something:** it holds an open loop owed by us, or a stated deadline ahead (`s1` stays live).
- **The other side left a door open in writing,** for example "keep us posted", "re-apply next intake" or "send us an update". The situation stays `monitoring`, with an expectation. The open door is an open loop of kind `condition` (or `ask`) whose quote is their written offer; quiet is refused while one is open.

Otherwise:
1. A situation linked `advances` or `depends_on` to a live or proposed goal goes on Maintain's review list.
2. When the playbook's stop rule for its kind and stage passes, the clock asks L2 one question: "close, or one last move?" (U13-24).
3. Only where no playbook applies, 90 days with nothing owed by either side sets `attention = quiet`. The rule that fired is recorded by name.

**Quiet work stays reopenable.** It re-opens on two things:
- new evidence of its own;
- a company-level fact that answers one of its open loops (a new positioning, a verified number, a milestone).

The new version names the fact and its source (`s1` re-opens as v2 when a newer positioning adds what it lacked).

### 5.4 · Leases (the Adaptive brain)

A lease (`learned_brain_entries`, `brain = adaptive`, adapted) holds:
- `kind`: `priority` · `timing` · `snooze` · `auto_close`;
- text, reason, the situation, `set_by` (`founder`, `l6`, `code`) and `starts_at`;
- `expires_at`, or `expires_on_event` (a meeting's end, mail from a party);
- `on_expiry`: `raise` · `close` · `recheck`.

P1's date index reads `expires_at`. Every Adaptive entry expires.

### 5.5 · Staleness

Maintain marks a fact stale when `now − last_confirmed_at > stale_after`. A stale fact is printed as stale, and never outranks a fresh one.

### 5.6 · Recurring work

Work the company repeats (a weekly report, a regular investor update, a recurring filing) is one situation with `recurrence`. Each occurrence is a member. Code sets the expectation from the cadence, so a missed occurrence is noticed. Code proposes a recurrence when three or more outbound mails or situations with one `template_key` go to one audience at intervals within 20% of their median; L2 admits it. `recurring_work()` (§12) lists recurring work for delegation to an agent.

## §6 · Goals

### 6.1 · The goal object (`company_goals`, 0254, adapted)

Start from 0254's fields and keep them: `goal_id`, statement (at most 200 characters), status lifecycle, source, department, `owner_seat`, metric, target, deadline, `parent_goal_id`, `subject_ref`, `evidence_refs`, `approved_by`, `approved_at`. Then add:

| Field | Meaning | Written by |
|---|---|---|
| `goal_kind` | `umbrella` (any of several counterparties can satisfy the end) or `door` (one counterparty's own decision door, §6.2) | L2, checked by code |
| `category` | One of the tenant's categories | L2, checked |
| `door` | The party or situation whose outcome reaches the goal. Two proposed goals with the same door are merged, keeping the earlier id | L2, checked by code |
| `target` | `{kind: number · count · state, value, unit, quote, evidence_id}` | L2, verbatim-checked; founder |
| `target_by` | A local date, with basis `stated` (quote) · `founder` · `not_set` · `not_in_your_mail`. P1's date index reads it | L2, checked; founder |
| `captured` | The moment of commitment: a verbatim quote and its source | L2, checked |
| `why`, `proof` | — | L2, quotes checked |
| `scenario` | At most 3 sentences (P4-6) | L2, quotes checked |
| `plan` | 3–6 ordered steps `{text, state: done · doing · next · missed · dropped, planned_by and done_at (both kept; either may be not set), work_id, evidence_id when done or missed}`. A done step's evidence is an admitted member of a linked situation, dated on that evidence's date. A `doing` step names its `work_id`, or it is a counted gap | L2, checked by code |
| `truth_source`, `truth_source_state` | The system of record its truth needs (billing, bank, CRM, a portal), read from `sources` | L2 · code |
| `health` | `on_track` · `at_risk` · `blocked` · `unmeasured` · `done`, with a reason line. This is not 0254's lifecycle status. `done` only when `outcome` is `achieved`; `unmeasured` when progress is unknown and no missing source or pending founder decision explains it. The one-number goal stays `blocked` until `verified_claims` for its metric has `picked_by` and a verifying source in state `full` | code by rule (P4-4); the model writes the reason |
| `progress` | `{method: outcome · steps · unknown, value_bp or null, reason when unknown: missing_source {name} · no_target · not_counted {why}}`. Never 0 without a count. Each change writes a `goal_progress` row `{goal_id, as_of, method, value_bp or null, unknown_reason, counted_ids or evidence_ids, cause, tool_id}`; `company_status(as_of)` reads the latest row at or before T | code |
| `progress_line` | Built by code from counts ("4 of 5 programme steps done") | code |
| `activity` | Counts by the state of linked situations (talked, passed, silent since, booked, waiting), shown as the count with a percentage beside it ("1 of 28 · 4%"; D-P2-20). Activity never inflates progress, and is never shown as progress | code |
| `next_move` | 1–3 open cards owed by us on linked situations. When nothing is owed by us: the next GeniOS check of the waiting situation (`work_id`, `next_check.at`) | L2, checked by code |
| `gaps` | `[{what, source: situation id · mail id · "source not connected: <name>", since}]`. Ages are computed by code | code (L2 words them) |
| `happened` | Inbound member evidence of linked situations, newest first, each with a date and one checked quote | code |
| `did` | What GeniOS did on linked situations, from admission-log rows and executions: each entry `{what, at, card_id (the card raised from the resulting version, or null), ledger or execution id}` | code |
| `outcome` | `open` · `reached_pending(since, event)` · `achieved(confirmed_by, at)` · `missed` · `abandoned` | admission; founder confirms |
| `questions` | The four: what counts, by when, who owns it, how we will know. Each is `{answer, source (a quote or the founder), answered}` | founder (L2 may propose an answer from a quote) |
| `snoozed_until` | "Not now" | founder |
| `merged_into`, `ended_at`, `end_reason` | — | admission |
| `observation`, `evidence_span` | What suggested it: the first and last evidence | L2 |
| `first_seen` | The month of the earliest evidence | code |

**Every goal change writes a goal version** with the columns of a page version (`changed_fields [{field, from, to}]`, `why_changed`, `caused_by_at`, `writer`, `writer_ref`, and `expertise_refs` for the goal package's units, P3 [07](../P3-PLANE-D/07-THE-PLANE-D-SPEC.md) §4.4) and `cause {situation_stage_change · verified_outcome · founder_answer · founder_edit · l2_result · merge · rule, ref id, date}`. A status, health, progress or outcome change with no cause is refused (A-28).

### 6.2 · Grain: a goal is an end

This follows the ideal and amends the architecture's D10 ("one goal per piece of work"), with Rohit's yes (D-P2-17). A piece of work gets its own goal only when it has its own decision door. If the answer is no, the grain falls back to one goal per piece of work, and the umbrella becomes the optional parent goal: rules 1 and 2 are replaced, and each piece of work (an application, the raise, a hire, a partner) is its own goal of `goal_kind` `door`, with `subject_ref` its judged situation; a broad goal such as the accelerator end is an optional `parent_goal_id`; nesting stays at most one level; rules 3 to 7 stand.

1. **One umbrella goal when any of several counterparties can satisfy the end,** for example "get into an accelerator this cycle". The applications are its situations.
2. **A separate goal only for one counterparty's own decision door** (the reconsideration, `i1`), nested under the umbrella. Nesting is at most one level: a goal whose parent has a parent is refused.
3. **No activity goals.** "Take every intro call" is activity under an end, not a goal.
4. **One goal per subject.** `subject_ref` is set by code, never by the model: for a `door` goal, the judged situation; for an `umbrella` goal, the capability class of its situations (from `expertise_path`, for example an accelerator application). Admission refuses a second open goal for the same (`goal_kind`, `subject_ref`).
5. **Formed from situations and their kinds,** never from counterparty files or brief wording.
6. **Every goal cites at least one act of ours:** our outbound mail, a meeting we held, or an application we filed.
7. **A goal's linked set counts only `advances`, `threatens` or `depends_on` links whose situation is live or waiting.** A channel's housekeeping is counted separately as activity.

### 6.3 · Links

**`goal_situation_links`** (adapted) carry:
- a `relation`: `advances` · `threatens` · `depends_on` · `unclear`;
- `through` (how the situation moves the goal), required unless the relation is `unclear`, and `why`;
- `evidence`;
- `size_basis` (what share of the goal it can move, and why);
- `confirmed` (false while the goal is proposed; such a link is never counted in a live goal's progress or shown on a card, and is promoted when the goal is approved);
- `writer`, `valid_from` and `valid_to`.

There is **one** link set. Pages and relate both write it, and the same link from both writes one row. Every live situation is linked, or listed as "not linked" (counted, never hidden).
- A link is written in the same transaction as the admitted situation (§11.3), and its relation is from the list above (A-26).
- A situation whose only links are `unclear` is listed as not linked.
- When goals merge, or one is dropped, its links get `valid_to`. A merge re-creates them on the survivor in the same transaction; the linked situations' fingerprints change, so they are re-checked.

**`goal_links`** (goal → goal) carry a relation of `depends_on` or `part_of`, with evidence. For example, every goal whose situations state traction depends on "one verified number everywhere".

### 6.4 · Proposal, approval and the one door

- **A goal proposal is admitted by code** (`context/goal_admission`). It is held:
  - when it duplicates a pending or accepted goal, or a dropped or rejected one, for the same `subject_ref` or `door`. A dropped or rejected goal is never proposed again unless the founder reopens it;
  - when it is over the weekly cap (3, or 10 in the first onboarding week, per `07` D3);
  - when it has no evidence of the company's own act.
- **A proposal is rejected** when it names an object that was not printed (A-10).
- An admitted proposal writes a pending brief "goals" line, never an approved goal.
- **The one door.** Confirming a goal anywhere (a card, the home page, the Goals page) calls the one owner-only decide endpoint for its brief line. That flips the line and writes the `company_goals` revision in the same transaction. There is no second route.
- **Confirmed** means status `approved` or `active`, with `approved_by` and `approved_at` from a founder decision (0254's check constraint). A goal is **`approved`** when the founder confirms it with a question still open: it is printed in G-live with that question as its next move (never in G-proposed), its links are confirmed, and its progress and health read "not yet active: <the question>". It is **`active`** only when all four questions are answered: only then do its progress, health and plan steps run.
- **A goal the founder states** (`state_goal`, §7.2) is stored as founder-act evidence and admitted with source `founder`, approved on creation, with its four questions asked.
- **No model change may set** a goal's status, `owner_seat`, deadline or `approved_*`. A target, metric or deadline from L2 is kept only as a quoted proposal.
- **Proposed goals in reasoning (D-P2-13, recommended).** The snapshot prints two separate blocks:
  - **G-live**: "the company's goals";
  - **G-proposed**: "goals GeniOS thinks you are pursuing; not confirmed; never treat as the company's goal".

  A link to a proposed goal is stored with `confirmed = false`, and no card shows it as confirmed. This amends 00-ARCHITECTURE §Goals, with Rohit's yes.

## §7 · Decisions, delegation and the founder's word

### 7.1 · The DecisionObject (L3 → L4, `decision_objects`)

It is minted only when L2 marks `decision_need = required` (GeniOS-008 L3-4). It holds:
- `dec_id`, the situation and its version;
- the question;
- the options, each `{label, cost, time, reversibility, risk, evidence}`;
- the recommendation and why;
- the owner and approver;
- the decision deadline (tool-computed);
- the unresolved items (unknown ids);
- the authority boundary: `{geni_may, human_only}`;
- the state: `open` · `decided` · `expired`.

**The Notebook never creates an obligation.** It holds a *recommended* owner. The *assigned* owner, deadline and ladder are written only from an L4 ExecutionObject or a founder decision. Admission refuses `assigned_*` fields from any L2 mutation.

### 7.2 · The founder's acts (`founder_decisions`)

| Field | Meaning |
|---|---|
| `kind` | `answer` · `approve` · `confirm_goal` · `state_goal` · `edit` · `choose_option` · `done` · `drop` · `not_now` · `later` · `ignore` · `undo` (ends an earlier decision, `dec_id`, with `valid_to`) · `delegate` · `correct` · `feedback` |
| `scope`, `scope_ref` | `situation` · `party` · `sender domain or mail kind` · `goal` · `card` · `company_page` · `address`; and what it applies to (a `work_id`, party id, goal id, domain or mail kind, card id, company-page field name or address) |
| `until_at`, `until_event` | — |
| `reason`, `feedback_scope` | From a closed list for feedback: `not_relevant`, `wrong_facts`, `bad_timing`, `misread_source`, `stale_data`, `wrong_person`, `not_how_we_work`; and the feedback's reach: `this_thread` · `this_kind_of_work` · `how_we_work` |
| `text`, `assignee`, `due_at`, `done_when` | For a delegation: to whom, by when, and how we will know it is done |
| `handover_state` | `proposed` → `approved` → `dispatched` → `reported` → `verified` |
| `dec_id`, `option`, `exe_id` | — |
| `card_id`, `card_version`, `situation_version`, `evidence_ids_shown` | What was on screen when the founder acted |
| `question_key` | For answers |
| `draft_id`, `draft_version`, `draft_text_digest` | For approvals of a send |
| `by` (seat), `at` | — |

**The rules:**
- **A founder correction locks.** A correction to a situation, party, goal, link or the company page writes a version by the founder, and puts the fields it set into `locked_fields`. A later L2 change to a locked field is held as "locked by the founder" and becomes a question. Parties and goals are never overwritten in place.
  - `locked_fields [{field, until}]` sit on situations, `party_profiles`, `company_goals` and `intelligence_links`; a company-page row with basis `founder` is locked. A-11 checks them all.
  - A founder's membership move writes `joined_by = founder` (or `left_reason = founder`), and placement may not move that member again.
- **An answer applies everywhere it belongs:** to the situation and its linked goals (`cause = founder_answer`). The same question (`question_key`) is never asked again, unless new evidence contradicts the answer.
- **Suppressions** (`ignore`, `not_now`, `later`) are respected by every later run within their scope until their date.
- **Message content is only evidence.** Text inside a message can never set an approval, permission, owner, goal status, chosen option or assignment. Those are writable only by `writer = human` or `l4_record`. Dossiers mark message text as untrusted data.

### 7.3 · Delegation and what comes back

- An L4 execution carries `work_id`, `page_version`, `goal_version` and `approval_ref`.
- **An agent's or a delegate's send must match its approval:** it links to an approval of the same draft version, and its new text matches the approved draft. This is invariant I-20.
- **A result that comes back after the page changed materially** is re-checked against the current version before it is kept or sent. Material changes are status, whose move, an expectation, a new `evidence_for` or milestone, or a locked field. Otherwise the result is held as "page changed since the task was given".
- **What comes back is evidence:** the sent item, the outcome and the counterparty's reply. Each passes the same checks as any mail before it settles a loop.
- **Work that needs a teammate's private evidence** gets a task for that seat: "share or act on <kind>".

### 7.4 · Feedback, attribution, and each agent's record

- **Feedback** is stored against the card version, the situation version and the evidence ids shown, with a closed reason, text and scope (`this_thread`, `this_kind_of_work`, `how_we_work`).
- **L6 attributions aimed at L3** are `attributions` rows `{work_id, version, card_version, code, layer: L3, source: l6, evidence_ids_shown, at}`, recorded against the situation and version the user judged. The codes are `wrong_entity_resolution`, `missing_context`, `outcome_changed` and `already_handled`.
- **`agent_track(agent_id, from, to)`** counts, with ids:
  - tasks given;
  - drafts approved unchanged, edited or rejected;
  - verified outcomes;
  - failures.

### 7.5 · Card outcomes and predictions

- **`card_outcomes`** (with P5) keep three things together when a card closes:
  - what GeniOS recommended (with card and page versions);
  - what the founder did;
  - what happened, with its evidence and whether `done_when` was met (`yes`, `no`, `unknown` with a reason).

  Each part carries its date (`recommended_at`, `acted_at`, `outcome_at`) and its evidence or decision id.

  Resolution also records `resolution {path (agent_proven, agent_fixed_by_founder, one_tap, founder_work), reason, rightly_founders}`, so AER and HIR are counted from rows. `reason` is closed, and set only when the path is `founder_work`: `missing_information` · `no_source` · `card_was_wrong` · `agent_step_fixed`. **Resolution is written by rule at resolve time:** `path` = `agent_proven` when `outcome_ref` is a verified execution outcome and the founder did not edit the step; `agent_fixed_by_founder` when the founder edited the agent's draft before approving it; `one_tap` when an approve, choose-option or done carried no edit and no answer; `founder_work` otherwise. `reason`: `missing_information` when a founder answer supplied the fact; `no_source` when it closed as `founder_word`; `card_was_wrong` when feedback marked the card wrong; `agent_step_fixed` when the founder replaced an agent's step. `rightly_founders` = true when the act was `human_only` in the DecisionObject's authority boundary (send, pay, sign, submit, accept an offer, declare a company fact). `aer_hir(from, to)` counts them, with ids, leaving out decisions that are rightly the founder's.
- **`predictions`** hold:
  - the statement and the situation;
  - the card and its version;
  - `by` (a local date);
  - the basis (evidence and pattern ids) and `made_at`;
  - the outcome: `came_true` · `did_not` · `unknown`, with its evidence and `checked_at`.

  A prediction is written when a page sets `if_missed`, or a card is predictive. Maintain scores due predictions. A verified outcome writes a `prediction_actual` row `{prediction_id, predicted, actual, evidence ids, delta}`: the row L6 reads.

## §8 · The four brains

| Brain | What it holds | Where | Who may change it | Promotion rule |
|---|---|---|---|---|
| **Expert** | What any competent professional knows | Git (Plane D, P3) | Human review only | L6 may only open a review item, never write |
| **Organization** | What is true about this company | the company page (§3.4) | The founder: accepted lines, decisions | A proposed line is accepted by the founder |
| **Behavior** | How this company actually works: "you reply to rejections within 0–7 days (4 of 4)", "broadcast updates get no replies; personal notes do" | `learned_brain_entries(brain = behavior)` from `learning_objects` | Code, from counted evidence (numerator, denominator, thread and mail ids, computed_at) | Promoted past a threshold of independent instances (at least 5 distinct situations, set by P4 [07](../P4-PLANE-R/07-THE-PLANE-R-SPEC.md) §12.3) and a governance check. Until then an entry is printed as "observed, n of m" and carries weight only as a labelled prior; a promoted entry that later evidence contradicts is demoted |
| **Adaptive** | What matters most right now | leases (§5.4) | Founder, L6, code | Always expires |

**Persona** is not a fifth brain.
- `preferences` hold the person's own stated preferences: the statement, what it is about, the source quote, who stated it, and a state of `candidate` · `confirmed` · `rejected`.
- A preference a third party states stays a candidate until the person confirms it. Only confirmed preferences are printed as facts.

**Pinned per run.** Each run reads the brains at a `brain_snapshot_id`, never unpinned mid-run (Atlas §II.3). No professional knowledge is ever stored as a company fact. A page sentence that states a norm, threshold or pattern as a company fact is held.

**Learning candidates** (`learning_objects`, adapted) hold:
- the statement and evidence ids;
- the validated count against its threshold;
- the governance verdict;
- the destination (`behavior`, `adaptive`, `organization`, `expert`);
- the state: `promoted` · `review` · `held` · `pr_open`.

A candidate destined for Expert only produces a review file for P3's review sheet.

**Company patterns** (`company_patterns`) hold `{pattern_id, kind (reply_time · stage_duration · move_outcome · recommendation_acceptance), subject, value, n, window_from, window_to, evidence_ids, computed_at, writer}`. Party cadence is a `reply_time` pattern. Behavior entries are the promoted subset. Maintain refreshes them weekly (P4-7's pass, through admission), and block B prints those whose subject matches, labelled "yours".

## §9 · Absence, coverage, unknowns and confidence

### 9.1 · The four kinds of "nothing found" (`situation_absences`, adapted)

| State | Meaning | Example |
|---|---|---|
| `verified_absence` | The whole scope was read; it isn't there | No mail to the fund after the call: Gmail fully read (`i3`) |
| `partial_coverage` | Some sources were seen, not all | The candidate's answer: the hire started on LinkedIn, which only Screen sees (`h1`) |
| `unknown` | Not enough to decide | Real MRR: no billing source is connected (`p1`) |
| `conflicted` | Sources disagree | Four traction numbers (`p1`) |

Each absence finding holds the statement, the state, the scope (the source ids and window read, and whether the search completed), the evidence and the coverage receipt.

**The rules:**
- **No verified absence without full coverage.** A `verified_absence` is refused when any source in scope is partial or not connected.
- **No absence without its coverage.** A loop marked `broken` or `missed`, a "no reply", "no update" or "no decision" is refused without its `coverage_ref`.
- **Weaker wording when coverage is short (HOLD → reworded).** When a change asserts a settled outcome ("declined", "accepted", "rejected", "not sent", "no reply") and the deciding party's channel is partial, unknown or not connected, code keeps the weaker form from a closed table ("declined" → "unknown: may be in <source>"). It logs the change as `HOLD_reworded`.

### 9.2 · Unknowns

Unknowns are `unk_` objects (§4.7). The admission rules:
- an unknown with neither an owner nor a date is held;
- every unknown says which decision or field it changes.

A field that is unknown is stored as `unknown {reason}`, never defaulted.

### 9.3 · Evidence needs (`evidence_needs`, adapted)

| Field | Meaning |
|---|---|
| `need_id`, `work_id`, `raised_by_result` | — |
| `question`, `why` | — |
| `acceptable_sources`, `unacceptable_sources` | — |
| `needed_by`, `owner` | — |
| `status` | `open` · `met` · `unavailable` |
| `met_by`, `met_at` | — |
| `max_cost_usd`, `expires_at` | As the table has today |
| `required_evidence` | The kind, the party and any text span the evidence must hold; a need without it cannot be matched and is refused (P4 07 §8) |
| `time_range`, `fields`, `visibility` | The window to search, the fields wanted, the run's viewer bound (P4 07 §8) |
| `stop_when`, `idempotency_key` | `met` · `unavailable` · `expired` · `budget`; `hash(work_id, question)`, so a repeat raises none (P4 07 §8) |

- **A HOLD raises a need** that names the missing fact (`hold_needs.py`, wired).
- **On each new member evidence,** code matches open needs by acceptable source kind and party (0 calls). A match marks the need met, links it, and wakes the situation through P1.
- **Archived mail is promoted through a need,** so L1 never reads the Notebook (§2.3).

### 9.4 · The confidence vector (Atlas §A.4)

| Dimension | Computed from (by units and code, never asserted by the model) | If weak, the card must… |
|---|---|---|
| Evidence | the count and authority class of the evidence | cite sources inline; move to investigation |
| Frame | the frame's support against rival frames | show the rival frame |
| Temporal | each expectation's basis: stated → strong; playbook or cadence → medium; none → weak | not state a deadline as fact |
| Causal | hypothesis status | state the cause as a hypothesis |
| Authority | owner and approver evidence, `kind_basis`, founder confirmation | ask who owns it; never guess an approver |
| Coverage | the coverage receipt (§2.6) | say what was not checked |

**How it is stored and used:**
- Each dimension is `strong` · `medium` · `weak`, with a reason when not strong and the id of the tool that computed it (P4-3's calculators; A-8).
- Cards show Temporal as "Timing" and Causal as "Cause".
- The situation's confidence is its **weakest** dimension, never a blend.
- Removing confidence from the model's answer schema also frees grammar room (N8).
- **Causal and coverage never block a card;** they change its wording.

## §10 · Correlation, and facts that travel

### 10.1 · Correlation is joins only

Inside the Notebook, correlation is deterministic joins. The joins are:
- same thread;
- same party or organisation;
- same meeting attendees within a window;
- same message id across sources;
- same document;
- same address.

They are stored as join rows with `derived_from` (§1). A join makes no situation and no conclusion, and its writer cannot write the intelligence tables (guard 1). Analytics (cadence, trends, patterns) live in P4-7's module and are stored as derived facts with `derived_from`. **Meaning is never computed by a join.** Code's comparisons of claims (§4.5) and its wave proposals (§4.8) are proposals to L2, or deterministic facts. They are never conclusions about intent.

### 10.2 · Facts travel (P2-6)

A **milestone** is an admitted stage change, a status of `resolved`, a decision, or a company milestone (§3.4). Code offers it, dated and with its source, as a candidate `evidence_for` to five audiences:
1. **situations of the same goal;**
2. **linked situations;**
3. **situations of goals that depend on its goal** (`goal_links`);
4. **by need:** every open situation with an open "update owed" loop, or a "re-contact with a new fact" next step, receives the company's milestones from the last 30 days that are new to that party (no `told_to` row for it, §3.4);
5. **company-level:** a new company-page version (positioning, verified claims, a milestone) is offered to situations in any state whose open loops owed by us share its topic or metric.

It wakes them through P1's `news` trigger. The receiving version records the `evidence_for` link and cites where the fact came from.

This is how the incubator's review reaches the accelerator's page (`i1`).

**Along parties.** A party fact is stored once on the party, with its date and evidence: an address bounced, a working alternative found, on leave until a date, left, changed role or company (`availability` and affiliations, §3.1). Every live situation with that party sees it in its next dossier.

### 10.3 · Dependents

`dependents(work_id)` returns the linked situations, the situations of the same goal and the situations sharing a blocker. P1-4 marks them dirty and re-runs to a fixed point, with an iteration cap of 3. Non-convergence writes a receipt.

## §11 · Admission: the one door in

### 11.1 · What arrives

| Source | What it carries |
|---|---|
| **L2 result** | A typed mutation `{outcome, changed_fields, …}`, one of Atlas's 14 outcomes: `no_material_situation` · `new_situation` · `update` · `unchanged` · `evidence_needed` · `monitor` · `decision_ready` · `plan_candidate` · `verify` · `resolved` · `reopen` · `merge` · `split` · `abstain`. `unchanged` and `abstain` write a receipt only. A delta changes only its named fields |
| **L4 record** | An execution and its state, an outcome |
| **Human act** | A founder decision (§7.2) |
| **L1 fact** | Evidence half only, through L1's graph writer |

**What each L2 outcome writes:**

| Outcome | Effect |
|---|---|
| `no_material_situation`, `unchanged`, `abstain` | A receipt only |
| `new_situation` | A `work_items` row and version 1, when complete (A-27) |
| `update` | A delta version: only the named fields change; the rest are inherited |
| `evidence_needed` | `awaiting_evidence`, and an EvidenceNeed (§9.3) |
| `monitor` | `monitoring`, with an expectation |
| `decision_ready` | `decision_ready`, and a DecisionObject (§7.1) |
| `plan_candidate` | The plan stored on the version for L4 (§4.7); no obligation |
| `verify` | `verifying` |
| `resolved` | `resolved`, only with `outcome_ref` (I-15) |
| `reopen` | `reopened`, then `investigating` (§5.1) |
| `merge` | The absorbed situation `superseded`, its members moved to the survivor (§4.1) |
| `split` | New `work_id`s for the parts, with the members partitioned between them. The parent keeps its history, and each part cites the result id |

**The writer must be one of these:** `l1_fact`, `l2_result`, `l4_record`, `l6_record` (L6's attributions, and the leases L6 sets), `human`, or `rule:<name>` for the code rules this file names. The store refuses any other writer, and ledgers the refusal.

### 11.2 · The laws

Each change is judged on its own. Passing changes are kept; a failing change is held as proposed, with its law id and reason.

| Law | The rule | On failure |
|---|---|---|
| A-1 | Every id cited was printed in the run's dossier | REJECT the change |
| A-2 | A quote is word for word in the cited evidence (case, quote marks, dashes, links, list markers and invisible characters folded); served text is cut from the evidence by offsets, and every `{evidence_id, start, end, quote}` reference cuts the same text | HOLD |
| A-3 | A claim about us is in the **new** text of our own outbound mail, or is a recorded third-party paraphrase | HOLD |
| A-4 | A loop closes only as §4.4 says | HOLD + EvidenceNeed |
| A-5 | `owed_by` agrees with the opening event; `whose_move` agrees with the open loops, unless a newer member event is cited | HOLD |
| A-6 | A state transition is in §5.1's table; `resolved` has `outcome_ref` | REJECT / HOLD |
| A-7 | Every date has a basis; a stated date has its quote; a tool date has its tool id; no `judgment` basis. `decision_deadline` and `escalation_at` have basis `tool` unless a quote states them, and a `decision_deadline` equal to `formal_deadline` is held unless a quote states it | HOLD |
| A-8 | A number in a summary, why line or card text matches a printed tool value or a quote ("numbers are code's"); each confidence dimension carries the tool id that computed it | HOLD |
| A-9 | Kind fits the party: a closed table, loaded from Plane D's vocabulary (P3-1), of allowed kinds of work per party kind (government → compliance; candidate → hiring; vendor → vendor; accelerator or incubator → program; investor → investor or program; intro platform → intro …). "A government portal is not a deal" | REJECT and route |
| A-10 | A goal, link, membership, merge, split or parent names only printed objects, and cites evidence. A placement gives its reason | REJECT (HOLD for a missing reason) |
| A-11 | A founder-locked field (on a situation, party, goal, link or company-page row) is not overwritten, and a founder-placed member is not moved | HOLD + question to the founder |
| A-12 | The version read is still current (compare-and-set on the `version` of each row the change updates; the tenant revision read is recorded, §11.3) | write nothing; "stale read" receipt; P1 wake-up |
| A-13 | Audience: a conclusion's audience is no wider than its evidence's | REJECT |
| A-14 | A conflict is never resolved by GeniOS; drafts use only settled values | HOLD |
| A-15 | A pass, rejection or silence is not recorded as final failure when the evidence holds an inbound offer to reconsider or re-apply, or when the stage's "quiet means" line says silence is not a no. The heuristic is logged | REJECT |
| A-16 | Temporary evidence is never cited | HOLD |
| A-17 | Coverage-bounded wording (§9.1) | HOLD → reworded |
| A-18 | A new situation that duplicates an open one (§4.1) | HOLD as `possible_duplicate_of` |
| A-19 | `noise` is not set on a thread with an obligation-class mail | HOLD |
| A-20 | Message content does not set approval, owner, permission, goal status, an option or an assignment (§7.2) | HOLD |
| A-21 | A hypothesis is not confirmed without a new evidence id; a model sentence is not stored as a fact without evidence. A fact with empty evidence ids, or an inference with an empty `based_on`, is held, with the sentence kept in the ledger | HOLD |
| A-22 | A missed expectation is not moved forward without new evidence or the founder (§4.3); a replaced date (`valid_to` set, §4.2) is never counted missed or overdue | HOLD |
| A-23 | An unknown has an owner or a date | HOLD |
| A-24 | The Atlas analytics laws carried by the BSO contract today: V-1 to V-10 (cohorts name their population; no trend on noise; correlation is never cause; integers only; every inference cites; completeness needs coverage) | as declared (`REJECT` or `OBSERVE`) |
| A-25 | Publication hold reasons carried today: verified evidence required, identity review required, source coverage insufficient, conflict open, cross-domain contradiction | HOLD |
| A-26 | A link or edge word is in its closed vocabulary (§2.5, §4.6, §6.3). `blocks` is rewritten as `depends_on`, reversed (D-P2-19) | REJECT |
| A-27 | A new situation is complete: title, kind and its basis, a situation type or "no authored type", department, stage, state, at least one member, evidence ids, `done_when`, and an open expectation or "nothing expected: <reason>" | HOLD with `missing_field`, and an EvidenceNeed naming it |
| A-28 | A goal version that changes status, health, progress or outcome names its cause `{kind, ref, date}` (§6.1) | REJECT |
| A-29 | A fact or inference rests on evidence ids, never only on an expertise or pattern reference; no norm, threshold or pattern is stored as a company fact (§8) | HOLD ("norm stated as company fact") |
| A-30 | An owner or approver role, or an `owned_by` or `approved_by` link, rests on a quote that assigns it or on a founder act (§3.1) | HOLD; the page says "no accountable owner found" |
| A-31 | A current fact or inference does not rest only on another situation's evidence (block H). A past case is cited as `work_id@version` | HOLD ("a past case is not proof") |
| A-32 | A new situation's department is switched on in the company page | REJECT |

**Every phase that admits model output** writes a held row for each refused item: company, parties, placement, judge, relate and goals. Nothing is filtered silently.

### 11.3 · How it is written

- **Everything admitted for one situation is written in one transaction:** the situation row, its interpretation, members, loops, links, claims and goal links.
- **Compare-and-set:** `update … where version = <the version read>`, on each row the change updates (the situation, and a goal or link it changes). The tenant revision the run read is recorded with the receipt, not compared, so judgments of different situations never refuse each other. If no rows change, nothing is written.
- **A failed run admits nothing.** A run that times out, is cancelled, or returns output that does not fit the schema writes no version and one receipt with the reason. Only law failures inside an otherwise valid result are admitted change by change.
- **Idempotent:** the same request id and bundle hash give the same verdict and no second situation.
- **Each change increments the tenant revision** (`graph_versions`). Rows are stamped `admitted_in_revision`.
- **Receipts never raise.** Each row is written in its own savepoint, so one bad row never fails the pass. A receipt row that fails to write is recorded as an error row (run id, row kind, reason).

### 11.4 · The admission ledger (`situation_admission_decisions`, adapted)

Each ledger row records:
- `at` and `run_id`;
- the subject;
- `op`: `create` · `update` · `merge` · `split` · `link` · `close` · `claim` · `goal` · `party`;
- the proposal, exactly as proposed, as a typed change record `{field, value, evidence_ids, law_id}`, never raw answer text (§12.4);
- the verdict: `ADMIT_create` · `ADMIT_update` · `ADMIT_merge` · `ADMIT_link` · `HOLD` · `HOLD_reworded` · `REJECT`;
- `law_id`, `missing_field` and `duplicate_of`;
- a reason of at most 120 characters;
- the resulting version.

There is one row per candidate **and** per change, admitted ones included.

**Every pass also writes a receipt** that counts:
- whether it was asked (a pass over zero candidates says `asked = true, candidates = 0`);
- candidates;
- admitted;
- held, by reason;
- rejected;
- unchanged;
- evidence placed in no situation;
- declared silences, each `{kind, reason, mover (the party or layer that must act), since}`;
- the ids of situations formed, decisions emitted and situations resolved (`situations_formed`, `decision_emitted`, `resolved`).

## §12 · Reads: the one door out (`context/notebook_api`)

Every read requires `org_id` and `viewer`, and filters by the viewer's audience. Every read is bounded and versioned, and takes `as_of`.

| Read | Returns |
|---|---|
| `snapshot(seeds, edge_types, states, window, max_hops=2, max_nodes≈60, max_expansions=2, max_primary_evidence=25, max_excerpts=12, include_unknowns, include_contradictions, include_history, viewer, as_of)` | `{revision, blocks, cut receipt}`. Immutable at its revision. Every empty block says why (`not connected`, `none found`, `cut`, `not authored`). The run receipt lists missing inputs |
| `page(work_id, version?)` | The page as of a version |
| `still_open(work_id, since_version)` | `{open, unchanged, current_version, outcome_ref}`, one indexed read, for P1 and L4 before every rung and send |
| `due_dates(from, to)` | Expectations, stated dates, loop dates, goal dates, lease expiries and `wake_on.at` crossing in the window (P1's date index) |
| `dependents(work_id)` · `open_situations_sharing(field, value)` | §10.3, §4.9 |
| `lineage(card_id)` | Card version → situation version → evidence ids → qualified signal ids → raw event ids, under one `trace_id`, with the card's footer: trace, pack hashes, model calls |
| `why_no_card(subject or evidence id)` | The verdict chain that explains a missing card |
| `citations(evidence_id)` | What keeps it alive (§14) |
| `claim_recipients(party)` · `party_appearances(party)` | §4.5; every situation, goal, claim, loop and card a party appears in |
| `goal_timeline(goal_id, as_of)` | A dated "what happened" across every linked situation, each line cited, with no model call. Lines are `{at, kind (inbound_mail · our_mail · meeting · stage_change · decision · bounce · silence_since), work_id, evidence_id, quote}`, oldest first; `silence_since` is computed by code |
| `company_status(as_of)` | Per department: every goal with its health, progress beside its target, owner and next move; the live situations by state, with whose move, since when and owner. Also `not_linked` (live situations with no `advances`, `threatens` or `depends_on` link to a live or proposed goal, with ids, ages and count), overdue loops and conflicts to decide. No model call |
| `changes(from, to)` | Opened, closed, quiet, woke, stage moved, goal moved, new claimed values per metric, each with its why and evidence |
| `performance(from, to)` | Promises kept, broken or kept late; our median days to answer; follow-ups within 7 days of a meeting; goal steps on time. Each with its ids |
| `meetings_without_followup(window)` · `meetings_without_decision(situation)` | §4.4 |
| `stale_pages()` | Every situation that is not superseded (resolved and quiet included) whose newest member, by `known_at`, is newer than `judged_through` |
| `metrics()` | Every count the dashboard shows from memory, each a named, tested query with numerator, denominator and row ids: parties, relationships, goals by health, open situations, conflicts held, sources connected, threads read, bounces caught, replies owed by party kind, goals and cards per category; meetings by `when_class`, with corroborated held beside; `duplicate_open_cards` (it should be 0); `not_linked`; human touches per resolved situation; calls and cost per admitted situation; the recall of important situations against the private sample (§20.4) |
| `company_checks()` | A fixed list of checks graded `working` · `needs_attention` · `broken`, each with its instances: open conflicts, bounces not re-sent, questions owed by us older than 7 days, missing sources, accepted intros not booked, follow-ups after meetings, agents whose rejected, edited or failed work is above a set share. Also: **behaviour patterns** (each promoted Behavior entry, or `company_patterns` row of kind reply time or move outcome, is a check: `working` when every counted instance in its window meets it, `needs_attention` when recent instances break it, with their ids) and **goals on track** (`working` when no goal is `at_risk` or `blocked`). Each check is a named query with a grade rule: an open conflict is `broken`; for the others, one or more instances is `needs_attention` and none is `working`. The read returns the counts per grade, the share working and the instance ids |
| `context_health()` | People and orgs; facts with a receipt %; fresh in 7 days %; conflicts to decide; sources connected |
| `party(party_id, viewer, as_of)` · `alternate_addresses(address)` | The profile with its typed facts, each with rank, evidence and since, and its receipt and version counts (§3.1); working addresses at the same organisation for a bounced one, each with its source thread |
| `delegates(work_id, as_of)` · `agent_track(agent_id, from, to)` | Team members of the work's department with their availability at `as_of`, and the agents that serve it, each with its approver (§3.3); each agent's record, with ids (§7.4) |
| `waiting_for(party or address)` | Open situations whose `awaited_party` or `wake_on` names it, so its first mail is placed there first (§4.4) |
| `settle_text(text, as_of)` | §4.5 |
| `page_diff(work_id, v_from, v_to)` · `history_of(work_id)` | The `{field, from, to}` changes with `why_changed` and evidence ids; both version chains of a merge (§4.1) |
| `stage_counts(scope, as_of)` | Situations by stage on a ladder (§4.10), for a goal, a kind or the company, with ids and `stage_since` |
| `meetings(window, viewer)` | Each meeting with its `when_class`, situations, goals, attendee parties (kind, role, response) and the founder's response |
| `suppressions(viewer)` · `lower_now(viewer, as_of)` | Active ignores, not-nows and laters, with scope and date, to undo; situations whose attention fell, each with its next date (the earliest expectation, `wake_on` or date) and reason |
| `recurring_work()` | Each recurring situation: cadence, last occurrence, next due, missed, delegated to (§5.6) |
| `aer_hir(from, to)` | Resolutions by path and reason, with ids (§7.5) |
| `item_uses(item_id, from, to)` | The versions that cited a Plane D, Plane R or company item, with later founder corrections |
| `receipt(run_id)` | The run receipt, joined to the situation and card versions it produced (§12.4) |

### 12.1 · The snapshot's blocks

| Block | Holds |
|---|---|
| **A** | Who we are: the company page, with local time and UTC, `verified_claims`, positioning in force |
| **W** | The page and its version |
| **N** | New members since `judged_through`, in full, each with its authority class |
| **L** | Open loops with ids, conditions, contradictions, open needs; each fact with its authority class |
| **C** | Claims in this situation, and what these parties already have from us, with authority classes |
| **P** | Parties: role, last interaction each way, usual reply time, open loops, relationship state, doubts, authority classes. For the anchor also its affiliations, its typed facts with ranks, and the loops owed by us (our commitments) and by them |
| **G** | G-live and G-proposed (D-P2-13), each with its current plan step, next move, health and linked situations |
| **E** | News from the same goal, linked situations and the company, dated and sourced (§10.2) |
| **F** | Coverage: what was and wasn't read |
| **H** | Prior situations with the same party or kind, their outcomes and durations, labelled "advisory: a past case, not this one". A current fact whose only evidence belongs to another situation is held |
| **B** | Behavior lines, company patterns (labelled "yours") and Adaptive leases that apply |
| **X** | Expertise and pattern ids selected (P3, P4), each with its version |
| **T** | Tool outputs (P4-3) |
| **S** | The bounded subgraph: nodes and edges (ids, types, valid window) within `max_hops` of the seeds, cut to `max_nodes`, with the cut counted |
| **V** | Other open situations on the same seeds, one header line each (state, whose move, nearest date) |

**What is printed in full:**
- Members newer than `judged_through` are printed whole.
- Older members appear as one header line each, and only when an open loop or claim cites them.
- The rest are available by id through the stored-event fetcher (`07` D6).

### 12.2 · Budgets

| Measure | Target |
|---|---|
| Snapshot read, p95 | under 2 s |
| Admission per page, p95 | under 1 s |
| A routine judgment | fits 20 s (high-stakes: 60 s) |
| Conclusions per founder tenant after a year | under 50 MB |

### 12.3 · Caches

- **Postgres is the only source of truth.**
- Dossiers, snapshots, the date index, the expertise index and any embeddings are caches, rebuilt from it.
- There is no graph database.
- **The test:** drop and rebuild every cache; the pages and wake-ups are identical. Guard 10 keeps the list of caches.

### 12.4 · Receipts and replay

- **A run receipt** (`reasoning_runs`) stores the revision read, `eval_time`, the request digest and the parsed answer. It also stores the calls, input and output tokens and cost (from P1's run ledger), the units that ran and those declined with their reasons, the Behavior and Adaptive lines used, and the admission ledger ids. `receipt(run_id)` joins it to the situation and card versions it produced. A replay re-admits from stored answers, with no model call, and gives the same rows.
- **Raw requests and answers** live only in the receipt store, under its own retention. Notebook tables hold no dossier text, unit fragments or raw model answers.
- **`model_call_evidence`** holds, per run, the evidence ids printed: ids only, never text. It is kept until erasure, so the founder can see which data reached a model, when and for which situation.

## §13 · Time and versions

- **Every instant is stored in UTC.** It is read in the company's time zone from the company page.
  - "Today", "before", "after", "by Monday" and the end of a due day are evaluated in local days (P1-1's clock).
  - `day_end(d)` is 23:59:59 local, stored in UTC.
  - A loop is broken only after its local due day has ended.
- **Evidence carries `occurred_at` and `known_at`.** Conclusions carry `as_of` and `known_at` (the run's eval instant), never the wall clock. Facts and links carry `valid_from` and `valid_to`.
- **`as_of(T)` returns, for each object, the latest version with `known_at` at or before T.** Replays state their mode: "as it happened" or "as GeniOS knew it".
- **The tenant revision** (`graph_versions`) increases with every admitting transaction. Each judgment records the revision it read, and its dossier uses only rows admitted at or below it.

## §14 · Visibility, privacy, retention, erasure, portability

- **Audience.** Every conclusion row (version, loop, claim, link, goal revision, parent situation) stores `audience` = the narrowest audience of its evidence and of the rows it derives from.
  - Reads filter by viewer.
  - A page for a person who may not see some evidence shows `withheld = [{owner seat, count, kind}]` with no words from it.
  - Conclusion tables are never drawn as a raw graph; only the evidence side may be.
- **Isolation.**
  - Row-level security on `org_id` covers every Notebook table.
  - A CI guard fails on SQL against these tables without an `org_id` predicate.
  - No reasoning reads across tenants.
- **Retention follows the work** (`evidence_citations`, D-P2-7):

  | Evidence | Kept |
  |---|---|
  | Cited by any situation not resolved or superseded (quiet included), or by a goal that has not ended | while cited |
  | Cited only by rows of closed situations or ended goals | `after_close_days` after the close (per tenant in `tenant_retention_policy`; 180 by default). Then it expires, and its citations are marked `quoted_only` |
  | In a thread we wrote in | at least 365 days after its last message |
  | Held by no situation (noise, bulk) | 180 days after capture, as today |
  | Admitted quotes, with their source ids | with the page, until erasure. When evidence finally expires, the citation is marked `quoted_only` |
  | Raw copies | object storage. Deleted once clean text exists and promotion is decided, unless a provenance row or fact still points at them; `tenant_retention_policy` may only shorten this |
  | Screen captures | encrypted in object storage, with retention per org |

  **Enforcement:** the purges skip rows that `evidence_citations` holds. The Notebook publishes a retention-hold list through its API, and an L0 platform retention job, not `capture/`, applies it.
- **Erasure.** A tenant's evidence and conclusions are deleted together. Every table in §1 is on the erasure path, and a test erases a test tenant and finds no row left (P2-24).
- **Portability (D-P2-15).** No Notebook table, check or invariant depends on a cross-tenant join or a hosted-only feature. A tenant's Notebook can be exported whole: `export_tenant(org_id)` writes every §1 table to one bundle, and `import_check` loads it into an empty database and runs every invariant and guard (P2-24). A local-first deployment stays a later product decision.

## §15 · Invariants (checked after every build, Evolve day and replay day; a failure fails the day)

| # | Must always hold |
|---|---|
| I-1 | Every member exists, and every cited id exists |
| I-2 | Every conclusion row has at least one evidence id that was printed to the run that wrote it, or names the code rule that wrote it |
| I-3 | Every evidence item known by the instant is a live member somewhere, or noise with a reason |
| I-4 | Every settled loop was settled per §4.4 |
| I-5 | Every claim is word for word, ours or a recorded paraphrase |
| I-6 | Every open card sits on a live situation version; its quotes are real; it holds no held reason or checker vocabulary, and no company number that differs from its metric's settled value |
| I-7 | Goals and links point at things that exist; one link set; no disagreement |
| I-8 | Spend is under the cap |
| I-9 | No quiet situation holds an open loop owed by us |
| I-10 | Every goal has a target, or "target not stated"; every done step has a date and evidence; every `doing` step names a situation or is counted as a gap; progress is never 0 without a count; every goal version that changed status or progress has a cause; every goal link except `unclear` has `through` |
| I-11 | No page cites evidence outside its audience |
| I-12 | No two live situations share (anchor, type, `matter_key`) unless one is `part_of` the other |
| I-13 | No situation that is not superseded (resolved and quiet included) has a member, by `known_at`, newer than `judged_through` without a pending wake-up |
| I-14 | Every live situation has an open expectation, or "nothing expected: <reason>" |
| I-15 | Every resolved situation has an `outcome_ref` |
| I-16 | No version row is ever updated; no DELETE outside erasure |
| I-17 | Every number served comes from a named query, with its inputs |
| I-18 | No verified absence without complete coverage |
| I-19 | No founder-locked field was changed by L2 |
| I-20 | Every item sent by an agent or a delegate links to an approval of the same draft version, and its new text matches `draft_text_digest` |
| I-21 | Every meeting starting within 14 days is a member of a live situation, or on the noise list with a reason (I-3) |
| I-22 | The evidence half holds no conclusion: every `graph_facts` and `graph_edges` row was written by L1's graph writer or by a named analytic with `derived_from`, and none carries a verdict, frame or recommendation |
| I-23 | A live situation has at most one open card, and a newer situation version updates that card's version |
| I-24 | Every party that is a member of a live situation has a current profile with a kind, a relationship line (or `unknown {reason}`) and a role there |
| I-25 | Every goal and every live situation has a department (or `unknown {reason}`); in a team, also an owner |
| I-26 | No live situation belongs to a department that is off |
| I-27 | No version row is over the size cap (§4.7) |
| I-28 | No open card stands on a situation whose attention is `quiet` or `ignored`, or whose state is `resolved` or `superseded` |

## §16 · Tests

Each test is a fixture from the ideal cards. The ids refer to [10](../10-ACCEPTANCE.md).

| Area | Test |
|---|---|
| Loops | `i2` stays `replied_not_answered` after the generic update; `i1`'s promise is `kept` by the 11 Aug mail (`fulfils`); `f3`'s referral is owed by the intro platform, missed since its promised date; `b3`'s ask is owed by the contact; a meeting creates a follow-through (`i3`) |
| Bounces | `i5` leaves 0 waiting loops on bounced recipients, and opens the re-send loops; `c1` reads "sent 16 Oct · 1 of 2 delivered" |
| Claims | `p1`'s four statements carry modality and recipients; MRR and ARR compared as one family; the 27 Oct broadcast joins the existing record; a draft with a conflicted number gets the placeholder |
| Situations | Each introduction is its own child; a new intro inside an old thread goes to placement; `c2`'s renewal notices and the vendor's acceptance are one situation; `f2`'s reminders sit on `f2` |
| Lifecycle | `s1` stays live with its card (an open loop owed by us); `f2` resolves on the first pass after 24 Oct as submitted or missed; a resolved situation reopens on contradicting evidence, through an L2 `reopen`, instead of spawning a new one; a meeting alone cannot resolve `b2`; every allowed transition passes and a sampled disallowed one is refused (A-6) |
| Goals | The 9 in-copy ideal goals load from a fixture with no field lost; the programme applications sit under the accelerator umbrella with `i1`'s reconsideration as its child; the reviewed-application goal's next move is `f4`'s check on Mon 26 Oct; the raise goal shows "nothing committed" as progress and its activity as counts |
| Travel | The incubator's review appears in the accelerator's dossier, dated, with its source |
| Time | At 23 Oct 07:10 local, the review at 11:30 is "later today"; a meeting rescheduled after 23 Oct shows its old time in a build as of 23 Oct |
| Absence | `i3` is a verified absence; `h1` is partial coverage; real MRR is unknown |
| Identity | A probable link stays a doubt; a merge undoes cleanly; an address with dots and capitals is stored and reused unchanged |
| Admission | Each law A-1 to A-32 has a positive and a negative fixture; a phase that drops a refused item silently fails its test; a change that names a known party, our product name or "UTC" is admitted |
| Links | One fixture per closed word; "X blocks Y" is stored as Y `depends_on` X; `causes` and `related_to` are refused (A-26); an ended link reads back as of an earlier date |
| Replay | Re-admitting stored answers reproduces the same rows with no model call |
| Caches | Dropping and rebuilding every cache gives identical pages and wake-ups |
| Visibility | A second seat's private thread never reaches the founder's page; the seat's own page quotes it |
| Erasure | A test tenant leaves no row |
| Isolation | Tenant A's session reads no row of tenant B in any table; a query without `org_id` fails guard 5 |
| Export | A tenant's export, loaded into an empty database, passes every invariant and guard |
| Guards | Each guard of §17 fails on its seeded mutation |

## §17 · Guards (CI)

1. **One writer:** only `context/work_store` writes the intelligence tables, and only L1's graph writer writes `graph_nodes`, `graph_facts` and `graph_edges`.
2. **One reader door:** no module outside `context/` selects from Notebook tables; `capture/` never imports `context/`.
3. **No model call in `context/`** (GeniOS-008 Rule 3, the layer guard).
4. **The ratchet:** the list of places that create or refresh a rule-born situation only shrinks (GeniOS-008 L3-2).
5. **No SQL against Notebook tables without an `org_id` predicate;** no DELETE outside erasure.
6. **The field registry:** every column has a named writer and a named consumer. A two-way totality guard fails on an undeclared column, or a declared field nobody writes or reads ("nothing computed may go uncarried").
7. **Seam tests:** an L2 result fixture goes through admission and the store, and out to the snapshot and the card, with no field lost.
8. **No dossier text, unit fragment or raw model answer** in a Notebook column.
9. **Vocabularies are data:** a fixture pack with a new kind needs no migration and no code change.
10. **Caches are declared:** the dossier, snapshot, date-index and expertise-index tables are listed as caches; no write path reads them as a source, and no graph-database client is imported.

## §18 · Size and performance

| Measure | Target |
|---|---|
| Conclusions per founder tenant after a year | under 50 MB |
| Evidence | as the retention rule leaves it; Screen and raw bodies in object storage |
| Snapshot read, p95 | under 2 s |
| Admission per page, p95 | under 1 s |
| A day with nothing new | 0 model calls, and a handful of indexed reads |

Daily health reports size per tenant.

## §19 · What this file changes in GeniOS-013 05 (the work object)

| 05 said | This file says | Why |
|---|---|---|
| New tables `work_items`, `work_item_versions` (0257) beside `context_situations`, kept side by side | `work_items` heads the one chain and **replaces** `context_situations` per tenant at cutover; Atlas III.4 is amended with Rohit's yes (D-P2-12) | Isolation from the nine old writers during migration, and one chain after it |
| `status`: proposed … merged | Atlas's 14 states (§5.1), with `whose_move` and `attention` separate | Atlas III.3; one machine, not two |
| `next_expected.by` must be in the future | It may be past when first set (`missed_since`) | Otherwise the silences `f3`, `i3`, `c1`, `i2` and `b3` are erased |
| `verdict.confidence`: six words written by the model | Computed by units and code (§9.4) | Atlas A.4; and the grammar limit (N8) |
| One `next_expected` | Several expectations, with ids, plus `dates` and `stated_dates` | Atlas's first-class Expectation; deadline-like dates are distinct |
| Situations seeded from correlations by code | Situations exist only after admission of an L2 mutation; code only proposes | GeniOS-008 L3-1; Atlas: L3 never forms situations |
| `decisions` holds the founder's answers | `decision_objects` (L3 → L4) and `founder_decisions` (human acts) are separate | They are different objects |

## §20 · Production hardening (beyond the four references)

The final review asked what a perfect Notebook needs that none of the four references asked for. These twelve answers are part of the specification.

| # | What | The rule | Test |
|---|---|---|---|
| 20.1 | **Indian number units and currencies** | Claims parse lakh (10⁵), crore (10⁷), K and M, and currency symbols, into `amount_minor` plus `currency`. Comparisons key on (currency, amount_minor, period). Today a crore and a lakh amount with the same digits get the same key | Synthetic strings only: "₹7 Cr" and "₹7 lakh" never compare equal; "$9K MRR" and "₹9K MRR" never compare equal |
| 20.2 | **Withdrawing one item** (a contact's erasure request under India's DPDP Act or GDPR, a founder deleting a thread, a source losing an item) | `evidence_withdrawals` and a job remove every quote and span taken from the item. They mark the claims, loops and facts that rested only on it as "evidence withdrawn", and re-judge the works affected | Withdrawing one mail leaves no quote from it, and its work is re-judged |
| 20.3 | **Undoing a bad run** | `revert_run(run_id)` writes new versions restoring the state before the run for every row it admitted, records the reason, and wakes the works affected | Reverting a seeded bad run restores every page exactly; both histories stay readable |
| 20.4 | **The Notebook's own accuracy** | A private, hand-labelled sample from the copy: about 60 loops, 40 claims, 80 party kinds, 30 membership decisions and 20 whose-move values. Precision and recall, and the recall of important situations, are scored on every build and logged in [08-LOG](../08-LOG.md). A step that lowers any score is not done. The sample and the map from ideal ids to real threads stay in the private folder; a lint fails if a tracked file holds a name, address or amount from them | The scores are produced for `b2`, and recomputed after each step |
| 20.5 | **Confidence and predictions that are actually right** | Each week Maintain compares each confidence level with later founder corrections, contradicting evidence and how predictions turned out, per dimension (for example, "strong" later corrected 3% of the time, "medium" 11%). A dimension whose "strong" is no more accurate than "medium" is flagged | A seeded set yields the expected rates |
| 20.6 | **One message, captured twice** (two seats, or mail and calendar) | `canonical_item_id` on the envelope, from the RFC Message-ID or the calendar's iCalUID. The audience becomes the union of both seats' audiences | A mail sent to two seats gives one member, one claim and one wave recipient |
| 20.7 | **A reliable "later"** | Store `sent_at` (the Date header), `received_at` (the provider's internal date) and the position in the thread. Order by `received_at`, then by thread position | Two mails with the same timestamp, in the right order, close the loop |
| 20.8 | **The company's working week and holidays** | `working_week` and `holidays` on the company page; P4-3's date tools use them | A follow-up after a Friday meeting is due Monday |
| 20.9 | **Old conclusions after the contract changes** | `contract_version` on every version row, with one upgrade function per version, tested on all of `b2`'s versions. When the contract changes, the pages left incomplete are listed and re-judged in priority order | Every `b2` version reads under the new contract |
| 20.10 | **Who may approve what** | `decision_rights` on the company page: seat, action kind, scope, limit. Admission refuses an approval from a seat without the right | A teammate's approval of a send to an investor is refused when only the founder holds that right |
| 20.11 | **Our own numbers over time, and how good our projections were** | A read, `series(metric)`, of achieved and projected values by date. When an achieved value arrives after a projection's target date, a derived fact `projection_accuracy` is written | The May projection in `p1` is scored against the August actual |
| 20.12 | **Secrets stay out of dossiers and quotes** | Before any text is printed to a model or kept as a quote, a code redaction pass replaces keys, passwords, card numbers and account numbers with typed placeholders, and counts them | A synthetic key in a mail never appears in a dossier or a quote |
