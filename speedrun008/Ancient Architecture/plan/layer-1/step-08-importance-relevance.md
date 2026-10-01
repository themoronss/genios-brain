# Step 8 — Importance ceiling and the relevance allocator

**Status:** NOT STARTED · **Effort:** days · **Depends on:** 4 · **Engine:** D
**Moves:** metric 5 — events never judged, **69 (31%) → <5%**

> **Re-measure before starting.** Step 4 feeds ALG-17 new typed inputs; the ceiling may have moved
> on its own.

## 1. Why this step exists — two defects that both cap the top of the scale

### a · Every score is under half the scale

> The whole tenant topped out at **4,640 bp of 10,000**. 395 signals, none above 4,700.

Arithmetically: the weights are `money 3000 · deadline 2500 · criticality 2000 · authority 1500 ·
signal_type 1000`. This inbox carries almost no amounts, so the money term — **30% of the scale** —
contributes ~0 for nearly every signal. `entity_criticality` sits at `first_seen` (2,000 bp) for
nearly every counterparty on a three-week-old graph. **The effective range was roughly 0–5,000, and
the tenant used all of it.** Then a floor at 2,500 did most of the sorting.

**This is not a formula bug. It is a cold-start bug** — ALG-17 is calibrated for a tenant with a
priced history and a populated graph, and it degrades **silently**. The `baseline_estimated` flag
already exists; **nothing reads it.**

### b · A third of events were never judged for relevance

> `ambiguous_over_budget` — **69 events**, 31% of everything that reached Layer 2.

`AMBIGUOUS_BUDGET_BP = 1000` (10%, min sample 50): above that share the unit **alerts instead of
spending**, and events fail open at unknown authority. On a three-week-old tenant almost every
sender is unknown, so the guard trips and the component that could have said *"this is a mass
programme announcement"* never runs.

The doctrine — *a high ambiguous share is a graph-coverage problem, not a relevance one* — is
right. Its consequence is still that the judgment is **binary: all or nothing**, when the correct
behaviour on a constrained budget is to spend it where it changes the outcome.

## 2. Current status
`esqe/importance.py` (1,184 LOC, mutation-checked: `return 5000` turns 16 tests red) ·
`esqe/baseline_reader.py` (`baseline_estimated` set, never read) · `esqe/relevance.py` (5-rule
ladder, LLM-5 on the remainder, all-or-nothing budget guard) · `DEFAULT_FLOOR_BP = 2500`,
per-tenant via `org_qualification_floors` with an owner and an append-only change log.

## 3. Expected result

| | Before | After |
|---|---|---|
| Events never judged | **69 (31%)** | **<5%** |
| Achievable ceiling published | no | yes, per tenant, beside the score |
| Cold-start recorded | flag set, unread | acted on |
| Floor | absolute 2,500 | relative to the tenant's measured distribution |
| **ALG-17 output on identical inputs** | — | **byte-identical** |

**The prediction that defines success:** the distribution's **shape** does not change. If p50, p90
or the distinct count move, **the formula was changed and the step failed.**

## 4. Edge cases
E1 a tenant with real amounts → nothing should change for them · E2 the allocator spends the budget
on high-importance items, but importance is *computed after* relevance → order by the best
available proxy and **say which** · E3 an unjudged event must be distinguishable from a judged-
relevant one — today both arrive as "kept" · E4 a relative floor on a tenant with 3 signals is
meaningless → fall back to the absolute floor below a minimum sample · E5 changing the floor is a
**row with an owner and a date**, never a deploy · E6 LLM-5 transport failure still fails **open**.

## 5. How to do it
| Unit | What |
|---|---|
| 8-U1 | record when the money term was **structurally unearnable** — a zero for a structural reason is not a zero on merit |
| 8-U2 | publish the achievable ceiling beside the score, so 4,640 reads as high rather than mediocre |
| 8-U3 | floor relative to the tenant's measured distribution, with an absolute fallback below a minimum sample |
| 8-U4 | replace the on/off guard with an **allocator**: sort the ambiguous remainder, spend top-down |
| 8-U5 | `unjudged_for_budget` as a first-class provenance value |
| 8-U6 | a per-tenant importance distribution report in CI, not only at gate time |

## 6. Test cases
T1 ALG-17 byte-identical on identical inputs (**the guard**) · T2 distribution holds: >50 distinct,
p90−p50 > 1500 · T3 cold-start tenant carries the unearnable-term marker · T4 the allocator judges
the high-importance head within budget · T5 `unjudged_for_budget` is distinguishable from
"relevant" (RED today) · T6 LLM-5 transport failure still keeps the event.

## 7. Verify
```bash
uv run --no-sync pytest tests/capture/esqe/test_importance.py tests/capture/esqe/test_relevance.py -q -p no:randomly
uv run --no-sync pytest tests/capture/esqe/test_qualification.py -q -p no:randomly
python scripts/importance_distribution.py --org <org> --database-url "<url>"
```

## 8. Done criteria
**Ticked 2026-09-24.** Three closed, one is Harsh's, one is untouched-and-still-true.

- [x] **T1 green — the formula is provably unchanged** — `IMPORTANCE_WEIGHTS_V1` is asserted
      member by member (`3000 · 2500 · 2000 · 1500 · 1000`, total 10000) in a test that fails in a
      DIFF rather than at import, so a weight edit inside this step is visible to a reviewer. The
      ceiling is computed strictly AFTER `importance_bp` is final.
- [x] **T2 green — distribution properties hold** — `test_importance_gate_probe.py`, 10/10,
      including `test_gate_the_distribution_is_wide_enough_for_layer_4_to_rank_on` and
      `test_gate_the_whole_corpus_replays_byte_identically`.
- [ ] **unjudged events < 5%, recorded in `STATUS.md`** — **NOT DONE, and it is Harsh's.** The
      allocator changes 100%-unjudged into a bounded share, measured on the test page as
      **40 → 30 of 40 deferred with 10 judged where 0 were before**. The production number needs
      the live corpus; the 31% baseline is from a tenant re-synced away on 19 Sept. **Deliberately
      not ticked** — a target against a vanished baseline is the mistake this plan exists to
      prevent.
- [x] **the achievable ceiling is published per tenant** — `ImportanceScore.achievable_ceiling_bp`,
      set by `score_importance` itself and driven by `test_the_ceiling_is_populated_by_the_real_
      scorer`. It is the FIRST reader `ImportanceFlag` has ever had: ten flags, computed on every
      score, and a grep for `.flags` outside the module returned zero.
- [x] **any floor change is a row with an owner and a date** — **untouched and still true.**
      `org_qualification_floors` has an owner and an append-only change log, and this step did not
      change the floor. 8-U3 (a relative floor) is deferred with a reason — see the findings §5.

## 9. Must NOT do
**Do not change ALG-17's formula, its five weights, or the sum-to-10000 check.** Do not let a model
produce or adjust `importance_bp`. Do not raise the budget to make the problem go away — **allocate
it**. Do not change the floor by deploy.
