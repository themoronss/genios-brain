# STEP-18 · TO BUILD · the live bugs already found — each with its seam and its probe

**Owner:** Claude. **Runs alongside**, one bug at a time, each in the step whose files it touches
where one exists. **Moves:** each bug's production probe goes green.

| # | Bug | Seam | Probe (read-only) | Status / where it is fixed |
|---|---|---|---|---|
| B1 | weekly calibration errors on every run since 10 Sep | `feedback/calibrate.py:109` filters `card_level`; `reason/authority.py:329` never projects it | `select max(evaluation_time) from calibration_runs` | fix in `STEP-16` §3.6, **auto-mute in shadow** |
| B2 | four writers emit edge types the closed vocabulary refuses — the whole event rolls back and parks as *"model unavailable"* | `context/graph_store.py` `EDGE_TYPES` lacks `involves` (`context/pipeline.py:1463`), `edited`, `assigned`, `used` | `l2_processing_runs` with `last_error like 'unknown edge_type%'` | add them with their meaning; `STEP-17` §3.3 guards it |
| B3 | 8 of 11 feedback reasons return 500 | `migrations/0034:168, 189` | the API itself | `STEP-16` §3.1 |
| B4 | a weekly human-review learning object can never be reviewed (409) | state stays `governed`; `api/learning_routes.py:137` wants `human_review` | — | write `human_review` when sending to review |
| B5 | per-signal coverage is always NULL; five conversation columns never filled | `_coverage_of` needs `summary.source`, which `SyncSummary` lacks; `_row_for` never supplies them | `qualified_signals.coverage is null` share | needed by `STEP-10` §3.10 |
| B6 | bounce reports never become `DELIVERY_FAILURE` | `[PROD]` 5 DSNs junked by the AI filter, 8 parked on the attached original; `capture/gate/rules.py:54-56` | `source_events` from `mailer-daemon` by outcome | admit delivery reports deterministically before S2; never park a DSN for its attached original (`STEP-10` §3.5) |
| B7 | the JWT secret defaults to a known string with no boot check | `platform/config.py:37` | — | refuse to boot outside `dev` with the default |
| B8 | `fundraising` and `general` can never be live | `reason/domain_shadow.py:512-526`; alias `packs/compiler/capability_resolver.py:35-47` | — | `STEP-11` §3.1 |
| B9 | the decider's daily cap is an in-process counter, reset on restart, with no dollar governor | `reason/llm_decision_maker.py:201-218`; `platform/config.py:81-88` | `llm_costs` per day vs 400 | `STEP-02` and `STEP-12` §3.3 |
| B10 | `vendor-relationship-live` can never match | gate `relationship.direction = outbound`; the writer emits only `they_evaluate_us\|we_evaluate_them\|peer` (`context/pipeline.py:414, 1836-1844`) `[inference]` | — | correct the gate in the corpus |
| B11 | the behaviour brain labels the counterparty's latency as the company's own | `packs/brains/behavior_distill.py:106` `[inference]` | — | relabel; `STEP-10` §3.2 computes both |
| B12 | `rebuild_graph.py` rebuilds only structured events | `scripts/rebuild_graph.py:77-83` never selects `qes_output` `[inference]` | — | select it |
| B13 | screen follow-ups can write duplicate graph observations | `reason/moments/followups.py:629-632` resets `graph_written_at`; each write mints a new id `[inference]` | observations per follow-up > 1 | key the observation on the follow-up |
| B14 | the parked drain re-selects the oldest rows every tick and starves newer ones | `capture/parked/drain.py:104-118` | — | `STEP-06` §3.5 |
| B15 | the slot reads *"they normally reply in N days"* from firm- or tenant-level evidence | `deliver/slots.py:212` ignores `party.reply_cadence_basis` `[inference]` | — | say the basis, or say *"we cannot judge"* |
| B16 | `ASK_KINDS` and `observations/kinds.yaml` disagree on what is an ask | `contracts/open_loop.py:24` | — | `STEP-09` §3.6 |

Each bug is fixed with a test that fails when the fix is reverted, and its probe is re-run on
production before the row is marked done.
