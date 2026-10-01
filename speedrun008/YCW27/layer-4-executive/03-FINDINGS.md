# L4 · findings — what measuring `executive/` actually turned up

**Date:** 2026-09-30. Everything here was measured before any code was written.

---

## ⛔ F1 · The plan said never to read `manager_seat_id`. It is the standing line

`executive/assignment.py:245` — `manager_of` reads the **dated** `seat_responsibilities.reports_to`
FIRST, and falls through to the `manager_seat_id` column. That is not a legacy path to be removed:
the dated row is an **override with a validity window**, and the column is the standing line it sits
on. Removing the column would leave a tenant with no manager whenever no dated row is in force.

**Correction #8 to the programme's planning documents.**

---

## ⛔ F2 · The topology test PASSED on an import that should not exist

My first `readiness.py` put its SQL where `platform` imported `executive`. `test_import_direction`
**passed**, because `platform` is in `CROSS_CUTTING` and is exempt as a source.

> **An import nothing fails the build on is not a safe one; it is an unchecked one.**

The SQL moved to `platform/org_readiness_sql.py`, which is where a cross-cutting package's own
queries belong. The exemption is correct — `platform` is the composition root — and an exemption is
not a licence.

---

## ⛔ F3 · `org_seats` has no `channel` column, and my query could never have run

The first CHANNELS query read `org_seats.channel`. That column does not exist, and **there is no
per-seat channel anywhere in the schema.** The query would not have errored loudly: the
per-requirement `try/except` would have caught it and reported `unknown` **forever** — a readiness
page permanently saying "we cannot tell", which reads as a data problem at the tenant rather than a
bug in the reader.

Channels are read from `org_channels`, at org level. And a channel receipt **already existed**, so
mine was dropped rather than duplicated: *two receipts answering one question disagree the first time
somebody tunes one.*

---

## ⛔ F4 · A test of mine was a blunt grep twice before it was right

The activation guard test first matched `def _persist_live(` — the definition, not the call. The
second version used a 900-character window that was too short for the comment block between the call
and the guard. The third walks the AST for `If(Not(Name('live_row')), [..., Continue])`.

> **Assert on structure — the AST, the column list — never on text that happens to sit near a thing.**

---

## ✅ F5 · Three things were already right, and one goes further than asked

| | |
|---|---|
| `lifecycle.next_state` | returns `WAITING` on `done_but_unproven`, **never** `COMPLETED` |
| `collect.classify_outcome` | `LABEL_SUCCEEDED if outcome_kind else LABEL_COMPLETED_UNPROVEN` |
| the `SeatDirectory` protocol | 7 methods; its docstring says *"three"* — recorded as drift with 3 tests rather than deleting methods or quietly rewriting the sentence |

---

## What changed because of these findings

| Finding | Effect |
|---|---|
| F1 | the reporting-line unit **reads both**, in the documented order, and a test asserts the fall-through |
| F2 | new file `platform/org_readiness_sql.py`; the SQL constants are separate, never string surgery on one |
| F3 | channels read `org_channels`; no fourth receipt |
| F4 | the guard test walks the AST |
| F5 | nothing rebuilt; three tests added so the properties now fail a build if broken |

---
---

# 2026-10-01 · RE-CROSSCHECK FINDINGS — F6 to F12

Measured read-only against production on 2026-10-01. Full trace:
[`05-RECROSSCHECK-why-the-queue-is-empty.md`](05-RECROSSCHECK-why-the-queue-is-empty.md).

## ⛔ F6 · The queue is empty for a reason one layer up, and it is declared

`GENIOS_L4_LLM_DECISION_MAKER = true`, no org allowlist → **on for every org**. The Anthropic
spend limit has refused every call since 2026-09-25 11:09 UTC.
`reason/llm_decision_maker.py:20` — *"**Failure is DEFER, never the formula.** ... Falling back to
the formula would make a test of 'what does the model decide' silently measure the formula."*

    the 8,044 candidates on the 2,681 runs since 2026-09-29:
      formula_utility  5,469   ✅ the deterministic scorer is HEALTHY
      llm_utility          0   ⛔ zero on every single one
      final_utility_bp     0   ⛔ zero on every single one
      outcome_kind     defer 2,669 · blocked 12 · decision ZERO  ->  0 signals emitted

L4's gate was decomposed join by join: 42 open signals survive joins 1–5 and **join 6 drops them
to 0** (`core.constraint` completed on the run behind the signal). ⛔ **Not the status filter** —
all 2,681 `core.constraint` rows are `completed`; the 98 runs behind every open signal have **zero
reasoner results of any kind**, because reasoner results only began being written on 2026-09-29.

**This is the tenth time in the programme a state would have been called a defect before the
declaration that created it was read.** It is DECISION #5.

> ⛔ **A deliberate refusal to degrade is still a stop.** Measurement modes must declare that they
> are measurement modes, or the first budget ceiling takes the product down silently.

## ⛔ F7 · STEP-02's finding is NOT superseded — and it cost 124 escalations

`readiness.py`, run through its own `COUNT_SQL` on all three orgs:
**seats 1 ✅ · channels 1 ✅ · reporting_line 0 ⛔**. Seats and channels are why 186 executions
exist at all. The reporting line is zero in **both** of `manager_of`'s sources —
`org_seats.manager_seat_id` 0 of 3, `seat_responsibilities` 0 rows.

    execution_escalations, 466 rows:
      day 1 notify   owner    175   127 fired   127 with target   ✅
      day 2 remind   owner      1     1 fired     1 with target   ✅
      day 3 remind   owner    165    75 fired    75 with target   ✅
      day 5 escalate manager    1     1 fired     1 with target   ✅
      day 7 escalate manager  124     0 fired     0 with target   ⛔⛔

**124 day-7 manager escalations were scheduled and not one ever fired.** The ladder works to day 3
and stops. Two blocks, two places: F6 stops work entering, F7 caps the ladder inside.

## ⛔ F8 · `seat_responsibilities.reports_to` is not a column — correction to F1 and to the Atlas

F1 above and the Atlas both write it as a column. The table's columns are
`org_id, seat_id, scope_kind, scope_key, accountability, source, evidence_ref, valid_from,
valid_until, created_at`. `assignment.REPORTS_TO = "reports_to"` is a **value of
`accountability`**, and `reports_to` appears in **no migration** — correctly.

**The code is right.** `readiness.py:66` states both paths precisely: *"set
`org_seats.manager_seat_id` for the standing line, or file a dated `reports_to` responsibility"*.
Only the prose was imprecise, in two documents, and this is the correction.

## F9 · ⛔ `source_events.occurred_at` max = **2056-04-20**

A date **30 years in the future** in a production column. Every freshness axis, every window and
every "most recent" read over that table is wrong for that row. ⛔ **One row is a finding; the
absence of a bound at ingest is the defect.** L1, its own unit.

## F10 · 708 outputs carry no `ranking_weights_version`

Present on **1,973 of 2,681** new outputs. The missing 708 are exactly the
`legacy.rule` + `legacy.score_gate` run count. Two scoring lanes, one of which cannot say which
weights it used — so it is not replayable. L2, its own unit.

## ⛔ F11 · `unreached.py` cites `api/routes.py:1150`; it is at **1195**

True claim, stale address — the exact shape of *"a comment that cites a record reads as a record
somebody can go and read"*. ⛔ **`tests/test_spec_deferrals_resolve.py` cannot catch it**: it
resolves document paths, not `file.py:line` citations in prose. That generalises beyond this file.

## F12 · The Atlas got L4 right — 11 claims checked, 1 superseded

Exactly right on *"Units 6 and 8 have no file and three files carry no number"* — numbered are
1, 2, 2.5, 3, 4, 5, 7, 9, 10; unnumbered "Unit" files are `assignment`, `escalation`,
`execution_guard`. And `unreached.UNIT_NUMBERING_UNRESOLVED` already records it **better** than the
Atlas does: *"A declared UNKNOWN, not a finding ... An absent number is not an absent unit."*

Its one superseded claim: *"the queue is empty because no domain is activated"* — true when
written, no longer the binding constraint, because L4 produced 186 executions and 165 cards.

---

## ⛔ Five load-bearing citations were opened by hand. One in five was wrong.

| | Claim | Checked |
|---|---|---|
| 1 | `contracts/execution.py:233` gates autonomy on `requires_approval` | ✅ `return not self.requires_approval and not self.external_effect` |
| 2 | `deliver/outbox.py:315` imports `build_summary` | ✅ exact |
| 3 | `escalation.py` + `deliver/` have **no** reference to a blocking step | ✅ zero hits — G1 confirmed |
| 4 | `deliver/` has **no** reference to preventive anything | ✅ zero hits — G4 confirmed |
| 5 | `api/routes.py:1150` calls `run_executive` | ⛔ **stale, it is 1195** → F11 |
