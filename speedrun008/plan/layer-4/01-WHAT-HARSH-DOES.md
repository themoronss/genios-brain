# Layer 4 — what Harsh does, in order

**For: Harsh.** Branch `speedrun008` · 2026-09-25

> ## ⛔ READ FIRST — Layer 4 is already running
>
> This is not a layer to switch on. `api/routes.py:1150` calls `sweep.run_executive` for **every
> org on every heartbeat tick**, before distribution. It plans commitments from authoritative
> decisions, then validates, transitions, reminds, escalates and closes them, and hands outcomes
> to Layer 7.
>
> **Your work here is data and measurement, not deployment.** ⛔ **No migration is pending** —
> 0041 and 0157 are both already applied and neither appears in `DO-THIS-NOW.md`'s list of nine.

---

# ⛔ THE ORDER MATTERS — do these in this sequence, not in any other

```
1. seat_responsibilities   (H5)   ← ⛔ BEFORE any channel
2. org_seats               (H2)
3. reporting line          (H3)   ← or the day-7 rung does nothing
4. Admin activation               ← Layer 3's P3; now there is something to plan
5. read SweepReport.reasons (H1)  ← the first honest number
6. org_channels / slack    (H4)   ← ⛔ LAST
```

⛔ **Why `seat_responsibilities` comes before the channel.** An empty
`seat_responsibilities` is read as **"the tenant"**, not as "this person owns nothing" —

> *"Reading empty as 'this person owns nothing' would **hide every card from everybody** on the day
> the table shipped."*

**So an empty table plus a registered Slack channel means EVERY CARD GOES TO EVERYBODY.** It fails
loud-and-wide, not silent. Survivable with two people; **not survivable with five.**

⛔ **Why the channel is last.** Everything before step 6 is reversible and invisible. **Step 6 is the
one that makes messages leave the building.** See
[`03-PRODUCTION-READINESS.md`](03-PRODUCTION-READINESS.md).

---

# H1 · Read `SweepReport.reasons` — ⛔ do this FIRST, right after Admin goes live

**Why first:** everything else on this page is guesswork until you know whether Layer 4 is seeing
anything at all.

`plan_commitments` gates on `AUTHORITATIVE_SIGNAL_PREDICATE` — **seven conditions**:

```
audited reasoning run            active pack authority        matching authority revision
matching config version          run completed after the pack's last update
signal still open                authority not expired
```

⛔ **Until Admin is activated, all of these are moot** — there are no authoritative decisions, so
`examined=0` and `created=0`. That is the healthy reading today, not a fault.

**Once Admin is live:**

```bash
curl -s -X POST "$BASE/executive/sweep" -H "$AUTH" | jq '.'
```

or read it out of the heartbeat's own response, where `api/routes.py` already reports
`{"orgs": n, "commitments_created": n, "commitments_examined": n}`.

**How to read `reasons`**, which counts refusals BY REASON rather than lumping them:

| if you see | it means |
|---|---|
| `examined=0` | nothing passed the authority gate. **Check Admin activation first**, then pack authority revision |
| mostly `no_action` | ⛔ **healthy.** Most decisions correctly conclude nothing needs doing |
| mostly `window_closed` | ⛔ **a misconfigured pack** — the outcome window is shorter than the decision's own expiry |
| `unreadable_expiry` | the decision core has no readable `expires_at` — a contract problem upstream |
| a channel/owner reason | you are missing the data in **H2–H4 below** |

> The docstring states the whole point: *"A sweep that plans nothing because every decision was
> `no_action` is healthy; one that plans nothing because every build hit `window_closed` is a
> misconfigured pack, and a single 'skipped' counter cannot tell those apart."*

**Write the numbers into this file when you have them.**

---

# H2 · `org_seats` — who the people are

**Table:** `org_seats` (migration 0008) — `org_id · seat_id · email · role · active`

**Without it:** `resolve_owner` cannot name anybody, so a commitment is created with no holder and
every reminder and escalation has nowhere to go.

```sql
select seat_id, email, role, active from org_seats where org_id = :org;
```

**Expect:** one active row per person who should ever own a commitment.

---

# H3 · ⛔ The reporting line — and there are TWO mechanisms, only one of which is right

**The day-7 rung of the escalation ladder is `escalate → manager`. Without a reporting line it has
nobody to climb to, and the ladder effectively stops at three rungs.**

| | mechanism | verdict |
|---|---|---|
| ⛔ **wrong** | `org_seats.manager_seat_id` (0041) — a single mutable column | see below |
| ✅ **right** | `seat_responsibilities` with `reports_to` (**0131**) — carries its own validity window | use this |

The code says why, in `assignment.manager_of`'s own docstring:

> *"`org_seats.manager_seat_id` is a **single mutable column**: covering the North for June means
> overwriting it on 1 June and remembering to overwrite it back on 1 July. **Nobody remembers**, so
> July's escalations still climb to the acting manager — and the June state was **DESTROYED** by
> the July write, so nothing can even say her term was meant to end. A `reports_to` responsibility
> **carries its own window** and simply stops applying."*

⛔ **Use `seat_responsibilities`.** If you populate `manager_seat_id` instead, every acting-manager
period silently becomes permanent.

---

# H4 · `org_channels` — where things are allowed to go

**Table:** `org_channels` (migration 0032) — `org_id · channel · config · active`

**Default without any row:** `in_app` only. `active_channels` always includes it —
*"the card surface needs no registration and it is the floor every other channel choice falls back
to. Without it a tenant with no integrations would have its commitments planned as undeliverable
rather than simply quiet."*

⛔ **So nothing breaks if this is empty — but nothing reaches Slack either.** The known chat channel
is `slack` (`communication.CHAT_CHANNELS`); the others are `in_app`, `digest`, `agent`.

---

# H5 · `seat_responsibilities` — who answers for what

**Table:** `seat_responsibilities` (0131)

⛔ **Empty is NOT read as "this person owns nothing".** From `SeatDirectory.responsibilities`:

> *"A tenant with no declarations has said nothing about who answers for what, and every reader
> must treat that as **'the tenant'** — which is exactly today's behaviour. Reading empty as 'this
> person owns nothing' would hide every card from everybody on the day the table shipped."*

**So the failure mode is the opposite of silence: every card goes to everybody.** With two people
that is survivable. It stops being survivable at five.

---

# H6 · Confirm the policy defaults — ⛔ Rohit's call, your implementation

Nothing here is broken; these are shipped defaults waiting for a yes or a change.

## The escalation ladder as shipped

| day | action | audience | interrupt |
|---|---|---|---|
| 1 | notify | owner | no |
| 3 | remind | owner | ⛔ yes |
| 7 | escalate | **manager** | no |
| 14 | critical | **executive** | ⛔ yes |

* Days are **offsets from creation**, not from the deadline — *"an escalation that starts when the
  window is already gone is a post-mortem."*
* `max_rungs: 6` — *"a ladder longer than this is somebody automating harassment rather than
  escalation."*
* Band tempo: `critical 5,000bp · high 7,500bp · standard 10,000bp` (critical runs the same ladder
  at half the delay).

⛔ **Open question for a two-person company: what do "manager" and "executive" mean?** If neither
exists, the ladder should be three rungs, not four — and the day-7 rung will silently do nothing
until H3 is populated.

⛔ **Good property, do not remove it:** a misconfigured ladder **raises `EscalationConfigError`**
rather than falling back to the default — *"an org believes it changed its escalation policy and
it did not, and they would only discover otherwise on the day the policy mattered."*

## Reminder cadence

| knob | default | the reasoning in the code |
|---|---|---|
| `min_interval_hours` | 20 | *"never twice inside a working day"* — 20 not 24 so a sweep running a few minutes early is not skipped for a whole cycle |
| `max_reminders` | 4 | *"two more than most people need and one fewer than it takes to get muted"* |
| `untouched_hours` | 24 | still PENDING, nobody opened it |
| `deadline_warning_bp` | 7,500 | three quarters of the window burned |
| `recheck_hours` | 6 | how long to wait when nothing is due |

**Urgency bands:** `critical 85 · high 70`

**Where to change them:** the tenant's effective pack config, under `scoring.execution`, in blocks
named `communication`, `reminder` and `monitor`. A missing block means *"use the engine defaults"*
and is the normal state — **not** an error.

---

# H7 · After the first live sweep — three things to look at

1. **`execution_outcomes`** — is anything closing? Seven terminal labels:
   `succeeded · completed_unproven · expired_untouched · expired_in_progress · cancelled_by_human ·
   cancelled_by_world · cancelled_by_system`
2. **`execution_escalations`** — is the ladder firing, and at which rung does it stop?
   ⛔ **If it always stops at day 3, H3 is not populated.**
3. **`execution_events`** — the per-commitment audit trail.

---

# ⛔ Traps

1. **No migration is pending for Layer 4.** 0041 and 0157 are applied. If someone tells you to run
   one, check `DO-THIS-NOW.md` — its list of nine is Layers 1–3 only.
2. **Do not populate `org_seats.manager_seat_id`.** Use `seat_responsibilities.reports_to` (H3).
3. **`examined=0` is not a bug before Admin is activated.** The gate is working.
4. **Do not "fix" `EscalationConfigError` into a fallback.** A silent fallback means an org believes
   it changed policy and did not.
5. **An empty `seat_responsibilities` sends every card to everybody**, not to nobody. It fails
   loud-but-wide rather than silent.
