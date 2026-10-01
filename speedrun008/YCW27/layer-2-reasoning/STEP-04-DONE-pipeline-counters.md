# Step 4 — ✅ DONE · the five pipeline counters

> **Tree:** `M11.C3.U01/U02` · **Section S4** · 2 units · **42 tests**

---

## 1 · What was expected

That the funnel `signals_detected → situations_formed → capability_resolved → decision_emitted →
card_delivered` existed somewhere.

## 2 · What is actually true

**Zero hits for all five**, across `genios_engine/` and `migrations/`.

So *"we made 28 cards"* and *"we made 28 out of 4,000 signals and lost 3,900 at a step nobody can
name"* were the same sentence.

⛔ **Every layer in this programme has found at least one defect a funnel count would have surfaced
years earlier:** `l4_bundle` at 0 successes from 600 calls; a five-day total model outage, twice; 467
situations held with nobody asking why; three modules built, tested, green and called by nothing. Each
was found by hand, by reading the graph against the cards.

## 3 · What was built

| Unit | Artifact |
|---|---|
| `U01` | `migrations/0188_pipeline_counters.sql` + `platform/funnel.py` |
| `U02` | `api/routes.py` · `_run_l2_chain` — four of the five counted |

## 4 · Three design decisions, each with its failure mode

**⛔ One row per stage, never one wide row.** A wide row needs every stage to have run before it can be
written, so a sweep that dies at stage three writes **nothing** — losing exactly the measurement that
would explain the death. Per-stage rows mean a partial funnel is still a funnel, and *"stages 1 and 2
wrote, 3 did not"* is itself the diagnosis.

**⛔ A zero is written, not skipped.**

| | |
|---|---|
| `situations_formed = 0` | the stage **ran** and formed nothing |
| *(no row)* | **nobody looked** |

`read_sweep` returns `None` for a missing stage, never `0` — returning zero for both would undo the
table's whole purpose at the last hop. This programme has been caught twice by exactly that conflation:
`no_model_wired` in L1 and the graph-revision guard in L3.

**⛔ It lives in `platform/`, and the topology forced that.** Five packages write these five numbers,
`capture` (layer 1) through `deliver` (layer 6). A writer in any one of them would be imported upward by
at least three others, and `tests/test_layer_topology.py` fails the build on an upward import — it
caught `capture/acquire/need_executor.py` doing exactly that earlier the same day. `platform/` is
cross-cutting, so it is the only home that does not make the dependency graph a lie.

## 5 · ⛔ The number this chain refuses to invent

**`signals_detected` is deliberately not written.** It belongs to `capture`, and nothing in
`_run_l2_chain` holds an honest count of it: `_reread_unread` returns a **recovery** count (mail
captured while L1 was off), not qualified signals detected.

> Labelling that number `signals_detected` would put a **wrong** number where a missing one belongs.
> `None` says nobody looked; a wrong number says we did.

It reads `None` until the capture sync writes it. `test_signals_detected_is_deliberately_not_written_here`
asserts the omission, and the source says why at the point of omission.

## 6 · ⛔ One SOURCE per number — and a check I almost got wrong

My plan said *"five writers, one per layer. Never a central collector."* I then wired all four writes
from `_run_l2_chain`, which looks like a collector.

The doctrine's actual requirement is narrower and I restated it: **a collector must not RE-DERIVE a
number it did not compute**, because a re-derived count can disagree with the thing it counts. Every
value here is read straight off the result dict of the pass that produced it — a **relay**, not a
recomputation — and `test_no_number_is_derived_by_arithmetic_in_the_chain` asserts no `+`, `-`, `sum(`
or `len(` appears in any `_count(...)` call.

Writing at the chain buys **one sweep id shared by all four**. A per-pass write would need the id
threaded through fifty call sites, and passes run outside this chain would write rows that cannot join
to anything.

⛔ **And I almost redesigned the migration on an unverified belief.** I assumed the five stages happened
in three separate passes, which would have made a `sweep_id` primary key wrong. `api/routes.py:580`
disproved it: `process_pending` → `run_l3` → `build_cards_for_org` run **in one chain, in one function.**
The key is right. Reading the code first saved a redesign.

## 7 · Verify

```
$ uv run --no-sync pytest tests/platform/test_a_zero_is_written_not_skipped.py -q
26 passed

$ uv run --no-sync pytest tests/test_the_funnel_has_five_numbers.py -q
16 passed

$ uv run --no-sync pytest tests/platform tests/reason tests/test_the_funnel_has_five_numbers.py tests/test_layer_topology.py -q
1344 passed, 99 skipped in 160s
```

## 8 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| a count of 0 | written | ✅ |
| a stage that wrote no row | reads back `None`, never `0` | ✅ |
| a real 0 vs a missing row | different | ✅ |
| a stage name outside the five | refused **by name** | ✅ with the list, not an `IntegrityError` |
| a negative count | refused | ✅ *"not a small count, a broken writer"* |
| 4000 → 100 → 90 → 85 → 28 | the worst pair named | ✅ `(signals_detected, situations_formed, 3900)` |
| a pair with an **unmeasured** end | ⛔ skipped, not a total collapse | ✅ or it sends somebody debugging a stage that never reported |
| a stage that grew | not called a loss | ✅ it is a defect, but not a funnel loss |
| a re-run of one sweep | overwrites | ✅ `expertise_packages` reached 181 MB by appending |
| the database down | `observe` returns False | ✅ so a caller can say "unmeasured", not "zero" |
| `signals_detected` | ⛔ **not written** | ✅ and the omission is documented where it happens |

## 9 · For Rohit

**One migration to apply: `0188_pipeline_counters.sql`.** Until then the chain's funnel writes are
swallowed and logged; nothing breaks, nothing is measured.

## 10 · For Harsh

`platform/funnel.py` has the five stages, `STAGE_OWNERS`, and `biggest_loss()`. `signals_detected` needs
the **capture sync** to call `funnel.observe(...)` with its own honest count — that is the one stage this
chain cannot produce, and it is the first stage of the funnel, so it is the one worth wiring next.
