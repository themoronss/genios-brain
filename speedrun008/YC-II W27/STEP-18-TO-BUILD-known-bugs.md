# STEP-18 · TO BUILD · the live bugs already found — each with its seam and its probe

**Owner:** Claude. **Runs alongside**, one bug at a time, each in the step whose files it touches
where one exists. **Moves:** each bug's production probe goes green.

B1, B2 and B17–B20 are now units of the tree block `yc2_w27` in `tree.yaml` (proposed 2026-10-05,
awaiting Rohit's go). B20–B24 were found by the 2026-10-05 root-cause runs on the scratch database.

✅ **2026-10-06: B1, B2 and B17–B20 are fixed in code — none is deployed.** Built on Rohit's go
(`yc2_w27`, `00-START-HERE.md`); each row names its commits. A row is done only when its probe is
re-run on production after the batch is pushed and deployed (`06` D10) — so every one stays open
here until then. The golden set (`STEP-01`) found twelve more the same day, `03-FINDINGS.md`
F38–F49, each with the step it belongs to; F42 — a paid relevance call on every calendar event,
about nothing — has no step yet and is the next small unit.

| # | Bug | Seam | Probe (read-only) | Status / where it is fixed |
|---|---|---|---|---|
| B1 | weekly calibration errors on every run since 10 Sep (`cd7f85d7`) — and **the obvious one-line fix arms unattended auto-muting** | `feedback/calibrate.py:109` filters `card_level` from `canonical_judgments`; `reason/authority.py:329-332` builds that CTE without it. Reproduced on Postgres 2026-10-05: `UndefinedColumn card_level`, every 6 h heavy tick, every org with an active connection; `precision_28d` fails the same way. The guard (`tests/contracts/test_the_outcome_vocabulary_is_wired.py:212-217`) counts text | `select max(evaluation_time), count(*) from calibration_runs` | **tree `yc2_w27/M18`**: shadow switch first (`run_calibration(apply=False)`, `calibration_apply` not default-on), then the column. Arming is `06` D13, after B22–B24 · ✅ **code-fixed** `184269a0`, not deployed |
| B2 | four writers emit edge types the closed vocabulary refuses — the whole event rolls back and parks as *"model unavailable"*. **27 of the 50 database-suite failures** (`STEP-00` §4.2). ⛔ **Latent in production today, live at `STEP-05` — fix it before `STEP-05`** | `context/graph_store.py:171` `EDGE_TYPES` (6) lacks `involves` (`context/pipeline.py:1463`; `capture/structured/registry.py:165-166`), `edited` (`context/documents.py:67, 263`), `assigned` (`capture/structured/registry.py:187`), `used` (`capture/structured/product_usage.py:121`) | `baseline/production_state.sql` `@l2_processing_runs` — 2026-10-05: 30 runs, 0 edge errors, because memory is gated on a signal and almost nothing reaches these writers | add the four with their meaning; `STEP-17` §3.3 guards it. Turns 27 database tests green · **tree `yc2_w27/M16.C1`** · ✅ **code-fixed** `d8c83cb4`, not deployed |
| B3 | 8 of 11 feedback reasons return 500 | `migrations/0034:168, 189` | the API itself | `STEP-16` §3.1 |
| B4 | a weekly human-review learning object can never be reviewed (409) | state stays `governed`; `api/learning_routes.py:137` wants `human_review` | — | write `human_review` when sending to review |
| B5 | per-signal coverage is always NULL; five conversation columns never filled | `_coverage_of` needs `summary.source`, which `SyncSummary` lacks; `_row_for` never supplies them | `qualified_signals.coverage is null` share | ✅ **code-fixed by `STEP-10`** (`yc2_w27_s10` C5, `1b1898a4`: the sync summary says its source and start, so a signal carries its coverage) — pushed 9 Oct, not deployed |
| B6 | bounce reports never become `DELIVERY_FAILURE` | `[PROD]` 5 DSNs junked by the AI filter, 8 parked on the attached original; `capture/gate/rules.py:54-56` | `source_events` from `mailer-daemon` by outcome | ✅ **code-fixed by `STEP-10`** (`06` D38: a delivery report is kept at the gate and read, its original is not a document of its own, and the bounce is a fact on the file — `context/delivery.py`) — pushed 9 Oct, not deployed |
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
| B17 | the funnel never records a zero decision: in every sweep that emitted nothing, `decision_emitted` reads *"nobody looked"* | `reason/runner.py:860` counts into a `Counter` and increments `emitted` only on an emission (`:1364`); `dict(out)` (`:1315, 1462, 1466`) carries no zero; `api/routes.py:774-775` relays `.get("emitted")` → `None` → no row (`:734-735`). Migration `0188` and `platform/funnel.record` both say a zero is written — the relay loses it one hop earlier. It also relays only the rule lane: `native_emitted` (`:1400`) and `composite` (`:1420`) never reach the stage | `@funnel_per_stage` — 2026-10-05: 64 sweeps since 3 Oct; `capability_resolved` written in 59, `decision_emitted` in 3, its values 1–4 and never 0 | `STEP-06` §3.2: the runner returns `emitted` as a count, zero included. Whether native and composite emissions belong in the stage is decided there, not assumed · **tree `yc2_w27/M17.C1`** · ✅ **code-fixed** `94a93d9f` — the zero is written and every lane counted; not deployed |
| B18 | the extractor's four park codes are in no drain set — a mail whose extraction did not parse waits forever, and the funnel counts it as *kept unread* | `capture/semantic/extractor.py:199-210` parks under `extraction_call_failed`, `extraction_parse_failed`, `extraction_schema_failed`, `extraction_total_loss`; none is in `capture/parked/drain.py` `RE_ADJUDICABLE` / `NEEDS_REFETCH` or `recapture.py:65` `NEEDS_RECAPTURE`. The drain's own comment (`drain.py:55-61`) names this shape: *"the documents sit at status='pending' forever while every surface that could show them reads clean"*. `tests/capture/parked/test_park_code_coverage.py` reads park sites from `capture/gate/` only, so it cannot see these | `@park_queue` — 2026-10-05: 2 mails, `extraction_parse_failed`, pending since 3 Oct 11:17 UTC, 0 attempts, no next attempt | `STEP-06` §3.1: give the four codes a class and a retry (the payload is retained); widen the coverage test to `capture/semantic/` · **tree `yc2_w27/M17.C2`** · ✅ **code-fixed** `9bfd911e`, `5c892922`, `2e76cf4a`, not deployed |
| B19 | **no Gmail attachment is read** — Composio refuses every attachment fetch: *"Missing required fields: file_name"* | `capture/connectors/composio.py:298-299` sends `GMAIL_GET_ATTACHMENT` only `message_id` and `attachment_id`. At capture the failure is swallowed into an empty stub (`:313-318`) that parks as DOC-02 / DOC-05; every refetch then fails the same way, and an unknown error is retried as `transient` by design (`capture/parked/refetch_policy.py:479-490`) until it dead-letters | `@attachment_refetch_errors` — 2026-10-05: 88 of 88 stored errors are this one; 50 dead-lettered after 5 tries, 38 pending, 0 ever recovered. Among them: Khushi's two attachments and NSRCEL's 22 (`04` §2) | send `file_name` — both paths already hold the filename (`composio.py:650`, the attachment's own entry; `capture/parked/refetch.py:339`) — after checking the field against Composio's tool schema; then re-queue the 50 dead letters. Harsh's area (`d4e035bb` made this reason readable) · **tree `yc2_w27/M17.C3`** · ✅ **code-fixed** `681a85e3` (the field; a response with no bytes now names its shape), `8ca130a3` (the re-queue script) — not deployed. After the deploy: `scripts/requeue_refused_attachments.py --org … --apply`, then read the first `refetch_last_error`. ⛔ The toolkit pin, `M17.C3.L-integration.V2.U04`, is blocked on Harsh — it needs the SDK the production image runs |
| B20 | **a disconnect-with-wipe, then a reconnect, extracts nothing** — every re-synced message is skipped as *seen on screen* | `api/routes.py:3207-3211` (`integration_disconnect(wipe_data=true)`) and `scripts/gmail_l1.py` delete `source_events` but not `message_fingerprints`; `capture/screen/fingerprint.py` `claim`: first seen wins, even when that event is gone. The tenant reset does delete them (`api/account_routes.py:651`). Found through the G7/G8/G10 tests, which fail the same way | after a reconnect: `select count(*) from event_trace where reason_code = 'seen_on_screen'` against messages whose canonical event no longer exists | **tree `yc2_w27/M17.C2.L-data.V0.U02`** (a claim by a gone event is void). ⛔ **Before `STEP-08`** · ✅ **code-fixed** `36567231`, `ba0577e3`, not deployed |
| B21 | a decimal number in a parsed model answer aborts the org's whole resolution pass | `context/model_audit.py:49` hashes the parsed answer, and `platform/canonical.py:51-53` refuses floats; in `context/lifecycle/resolution.py:221` it runs before `result.ok` is checked, outside any try | `l2_model_runs` (site `resolution`) vs `llm_costs` (`l2:resolution`), per hour — 2026-10-05: equal since the 3 Oct reset, so **latent** | audit the parsed answer as integers or strings, never refuse after the call is paid; `STEP-12` (the expert pass audits the same way) |
| B22 | once calibration is armed, a muted rule's cards vanish with no suppression row — `why_not` cannot explain it | `reason/runner.py:1076` skips the rule and writes nothing; `executive/explain.py:16` has the text for a reason nobody records | a muted rule with open cards and no suppression row | before arming (`06` D13), `STEP-16` |
| B23 | a mute is permanent until the pack version changes — there is no unmute path | a muted rule produces no new judgments under the new revision, so recovery can never trigger (`feedback/calibrate.py:326-354`) | `rule_mutes` rows older than their window | before arming, `STEP-16` |
| B24 | ⛔ **any applied mute or nudge hides every open card of that pack**, and they do not come back | the revision bump (`feedback/calibrate.py:389-400`) fails `reason/authority.py:254`; regeneration then reads the previous signal (`reason/runner.py:262-270`) and suppresses as `no_new_evidence` (`:1238-1257`). On Postgres a *loosening* nudge took the queue from 5 to 0 | open cards per pack before and after a calibration run | before arming, `STEP-16` |
| B25 | the relevance page asks the model about every calendar event, with *"(no readable text)"* as the item — a paid call per event about nothing (`03` F42) | `capture/gate/relevance.py` — the page is built from every object of the sweep, a structured calendar record included | `@llm_calls_by_site` — relevance calls against calendar events in the same sweep | open — owner given 10 Oct (`yc2_w27_align` M34.C3.L-contract.V1.U02) |
| B26 | the AI filter still answers keep or drop, and its prompt still names *automated matchmaking* and *self-service* as junk (`03` F02; STEP-03 §3.5 — *"the AI filter decides attention, with context"* — was planned after STEP-07 and not built) | `capture/gate/relevance.py:65-122, 233-268` | the junk verdicts by sender domain, read-only | open — owner given 10 Oct (M34.C3 U02) |
| B27 | an archive made on the connector's fast path holds the list snippet, and promotion re-reads that snippet — nothing fetches the body (`03` F58) | `connectors/composio.py` fast path; `capture/landing/unread.to_raw_object` reads the stored payload; `capture/landing/resync` frees deleted mail only | archives whose payload is a snippet, by rule code | open — owner given 10 Oct (M34.C3 U02) |
| B28 | coverage compares objects with messages: `scanned` counts a message and each attachment, the provider's total counts messages — capped and labelled an estimate since STEP-10 (`03` F110) | `capture/coverage/window`; a summary field needs a migration | the coverage receipt against the listed-message count | open — owner given 10 Oct (M34.C3 U02) |
| B29 | a poison-quarantined object stores nothing and has no drain — the parked drains cannot re-read it (`03` F154) | `capture/acquire/sync_runner.py:751-758` | quarantined objects per sync run | open — owner given 10 Oct (M34.C3 U02) |

Each bug is fixed with a test that fails when the fix is reverted, and its probe is re-run on
production before the row is marked done.

## 8 · The check of 2026-10-12 — every row at `fbd0aeaa`, and what is built now

Re-checked row by row against branch `yc2w27-s18` @ `fbd0aeaa` (STEP-13 nearly built), by reading each
seam at that commit. Layers are named the product's way, with the package beside each: L1 Signals
(`capture/`), L2 Signals Qualification — Plane D (`packs/`) and Plane R (`reason/`), L3 Context Graph
(`context/`), L4 Executive (`executive/`), L5 Delivery (`deliver/`), L6 Learning (`feedback/`).

**The count.** Of the 29 rows: **8 fixed** by earlier steps (B1, B2, B5, B6, B14, B17, B18, B19),
**2 half fixed** (B8, B20), **1 retired** by STEP-09's own measurement (B16), **18 live**. Of the 18:
**8 are built here** (B3, B4, B7, B11, B12, B13, B21, B25 — and B20's second half; §8.6); **10 are left** —
a decision (B9, B10, B26), arming (B22–B24, behind `06` D13), a recorded prompt (B15) or a design of
their own (B27–B29). Of the sixteen rows of `03` that name STEP-18, **six are built here** (F65, F97,
F117's bounce, F120, F128, F135) and ten are left, each with its reason (§8.2).

### 8.1 · The rows

| # | Now | Evidence at `fbd0aeaa` | What happens to it |
|---|---|---|---|
| B1 | ✅ fixed | `feedback/calibrate.py:239-262` runs in shadow unless `apply`; `reason/authority.py:278, 332-335` carries `card_level` (`184269a0`, `yc2_w27/M18`) | not deployed; arming is `06` D13 |
| B2 | ✅ fixed | `context/graph_store.py:178-205` — `involves`, `edited`, `assigned`, `used` declared (`d8c83cb4`, `M16.C1`) | not deployed |
| B3 | ❌ **live** — L6 Learning (`feedback/`) | `migrations/0034_l4_learning_authority.sql:166-168, 187-189` allow 3 reasons; the route accepts all 11 (`api/intelligence_routes.py:956` = `deliver/actions.py:42` = `contracts/learning_attribution.ALL_REASONS`) and inserts at `:1071` — 8 of 11 are a 500 | ✅ **built** — `yc2_w27_s18` M48.C1.L-contract.V0.U01 (`0210`; `61d679ed`, fix `360c8596`), ahead of STEP-16 §3.1, which planned exactly this. Arms nothing: calibration is shadow; the Adaptive lease counts `bad_timing` only, so a new reason only adds to its denominator (`packs/brains/adaptive_lease.py:150-158`) |
| B4 | ❌ **live** — L6 Learning (`feedback/`) | `feedback/orchestrator.py:277` persists at `governed`; `feedback/publisher.py:242-245, 278` logs `governed → human_review` and never moves the row; `api/learning_routes.py:136` answers 409 | ✅ **built** `4b4aefbd` (fix `a059ab81`) — M48.C1.L-data.V0.U02; the wider shape is s18-F3 |
| B5 | ✅ fixed by STEP-10 | `capture/esqe/publisher.py:1064-1081` (`_coverage_of` reads the summary's source and start), `:385-396, 475` (the five conversation columns of `0181`) — `1b1898a4` | not deployed |
| B6 | ✅ fixed by STEP-10 | `context/delivery.py:70`; `capture/gate/rules.py:51-56, 219-235` (`06` D38) | not deployed |
| B7 | ❌ **live** — platform | `platform/config.py:37` ships a default secret; `platform/auth.py:266`, `platform/sessions.py:93` sign and verify with it; `main.py:64-110` checks nothing at boot | ✅ **built** `f390fbeb`, `23af52f5` — M49.C3 U07, U08. ⛔ Deploy precondition (s18-F11): production's `GENIOS_JWT_SECRET` is set first |
| B8 | ½ | `fundraising` → the Founder Office (`reason/domain_shadow.py:925`, `packs/compiler/capability_resolver.py:45`; STEP-11 `c3b494dc`); `general` → `None` by declaration (`domain_shadow.py:926-929`: `relationship` is claimed by all three older corpora) | left — `general`'s route is a choice, Rohit's |
| B9 | ❌ live — L2 Plane R (`reason/`) | `reason/llm_decision_maker.py:211-228` counts in process; no dollar check before the call (`:798-799`) | left — a decision (s18-F4): a durable cap starts deferring decisions that today go through |
| B10 | ❌ live — the Admin corpus | `vendor-relationship-live.yaml:36-39` gates `relationship.direction = outbound`; the writer's vocabulary is `they_evaluate_us · we_evaluate_them · peer` (`context/pipeline.py:419`, `context/extract/prompt.py:49`) | left — correcting the gate opens a live Admin situation (new cards), and the corpus is its authors' (`06` D45) |
| B11 | ❌ **live** — L2 Plane D (`packs/`) | `packs/brains/behavior_distill.py:105` calls `relationship.response_latency_hours` "how fast this company answers"; it is our outbound to THEIR next inbound (`context/analytic/sampler.py:709-728`) | ✅ **built** `5b991ecf` — M49.C2.L-logic.V0.U03; already-published entries: s18-F9 |
| B12 | ❌ **live** — L3 Context Graph (`context/`) | `scripts/rebuild_graph.py:79-85` selects no cached extraction and only `emitted`; `context/runner.py:178-186` holds such a mail `held_missing_qes_extraction` — a rebuild restores the calendar and none of the mail | ✅ **built** `e0c55aa8` (fix `82acda6f`), `eddc2d2b` — M48.C2 U04 (the read), U05 (the script) |
| B13 | ❌ **live** — L2 Plane R (`reason/moments`) into L3 | `reason/moments/followups.py:629-632` clears `graph_written_at` on a change; `screen_memory.py:64-98` writes a new observation each time with a fresh id (`context/graph_store.py:948`) and leaves the old one active | ✅ **built** `8fa82a42` (0211, added in build: M48.C2.L-contract.V0.U12), `14beeff1` — M48.C2.L-data.V0.U06 |
| B14 | ✅ fixed by STEP-06 | `capture/parked/drain.py:136-149` (`b2ae9e86`, `M24.C5.L-data.V1.U01`) | not deployed |
| B15 | ❌ live — L5 Delivery (`deliver/`) | `deliver/slots.py:212, 255` fill *"they normally reply in about N days"* (`outbound-awaiting-reply.yaml:143-145`) whatever `outreach.their_normal_reply_basis` says — firm, tenant, or the floor `context/waiting.py:302-306` calls "not a cadence" | left — the fix changes a recorded narrator prompt (golden F55's): s18-F10, the lead's |
| B16 | retired | STEP-09 §8.2, §8.3.6: `is_ask` and `ASK_KINDS` mean different things; adding `approval_requested` opens a wrong loop on F25 | s18-F8 — STEP-09's declaration stands |
| B17 | ✅ fixed | `94a93d9f` (`M17.C1`) | not deployed |
| B18 | ✅ fixed | `9bfd911e`, `5c892922`, `2e76cf4a` (`M17.C2`) | not deployed |
| B19 | ✅ fixed | `681a85e3`, `8ca130a3` (`M17.C3`) | not deployed; the toolkit pin (`M17.C3.L-integration.V2.U04`) is Harsh's |
| B20 | ½ | the disconnect ✅ (`api/routes.py:3323-3326`, `ba0577e3`); a set-aside claim is void ✅ (`capture/screen/fingerprint.py:115-146`, `36567231`); **`scripts/gmail_l1.py:18-24` still deletes events and leaves their fingerprints**, and a claim by a deleted event is still honoured | ✅ **built** `acd298bb` — M48.C3.L-data.V0.U11 (s18-F2) |
| B21 | ❌ **live** — L3 Context Graph (`context/`) | `context/model_audit.py:49` hashes the parsed answer through `platform/canonical.py:51-53`, which refuses floats; `context/lifecycle/resolution.py:234-241` audits before it reads `ok` | ✅ **built** `1c311b79` — M48.C2.L-logic.V0.U03. The golden set's 99 recorded resolution answers hold no float — its board does not move |
| B22 | ❌ live, inert while calibration is shadow | `reason/runner.py:1360-1362` skips a muted rule and records nothing | left — `STEP-16`, before arming (`06` D13) |
| B23 | ❌ live, inert | `feedback/calibrate.py:310-360` — recovery needs judgments under the muted rule's own pack version | left — `STEP-16`, before arming |
| B24 | ❌ live, inert | `feedback/calibrate.py:389-400` bumps the revision; its seam is `reason/authority.py:254` | left — `STEP-16`, before arming; `reason/authority.py` is STEP-13's while it builds |
| B25 | ❌ **live** — L1 Signals (`capture/`) | `capture/pipeline.py:1369-1385` builds the page candidate with no `is_structured` (`capture_event` routes the same object structured, `:1588-1590`), so a calendar event is pre-judged at `capture/esqe/relevance.py:883-945` and decided by rule anyway (`:513-514`) | ✅ **built** `490a6a51` — M49.C1.L-logic.V0.U01 (s18-F6). The golden runner lands calendars on their own pages: no mail prompt changes, the calendar pages' answers go unasked |
| B26 | ❌ live — L1 Signals (`capture/gate`) | `capture/gate/relevance.py:72, 79, 105-108` still name self-service and automated matchmaking as junk; `:91, 119` still answer keep or drop | left — a prompt (every `junk_gate` answer re-recorded, the lead's) and a policy of what is kept (STEP-03 §3.5, STEP-07): a decision |
| B27 | ❌ live — L1 Signals (`capture/`) | the fast path keeps a confident drop's list snippet (`capture/connectors/composio.py:539-552`); a promotion re-reads the stored payload (`capture/landing/unread.py:74-96`) | left — a design: a promotion that fetches the body through the connector |
| B28 | ❌ live — L1 Signals (`capture/`) | `capture/acquire/sync_runner.py:699` counts a message and each attachment; the provider's total counts messages | left — a migration and a connector field, and the coverage line reaches the expert's dossier (a re-record) |
| B29 | ❌ live — L1 Signals (`capture/`) | `capture/acquire/sync_runner.py:783-790` parks `poison_quarantine` with nothing kept; the drains class it terminal (`tests/capture/parked/test_drain_surfaces.py:142`) | left — a design: an object that never landed has no event to keep a payload under |

### 8.2 · The rows of `03` given to STEP-18

| # | Now | Evidence at `fbd0aeaa` | What happens to it |
|---|---|---|---|
| F65 | ❌ **live** — L3 (`context/`) | `context/backfill.py:680` opens a connection inside an expression; its twin is `reason/runner.py:343` (s18-F1) | ✅ **built** `e617d15c`, `32b093af` — M48.C2 U09 (with a guard), U10 |
| F79 | ❌ live — L1 (`capture/gate`) | the junk batch is primed on known senders and duplicates (`capture/gate/relevance.py:244-264`), whose verdicts `classify` never reads (`:303-304`) | left — the batch prompt changes on every golden page with a known sender: a re-record, the lead's |
| F97 | ❌ **live**, latent — platform | `platform/company_brief.py:51-80` — a connection is `conn.engine`, read through a second connection and cached | ✅ **built** `28b07068` — M49.C2.L-logic.V0.U04 |
| F100 | ❌ live — platform | `platform/table_coverage.py:227` — any string opening with `with`, `select`, `update`, `delete` or `insert` counts as SQL | left — the instrument behind the statement pin and the resolver's ratchet; changing it moves every count those guards hold, so it is measured first (`STEP-17`) |
| F108 | ❌ live, conservative — L1 (`capture/coverage`) | `capture/coverage/window.py:313` needs every run exhausted; a multi-round backfill's earlier rounds never are | left — a backfill's rounds carry no shared id; it errs towards saying less |
| F109 | ❌ live — L1 | `connections.external_account_id` has no writer (`api/routes.py:863`) | left — writing it needs a provider call, and the column IS "us" (`platform/self_identity.py:134-135`): STEP-04's kind of decision |
| F111 | ❌ live — L3 (`context/`) | `context/pipeline.py:1373` skips only our exact addresses | left — it changes a campaign's counts, which reach the cards on production-shaped golden cases: measure with the lead first |
| F117 | ❌ **live** — L1 (`capture/connectors`) | a bounce is primed and may be left a snippet (`capture/connectors/composio.py:503-536`, s18-F5); a kept message's attachments are downloaded on the light pass and again on the full fetch (`:582-608, 719-735`) | ✅ **built**, the bounce, `3f95fb04` — M49.C1.L-logic.V0.U02. The double download is left: a dropped message's light objects travel on, so skipping their download first needs `worth` and `_is_extractable_part` proven equal |
| F120 | ❌ **live** — L1 (`capture/coverage`), L3 (`context/`) | `capture/coverage/window.py:208-217` and the source list of `context/situations.window_coverage_gaps` swallow a failed statement with no savepoint | ✅ **built** `1ec3ab3a`, `371a5b1e` — M48.C2 U07, U08 |
| F128 | ❌ **live** — L1 → L3 | `capture/structured/apply.py:24-25` (8 hosts, read by `context/pipeline.py:225` and `context/introductions.py:64`) against `capture/validate/canonical.py:185-191` (24) | ✅ **built** `75264c4b` — M49.C2.L-logic.V0.U05. No golden case writes from the 16 hosts |
| F135 | ❌ **live** — scripts | `scripts/activate_tenant.py` keeps its own `EFFECT` table, with no `founder_office` | ✅ **built** `668acf90` — M49.C2.L-interface.V0.U06 |
| F158 | ❌ live — L3 (`context/`) | Layer 3 still anchors a file on a company NAMED for us (golden F02); STEP-12 only keeps the expert away from it | left — it moves F02's files, situations and recorded prompts: a re-record, the lead's |
| F159 | ❌ live — L3 (`context/`) | `context/workstreams.py:496-504` takes a future booking as the last touch | left — a situation's last-seen feeds the decider's and the dossier's words (recorded prompts) |
| F165 | open, a decision | an undated promise never enters memory (`context/pipeline`, `if subj and (due or transcript_mode)`) | left — `06` D56 first |
| F166 | ❌ live — L3 / the expert's dossier | open asks and whose move (golden F02, F38, F45, F50, F51, F55, F58) | left — the dossier is `reason/expert/` (STEP-13's while it builds), and every fix moves recorded expert prompts |
| F180 | measured — L4 Executive (`executive/`) | the two copies have drifted (s18-F7) | left — `STEP-15` |

### 8.3 · New — not in the plan

Provisional ids; the lead numbers them in `03` when merging. (A separate `findings.md` was refused by the
worker's harness, so they live here.)

| # | Finding | Evidence | Owner |
|---|---|---|---|
| s18-F1 | **F65 has a twin on the live sweep path.** `reason/runner._bulk_load_situations` — every node's situation, once per org per sweep — opens a connection inside an expression and never closes it | `reason/runner.py:343`; `context/backfill.py:680`; no third site in `genios_engine/` or `scripts/` | `yc2_w27_s18` M48.C2.L-data.V1.U10 |
| s18-F2 | **B20 is half fixed.** `scripts/gmail_l1.py` deletes the gmail events and leaves their fingerprints, and a claim by an event with no row is honoured by design — so a re-run of the script skips every re-synced message as `seen_on_screen`, silently | `scripts/gmail_l1.py:18-24`; `capture/screen/fingerprint.py:126-128` | M48.C3.L-data.V0.U11 |
| s18-F3 | **B4 is wider than its row.** Every object the weekly sweep publishes stays `governed` on its row whatever its sink — `temporary`, `published`, `human_review`, `rejected` are logged in `learning_transitions` and never written to the row; only the discovery path moves it. The review case is B4; for the rest the row disagrees with its own ledger, read today only by the review route and the console's queues | `feedback/orchestrator.py:277, 286`; `feedback/publisher.py:240-280`; `feedback/org_rule_ingest.py:107-110` | `STEP-16`. Probe, read-only: `learning_objects` by `state` against each object's latest transition |
| s18-F4 | **B9's cap has never bound.** Production made 718 · 477 · 1,204 · 306 decider calls a day (2–5 Oct) against 400 per org per day: the count lives in one process. A durable count would start deferring decisions on a busy day; and no one has chosen the dollar governor's default | `reason/llm_decision_maker.py:211-228, 798-799`; `[PROD]` `03` §F | Rohit — the number and the dollar default; then one unit |
| s18-F5 | **F117 loses a bounce's body.** A delivery report primed with a confident `drop` passes `_skip_body` and keeps its list snippet — the body the bounce parser reads (`06` D38) is never fetched | `capture/connectors/composio.py:503-536`; `capture/gate/rules.py:219-235` | M49.C1.L-logic.V0.U02 |
| s18-F6 | **B25's paid verdict was never read**, and a calendar page of unknown organisers raised the 10% "graph-coverage" alert about nothing | `capture/pipeline.py:1369-1385, 1588-1590`; `capture/esqe/relevance.py:513-514, 932-945` | M49.C1.L-logic.V0.U01 |
| s18-F7 | **F180's two copies have drifted**: `platform/grounding` carries a grammar-word list, accent folding and a haystack that `executive/validate.py` lacks — pointing the executive at one rule changes what passes on every executive surface | `platform/grounding.py:37, 135-269`; `executive/validate.py:19-74` | `STEP-15` |
| s18-F8 | **B16 was retired by measurement** (STEP-09 §8.2, §8.3.6) | `contracts/open_loop.py:21-28`; `context/observations/kinds.yaml:15-18` | STEP-09's declaration |
| s18-F9 | **B11's published entries have no retraction path**: once the metric leaves the eligible set, an entry published before stays active; the build names it `metric_not_ours` | `packs/brains/behavior_distill.py:232-264, 745-763` | Harsh — the probe: `select count(*) from learned_brain_entries where brain = 'behavior' and active and subject like 'behavior:relationship.response_latency_hours:%'`; a retraction path, if it is not 0, `STEP-16` |
| s18-F10 | **B15's fix reaches a recorded prompt.** The narrator is handed the same grounded `their_cadence` slot (`deliver/render.py:470-518`), so the fix changes the narrator's prompt wherever the basis is not the person's own; golden F55 holds the one recorded narrator answer | `deliver/slots.py:212, 255` | the lead — a unit in `deliver/slots.py`, with F55 re-recorded |
| s18-F11 | **B7 needs a deploy precondition.** The refusal fires where `GENIOS_ENV` names an environment outside dev and the secret is the shipped default; an unset `GENIOS_ENV` reads `dev`, as it always has | `platform/config.py:18, 37`; `docs/plans/TENANT_DATA_PRIVACY.md:49` | Harsh — confirm `GENIOS_JWT_SECRET` (and set `GENIOS_ENV`) in production before the deploy (`08`) |
| s18-F12 | **`scripts/activate_tenant.py` printed five blank effects, not one** — `founder_office` (F135) and four Layer 4 features (`situation_reasoner`, `cards_from_situations`, `calibration_apply` — the switch that arms muting — and `expert_review`); and the script can still neither plan nor flip those four (`PLAN` holds five features) | measured at `fbd0aeaa`; `scripts/activate_tenant.py:40-75, 155-180` | the effects: built (M49.C2.L-interface.V0.U06). Planning the four: Harsh (the operator's script) |
| s18-F13 | **Two root/reason guards are red at `fbd0aeaa`, before this branch**: `tests/test_the_situation_reaches_the_signal.py::test_what_each_writer_declares_matches_the_column_list_it_actually_has` (`reason/domain_shadow` now holds 2 signal inserts) and `tests/reason/test_every_card_expiry_says_why.py::test_no_other_function_in_these_files_calls_the_writer` (`domain_shadow._ask_the_founder`, `_retire_question`) — both from STEP-13 M36.C2.L-integration.V2.U03 (`1b6080fb`), in a file this branch may not touch | every group guard G1–G7 of this branch; `git diff fbd0aeaa HEAD -- genios_engine/reason/domain_shadow.py` is empty | the lead — STEP-13's M36.C2 |
| s18-F14 | **A timing guard reads the machine's load**: `tests/platform/test_the_coverage_report_does_not_mis_signal.py::test_the_report_is_fast_enough_to_re_run` (20 s bound) failed twice in seven platform runs at load average ~7 (20.5 s, 23.8 s) and took 16.3 s alone — `03` F156's shape | group guards G4 and G6 of this branch | `STEP-17` (real tests) |

### 8.4 · What will be built — tree block `yc2_w27_s18` (M48, M49)

Proposed in `baseline/yc2w27-s18/tree_s18.yaml` for the lead to merge into `tree.yaml`: **19 units**, every
one with one artifact, one verify command and its dependencies; critical path 2.

**M48 — what you tell it is kept, and nothing memory holds is aborted, lost or doubled.** C1 your verdicts
(L6 Learning, `feedback/`): `0210` — every wrong reason is kept (B3); a review object waits for review (B4).
C2 memory (L3 Context Graph, `context/`, and its writers): a decimal answer is audited (B21); the rebuild
reads every road, then the script replays it (B12); a screen follow-up has one observation (B13); a failed
coverage read loses itself alone, twice (F120); no read leaves its connection open, twice (F65, s18-F1). C3
a wipe takes its claims (L1 Signals, `scripts/`): `gmail_l1.py` (B20's second half).

**M49 — nothing is paid for that nothing reads, and what it says about itself is true.** C1 (L1 Signals,
`capture/`): a calendar event buys no relevance call (B25); a bounce is read whole on the fast path (F117).
C2: the behaviour brain holds our conduct (B11, L2 Plane D `packs/`); a brief read in a transaction sees it
(F97); one list of public mail hosts (F128); the activation script names every effect (F135). C3: the dev
secret never boots outside dev — the rule, then the boot (B7).

No unit changes a model prompt or a golden cassette; no unit touches a file STEP-13 is building.

### 8.5 · Decisions this check asks for

| | Question | Recommended | Default |
|---|---|---|---|
| s18-D1 | B9 — make the decider's daily cap durable, and at what number; a dollar governor, and at what default? | durable, read off `llm_costs`; the number set from a week of the post-STEP-02 rate; a dollar governor at the R-sites' $2/org/day | nothing changes (in-process, 400, no dollars) |
| s18-D2 | B10 — correct the vendor gate to `we_evaluate_them`? | yes, in the corpus review (`06` D45) — it opens a live Admin situation | the gate stays closed |
| s18-D3 | B26, F79 — the AI filter's prompt and batch: re-record which pages? | with STEP-03 §3.5's *attention, with context*, in one re-record | unchanged |

### 8.6 · Built — 2026-10-12, branch `yc2w27-s18` (20 units, 3 fixes)

Every unit: a test written first and seen red for the reason the row names, its verify green on a
database created fresh on pg2, a mutation run with every mutant killed (a survivor was killed by a
new test before its commit), its own commit, and the trace claimed, recorded and released.

| Unit | Commit | Bug | Mutations |
|---|---|---|---|
| M48.C1.L-contract.V0.U01 · `0210` every wrong reason kept | `61d679ed`, fix `360c8596` | B3 | 6/6, 6/6 |
| M48.C1.L-data.V0.U02 · a review object waits for review | `4b4aefbd`, fix `a059ab81` | B4 | 5/5 |
| M48.C2.L-logic.V0.U03 · a decimal answer is audited | `1c311b79` | B21 | 7/7 |
| M48.C2.L-data.V0.U04 · the rebuild reads every road | `e0c55aa8`, fix `82acda6f` | B12 | 6/6 |
| M48.C2.L-integration.V1.U05 · the script rebuilds the mail | `eddc2d2b` | B12 | 4/4 |
| M48.C2.L-contract.V0.U12 · `0211` a follow-up names its observation (added in build) | `8fa82a42` | B13 | 4/4 |
| M48.C2.L-data.V0.U06 · one active observation per follow-up | `14beeff1` | B13 | 5/5 |
| M48.C2.L-data.V0.U07 · the window read in a savepoint | `1ec3ab3a` | F120 | 2/2 |
| M48.C2.L-data.V1.U08 · the source list in a savepoint | `371a5b1e` | F120 | 2/2 |
| M48.C2.L-data.V0.U09 · `name_thread_nodes` closes its read, and a guard | `e617d15c` | F65 | 1/1 |
| M48.C2.L-data.V1.U10 · the sweep's situation read closes | `32b093af` | s18-F1 | 1/1 |
| M48.C3.L-data.V0.U11 · `gmail_l1` takes its fingerprints | `acd298bb` | B20 | 3/3 |
| M49.C1.L-logic.V0.U01 · a calendar event buys no relevance call | `490a6a51` | B25 | 4/4 |
| M49.C1.L-logic.V0.U02 · a bounce is read whole on the fast path | `3f95fb04` | F117 | 4/4 |
| M49.C2.L-logic.V0.U03 · their latency is not our behaviour | `5b991ecf` | B11 | 4/4 |
| M49.C2.L-logic.V0.U04 · a brief read in a transaction | `28b07068` | F97 | 2/2 |
| M49.C2.L-logic.V0.U05 · one list of public mail hosts | `75264c4b` | F128 | 2/2 |
| M49.C2.L-interface.V0.U06 · every switch names its effect | `668acf90` | F135, s18-F12 | 5/5 |
| M49.C3.L-contract.V0.U07 · the dev-secret rule | `f390fbeb` | B7 | 6/6 |
| M49.C3.L-integration.V1.U08 · the boot refuses first | `23af52f5` | B7 | 2/2 |

**Group guards** (root `tests/test_*.py`, `tests/platform`, and the folders each group touched, one
part at a time, each on a database created fresh on pg2): G1 feedback/api, G2 context/scripts, G3
coverage/context, G4 reason/scripts, G5 capture, G6 packs/context/feedback/scripts, G7 after B7. Every
red was either this branch's (fixed by the three `(fix)` commits) or s18-F13 (STEP-13's, before this
branch) or s18-F14 (load). Skips, every one pre-existing and environmental: `0080` (a declared
exception), `tests/test_health_memory.py` (internal auth not wired in the harness), and on capture
`tests/capture/transcripts/test_transcript_units.py` (no `docx` module).

**The statement pin** (`tests/platform/test_a_delete_is_not_a_read.py`) moved 3,079 → 3,080 (U02) →
3,078 (U04: the drain's SELECT was counted three times by the counter, now once as a constant — no
SQL removed) → 3,077 (U05) → 3,078 (U06) → 3,079 (U11): net 0, each move named in the pin's log.

**What reaches production and who acts**: two migrations (`0210`, `0211`, additive) with the deploy;
⛔ before the deploy, production's `GENIOS_JWT_SECRET` must be set (s18-F11 — Harsh); after it, the
read-only probe of s18-F9 (published behaviour entries of the counterparty's latency) and s18-F3's
`learning_objects` state count. Nothing here arms calibration or changes a model prompt.
