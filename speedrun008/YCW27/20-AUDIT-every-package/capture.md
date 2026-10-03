# L3 · `capture/` — the file-by-file coverage audit

⛔ **GENERATED, NOT WRITTEN.** Regenerate with:

```
python scripts/context_coverage_report.py capture > \
    speedrun008/YCW27/layer-3-context-graph/05-AUDIT-capture-file-by-file.md
```

Measured 2026-10-03. ⛔ Every number here is a measurement of one checkout; *a hardcoded count in a document is wrong the next day*, so the command above is the real answer and this file is its output.

```
files                       158
lines                       47,184
files that WRITE a table    25
distinct tables written     25
⛔ written, no receipt       19
declared silences           7
```

## ⛔ Tables this package writes that no receipt covers

| table | external readers | writers in this package |
|---|---|---|
| `graph_source_refs` | 22 | `fingerprint.py`, `pipeline.py` |
| `l1_extraction_results` | 13 | `cache.py` |
| `connections` | 12 | `store.py` |
| `prepared_content` | 12 | `prepared_store.py`, `refetch.py` |
| `qualified_signals` | 12 | `signal_store.py` |
| `agent_registry` | 8 | `events_store.py` |
| `qualification_drops` | 7 | `qualification.py` |
| `source_coverage` | 4 | `store.py` |
| `signal_conflicts` | 2 | `conflict_store.py` |
| `transcripts` | 2 | `ingest.py` |
| `agent_events` | 1 | `events_store.py` |
| `human_events` | 0 | `events_store.py` |
| `message_fingerprints` | 0 | `fingerprint.py` |
| `org_qualification_floors` | 0 | `qualification.py` |
| `publication_rejections` | 0 | `publisher.py` |
| `qualification_floor_changes` | 0 | `qualification.py` |
| `signal_lifecycle` | 0 | `lifecycle.py` |
| `source_waitlist` | 0 | `source_waitlist.py` |
| `unclassified_observations` | 0 | `open_lane.py` |

## ⛔ THE COLUMN THAT WAS HERE IS GONE, AND THAT IS A FINDING

This section used to list modules of 100+ lines that no test file names. ⛔⛔ **It was removed on 2026-10-03 after six repairs failed to make it honest**, and the removal is the most useful thing it produced.

Across three package audits it reported **33** entries. ⛔ Nineteen were false, and each false entry was a candidate finding that died on inspection:

```
a @router.get handler has no Python caller and no test imports its module   -> false
a table read through funnel.read_sweep: reached, path written nowhere       -> false
test_unit_roster.py parametrises ALL_UNITS: 23 units run, no class named    -> false x16
ConstraintReasoner = ConstraintUnit — an alias a ClassDef scan cannot see   -> false
```

⛔ And every repair over-corrected in the other direction, which is worse, because a false negative **hides** a live module:

```
counting a generic CAPABILITY constant rescued a module with NO test at all
counting __all__ as a definition made all 23 unit names look ambiguous, so the
    whole column collapsed to zero findings
⛔⛔ and the guard written FOR this column named two functions in its own docstring,
    which made the module it was asserting is untested read as named — the observer
    altering the thing it measured
```

> ⛔ **A column whose error rate is unknown in BOTH directions is a column nobody should act on.** Naming is not coverage, six attempts did not make it one, and the section produced **zero** surviving findings in three audits while costing nineteen false leads.

⛔ **What it did produce, kept as a real finding rather than a table row:** `api/identity_routes.py` has **five routes and 130 lines**, and no test file mentions it by any means — verified by hand, not by this column. That is on `21-PLAN-TO-PRODUCTION.md`.

⛔ **What replaced it: nothing.** The table above — *tables a package writes that no receipt covers* — held in all three audits and is what the audit is for.

## Every file

| file | lines | public | declared silences | writes | reads |
|---|---|---|---|---|---|
| `semantic/extractor.py` | 1994 | 10 | — | — | — |
| `pipeline.py` | 1787 | 9 | — | `graph_source_refs` | — |
| `esqe/publisher.py` | 1267 | 14 | — | `publication_rejections` | `publication_rejections` |
| `esqe/importance.py` | 1262 | 8 | — | — | — |
| `esqe/relevance.py` | 1092 | 5 | — | — | — |
| `esqe/lifecycle.py` | 1073 | 20 | — | `signal_lifecycle` | `signal_lifecycle` |
| `validate/conflict.py` | 1057 | 6 | — | — | — |
| `esqe/qualification.py` | 994 | 12 | — | `org_qualification_floors`, `qualification_drops`, `qualification_floor_changes`, `raw_payloads` | `org_qualification_floors`, `qualification_drops`, `qualification_floor_changes` |
| `validate/dates.py` | 979 | 6 | — | — | — |
| `validate/spans.py` | 970 | 4 | — | — | — |
| `acquire/sync_runner.py` | 941 | 7 | — | — | — |
| `parked/refetch.py` | 937 | 3 | — | `document_jobs`, `parked_events`, `prepared_content`, `raw_payloads`, `source_events` | `parked_events`, `raw_payloads`, `source_events` |
| `structured/mapper.py` | 875 | 9 | — | — | — |
| `validate/schema.py` | 854 | 1 | — | — | — |
| `semantic/batch.py` | 822 | 4 | — | — | — |
| `connectors/composio.py` | 805 | 1 | — | — | — |
| `semantic/open_lane.py` | 751 | 4 | — | `unclassified_observations` | `unclassified_observations` |
| `semantic/profiles.py` | 743 | 3 | — | — | — |
| `structural/tokens.py` | 708 | 4 | — | — | — |
| `esqe/normalize.py` | 658 | 1 | — | — | — |
| `semantic/evidence_binder.py` | 652 | 5 | — | — | — |
| `validate/canonical.py` | 648 | 3 | — | — | — |
| `esqe/signal_store.py` | 641 | 1 | — | `qualified_signals` | `qualified_signals` |
| `validate/confidence.py` | 639 | 8 | — | — | — |
| `validate/claim_group.py` | 626 | 7 | — | — | — |
| `semantic/injection.py` | 610 | 4 | — | — | — |
| `validate/money.py` | 606 | 3 | — | — | — |
| `esqe/detector.py` | 581 | 2 | — | — | — |
| `validate/authority.py` | 513 | 4 | — | — | — |
| `transcripts/ingest.py` | 507 | 12 | — | `transcripts` | `capture_policies`, `l2_processing_runs`, `org_seats`, `transcripts` |
| `parked/refetch_policy.py` | 490 | 7 | — | — | — |
| `semantic/cache.py` | 445 | 3 | — | `l1_extraction_results` | `l1_extraction_results` |
| `esqe/source_analyzer.py` | 435 | 3 | — | — | — |
| `semantic/model_router.py` | 431 | 5 | — | — | — |
| `structured/targets.py` | 418 | 5 | — | — | — |
| `documents/chunking.py` | 401 | 2 | — | — | — |
| `semantic/sink_guard.py` | 399 | 2 | — | — | — |
| `gate/rules.py` | 389 | 12 | — | — | — |
| `semantic/router.py` | 380 | 3 | — | — | — |
| `benchmark.py` | 375 | 3 | 3 | — | — |
| `documents/native.py` | 370 | 4 | — | — | — |
| `transcripts/parse.py` | 368 | 5 | — | — | — |
| `screen/render.py` | 362 | 6 | — | — | — |
| `semantic/schema_gen.py` | 357 | 1 | — | — | — |
| `source_registry.py` | 353 | 9 | 2 | — | — |
| `structural/threads.py` | 346 | 2 | — | — | — |
| `parked/recapture.py` | 308 | 3 | — | `parked_events`, `source_events` | `parked_events`, `source_events` |
| `semantic/vocabulary.py` | 296 | 4 | — | — | — |
| `connectors/drive.py` | 290 | 2 | — | — | — |
| `structured/registry.py` | 269 | 6 | — | — | — |
| `gate/relevance.py` | 268 | 0 | — | — | — |
| `transcripts/link.py` | 264 | 8 | — | — | `graph_edges`, `graph_facts`, `graph_nodes`, `orgs` |
| `domain/hints.py` | 260 | 2 | — | — | — |
| `validate/conflict_store.py` | 260 | 3 | — | `signal_conflicts` | `signal_conflicts` |
| `screen/fingerprint.py` | 256 | 9 | — | `graph_source_refs`, `message_fingerprints` | `message_fingerprints`, `source_events` |
| `connectors/manifest.py` | 253 | 2 | — | — | — |
| `screen/relevance.py` | 251 | 3 | — | — | — |
| `source_waitlist.py` | 248 | 3 | — | `source_waitlist` | `source_waitlist` |
| `esqe/baseline_reader.py` | 240 | 4 | — | — | `graph_nodes`, `l1_extraction_results`, `org_mission_critical_entities`, `source_events` |
| `esqe/bundle.py` | 239 | 7 | — | — | — |
| `domain/proposer.py` | 234 | 2 | — | — | — |
| `acquire/need_executor.py` | 229 | 2 | — | — | — |
| `structured/lane.py` | 225 | 2 | — | — | — |
| `esqe/signal_states.py` | 222 | 4 | — | — | — |
| `journey.py` | 214 | 2 | — | — | `event_trace`, `source_events` |
| `coverage/audit.py` | 213 | 1 | — | — | — |
| `parked/drain.py` | 213 | 2 | — | `parked_events`, `source_events` | `event_trace`, `parked_events`, `raw_payloads`, `source_events` |
| `coverage/window.py` | 211 | 1 | — | — | `l1_sync_runs` |
| `esqe/domain.py` | 209 | 1 | — | — | — |
| `connectors/calendar.py` | 206 | 0 | — | — | — |
| `transcripts/speakers.py` | 206 | 6 | — | — | `graph_aliases`, `graph_nodes`, `org_seats` |
| `connectors/push_ingest.py` | 200 | 1 | — | — | — |
| `structured/coverage.py` | 199 | 1 | — | — | — |
| `delivery_status.py` | 196 | 3 | — | — | — |
| `acquire/scheduler.py` | 194 | 5 | — | — | — |
| `connectors/attendees.py` | 189 | 4 | — | — | — |
| `acquire/cadence.py` | 185 | 4 | — | — | — |
| `connectors/linear.py` | 182 | 0 | — | — | — |
| `structured/apply.py` | 180 | 3 | — | — | — |
| `structured/product_usage.py` | 179 | 2 | — | — | — |
| `coverage/signal_coverage.py` | 178 | 1 | — | — | — |
| `coverage/store.py` | 175 | 1 | — | `source_coverage` | `source_coverage` |
| `coverage/declaration.py` | 174 | 3 | — | — | `source_events` |
| `coverage/symmetry.py` | 174 | 1 | — | — | — |
| `esqe/review_candidates.py` | 167 | 2 | — | — | — |
| `validate/directness.py` | 164 | 2 | — | — | — |
| `coverage/model.py` | 162 | 3 | — | — | — |
| `documents/transcript.py` | 158 | 3 | — | — | — |
| `intake.py` | 155 | 4 | — | — | — |
| `esqe/instants.py` | 154 | 2 | — | — | — |
| `acquire/evidence_need.py` | 153 | 2 | — | — | — |
| `connectors/hubspot.py` | 153 | 0 | — | — | — |
| `landing/unread.py` | 146 | 5 | — | `source_events` | `l1_extraction_results`, `l1_semantic_activation`, `l2_processing_runs`, `qualified_signals`, `raw_payloads`, `source_events` |
| `esqe/finalize.py` | 143 | 1 | — | — | — |
| `documents/base.py` | 141 | 0 | — | — | — |
| `gate/gate.py` | 141 | 1 | — | — | — |
| `connections/store.py` | 140 | 0 | — | `connections` | `connections` |
| `domain/coverage.py` | 140 | 1 | — | — | — |
| `capture_health.py` | 138 | 4 | — | — | — |
| `internal_knowledge.py` | 138 | 4 | — | — | — |
| `esqe/classifier.py` | 132 | 2 | — | — | — |
| `connectors/dispatch.py` | 130 | 4 | — | — | — |
| `documents/pages.py` | 130 | 2 | — | — | — |
| `domain/ontology.py` | 126 | 3 | — | — | — |
| `prepared_store.py` | 126 | 1 | — | `prepared_content` | `prepared_content` |
| `connectors/base.py` | 123 | 0 | — | — | — |
| `events_store.py` | 123 | 1 | — | `agent_events`, `agent_registry`, `human_events` | `agent_registry` |
| `documents/router.py` | 119 | 2 | — | — | — |
| `acquire/catchup.py` | 102 | 1 | — | — | — |
| `connectors/backfill.py` | 102 | 2 | — | — | — |
| `connectors/thread_position.py` | 101 | 2 | — | — | — |
| `visibility_rules.py` | 100 | 1 | — | — | — |
| `connectors/notion.py` | 99 | 0 | — | — | — |
| `preprocess/quoted.py` | 99 | 2 | — | — | — |
| `documents/ocr_policy.py` | 98 | 2 | — | — | — |
| `documents/enablement.py` | 97 | 2 | — | — | — |
| `parked/store.py` | 96 | 1 | — | `parked_events` | `parked_events` |
| `landing/pg_repository.py` | 91 | 0 | — | `source_events` | `source_events` |
| `preprocess/pii.py` | 91 | 2 | — | — | — |
| `acquire/cursor_store.py` | 84 | 0 | — | `sync_cursors` | `sync_cursors` |
| `connectors/database.py` | 81 | 0 | — | — | — |
| `intent_rate.py` | 80 | 2 | 2 | — | — |
| `acquire/jitter.py` | 79 | 1 | — | — | — |
| `documents/fake.py` | 75 | 0 | — | — | — |
| `connectors/composio_push.py` | 70 | 2 | — | — | — |
| `payload_store.py` | 67 | 0 | — | `raw_payloads` | `raw_payloads` |
| `landing/normalize.py` | 66 | 1 | — | — | — |
| `preprocess/text.py` | 66 | 2 | — | — | — |
| `documents/store.py` | 59 | 0 | — | `document_jobs` | — |
| `documents/tesseract.py` | 59 | 1 | — | — | — |
| `esqe/__init__.py` | 56 | 0 | — | — | — |
| `landing/reread.py` | 53 | 1 | — | — | — |
| `connectors/composio_base.py` | 52 | 0 | — | — | — |
| `trace_store.py` | 52 | 0 | — | `event_trace` | — |
| `connectors/fake.py` | 47 | 0 | — | — | — |
| `triage/triage.py` | 43 | 1 | — | — | — |
| `landing/repository.py` | 42 | 0 | — | — | — |
| `gate/context.py` | 35 | 0 | — | — | — |
| `preprocess/preprocess.py` | 31 | 1 | — | — | — |
| `structural/__init__.py` | 24 | 0 | — | — | — |
| `source_families.py` | 23 | 0 | — | — | — |
| `documents/__init__.py` | 17 | 0 | — | — | — |
| `semantic/__init__.py` | 12 | 0 | — | — | — |
| `structured/__init__.py` | 10 | 0 | — | — | — |
| `validate/__init__.py` | 8 | 0 | — | — | — |
| `gate/__init__.py` | 6 | 0 | — | — | — |
| `__init__.py` | 5 | 0 | — | — | — |
| `transcripts/__init__.py` | 4 | 0 | — | — | — |
| `acquire/__init__.py` | 0 | 0 | — | — | — |
| `connections/__init__.py` | 0 | 0 | — | — | — |
| `connectors/__init__.py` | 0 | 0 | — | — | — |
| `coverage/__init__.py` | 0 | 0 | — | — | — |
| `domain/__init__.py` | 0 | 0 | — | — | — |
| `landing/__init__.py` | 0 | 0 | — | — | — |
| `parked/__init__.py` | 0 | 0 | — | — | — |
| `preprocess/__init__.py` | 0 | 0 | — | — | — |
| `screen/__init__.py` | 0 | 0 | — | — | — |
| `triage/__init__.py` | 0 | 0 | — | — | — |
