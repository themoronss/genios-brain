# Steps 2–8 — DONE · the seven remaining source declarations

> **Status:** DONE · **59 guard tests passing** · built 2026-09-30, recorded 2026-10-01
> **Why one file and not seven:** `02-PLAN.md` already specifies each unit in full, and six of the
> seven are a single declaration line. Seven files each restating one line would be seven places a
> count could drift. The plan is the spec; this is the record of what landed and what it cost.
> **The gap this closes:** the units shipped and only `STEP-01` had a note. A built unit with no
> record is indistinguishable from one nobody built.

---

## 0 · What the whole section was for

`core.tradeoff` had fired its `cost_vs_benefit` axis **0 times in 1,200 production rows** while
`tests/reason/test_tradeoff_cost_axis.py` proved the axis works — on a prior the test supplied
itself. The cause: a unit reads another unit's published metric by a string, and **nothing
anywhere said which units a unit reads.** So a source could stop publishing, or never be
scheduled, and the consumer would go quiet with no error, no log and no failing test.

**The contract this section introduced:** every reasoner declares `source_units` — the units whose
output it reads — and a guard proves the declaration cannot be forgotten or faked.

---

## 1 · The seven units, what each was, and what landed

| Unit | Task | Landed | File |
|---|---|---|---|
| `S5.U06` | the two units that read nobody declare `()` **with the reason** | `source_units: tuple[str, ...] = ()` + why | `confidence.py:429`, `priority.py:232` |
| `S5.U02` | `core.tradeoff` declares, **derived** from `AXIS_SOURCES` | `tuple(sorted({unit_id for _, unit_id, _ in AXIS_SOURCES}))` | `tradeoff_unit.py:277` |
| `S5.U03` | `core.risk` declares 2 | `(DEFAULT_RELATIONSHIP_SOURCE, DEFAULT_TEMPORAL_SOURCE)` | `risk.py:268` |
| `S5.U04` | `core.opportunity` declares 1 | `(DEFAULT_MOMENTUM_SOURCE,)` | `opportunity.py:219` |
| `S5.U05` | `core.impact` declares 1 | `(DEFAULT_RELATIONSHIP_SOURCE,)` | `impact_unit.py:306` |
| `S5.U07` | the guard cannot pass trivially | 8 tests | `tests/reason/reasoners/test_a_declared_source_cannot_be_forgotten.py` |
| `S5.U08` | the unit's declaration and the roster's must agree | 7 tests | `tests/reason/adapters/test_the_roster_and_the_unit_agree.py` |

`S5.U01` (`DEFAULT_RELATIONSHIP_SOURCE` becomes a named constant at `impact_unit.py:127`) has its
own record in `STEP-01-DONE-the-unit-source-contract.md`, and `U05` depends on it — which is why
the plan ordered them that way and why they are not in one unit.

---

## 2 · Why `U02` is derived and the others are literal — the decision worth keeping

`core.tradeoff` reads six metrics across three axes, and that list already existed as
`AXIS_SOURCES`. Declaring the six by hand would have created **two lists that must agree**, with
nothing making them agree. So `U02` computes the declaration from `AXIS_SOURCES`:

    source_units = tuple(sorted({unit_id for _, unit_id, _ in AXIS_SOURCES}))

`sorted` and `set` because `registry.declared_source_units` sorts and de-duplicates, so a derived
tuple that did not would fail its own equality check for a reason no reader would find.

The other four units read one or two sources, named by module constants that already existed after
`U01`. There is no second list to drift from, so a literal tuple of those constants is the whole
declaration — and it must be the **constants**, not retyped strings. A retyped `"core.relationship"`
satisfies the guard while defeating the thing the guard is for: renaming the constant would leave
the copy pointing at a unit that no longer exists. `opportunity.py:218` carries that warning in a
comment, pointing at `tradeoff_unit.source_units`.

---

## 3 · What `U06` is actually asserting, because `()` looks like nothing

`core.confidence` and `core.priority` read **no** other unit's output. An empty tuple is therefore
correct — and indistinguishable from a developer who never filled it in. So both carry the reason
beside the declaration. This is the same doctrine as `unit_health.DeclaredSilence`: *a declared
absence with no reason is an undeclared absence with paperwork.*

---

## 4 · Why `U07` exists at all

A guard that only checks *"does every reasoner have a `source_units` attribute"* is satisfied by
eight empty tuples. `U07`'s 8 tests prove the declaration is **load-bearing**:

* every unit id a module names in a `DEFAULT_*_SOURCE` constant appears in some `source_units`
* a declaration naming a unit the registry does not know raises `UnregisteredSourceUnit`
* `declared_source_units` sorts and de-duplicates, so two orderings are one declaration

⛔ **The six supplementary units have no `unit_id` class attribute** — they predate this framework
and are identified by `spec.reasoner_id`. That broke the guard at **pytest collection**, not at
assertion time, which is why it was found late. Closed with one `_id_of()` helper rather than by
narrowing what the guard walks.

---

## 5 · `U08` · the roster and the unit must agree, and they are two different authors

`reason/adapters/expertise._ROSTER` binds units to fact paths; the unit declares the units it
reads. Both describe the same dependency from opposite ends, and nothing made them agree until
`U08`'s 7 tests. This is the same shape as `unit_health`'s hand-written `bound_by` versus derived
`roster_fact_paths()` — two independent statements of one fact, asserted equal.

---

## 6 · Outcome, measured

    tests/reason/reasoners/test_a_declared_source_cannot_be_forgotten.py     8
    tests/reason/adapters/test_the_roster_and_the_unit_agree.py              7
    tests/reason/test_selector_and_registration.py                         14
    ...with the rest of the section's coverage                       59 passed

    tests/reason, whole package                                   1,392 collected
    full suite                                            14,534 passed, 0 failed

### ⛔ WHAT THIS SECTION DID **NOT** DO, and must not be read as doing

**It did not make `cost_vs_benefit` fire.** The axis is still silent in production, because
`core.impact` completes and publishes nothing — 100% silent, declared in
`reason/unit_health.DECLARED_SILENT` with its reason and its mover (**Harsh**, a writer for
`deal.status`). What this section changed is that the silence is now **declarable and visible**
instead of arriving as a zero nobody could distinguish from a measurement.

`S5.U08` also pins **ALARM A5** so it cannot widen silently: the live lane schedules none of
`core.impact`, `core.cost`, `core.opportunity`, so switching `core.tradeoff` on today would compare
1 of 6 axes. Schedule the sources **before** the consumer. Whose: **Rohit**, at roster activation.
