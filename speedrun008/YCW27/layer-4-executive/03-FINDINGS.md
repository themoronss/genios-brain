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
