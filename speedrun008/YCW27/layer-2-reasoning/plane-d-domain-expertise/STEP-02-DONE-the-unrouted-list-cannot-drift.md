# Plane D STEP 02 · `M11.C5.U02` · data · the unrouted list cannot drift · **DONE**

*(Level 0 — independent root.)*

## ⛔ The plan's premise was false, and finding that out IS the unit

`02-PLAN.md` said *"`unrouted_l2_types` is **generated**, not hand-kept."*

**It is already generated.** `_tools/index.py:205` emits the block — **including the comment I had
quoted as evidence of hand-keeping** — from `all_l2 - bound_globally` computed at line 61. The whole
registry file is machine-written.

**Measured before writing anything:** backed up all three registries, ran `index.py`, diffed.
**Byte-identical.** Nothing hand-kept. Nothing drifted.

> ⛔ **How the wrong conclusion was reached:** I read `validate.py`, found it computing the same set,
> saw the block in the YAML, and concluded there were two maintainers of one fact. **I never checked
> whether the YAML had a generator, because the name `index.py` appeared in nothing I had read.**
> Same one-name-absence trap as `no_model_wired` (L1), the graph-revision guard (L3) and
> `invention_ok` (L5). **Fourth occurrence.**

## What the real gap is, and it is a better unit

`index.py` has to be **run**. Add a situation that binds a type, commit without regenerating, and the
one file everyone reads for routing coverage says a bound type is unrouted — **and it fails in the
safe-looking direction**, because the failure mode is forgetting to add, not forgetting to remove.

Meanwhile `validate.py` computed the same set **three lines away** and never compared them.

> ⛔ **Two computations of one fact that are never compared eventually disagree** — the argument
> `deliver/lane_recall` makes about the per-lane tallies, and the reason a total that is never checked
> is a claim rather than a measurement.

## What was built

`validate.py` now reads each domain's committed registry and compares `unrouted_l2_types` against its
own computation. A mismatch is an **ERROR** naming the types and the one command that fixes it.

**11 tests**, which drive the real tool over a real edit **in both directions** and restore the file.

## Four decisions

⛔ **An error, not a warning.** There are 283 warnings; a 284th is read by nobody. A stale registry is
a wrong fact in the file the compiler's reverse index is built from, and the fix is one command.

⛔ **The validator does not write.** A validator that rewrites the corpus turns a read into a write and
makes `git status` unreadable after a routine check. `index.py` stays the only writer, and a test
asserts no registry file changes during a validation run.

⛔ **Order counts.** Same members in a different order is reported as stale — because the file is
generated sorted, and a reordering means somebody edited it by hand.

⛔ **Absent is not stale.** A domain with no registry is skipped: that is a louder problem the index
pass reports when it runs, and inventing an error here would put one complaint in two tools with two
wordings.

## Recorded, not fixed

The block's own comment says *"Global, not this domain's fault"* — and there is **one copy per
domain**. A global fact stored three times is read by whoever opens a folder and missed by everyone
else. Moving it is a corpus reorganisation touching every reader of that file: **its own unit, its own
decision.** What this unit guarantees is that wherever it lives, it is **true** — and a test asserts
all three copies agree.
