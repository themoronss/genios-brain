# L4 · cross-check — what is actually true in `executive/`

**Written for:** Harsh (CTO) and Rohit. **Date:** 2026-09-30. **No code written yet.**

`executive/` — 26 files, 5,990 lines. **Milestone M12, 4 units as specified.**

> Every number below came from a command. Three layers in, this programme has produced **seven**
> corrections to its own planning documents, every one from reading the code before changing it.

---

## The verdict first

| Unit as `tree.yaml` specifies it | Verdict |
|---|---|
| `M12.C1.U01` seats, channels, reporting line — *"`reports_to` read from `seat_responsibilities`, **never** `org_seats.manager_seat_id`"* | ⛔ **BUILT, and the spec is WRONG.** Following it would delete the standing reporting line |
| `M12.C1.U02` the admin door that reports what is still missing | ✅ **genuine gap** — and it is why L4's queue is empty |
| `M12.C2.U03` the activation row + a receipt that the LIVE pass ran | ⚠️ **split.** The row is data (Rohit/Harsh); the receipt is a real gap |
| `M12.C2.U04` one situation walks signal → card → approval → execution → verified outcome, as a test | ⚠️ **half built.** The walk exists and stops at `run_executive` |

---

## 1 · ⛔ Finding 1 · `M12.C1.U01`'s specification would break the escalation ladder

**What the tree says to build:** *"reports_to read from `seat_responsibilities`, never
`org_seats.manager_seat_id`."*

**What the code does** — `executive/assignment.py:651`, and it reads **both, in order**:

```python
# THE DATED LINE FIRST, THEN THE COLUMN. An acting term is a `reports_to`
# responsibility with its own window, so it stops applying on its end date without
# anybody remembering to undo a write — and the standing line underneath survives it,
# which is what makes "who was her manager in June?" answerable in September.
```

And at line 250 it says why the column alone was not enough:

> `org_seats.manager_seat_id` is a single mutable column: covering the North for June means
> overwriting it on 1 June and remembering to overwrite it back on 1 July. Nobody remembers, so
> July's escalations still climb to the acting manager — and the June state was **DESTROYED** by the
> July write.

⛔ **So the two sources are not rivals — they are a dated override over a standing line.** Removing
the column, as the unit says to, would leave every seat with no manager unless somebody had filed a
dated `reports_to` responsibility for it. The ladder would climb to nobody.

**The unit is retired. What it needs is a test**, because the layering is asserted only in comments.

---

## 2 · ✅ Finding 2 · Nothing tells a tenant why it cannot be routed to

`platform/receipts.py` carries **23 receipts** across L1–L6. Grepped every one: **not a single one is
about organisation data.** No receipt says *"this tenant has no seats"*, *"no reporting line"* or
*"no channel for this seat"*.

⛔ **That is the whole reason `executive/` "examines nothing every tick".** The layer is built and
correct; it has nobody to route to, and no surface says so.

| What is missing | What breaks without it |
|---|---|
| seats | there is no owner to assign, and `assignment` returns nothing |
| the reporting line | the ladder's rung 7 (`escalate → manager`) climbs into nothing |
| a channel per seat | `communication` has nowhere to send, so the plan is authored and never delivered |

The existing receipts prove the machinery is the right shape — `test_a_tenant_nobody_feeds_is_not_ready`
exists for exactly this class of problem one layer down, and its docstring states the principle:

> *"Every other receipt can pass while a tenant's feed is dead. ... seventeen receipts still say PASS.
> Nothing said the feed had stopped."*

**Organisation data is the same failure, one layer up.**

---

## 3 · ⚠️ Finding 3 · The activation row is data; the receipt is code

`M12.C2.U03` bundles two different things:

| | Who |
|---|---|
| the admin activation row for the pilot tenant | **Rohit / Harsh** — a row in `l3_activation`, not code |
| a receipt that the **live** pass, not the shadow pass, actually ran | **us** — and nothing checks it today |

⛔ **The second half matters more than it looks.** `platform/l3_activation` shipped once with a reader,
a fail-closed gate, an erasure row, an admin API, a report — **and no caller.** Plane R's own notes
record the lesson: *"a switch that reports itself on and changes nothing is worse than no switch."*

So a receipt that distinguishes *"Admin is activated"* from *"Admin ran live"* is not ceremony; it is
the guard against that exact defect recurring after somebody inserts the row.

---

## 4 · ⚠️ Finding 4 · The end-to-end walk exists and stops early

`tests/test_e2e_all_layers.py` exists, is `pg`-gated, and walks a real email through the layers on one
shared store. Its own docstring:

> *"L1 sync → L2 context/graph → L4 reasoning → L5 executive → L5.2 cards → L6 learning"* (old
> numbering).

Measured: it reaches `run_executive` at line 217 and **stops there**. Grepped the file for `approve`,
`execution_outcomes`, `verified`, `run_lifecycle` — **none appear as assertions.**

So U04's specific claim — *"signal → card → **approval → execution → verified outcome**"* — is
**half** proven. The tail is the half that matters: it is where "activity is not outcome" is either
enforced or not.

---

## 5 · What is NOT wrong here

| | |
|---|---|
| the execution lifecycle | `interpret → plan → owner → channel → validate → track → remind → escalate → monitor → outcome`, on every heartbeat tick, **before** distribution |
| the input gate | seven conditions — audited run, active pack authority, matching authority revision, matching config version, run after the pack's last update, signal still open, authority not expired |
| the three laws | no model decides; nothing fires without re-validation; the plan is immutable and content-addressed |
| the ladder | day 1 notify, 3 remind, 7 escalate, 14 critical, `max_rungs: 6` — days counted from **creation**, because an escalation that starts when the window is gone is a post-mortem |
| `SweepReport.reasons` | refusals counted **by reason**, so *"planned nothing: every decision was no_action"* is distinguishable from *"every build hit window_closed"* |
| the bridge direction | Executive never imports Delivery; it writes an `execution_events` row and L5 reads it |
| storage | `executions`, `_actions`, `_escalations`, `_events`, `_outcomes` — migration 0041, delegation 0157 |

⛔ **The Atlas's own summary of this layer is accurate:** *"Running correctly over an empty queue."*

---

## 6 · What M12 actually is

| Unit | Action |
|---|---|
| `M12.C1.U01` | ⛔ **retire the spec, keep the code, add the test it never had** |
| `M12.C1.U02` | ✅ build — an organisation-readiness receipt that **names what is missing** |
| `M12.C2.U03` | ✅ build the **live-pass receipt**; the activation row stays Rohit's |
| `M12.C2.U04` | ✅ extend the walk through approval → execution → **verified outcome** |

---

## 7 · The pattern, four layers running

> **This codebase's comments record decisions its planning documents do not.**

| Layer | The planning document said | The code said |
|---|---|---|
| L1 | `no_model_wired` is a broken wiring | one lane is model-free **on purpose** |
| L3 | nothing guards the graph revision | `reason/runner.py:570` is the guard |
| L2 | plan compile should fail on an unproduced source | it did, and it **cost six units to one absent fact** |
| **L4** | **never read `manager_seat_id`** | **it is the standing line the dated override sits on top of** |


---

## ⛔ 2026-10-01 · *"No code written yet"* at the top of this file was true on the day it was written

**L4 (M12) has since been built: 4 steps, all DONE, 63 tests.**

This file is a **crosscheck**, so *"no code written yet"* is not an error — it is what a crosscheck
says, and the date beside it is what makes it honest. It is noted here anyway because a reader
scanning for status reads that line as current, and this programme has now paid for that mistake
three separate times: a corpus comment that was true when written sent a whole unit to be specified
before it was withdrawn; seven step files carried `TO BUILD` titles on finished work; and
`02-DECISIONS.md` said *"all four open"* when two were closed.

**Nothing above is retracted.** The findings in this crosscheck are what the build was planned from,
and where one of them turned out to be wrong the retraction is recorded at the point it was found,
not here. For current status read
[`../07-LEDGER-every-step-what-why-how-outcome.md`](../07-LEDGER-every-step-what-why-how-outcome.md)
— or `../../07-LEDGER-...` from a plane folder.
