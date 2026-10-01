# speedrun008 / plan

The execution folder. `../docs/` holds the **investigation**; this folder holds the **work**.

## How this folder is used

1. `STATUS.md` is the live state of every layer. It is the first file to read and the last to
   update. Nothing else records what is done.
2. `layer-1/00-OVERVIEW.md` holds the eleven steps, their dependency order, and the six numbers
   that define "better".
3. `layer-1/step-NN-*.md` is one step. Each is self-contained: a person who has never seen this
   repo can execute it from that file alone.
4. `layer-1/findings/step-NN-*.md` is what a step **found**. One per step. The step file says what
   to do; the findings file says what happened when it was done. `STATUS.md` stays a table and
   points at both.
5. When the instruction is **"next step"**, take the lowest-numbered step in `STATUS.md` that is
   `NOT STARTED`, execute it, and then do **all four** of these before calling it done:
   * write `layer-1/findings/step-NN-*.md`
   * tick the done criteria in `layer-1/step-NN-*.md` itself
   * update that step's row in `STATUS.md`'s table
   * update any of the six metrics the step moved
   Skipping the last three is how a finished step still reads as `NOT STARTED`. That happened on
   step 1 and was corrected the same day.

## The rules that make this work

**A step is done when its NUMBER moves, not when its tests go green.**
Every loss in `../docs/` was hidden by a green suite at some point. A green test on code that
nothing calls, or on a value nothing carries, proves the unit and not the wiring.

**Measure before you change.** Every step states its expected number *before* the change. If the
measured result does not match the prediction, the **understanding of the system was wrong** —
fix the understanding before writing more code. That is the loop, and it is not optional.

**Prove the defect first.** Every step writes a test that FAILS for the intended reason on
today's code, before the production change. A test written after the fix proves nothing about the
defect it claims to close.

**One unit at a time. Never a parent before its children are green.**

**A skip is not a pass.** The seam steps are Postgres-only. Without
`GENIOS_TEST_DATABASE_URL` set they skip silently, and a skipped test is a red step.

## Every step file answers the same nine questions

| § | Question |
|---|---|
| 1 | Why does this step exist — what measured defect does it close? |
| 2 | What is the current status, with file and line? |
| 3 | What number must move, from what to what? |
| 4 | What are the edge cases and failure scenarios? |
| 5 | How is it done, unit by unit, and how is each unit wired? |
| 6 | What test cases prove it — RED first, then GREEN? |
| 7 | What exact commands verify it? |
| 8 | What are the done criteria? |
| 9 | What must this step NOT do? |

## Verify prelude — every command in every step assumes this

```bash
export PATH="/Users/rohitswerashi/MacBook Air Professional/VS Code/VS Code Setup/toolchains/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="<scratchpad>/venv"
export GENIOS_TEST_DATABASE_URL="<scratch postgres>"   # required, not optional
```
