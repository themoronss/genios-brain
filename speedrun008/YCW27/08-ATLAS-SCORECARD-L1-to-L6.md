# 08 · ATLAS SCORECARD — L1 to L6 · 56 claims checked, claim by claim

**The source.** `Rohit_Updates/Secret War Updates/08-Cross-Layer-Synthesis/
01-Master-Atlas-vs-Code-Coverage-Matrix.md` — seven layer audits against
`harsh/mvp@b739bd5c`, dated **2026-08-22**. Six weeks old, so every cell is a **claim** until
re-measured. All 24 below were taken again against the current code and production, read-only.

**Vocabulary.** YCW27 L1/L2/L3 = Atlas **L1 Knowledge**, **L3 Domain Expertise + L4 Reasoning**
(the two planes, inside YCW27's L2), and **L2 Context**. `genios_engine/LAYERS.py` documents all
four vocabularies; the folders are the PRODUCT column.

---

## THE SCORE

    EXPIRED — the Atlas is wrong today       6
    STILL TRUE — the Atlas is right          11
    DISAGREEMENT — a design it mislabelled    1
    PARTLY EXPIRED                            2
                                            ──  L1+L2+L3, 24 claims

    L4                                       11  2 superseded, 2 imprecise
    L5                                       10  ⛔ 5 superseded, 1 OMISSION, 2 imprecise
    L6                                       11  ⛔ 4 EXPIRED, 4 PARTLY, 3 still true
                                            ──
    total                                    56

⛔ **L5 is the layer the Atlas is most out of date about, and in a specific direction: it calls
built things gaps.** Three of its five supersessions were created by THIS PROGRAMME, four days
before the document was read — and the one that matters most is not a wrong badge at all but an
**omission**: an entire six-module architecture the Atlas names nowhere. See **L5-08**.

---

# L1 · ENTERPRISE SIGNALS · `capture/`

| | Atlas claim, 2026-08-22 | Measured 2026-10-01 | Verdict |
|---|---|---|---|
| **L1-01** | *"only **eight** canonical source IDs are buildable… catalogued is not connected"* | `SOURCES` 36 catalogued · `BUILDABLE_SOURCES` **13 ids**, but `calendar/gcal/google_calendar` and `drive/gdrive/google_drive` and `database/mysql/postgres` are aliases → **~7 distinct providers** | **STILL TRUE** |
| **L1-06** | *"Full `QualifiedEnterpriseSignal` boundary — **Absent as Atlas contract**"* | `contracts/signal.QualifiedEnterpriseSignalBundle` exists and `capture/esqe/bundle.py` builds it (L1 STEP-06, needs `0186`) | ⛔ **EXPIRED** |
| **L1-07** | *"no mandatory typed business roles leave L1"* | no roles contract in `contracts/`. `signal.py` carries `subject_key`, a **derived string**, not typed roles | **STILL TRUE** |
| **L1-08** | *"`RawObject`, `SourceEvent` and `GatedEvent` do not require visibility"* | all three measured: **zero** declare a `visibility` field | **STILL TRUE** |
| **L1-09** | *"the coverage snapshot is not mandatory on each emitted signal"* | `GatedEvent.coverage_ready: bool \| None = None` — present, **optional** | **STILL TRUE** |
| **L1-10** | *"stable `new/active/satisfied/expired/superseded/revoked` signal identity is **absent**"* | `contracts/signal.SIGNAL_STATES = {active, superseded, expired, resolved}` — **exists**, 4 states not 6, `resolved` not `satisfied`, no `new`/`revoked` | **PARTLY EXPIRED** |
| **L1-12** | *"one authorized query cannot yet prove source span… end to end"* | `platform/funnel.py` — all five counters `signals_detected → situations_formed → capability_resolved → decision_emitted → card_delivered` (L2 STEP-04, needs `0188`) | ⛔ **EXPIRED** |

⛔ **L1-02/03/04/05/11 were graded *Present + Wired + Tested* by the Atlas itself** and nothing in
this programme touched them, so they are not re-litigated here. Their stated residual risks
(per-provider pagination, unstable `content_version`, exact HTML/PDF quote receipts, wrong-LLM
drop recovery) all remain open and all are honest.

---

# L2 · REASONING · the two planes — already re-measured in full

See `layer-2-reasoning/13-ATLAS-RECHECK` and `14-PLANE-D-AND-R`. In summary:

| | Atlas claim | Measured | Verdict |
|---|---|---|---|
| **Plane D** | *"**Stub.** Admin: 57 files, **all 57 stubs**, zero reviewed/accepted, zero routes"* and *"zero reviewed or accepted"* across the corpus | **155 capabilities, every one `stable`+`approved`, 0 hollow.** Admin 59 · Support 49 · Sales 47 | ⛔ **EXPIRED** |
| **Plane R** | *"**Seventeen** units registered; the manifest schedules roughly **six**"* | `CORE_UNITS` **17**, built-in schedules **7** | **STILL TRUE** (exact) |
| **Plane R** | *"**Registered is not active.**"* | **22 of 23** units ran in production; registry and production agree exactly; only `core.signal_composition` never ran | ⛔ **EXPIRED** |
| **Plane R** | *"the common legacy manifest… Every card needs an executed/skipped unit receipt"* | `reasoning_reasoner_results` carries one row per unit per run with `status` + `skip_reason_code` | ⛔ **EXPIRED** |

**Plane D's remaining gap:** 23 situations are `draft` — **18 unreviewed + 5 reviewed-but-unflipped**
(ALARM D-A2). **Plane R's remaining gap:** `cost_vs_benefit` has fired **0 times in 1,973 runs**,
and `axis_count` has **never been 3**.

---

# L3 · CONTEXT GRAPH · `context/`

| | Atlas claim, 2026-08-22 | Measured 2026-10-01 | Verdict |
|---|---|---|---|
| **L2-08** | *"Generic unregistered domain declares no expected fields and reports **100% coverage**… Empty requirements can look complete"* | **True, and deliberate.** `domain_spec.py`'s own header: *"OPEN BY DEFAULT… expected fields → none, so coverage is 100% ('we expect nothing, so nothing is missing'), never 0% ('we know nothing'). **That second one is the trap.** A registry that returns 'no expectations' as 'nothing known' would report every situation in a new domain as completely uncovered — absence read as negative evidence, which this codebase refuses everywhere else"* | ⛔ **DISAGREEMENT** — the Atlas graded a stated design decision as a gap |
| **L2-10** | *"Slice… **hardcodes** org visibility and `missing_fields=()` (`situation_bso.py:144-166`)"* | `situation_bso.py:2086` → `missing_fields=_missing_paths(situation, facts, neighbor_facts)`, and :2029 records the fix: *"This used to be a hardcoded empty tuple, and an empty `missing_fields` is not a neutral…"* | ⛔ **EXPIRED** (the `missing_fields` half) |
| **L2-06** | *"No explicit candidate/discard receipt exists"* | absence machinery exists — `context/quality/missing.py`, `context/quality/inference.py`, `situation_absences`. L3 STEP-03/04/05 added hold→need→clear | ⛔ **EXPIRED** |
| **L2-01** | *"`graph_store.py:29-223` protects against stale/replay overwrite… Incorrect authority configuration would still be applied consistently"* | ⛔⛔ **STILL TRUE, AND NOW LOCATED (2026-10-03).** The residual risk is real and this is where it lives: `graph_facts.authority_rank` carries **two scales** — the dense `0..6` ladder and `context/analytic/publish.DEFAULT_AUTHORITY_RANK = 100`, same table, same column. `fact_write_action` compares the raw integers, so a row at 100 is unsupersedable and a `signed_document` arriving against one comes back a `discrepancy` and is **dropped**. Three more ranks do not say how they were decided: the unmapped floor is `inferred`'s own 0, `write_fact`/`build_evidence_ref` default to a bare 1 = `chat_aside`, `write_edge` to a bare 2 = `email_prose`. ⛔ Measured as NOT firing today. **Receipt 46** + `UNINTERPRETABLE_RANKS` | **STILL TRUE** · located |
| **L2-02** | *"Distinct source labels are not necessarily independent causal authorities, so copied claims may inflate strength"* | unchanged | **STILL TRUE** |
| **L2-03** | *"First claimant owns a same-name alias (`identity.py:134-145`), so later name-only prose can attach to the wrong human"* | ⛔⛔ **CORRECTED 2026-10-03 — this row was wrong.** Closed in code, and the chain holds in both directions: `observe_person_name` sets `origin='contended'` when a SECOND LIVE person claims the key; `resolve_alias` excludes contended **and** returns `None` on 2+ rows; `resolve_alias_candidates` exists so "nobody" and "several" are not conflated; `tests/context/test_a_person_the_graph_knows_by_name.py` guards it. The docstring states the law — *"a name shared by several anchored people resolves to NOBODY, not to the first claimant"* — and the implementation earns it | ✅ **EXPIRED** |
| **L2-04** | *"explicit complete authority/ownership/resource/use-restriction views… are absent"* | ⛔ **PARTLY EXPIRED (2026-10-03).** `authority` IS built — `context/authority_view.py`, imported in production by `context/patterns/store.py`. The other three have no read surface, and `ownership`'s **data** is written (`commitment.owner`) while its surface is not — `context/pipeline.py` calls that gap *"the distinction an ownership surface is built out of"*. `use_restriction` appears in **0 files** engine-wide other than its own declaration. ⛔ My first re-measurement of this row was wrong twice, both times from grepping filenames. Declared in `ATLAS_L2_04_VIEWS` | ⚠️ **PARTLY EXPIRED** |
| **L2-05** | *"Same-company independent deals can collapse without a deal object"* | unchanged — and it is the **same root** as `deal.status` having 3 rows of 293 | **STILL TRUE** |
| **L2-07** | *"role/source-readiness completeness is not part of the blocking vector"* | unchanged. ⛔ This is the **ConfidenceVector axes decision** (`02-DECISIONS` #1), still open and Rohit's | **STILL TRUE** |
| **L2-09** | *"Producer… emits one anchor, empty relationships/dependencies and **constant importance** (`situation_bso.py:69-141`)"* | importance is no longer constant — `context/importance.compose_situation_importance` is imported and used, with `importance_source` recorded in metadata and a **named fallback** for a situation whose events published no live score. ⛔ **MEASURED 2026-10-03, and it splits two ways.** `context/situation_bso.py` is 2,133 lines and mentions `relationships` **0 times** and `dependencies` **0 times** (against `evidence` 66, `anchor` 55, `entities` 7) — so that half is TRUE, and it is **declared twice**, by `contracts/situation.py`'s GAP FLAG and by `contracts/dependency.py`, both naming the X8 cutover. ✅ But the *"0 derived facts"* half is CLOSED: `context/conversion.py` is the census built for exactly that number, and it has a **writer** (both correlators call `record_conversion`), a **reader** (`runner.py:1400` `read_conversion`) and a test. ⛔ This is the one I expected to find unread | **PARTLY EXPIRED** · the rest DECLARED |
| **L2-11** | *"Wrong first domain or restricted mixed-domain evidence can still enter the wrong view"* | ⛔⛔ **STILL TRUE, AND WORSE THAN GRADED (2026-10-03).** `reason/adapters/expertise.py:1463` takes `domain_ids[0]`, and the list arrives `tuple(sorted(selected_domains))` out of a `set` — so the index selects the **alphabetically first** domain. That value becomes `CapabilityManifest.domain`, and `reason/domain_shadow.py:1169` uses it to select which **tenant pack** the reasoning reads. ⛔ Nothing records that a choice was made, while the package's own citation tags carry every domain. ✅ The contract already owns the accessor that does not do this (`domain_hints`). **Receipt 45** | ⛔ **STILL TRUE** · located |
| **L2-12** | *"A tenant replay is missing"* | unchanged | **STILL TRUE** |

⛔ **The file the Atlas cited at `:144-166` is now 2,133 lines.** Every line reference in a six-week-old
audit of this codebase should be treated as a name, not an address.

---

# WHAT THIS MEANS, IN ONE PARAGRAPH

**The Atlas was right about the hard things and wrong about the built things.** Everything it graded
as *absent* in L1 and L2 that this programme then built — the signal bundle, the evidence-need door,
the five counters, the lanes, `missing_fields`, the absence machinery, the corpus — has expired. What
**remains true** is the list it could not have been wrong about, because none of it is code we were
missing: **typed business roles, visibility carried through the capture seams, a mandatory coverage
snapshot, independent-corroboration semantics, a tenant replay, and the confidence-vector axes.**
Those are design decisions and connectors, not gaps.

⛔ **TWO ITEMS WERE STRUCK FROM THAT SENTENCE ON 2026-10-03, and the correction is the point.**
*Same-name identity* was in it, and `identity.py` closes it in both directions — the writer marks a
contended key, the reader excludes it, and a third function exists so "nobody" and "several" are
not conflated. *The complete graph views* was in it, and one of the four is built and imported in
production. ⛔ **Both were graded by re-reading the Atlas rather than the code**, which is the one
mistake this scorecard exists to prevent, and it survived here for two days. The L2 rows above now
carry the measurement that settles each one.

**One cell is a disagreement rather than a finding** — L2-08, where the Atlas graded *open by
default* as *empty requirements look complete*. The code states the reasoning, and the reasoning is
this codebase's own rule: absence is never read as negative evidence. **That one should be corrected
in the Atlas, not in the code.**

---
---

# ⛔ 2026-10-01 · L4 ADDED TO THE SCORECARD — 11 claims, 1 superseded

The Atlas's L4 section is the most accurate in the document. Full trace:
`layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md` PART 3.

| | Atlas claim | Verdict |
|---|---|---|
| **L4-01** | `executive/` 26 files, 5,990 lines | ⚠️ **27 / 6,167** — the Atlas is dated 29 Sep; `readiness.py` landed after. A date, not an error |
| **L4-02** | *"Units 6 and 8 have no file and three files carry no number"* | ✅ **EXACT.** Numbered: 1, 2, 2.5, 3, 4, 5, 7, 9, 10. Unnumbered "Unit": `assignment`, `escalation`, `execution_guard` |
| **L4-03** | *"the spec that numbered them is not in the repo — an open question, not a gap"* | ✅ and ⛔ **the code says it better**: `unreached.UNIT_NUMBERING_UNRESOLVED` already records it as *"A declared UNKNOWN, not a finding ... An absent number is not an absent unit"* |
| **L4-04** | execution.v1 runs on every heartbeat tick, before distribution | ✅ — at `api/routes.py:1195`, not the `:1150` `unreached.py` cites (**F11**) |
| **L4-05** | ladder day 1 notify · 3 remind · 7 escalate · 14 critical · max_rungs 6 | ✅ built · **466 escalation rows** · ⛔ **but 124 day-7 rungs never fired** (F7) |
| **L4-06** | five tables, migration 0041, delegation wiring 0157 | ✅ 186 executions · 794 actions · 466 escalations · 1,021 events · 186 outcomes |
| **L4-07** | *"the queue is empty: no domain activated; organisation data missing"* | ⛔ **SUPERSEDED.** L4 produced 186 executions and 165 cards, so it was never blocked on activation. **Two real blocks**: the LLM switch (F6) and the reporting line (F7) |
| **L4-08** | `seat_responsibilities.reports_to`, never `org_seats.manager_seat_id` | ⚠️ ⛔ **there is no such column.** `reports_to` is a **value of `accountability`**, and it appears in no migration. The code is right; the prose is not (**F8**) |
| **L4-09** | DecisionObject is `target`; brief.v1 exists | ✅ and `unreached.PULL_ONLY` says why: *nothing in `sweep.py` composes a brief* |
| **L4-10** | two open product decisions: preventive → card? brief pushed? | ✅ **both already declared** in `unreached.PULL_ONLY`, each with its cost spelled out |
| **L4-11** | L4 owns who/where (`assignment.py`, `communication.py`) | ✅ `deliver/router.py:9-12` records the move; all four `deliver/` modules import it |

    L1 + L2 + L3    24 claims checked
    L4              11 claims checked
    ────────────────────────────────
    total           35 claims · 2 superseded · 2 imprecise · the rest verified exact

⛔ **The Atlas's L4 section is more accurate than its L1 section**, and the one place the code
beats it (L4-03) is `unreached.py`, which declared the unit-numbering unknown before the Atlas
described it.


---
---

# ⛔ 2026-10-01 · L5 ADDED TO THE SCORECARD — 10 claims, **5 superseded and 1 omission**

The Atlas's L5 section is the **least** accurate in the document, and the reason is structural
rather than careless: L5 is where this programme did most of its building, so the cells describing
it went stale fastest. Full traces:
[`layer-5-delivery/05-RECROSSCHECK-the-silences-of-the-delivery-spine.md`](layer-5-delivery/05-RECROSSCHECK-the-silences-of-the-delivery-spine.md),
[`06-AUDIT`](layer-5-delivery/06-AUDIT-the-measurement-that-corrected-itself.md),
[`07-AUDIT`](layer-5-delivery/07-AUDIT-the-second-delivery-architecture.md).

| | Atlas claim | Verdict |
|---|---|---|
| **L5-01** | `deliver/` 36 files, 8,674 lines | ⚠️ **40 files / 9,431 lines** — and the **36 matches the top-level count exactly**, so the Atlas counted top-level only and never descended into `channels/` (4 files, 434 lines). 323 lines landed in those 36 since. **A counting convention plus four days, not an error** |
| **L5-02** | claim-level validation is a `target` | ⛔ **SUPERSEDED — BUILT.** `deliver/claim_validator.py` + `claims.py`, M13 `STEP-03`/`STEP-04`, shared 34 tests. Bound to the existing `contracts/claim_state.ClaimState` rather than inventing a second taxonomy |
| **L5-03** | *"no lanes on the card"* — called **L5's biggest gap** | ⛔ **SUPERSEDED — BUILT.** `lane_display.py` + `lane_recall.py`, M13 `STEP-01`/`STEP-02`, 55 tests, `migrations/0190_card_lane.sql`. ⛔ **And this programme CREATED that gap one step earlier** — `0189` added `signals.output_lane` and nothing read it |
| **L5-04** | three delivery failures *"to design out"*: duplicates across paths, card flattening, stale fire | ⛔ **SUPERSEDED — ALL THREE ALREADY GUARDED.** Duplicates: `logical_dedupe_key` + a unique index + `on conflict` + the two paths made **mechanically disjoint** (`dedupe_key is null` vs `is not null`) + fence tokens. Flattening: `card_source.COMPARISON_KEYS` counts BOTH card paths every sweep before either retires, plus `slots.py`'s sentinel guard carrying the fault that taught it (*"Raised severald ago"*, shipped to a reader). Stale fire: four grains in `store.py` — one staleness test shared by claim and upsert, a lease only its owner can release, terminal cards that cannot be resurrected, and `window.lapsed` expiry feeding L6 |
| **L5-05** | *"the scalar publication floor is replaced by lane routing"* | ⛔ **SUPERSEDED — there is no scalar floor in `deliver/`.** `gate.py` is moment + permission; `bands.py` cuts an urgency band from **pack config**; the score gate is `reason/runner.py:1133` (`out["below_gate"] += 1`) and `executive/explain.py` **already reads** its receipt. Replacing it here would have meant building it first in order to remove it |
| **L5-06** | the invention validator is missing | ⛔ **SUPERSEDED — it exists.** `render.py:334` `invention_ok`, called at `:861`, re-exported by `executive/validate.py:69`, tested. ⛔ I nearly recorded it as absent: *a conclusion drawn from one name's absence* |
| **L5-07** | eight delivery surfaces; *"Budget and surfaces"* is a `target` | ⚠️ **STAYS `target`, and the reason must be written in: it is a DEPLOYMENT and PRODUCT fact, not a code gap.** `units.py` has **11 units over 11 channels**; **2 of 6** push channels have an adapter (`slack`, `agent_push`); **3 of 11** units have no reachable channel; **1** (`email`) honestly declares `engine_ready=False`. And `capability_report` is **fail-closed** — it names `no_adapter` as **OUR** gap rather than the tenant's, and deliberately excludes `in_app`/`dashboard` from needing one because demanding it *"would report the one delivery path that actually works today as broken"* |
| **L5-08** | — | ⛔⛔ **THE OMISSION, AND IT IS THE LARGEST L5 FINDING.** `deliver/` contains a five-phase pipeline the Atlas names **nowhere**: `presence.py` (Ph2, Delivery Context Resolver) · `orchestrator.py` (Ph2, seven responsibilities → one materialised `DeliveryObject`) · `spine.py` (Ph3, the durable outbox spine) · `tracker.py` (Ph4, the Delivery Tracker) · `units.py` (Ph5, the eleven delivery units and their capability registry) · `analytics.py` (Ph5). **A `gap` badge on built work costs a wasted unit; an omission costs a REBUILD** — the next person planning L5 from the Atlas plans to build `presence.py`. L2 paid **six units** for one absent fact |
| **L5-09** | — | ⛔ **AND THAT ARCHITECTURE IS CONNECTED AT ONE TIER OF FOUR.** Measured: tier 1 **resolution** is shadow-measured in production (`outbox.shadow_resolve_v2`, counters at `outbox.py:1441`); tier 2 **persistence**, tier 3 **claiming** and tier 4 **policy** have **no production evidence**, and `rate_limiter`/`retry` are not even imported. So a cutover decision would rest on evidence about **routing** while the three tiers that touch the network have none. The two paths ARE mechanically disjoint, so none of it is a live defect — *an uncalled function on an un-cut-over path is not a bug; it is an unguarded cutover* |
| **L5-10** | — | ⛔ **AND THE QUESTION IS NOT L5's ALONE.** Running the corrected reachability resolver over **every** package: **147 top-level public functions are unreached by production and declared nowhere** — 18 hidden by a name collision, **129 visible to both resolvers all along**. Only `executive/` and `deliver/` have a reachability guard. See [`18-AUDIT-the-engine-wide-reachability-gap.md`](18-AUDIT-the-engine-wide-reachability-gap.md). ⛔ **147 is NOT 147 defects**: L5's own 24 were 12 un-cut-over, 7 deliberate, **5** defects |

    L1 + L2 + L3    24 claims checked
    L4              11 claims checked
    L5              10 claims checked
    ──────────────────────────────────
    total           45 claims · 7 superseded · 1 OMISSION · 4 imprecise · the rest verified exact

---

## ⛔ What L5's row changes about how to read this document

**The pattern, now six layers running:** the Atlas describes the engine as it was **designed**, and
the code has moved past it in exactly the places the design was most specific.

| Layer | The document said | The code said |
|---|---|---|
| L1 | `no_model_wired` is broken wiring | one lane is model-free **on purpose** |
| L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| L2 | plan compile should fail on an unproduced source | it did, and it cost **six units to one absent fact** |
| L4 | never read `manager_seat_id` | it is the **standing line** the dated override sits on |
| **L5** | *"no lanes on the card"* is the biggest gap · replace the scalar floor · three failures to design out | **all built or already guarded — three of them by this programme, four days earlier** |

⛔ **And the direction is consistent: the Atlas understates what exists.** Correcting a badge is
cheap. Building from a stale badge is what cost L2 six units — and an **omission** (L5-08) is worse
than a wrong badge, because nothing in the document tells you to look.

> ⛔ **A document that has fallen behind the code is not wrong, it is superseded — and it is still
> dangerous.** The repair is to date it, not to argue with it.

## What the Atlas is RIGHT about in L5, and it is the harder half

| | |
|---|---|
| the bridge direction | Executive never imports Delivery; it writes `execution_events` and L5 reads it |
| the outbox | every outbound notification is a **row**, never a blocking call |
| the why-not vocabulary | `below_gate · budget · cooldown · muted · shadow · situation` — written **and read** |
| L5 owning the moment, L4 owning who/where | `deliver/router.py:9-12` records the move and all four modules import it |
| surfaces being a real gap | ⚠️ L5-07 — the `target` badge stands; only the **reason** needed writing down |


---
---

# ⛔ 2026-10-02 · L6 ADDED TO THE SCORECARD — 11 claims, **4 expired, 4 partly, 3 still true**

## ⛔ The vocabulary, stated before the table, because this is where it bites

The source matrix labels these rows **`L7 Learning`** — the `genios_engine/LAYERS.py` numbering,
where `feedback` is 7. ⛔ **This scorecard numbers `deliver/` as L5**, so the learning layer is
**L6** here. Both are correct in their own column and `LAYERS.py` warns about exactly this: *"always
name the package, never the digit alone."*

⛔ **The programme has now paid for that collision twice** — once in `STEP-10`'s receipt count (see
[`layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`](layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md))
and once in my own plan, which called this step *"`L1-to-L7`"*. **Every cell below is
`feedback/`.**

| | Atlas claim (matrix row `L7 Learning`) | Atlas badge | ⛔ Measured 2026-10-02 |
|---|---|---|---|
| **L6-01** | *"Tenant/time-bounded feedback selector… A green run can learn nothing without an input-health/readiness gate"* | Present · live input health Unknown | ⚠️ **PARTLY EXPIRED.** The gate exists — `degraded_seams` + `degraded` — ⛔ **and it was BROKEN**: `getattr(batch, "deliveries", ())` names a field that does not exist, so the delivery seam was reported degraded on **every run** and `degraded` was always True. Fixed in `S7`, seam names derived from the dataclass, plus `quarantined_seams` so a LOST seam is no longer reported as an empty one |
| **L6-02** | *"Explicit feedback learning — `feedback/units.py:59-63` returns `[]`"* | **Stub** | ✅ **EXPIRED.** `unit_feedback_learning` is built (M14): it reads `card_feedback_verdicts`, groups by rule, and targets `METRICS`. Its own docstring records why returning `[]` was the worse bug: *"the FIRST verdict a human ever gives would have been read, loaded into the batch, and discarded here"* |
| **L6-03** | *"Preference learning — direct unit returns `[]`; explicit bounded preference cannot become policy-aware versioned state"* | **Stub** | ⛔ **STILL TRUE — and narrowed by `S5`.** *"Empty until the inbox lands"* was stale: `learning_event_inbox` (0046) **exists, is written in production** by `reason/moments/store.record_feedback`, and is loaded into **every** weekly batch. ⛔ **The gap is a `kind`, not a table** — every row is `payload.kind == "moment_feedback"`. A table is a migration; a `kind` is a **surface**, and there is none |
| **L6-04** | *"Temporary memory/directive — `pause outreach this week` has no canonical TTL/consumption path and may be lost or stored permanently elsewhere"* | **Stub** | ⚠️ **PARTLY EXPIRED, and the stronger half is wrong.** The unit is still `[]`, ⛔ **but the TTL/consumption path is LIVE**: `packs/brains/adaptive_lease` emits `RUNTIME`, `govern()` routes it to `TEMPORARY`, `publish_runtime` writes `temporary_memories` with `expires_at NOT NULL`, bounded at 7 days by the tenant's own ceiling and retired by `expire_leases`. *"May be stored permanently"* is **not** possible on that path. Only the explicit-directive INPUT is missing |
| **L6-05** | *"Outcome/pattern/recommendation learning… exposure/action/delivery/outcome identity is fragmented, so correlation can masquerade as efficacy"* | Present · live cohort quality Unknown | ⚠️ **PARTLY EXPIRED.** The reconciliation exists: `counterfactual_ledger` (migration 0072) joins signal → card → `card_events` → verdict → `delivery_outbox` → `executions` → `execution_outcomes` → `llm_costs`, **one row per recommendation**, and carries a production receipt asserting the join reaches end to end. ⛔ The *attribution* caution stands — the view separates the stages but does not claim causality |

⛔⛔ **`S10` ADDENDUM 2026-10-02.** Two of the Atlas's three acceptance clauses for this row are closed by things that were already there: `migrations/0041:248`'s `unique (org_id, execution_id)` — named `execution_outcomes_once` and commented *"a second row would double-count it in every precision calculation Layer 7 runs"* — makes *"the same external event counted once"* a **database guarantee**, and `label_class` keeps `unknown` out of the confidence denominator. ⛔ The third, *"correction retracts derived proposal"*, is **blocked behind `L6-01`**: every unit that reads `card_feedback_verdicts` targets `METRICS`, so no durable proposal is derived from a correction and there is nothing to retract. → [`layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md`](layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md)
| **L6-06** | *"Behavior Brain evolution — cohort builder returns `[]`; repeated role-specific corrections cannot govern future packages"* | **Stub** | ⛔ **EXPIRED — and this is the Atlas's sharpest miss.** `packs/brains/behavior_distill.distill` is **776 lines**, reads L2.4's published trend facts, gates them against the tenant's own policy floors and proposes — and `feedback/brain_pipeline.brain_pipeline_proposals` appends its output to the **same weekly run**, inside a savepoint. ⛔ The stub (`365cf7a6`, 2026-08-08) **predates the implementation** (`ed1b10c3`, 2026-09-07) by a month. *A call site that looks DEAD is not a dead feature* |
| **L6-07** | *"Adaptive Brain evolution — recommendation unit can emit Adaptive without expiry and the publisher may publish durable Adaptive… does not currently fail closed"* | **Contradictory/partial** | ⛔ **STILL TRUE, verified end to end in `S1`.** `unit_recommendation_learning` → `ADAPTIVE` → `preflight` *"org-derived — ALLOWED"* (⛔ **three** expiry checks for RUNTIME, **none** for ADAPTIVE) → `govern` **`auto_promote`**, no human → `publish_brain` → `learned_brain_entries`, no expiry column. And `packs/compiler/runtime_brains.py` reads that brain **into the compiled package the recommender reasons from** — the Atlas's own *"no self-training from recommendation score"*. ⛔ **The repair is Rohit's**: all three options change what the brain contains |

⛔⛔ **`S10` ADDENDUM 2026-10-02 — STILL TRUE ABOUT THE SHAPE, AND THE PATH IS NOT OPEN.** `S1` verified the chain `unit_recommendation_learning` → `ADAPTIVE` → `preflight` allows → `govern` auto-promotes, and every link of that is real. ⛔ **What `S1` did not ask is whether a proposal ever reaches `preflight`.** It does not: the unit pins `evidence.distinct_days = 1`, `LearningPolicy.min_distinct_days` defaults to **2**, and `orchestrator.run_learning` runs `validate_learning` **first** and `continue`s — so every proposal is recorded `held / insufficient_distinct_days` and governance never sees it.

⛔⛔ **THE CELL IS THEREFORE STILL TRUE AND THE RISK IS LATENT — WHICH MAKES THE OBVIOUS REPAIR THE DANGEROUS ONE.** Measuring `distinct_days` properly is correct for the five sibling units (all `METRICS`/`KNOWLEDGE_SUGGESTION`, which bypass the gate), is what `unit_pattern_learning` already does, and the data is in hand — so a future engineer would make it and **silently open an auto-promoted durable Adaptive write that trains the recommender on its own score**. `feedback/target_policy.BLOCKED_BY_ARITHMETIC` declares it and a tripwire test fails on each of the three things that would open it, including a stored policy with `min_distinct_days = 1` (no clamp in the loader, **no CHECK** in `0045`). ⛔ *A cell the Atlas marks a risk is not a cell whose risk is reachable* — and the difference decides whether the fix is a bug fix or ADR-10. → [`layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md`](layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md)
| **L6-08** | *"Expert knowledge review proposals… review SLA and corpus release receipt are unproved"* | Present | ✅ **STILL TRUE.** `unit_knowledge_evolution` targets `KNOWLEDGE_SUGGESTION` and `govern()` sends it to `HUMAN_REVIEW` **unconditionally** — the comment says this *"cannot be removed from policy"*. The review SLA and the corpus release receipt remain unproved, exactly as the Atlas says |
| **L6-09** | *"Validation, publisher, versioning and rollback — Organization review approval changes state without publishing a brain row; policy loading drops `blocked_targets` and `blocked_subject_prefixes`"* | Present primitives; **broken seams** | ⛔ **EXPIRED on BOTH named defects — and a third was found in the same area.** Approval **does** publish: `_publish_approved` runs in the same transaction, with the comment *"a reviewer who approves has every reason to believe the system now knows something — and it did not."* `S3` closed the policy load (the absence is representable, refused at two gates, and the skip does not burn the week). ⛔⛔ **But `S6` found `publisher.publish` writing `governed → published`, an edge `ALLOWED_LEARNING_TRANSITIONS` forbids, on every brain publish** — unvalidated, into the one ledger nothing read |
| **L6-10** | *"Organization pivot/reset — reset is auditable but does not fully supersede Organization Brain or Behavior entries, cannot rely on an Adaptive expiry contract that does not exist"* | Present/partial · Organization config boundary **Absent** | ⚠️ **PARTLY EXPIRED, and the fix is more complete than the Atlas knows.** `feedback/reset.py` already renamed its count to **`runtime_memories_expired`** and returns **`adaptive_ttl_unresolved: True`** — ⛔ **the exact disposition the Atlas's own fail-closed table requires** — naming ADR-10 as unratified rather than implying an answer. ⛔ **STILL TRUE:** durable Organization/Behavior/Adaptive entries are not superseded, and `L7-40`'s `durable_brain_reset_incomplete` is not emitted by the rerun route. ⛔ **AND A NEW DEFECT:** `reset.py`'s stated reason for not touching Behavior — *"`unit_behavior_evolution` is presently an unwired stub that always returns `[]` — there is no live Behavior Brain content to decay"* — **was true when written and is false now** (`L6-06`). *A stale comment reads as a measurement*, and this one is the justification for a gap |

⛔⛔ **`S10` ADDENDUM 2026-10-02 — THE RESET PROPAGATES, AND THE ATLAS DOES NOT CREDIT IT.** `deliver/outbox.py:1050-1068` reads the latest reset at SEND time, compares it with the card's `created_at`, and cancels with *"org corrected its identity after this card was built"* — on the **same connection under the same locks** as the authority re-proof, and **fail-closed-to-send** on an unreadable table. ⛔ Two of `apply_organization_reset`'s three callers are seat lifecycle rather than pivots, and **both justify it in writing**, so that candidate retired before it was recorded. ⛔⛔ The real finding was **mine**: `feedback_health`'s declaration called `latest_reset_at` *"a surface that was never built"* — the reader exists one layer DOWN and **may not import upward**, so the duplication is **forced by the topology**. ⛔ The Atlas's *"fails promotion"* clause stays unimplemented and is now guarded. → [`layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md`](layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md)
| **L6-11** | *"Customer value analytics — `api/intelligence_routes.py:531-545` hardcodes zero outcomes/value despite structured outcome paths"* | **Stub/misleading surface** | ⛔ **EXPIRED — and `S2` found what was actually wrong.** `outcomes_recorded` is a real `count(*)` over `execution_outcomes`, and `actions_taken` carries its own fix (the predicate matched `kind` while every writer puts the verb in `cause`). ⛔ `value_recovered_inr` is still `null` and **that is correct** — but the REASON was false: it blamed *"the counterfactual ledger, which does not exist"* (`0072` creates it). ⛔⛔ **The real reason: `macv_ledger` — *"the North Star … the number the customer can verify"* — has never had a writer.** Five occurrences repo-wide and **the only code that touches it deletes it** |

## ⛔ What L6's row changes about how to read this document

```
EXPIRED           4    L6-02 · L6-06 · L6-09 · L6-11
PARTLY EXPIRED    4    L6-01 · L6-04 · L6-05 · L6-10
STILL TRUE        3    L6-03 · L6-07 · L6-08
                 ──
                 11
```

⛔⛔ **Four of eleven cells were out of date in the direction the Atlas is consistently wrong in:
it calls built things stubs.** `L6-06` is the clearest — a 776-line component wired into the weekly
run, recorded as *"cohort builder returns `[]`"* because the stub that preceded it by a month was
never removed.

⛔⛔ **And THREE of the eleven cells hid a defect the Atlas did not name**, each found by measuring
the cell rather than reading it:

| Cell | The Atlas's badge | ⛔ What measuring it found |
|---|---|---|
| `L6-01` | *"live input health Unknown"* | the health gate was **broken** — `degraded` was always True |
| `L6-09` | *"broken seams"*, both named ones now fixed | ⛔ `governed → published`, an illegal lifecycle edge on **every brain publish** |
| `L6-10` | *"does not fully supersede Behavior"* | ⛔ the module's **stated reason** for that is now false |
| `L6-11` | *"hardcodes zero"* — fixed | ⛔ the product's headline ledger **has no writer at all** |

> ⛔ **A cell the Atlas marks *Present* is not a cell that needs no measurement.** Three of the four
> new defects sit under badges that read as reassuring, and the fourth sits under a badge that was
> already corrected.

## What the Atlas is RIGHT about in L6, and it is the part that matters

⛔ **`L6-07`.** The Adaptive lifecycle is *"contradictory/partial"* and *"does not currently fail
closed"*, and six weeks later every word of that is still true — verified line by line in `S1`. The
Atlas also names the required disposition, `adaptive_ttl_unresolved`, and ⛔ **`feedback/reset.py`
already emits exactly that string** — so the codebase agrees with the Atlas about the shape of the
unanswered question and is waiting on the answer.

⛔ **`L6-03` and `L6-08`.** The preference inbox and the review SLA are genuinely absent, and the
Atlas's own improvements table makes the inboxes **P1**. `S5` narrowed the first from *"no inbox"*
to *"no `kind`"* — which moves it from engineering to a **surface decision**, and that is Rohit's.
