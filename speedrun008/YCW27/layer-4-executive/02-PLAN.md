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

---
---

# ⛔ 2026-10-01 · ROUND 2 — six units, in dependency order

The first round (STEPS 1–4) built what L4 was **missing**. This round addresses what L4
**built and never calls**, plus what stops its queue. Source of truth for the gaps is
`executive/unreached.py`, which declared them before the Atlas did.

## ⛔ U0 · DECISION #5 — not a build, and it gates every other unit's VALUE

Not its buildability — U1 to U5 can all be built today. But **no card is produced until U0 is
answered**, so building first and deciding later means building blind.

See `../02-DECISIONS.md` decision #5. Three options: **A** raise the Anthropic spend limit ·
**B** `GENIOS_L4_LLM_DECISION_MAKER = false` and let the formula decide (`formula_utility` is
already **5,469** on live candidates) · **C** build a third path where `llm_decision_unavailable`
falls back and `llm_declined` still defers.

**Recommendation: B now, C as a unit, A when the budget allows.**

---

## U1 · the receipt that says the queue is empty, and why — **UNBLOCKED**

**Why first.** Today **nothing anywhere says this.** The operator-visible symptom is "no cards",
and six layers report healthy. A product that stops and cannot say so is the failure this whole
programme exists to make impossible.

**Build.** A 32nd claim in `platform/receipts.py`: *"no reasoning era selects zero candidates."*

⛔ **It must be a CONJUNCTION, not a count.** A high defer rate is **healthy** — the old era
deferred 8,208 times and still produced 1,157 decisions. The defect is a **100% defer rate over a
window of runs that produced candidates**. That distinction is exactly what audit D taught:
*a count without its dimension is not a measurement.*

    select ... from reasoning_run_outputs ro
     where ro.created_at >= <lower bound>          -- ⛔ a receipt over append-only
                                                   --    history needs a lower bound
     having count(*) > 0
        and count(ro.selected_candidate_id) = 0    -- ZERO selected, not "few"

⛔ **And the lower bound comes from a function, never a literal** — the frozen-formula receipt
(audit D) learned that a copied date goes stale and the receipt becomes a monument.

**Verify.** The receipt is **RED today** against production, and would have been red since
2026-09-29. ⛔ A receipt that is green on a stopped product is the thing it exists to prevent, so
"it goes green" is **not** the success condition here — "it goes red, correctly, now" is.

---

## U2 · G2 · `assignment.resolve_approver_seat` reaches a live path — **UNBLOCKED · safest**

**Why it is the safest.** Eight tests already pin the hard part: `AuthorityView.resolve` has three
outcomes and **only `enforced` may name anybody** — `suggested` means observed behaviour matched
and a human must confirm; `no_authority_rule` means the org holds no rule, which is **NOT** "anyone
may approve". The thinking is done; only the wiring is missing.

**What it costs today.** `unreached.py` quotes the function's own docstring: *"a card that says
'this needs sign-off' and cannot say whose is less useful than one that can."* The
`requires_approval` flag **is** read — `contracts/execution.py:233` gates autonomy on it — and
nothing ever resolves who must sign.

**Build.** `sweep.plan_commitments` resolves the approver beside the owner when
`context.requires_approval` is set.

⛔ **`None` stays `None`.** With `no_authority_rule` the card says *"sign-off needed"* and names
nobody — which is what it says today and is correct. This unit does not invent an approver.

⛔ **Delete the `assignment.resolve_approver_seat` entry from `unreached.UNREACHED` in the SAME
commit.** `tests/test_the_executive_says_what_it_does_not_call` checks both directions: an entry
naming a function that is now called is as much a lie as a function unreached and undeclared.
**That test failing is the proof the unit landed.**

**Verify.** A commitment with `requires_approval` and an `enforced` rule names its approver; one
with `no_authority_rule` still names nobody; the both-directions guard passes.

---

## U3 · G1 · the escalation names the step it is waiting on — **UNBLOCKED**

**What it costs today.** `unreached.py` calls this *"the ONE worth reading twice, and the only one
here that is a real product gap"*, and quotes the docstring: *"'Your Acme follow-up is stuck on
getting it approved' is a message somebody can act on; 'your Acme follow-up is stalled' is a
message somebody can only feel bad about."* Measured: `escalation.py` and `deliver/` contain
**zero** references to a blocking step, so every stalled-commitment escalation today is the second
sentence.

**⛔ Tests FIRST.** `monitor.blocking_action` is the **only** entry in `UNREACHED` with no tests at
all — unreached *and* unexercised. Building on an untested function is how an untested function
becomes a wrong one.

**Build.** The `remind` and `escalate` rungs carry the blocking step; `escalation.py` copy names
it.

⛔ **Timing does not move.** `unreached.py` says it explicitly: *"That is a change to escalation
copy, not to the ladder's timing, so it does not touch policy — but it needs the rung to carry a
field it does not carry today."* The ladder's day-1/3/7/14 policy and `max_rungs: 6` are untouched.

⛔ **And the plan stays immutable.** Execution objects are frozen and content-addressed over
organisation, decision and plan. **This adds a field to the RUNG, never a mutation to the plan** —
otherwise *"why did this escalate on day 7?"* stops being answerable months later.

**Verify.** A stalled commitment whose second action is unticked escalates with that action named;
one with no identifiable blocker escalates with **today's** wording, not an invented one.

---

## U4 · F9 · the future-dated row — **UNBLOCKED · L1**

`source_events.occurred_at` max = **2056-04-20**. Measure the blast radius first — how many reads
order by or window on that column — then choose between a bound at ingest and a correction.

⛔ **The bound is the unit; the row is the symptom.** Correcting one row and leaving the ingest
unbounded means the next parser escape writes the next one.

---

## U5 · F10 · the legacy lane's ranking weights — **UNBLOCKED · L2**

708 of 2,681 outputs carry no `ranking_weights_version` — exactly the
`legacy.rule` + `legacy.score_gate` count. Either the legacy lane records its weights, or it
**declares that it has none**, in `unit_health.py`'s shape: a reason and a mover.

⛔ A scoring lane that cannot say which weights it used is not replayable, and replay is what makes
a stored decision a decision rather than a memory.

---

## U6 · G3 + G4 · brief push and preventive push — ⛔ **BLOCKED on a product number**

Both are declared in `unreached.PULL_ONLY` with their costs already written:

- **G3** `brief.py` calls brief.v1 *"the executive unit of output"* — and **nothing in `sweep.py`
  composes one.** The layer's unit of output is never produced on a tick; a client must GET it.
- **G4** `modes.py` names preventive mode *"the vision's USP"*. `deliver/` contains **zero**
  references to preventive anything — **no preventive finding has ever become a card.**

⛔ **Why neither is buildable yet**, in `unreached.py`'s own words:

> *Turning [preventive] into a push is NOT a small change: every elapsed-time rule condition on
> every node produces a clock reading, so a naive 'one card per finding' would spend the daily card
> budget on warnings. **It needs a threshold, and the threshold is a product decision about how many
> warnings a founder should see a day.***

**Building either without that number first is building a guess.** They stay Rohit's, and they are
exactly the Atlas's two declared open product decisions.

---

# ⛔ Not a unit — organisation data

**Block 2** (F7: 124 day-7 escalations, 0 fired) is **not code**. `readiness.py:66` already says
what to do, and it has said it since STEP-02:

> *set `org_seats.manager_seat_id` for the standing line, or file a dated `reports_to`
> responsibility*

Either closes it. Neither is a build.
