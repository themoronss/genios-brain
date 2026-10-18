# 24 · `reason/` AUDIT — twenty retirements, and the finding was in the audit's own measurement

**Written for:** Rohit. **Date:** 2026-10-03. ⛔ **Step `1.3` of
[`21-PLAN-TO-PRODUCTION.md`](21-PLAN-TO-PRODUCTION.md).**

```
reason/     121 files · 41,363 lines · 21 writers · 35 tables · ⛔ 29 with no receipt
new tests   26  ·  the two guards below
⛔ candidates 20 raised · 20 retired · 0 receipts added
⛔⛔ the finding  the audit's own "no test names it" column was wrong 19 of 33 times, and is DELETED
```

---

## 0 · ⛔ Why no receipt was added, and why that is the right outcome

`reason/` leads the uncovered-table list with **29**. Every claim that was derivable turned out to
be **already enforced or already receipted**:

| candidate | ⛔ why it died |
|---|---|
| `signals` — 29 readers, **six** writers in `reason/`, no receipt | the owner states the contract itself: *"**Projection, not decision.** … publishing twice from the same execution produces **byte-identical bindings**."* ⛔ And it is **database-enforced**: `on conflict (org_id, pack_id, pack_version, rule_id, subject_node_id) where status='open' do nothing` |
| ⛔ that `on conflict` has no matching partial unique index | ⛔⛔ **my single-line grep lied.** The index exists |
| ⛔ **two** overlapping partial unique indexes, the narrower one unreachable by `do nothing` | ⛔⛔ **also wrong**: `0034` **DROPS** `signals_one_open` and recreates it with the wider column set. My measurement flattened every migration into one string and **lost the order** — *a measurement that flattens history cannot see a replacement* |
| 16 of 23 reasoning unit classes named by no test | ✅ `tests/test_unit_roster.py` is `parametrize("unit", ALL_UNITS)` — protocol, identity, uniqueness, and ⛔ *"no unit publishes a metric another unit owns"*. **All 23 are exercised with no class name in the file** |
| `signal_suppression_log` — a refusal log nobody reads | ✅ read by `executive/explain.py`, which explains why a signal was suppressed |
| `discrepancies` · `reasoning_context_payloads` · `moments` · `card_events` … | ✅ each read by between two and seven modules |
| a silent reasoning unit | ✅ already receipted — *"every reasoning unit that says nothing is one we declared"* |

> ⛔ **Twenty retirements and no receipt is a result.** *A gate derived from an invented claim is a
> gate nobody reads* — and after `context/`'s receipt 42 and `platform/`'s 43, both derived from a
> module's own sentence, `reason/` had no sentence left to derive from.

---

## 1 · ⛔⛔ THE FINDING: the audit's own column was wrong 19 of 33 times

The report's second section listed modules of 100+ lines that **no test file names**. Across three
package audits it reported **33** entries. ⛔ **Nineteen were false**, and each false entry was a
candidate finding that died on inspection:

```
a @router.get handler has no Python caller and no test imports its module      api/
a table read through funnel.read_sweep — reached, its path written nowhere     platform/
⛔ test_unit_roster.py parametrises ALL_UNITS: 23 units run, no class named     reason/  x16
ConstraintReasoner = ConstraintUnit — an alias a ClassDef scan cannot see      reason/
```

### ⛔ Six repairs, and every one over-corrected

| # | repair | ⛔ what it then got wrong |
|---|---|---|
| 1 | count any **exported symbol** a test names | 33 → 14. Still missed parametrisation |
| 2 | follow symbol → **collection** | rescued 6 more. One hop short of `CORE_UNITS` |
| 3 | make the closure **transitive** | no change — the real blocker was elsewhere |
| 4 | read the module's **`__all__`** | rescued `constraint.py` correctly, and ⛔ **rescued `team/away.py`, which has no test for either public function**, via a generic `CAPABILITY` constant |
| 5 | a name is evidence only if **distinctive** | ⛔⛔ and `__all__` counted as a *definition*, so all 23 unit names looked ambiguous and the column **collapsed to zero findings** |
| 6 | read the test corpus from the **AST** | ⛔⛔ and then `context/`'s two hand-verified-as-reached modules came **back**, because `*_health.py` is reached by `importlib` over a **string** |

⛔⛔ **And the sharpest one: the guard written FOR this column named `deadline_situations` and
`team_away` in its own docstring**, in order to assert that `reason/team/away.py` has no test — so
a regex over the corpus counted those words and the module became *named by the test claiming it was
not*. **The observer altered the thing it measured.** Sixth time in one day that prose satisfied a
text-level measurement.

### ⛔ So it was deleted, not repaired a seventh time

> ⛔⛔ **A column whose error rate is unknown in BOTH directions is a column nobody should act on.**
> Naming is not coverage. It produced **zero** surviving findings in three audits and cost nineteen
> false leads, and each repair traded false positives for false negatives — which are worse,
> because a false negative **hides** a live module.

The section, its five helper functions and the per-file `tests` cell are **gone**. Each page now
carries the reasoning in place of the column, and
`tests/platform/test_the_coverage_report_does_not_mis_signal.py` fails if **any** of the six
heuristics returns — by name, one parametrised case each.

⛔ **Its one real contribution is kept as a finding rather than a table row**, verified by hand:
**`api/identity_routes.py` — five routes, 130 lines, mentioned by no test by any means.** That is
step `1.3b` of the plan. `approval_routes.py` is the same shape and is **already declared** in
`api_health.UNREACHED`, which is why only one is listed.

⛔ **And the report got faster**: the last heuristic re-parsed a package once per module and took
minutes; the generator now runs in **1.6 s**. *A report too slow to re-run is a report nobody
regenerates*, which is the whole reason it is generated.

---

## 2 · ⛔ A second guard, from a second drift found while writing the first

`00-INDEX.md`'s summary table is written **by hand** over **generated** pages. Adding
`platform/table_coverage.py` moved that package's line count, its unreceipted-table count and its
declared-silence count — and the index kept the old numbers, in the one table a reader looks at
first.

`tests/platform/test_the_audit_index_agrees_with_its_pages.py` now parses every row and compares it
with the page it links, parametrised per package, and fails if a row stops parsing — ⛔ *an unparsed
row is an unchecked row.* It also asserts the deleted column cannot return as **data** while the
index still **explains** its removal.

> ⛔ *A total is a measurement, not an addition of other people's measurements* — and an index over
> generated pages is exactly that addition. Third instance of this rule in two days.

---

## 3 · Doctrine

| Rule |
|---|
| ⛔⛔ **a column whose error rate is unknown in both directions is a column nobody should act on** |
| ⛔ **delete a measurement rather than repair it a seventh time** — and record why, or it gets rebuilt |
| ⛔ **a false negative is worse than a false positive** — one wastes a reading, the other hides a gap |
| ⛔⛔ **the observer can alter what it measures** — a guard's own docstring changed its subject's score |
| ⛔ **a measurement that flattens history cannot see a replacement** — the dropped index |
| ⛔ **a re-export is not a definition** · **a name that is not distinctive is not evidence** |
| ⛔ **a report too slow to re-run is a report nobody regenerates** |
| ⛔ **an index over generated pages is an addition, not a measurement** — so it is checked against them |
| **twenty retirements and no receipt is a result** |

---

## 4 · What `reason/` leaves open

| | |
|---|---|
| ⚠️ **29 unreceipted tables** | every derivable claim was already enforced or receipted. The list stays as the measurement; the next real claim will come from a module's own sentence, as 42 and 43 did |
| ⛔ **`api/identity_routes.py`** | five routes, no test — step `1.3b`, and the only thing the deleted column leaves behind |
| ⛔ **`reason/team/away.py`** | `deadline_situations` and `team_away` have engine callers and no test. ⛔ Surfaced by hand while the column was being disbelieved, and worth one test each |
| ⛔ **Atlas `L2-01`…`L2-12`** | nine claims still open, the largest remaining block — step `2.1`, and `L2-02`'s mover is now a read-only query on Harsh's page (`H8.5`) |
