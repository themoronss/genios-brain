# Step 1 — ✅ DONE · the reporting line, tested · ⛔ and a spec retired

> **Tree:** `M12.C1.U01` · 17 tests · **no production code changed**

## 1 · What was expected

> *"Seats, channels and the reporting line for the pilot — `reports_to` read from
> `seat_responsibilities`, **never** `org_seats.manager_seat_id`."*

## 2 · ⛔ What is actually true — following the spec would break the escalation ladder

`assignment.py` reads **both, in order**: a dated `reports_to` responsibility first, then the column.
Two comments say why. At line 250:

> `org_seats.manager_seat_id` is a single mutable column: covering the North for June means overwriting
> it on 1 June and remembering to overwrite it back on 1 July. Nobody remembers, so July's escalations
> still climb to the acting manager — and the June state was **DESTROYED** by the July write.

And at 651:

> THE DATED LINE FIRST, THEN THE COLUMN. ... the standing line underneath survives it, which is what
> makes *"who was her manager in June?"* answerable in September.

⛔ **They are not rivals. They are a dated override over a standing line.** Removing the column would
leave every seat with no manager unless somebody had filed a dated responsibility for it, and rung 7 of
the ladder (`escalate → manager`) would climb into nothing.

**The spec is retired. The code stays. What it never had was a test** — `tests/executive/` did not exist.

## 3 · Verify

```
$ uv run --no-sync pytest tests/executive/test_the_reporting_line_resolves.py -q
.................                                                        [100%]
17 passed in 0.06s
```

## 4 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| no line at all | `None`, never a guess | ✅ an escalation with no manager refuses |
| the column alone | resolves | ✅ ⛔ **the case the spec would have broken** — most seats have only this |
| an inactive manager in the column | not returned | ✅ a departed manager is not a target |
| a dated cover in force | outranks the column | ✅ |
| a dated cover **expired** | ⛔ **falls back to the standing line** | ✅ **the test that carries the file** |
| a cover that has not started | does not apply yet | ✅ |
| an open-ended cover | keeps applying | ✅ |
| a cover naming an **inactive** seat | falls through to the column | ✅ a cover is an override, not a veto |
| June and July, same directory, nothing overwritten | different answers | ✅ the window did the work |
| `at` | optional, defaults to now | ✅ a required parameter would have broken every caller |
| an **inferred** responsibility | may never narrow a view | ✅ hiding a real situation on a guess is a silent false negative |
| the window boundary | half-open `[from, until)` | ✅ a term that ended yesterday stops today |

## 5 · ⛔ A second finding: the protocol says three and has seven

`SeatDirectory`'s docstring:

> *"Kept to three questions on purpose. A richer directory abstraction would invite ownership logic to
> grow features nobody asked for."*

Measured: `active_seat`, `responsibilities`, `manager_of`, **`admins`, `seat_for_node`,
`seats_for_scope`, `answerable_for`** — seven. ⛔ **The exact growth the comment warned about happened,
and the comment was never updated to say it was accepted.**

**Not fixed, either way.** Deleting four methods that callers use would break routing to close a
documentation gap; rewriting the docstring is a judgement about whether the growth was right, and that
is a decision with an owner. Three tests pin the current surface so the **eighth** is deliberate, and
one asserts the docstring still says three — so the drift shows up in a test result, not only a comment.

## 6 · For Rohit / Harsh

**Nothing.** No production code changed. One correction to carry: `tree.yaml`'s `M12.C1.U01` text is
wrong and is now marked retired — do not act on *"never `manager_seat_id`"*.
