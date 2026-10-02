# S9 — DONE · the paperwork, and a finding of mine refuted by its own gate

**Unit:** `M14.C2.S9` · **Owner:** me · ✅ **2026-10-02** · **+10 tests · 2/2 mutations caught**
**Closes:** `F16` the status counts · `F17` the mover convention · `F18` `wipe_org_data` ·
`F22`/`F32` the 104 guards

---

## 1 · ⛔⛔ `F17` IS REFUTED — and it was my own false finding

`03-FINDINGS` §F17 recorded *"a mover-convention deviation the guard cannot see"*:
`feedback_health.py` uses **`MOVES WITH`** where the house convention is `MOVES WHEN`, and
`test_every_entry_carries_a_reason_and_a_mover` only requires *"at least two parts"*, so it passes.

⛔ **The plan's gate for this step was: *"measure the distribution BEFORE touching either side."***
Measured:

```
MOVES WHEN   115 occurrences
MOVES WITH    29 occurrences, across NINE of the thirteen declaration modules
```

| module | WHEN | WITH |
|---|---|---|
| `context/context_health.py` | 13 | **8** |
| `platform/platform_health.py` | 15 | **7** |
| `feedback/feedback_health.py` | 9 | **3** |
| `capture/` · `contracts/` · `reason/` · `deliver/` · `packs/` · `api/` | 1–19 | **1–2 each** |

> ⛔ **`MOVES WITH` is a CONVENTION, not a deviation**, and it means something `MOVES WHEN` cannot:
> *"this entry moves when its PAIR moves"* — two guards over one map from opposite sides, where
> naming a separate condition would be a lie. **The existing guard is right to accept both.**

⛔ **The gate stopped me from tightening a guard onto correct code** — *do not weaken a verify to
make it pass, and do not tighten one to make it fail.* Seventh time in this programme that
verifying a suspicion before writing it prevented a false finding.

## 2 · ⛔ But a THIRD form did exist, and now cannot

`context_health.py` carried **`MOVES ON A SEAM DECISION`**. Normalised to
`MOVES WHEN SOMEBODY TAKES THE SEAM DECISION` — a wording change, not a meaning change — so the
vocabulary is exactly two forms.

```python
MOVER_FORMS = ("MOVES WHEN", "MOVES WITH")
```

⛔ **And the new guard does NOT demand a mover**, which is the whole care in it. Three tables
correctly have none: `executive/PULL_ONLY` and `deliver/PULL_ONLY` are keyed `(route, why)`, and
`feedback/target_policy.UNIT_TARGETS` is `(target, why)` — its movers live in `DELEGATED` and
`DURABLE_FROM_A_MEASUREMENT` beside it. ⛔ **Demanding one everywhere would fail on all three —
exactly the mistake the guard above it records making** when it demanded two long strings and broke
on `PULL_ONLY`.

So the assertion is conditional: *where* a string says `MOVES`, it must use a recognised form.
**+10 tests**, one per declaration module.

### ⛔ The mutation that matters

```
M1 · a THIRD mover form comes back                                    ✅ CAUGHT
M2 · ⛔ the guard is "fixed" the way F17 suggested — MOVES WITH rejected  ✅ CAUGHT
```

⛔ **`M2` is the refutation, executed.** Narrowing `MOVER_FORMS` to `("MOVES WHEN",)` — the "fix"
`F17` implied — fails on the **29 correct entries** in nine modules. *The finding was wrong and the
guard now proves it.*

## 3 · ⛔ The 104 absence guards: measured, declared, and deliberately NOT converted

`F22` and `F32` recorded that three guards broke on correct code this session, all asserting a
forbidden string was absent from source — because **the fix that removed the forbidden thing also
documented it.**

```
584   assert "..." not in <anything>
104   assert "..." not in src|code|source|text|blob|content|body    ← source-text guards
       78 CODE-shaped · 13 SQL-shaped · 13 that LOOK like prose, most of them code
          fragments (`import calendar`, `if done or affected:`, `raise AuthoringIntegrityError`)
```

⛔ **"104 broken" would be an overstatement and so would "0".** Every one is *structurally*
vulnerable; which are at risk **today** is the question.

### ⛔ And that question is not answerable statically — measured, not assumed

I built a resolver to find each guard's target file and check the phrase against **that** file's own
prose. ⛔ **It resolved 1 of 104.** The dominant form is `inspect.getsource(<an imported function>)`,
and a function's defining module can only be found by **importing** it.

> ⛔ **A resolver that answers for 1 of 104 answers nothing** — the fourth name-shaped resolver in
> this session to produce a confident wrong answer, and the first I caught by checking its coverage
> instead of its output. An earlier version reported *"0 at risk"* from that 1-of-104 sample, which
> would have been the most reassuring wrong number in the programme.

### So: the rule, not the rewrite

⛔ **78 mechanical rewrites with no measured defect behind them is speculative work**, and each
conversion is a chance to change what a guard means. The three that broke are fixed and **pinned
with regression tests**. The rule is now written where the next author will look —
**`tests/README.md`**, a new section:

| The claim is about | The check |
|---|---|
| **PROSE** | ⛔ **attribution, not presence** — allow the phrase, require a marker (`CORRECTED`, `used to read`) within a few lines. A **relapse** adds an unmarked occurrence and fails |
| **CODE** | ⛔ **the AST** — an attribution window would *pass* and is the **wrong tool**: the question is not *"who said this"* but *"does any unit read this attribute"*. Walk for the attribute **and** for `getattr(obj, "name", …)` |
| **a SQL construct** | a text check is usually fine — `insert into` rarely appears in prose that is not quoting a query. Lowest risk, still worth a comment saying so |

## 4 · `F18` · `scripts/wipe_org_data.py` — a real fix with an invented reason

The comment said the old exclusion *"read `information_schema.views`, which omits MATERIALIZED views
— `counterfactual_ledger` (0072) slipped through."*

⛔ `0072` is `create or replace **VIEW**` — a **plain** view, deliberately, and the migration says
why: *"materialising a copy would be a second thing to keep honest."* **A plain view IS listed in
`information_schema.views`**, so an exclusion built from that table would have excluded it.

⛔ **And I did not invent a second cause.** Whatever actually let it through is not recoverable from
this file; guessing would repeat the first mistake. The comment now says that, and says why the fix
is right **for a reason that does not depend on the story**: `table_type='BASE TABLE'` excludes
plain views, materialised views, foreign tables and anything a future PostgreSQL adds. **A positive
selection cannot be out of date.**

> ⛔ *A stale comment reads as a measurement* — and this one explained a real fix with an invented
> reason, **the harder kind to notice**, because the code around it is correct.

## 5 · `F16` · three test counts, three meanings, none wrong when written

```
00-START-HERE.md        "53 tests"   ← ONE file, on the day M14 shipped
01-CROSSCHECK addendum  "87 tests"   ← a different scope, 2026-10-01
measured by S5          60 passed, 27 skipped
measured by S9          243 passed, 27 skipped
```

⛔ **The fix is the date, not the number.** Both are now dated, and neither page carries a total:
the command is the answer — `.venv/bin/pytest tests/feedback -q -rs`, ⛔ **with `-rs` not
optional**, because the 27 skips are two files that need real Postgres, they are `H7`, and *a skip
is not a pass.*

> ⛔ **A hardcoded count in a document is wrong the next day.** A dated one is a record rather than
> a claim about today.

## 6 · Verify

```bash
.venv/bin/pytest tests/platform/test_every_package_says_what_it_does_not_call.py -q   # 68 passed
.venv/bin/pytest tests/scripts tests/context -q
.venv/bin/pytest -q                                                            # the FULL suite
grep -rhoE "MOVES [A-Z]+" genios_engine/ | sort | uniq -c        # exactly two forms
```

## 7 · Doctrine

| Rule |
|---|
| ⛔ **measure the distribution before calling one instance a deviation** — `F17` was my own false finding, refuted by its own gate |
| ⛔ **a resolver that answers for 1 of 104 answers nothing** — check a resolver's COVERAGE, not just its output |
| ⛔ **a claim about prose needs attribution; a claim about code needs the AST** — and an attribution window on a code claim is the wrong tool, not a weaker one |
| ⛔ **a hardcoded count in a document is wrong the next day** — date it, or point at the command |
| ⛔ **a real fix with an invented reason is the harder kind of stale comment to notice** |
| ⛔ **do not invent a second cause to replace a wrong one** — say it is not recoverable |
| **a guard may reject a third form without demanding a first** — three tables correctly have no mover |
| **the rule, not the rewrite** — 78 mechanical conversions with no measured defect is speculative work |
