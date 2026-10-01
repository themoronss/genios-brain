# L3 cross-check — built vs. asked, 30 Sep 2026

Every row was read in the code. The pilot numbers are Harsh's 29 Sep read-only measurement.

> **Verdict: unlike Layer 1, Layer 3's gaps are real.** The two things `M10` asks for — a bounded
> query API and a compare-and-set write — are genuinely absent. But the *third* finding is the
> familiar one: the revision counter that a compare-and-set needs **already exists and is never
> read as a guard.**

---

## 1 · The bounded query API — genuinely missing

`context/` offers exactly two graph reads:

```python
GraphStore.read_graph(org_id, *, as_of)   # the whole org, at a moment
GraphStore.live_graph(org_id)             # the whole org, now
```

**No seeds. No hop limit. No node cap. No visibility of the asking seat.** A caller wanting three
nodes gets the tenant's entire graph and filters in Python.

That is survivable at 66 situations and is the wrong shape at any size — and it is the shape the
reasoning layer has to read through, so the cost lands on the layer that can least afford it.

`read_models.py` has `build_entity_360` and `private_facts_for`, which are *fixed* projections for
one node. Useful, and not the same thing: they answer a question somebody already decided on.

## 2 · ~~Compare-and-set — missing~~ · **WITHDRAWN. I was wrong.**

**Corrected 2026-09-30, before any code was written against it.**

What this section originally said: *"`graph_versions` is read in exactly two places, and neither is
a guard — the version is a label, not a lock."* That claim was produced by grepping for the version
read **inside `context/` only**. It is false.

The compare-and-set exists, and it is not a sketch:

| Where | What it does |
|---|---|
| `reason/runner.py:570` `_graph_version_guard` | reads the tenant row `for share`, compares `current == expected`, and **yields a boolean** |
| `reason/runner.py:1276` | the caller **honours it** — on drift it sets `graph_drifted` and counts `graph_changed_retry` instead of publishing |
| `deliver/` × 8, `api/` × 4 | take `for share` on the same row before reading, so a delivery cannot straddle a write |
| `tests/test_graph_version_consistency.py` | **6 tests, all passing**, including `test_runner_captures_graph_version_before_tenant_p90_and_retries_on_drift` |

The guard is also better than the one I was about to build: the refusal is a **value**, not an
exception, which was the one design constraint I had written down as the thing that mattered.

### Why I got it wrong, recorded so it is not repeated

I searched one package for the reader and concluded from its absence there. The read-modify-write
cycle **spans packages by design** — `context/` writes and bumps, `reason/` reads and guards — so
looking for the guard next to the bump was looking in the one place it could not be. The rule this
adds to the programme:

> **A guard lives with the reader, not with the writer. Absence in the writer's package is not
> absence.**

This is the second time a count taken along the wrong dimension produced a confident wrong finding
in this programme. The first was `no_model_wired` in Layer 1.

### What is actually left, and it is much smaller

`_graph_version_guard` is **private to `reason/`** and carries pack-authority and watermark logic
specific to reasoning publication. `context/` is a lower layer and cannot import it. So a
read-modify-write that *starts from the new bounded read* has no guard available to it in `context/`.

That is a real gap and it is worth exactly one unit — **but only once something needs it.** Building
it now would be the six-times defect: built, tested, green, called by nothing. It is therefore folded
into Step 4, which is the first caller. See [STEP-02](STEP-02-WITHDRAWN-compare-and-set.md).

## 3 · The holds — and which of them are actually evidence questions

Measured on the pilot: **467 held against 223 admitted.**

| Hold reason | Count | Is it an evidence question? |
|---|---|---|
| `verified_evidence_required` | 398 | ✅ a span could not be verified — fetching the source settles it |
| `qes_required` | 398 | ✅ Layer 1 published no qualified signal for it |
| `source_coverage_insufficient` | 69 | ✅ **the clearest one** — we did not read enough to make the claim |
| `identity_review_required` | — | ❌ a merge proposal is open. **A human decides**; more evidence does not |
| `pattern_evidence_required` | — | ~ depends on the pattern — receipt vs. source |
| `conflict_open` | — | ❌ two sources disagree. This is **adjudication**, not absence |
| `cross_domain_contradiction` | — | ❌ same — two domains claiming opposite things |

⛔ **The exclusion is the design, exactly as it was for residue in Layer 1.** Raising an
`EvidenceNeed` for `conflict_open` would send Layer 1 to fetch a fact it already has *twice*, and
the need would close successfully — teaching the system that conflicts resolve themselves.

## 4 · Two integration gaps inherited from Layer 1

Both land here, because this is the layer that owns the sweep.

| Gap | Where it belongs |
|---|---|
| nothing calls the residue → `EvidenceNeed` conversion on a sweep | `context/runner.py:1347`, immediately after `detect_residue` |
| the executor's `fetchers` map is injected and nothing injects real connectors | the composition root, driven by a sweep pass |

## 5 · What is NOT wrong here

| | |
|---|---|
| the situation publisher | ADMIT / HOLD / REJECT is sound, and HOLD already distinguishes **recoverable** incompleteness from the rest |
| the two graphs | the Intelligence Graph is a foreign-key chain with **no tables of its own**, and 0 hard deletes. Keep it that way |
| correlation | ten modules, joins only — the group law holds |
| the sweep's cycle | state → residue → angles → readings → re-rank, with a second pass. The ordering comments explain why reordering would break the coverage measurement |
| `context/quality/window.py` | the coverage read — *"read 37 of about 465"* — built and correct |

---

## What M10 actually is

| Unit | Status after cross-check |
|---|---|
| `M10.C1.U01` bounded read contract | ✅ stands — genuinely missing |
| `M10.C1.U02` the bounded reader | ✅ stands |
| `M10.C1.U03` compare-and-set | ✅ stands — **and cheaper than it looked**, the counter exists |
| `M10.C2.U04` HOLD raises a need | ✅ stands — **with an exclusion rule**, only 3 of 7 hold reasons qualify |
| `M10.C2.U05` a met need clears its hold | ✅ stands |
| **new** | wire residue → needs into the sweep (inherited from L1) |

---

## Addendum — after the build, 2026-09-30

Four of five steps built, one withdrawn. What the build taught that the cross-check did not know:

**Finding 2 was wrong** and is retracted in place above. The rule it produced: *a guard lives with the
reader, not with the writer.*

**Finding 3 was right about which reasons, wrong about how many questions.** `qes_required` and
`verified_evidence_required` are ONE question — the codebase had already measured it (480 of 504 holds
carry both) and written it down in `situation_bso.l1_refusal` and `_preflight`. Three reasons, two
questions.

**Two contracts refused inputs my defensive branches were written for**, which is the right outcome
and worth recording as a pattern:

| Branch | Refused by | Still reachable? |
|---|---|---|
| a candidate with no subject | `SituationCandidate.__post_init__` — demands ≥1 signal and ≥1 evidence | ✅ via a `RowMapping` on the publish path |
| an `unavailable` need with no reason | `EvidenceNeed`'s validator **and** migration 0187's check constraint | ✅ via a raw row |

Both guards stayed, both tests now use a row rather than a contract object, and both say why in the
docstring. A guard that the type system makes unreachable *through one door* is not dead code when
another door exists — but the test has to enter through the door that is actually open, or it proves
nothing.

**One test found a real defect in code I had just written.** The first bounded reader appended an edge
before checking the node cap, so a truncated view came back holding an edge to a node it refused to
contain. Fixed the code. That is the one and only outcome allowed there.
