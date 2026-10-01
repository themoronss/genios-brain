# Step 17 · Adversarial validation — findings

**Run:** 2026-09-24 · premise checked BEFORE any test was written
**Status:** 17-U1…U5, U7 **DONE** · **17-U6 BLOCKED on Harsh** · 127 tests · 1 row still OPEN

> **This step does not build a feature. It tries to break the other sixteen.**
> Its output is a list of things that are wrong, not a list of things that were shipped.

Full list: [`FAILURE-LOG.md`](../FAILURE-LOG.md).

---

## 1. ⛔ Premise check — the step's central criterion is self-contradictory

§8 asks that *"every one of them was **RED first**, for the stated reason"*. **That cannot be met,
and meeting it would mean the previous sixteen steps failed.**

This plan was written **before** they ran. Its own scenario table proves it:

| §4 says | Reality |
|---|---|
| S01 *"fails today because `In-Reply-To` never captured"* | **step 16 captured it** |
| S03 attendees flattened to emails | **step 13 fixed it** |
| S21/S22 the coverage gate | **steps 12 and 15 built it** |
| S02 *"bcc never captured"* | **impossible** — the provider does not supply it |

Making those red again means **un-fixing the product**, which §9 forbids in as many words.

### 1.1 · What replaces it, and why it is stronger

§2's technique 3 and §6's condition 2 already say the right thing:

> *"A fix is not accepted until technique 3 has been applied to it — neutralise the fix and confirm
> the probe goes red. A probe that passes with the fix removed proves nothing."*

**RED-first proves a test was failing.** A test can be red for reasons that have nothing to do with
the change. **Sensitivity proves the test fails precisely when this fix is removed and passes when
it is present** — which is the claim anybody actually wanted.

So every CLOSED scenario carries a mutation row, and `test_sensitivity.py` is the reason the other
six files are evidence rather than decoration.

---

## 2. ⛔ §7's purity grep reports its own guard rails as the violation

```bash
grep -rn "float(" genios_engine/capture/validate/     # 3 hits — ALL of them the float GUARD
```

Two are docstrings saying *"never `float()` on the way past"*; one is `require_no_float(...)`.

**A verify command that cries wolf on the protection is a verify command nobody runs twice.**
`test_invariants.py` excludes comments, docstrings and the guard's own name, so only a real
conversion can fire it. The clock and model greps return nothing and are correct as written.

---

## 3. What was built

| Unit | What |
|---|---|
| **17-U1** | 40 scenario rows across six files, each typed with its §3 failure class |
| **17-U2** | **27 mutation rows covering all sixteen steps**, + 1 on the harness — §5's actual deliverable |
| **17-U3** | distribution: the benchmark scores **20 of 38**, `calibrate` reports 0 unexplained |
| **17-U4** | technique 3 throughout, **including on the harness itself** |
| **17-U5** | ARCHITECTURE §10's invariants 1, 2, 4, 5 and 8 as walking tests |
| **17-U6** | ⛔ **BLOCKED** — §5 |
| **17-U7** | the failure log, with its own counts machine-checked |

### 3.1 · The totality guard, not a marker taxonomy

§6 condition 5 needs the class to be **machine-readable**. `--strict-markers` is on and twenty new
pytest markers would be a taxonomy nobody maintains, so this uses the repo's own idiom — the one
`PRECEDENCE`, `SIGNAL_TYPE_WEIGHT_BP` and `ANCHOR_FAMILIES` already use: a table with a row per
member and a check that **neither side has a hole.**

Without it, *"all 39 scenarios encoded"* is a claim in a document — **which is exactly the kind of
claim §1's table is made of.**

### 3.2 · Nine steps is not sixteen

The first draft's mutation pass covered steps 2, 4, 5, 8, 9, 12, 13, 15 and 16. §5 says *"for each
of the sixteen steps"*, and *"a step whose mutation kills nothing has decorative tests"* is a
**measurement, not a hope** — so rows for steps 1, 3, 6, 7, 10, 11 and 14 were added.

Step 11's row is the sharpest: it reproduces **the bug `calibrate` caught in the harness itself** —
checking *"does the type exist"* made 8 stranded objects read as present.

### 3.3 · Four mutations were badly aimed, and the harness refused to count them

`_dies` re-raises anything that is not an `AssertionError`, so a mutation that mangles a signature
cannot pass for sensitivity. Four did on the first run — a `TypeError` from a wrong constructor, a
`Failed` that `pytest.raises(Exception)` does not catch, and two mutations whose probe survived
because the mutation did not actually change the answer.

**Every one was a bad mutation, not a weak probe**, and the harness saying so is the harness
working. The meta-row `test_the_harness_reports_a_surviving_probe_as_a_failure` is technique 3
applied to technique 3.

---

## 4. The result

| Verdict | Rows |
|---|---|
| CLOSED — fixed by a step in this round, **sensitivity proven** | **29** |
| GUARD — always worked; proves sixteen steps cost nothing | 5 |
| CORPUS — logic proven, distribution is Harsh's | **4** |
| **OPEN** — still fails | **1** |
| IMPOSSIBLE — cannot be satisfied as written | 1 |

**The one OPEN row is `S01b`:** `pipeline.py` hands `reconstruct_thread` a list of **ONE** message,
so ALG-03's full RFC 5322 parent resolution has still never run on real data. Step 16 carried the
headers onto that `ThreadMessage`, so closing it is now **one caller change rather than two**.

Recorded as a **test that fails the day somebody changes that call** — a defect with an address,
not a TODO in a document.

---

## 5. ⛔ 17-U6 is blocked, and it is one environment variable

```
12875 passed · 14 failed (all pre-existing) · 995 skipped
                                              └── 991 say "GENIOS_TEST_DATABASE_URL not set"
                                                  618 tests carry the `pg` marker
```

§2 records exactly what is being missed: the hermetic lane skipped ~800 tests, and a scratch DB
surfaced **12 failures the green suite never showed — 10 of them from a dirty scratch DB**, which
is why the run must **drop and recreate first**.

**A skip is not a pass.** This criterion stays unticked. Harsh item 1, open since step 1.

---

## 6. Test result

```
FULL SUITE      12875 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 17: 12748 passed · 14 failed
```

**Zero regressions, +127 tests.** No production code changed — this step writes tests and reads
code. No migration, no model call, no prompt change, no vocabulary change.

---

## 7. What this step does NOT do

* **It does not prove Layer 1 is correct.** It proves 29 specific behaviours fail when their fix is
  removed. That is a much smaller claim and the only one the evidence supports.
* **It does not run on real Postgres.** 618 tests are skipped, not passing — §5.
* **It does not measure a distribution over the corpus.** Four scenarios wait on it, and two of
  them (S29, S33) decide whether step 10 should exist at all.
* **It does not close S01b.** It gives it an address and a failing test.
* **It quotes nothing externally.** §9: *"N=1, and this founder's outbound volume is unusually
  small, which flatters sent-side results."*
