# 05 · L3 Context Graph (`context/`): one piece of work, one file, one truth (D14–D23)

**Written for:** coding agents (units) and Harsh (the re-file runs).
**Fixes:** D14–D23 of [02](02-THE-PATH-OF-ONE-MAIL.md).
**Atlas v2 target for L3** ([GeniOS-008 00-ARCHITECTURE](../GeniOS-008/00-ARCHITECTURE.md)): L3 holds the company's accepted state: evidence, entities, relationships, situations and their revisions. It serves L2 a bounded, versioned snapshot. L2 **proposes**; L3 **admits** (accepted / held / rejected / unresolved / failed). L3 never invents business meaning, and never saves an LLM guess as a fact.

**Where today's code differs from that target** (each difference is a finding to fix, never a reason to keep it):
- Nine writers create situations **before** any reasoning, by keyword rules (D17). Atlas v2: a situation exists after L2's judgment is admitted (S24).
- Admission runs, but sees only part of the file, and its HOLD silently keeps the old lane in charge (D18).
- Conflicts between equal-rank facts are overwritten, not kept (D22).
- A rebuild deletes accepted state, including human decisions (D23).

**Cards this file unlocks:** `i1` (one live situation instead of several), `i2` (an answer that does not answer), `i4`/`s2` (waves), `i5`/`c1` (bounces), `p1` (conflict), and stable cards that do not come back after a rebuild.

---

## How a file is made today (read this before any unit)

- `context/correlation.correlate_event` (`:616-653`) finds the anchors the event touched (`choose_anchors` `:228-259`). The anchor is the **strongest tier**: deal 10 < project 20 < subscription 30 < product_account 31 < company 40 < person 50. A person is lifted to their company, and a company to its deal when the domain has deals. Connectors, our own nodes and the tenant are excluded.
- Each anchor gets a **correlation** keyed `(anchor_node_id, domain, generation)` (`find_or_open` `:431-470`). The domain comes from ranked hints (source prior, then model, then keyword) and defaults to `general` (`resolve_domain` `:199-219`). A new generation opens when an event falls outside the correlation's span ± the window (`joins_window` `:262-276`): 45 days by default (`CORRELATION_WINDOW_DAYS`, `:73`), or `file_quiet_days` from an accepted in-motion brief line (90 for investor/program).
- The thread is not an anchor, only a continuity carrier: if the thread already holds correlations, the event joins them first (`thread_correlations` `:340-377`; fixed by **S14.U1** ✅ to read engine-owned correlations only).
- A **file** (`context/workstreams.py`) is `file_id = anchor_node_id`: every correlation with that anchor, across all domains and generations (`_files` `:437-527`).

So the file is the right unit (one counterparty). What is wrong is what happens *inside* it, and what never gets into it.

---

## Part A · What never reaches a file (D14, D15, D16)

### What happens

| Event | Where it stops | Why |
|---|---|---|
| noise (newsletter, spam, auto-reply) | `context/pipeline.py:2326` `correlations = [] if (is_noise or metadata_only) …`; noise defined `:965-976` | by design |
| archived mail (metadata only) | `context/memory_lanes.lane_for` → METADATA lane, "no correlation" | by design, but an archive that is later **promoted** is never correlated: `backfill.backfill_correlations` considers only `outcome='emitted'` |
| anchorless | `choose_anchors` returns `[]` when only our own nodes or connectors remain | a mail with only our people on it |
| private | correlated, but `workstreams._MEMBERS` (`:162-169`) drops `visibility_scope='private'` | privacy |
| failed extraction | `context/runner.py:179-183` `held_missing_qes_extraction`; `:419-443` `_record_failure` parks after `_MAX_ATTEMPTS`, retried daily | — |

The funnel (`platform/funnel.py:54-60`) has no "filed" stage, so none of this is visible.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S14.U4** | Claude | "Filed" is a number on the funnel | Add `events_filed` and `events_unfiled_by_reason` (noise, metadata_only, anchorless, private, held, parked) to `process_pending`'s output and to `daily_health` (`platform/daily_health.py`, one migration adding the columns) | `daily_health` shows filed vs unfiled for yesterday; a planted anchorless event counts as `anchorless` | ⬜ |
| **U12-10** | Claude | A promoted archive gets filed | When `promote_archived --apply` (or the S06.U1 re-judgment) turns an archive into an emitted event, enqueue it for `correlate_event` in the same transaction, instead of waiting for a backfill that ignores it | a synthetic archived intro, promoted, appears in its counterparty's file on the next sweep. Mutation: drop the enqueue → red | ⬜ |
| **D-12-2** | Rohit | Private events and the owner's own judgment | Today a private event is in no file, even for its owner. Recommended: keep private events out of shared cards, but let the **owner's** seat-scoped judgment read them (the visibility chain already carries the seat). | decision logged | 🔒 |

---

## Part B · One file, one live situation, and admission that sees it (D17, D18)

### What happens, and how

1. `situations.refresh_situations` (`situations.py:1086`) writes **one situation per correlation** (`on conflict (org_id, correlation_id)`). One counterparty therefore gets one situation per keyword domain (`venture_capital` → `investor_relationship`, `general` → `relationship`, …) × one per generation.
2. The **reading writers** add more on synthetic anchors (`outreach_situations.READINGS` `:1446`: `awaiting_response`, `reply_owed`, `commitment_overdue`, `cohort_outreach_gap`, `condition_in_review`, `condition_satisfied`, `organization_gone_quiet`, `campaign_awaiting_reply`, `meeting_follow_through`, …; anchored on an outreach node, a thread, a commitment node, `organization`, `cohort:{objective}`, `campaign:{id}`).
3. The nine writers, in `context/runner.process_pending` order (pinned shrink-only by `tests/test_rule3_situation_writers_only_shrink.py`, S04.U1 ✅):

   | # | Writer | Where | What it writes |
   |---|---|---|---|
   | 1 | `periodic.refresh_period_situations` | `runner.py:868-870` (def `periodic.py:170`) | `*_period_review` on the tenant node |
   | 2 | `support_situations.refresh_support_situations` | `:880-882` (def `:1538`) | seven support readings |
   | 3 | `meeting_touch.refresh_channel_touch_situations` | `:891-893` (def `:186`) | `channel_touch` |
   | 4 | `outreach_situations.refresh_state_situations` | `:904-906` and again `:1680` (def `:1782`) | the outreach `READINGS` |
   | 5 | `document_register.refresh_document_situations` | `:915-917` (def `:523`) | `document_under_control` |
   | 6 | `situations.refresh_situations` | `:1041-1042` (def `:1086`) | one per correlation, typed by `domain_spec.type_for` |
   | 7 | `situations.age_uncorrelated_situations` | `:1057-1058` (def `:1033`) | ages the rest |
   | 8 | `lifecycle.store.apply_lifecycle` via `detect_resolutions` | `:1087-1088` (def `lifecycle/store.py:319`) | resolutions |
   | 9 | `situation_bso.refresh_situation_importance` | `:1465-1466` and ~`:1706` (def `:1969`) | importance |

4. **Admission** (`context/l2_admission.py` `decide` `:68-113`) decides ADMIT / HOLD / REJECT per seed situation from the L2 `ReasoningResult`, and upserts `l2_admissions` and `situation_interpretations`. It never touches `context_situations`. Its situations come from `workstreams.lifecycle_for` (`:388-409`), whose `_SITUATIONS` (`:327-331`) selects **`where anchor_node_id = :f`**, limit 10. The readings sit on synthetic anchors, so admission cannot see them.
5. With more than one live situation and none named, admission returns **HOLD**, and `reason/l2/sweep.py:379-383` then refuses to make the judgment the file's review. The old lane stays in charge. (GeniOS-011 called admission "shadow only"; this crosscheck corrects that: its HOLD changes behaviour.)

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S15.U1** | Claude | Every reading names the file it concerns | Each reading situation carries `file_id` (the counterparty anchor of its subject), set by the writer; `_SITUATIONS` selects `where anchor_node_id = :f or file_id = :f` | on a synthetic investor file with an `awaiting_response` reading on its outreach node, `lifecycle_for(file)` returns it | ⬜ |
| **S15.U2** | Claude | One live situation per file; the judgment may name one | Keep correlations as they are (they are evidence groupings), but have `refresh_situations` keep **one live situation per file per kind of work**: the newest generation stays live, older ones close as `superseded_by_generation`; keyword domains become a *tag* on the one situation, not a second situation. In admission, a judgment may name `sit:<id>`; with one live situation and none named, admission targets it instead of holding. | the synthetic file with two domains and two generations has one live situation; L2 ADMITs on it; the multi-live HOLD count on the golden set drops to 0. Mutation: restore per-correlation writing → red | ⬜ |
| **S15.U3** | Claude | Re-anchor when the company appears; names through `resolve_alias` | a person file moves under its company when the company node appears, keeping situation ids | the person's history follows them | ⬜ |
| **S18.U4** | Claude | Bind a judged file's decision to the file itself | see [06 Part C](06-L2-PLANE-D-AND-R.md); removes the need for a pre-existing "home" situation | — | ⬜ |
| **S24.U1–U4** | Claude | Atlas v2: admission decides existence, one type at a time | for the first situation type, the writer stops creating it; L2 proposes it, admission ADMITs, and only then the situation exists. Each retired type is deleted from `SITUATION_WRITERS` in the S04.U1 guard. | first type live by admission only; the guard list shrinks by one | ⬜ |

---

## Part C · A wave is one subject (D19)

### What happens, and how

- `context/correlation_conversation.py` already **detects** waves: `find_campaigns` (`:308`) groups an identical sentence sent to ≥ 3 people (`MIN_RECIPIENTS`, `:90`) within 36 hours (`WINDOW_HOURS`, `:101`); `find_waves` (`:614`) groups the same subject.
- Through `_gather` (`outreach_situations.py:1765-1771`), a campaign can mint `campaign_awaiting_reply` on a `campaign:{id}` anchor. `find_waves`' only reader is `workstream_numbers.numbers_for` (`:173`), which prints waves inside each recipient's file.
- Each recipient keeps its own situations. Nothing judges "an update to 12 investors, 0 replies in 10 weeks" as **one** thing. The module docstring "NOTHING READS A WAVE YET" (`:64`) is stale.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S21.U1** (L3 half) | Claude | A wave is a file | A wave-anchored correlation (`wave:<wave_id_for>`, `:374`) whose members are the outbound mails and every reply; `workstreams._files` lists it as a file of kind `wave`; a reading `wave_gone_silent` (all recipients silent past the kind's usual gap, from Plane D) on it. The L2 half (judged once) is in [06](06-L2-PLANE-D-AND-R.md). | a synthetic update to 12 recipients with 0 replies after 70 days gives one wave file and one `wave_gone_silent` situation; a recipient's own file still holds its own thread | ⬜ |
| — | Claude | Fix the stale docstring | `correlation_conversation.py:64` | — | ⬜ |

---

## Part D · A reply that does not answer (D20)

### What happens, and how

- `context/vocabulary.py:263-274` `CLOSED_ANSWERED` / `CLOSED_REPLIED`, `discharged_asks` `:274`; `context/open_loops.py:66-77` `_closed_basis_clause`; `context/pipeline.py` ~`:1380-1388`.
- **Any** reply on the thread closes **every** open ask. The basis is `answered` only if the message's observed kind is in the `kinds.yaml` `discharges` table, else `replied`. The code's own example: "what is your ARR?" met by "let me check" is `replied`.
- The dossier shows "closed — only replied to" (`reason/expert/dossier.py` `_CLOSED_SAYS` `:335`, `_asks_closed` `:361-371`), but only for asks closed since the last review. Verify holds a move whose ask is `ANSWERED`. `_clear_file_decision` (`reason/domain_shadow.py:709-741`) resolves a card `verified` only on `answered`.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **U12-08** | Claude | An ask closed only by "replied" stays open for judgment | Keep an ask closed with basis `replied` in a new state `replied_unanswered`: off the "awaiting their reply" list, but **on** the file's dossier every review (not only since the last one) until the L2 judgment says answered or not. The L2 half (the judgment checks reply against ask) is in [06 Part E](06-L2-PLANE-D-AND-R.md). Files: `context/vocabulary.py`, `context/open_loops.py`, `reason/expert/dossier.py`. | a synthetic "what is your ARR?" → "will send soon" stays `replied_unanswered`; "ARR is $X" closes `answered` | ⬜ |

---

## Part E · The founder's own claims conflict (D22)

### What happens, and how

- `context/graph_store.py:40-71` `fact_write_action` decides write, supersede or discrepancy. A `discrepancies` row (table from `migrations/0004_l2_context_graph.sql:138-147`, written by `write_discrepancy` `:875`) is written only when the **new fact's rank is lower** than the held one. Two equal-rank email facts that disagree: the newer **silently supersedes**.
- There is no field for the tenant's own metrics: the extraction prompt sends unknown names to `other.*` ("never consulted"), and `deal.*` claims about us are rerouted (`context/pipeline.py` ~`:1756-1762`). Own-company numbers exist only as periodic aggregates on the tenant node and as canon uploads tagged `kpi`/`goal` (`capture/internal_knowledge.py`, rank 4).

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **N1b** (07's N1, graph half) | Claude | The founder's claims are facts, and disagreeing claims are a conflict | 1. Write each self-claim from N1a ([04 Part E](04-L1-SIGNALS.md)) as `company.<metric>` on the **tenant node** at rank 2, with its source mail and recipient list. 2. In `fact_write_action`, for `company.*` facts only: an equal-rank value that differs from a held one within 120 days → keep both and write a `discrepancies` row (never supersede). A third identical value adds evidence, not a row. 3. A reading `information_conflict` on the tenant node for an open discrepancy, naming who received which value. GeniOS never picks the true one; a billing source (when connected) is the only authority above rank 2. Files: `context/pipeline.py` (outbound leg), `context/graph_store.py`, `context/outreach_situations.py` or a new `context/self_claims_reading.py`, migration only if a column is needed, test `tests/context/test_own_claims_conflict_pg.py`, synthetic golden F73. | two sent mails "$10k ARR" and "$5K MRR" give one conflict situation with both values and their recipient counts; a received mail's number does not count; a third identical value adds no situation. Mutation: drop the equal-rank branch → red | ⬜ |

**Why only `company.*`:** changing equal-rank behaviour for every fact would turn every corrected email date into a conflict. The founder's own claims are the case where disagreement *is* the finding.

---

## Part F · A bounce becomes visible (D21)

### What happens, and how

- `context/delivery.py:70` `record_delivery_failure` (called from `context/pipeline.py:2034`) writes a `delivery_failure` observation on the failed address's node. When it finds the original (our last mail in the same thread to that address, `_original` `:126`), it also writes one on `thread:<parent_object_id>` and `delivery.status=failed` (rank 2) on the address. A thread older than the window gives no original.
- The only reader with behaviour is `context/waiting.py:199-230`: it **retires** the "waiting for reply" facts. So a bounce makes the awaiting-reply card **disappear**, and nothing replaces it. Nothing in `reason/`, `deliver/`, the packs or the Domain Expertise YAML references `delivery_failure`.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **N4** (from 07) | Claude | "Your mail never arrived" | Add a reading `delivery_failed` to `outreach_situations.READINGS`, anchored on the recipient's file (via S15.U1's `file_id`), one per recipient, carrying the original's subject and date; a `domain_spec` type for it in Admin; a playbook line in Plane D: "check the address, resend, or reach them another way"; re-sending stays an approval. Keep the waiting-fact retirement, but the bounce now *replaces* the waiting situation instead of erasing it. | a planted mailer-daemon notice on a thread gives one `delivery_failed` situation naming the recipient; a second bounce on the same thread updates it; the awaiting-reply situation is closed as `superseded_by_bounce`, not deleted | ⬜ |

---

## Part G · A rebuild keeps what was decided (D23)

### What happens, and how

- `context/backfill.backfill_correlations(rebuild=True)` (`backfill.py:131-135`) deletes `context_situations`, `context_correlation_members` and `context_correlations` for the org. It is triggered by `backfill_layer2` (`:428-447`) **whenever `deal_nodes_created` is non-zero**, including the automatic history replay (`api/routes.py:777-778`), and by `POST /api/org/{org}/situations/backfill?rebuild=` (`api/situation_routes.py:133-154`). `_release_stale_correlations` (`:390-424`) deletes situations of emptied correlations. `scripts/rebuild_graph.py:175-181` wipes the graph tables (including `discrepancies`) and `l2_processing_runs`.
- Correlation ids are stable (`stable_id`). **Situation ids are not**: `refresh_situations` uses `new_id("sit")` (`situations.py:1220`) = uuid4 (`platform/ids.py:6`). The reading writers use `held or new_id("sit")` (support `:1702`, periodic `:243`, meeting_touch `:272`, document `:657`). The `backfill.py:126-129` docstring says the id is "a content hash of (anchor node, domain, generation)": **false**.
- Human resolutions (`resolved_by='human'`) are deleted with the rows. So a card the founder closed comes back after any history replay that created a deal node.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S14.U2** | Claude | Deterministic situation ids; a rebuild keeps readings and human decisions | `situation_id = stable_id("sit", org_id, correlation_id)` in `refresh_situations`; for readings, `stable_id("sit", org_id, reading_type, anchor)`; before a rebuild deletes, copy human resolutions and admissions keyed by the stable id, and restore them after. Fix the docstring. | rebuild twice → identical situation ids; a human-closed situation stays closed. Mutation: back to `new_id` → red | ⬜ |
| **S14.U3** | Claude | `rebuild_graph` re-derives correlations; `files_for` reports dropped anchors | as in GeniOS-011 02-PLAN | — | ⬜ |
| **U12-11** | Claude | The automatic replay never rebuilds destructively | In `backfill_layer2`, a non-zero `deal_nodes_created` triggers an **incremental** re-correlation of the affected anchors, never `rebuild=True` for the org | a replay that creates one deal node changes only that deal's file | ⬜ |

---

## Part H · Memory holds what was said (feeds D25)

| Unit | Owner | What | Status |
|---|---|---|---|
| **S16.U1** | Claude | Every promise enters memory (`graph_facts` `commitment.*` on commitment nodes; the quote in `graph_source_refs.evidence->>'text'`). Today the dossier reads only facts created by the file's own events (`reason/expert/dossier.py::read_promises` `:692-704`). | ⬜ |
| **S16.U2** | Claude | A marker is not a quote: a stored mark never reaches a card as something the person said | ⬜ |
| **S16.U3** | Claude (built) | The snapshot has `as_of`, typed unknowns and open contradictions (`bd260f0a`, branch `g011-S16U3`) | ⏸ held: replays judge at past instants while `recorded_at` is wall-clock, so on the L2 path every snapshot lost its edges (10 of 10 had 1 node, 0 edges) |
| **U12-09** | Claude | The replay harness pins knowledge time | In `tests/replays/engine_runner.py`, stamp every graph write's `recorded_at` with the replay's sweep instant (or read the snapshot `as_of` the sweep instant on a clock the harness owns). Then merge S16.U3. Also give each golden run its own connection id (GeniOS-011 F2: overlapping runs stole each other's mailbox). | ⬜ |

---

## After this file: what should be true

1. Every event is filed, or counted with the reason it is not.
2. A counterparty's file has one live situation; admission sees every reading; a judgment is ADMITted instead of held.
3. An update to many people is one wave subject.
4. A reply that does not answer stays visible to the judgment.
5. The founder's conflicting claims are one conflict, not a silent overwrite.
6. A bounce replaces the waiting card with "never arrived".
7. A rebuild changes nothing a human decided.

**Expected after Step 4 (with Steps 1–3):** the `i5` card (bounces), and fewer duplicate or held cards. `i4`, `s2` (waves), `p1` (conflict), `i2` (unanswered ask) and `h1` (typed unknowns) exist as **situations** after Step 4; their cards need the L2 judgment (Step 5) and, for `p1`, the card writer (Step 7). Record what actually appears in [13-LOG](13-LOG.md).
