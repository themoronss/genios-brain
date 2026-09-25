# L3-05 · Evidence lineage — findings

**Run:** 2026-09-25 · premise checked before any code · **no migration · no model call**

---

## 1. ⛔ The plan's headline claim was FALSE, and that is the finding

The plan said, in bold, three times across three documents:

> *"CQ-HCS-01 is a live defect, not a design question. The ladder is one:60 / two:85 / three+:100,
> driven by `src_count`, deduped **per event** — and ten forwards of one original are ten events.
> So ten copies of one claim read as ten independent sources today."*

**`reason/runner.py:105`:**

```sql
(select count(distinct sr.source) from graph_source_refs sr
   join graph_facts fv on fv.fact_version_id=sr.fact_version_id and fv.org_id=f.org_id
 where fv.fact_id=f.fact_id) as src_count
```

⛔ **`count(distinct sr.source)`. Ten Gmail forwards are one system. The ladder was never fooled.**

### 1.1 · What I mistook for the whole picture

`graph_store`'s corroboration branch dedupes **per event**, and I read that as the only protection.
Its own comment says otherwise in the next clause — *"deduped per event so a re-sync doesn't
inflate; **distinct-source counting downstream handles same-source repeats**"* — and the downstream
counting is real.

**Two layers, two jobs: the write side stops a re-sync doubling a ref, the read side stops one
channel counting twice. I measured the first and asserted the second did not exist.**

### 1.2 · And `evidence_score` had already fought this argument

`situations.evidence_score` splits **60 for corroboration against 40 for volume**, uses
`count(distinct se.source)`, and its docstring records a previous version that had the split
inverted *"and made this docstring a lie"*, now pinned by tests. It even records the correction
that `voice_count` exists because tool-count alone put a ceiling on correspondence-only tenants.

**This was considered, got wrong once, was fixed, and was pinned. My plan called it unbuilt.**

---

## 2. ⛔ What was actually wrong — one word, duplicated, untested

The `distinct` was a keyword inside **two hand-written copies** of the same subquery
(`runner.py:105` and `runner.py:157`), and **no test drove either.** Every test in the suite
supplies `src_count` as a literal.

**So deleting the word would have pushed every fact to the top corroboration rung with nothing
failing anywhere.**

⛔ **That is L3-04's shape exactly** — `graph_store._WINDOW_AT` and `importance.FACT_WINDOW_AT`, one
predicate in two readers — **except that one had a pin holding the copies together and this had
neither a pin nor a single home.**

### 2.1 · Built

| | |
|---|---|
| `_SRC_COUNT_SUBQUERY` | one home, both readers reference it |
| the pin | `distinct` present, `count(sr.source)` absent, counted over `fact_id` not `fact_version_id` |
| the rungs | 60 / 85 / 100 pinned, so the word stays load-bearing |
| the authority path | rank ≥ 3 reaching 100 alone, pinned so it is not read as a bug later — ⛔ **the one route to the top rung copies cannot fake, because a forward does not change its rank** |

---

## 3. ⛔ The residual hole, declared rather than built

`distinct sr.source` collapses copies **within** one channel. It does not collapse **one original
assertion quoted across channels** — CC-27's *"a Slack discussion quotes the original email and a
meeting summary quotes the Slack discussion"* is **three distinct sources and one lineage**, and it
would reach the top rung.

`graph_source_refs.independence_group` is the column for exactly that, and it is populated only for
the narrow screen/email same-message case in `capture/screen/fingerprint`.

⛔ **Not built, on purpose.** A two-connector tenant cannot produce the case. Building a lineage
system for an unreachable failure is the over-scaffolding this plan refuses — **the same reason
L3-01 declined to add a second decision identity.** `LINEAGE_UNPROTECTED` declares it with a reason
and a mover (**the third connector**), guarded by a test.

---

## 4. My own mistakes in this step

**The seventh blunt grep, and it was mine.** `test_the_subquery_has_exactly_one_home` counted the
SQL string anywhere in the module and went red at 3 — **because the constant's own explanation and
the declared-silence note both name the SQL they are explaining.** Comment lines are now stripped
before counting.

**And two mutation probes were wrong rather than the tests being weak.** MUT 1 replaced the first
occurrence of the string, which is in a comment, so the constant was never touched; MUT 3 wrote
`{} or {…}`, which evaluates to the original dict. **Both looked like passing probes and were
no-ops.** Re-run against the real code, both go red.

⛔ **A mutation that does not apply is indistinguishable from a test that does not work, and only
asserting that the edit changed the file tells them apart.**

---

## 5. Result

```
FULL SUITE   13,204 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-05: 13,198 passed · 14 failed
```

**+6 tests · 0 regressions · no migration · no model call. ⛔ Wave 1 complete.**

**Technique 3 — five mutations, all red:** drop the `distinct`; count per version; undeclare the
residual hole; collapse the middle rung; remove the authority path.

## 6. What this step does NOT do

* **It does not build cross-channel lineage.** Declared, with a mover.
* ⛔ **It does not change a single computed number.** Every score is what it was; what changed is
  that it cannot silently stop being.
