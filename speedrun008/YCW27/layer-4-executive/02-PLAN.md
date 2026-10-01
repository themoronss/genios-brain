# L4 · the plan — sections → functions → units

**Written for:** Harsh (CTO) and Rohit. **Written BEFORE the build.** Read
[`01-CROSSCHECK.md`](01-CROSSCHECK.md) first.

`executive/` — 26 files, 5,990 lines. **Milestone M12.**

---

## The shape

**Three sections, six functions, five units.** One of the four specified units is retired.

| | Section | Units | What | Blocked? |
|---|---|---|---|---|
| **S1** | The reporting line, tested | 1 | ⛔ retires a spec that would break the ladder | no |
| **S2** | Organisation readiness | 2 | ✅ **the reason the queue is empty** | no |
| **S3** | The walk reaches its end | 2 | ✅ approval → execution → verified outcome | no |

### Why this order

```
S1  test what exists     ← cheapest, and it retires a unit
S2  say what is missing  ← the diagnosis L4 has never been able to give
S3  prove the tail       ← needs nothing from S1 or S2, but is only meaningful after them
```

⛔ **Nothing here inserts a row for a tenant.** Activation and organisation data are Rohit's and
Harsh's; what this plan builds is the machinery that **says what is missing** and **proves it worked**
once they do.

---
---

# S1 · The reporting line, tested

## What was expected

`tree.yaml`: *"`reports_to` read from `seat_responsibilities`, **never** `org_seats.manager_seat_id`."*

## What is actually true

`assignment.py` reads **both, in order** — a dated `reports_to` responsibility first, then the column.
Two comments say why, at lines 250 and 651.

⛔ **The spec would break the escalation ladder.** Removing the column leaves every seat with no
manager unless somebody filed a dated responsibility for it, and rung 7 (`escalate → manager`) would
climb into nothing.

### F1.1 · Test the layering instead of changing it

**How:** a test over `SeatDirectory` covering four cases — no line at all, the column alone, a dated
override in force, and a dated override that has **expired**.

**⛔ Why the expiry case is the one that matters:** the whole reason the dated form exists is that a
column overwrite destroys the previous state. *"Covering the North for June means overwriting it on
1 June and remembering to overwrite it back on 1 July. Nobody remembers."* A test that only checks the
override applies would pass on an implementation that never stops applying it.

**Why not also refactor:** it works, it is documented in two places, and it is not what was asked for.
Noticing something adjacent makes a new unit, not a silent edit.

| Unit | Artifact | Verify |
|---|---|---|
| `M12.C1.U01` → **retire spec, keep code** | `tests/executive/test_the_reporting_line_resolves.py` | `uv run --no-sync pytest tests/executive/test_the_reporting_line_resolves.py -q` |

---
---

# S2 · Organisation readiness — the diagnosis L4 has never been able to give

## What is actually true

`platform/receipts.py` carries **23 receipts** and **not one** is about organisation data.

⛔ So a tenant with a compiled pack, a live activation row, a full graph and 23 green receipts can
still be **unroutable** — and nothing says so. That is the state the pilot is in.

### F2.1 · A readiness report that names what is missing

**How:** a pure function over the org's rows returning, per requirement, one of three states:

| State | Meaning |
|---|---|
| `ready` | present and usable |
| `missing` | ⛔ absent, and **named** — with what to do about it |
| `unknown` | the query could not run; **not the same as missing** |

**⛔ Why `unknown` is a third state and not folded into `missing`.** *"Nobody has filed a reporting
line"* and *"we could not read the table"* call for opposite actions, and this programme has been
caught twice by exactly that conflation — `no_model_wired` in L1 and the graph-revision guard in L3.
The rule it produced: **a count without its dimension is not a measurement.**

**⛔ Why it names the FIX, not just the gap.** *"seats: missing"* sends somebody hunting. *"No active
seat has a channel — without one, every plan L4 authors is written and never delivered"* is a sentence
an operator can act on. A readiness report nobody can act on is a status page.

**Why it is pure:** the rows come in, the verdict comes out. A readiness check that could itself fail
on the network is one more thing to diagnose.

| Unit | Artifact | Verify |
|---|---|---|
| `M12.C1.U02a` | `genios_engine/executive/readiness.py` | `uv run --no-sync pytest tests/executive/test_an_unroutable_tenant_says_why.py -q` |

### F2.2 · The receipt, and the door

**How:** register the readiness check as a receipt in `platform/receipts.py`, alongside the 23, and
expose it through the admin door.

**⛔ Why a receipt and not only an endpoint:** an endpoint is read when somebody asks. A receipt is read
on every health pass, which is the difference between a diagnosis and a diagnosis somebody has to think
to request. `test_a_tenant_nobody_feeds_is_not_ready` made the identical argument one layer down.

**⛔ Why it must not be fatal:** a tenant that is not ready is a tenant to be onboarded, not an error.
A readiness receipt that raised would take down the health pass for every other tenant.

| Unit | Artifact | Verify |
|---|---|---|
| `M12.C1.U02b` | `genios_engine/platform/receipts.py` | same command |

---
---

# S3 · The walk reaches its end

## What is actually true

`tests/test_e2e_all_layers.py` exists, is `pg`-gated, and reaches `run_executive` at line 217 —
**then stops.** Grepped for `approve`, `execution_outcomes`, `verified`, `run_lifecycle`: none appear
as assertions.

⛔ **The missing tail is the half that matters.** Everything before `run_executive` proves the seams
line up. Only the tail proves **"activity is not outcome"** — that a situation closes on evidence of
the result and not on a status click.

### F3.1 · The live pass leaves a receipt

**How:** a receipt that distinguishes *"the domain is activated"* from *"the live pass ran for it"*.

**⛔ Why:** `platform/l3_activation` shipped with a reader, a gate, an erasure row, an admin API and a
report — **and no caller.** The lesson Plane R recorded: *"a switch that reports itself on and changes
nothing is worse than no switch."* Once Rohit inserts the row, this is what proves it did something.

| Unit | Artifact | Verify |
|---|---|---|
| `M12.C2.U03` | `genios_engine/platform/receipts.py` | `uv run --no-sync pytest tests/platform/test_activation_changes_the_pass.py -q` |

### F3.2 · Approval → execution → verified outcome

**How:** extend the walk past `run_executive` through an approval, the lifecycle, and a closure that
requires **outcome evidence**.

**⛔ The assertion that carries the unit:** a `done_claimed` execution with no outcome evidence must
**not** reach `verified`. Rule 11 — *activity is not outcome* — is either enforced here or it is a
sentence in a document.

**Why it stays `pg`-gated:** the walk's whole value is that the seams line up on **real persisted
output**. A mocked version would prove the mocks agree with each other.

**⛔ Why the assertions go in a new file rather than into the existing walk:** the existing test is a
compatibility proof that many people depend on. A separate file can fail for its own reason, and a
reader can tell "the seams broke" from "the tail broke".

| Unit | Artifact | Verify |
|---|---|---|
| `M12.C2.U04` | `tests/test_the_walk_reaches_a_verified_outcome.py` | `uv run --no-sync pytest tests/test_the_walk_reaches_a_verified_outcome.py -q` |

---
---

## ⛔ What we are deliberately NOT doing in L4

| Not doing | Why |
|---|---|
| ⛔ removing `org_seats.manager_seat_id` as the tree says | it is the **standing line**. Removing it leaves the ladder climbing into nothing |
| inserting an activation row or organisation data | ⛔ that is a tenant decision, Rohit's and Harsh's. We build what **says it is missing** |
| making the ladder organisation-configured, dependency-aware, acknowledgement-aware | all three are real improvements the Atlas names as targets. None is M12, and doing them before a single tenant is routable would be tuning an empty queue |
| numbering executive units 6 and 8 | they have no file and the spec that numbered them is not in the repo. ⛔ **an open question, not a gap** |
| answering the two open product decisions | does a preventive warning become a card; is a brief pushed? ⛔ **Rohit's**, and both stay behind a flag |

---

## Unsound verifies, named before anyone trusts them

| # | Problem | Status |
|---|---|---|
| 1 | `tests/executive/` **does not exist** — the directory has never held a test | created by S1 |
| 2 | `tests/api/test_org_record_loads.py` is named by `M12.C1.U02` and does not exist | ⛔ **the door moves to a receipt.** See S2.F2.2 for why; the tree row is corrected |
| 3 | The `pg`-gated tests are skipped in every run that has no `GENIOS_TEST_DATABASE_URL` | ⛔ **open.** A skip is not a pass, and S3's tail is only proven where a database exists |
