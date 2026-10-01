# Layer 4 — production readiness

**2026-09-25 · measured, not assumed**

> ## ⛔ THE SHORT ANSWER
>
> **Layer 4 is SAFE in production. It is not USEFUL in production yet.**
>
> And it is not useful for a reason that has nothing to do with Layer 4: **Admin is not activated**,
> so the layer runs correctly on every tick and finds an empty queue.
>
> ⛔ **It is already deployed.** `api/routes.py:1150` calls it for every org on every heartbeat.
> There is no "ship it" decision to make — only a "does it do anything yet" question, and today the
> answer is almost nothing, by design.

---

# 1 · Is it SAFE? — ✅ five guards, each measured

| # | guard | what it protects |
|---|---|---|
| **1** | **Three levels of exception guarding** — org enumeration, per-org, whole pass | one org failing does not stop the others; the whole pass failing does not stop the heartbeat. The code says it: *"never kill the beat"* |
| **2** | **Every write idempotent** — `on conflict do nothing` on `executions`, `execution_actions`, `execution_escalations`, `execution_outcomes` | a double-run or a multi-instance deploy is safe |
| **3** | ⛔ **Re-validation immediately before send** | *"a queued message must prove its subject is **still** live at send time, not merely that it was live when queued. A reminder can sit in the outbox through a retry backoff, and the customer can reply in that window — which is exactly the nudge this whole layer exists to never send."* |
| **4** | ⛔ **Gated on `org_channels`** | with no registered human channel, **nothing reaches a person.** The outbox logs a warning and stops. This is the implicit off-switch |
| **5** | ⛔ **Gated on Layer 3** | `AUTHORITATIVE_SIGNAL_PREDICATE`'s seven conditions. No Admin activation → no authoritative decisions → `examined=0`, `created=0` |

**Plus the three laws the layer holds everywhere:** no model decides anything · nothing fires
without re-validation · the plan is immutable and only the row moves.

---

# 2 · If everything shipped to production right now

| question | answer |
|---|---|
| Will anything break? | ⛔ **No.** Guards, idempotency, re-validation, channel gate |
| Will a wrong message go out? | ⛔ **No** — while `org_channels` is empty, nothing reaches a person at all |
| Will it do anything useful? | ⛔ **Almost nothing** — Admin is not activated, so there is nothing to plan |
| Could data be corrupted? | **No** — every write is `on conflict do nothing` |
| Can it be turned off? | **Yes, two ways** — deactivate the channel, or leave Admin unactivated |

---

# 3 · ⛔ THE ONE REAL RISK, and exactly when it turns on

**Today: harmless. The day two things are both true, it stops being harmless.**

```
org_channels has a human channel (e.g. slack)
        AND
seat_responsibilities is empty
        ⇒   EVERY CARD GOES TO EVERYBODY
```

**Why**, from `SeatDirectory.responsibilities`:

> *"A tenant with no declarations has said nothing about who answers for what, and every reader must
> treat that as **'the tenant'** — which is exactly today's behaviour. Reading empty as 'this person
> owns nothing' would **hide every card from everybody** on the day the table shipped."*

⛔ **It fails loud-and-wide, not silent.** That was the right default when the table shipped. It is
survivable with two people and **not survivable with five.**

**Mitigation:** populate `seat_responsibilities` (Harsh's **H5**) **before** registering a Slack
channel — not after.

---

# 4 · ⛔ What production measurement already says about owner resolution

`resolve_owner`'s Rule 3 comment, written against real production data:

> *"Every input above is **structurally absent in production**: `deal.owner`/`relationship.owner`
> have **no `write_fact` producer anywhere**, `commitment.actor` is never written as a fact, and
> `graph_nodes.attributes` is **never populated at all**. So this returned `None` for every card
> ever built — **all 43 carry `assignee = NULL`**, `router.budget_full` short-circuits to False for
> every one of them, and the executive bridge's `assignee is not null` predicate matches **zero
> rows**."*

**What that means for today:**

* **Rules 1 and 2 of owner resolution never fire in production.** Every commitment lands on
  **Rule 3 — the org admin.**
* For a **single-founder tenant that is correct** — the card goes to the founder.
* For a **team it would be wrong** — but it fails *toward the founder*, not toward silence and not
  toward everybody. ⛔ **That is a good safety property right now** and should not be "fixed" by
  inventing a fact producer.

---

# 5 · What does NOT work in production today

| # | what | effect | step |
|---|---|---|---|
| 1 | Admin not activated → nothing is planned | **the layer runs and sees an empty queue** | Layer 3's P3 |
| 2 | `org_seats` empty → owner falls to the admin queue | fine for one founder | H2 |
| 3 | No reporting line → **day-7 "escalate to manager" has nobody to climb to** | the ladder stops at 3 rungs | ⛔ **H3** |
| 4 | `org_channels` empty → nothing reaches Slack | in-app only | H4 |
| 5 | ⛔ Escalations say *"stalled"*, never *"stuck on getting it approved"* | a message people can only feel bad about | **L4-04** |
| 6 | ⛔ Approvals say *"needs sign-off"*, never whose | | **L4-05** |
| 7 | ⛔ **Preventive warnings never become cards** | the USP is never delivered | **L4-06** |
| 8 | Briefs are never pushed | the layer's stated output has no producer | **L4-07** |

⛔ **Not one of these makes the system say something WRONG.** Every one is *"says less than it
could"*, never *"says something untrue"*. **That is why shipping now and improving later is a sound
plan** — the gaps are omissions, not errors.

---

# 6 · The safe activation order

```
1. seat_responsibilities            ← BEFORE any channel.  Otherwise: everybody gets everything
2. org_seats                        ← who the people are
3. reporting line (reports_to)      ← or the day-7 rung does nothing
4. activate Admin                   ← now the layer has something to plan
5. read SweepReport.reasons         ← the first honest number
6. org_channels (slack)             ← LAST. This is the step that makes messages leave the building
```

⛔ **Step 6 is last on purpose.** Everything before it is reversible and invisible. Step 6 is the one
that reaches a human.
