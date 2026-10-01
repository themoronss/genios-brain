# The program — what we are going to do, in order

**44 units · 7 milestones · critical path 10 units long.** The tree lives at `../../tree.yaml`
under `atlas_v2_alignment`. `M1`–`M7` above it are permanent and retired in place; their ids are
never reused.

**Order is data-flow, not Atlas numbering** — `capture` feeds `context`; `reason` READS `context`.
The Atlas numbers Reasoning L2 and the Context Graph L3, but data reaches them the other way round.

---

## The order, and why each step is where it is

| # | Milestone | Folder | Units | Why here |
|---|---|---|---|---|
| 1 | **M8 · The baseline is true** | — | 15 | One of three spot-checked badges was wrong. Everything downstream is planned against these numbers |
| 2 | **M9 · L1 Enterprise Signals** | `layer-1-enterprise-signals/` | 9 | Nothing above can be fed better than L1 hands up |
| 3 | **M10 · L3 Context Graph** | `layer-3-context-graph/` | 5 | `reason/` reads `context/`; the read has to be bounded before it is relied on |
| 4 | **M11 · L2 Reasoning** | `layer-2-reasoning/` | 4 | Needs the bounded read below it and the vector decision above it |
| 5 | **M12 · L4 Executive** | `layer-4-executive/` | 4 | The first milestone whose queue stops being empty |
| 6 | **M13 · L5 Delivery** | `layer-5-delivery/` | 4 | A lane can only render once L2 produces one |
| 7 | **M14 · L6 Learning** | `layer-6-learning/` | 3 | Attribution needs a card that named its layer |

## The critical path

```
M8.C1.U01  extract every Atlas claim
   → U03   resolve each against the code
   → U04   the corrected baseline, committed
      → M8.C2.U07  the naming freeze
         → U09     the totality guard, both directions
            → M9.C2.U06  EvidenceNeed contract
               → U07     evidence_needs table
                  → U08  the executor
                     → U09  residue.signal_unreached raises a need
                        → M10.C2.U05  a met need clears its hold
```

Delivery length is bounded by **verification and a naming decision**, not by any feature. That is
the shape we wanted: the expensive part is agreeing what is true, and it is front-loaded.

---

## M8 — the baseline is true · 15 units

| Category | What ships |
|---|---|
| `M8.C1` Badge verification | `scripts/atlas_claims.py` + `atlas_probe.py` + `atlas_verify.py`, and `ATLAS_BASELINE.md`. A **re-runnable** check, not a one-time read |
| `M8.C2` The four decisions | each recorded as enforced code — see `02-DECISIONS.md` |
| `M8.C3` The funnel counters | `signals_detected → situations_formed → capability_resolved → decision_emitted → card_delivered` |
| `M8.C4` The Atlas, corrected | both editions brought level with the baseline |

The probe answers **EXISTS / ABSENT / UNPROVABLE**. `UNPROVABLE` is a real third answer and is
never silently read as `ABSENT` — that is the mistake the Atlas made with coverage receipts.

## M9 — L1 · 9 units

`M9.C1` the signal bundle — a contract, a table, the incoming-only grouper, the coverage receipt
assembled from what already exists, and a publisher that emits it **beside** `qualified_signals`
rather than over it. `M9.C2` the evidence-need door — contract, table, executor, and the wire from
`residue.signal_unreached` that does not exist today.

## M10 — L3 · 5 units · ✅ **COMPLETE 2026-09-30** (4 built, 1 withdrawn)

`M10.C1` the bounded query API — seeds, hops, max nodes, visibility, and the revision it read.
`M10.C2` a HOLD that asks instead of waiting.

| Unit | Status |
|---|---|
| `M10.C1.U01` read request contract | ✅ `context/bounded_read.py` |
| `M10.C1.U02` the bounded reader, reporting truncation | ✅ same file |
| `M10.C1.U03` compare-and-set on write | ⛔ **RETIRED — already built.** `reason/runner.py:570` is it |
| `M10.C2.U04` a hold raises a need | ✅ `context/hold_needs.py` |
| `M10.C2.U05` a met need clears its hold | ✅ `context/hold_resolution.py` |
| *(added)* the needs queue, written and called | ✅ `context/evidence_need_store.py` + `context/runner.py` |

**91 new tests. `tests/context` whole: 2,679 passed, 0 failed.**

⛔ `M10.C1.U03` is **retired, not deferred.** The finding behind it was wrong: I grepped `context/`
for the guard, and the read-modify-write spans packages by design, so `context/` is the one place it
could not be. See [STEP-02](layer-3-context-graph/STEP-02-WITHDRAWN-compare-and-set.md). The rule
this adds: **a guard lives with the reader, not the writer.**

⛔ **The loop is half-closed.** The sweep files evidence needs; no pass works them yet, because the
executor needs real connector `fetchers` — the L1 integration gap owned by Harsh. The queue is
write-only until then, and `evidence_needs_filed > 0` must not be read as "something is being
fetched".

## M11 — L2 · 4 units

⛔ **CORRECTED 2026-09-30 — the original text of this paragraph was wrong twice.** It said:

> *`M11.C1` dependency-complete plans — plan compile fails when a scheduled unit declares a source no
> other scheduled unit produces. This is the live defect that leaves two of `core.risk`'s three
> plugins silent.*

**Both halves are false.**

1. ⛔ **The fix would be a REGRESSION.** `reason/plan.py:229` records removing exactly that rule: under
   it *"six units lost to one absent fact"*. The settled rule is that a unit is dropped only when it
   has NOTHING left to read.
2. ⛔ **The defect does not exist.** Measured by `scripts/l2_unit_silence.py`: `core.risk` is **one**
   unit, not three plugins, and it completed **1,165 of 1,165**. 20 of 22 units speak. `core.policy` is
   silent by design. `core.relationship` returned `insufficient_context` 532 times and completed never
   — **but every per-unit result row postdates the 25 Sep model outage, so nothing there is
   attributable yet.**

**What M11.C1 actually is:** a **receipt**, not a refusal. A unit that is KEPT and loses one of several
sources records nothing today — 3,102 by-design skips are receipted and zero partial losses are. See
`layer-2-reasoning/02-PLAN.md` §S2 and `STEP-01-DONE-prove-the-claims.md`.

`M11.C2` the five output lanes, and the router that chooses one deterministically — ⛔ **not** merged
into `DecisionOutcome`, and **never** named a bare `lane` (it collides with `reason/uncited_lanes.py`).
Plus `M11.C3`, added: the five pipeline counters, which do not exist at all (0 hits).

## M12 — L4 · 4 units

`M12.C1` organisation data — seats, the reporting line from `seat_responsibilities.reports_to`,
channels. `M12.C2` the activation row and the end-to-end walk as a **test**, not a demo.

## M13 — L5 · 4 units

⛔ **CORRECTED 2026-09-30.** `M13.C1` claim-level validation — widening the invention validator
(which **exists**, at `deliver/render.py:334`) from numbers, names and dates to every claim, without
weakening it. `M13.C2` the lane on the card — and **not** the scalar floor replaced by lane routing,
because there is no scalar publication floor in `deliver/`: `gate.py` is moment + permission,
`bands.py` cuts an urgency band from pack config, and the score gate is `reason/runner.py:1133` whose
`below_gate` receipt `executive/explain.py` already reads. `U04` became the **recall guard**, the
half of the unit that was real and unproven.

The recall guard itself stands exactly as written — **fewer cards must come from merging, never from
dropping** — and is now proved rather than asserted: no decision under the confidence floor may land
in a silent lane, at any floor a tenant could set, walking the real router; and the six per-lane
tallies must sum to the cards actually written.

## M14 — L6 · 3 units

⛔ **CORRECTED 2026-09-30.** *"A timing complaint never lowers a correct rule's precision"* was
**already true in three independent places** — `TAXONOMY`'s `precision: "none"`, `units.py:135`, and
`_PRECISION_SQL`'s reason list — with a fourth documenting it. `U03` became the **layer debit** plus
the first guard over that property, because a rule enforced in three places can be broken in three
and none of them failed a build.

`M14.C1` attribution by layer — eleven reasons, each mapped to exactly one layer, closed in both
directions, so `bad_timing` reaches L5 timing rather than a correct rule's precision.

---

## Three verify commands that are not yet sound

Named here because a build must not start by pretending they are.

1. **`tests/platform/test_migrations_apply.py` does not exist**, and three units name it as their
   verify (`M8.C3.U10`, `M9.C1.U02`, `M9.C2.U07`). Either add the unit that creates it, or change
   all three.
2. **`M8.C1.U03`'s `--report` exits 0 even with disagreements.** An exit code that cannot fail is
   not a verification. Either it grows `--zero-disagreements`, or we accept that `U04` is the gate.
3. **`M8.C2.U06` and `U08` both verify on `test_layer_topology.py`** — the same command for two
   units, and it passes today. The test has to be extended by each unit, or both go green having
   changed nothing.

## Not in this program

- **The heartbeat deploy.** It is the single most consequential open item (`01-BASELINE.md` §3) and
  it is a deploy, not code. Harsh owns it. Nothing above L1 can be called "measured in production"
  until it runs.
- **Re-basing the parity gate.** Rohit's, and it must become a ratio rather than a lowered
  threshold.
- **Backfill 60 → 365** on the pilot connection.
- **Sales and Support packs.** They stay in shadow until they pass Admin's evaluation bar.
