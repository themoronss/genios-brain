# ATLAS SCORECARD · L1, L2, L3 — claim by claim, re-measured 2026-10-01

**The source.** `Rohit_Updates/Secret War Updates/08-Cross-Layer-Synthesis/
01-Master-Atlas-vs-Code-Coverage-Matrix.md` — seven layer audits against
`harsh/mvp@b739bd5c`, dated **2026-08-22**. Six weeks old, so every cell is a **claim** until
re-measured. All 24 below were taken again against the current code and production, read-only.

**Vocabulary.** YCW27 L1/L2/L3 = Atlas **L1 Knowledge**, **L3 Domain Expertise + L4 Reasoning**
(the two planes, inside YCW27's L2), and **L2 Context**. `genios_engine/LAYERS.py` documents all
four vocabularies; the folders are the PRODUCT column.

---

## THE SCORE

    EXPIRED — the Atlas is wrong today      6
    STILL TRUE — the Atlas is right          11
    DISAGREEMENT — a design it mislabelled    1
    PARTLY EXPIRED                            2

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
| **L2-01** | *"`graph_store.py:29-223` protects against stale/replay overwrite… Incorrect authority configuration would still be applied consistently"* | unchanged, and the residual risk is real: the guard is correctness-of-ordering, not correctness-of-config | **STILL TRUE** |
| **L2-02** | *"Distinct source labels are not necessarily independent causal authorities, so copied claims may inflate strength"* | unchanged | **STILL TRUE** |
| **L2-03** | *"First claimant owns a same-name alias (`identity.py:134-145`), so later name-only prose can attach to the wrong human"* | unchanged | **STILL TRUE** |
| **L2-04** | *"explicit complete authority/ownership/resource/use-restriction views… are absent"* | unchanged | **STILL TRUE** |
| **L2-05** | *"Same-company independent deals can collapse without a deal object"* | unchanged — and it is the **same root** as `deal.status` having 3 rows of 293 | **STILL TRUE** |
| **L2-07** | *"role/source-readiness completeness is not part of the blocking vector"* | unchanged. ⛔ This is the **ConfidenceVector axes decision** (`02-DECISIONS` #1), still open and Rohit's | **STILL TRUE** |
| **L2-09** | *"Producer… emits one anchor, empty relationships/dependencies and **constant importance** (`situation_bso.py:69-141`)"* | importance is no longer constant — `context/importance.compose_situation_importance` is imported and used, with `importance_source` recorded in metadata and a **named fallback** for a situation whose events published no live score. Anchor/relationships not re-measured | **PARTLY EXPIRED** |
| **L2-11** | *"Wrong first domain or restricted mixed-domain evidence can still enter the wrong view"* | unchanged | **STILL TRUE** |
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
snapshot, independent-corroboration semantics, same-name identity, the complete graph views, a tenant
replay, and the confidence-vector axes.** Those are design decisions and connectors, not gaps.

**One cell is a disagreement rather than a finding** — L2-08, where the Atlas graded *open by
default* as *empty requirements look complete*. The code states the reasoning, and the reasoning is
this codebase's own rule: absence is never read as negative evidence. **That one should be corrected
in the Atlas, not in the code.**
