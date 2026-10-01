# Plane D STEP 05 · `M11.C5.U04` · data · every capability has a door or a reason · **DONE**

*(Level 1 — after `U02`, because both are verified by the same validator run.)*

## What was there

| Domain | `deferrals.yaml` | routed by nothing |
|---|---|---|
| Admin | ✅ 30 entries | 0 |
| Customer Support | ⛔ **none** | **7** |
| Sales | ⛔ none | 0 |

Seven Support capabilities: authored, admission-stamped, `stable`, **not stubs** — and reachable by
nothing. The validator could only **warn**, because the census is enforced as errors only for a domain
that has opted in by authoring a ledger. **Seven warnings among 290 is a fact nobody reads.**

## ⛔ Two things measured before writing the file, either of which would have broken the build

**1 · The ledger raises this domain's bar, and it is all-or-nothing.** `validate.py:599` errors on an
unrouted capability with no deferral **only when the file exists**. Creating it converts 7 warnings
into 7 errors unless all seven are covered in the same commit. **A partial ledger is worse than none.**

**2 · Seven `also_serves` conflicts, which would have been seven errors.** A deferred capability
reached through a **live** situation somebody else owns is refused. I found all seven before writing —
and then found the two guards that make them harmless:

```python
if owner in deferred:                                        continue   # suppressed
if not (matches.l2_situation_types or []):                   continue   # routes nothing
```

Every conflicting situation fails **both**: its owner is itself in the deferral set, **and** it binds
zero L2 types. Verified, not assumed.

## What was built

`Domain Expertise/Customer Support Expertise/deferrals.yaml` — all seven. **33 tests.**

⛔ **All seven are one kind, and that is the finding.** Every one is `blocked_on_l2_type` — not out of
scope, not unobservable in principle. Waiting on a type Layer 1 or Layer 2 does not emit:
`issue_under_diagnosis`, `ticket_reopened`, `major_incident_declared`, `incident_unresolved` — all four
in `planned_substrate`, all emitted by nothing.

**Three of the seven own one situation each, and all three bind ZERO L2 types** while declaring a
`pending_l2_situation_types` block naming the missing emitter. **Not a missing door — a missing
doorway.** The other four own no situation at all and wait on the same absent `issue` and `incident`
objects.

The reasons are drawn from what those situation files already argue — e.g. *"`support_case` is anchored
on a company; an issue spans companies, so the binding would produce one root-cause analysis per
customer of the same defect"* — because the corpus had already done the thinking and paraphrasing it
loosely would have been the only way to get it wrong.

## The suppression cost, stated rather than discovered

Deferring three of the seven **removes their situations from the generated map**. All three are
`status: draft` and bind no type, so they routed nothing before and route nothing now. A test asserts
exactly that, **so if it ever stops being true the deferral is re-examined** rather than silently
suppressing a live finding.

⛔ And the registry had to be regenerated. `index.py` was re-run — and **`U02`'s new guard is what
would have caught it if I had forgotten.** The two units verify each other:
`capabilities_deferred: 7`, `capabilities_unrouted_unreasoned: 0`.

## Scope, stated three times because it matters

⛔ **This is an explanation, not an activation.** Customer Support stays on hold. Nothing here switches
a domain on and nothing here compiles for any tenant; Admin remains the only activated corpus. The
reason it is in scope at all: *"the difference between 'deferred, and here is why' and 'forgotten' is
the entire declared-silence doctrine"*, and this domain had nowhere to say the first. A test asserts
the file says so in its own header.

⛔ **Sales gets nothing.** 47 capabilities, zero routed by nothing — nothing to explain. An empty
ledger would raise its error bar for no present benefit and be a file whose only content is that it
exists.

⛔ **Admin's ledger was not touched.** This unit added a file; it did not edit the domain that already
did this correctly.

## Result

```
before:  0 error(s), 290 warning(s) — OK
after:   0 error(s), 283 warning(s) — OK
```

**No capability in any domain is now authored, unreachable, and unexplained** — asserted over the whole
corpus by one test.
