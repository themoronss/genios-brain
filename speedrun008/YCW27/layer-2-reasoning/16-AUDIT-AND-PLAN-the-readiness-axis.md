# 16 · AUDIT AND PLAN — the readiness axis (Atlas cell L2-07)

> **Date** 2026-10-01 · **Layer** YCW27 L2 (Atlas L4 Reasoning) · **Unlocked by** decision #1 = A
> **Atlas cell** L2-07 — *"role/source-readiness completeness is not part of the blocking vector"*
> **Status** AUDIT COMPLETE · **U1 BUILT · U2 BUILT** · U3 blocked on H1 · U4 is Rohit's call

---

## PART 1 · The audit, and what it found

Decision #1 closed with option **A** (keep the code's six axes, correct the Atlas) and
`02-DECISIONS.md:162` recorded that the Atlas's substantive point **survives** that decision:

> That is true, it is not solved by any existing `authority_bp`, and it needs its own axis
> computed from `capture/coverage`'s readiness model.

This audit tested that sentence against the code and the production database rather than
inheriting it. **It holds, and it now has a number.**

### 1.1 · The claim is TRUE, and here is the trace that proves it

The L2 blocking vector is `contracts/situation.ConfidenceVector` — six nullable axes and
`overall_bp`, bounded by the weakest axis named in `composed_from`. Its `coverage_bp` axis is
the one that *sounds* like readiness. It is not.

    coverage_bp  <--  context_situations.coverage                    (the column)
                 <--  situations.py:641  coverage_score(present_fields, expected)
                 ==   how many EXPECTED FIELDS this situation has, as a percentage

`coverage_score`'s own docstring says what it measures: *"How complete the picture is"* — a close
date, a stage, an owner. **Field completeness on one situation.** It has nothing to say about
whether the domain's required capabilities are connected at all.

Source readiness lives somewhere else entirely, and it stops before it reaches L2:

    compute_coverage(domain, connected)      capture/coverage/model.py
      -> coverage_ready: bool                 every REQUIRED capability is `fresh`
      -> readiness: 5 predicates              can_evaluate_no_reply, can_evaluate_no_meeting,
                                              can_evaluate_payment_state, can_evaluate_usage_drop,
                                              has_company_canon
      -> missing_required: list[str]          WHICH capability is absent
            |
            v
    capture/esqe/publisher.py:413-415         coverage_bp=(10000 if coverage_ready else 0)
            |
            v
    QualifiedEnterpriseSignal.confidence_vector    <-- a DIFFERENT vector: FOUR components
                                                       (evidence, expertise, freshness, coverage)
            |
            X   STOPS HERE. Nothing carries it into context_situations.coverage.

So the word `coverage` means **source readiness** in L1's four-component vector and **field
completeness** in L2's six-axis vector, and only the second one blocks. The Atlas is right.

### 1.2 · ⛔ The number: 310 Admin situations, on a domain the model says is not ready

    source_coverage                 (production, read-only)
      admin        coverage_ready = FALSE   x3 orgs   required [finance, communication]
      sales        coverage_ready = FALSE   x3 orgs   required [communication, crm]
      support      coverage_ready = FALSE   x3 orgs   required [support_desk, communication]
      fundraising  coverage_ready = TRUE    x3 orgs   required [communication]

      connected and fresh, all 3 orgs:  {calendar: fresh, communication: fresh}
      ⛔ `finance` is NOT connected -> admin is not ready, and has never been

    context_situations by domain
      admin         310   (103 of them carry coverage = -1, COVERAGE_UNKNOWN)
      support        73
      sales          61
      fundraising    11
      general         4
      ----             
      total         459   (coverage: 0 null · 103 unknown · 356 scored)

**Admin is the only domain in scope** (`admin-domain-only`), it is **67% of every stored
situation**, it is **not coverage-ready in any org**, and **the blocking vector cannot see that.**
Every one of the 103 COVERAGE_UNKNOWN situations is an Admin one.

That is cell L2-07, measured.

### 1.3 · Findings that are NOT this unit

| | Finding | Severity | Action |
|---|---|---|---|
| F-1 | **The axes are declared THREE times and only two are constants.** `contracts/situation.py:126` and `contracts/situation_evidence.py:162` are two named `CONFIDENCE_AXES` tuples with identical contents; `context/situation_publisher.py:161-162` **hardcodes the six names inline**. A seventh axis added to the constants would be **silently dropped** by the publisher. | 🟠 latent | **inside this unit** — it is the step that proves whether the three agree |
| F-2 | `compute_coverage` gates on the **constant** `PACK_REQUIREMENTS` while `declaration.py:163` iterates the **function** `pack_requirements()`. An authored corpus is therefore asked about and then answered `unknown_domain` with every readiness predicate FALSE — the exact failure `_authored_requirements()`'s own docstring says it exists to prevent. **MEASURED: zero authored domains exist today, so the divergence is latent, not live. Nothing is mis-assessed right now.** It fires on the first authored corpus. | 🟡 latent · 0 rows | **new unit, not this one** · L1 |
| F-3 | `publisher.py:415` reads `10000 if coverage_ready else 0`, and `coverage_ready` is a **tri-state** — `declaration.py:5` records that it was `None` on 100% of events for a period. `None` becomes **0**, which is "we looked and it was terrible" standing in for "we never looked" — the one error `AXIS_UNKNOWN_BP = -1` and `COVERAGE_UNKNOWN = -1` exist to prevent. | 🟠 | **new unit, not this one** · L1 |

> Adjacent findings get their own unit, never a silent fix. F-2 and F-3 are logged here and
> belong to L1; neither blocks this plan.

---

## PART 2 · The plan — four units, and only the first two are unblocked

### ⛔ The two hard constraints that set the shape

**C-1 · The behaviour change is on 67% of production.** A seventh axis in `composed_from` binds
`overall_bp` through the weakest-axis law. Admin has 1 of 2 required capabilities fresh. If
readiness composes, **every one of the 310 Admin situations is capped at that number**. That is
not a refactor; it is a re-scoring of two thirds of the corpus. It must be **measured before it is
switched on**, which is why storing and composing are different units.

**C-2 · The migration is behind five unapplied ones.** The newest file is `0190_card_lane.sql`;
`0186`–`0190` have **never run in production** and `0190` breaks the next card write until it does
(Harsh's H1). A readiness column is `0191`, so **U3 cannot be verified in production until H1
lands.** U1 and U2 do not touch the database and are unblocked today.

### U1 · `readiness_score()` — the pure function. ✅ **BUILT**

One function in `context/situations.py`, beside the six that are already there, same shape as
them: keyword-only, no clock, no connection, returns `(score, missing)`.

    readiness_score(*, required: Sequence[str], freshness: Mapping[str, str])
        -> tuple[int, list[str]]

- `required` empty → `COVERAGE_UNKNOWN`, exactly as `coverage_score` does for `not expected`.
  An unregistered domain grants no permissions and is **not** scored 0 — F-3 is the error this
  refuses to repeat.
- otherwise → `round(100 * fresh / len(required))`, plus the names of what is missing.
- **Admin today: 1 of 2 → 50.** ⛔ Which in basis points is **5000**, the forbidden neutral
  default (`reason/decision_maker.py:181`). A *measured* 5000 is legitimate and a *substituted*
  one is the bug — but on a stored column the two are indistinguishable six months later. So the
  function returns the **missing list** as well, and U3 stores it, so every 5000 carries its own
  numerator and denominator. That is `composed_from`'s discipline applied one field down.

**Verify:** `pytest tests/context/test_readiness_score.py -q` — the unknown branch, the all-fresh
branch, the half branch returning exactly 5000 **with** its receipt, and a stale-not-missing case.

### U2 · the seventh axis, **declared and not composed**. ✅ **BUILT**

`readiness_bp: int | None = None` on `ConfidenceVector`; `readiness: int` on
`SituationConfidenceVector`; both `CONFIDENCE_AXES` tuples go to seven.

⛔ **And F-1's third copy** — `situation_publisher.py:161-162`'s hardcoded tuple — **is replaced by
the constant in this unit.** Not as a tidy-up: it is the assertion. If the publisher keeps its own
list, the axis exists on the contract and is `None` on every published situation, and the unit
would report itself as working while carrying nothing.

The axis is **added and left out of `composed_from`.** Nothing is capped. `overall_bp` does not
move. This is deliberate: the law stays satisfied by the six that are already there, the seventh
becomes readable, and nothing re-scores until U4 says so.

**Verify:** the existing pins move by hand, each with its reason written in the test —
`test_l2_contracts.py:985` (`len(CONFIDENCE_AXES) == 6`),
`test_situation_publisher.py:910` (`CONFIDENCE_AXES[:5]`), `test_l2_must_not_regress.py:485`.
Then the full suite: **14,585 passed, 0 failed** is the floor, and no number may fall.

### U3 · the column and the writer. **BLOCKED on Harsh's H1**

`0191_situation_readiness.sql` — `confidence_readiness int` plus `readiness_missing text[]` on
`context_situations`; `situation_bso.py:1328` reads `readiness=axis("confidence_readiness")`; the
sweep writes it from U1 against that org's `source_coverage` row.

**Verify:** the receipt. A 31st claim in `platform/receipts.py` — *"every situation on an
assessed domain carries a readiness axis"* — red until the sweep runs, which is the honest state.

### U4 · composition. **BLOCKED on U3's measurement, and it is Rohit's call, not mine**

Only after U3 has stored the number for a full sweep can the question be asked with data:
*what does `overall_bp` become on 310 Admin situations if readiness joins `composed_from`?*

I will produce that table. **I will not flip it.** Capping two thirds of the corpus at a number
is a product decision about what the product should refuse to say, and the honest answer may well
be "connect `finance` first" rather than "re-score everything".

---

## PART 3 · What is and is not true, in one block

    TRUE   · L2-07 is a real cell. Source readiness is absent from the L2 blocking vector.
    TRUE   · The readiness data exists, is correct, and is already computed (`compute_coverage`).
    TRUE   · It reaches L1's four-component vector as a BINARY and stops there.
    TRUE   · Admin — the only domain in scope — is `coverage_ready = FALSE` in all 3 orgs,
             because `finance` is not connected, and 310 situations (67%) sit on it.
    FALSE  · "coverage_bp already covers this." It measures field completeness, not sources.
    FALSE  · "authority_bp could serve." It exists three times and means three things, none of
             them situation readiness (decision #1, and it is closed).
    LATENT · F-2, zero rows affected today; F-3, a tri-state collapsed to a binary. Both L1,
             both their own units, neither blocking.
    OPEN   · whether readiness should COMPOSE. Not answerable before U3. Rohit's, not mine.

**Nothing below U2 can be verified until `0186`–`0190` are applied.** That is H1, and it is the
same blocker that breaks the next card write.


---

## PART 4 · WHAT WAS BUILT, 2026-10-01 — and the one place the plan was wrong

### U1 ✅ `context/situations.readiness_score()` · 8 tests · 3 mutations proved

    admin (finance missing)      ->   50   missing=['finance (not connected)']
    fundraising (ready)          ->  100   missing=[]
    unregistered domain          ->   -1   COVERAGE_UNKNOWN, never 0
    all required stale           ->    0   ['communication (stale)', 'finance (stale)']
    sales (crm missing)          ->   50   missing=['crm (not connected)']

Stale and never-connected cost the same SCORE and read as different PROSE, because only one of
them has something to reconnect. The three mutations proved: the unknown branch returning 0, the
missing list emptied, and stale counted as fresh — each caught by the test written for it.

### U2 ✅ the seventh axis · 6 tests · mutation proved

`contracts/situation.CONFIDENCE_AXES` -> 7 · `ConfidenceVector.readiness_bp: int | None = None` ·
`situations.Confidence.readiness` · `situation_publisher._confidence` reads the constant.

    score_situation(... no readiness row ...)   overall=100  readiness=-1  known=False
    score_situation(... admin's real row ...)   overall=100  readiness=50  missing=[...]
                                                ^^^^^^^^^^^ IDENTICAL

### ⛔ WHERE THE PLAN WAS WRONG, and the test that caught it

PART 2's U2 said "the seventh axis on the two contracts". **That was wrong in two ways, and the
repo's own tests found both before anything shipped:**

**1 · The plan forgot `situations.Confidence` entirely.** `tests/contracts/test_l2_contracts.py::
test_the_six_axes_are_the_six_that_exist` pins `CONFIDENCE_AXES` against the fields of the
dataclass the scorer returns, and says why: *"an axis the contract names but the scorer does not
produce is that collapse one field at a time."* The plan named two contracts and the real answer
was three places — the constant, the model, and the scorer's own dataclass.

**2 · The plan would have broken the group gate.** It said to add the axis to
`contracts/situation_evidence.SituationConfidenceVector` as well. That object's `complete`
property **is** the group gate's row — *"confidence vector axes present — all 6"* — taken as a
count (`situation_bso.py:1663`). A seventh axis there, before `confidence_readiness` exists as a
column, flips `complete` to False on every situation **for a reason nobody can look up**, because
there is no column to inspect. The storage vector was therefore left at six, and the divergence
asserted as an exact set difference.

> ⛔ **A gate whose criterion names a count is a contract with the number.** Changing the count
> is changing the contract, and it may only be done in the unit that makes the new count
> reachable.

### F-1 was the real content of U2

`context/situation_publisher.py:161` held a **hand-written tuple** of the six axis names — a third
copy of a vocabulary that already existed twice as a constant. A seventh axis added to the
contract would have been read by nothing there, published as `None` on every situation, and
**reported as working by every test that only asked the contract.**

The fix is one line and the test is an AST walk, not a grep. It was mutation-proved by putting
back a hardcoded tuple **with the correct seven names** — and the test still caught it, because it
asserts on the structure (`ast.Tuple` of string constants inside `_confidence`) and not on the
text. The blunt-grep family, avoided on purpose.

### What U3 needs, written down now while it is fresh

    0191_situation_readiness.sql
      alter table context_situations
        add column confidence_readiness int,          -- percent, COVERAGE_UNKNOWN = -1
        add column readiness_missing    text[];       -- the numerator's evidence

    situation_bso.py:1328      readiness=axis("confidence_readiness")
    situation_evidence.py      CONFIDENCE_AXES -> 7, SituationConfidenceVector.readiness
                               ⛔ AND the group gate's row moves from "all 6" to "all 7"
                                  IN THIS UNIT, because this is the unit that makes 7 reachable
    receipts.py                a 31st claim: "every situation on an assessed domain carries a
                               readiness axis" — red until the sweep runs, which is honest
    the sweep                  pass `required_capabilities` + `capability_freshness` from the
                               tenant's `source_coverage` row into `score_situation`

⛔ **U3 cannot be verified in production until `0186`–`0190` are applied.** That is Harsh's H1, and
it is the same blocker that breaks the next card write.
