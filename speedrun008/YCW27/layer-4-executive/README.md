# L4 · Executive — `executive/`

**26 files · 5,990 lines.** Milestone **M12**, 4 units.

> Who decides — and how does a decision become owned, dated, tracked work?

> *A conclusion is an opinion. A commitment is an opinion with an owner, a deadline, a channel, a
> ladder and a clock attached.* Until this layer existed, GeniOS produced good recommendations and
> then had no idea whether anything was ever done.

---

## Two halves

| | |
|---|---|
| **Decision intelligence** | Decision Briefs (`brief.v1`), the verb taxonomy, four modes including **preventive** (distance to the point where the decision flips), the summary ladder, executive memory, why-not receipts |
| **The executive engine** | the Execution Object (`execution.v1`): interpret → plan → owner → channel → validate → track → remind → escalate → monitor → outcome |

It **owns who and where** (`assignment.py`, `communication.py`). Delivery executes the plan this
layer authors and never authors one itself.

⛔ **`ReasoningDecision` is the DecisionObject.** `tests/contracts/test_the_decision_object_is_one_object.py`
settled this: the five rows are projections of one typed, semantically hashed object. Do not mint a
second one.

---

## Three laws

1. **No model decides anything.** A model may improve a reminder's wording; never whether to remind,
   whom to escalate to, the steps, or the urgency. *Approval boundaries and escalation ladders
   cannot be probabilistic.*
2. **Nothing fires without re-validation.** *A nudge about something that already happened costs
   more trust than ten missed ones ever could.*
3. **The plan is immutable; only the row moves.** Execution objects are frozen and content-addressed
   over `(org, decision, plan)` — which is what makes *"why did this escalate on day 7?"* answerable
   months later, after the pack has been retuned twice.

## The input gate — seven conditions

```
audited reasoning run · active pack authority · matching authority revision
matching config version · run completed after the pack's last update
signal still open · authority not expired
```

`SweepReport.reasons` counts refusals **by reason**, because *"a sweep that plans nothing because
every decision was `no_action` is healthy; one that plans nothing because every build hit
`window_closed` is a misconfigured pack, and a single 'skipped' counter cannot tell those apart."*

## The ladder, as shipped

| Day from **creation** | Action | Audience | Interrupts? |
|---|---|---|---|
| 1 | notify | owner | no |
| 3 | remind | owner | **yes** |
| 7 | escalate | manager | no |
| 14 | critical | executive | **yes** |

Days count from creation, not the deadline — *an escalation that starts when the window is already
gone is a post-mortem*. `max_rungs: 6`, because a longer ladder is automated harassment.

---

## Measured today

**It runs on every heartbeat tick and finds an empty queue.** Not broken — correct, over nothing.

| | |
|---|---|
| Domains activated | **0** ⇒ no authoritative decisions ⇒ nothing enters |
| Organisation data | ⛔ missing — seats, reporting line, channels |
| Tables | `executions` · `execution_actions` · `execution_escalations` · `execution_events` · `execution_outcomes` (0041), delegation wiring (0157) |
| Units 6 and 8 | have no file, and three files carry no number. The spec that numbered them is not in this repo — **an open question, not a gap** |

⛔ **And the heartbeat does not appear to run in production at all** (`01-BASELINE.md` §3). That is
upstream of this entire layer.

---

## What changes — M12

### `M12.C1` Organisation data

| Unit | What |
|---|---|
| `U01` | seats, channels and the reporting line — ⛔ `reports_to` lives in `seat_responsibilities`, **never** `org_seats.manager_seat_id` |
| `U02` | the admin door that loads an org record **and reports what is still missing** |

### `M12.C2` Activation and the end-to-end walk

| Unit | What |
|---|---|
| `U03` | the activation row for the pilot, plus the receipt that the **live** pass actually ran — not the shadow pass |
| `U04` | one situation walks signal → card → approval → execution → verified outcome, **as a test, not a demo** |

⛔ `U03`'s receipt exists because of how `l3_activation` shipped the first time: reader, gate,
erasure row, admin API, report — and **no caller**. Never again ship a switch that cannot prove it
changed the pass.

## Order inside M12

`seat_responsibilities` first, then `org_seats`, then the reporting line, then `org_channels` last.
None of it is code; all of it is who the people are. Harsh owns the data; the units own the door
and the proof.

## Read these first

`executive/__init__.py` then `executive/sweep.py` · `executive/assignment.py` ·
`executive/reminder.py` — `reminder_facts`, which is literally the vocabulary a reminder may use
