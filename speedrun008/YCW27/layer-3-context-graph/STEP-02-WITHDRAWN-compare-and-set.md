# Step 2 — ⛔ WITHDRAWN · compare-and-set on write

> **Tree:** `M10.C1.U03` · **retired, not built.** The thing it was going to build already exists.
> Retired 2026-09-30, before a line of code was written against it.

## What this step claimed

> `graph_versions` is read in exactly two places — `read_models.py:52` and `situation_bso.py:2054` —
> and **both stamp, neither guards.** Two sweeps that both read revision *N* can both write, and the
> second silently wins. It is one `select` away from being the lock it looks like.

## What is actually true

The compare-and-set is built, is tested, and the caller honours it.

| Where | What it does |
|---|---|
| `reason/runner.py:570` `_graph_version_guard` | reads the tenant row `for share`, compares `current == expected`, **yields a boolean** |
| `reason/runner.py:1276` | on drift sets `graph_drifted` and counts `graph_changed_retry` — **it does not publish** |
| `deliver/store.py`, `deliver/outbox.py`, `deliver/actions.py`, `deliver/agent_api.py`, `api/intelligence_routes.py`, `api/account_routes.py` | 12 more sites take `for share` (or `for update`) on that row before reading |
| `tests/test_graph_version_consistency.py` | **6 tests, 6 passing** |

Verified, not read off:

```
$ .venv/bin/python -m pytest tests/test_graph_version_consistency.py -q
......                                                                   [100%]
6 passed in 0.34s
```

The existing guard also already satisfies the one constraint this step had flagged as the thing that
mattered — ⛔ *"the refusal must be a value, not an exception"* — because it yields a boolean the
caller branches on. Building `write_if_unchanged` next to it would have been a second, weaker copy of
a working mechanism.

It even covers the case the step invented as its headline scenario. The runner captures the version
*before* the expensive phase and re-runs on drift; the test is named
`test_runner_captures_graph_version_before_tenant_p90_and_retries_on_drift`.

## ⛔ Why the finding was wrong, and the rule it adds

I grepped for the version **reader** inside `context/` and concluded from its absence there.

But the read-modify-write cycle **spans packages by design**: `context/` writes the graph and bumps
the counter; `reason/` reads the counter and guards against it. Looking for the guard beside the bump
was looking in the one place the architecture guarantees it cannot be.

> **A guard lives with the reader, not with the writer. Absence in the writer's package is not
> absence.**

This is the second wrong finding in this programme produced by counting along the wrong dimension.
The first was Layer 1's `no_model_wired`, where 632 failures looked like a broken wiring and were in
fact one lane that is model-free on purpose. Layer 1 recorded that as *"a count without its dimension
is not a measurement."* This adds the package dimension to the same rule.

**What I did not do:** refactor `_graph_version_guard` to be shared, move it, or rename it. It works,
it is tested, and it is not what was asked for. Noticing something adjacent makes a new unit, not a
silent edit.

## What survives, and where it went

`_graph_version_guard` is private to `reason/`, and carries pack-authority-revision and publication
watermark logic that belongs to reasoning publication specifically. `context/` sits below `reason/`
and **cannot import it** — `tests/test_layer_topology.py` fails the build on an upward import.

So a read-modify-write in `context/` that begins from the new bounded read has no guard of its own.
That is real, and it is one small unit.

⛔ **It is not being built here, because nothing calls it yet.** A guard with no caller is the
six-times defect this programme keeps finding: built, tested, green, and called by nothing. It is
folded into **[Step 4](STEP-04-need-clears-hold.md)**, which is its first genuine caller — clearing a
hold is a read-modify-write on a situation, and it must not clobber a concurrent sweep.

## For Harsh — what to take from this

Nothing to do. No code changed. The value of this step is the retraction: **`M10.C1.U03` is retired,
not deferred**, and the concurrency guard you may have been told was missing is not missing.

If you want to confirm it yourself, the one command is the pytest line above.
