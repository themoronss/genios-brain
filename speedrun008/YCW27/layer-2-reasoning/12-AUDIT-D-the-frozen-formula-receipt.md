# AUDIT D · the frozen-formula receipt — a gate that can never go green

Measured against production 2026-10-01, read-only (`set transaction read only`), model off.
This is the tenth finding, and the one never examined. A, B and C covered nine.

---

## PART 0 · WHAT THE RECEIPT CLAIMS

`platform/receipts.py:391`, layer L4:

    title  : "the score components are measured, not placeholders"
    query  : select count(*) from reasoning_candidates where
             score_components->>'impact' = '5000' and score_components->>'risk' = '5000'
             and score_components->>'effort' = '5000'
    expect : n == 0
    detail : "four of five components frozen at 5000 means every L4 unit adjustment is a no-op"

It **FAILS**, at 59.

---

## PART 1 · THE FIRST READING WAS WRONG, AND IS RECORDED RATHER THAN DELETED

I opened this expecting the shape found in C: a receipt whose detail does not match its own
query. The first measurement supported that — each component sampled on its own:

    component          present   =5000  frozen share
    effort                3000     288            9%
    impact                3000      95            3%
    risk                  3000      15            0%
    urgency               3000      52            1%
    success               3000      57            1%
    formula_utility       2994       9            0%
    llm_utility           2938       2            0%
    importance            2221       0            0%
    priority_override     2221       0            0%

Read alone, that says *nothing is frozen* and the receipt is overstated. **That reading was
wrong**, and the error was the same one the session has now made a rule about: a count without
its dimension is not a measurement. Measuring each component *independently* cannot see a
defect that is defined by components coinciding. The conjunction is the dimension.

---

## PART 2 · THE CONJUNCTION — A PERFECT CORRELATION, WHICH IS NOT CHANCE

    risk = 5000, on its own                                    59 rows
    impact = 5000 and risk = 5000 and effort = 5000             59 rows   ⛔ identical

Every single row where `risk` is 5000 also has `impact` and `effort` at 5000. Three nominally
independent integers never once land on 5000 apart. Widening the conjunction:

    3-way  impact+risk+effort                                  59
    4-way  impact+risk+effort+success                          59
    5-way  impact+risk+effort+success+urgency                  53

So the true shape is **worse than the detail says**. The detail claims *four of five*; for
**53 of the 59 rows all five components are 5000** — the entire ranking formula was one
constant. For the remaining 6, four of five. "Four of five" is the defect's floor, not its
ceiling.

`guards.CANDIDATE_COMPONENTS` is a closed set of exactly five — `impact, success, urgency,
effort, risk` — so "four of five" names the right denominator. The detail is accurate about
the shape. It is the *consequence clause* that is false, and PART 4 shows why.

One of the 59, in full:

    play_id=reply  disposition=eligible  initial=5500  final=5500
      effort 5000   impact 5000   risk 5000   success 5000   urgency 8700

---

## PART 3 · THE DEFECT IS REAL, AND THE CODEBASE ALREADY NAMED IT

5000 is not an innocent midpoint. `reason/decision_maker.py:181` states the doctrine:

> *"Never substitute 5000. A neutral default is exactly the bug that made every card score 50."*

And the cause is documented at the two seams that produce candidates:

* `reason/adapters/legacy_pack.py:285` — *"Leaving them unset meant every one of this org's 144
  candidates carried {impact 5000, success 5000, effort 5000, risk 5000} — four of the five
  inputs to the ranking formula frozen at the same placeholder, which makes any unit that
  adjusts them a no-op and makes the persisted score_components read as measurements when
  nothing was measured."*
* `reason/adapters/play_priors.py:1` — Wave Z3 · K1, the same bug one lane over: the compiled
  lane built every `PlayDefinition` without these fields and *"the dataclass defaults are 5_000
  apiece … 45% of the ranking formula was a constant"*.

**The receipt's detail is a paraphrase of that comment.** It was written from the code, and the
code was right. This is not a badly-drawn receipt. It detects a real defect, with the right
query, on the right table.

---

## PART 4 · AND THE DEFECT IS CLOSED — WHICH IS WHAT THE RECEIPT CANNOT SEE

    the 59 frozen rows : 2026-08-17 19:21:18 -> 2026-09-07 23:55:58
    all 34,232 rows    : 2026-08-17 19:21:18 -> 2026-09-30 10:39:04

    frozen rows per day: 08-17:1  08-21:1  08-23:2  08-24:2  08-26:9
                         09-01:4  09-02:27  09-07:13   then nothing

The decisive test:

    candidates written after 2026-09-07 23:55:58 : 34,167
    of those, frozen                             :      0

Per org, since the boundary:

    org_e97e86f858ad48b2bbf64b8a   18,962 written   0 frozen
    org_2f1bc0f366a149e18bd17b06    8,183 written   0 frozen
    org_66bca8648ac94c73a1211e3d    7,020 written   0 frozen

All 59 belong to one org, `org_2f1bc0f366a149e18bd17b06`, which has since written 8,183 clean
candidates.

**The boundary is not a guess.** `git log` on the module that closed it:

    75096bab  2026-09-08  "Layer 4: the formula's dead components, and the chain that was
                           never checkable"      genios_engine/reason/adapters/play_priors.py

The last frozen row is **2026-09-07 23:55:58**. The fix landed **2026-09-08**. The defect's
final occurrence is the day before the commit that closed it, and 34,167 rows of evidence say
the fix holds.

---

## PART 5 · SO WHAT IS ACTUALLY BROKEN

Not the scorer. **The receipt.**

`reasoning_candidates` is append-only history, and the doctrine here is soft delete only. Those
59 rows will exist forever. The receipt scans all of history with no lower bound, so:

> ⛔ **This receipt can never return 0 again. It is red permanently, for a defect that was fixed
> three weeks ago.**

And `api/routes.py:161` computes `ready = not failed` over this same receipt list — the release
gate. So one unfixable receipt holds `ready` false forever, which is how a gate stops being
read at all.

The module that should have caught this already says so. `reason/unit_health.py`, in its own
header, explaining why *its* receipt asks a narrower question:

> *"A receipt asserting 'no unit is silent' would be **permanently red** for an upstream reason
> this layer cannot clear … A gate that is always red is a gate nobody reads. So the claim is
> the one that is true today and false the moment it gets worse."*

**The doctrine was already written. This receipt predates it and violates it.** That is the
finding, and it is a different one from the nine in A, B and C: not a wrong question, not a
missing writer — a correct question asked without a date.

---

## PART 6 · THE RULE THIS PRODUCES

> **A receipt over append-only history needs a lower bound, or it is not a gate — it is a
> monument.** History cannot be repaired, so a receipt that scans all of it converts every
> defect ever fixed into a permanent failure, and the fix becomes invisible.

Corollary, which is the session's existing rule arriving from the other side: *an audit is a
measurement with a date on it.* A receipt is an audit that re-runs. It needs the date too.

---

## PART 7 · THE PLAN — three units, bottom-up

Same shape as A and B: the declaration first, then its reader, then the proof.

**D1 · `ClosedDefect` and the declaration** — `reason/unit_health.py`.
A third declared fact beside `DeclaredSilence` and `UnwrittenFact`. A closed defect needs no
mover (nobody has to act) but it does need what a silence needs: a reason, a date, and the
measured size. Plus the one thing the other two do not have — the **boundary**: the instant
after which the defect must never recur, and the commit that establishes it.
Refuse an empty field exactly as `DeclaredSilence.__post_init__` does.
Declare the one defect: `score_components.neutral_default`, 59 rows, boundary `2026-09-08`,
closed by `75096bab`.

**D2 · the receipt asks the liveness question** — `platform/receipts.py:391`.
Bound the query to `created_at >= boundary`, keep `expect(n) == 0`, and rewrite the detail so
it states the measured truth: 53 of 59 historical rows carried all five components at the
placeholder, the defect closed on 2026-09-08, and what the receipt now watches is whether the
scorer running *now* reproduces it. The receipt then passes — not because it was weakened, but
because it finally asks about the code that is running.

**D3 · the proof** — a new test file.
It must prove the receipt can still fail, or D2 is indistinguishable from making it green:
`expect(1) is False`, `expect(0) is True`; the SQL carries a lower bound and it is the declared
boundary; the declared row count still matches production (59); and the declaration refuses an
empty reason, an empty boundary and an empty date.

### ⛔ ALARM D-A1 — not raised as a fix, recorded as a bound
The 59 rows are inside `org_2f1bc0f366a149e18bd17b06`'s decision history, and six of them were
`disposition=eligible` candidates ranked on a formula that was entirely constant. **Any card
delivered from those 59 was ranked by nothing.** No card has been written since 2026-09-25 and
these predate that, so nothing is live — but if that org's past cards are ever used as training
or evaluation data, these 59 are not evidence. Mover: Rohit, at the point L6 learning reads
history.

### What this unit does NOT do
It does not touch the scorer, the adapters, or `play_priors.py`. Those are correct. It does not
delete or amend the 59 rows — append-only, and PART 6 is the reason.

---

## PART 8 · BUILT — what landed, measured 2026-10-01

**D1 · `reason/unit_health.ClosedDefect` + `CLOSED_DEFECTS` + `neutral_default_boundary()`.**
A third declared fact beside `DeclaredSilence` and `UnwrittenFact`, and the first that carries a
**boundary** instead of a mover. `__post_init__` refuses an empty reason, an empty boundary, an
empty `closed_by` and an empty `measured_on`, and a negative row count — verified, all five refuse.
`neutral_default_boundary()` is a function rather than a constant so the receipt cannot drift from
the declaration by copying it.

**D2 · `platform/receipts.py:86` `_PLACEHOLDER_COMPONENTS_SQL(org)`**, beside the two sibling
builders, with the receipt at L4 rewritten to call it. The receipt count is **29, unchanged** — a
rewrite, not an addition. `import re` added for the date-shape check.

The whole change to the question, in full:

    unchanged  select count(*) from reasoning_candidates where
               score_components->>'impact' = '5000' and score_components->>'risk' = '5000'
               and score_components->>'effort' = '5000'
    added      and created_at >= '2026-09-08'          <- read from the declaration

**D3 · `tests/platform/test_the_frozen_formula_receipt_is_dated.py` — 17 tests, all passing.**
The three that matter:

* `test_the_predicate_is_byte_for_byte_what_it_always_asked` — the original SQL must survive as a
  prefix, so dating can never become weakening unnoticed.
* `test_the_only_change_is_the_lower_bound` — the suffix must equal exactly
  `" and created_at >= '<declared boundary>'"`. Nothing else may be added.
* `test_the_receipt_was_not_made_to_pass` — `expect(1) is False`. One candidate written by the old
  code today and the receipt goes red again.

Plus `test_the_builder_reads_the_declaration_rather_than_restating_the_date`, which walks the AST
of the builder and asserts no string literal in its **body** equals the boundary — the docstring is
excluded on purpose, because it quotes the date, and a whole-file grep would have matched this
document, the receipt's own detail and the test's own prose. Seventh instance in this session of
the blunt-grep family, and the first caught before it was written.

### VERIFIED ON PRODUCTION, read-only

    the D receipt                     PASS   value = 0
    all 29 receipts, fleet-wide       21 PASS   7 FAIL   1 ERROR     (was 21/8/1)
    tests/platform/ + topology        454 passed, 14 skipped

### ⛔ THE RESULT THAT MATTERS MORE THAN THE RECEIPT

With D closed, **not one remaining receipt failure is a mis-asked question.** All seven FAILs and
the one ERROR are now true statements about real gaps with named movers:

    [L1] the parked queue is not a black hole                    1662   ops — no drain path run
    [L1] every drop we might be wrong about can still be         26     ops
    [L1] attachments carry readable text                         872    pytesseract not installed
    [L4] at least one seat has a manager                         0      no reporting line authored
    [L6] no card gives an order with an empty draft              18     cards frozen since 09-25
    [L6] there is a channel this tenant can be reached on        0      Slack not connected
    [L7] a human verdict has reached the loop                    0      no verdict submitted yet
    [L5] every delivered card carries a lane                     ERROR  migration 0190 unapplied

A, B, C and D between them examined all ten findings. One receipt asked the wrong question (C,
the L6 draft), one asked a correct question with no date (D, this one), and eight were correct as
written — including three I suspected and cleared.

---

## PART 9 · THE FULL SUITE CAUGHT ME, AND THE GUARD WAS RIGHT

The targeted runs were green — 17 new tests, `tests/platform/` 454 passed — and the full suite was
not:

    FAILED tests/test_spec_deferrals_resolve.py::test_no_comment_defers_to_a_record_that_does_not_exist
    FAILED tests/test_spec_deferrals_resolve.py::test_nothing_in_the_engine_dangles_at_all

    these comments point at a record that does not exist:
      [('genios_engine/platform/receipts.py', 91, 'speedrun008/YCW27/layer-2-reasoning/12-AUDIT-D')]

`_PLACEHOLDER_COMPONENTS_SQL`'s docstring said *"see
`speedrun008/YCW27/layer-2-reasoning/12-AUDIT-D`"* and the file is
`12-AUDIT-D-the-frozen-formula-receipt.md`. **I wrote a pointer to a document that does not
exist**, in the same unit whose whole subject is a claim nobody could check. The reference is now
the complete path and all three tests pass.

> ⛔ Worth recording rather than quietly fixing, because it is the same family as the stale comment:
> **a comment that cites a record reads as a record somebody can go and read.** An abbreviated path
> is indistinguishable from a real one to every reader except this guard.

And the guard exists because somebody already knew that. It is the counterpart to the blunt-grep
family — where those tests asserted on prose that happened to sit near a thing, this one asserts
that prose claiming to point at a thing actually resolves to it.

### Two targeted runs are not a suite run
Both failures were in a file neither targeted run touched. The rule the working agreement already
states, arriving with a cost attached: *an incomplete QA run is not green.*
