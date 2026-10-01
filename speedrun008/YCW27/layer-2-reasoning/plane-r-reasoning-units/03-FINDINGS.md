# Plane R · FINDINGS — the index

> *How a professional thinks.* **59 guard tests.** 8 units across two step files.
> **The counted hierarchy, from code:** 4 categories — Situation Understanding (4), Business
> Evaluation (5), Optimization (5), Decision Support (3) = **17 core**, plus 6 supplementary
> (`legacy.rule`, `legacy.score_gate`, `temporal`, `relationship`, `signal_composition`, `planning`)
> = **23 units, 56 plugins**.
> **Date:** 2026-10-01.

---

| | Finding | Full record |
|---|---|---|
| **1** | ⛔ **Nothing anywhere said which units a unit reads.** A reasoner reads another's published metric by a **string**, so a source could stop publishing or never be scheduled and the consumer would go quiet with no error, no log and no failing test | `01-CROSSCHECK.md` → the `source_units` contract |
| **2** | **`tradeoff.cost_vs_benefit` had fired 0 times in 1,200 production rows** while `tests/reason/test_tradeoff_cost_axis.py` passed — on a prior the test supplies itself. **A green test over 1,200 rows where the axis has never spoken** | `../09-AUDIT-the-lost-axis-receipt.md` |
| **3** | **A default source was an inline literal** at `impact_unit.py:191`, so a rename would have left it pointing at a unit that no longer exists | `STEP-01` → `DEFAULT_RELATIONSHIP_SOURCE` at `impact_unit.py:127` |
| **4** | **Two units read nobody, and `()` is indistinguishable from an unfilled field** | `STEP-02-to-08` §3 → `core.confidence` and `core.priority` declare `()` **with the reason**, the same doctrine as `DeclaredSilence` |
| **5** | **`core.tradeoff`'s six sources existed as `AXIS_SOURCES` already.** Declaring them by hand would have created two lists that must agree with nothing making them agree | `STEP-02-to-08` §2 → the declaration is **derived**, with `sorted`/`set` to match what `declared_source_units` returns |
| **6** | ⛔ **The six supplementary units have no `unit_id` class attribute.** They predate the framework and are identified by `spec.reasoner_id`. This broke the guard at **pytest collection**, not at assertion time, which is why it was found late | `STEP-02-to-08` §4 → one `_id_of()` helper, rather than narrowing what the guard walks |
| **7** | **The roster and the unit described the same dependency from opposite ends with nothing making them agree** | `STEP-02-to-08` §5 → `U08`, 7 tests |

---

## ⛔ ALARM A5 — pinned here so it cannot widen silently

The live lane schedules none of `core.impact`, `core.cost`, `core.opportunity`. Switching
`core.tradeoff` on today would have it compare **1 of 6 axes** and report a tradeoff.
**Schedule the sources before the consumer.** Whose: **Rohit**, at roster activation.

⛔ An earlier version of this alarm said those three units are **never** scheduled. That was wrong —
all three have completed thousands of times. The alarm is about the *live* lane specifically, and the
correction is recorded in three files rather than edited away.

---

## What this plane did NOT do

**It did not make the axis fire.** `core.impact` publishes nothing because `deal.status` has no
writer, and the unit is **right** to be quiet — its own docstring: *"Silence is not zero … a
fabricated zero silently lies."* The defect was never the silence; it was that nothing downstream
could tell an honest silence from a measurement. That is now declarable, in
`reason/unit_health.DECLARED_SILENT`, with a reason and a mover (**Harsh**).

⛔ **Still open, and deliberately not fixed here:** `axis_count` and `axes_unavailable` are published
on every run and **read by nobody**. The fix is a reader, not a field — adding a field present on
every run breaks replay for every stored trace. Briefed as **CA2** in `../../HANDOFF-CODING-AGENT.md`.
