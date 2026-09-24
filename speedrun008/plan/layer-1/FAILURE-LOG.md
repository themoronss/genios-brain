# Layer 1 · failure log

**17-U7.** Every miss gets a **class**, a **scenario id**, and the **step that owns it**.
Generated against `tests/scenarios/_registry.py`, which is machine-checked both ways — a scenario
with no test and a test with no class both fail the suite.

> **This step does not build a feature. It tries to break the other sixteen.**
> Its output is a list of things that are wrong, not a list of things that were shipped.

**Run:** 2026-09-24 · 40 rows (39 from §4, plus `S01b`) · 127 tests · 27 mutation rows + 1 on the harness

**These counts are machine-checked** against the registry by
`test_the_failure_log_counts_match_the_registry` — a hand-maintained scoreboard that
drifts from its source is the exact failure mode §1's table is made of, and this one
already drifted once while being written.

---

## The one-screen version

| Verdict | Rows | What it means |
|---|---|---|
| **CLOSED** | **29** | a step in this round fixed it — **sensitivity proven**, not merely green |
| **GUARD** | 5 | always worked; proves sixteen steps cost nothing |
| **CORPUS** | **4** | logic proven, distribution needs the pilot corpus — **Harsh** |
| **OPEN** | **1** | still fails · `S01b` |
| **IMPOSSIBLE** | 1 | cannot be satisfied as written · `S02` |

---

## ⛔ OPEN — the one thing still wrong

| id | class | What | Owner |
|---|---|---|---|
| **S01b** | **F05** | `pipeline.py` hands `reconstruct_thread` a list of **ONE** message, so ALG-03's full RFC 5322 parent resolution **has still never run on real data** | 16 |

§1 of step 17 says `assemble_chain` *"always falls back to chronology"*. **It never gets that far.**
The unit is correct — `S01`'s branch test passes on its first run and proves it — and it is handed a
single-element list, so there is no chain to build, branched or straight.

Step 16 captured `In-Reply-To`/`References` and **carried them onto that `ThreadMessage`**, so
closing this is now **one caller change rather than two**. Feeding it the sibling messages needs an
API call or a store read, which is a different unit.

Recorded as a **test that fails the day someone changes the call** — a defect with an address, not a
TODO in a document.

---

## ⛔ IMPOSSIBLE — and the reason is the point

| id | class | What | Owner |
|---|---|---|---|
| **S02** | F04/F17 | *"a bcc'd recipient is captured and `visibility_rules` restricts who sees it"* | 16 |

**Gmail's API does not supply bcc**, and on a message we *received* it is invisible by definition —
that is what bcc means.

This has now cost a full premise check **twice** (step 13, then step 16). `connectors/manifest.py`
carries the row with the reason written down so it is never re-opened as an oversight. Step 13's
`bcc_recipients` field exists and is empty everywhere, so the day a source offers one, nothing
downstream changes.

The half of S02 that **is** real — that `visibility_rules` governs whatever recipient set it is
given — is asserted separately and passes.

---

## CORPUS — four rows whose logic is proven and whose numbers are Harsh's

| id | class | The question only the corpus answers | Harsh item |
|---|---|---|---|
| **S15** | F09 | does any pilot event carry **two** signals with **two** extractions? | 1 |
| **S17** | F09 | does a composed situation carry non-`None` domains, confidence, `occurred_at`? | 1, 3 |
| **S29** | F13 | **is the REVIEW population non-empty at all?** | 15 |
| **S33** | F13 | the 68 pilot floor-refusals → a count that is **neither 0 nor 68** | 15 |

**S29 and S33 decide whether step 10 should exist.** Step 10 gated itself: `PublicationOutcome`
stays closed at three outcomes until a real count says a fourth is worth building. **0** would mean
the floor refuses nothing worth a look; **68** would mean the floor is simply wrong.

---

## The twenty classes, and where they landed

| Class | Failure | Rows | Status |
|---|---|---|---|
| F01 | ingestion omission | S07 | closed |
| F02 | pagination — the cursor did not exhaust | S04 | closed |
| F03 | scope mismatch | — | not exercised without the corpus |
| **F04** | **field omission** | S01, S02, S03 | 2 closed · **1 impossible** |
| **F05** | **structural extraction failure** | S01, **S01b** | **1 OPEN** |
| F06 | entity ambiguity — merged or split | S35, S36 | closed |
| F07 | intent interpretation | — | step 7; no §4 row |
| F08 | category interpretation | S27 | closed |
| F09 | relationship inference | S15, S16, S17 | 1 closed · 2 corpus |
| F10 | temporal interpretation | S23 | closed |
| F11 | contradiction | S26 | closed |
| F12 | evidence grounding | S10, S13, S14 | closed |
| F13 | qualification **false negative** | S28, S29, S33 | 1 closed · 2 corpus |
| F14 | qualification **false positive** | S30, S34 | closed |
| F15 | lifecycle transition | S19, S20, S23 | closed |
| F16 | cross-source join | S37, S38, S39 | closed |
| F17 | permission / visibility | S02 | impossible |
| F18 | dedup semantic collapse | S06, S24 | closed |
| F19 | coverage misreporting | S18 | closed |
| **F20** | **`unknown` → `false`/`true`** | S08, S09, **S21, S22, S25** | **all closed, all sensitivity-proven** |

**F20 is the one §3 says to watch hardest** — *"the failure that loses trust rather than quality"*.
All five rows are closed, and each one dies under mutation: lower step 12's gate to zero and S21
fails; treat a missing coverage figure as full and S22 fails; empty `_NEGATIVE_STATES` and the
contract stops refusing an unproven negative.

---

## ⛔ 17-U6 is BLOCKED, and it is one environment variable

§8: *"the full suite run on a **freshly recreated** Postgres, **0 skips**."*

```
12865 passed · 14 failed (all pre-existing) · 995 skipped
                                              └── 991 say "GENIOS_TEST_DATABASE_URL not set"
                                                  618 tests carry the `pg` marker
```

**991 of 995 skips are one missing URL.** The four that are not: a missing `docx` module, an
unwired internal-auth harness, an empty parameter set, and one declared migration exception.

**A skip is not a pass**, and this criterion cannot be ticked. §2 records exactly what is being
missed: the hermetic lane skipped ~800 tests, and a scratch DB surfaced **12 failures the green
suite never showed — 10 of them from a dirty scratch DB**, which is why the command must **drop and
recreate before every full run**.

This is Harsh item 1, and it has been the single biggest unblock since step 1.

---

## What the mutation pass proved — 28 rows, covering all sixteen steps

⛔ **Three of them are regressions that ACTUALLY HAPPENED in this round**, reproduced so they
cannot happen twice:

| Mutation | Real? | Probe that dies |
|---|---|---|
| directness `UNKNOWN` 10000 → 9000 | ✅ **shipped for half an hour, broke 8 tests** | S26 neutrality |
| `meeting_kind` cohort rung moved below the domain check | ✅ **step 13 built it wrong first** | S38 cohort |
| ALG-08 stops walking `roles`/`availability`/`questions` | ✅ **the step-4 defect** | S13 evidence |
| step 12's gate lowered to 0 | — | **S21** |
| a missing coverage figure read as full | — | **S22** |
| `_NEGATIVE_STATES` emptied | — | **S22** second lock |
| unknown denominator defaults to 10000 | — | S18 (Gemini's 18-of-18) |
| failure markers matched before delay markers | — | S08 (Surge's 47 hours) |
| a bounce's unreadable address filled from the sender | — | S10 |
| the undecided rules added to the refusing set | — | S31 (31% of a young tenant) |
| `ranked[:budget]` with a negative budget | — | S32 |
| attendees flattened to addresses | — | S03/S37 |
| `to`/`cc` flattened again | — | S39 |
| a failing span grade passes `verified` through | — | S14 |
| directness multiplier allowed above 10000 | — | S26 Rule 11 |
| the connector stops stating a thread position | — | S01 |
| `assemble_chain` blinded to its headers | — | S01 branch |
| a drain reports complete AND budget-stopped | — | S04/S18 |
| **`_dies` itself, fed a probe that survives** | — | **the harness** |

The last row is technique 3 applied to technique 3. Without it every row above could be decoration.

---

## Two corrections this step made to its own plan

**1 · §8's "every one of them was RED first" cannot be met, and meeting it would mean the previous
sixteen steps failed.** The plan was written before they ran: `S01`'s *"fails today because
`In-Reply-To` never captured"* was true when written and step 16 closed it; `S03` was closed by step
13; `S21`/`S22` are step 12's and step 15's. Making them red would mean un-fixing the product, which
§9 forbids in as many words.

**Technique 3 replaces it, and is strictly stronger.** RED-first proves a test was failing — which
can be true for reasons unrelated to the change. Sensitivity proves the test fails **precisely when
this fix is removed and passes when it is present**.

**2 · §7's purity grep reports its own guard rails as violations.**

```bash
grep -rn "float(" genios_engine/capture/validate/     # 3 hits, all of them the FLOAT GUARD
```

Two are docstrings saying *"never `float()` on the way past"* and one is `require_no_float(...)`.
A verify command that cries wolf on the protection is a verify command nobody runs twice.
`tests/scenarios/test_invariants.py` excludes prose and the guard's own name, so only a real
conversion can fire it. The other two greps (clocks, models) return nothing and are correct as
written.
