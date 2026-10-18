# L5 · audit — the second delivery architecture, triaged tier by tier

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01. **Written during STEP-05, before any
code.** **Corrects:** `STEP-06`'s claim that the cutover has no measurement.
**Reads with:** `06-AUDIT-the-measurement-that-corrected-itself.md`.

`06-AUDIT` established *how many* functions production does not call — **24 of 123.** This document is
the triage: *why not*, one at a time. It exists because STEP-05's guard requires a reason and a mover
per entry, and **guessing at any of them is how a declaration becomes decoration.**

The triage found that most of the 24 are not 24 separate accidents. They are **one architecture**, built
beside the running one, and the interesting question is not *"why is this function uncalled"* but
**"how far has the cutover got, and what is measuring it."**

---

## 1 · The answer in one table

`deliver/` has **35 modules**. Measured by resolving every import in the engine, relative and absolute:

| | |
|---|---|
| reachable from **outside** `deliver/` | **15** |
| reachable only from **inside** `deliver/` | **17** |
| ⛔ imported by **nothing in the engine at all** | **3** — `lane_recall`, `rate_limiter`, `retry` |

And the v2 control plane splits into **four tiers with four different levels of evidence**:

| Tier of the v2 path | Modules | Production status |
|---|---|---|
| **1 · resolution** | `orchestrator.resolve` · `presence` · `audience` | ⛔ **SHADOW-MEASURED IN PRODUCTION.** `outbox.shadow_resolve_v2` runs it over every live card and sends nothing |
| **2 · persistence** | `spine.materialize` · `logical_dedupe_key` · `record_materialization_failure` | not called. ⛔ `outbox.py:804` says so in writing |
| **3 · claiming** | `spine.claim_due` · `recover_expired_claims` | not called. The recovery has **no test** either |
| **4 · policy** | `rate_limiter` · `retry` · `scheduler.schedule_order` | ⛔ **orphan modules — nothing imports them at all** |

> ⛔ **The finding is the gradient, not the gap.** The cutover is being measured at tier 1 and is
> **unmeasured at tiers 2, 3 and 4** — and two of tier 4's modules are not even imported, so the shadow
> could not exercise them if it tried. A decision to cut over, taken on the evidence that exists, would
> be taken on routing alone.

---

## 2 · ⛔ STEP-06 was wrong about this, and the correction improves it

`STEP-06` states, under *"What this step does NOT do"*:

> *"the measurement that would justify it — `COMPARISON_KEYS`-style counters over both paths — does not
> exist for the outbox."*

**It exists.** `outbox.py:1254`:

```python
def shadow_resolve_v2(engine, org_id: str, *, now: datetime) -> dict:
    """Run the v2 control plane's RESOLUTION over this org's live cards — measure, send nothing."""
```

Called at `outbox.py:1441` inside the sweep, accumulating `v2_shadow_resolved` and
`v2_shadow_unroutable` into the sweep totals, with per-org failures isolated into a count because
*"a shadow must never be able to break the live sweep it is shadowing."* `card_builder.py:497` names it
too: *"its one caller is `outbox.shadow_resolve_v2`, which sends nothing."*

⛔ **This is the `COMPARISON_KEYS` discipline applied to the outbox, and I reported it absent.** Same
error class as five earlier ones in this programme: *a conclusion drawn from one name's absence.* I
searched for a comparison of **both paths' outputs** and did not search for a **shadow**.

> **Doctrine: a measurement can be present under a name you did not search for.** The repair is not to
> search harder; it is to ask *"what would this be called here?"* — and this codebase's own word for it
> is `shadow`, used in `reason/domain_shadow.py` as well.

**What survives, and it is the sharper claim:** the shadow measures **resolution only**. Tiers 2–4 have
no production evidence of any kind. So `STEP-06`'s guard is still right and its justification changes —
from *"nothing measures the cutover"* to **"one tier of four is measured, and the three that touch the
network are not."**

---

## 3 · ⛔ The recall guard this programme built four days ago is an orphan module

`deliver/lane_recall.py` — M13 `STEP-02`, written 2026-09-30, *"prove nothing died quietly"*, **24
tests**. Three files in the engine mention it:

| | |
|---|---|
| `lane_display.py:126` | `#: trusting that they do — `lane_recall.recall_verdict` does exactly that.` |
| `pipeline.py:516` | `# ... `lane_recall.recall_verdict` a tautology, since the tally and the comparison would ...` |
| `reason/domain_shadow.py:1308` | `# ... the argument `deliver/lane_recall` makes about ...` |

⛔ **All three are comments. Nothing imports it. Nothing calls it.** Its three public functions have
**9 test callers and zero engine callers.**

And the second reference is the one that stings: `pipeline.py:516` is **reasoning about the guard's
correctness** — explaining how the tally was shaped so that `recall_verdict` would not be a tautology.
The code was designed around a guard that never runs.

> ⛔ **Ninth instance of built-tested-green-and-called-by-nothing, and the second of this programme's
> own making.** The first was `signals.output_lane` with no reader, found in `01-CROSSCHECK §1` — and
> the unit that closed it produced this one. **A finding's fix is the most likely place for the next
> instance of the same finding**, because it ships under the confidence of having just understood the
> problem.

`lane_recall`'s own header says *"THIS UNIT WAS REWRITTEN… A CORRECTION TO THE PLAN."* The rewrite was
right about what to build and never answered **who calls it.**

---

## 4 · ⛔ Two orphan policy modules — the window and the ladder

### 4.1 `rate_limiter.py` — the per-recipient attention window

| | |
|---|---|
| `hour_recipient_key` | *"The rolling-hour bucket key: a shared stream for chat families, else the seat"* |
| `reserve_slot` | *"Atomically reserve one attention slot… the `where` on the conflict update is what makes two concurrent workers"* safe |
| `release_slot` | *"Give a reserved slot back — only on a DEFINITE non-delivery. Never below zero"* |

⛔ **Nothing in the engine imports this module.** 9 test callers, 0 engine callers.

**And the grain matters, so this is not a duplicate of something upstream.** A `budget` suppression
*does* exist in production — `reason/runner.py:1294` writes `_suppress(..., "budget", ...)` — but that
is **per rule, per node, daily**. `rate_limiter` is **per recipient, per rolling hour**. Different
question, different answer, and only one of them is being asked.

> **So: there is no per-recipient hourly ceiling in the running path.** Under the spend limit nothing is
> delivering, so nothing has been exceeded — which is the same mask that hides `0190`. ⛔ **Whether that
> ceiling should exist is a product decision**, and the correct unit is a declaration naming it, not a
> wiring.

### 4.2 `retry.py` — the ladder and the failover rule

| | |
|---|---|
| `next_attempt_at` | *"When the next provider attempt may run after a DEFINITE failure, or None if terminal"* — honours a provider `Retry-After`, never pulls the delay in below the ladder |
| `may_cross_channel_failover` | ⛔ *"An UNKNOWN outcome must not fail over: the first provider may already have delivered, and a second channel would then be a duplicate human interruption. **Ambiguity stops for reconciliation**"* |

⛔ **Nothing in the engine imports this module either.**

And `may_cross_channel_failover` is the **same rule** `recover_expired_claims` enforces at a different
grain: *an ambiguous outcome must not be retried over.* **Both halves of that rule are written, tested,
and outside the running path** — while the legacy drain handles a crashed sender by pushing
`next_attempt_at` into the future, which is correct for a crash and says nothing about an ambiguous
provider response.

> ⛔ **This is the one triage result that is worth a product conversation rather than a declaration.**
> The v2 path refuses to fail over on ambiguity; the legacy path has no concept of ambiguity. That is
> not a bug in the legacy path — it is a narrower contract — but **it is the reason the cutover was
> designed**, and it is invisible from the running code.

---

## 5 · The rest of the 24, each with its answer

| Function | Why production does not call it | Kind |
|---|---|---|
| `scheduler.schedule_order` | the in-process twin of the SQL ranker. `scheduler.rank_sql` **is** used — by `api/delivery_routes.py` and by `spine.claim_due` — so the ordering rule is live and this composition of it is not | superseded in place |
| `presence.absent` | *"A minimal already-expired context so callers can treat 'no lease' uniformly"* — a tier-1 helper, reached only through the shadow's resolution path | v2 tier 1 |
| `claim_validator.observed_claims` | *"The set a reviewer should read"* — M13 STEP-03/04. **A reviewer surface with no reviewer**: nothing renders it | no producer |
| `claims.by_state` | *"The mix, with every state declared — including the states that did not occur"* — the same shape, same absence of a renderer | no producer |
| `outbox.revive_undeliverable` | ⛔ *"Re-open every row this org parked only because it had nowhere to send it… the answer to 'a card must become deliverable the moment a channel exists'"*. **Nothing calls it, so a parked card stays parked when a channel appears** | ⛔ a real gap |
| `push.push_action_to_agents` | ⛔ **correctly uncalled.** *"This shim stays fail-closed for its old signature — an org-wide unapproved action fan-out is exactly what the protocol exists to make impossible"*. It raises on purpose; external actions go through `executive/delegation.py` | ⛔ deliberately fail-closed |
| `routing.is_agent_transport` · `units.get_unit` | **no docstring.** Leaf predicates, each with a test. The honest declaration says *why it is unreached is not recorded anywhere*, which is itself the finding | ⛔ undocumented |
| `card_builder.resolved_person_name` | the measured 35-of-38 headline defect | ⛔ defect → `STEP-08` |
| `gate.describe_decision` | the unlogged admission record | → `STEP-09` |
| `push.push_card_to_agents` | the push half of a surface served by pull | PULL_ONLY → `STEP-07` |

⛔ **`outbox.revive_undeliverable` is a finding the plan did not have.** Its docstring states a product
promise — *a card must become deliverable the moment a channel exists* — and lists the alternative
designs that were considered and rejected to arrive at it. The function is the conclusion of that
reasoning, and nothing calls it. **So the promise is not kept**, and the specific shape of the failure
is: a tenant registers Slack, and every card parked before that stays parked.

---

## 6 · What this changes

| | |
|---|---|
| `STEP-05`'s table | **24 entries, triaged** — and three distinct tables are needed, not one: deliberate silence, a defect with a step number, and ⛔ **an un-cut-over tier with its shadow named** |
| `STEP-06`'s justification | corrected: one tier of four is measured. ⛔ The guard is unchanged and better founded |
| ⛔ **new** `STEP-14` | `lane_recall` is an orphan — the recall guard this programme built has no caller. **Mine, and the highest-value item in this audit** |
| ⛔ **new** `STEP-15` | `outbox.revive_undeliverable` — a stated product promise with no caller |
| ⛔ **new** `STEP-16` | ⛔ **Rohit's.** Is there a per-recipient hourly ceiling? `rate_limiter` implements one and nothing enforces it |
| `STEP-13` | unchanged — the `called_names` name-collision defect from `06-AUDIT §2` |

---

## 7 · The doctrine this triage produced

| Rule | Where it came from |
|---|---|
| ⛔ **a measurement can be present under a name you did not search for** | §2 — I searched for both-path counters and the codebase calls it a `shadow` |
| ⛔ **a finding's fix is the most likely place for the next instance of the same finding** | §3 — the unit that closed *"a lane nothing reads"* produced *"a guard nothing calls"* |
| **the cutover gradient, not the cutover gap** | §1 — four tiers, four different levels of evidence, and only the safe tier is measured |
| **a comment that reasons about a guard's correctness is not evidence the guard runs** | §3 — `pipeline.py:516` shaped the tally around a verdict nothing computes |
| **two implementations of one word can be two different questions** | §4.1 — `budget` per-rule-daily upstream, per-recipient-hourly here |
