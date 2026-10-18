# Step 2 — ✅ DONE · why this tenant cannot be routed to

> **Tree:** `M12.C1.U02` · 30 tests · **the reason L4's queue is empty**
>
> ## ⛔ 2026-10-01 · NARROWED, NOT WRONG — and it cost 124 escalations
>
> Re-measured through this step's own `COUNT_SQL`: **seats 1 ✅ · channels 1 ✅ ·
> reporting_line 0 ⛔**, on all three orgs. So organisation data is **partial**, not absent —
> seats and channels are exactly why **186 executions and 165 cards** exist at all.
>
> ⛔ What the missing reporting line actually costs, counted:
> **124 day-7 manager escalations were scheduled and NOT ONE EVER FIRED** (0 with a resolved
> target). The ladder works to day 3 and stops. `manager_of` has two sources and both are empty:
> `org_seats.manager_seat_id` 0 of 3, `seat_responsibilities` 0 rows.
>
> ⛔ And the **input** stopped for a different reason, one layer up, five days before this branch
> began — see `05-RECROSSCHECK-why-the-queue-is-empty.md` F6 and DECISION #5. **Two blocks at two
> places; fixing either alone leaves the other.**
>
> This step's finding stands. Its scope is the **ladder**, not the queue's input.

## 1 · What is actually true

`platform/receipts.py` carried **23 receipts** across every layer. Grepped every one: **not a single one
is about organisation data.**

⛔ So a tenant with a compiled pack, a live activation row, a full graph and 23 green receipts can be
completely **unroutable** — and nothing says so. That is the state the pilot is in, and the whole reason
`executive/` "examines nothing every tick".

`test_a_tenant_nobody_feeds_is_not_ready` made the identical argument one layer down:

> *"Every other receipt can pass while a tenant's feed is dead. ... seventeen receipts still say PASS.
> Nothing said the feed had stopped."*

**Organisation data is the same failure, one layer up.**

## 2 · What was built

| Artifact | What |
|---|---|
| `platform/org_readiness_sql.py` | the three counts, as SQL, in the **floor** |
| `executive/readiness.py` | the verdict — three states, a consequence and a fix per gap |
| `platform/receipts.py` | **+2** receipts (23 → 25) |

## 3 · ⛔ Three states, not two

| State | Meaning |
|---|---|
| `ready` | present and usable |
| `missing` | absent, **named**, with the consequence and the fix |
| `unknown` | ⛔ the query could not run — **not the same as missing** |

*"Nobody has filed a reporting line"* and *"we could not read the table"* call for opposite actions.
This programme has been caught twice by that exact conflation — `no_model_wired` in L1 and the
graph-revision guard in L3 — and the rule both produced is **a count without its dimension is not a
measurement.**

`unknown` does **not** appear under "blocked by"; it appears under "could not measure", separately. And
it still leaves the tenant unroutable, because we cannot claim routable on evidence we could not read.

## 4 · ⛔ It names the fix, not only the gap

> *"seats: missing"* sends somebody hunting through five tables.

```
org_1 is not routable: blocked by seats; could not measure channels
```

and per requirement:

> *"no active seat exists, so there is nobody to assign an owner to and every execution plan is refused
> before it is written. Fix: load the org's seats (org_seats), marking the active ones"*

## 5 · ⛔ Three corrections I made to my own design, all from reading the schema

**1 · `org_seats` has no `channel` column.** My first CHANNELS query read `org_seats.channel`. Migration
0008 defines the table (`org_id, seat_id, email, role, active, created_at`) and 0041 added only
`manager_seat_id`. The query **could never have run** — and would have reported `unknown` forever. ⛔ *A
readiness check that can never measure one of its three requirements is worse than one that admits it
has two.* Corrected to `org_channels`.

**2 · There is no per-seat channel in the schema at all.** `org_channels` is keyed `(org_id, channel)`.
So the consequence sentence could not say *"no active seat has a channel"* — it now says *"the tenant
has no active channel"*. Saying more than the data supports is the failure every other sentence in that
file guards against.

**3 · A channel receipt already existed** — *"there is a channel this tenant can be reached on"*, over
the same table. ⛔ **I dropped mine.** Two receipts answering one question disagree the first time
somebody tunes one. The readiness page still reports channels, because that is the other surface, not a
second claim.

## 6 · ⛔ And one about where the SQL lives

I first put `COUNT_SQL` in `executive/readiness.py` and imported it from `platform/receipts.py`. That is
**`platform` → `executive`** — the floor importing a layer. The topology test **passed**, because
`platform` is cross-cutting and exempt.

> ⛔ **An import nothing fails the build on is not a safe one; it is an unchecked one.**

The SQL moved to `platform/org_readiness_sql.py` and both callers now reach **down** for it. One
definition of "ready", two surfaces — the rule `receipts.py` states for itself.

## 7 · Verify

```
$ uv run --no-sync pytest tests/executive/test_an_unroutable_tenant_says_why.py -q
..............................                                           [100%]
30 passed in 0.26s
```

## 8 · Scenario → what actually happened

| Scenario | Expected | Actual |
|---|---|---|
| everything loaded | routable | ✅ |
| any single gap | blocks, and is **named** | ✅ all three |
| an unreadable count | ⛔ `unknown`, **never** `missing` | ✅ and not listed as a block |
| `unknown` | still unroutable | ✅ |
| 0 vs unreadable | different states | ✅ |
| one gap + one unreadable | **both halves said separately** | ✅ |
| a missing requirement | consequence **and** fix | ✅ >60 chars, `Fix:` present |
| the channel sentence | claims only what the schema supports | ✅ no "seat" in it |
| a state outside the three | refused | ✅ |
| a verdict with no detail | refused | ✅ a state with no sentence is a status page entry |
| one unreadable table | ⛔ does **not** make the other two unknown | ✅ per-row seam |
| a dead connection | all three `unknown`, no raise | ✅ |
| the SQL object | ⛔ **the same object** in both callers | ✅ `is` identity |
| every tenant-scoped count | carries `:org` | ✅ |
| the fleet variants | separate constants | ✅ a filter removed by `.replace()` is one nobody can see was removed |
| channel receipts | **exactly one** | ✅ |

## 9 · For Rohit

⛔ **This is the step that tells you what to load.** Once the pilot's row exists, run:

```
.venv/bin/python scripts/runtime_receipts.py --org <org_id>
```

Two new L4 claims appear: *"the tenant has at least one active seat"* and *"at least one seat has a
manager"*. A red one names the consequence.
