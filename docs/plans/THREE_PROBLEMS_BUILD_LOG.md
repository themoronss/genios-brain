# Three problems — implementation and verification record

Status: IN PROGRESS. User approved the 26-unit build shape on 10 September 2026.

Order: Task 1 (1E/1F, 1A/1B, 1C/1D) → Task 3 → Task 2.
Supplied live measurements are specification inputs, not measurements taken by this build.
Tests use fixed timestamps, SQLite and fake external services. No production database,
activation, live attachment drain, commit, push or deployment is part of this run.

Protected: 4500 floor, evidence/freshness formulas, analytic ramp, deterministic reasoning,
cards_one_per_signal, and FEATURE_BUNDLE activation.

## Setup and baseline

- Only the previously approved tree.yaml addition was present; production worktree clean.
- GENIOS_PY=.venv/bin/python bash scripts/qa/check-tree.sh: exit 0. Graph acyclic;
  every unit has a verify. 26 new units, 34 live including historical milestones.
- Trace scripts absent: inspected existing locks, then used atomic directory claims in
  .trace/locks and append-only .trace/events.jsonl. No trace framework added.
- Initial baseline failed before collection: pytest absent from .venv.
  uv pip install --python .venv/bin/python '.[dev]' installed declared dev dependencies.
  This is a setup failure, not an application regression.
- Current baseline running with GENIOS_TEST_DATABASE_URL, GENIOS_DATABASE_URL,
  GENIOS_ANTHROPIC_API_KEY and GENIOS_COMPOSIO_API_KEY explicitly empty.
  Command: uv run --no-sync pytest -q -p no:randomly
  --junitxml=/tmp/genios-three-problems-baseline.xml.
  Supplied 9899-pass/24-failure baseline is not treated as a current result.

## Unit record

Each completed entry records defect, why this seam, RED and GREEN commands/results,
observed fixture delta, and what remains unverified.

### 1E — M5.C1.L-logic.V0.U01

- Defect: legal cohorts of 5..77 peers impose 1200..4400 bp against the 4500 floor.
- Change: analytic no longer participates in SituationTrustPlugin's ceiling. Both explanatory
  comment blocks now carry that measurement. The analytic receipt and formula remain intact.
- Test contract changed explicitly as requested: replaced the old analytic-binds expectation
  with all populations 5..78, fixed arithmetic, preserved receipt and four factual-zero cases.
- RED: confidence suite 74 failed, 61 passed. First failure was 1200 instead of 5000.
- GREEN: uv run --no-sync pytest tests/reason/test_confidence_rule11.py -q -p no:randomly:
  135 passed, zero skips. No evidence/freshness formula or floor change.
- Fixture delta: cohort no longer vetoes the 5000-bp factual ceiling. Live counts not measured.

### Baseline result and environment correction

- Original collected suite: 9892 passed, 31 failed, 899 skipped, 152 xfailed (314.81s).
  Its old analytic-binds test passed, confirming that baseline executed the original module.
- 24 failures match the supplied baseline files. Seven extra failures were missing office/OCR
  Python dependencies: six office extraction tests and one OCR availability test.
- Installed document packages at the versions already pinned in requirements.txt; no dependency
  declaration or production OCR code changed. Focused office/OCR plus calendar tests: 40 passed.
- The packaging command generated an untracked build directory; moved that generated artifact
  into a temporary genios-packaging-artifact directory, leaving user files untouched.

### 1F — calendar actor and factory wiring

- M5.C1.L-logic.V0.U02 RED: 6 failed, 1 passed (connector could not accept the identity set).
  GREEN: 7 passed. External organiser, normalised internal addresses, empty/absent identity sets,
  absent organiser, webhook/poll equivalence and provider watermark are covered.
- M5.C1.L-integration.V0.U01 RED: 3 failed, 5 passed (factory still called outsiders staff).
  GREEN with actor and office/OCR checks: 40 passed, zero skips.
- Factory injects context.runner._internal_emails: active seats, owner, connected mailboxes.
  Layer 1 imports no Layer 2 code. A failed identity refinement logs a warning and keeps the
  old behaviour, as required; a successful read classifies membership instead of hardcoding it.
- Broader backfill/push regressions: 54 passed, 1 existing PG skip. Not called zero-skip green.

### 1A — shared receipts and support writers

- Shared writer M5.C2.L-data.V0.U01: RED 5 failures; GREEN 5 passed, zero skips.
  Real SQLite proves two events → two refs, actual source/object/independence group, stable IDs,
  removed-member cleanup, other-tenant exclusion, and savepoint-isolated read failure.
- Support unit U01 was retired in favour of U04: the original verify mixed in PostgreSQL-only
  skips. The replacement runs new SQLite proof; existing support tests remain regression checks.
- Support RED: missing receipt argument/event-ID field, then empty escalation/mailbox receipts.
  GREEN: 55 passed, zero skips across new persistence tests and the seven-reading suite.
- Every support reading now retains available contributing message IDs before reducing them to
  counts. Fact and source refs are written in one transaction; JSON binds work on SQLite and PG.
  Missing source messages are not invented. Failed enrichment retains the old write path.

### 1A — outreach writers

- M5.C2.L-data.V1.U02 RED: 3 failures. GREEN: 54 passed, zero skips across new SQLite
  provenance tests and existing campaign, organization and conversation regressions.
- Campaign event membership is retained in full; the 20-event preview remains presentation-only.
  Cohort and organization findings retain all contributing members, not just one representative.
  Active original-fact receipts supply actual source events; cross-tenant rows cannot contribute.

### 1A — document writers

- M5.C2.L-data.V1.U05 RED: 2 failures. GREEN: 2 passed, zero skips in the SQLite unit.
  Existing document register checks: 24 passed, 5 existing PG skips (not zero-skip green).
- Gather retains the latest revision event for each document. Every cluster-derived fact carries
  the revisions of all files it compared, with stable source refs and replay-safe replacement.

### 1B — scope-aware evidence and freshness

- Neighborhood RED: 3 failed, 1 passed; GREEN: 4 passed. Both directions, actual event time,
  duplicated refs, foreign tenants, retired edges, future events and second-hop exclusion tested.
- Group RED: 4 failures; GREEN: 4 passed. Computed campaign membership is not assumed to be a
  database correlation ID; genuine groups join through context_correlation_members.event_id.
- Refresh RED: 3 failures including campaign evidence 0 / freshness unknown. Combined GREEN:
  65 passed, zero skips. Seven Gmail events exactly 30 days old now yield 65 evidence / 50 freshness.
- Read refinements use savepoints and return original stats on failure. The actual synthetic
  anchor is queried after creation, avoiding accidental two-hop history through its representative.
- This proves scoring inputs, not persisted publication. The compiler/card integration is pending.

### 1C / 1D — event presence on established subjects

- Redrew calendar unit U01 as U03: actual runtime writer is structured.commit_structured.
  Added a supporting GraphStore unit for stable event/subject presence IDs and real JSON refs.
- Shared presence RED: missing method after fixture correction. GREEN: 1 passed, zero skips.
  Concurrent-safe insert-on-conflict and replay preserve one observation/ref per event/subject.
- Calendar RED: both small and bulk fixtures had zero observations. GREEN with regressions:
  53 passed, zero skips. Internal people retain evidence; bulk attendee guard remains unchanged.
- Recipient RED: four content paths had zero recipient observations. Combined GREEN: 7 passed,
  zero skips. Question, semantic observation, mention and plain email all establish recipients;
  the sender remains the speaker and no recipient inherits the sender's commitment.
- Tree check: 35 live units / 4 retired, acyclic. New IDs record corrected seams; tests not weakened.

### Task 1 — real compiler/decision probe

- Split oversized M5.C5.U01 into U02 decision proof and U03 final persisted-card assembly.
  U03 remains required, depending on renderer/noun integration; it is not marked green.
- Fixed-time seven-event probe: real shipped corpus compiler and full reasoning roster selected
  a candidate at confidence 5000 bp; floor remains 4500. GREEN: 1 passed, zero skips.
- This fixture supplies qualified-signal identities and exercises the compiler in shadow mode.
  It does not claim production admission/activation, signal persistence or a customer-visible card.

### Task 3 — preserve the authored sentence and its receipt

- Per-card YAML situation cap now overrides the unchanged 140-character default. Campaign
  measurement is 130 prose characters at stored 7/7 counts, so its explicit cap remains 140.
- Source-backed quote loading verifies the exact bytes against same-tenant prepared content.
  Verified quotes retain their full text; unverified quotation marks do not bypass the cap.
- Quote-aware rendering preserves verified spans through fallback, whitespace handling and
  model-length repair. Headline cap and invention guards remain unchanged.
- Corpus-authored rejection fallback was already wired. Added tests rather than changing its
  compatibility mode label. Placeholder probes found no literal leaked template in this repo;
  historical source/render inputs are still needed and have been requested.
- Real campaign assembly exposed a separate slot bug: campaign counts read cohort fields,
  producing "several" or unrelated counts. New unit scopes slots by reason code; 7/7 stays 7/7.
- Focused cap/compiled/delivery run: 61 passed, zero skips. Authored fallback: 25 passed.
  Quote loader: 4 passed. Placeholder probes: 3 passed. Campaign slots: 2 passed.
  Final real-compiler/render integration: 1 passed, zero skips (reverified 4.51s).

### Midpoint regression measurement

- Full hermetic suite before the later renderer units: 10022 passed, 25 failed, 899 skipped,
  152 xfailed. This is not a green full suite.
- 24 failures match the supplied baseline. The additional corroboration failure was an old
  SQL fake expecting a JSON SQL string after binding became typed JSON; it now asserts the
  full evidence object. Corroboration plus actual SQLite presence proof: 4 passed.
- The next complete-suite run must confirm no additional failures remain. Live tenant
  measurements, backfill and activation are separate from these fixed-time fixture results.

## Boundaries that must not be called complete

### Task 2 — source-backed business nouns

- Added a typed BusinessFact lane for all nine requested fields. The existing extraction call
  requests the fields, standing and exact prepared-content receipts. No second LLM call was added.
  The cache-keyed prompt changes; old cached empty output is not reused on re-extraction.
- Generated schema needed explicit Literal and text/Money support. Kept ambiguous generic unions
  rejected. Contract/schema/prompt checks: 123 passed, zero skips at that stage.
- Parser and ALG-08 now retain/verify this lane. Fabricated receipts are dropped by ALG-08;
  nested Money must match its own verified quote and literal amount. Combined check: 224 passed.
- The active QES adapter previously discarded this lane. It now carries subject, standing,
  typed value and exact verified spans into L2. Adapter check: 4 passed.
- Real GraphStore JSON persistence and authority checks: 21 passed. A directly stated value
  outranks R1 judgement in either arrival order; same-value confirmation promotes the held rank.
  Replay and stronger-source temporal rules are unchanged. Existing driver fakes now return
  actual decoded JSON scalars; no assertion was removed to hide a failure.
- Subject resolution uses the exact existing person/company/campaign or actual message thread.
  Ambiguous subjects are omitted, never assigned to the sender by default. Deal facts use their
  own account, not an arbitrary CC. Legacy purpose/role interpretations are R1 as well.
- All nine fields reject None, empty and unknown on typed and legacy paths. Authority/missingness:
  69 passed. Empty extraction cannot erase an existing explicit fact.
- End-to-end fake-model fixture through real extraction, ALG-08, QES and SQL: 2 passed.
  Supported input writes 3 fact/ref rows (role, title, purpose), requested coverage100; empty input
  writes0, coverage0 and both role/purpose remain missing. These are fixture deltas, not live counts.
- Attachment recovery: 40 passed, zero skips. Real document router and parked drain, fake provider
  and OCR; readable deck recovers once, failed/missing OCR stays parked without emitting evidence.
  Live767 drain NOT RUN. Existing operator routes: GET /parked/refetch, privileged
  POST /parked/refetch/requeue; heartbeat _drain_attachment_refetch consumes approved org queues.
  GENIOS_OCR_ENABLED_ORGS controls the allowlist. Generic drain_parked is not the OCR-refetch drain.

### Review corrections — quote selection, stale cards and typed Money

- Independent reviewer stopped on workspace credits, so no completed independent-review claim.
  Its two intermediate quote concerns were independently reproduced with real SQLite queries.
- Presence-only observations consumed LIMIT ahead of a real quote. They are now excluded before
  selection. Campaign member refs cannot all stand for the representative quote: only an actual
  same-tenant prepared source containing that quote supplies its author/ACL. Match occurs before
  LIMIT, not after. Fresh combined quote checks: 12 passed, zero skips.
- Builder revision was still v4 despite changed visible output. Bumped to
  card-builder.v5-evidence-backed-copy. Existing one-card-per-signal upsert is retained; untouched
  built/queued/surfaced cards may be recomposed. Claimed/snoozed/acted/resolved/expired cards and
  cards with resolved_at are protected. Real SQL build-claim and delivery checks: 46 passed.
  State-list binds use equivalent expanding IN for SQLite/PG; no lifecycle policy changed.
- Crosscheck found typed Money reached storage but float(dict) rendered it as no value set.
  Added a separately claimed unit. RED4; GREEN37 with delivery/count regressions. Source literals
  survive for USD/EUR/JPY/zero; no implicit USD conversion or minor-unit arithmetic was added.

### Persistence boundary — stronger proof, still not a shipped-card claim

- Added real campaign fact/ref/situation persistence and repeated writes, then re-read those rows
  into the actual compiler/reasoner. JSON inputs initially became0 in SQLite; typed JSON bindings
  now preserve the data. Focused campaign/support run: 54 passed, zero skips.
- Stored situation is evidence65 / freshness50 / overall50; each derived fact has7 event refs,
  and replay does not multiply them. The compiled candidate remains selected at5000bp.
- The actual publication function returns None for this SHADOW fixture. No fake audit bundle,
  fabricated run IDs or tenant flag changes were used. Authorized persisted audit -> signal ->
  CardStore insertion is STILL NOT PROVEN. M5.C5.U03 remains partial despite its boundary test passing.
- Crosscheck report: .trace/reports/crosscheck-20260911-three-problems.md. It records the remaining
  scope gap: thread purpose is correctly stored on its thread, but propagation into every older
  person/cohort consumer is not proven. Never copy one thread's purpose onto all correspondence.

### Remaining boundaries

#### Time boundary — the acceptance arithmetic is not time-independent

Read-only calculation against the unchanged production functions, fixed source time
2026-08-11T12:00:00Z:

| Evaluation time | Evidence age | Evidence | Freshness | Trust ceiling |
|---|---:|---:|---:|---:|
| 2026-09-10T12:00:00Z | 30 days | 65 | 50 | 5000 bp |
| 2026-09-11T12:00:00Z | 31 days | 65 | 30 | 3000 bp |

The 4500 floor and freshness_score are protected. Fresh evidence may change the live result;
merely recomputing or redeploying cannot reset the age of the original source event. A live
replay after the 30-day boundary is therefore NOT promised to emit this campaign card.

#### Target sentence: what is implemented versus not established

| Requested clause | Local code/proof | Remaining evidence |
|---|---|---|
| Theresa / Antler | Existing identity and works_at paths retained | Actual tenant rows not re-read |
| Partner at | Typed title/role extraction, own verified receipt | Actual title source and live re-extraction |
| 30 days silent / 11 August | Actual source timestamps, fixed30-day regression | At31days trust ceiling changes; do not freeze age |
| You sent the deck | Real attachment recovery path tested with fake OCR/provider | Live767 drain and a readable deck receipt |
| In a raise | Source-backed objective, judgementR1 vs observedR2/4 | Real statement/inference and scoped consumer wiring |
| 6 of13 | No fabricated counts: actual supplied campaign is7contacted/7awaiting | Different6/13 population must be evidenced separately |
| The same line | Derived refs plus prepared-source quote verification and quote-aware rendering | Live source retention and actual card ID |
| Sending it again is not the move | Not supplied by a deterministic count | User-controlled bundle/critique activation and a published decision |

The supplied spec snapshot says roster_v2/ranking_v2 were enabled by harsh on8Sep and
bundle/critique/brief had never been enabled. That is supplied historical evidence, NOT a fresh
tenant measurement. None of those activation rows or FEATURE_BUNDLE was changed here.

- First final-suite attempt: 10195 passed /26 failed /899 skipped /152 xfailed. Two new failures
  were the whole-corpus validator rejecting situation_cap. Added a dedicated schema unit instead
  of weakening the validator or removing the YAML property. Positive integers accepted;
  zero/negative/bool/string/null/fractional values and unknown properties rejected. 52 passed,
  zero skips across the unit and both complete corpus regression files. Final suite restarted
  after this correction and the Money/persisted-situation additions.

- Exact historical Insert/SwerashiGeniOS render inputs were not supplied. Locate the producer
  before changing it; do not allowlist tokens or weaken the invention guard.
- Seven stored campaign recipients are not the illustrative thirteen. Do not invent 6-of-13.
- A 5000-bp trust ceiling alone is not a published decision or customer-visible card.
- Live attachment drain, activation and post-rollout tenant/card measurements remain NOT RUN.

## Final verification — 11 September 2026

All implementation edits preceded the final complete-suite run. Result:

```
24 failed, 10217 passed, 899 skipped, 152 xfailed, 660 warnings in 449.28s (0:07:29)
```

Command (database and provider credentials explicitly unset for this process):

```
GENIOS_TEST_DATABASE_URL= GENIOS_DATABASE_URL= GENIOS_ANTHROPIC_API_KEY= GENIOS_COMPOSIO_API_KEY= uv run --no-sync pytest -q -p no:randomly --junitxml=/tmp/genios-three-problems-final-verified.xml
```

- Exit1. Exact failed test IDs match the24 supplied baseline failures, verified against the
  original baseline JUnit. New failure IDs: []. This is NOT a green full suite.
- Task-scoped verification:39 commands,481 test executions (480 distinct tests),0fail/0skip.
- Tree:47 active units,6 retired; IDs independently checked unique, dependency graph acyclic.
- git diff --check: exit0. Protected scoring functions, decision floor, activation module,
  migrations, .env and .env.example have no diff. No test threshold or assertion was weakened.
- The complete QA harness is absent. Connections/environment integrations/live API tiers are
  NOT RUN; SQLite integration fixtures do not stand in for them. All899 skipped test IDs and
  their exact reasons are in `.trace/reports/qa-20260911-three-problems.json`.
- No commit, push, deployment, tenant mutation, OCR drain or feature activation was performed.
- Final status: implemented fixes have no new full-suite failures; overall acceptance remains
  incomplete for the historical placeholder producer and authorized persisted/live card proof.

### Full-suite failing lines (verbatim)

```
FAILED tests/capture/connectors/test_new_route_wiring.py::test_a_tenant_can_change_how_far_back_their_first_sync_reaches
FAILED tests/capture/connectors/test_new_route_wiring.py::test_an_out_of_range_window_is_refused_at_the_edit_not_at_the_next_sync
FAILED tests/capture/connectors/test_new_route_wiring.py::test_an_unmapped_structured_source_is_reported_as_actionable
FAILED tests/capture/connectors/test_new_route_wiring.py::test_another_tenants_connection_cannot_be_retuned
FAILED tests/capture/connectors/test_new_route_wiring.py::test_the_mapping_coverage_report_reads_the_tenants_own_connections
FAILED tests/capture/connectors/test_new_route_wiring.py::test_the_window_route_is_not_shadowed_by_the_lifecycle_action_route
FAILED tests/capture/esqe/test_qualification_routes.py::test_a_drop_whose_components_predate_this_shape_says_so_instead_of_inventing_a_sentence
FAILED tests/capture/esqe/test_qualification_routes.py::test_a_floor_outside_the_basis_point_range_is_refused_by_the_route[-1]
FAILED tests/capture/esqe/test_qualification_routes.py::test_a_floor_outside_the_basis_point_range_is_refused_by_the_route[10001]
FAILED tests/capture/esqe/test_qualification_routes.py::test_a_floor_outside_the_basis_point_range_is_refused_by_the_route[99999]
FAILED tests/capture/esqe/test_qualification_routes.py::test_an_unknown_drop_is_a_404_and_not_an_empty_explanation
FAILED tests/capture/esqe/test_qualification_routes.py::test_an_untuned_tenant_reads_the_default_floor_and_says_nobody_set_it
FAILED tests/capture/esqe/test_qualification_routes.py::test_moving_the_floor_writes_a_changelog_entry_naming_who_and_why
FAILED tests/capture/esqe/test_qualification_routes.py::test_one_drop_renders_the_sentence_l1_6_7_u3_was_written_to_produce
FAILED tests/capture/esqe/test_qualification_routes.py::test_one_tenants_drops_are_never_visible_to_another
FAILED tests/capture/esqe/test_qualification_routes.py::test_the_drops_read_narrows_to_one_event
FAILED tests/capture/esqe/test_qualification_routes.py::test_the_floor_can_be_moved_through_the_route_and_the_move_is_attributed
FAILED tests/capture/esqe/test_qualification_routes.py::test_the_ledger_answers_why_did_i_never_see_this_with_components_and_a_payload_ref
FAILED tests/capture/esqe/test_rejection_ledger.py::test_a_tenant_can_ask_why_a_rejected_signal_never_appeared
FAILED tests/capture/esqe/test_rejection_ledger.py::test_the_drops_route_survives_a_row_that_came_out_of_the_database
FAILED tests/capture/esqe/test_rejection_ledger.py::test_the_signal_read_route_ages_what_it_returns
FAILED tests/capture/esqe/test_rejection_ledger.py::test_the_sync_hook_itself_files_rejections
FAILED tests/capture/test_g9_gate_probes.py::test_probe_deleting_an_org_still_works_after_the_extraction_table_rename
FAILED tests/contracts/test_h0_gate.py::test_every_layer_two_placeholder_skips_with_its_wave_and_gate_named
```
