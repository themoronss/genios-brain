# HANDOFF · coding agent — three standalone briefs

> **Written:** 2026-10-01 · from the YCW27 programme
> **Each brief below is self-contained.** If you need to ask a follow-up question to start, the
> brief was written badly — say so and name what is missing, rather than guessing.
> **Three units. Two build, one measures first.** They touch disjoint files, so they can run in
> parallel — but **one writer per file, always**, and nothing here may be merged with the others'
> edits in the same commit.

---

## THE RULES THIS REPO ENFORCES, AND WILL FAIL YOUR BUILD OVER

Read these before the briefs. Every one of them has already failed a build in this programme.

1. **`genios_engine/LAYERS.py` is the single source of layer numbers.**
   `tests/test_layer_topology.py` fails the build on an upward import. **`contracts/` may depend on
   platform and stdlib only** — a `contracts` module importing `LAYERS` broke the build once; the
   check moved into a test instead.
2. **Integer basis points everywhere.** No float, no `round()`. Divisions use `divide_half_up` on
   ints, because these numbers reach content hashes and must be identical on every machine.
3. **`eval_time` is a parameter, never `now()`.** No clock inside logic.
4. **Conditional inclusion** (`contracts/reasoning.py:845`): a new output field **must be omitted
   when it has nothing to say**, so an identical computation hashes identically. Adding a field that
   is present on every run makes every stored trace fail replay verification.
5. **NULL is an answer.** Never fabricate a zero for an absent measurement. `5000` in particular is
   forbidden as a neutral default — `reason/decision_maker.py:181` says why, and
   `reason/unit_health.CLOSED_DEFECTS` records what it cost last time.
6. **Soft delete only. Receipts cannot abort.** A receipt that raises must not stop the ones after
   it; `platform/receipts.evaluate()` resets the connection in a `finally`, not an `except`.
7. **⛔ Assert on structure, never on text that sits near a thing.** This repo calls it the
   blunt-grep family and it has bitten **seven times** in this programme, every time matching the
   author's own prose. `"denominator" not in src` matched its own docstring. A whole-file scan for a
   date matched the comment explaining the date. **Walk the AST, or assert on the column list — and
   when you must exclude a docstring, exclude it explicitly.**
8. **A comment is not a measurement.** If a docstring says something is missing, broken or ungated,
   **run or read the thing it names before writing any of it down.** Four findings in this programme
   were wrong because a true-when-written comment was read as current.
9. **Never weaken a verify to make it pass.** If you change a test so it passes, you must be able to
   show a mutation of the product code that the old test accepted and the new one rejects. If you
   cannot, you weakened it.
10. **Two targeted test runs are not a suite run.** Run `pytest -q` whole before claiming green. The
    last two findings in this programme were in files no targeted run touched.
11. **A skip is not a pass.** An incomplete QA run is not green.
12. **Do not commit or push** unless explicitly asked.

### How to verify anything against production

```bash
cd <repo> && set -a && . "../.env" && set +a    # .env is ONE LEVEL ABOVE the repo
```

psycopg **v3**, not v2. `get_engine(database_url)` takes a **positional** arg. Every read runs
`set transaction read only` as its first statement. **Never** set `GENIOS_ALLOW_PROD_WRITE` to run a
report — that variable is named for writes because it was written for writes.

⛔ **The pooler was unreachable at the time of writing** (connection timeout, three hostaddrs;
it had answered 20 minutes earlier). If a number below disagrees with the database, the database is
right.

---
---

# CA1 · `core.confidence` and `core.priority` accept a manifest that forgot its source

> **Type:** behaviour change · **its own unit precisely because it changes behaviour**
> **Files you own:** `genios_engine/reason/reasoners/priority.py`,
> `genios_engine/reason/reasoners/confidence.py`, plus one new test file
> **This is ALARM A6 in `STATUS.md`.**

### What is there now

Both units read their source from the manifest and fall back to an empty string:

    priority.py:65     return str(view.config.get("source_reasoner") or "")
    confidence.py:139  source = str(view.config.get("source_reasoner") or "")

`priority.py:228` already states the consequence in its own words: a capability that **forgets**
`source_reasoner` yields an empty source string rather than a refusal.

### Why it is wrong, and why it is nonetheless safe today

An empty source is not a source. The unit then looks up a prior published by `""`, finds nothing,
and goes quiet — which is **indistinguishable from the honest silence** of a unit whose source ran
and published nothing. A manifest-authoring mistake becomes a measurement that is simply absent.

It is safe today only because every shipped manifest names a `source_reasoner`. It becomes unsafe
the first time someone authors one that does not, and the symptom will be a unit that mysteriously
stopped contributing.

### What to build

A manifest that omits `source_reasoner` must produce a **refusal**, not an empty string — the same
shape the codebase already uses for a deployment fault. `reason/guards.py` states the principle for
its own closed sets: *"an unknown component or stage is a deployment fault, never a silent
no-op."* Follow that, and look at how `packs/compiler/errors.NoExpertiseRoute` carries a
**required, keyword-only `reason`** drawn from a closed set — the refusal here should name which of
the two units refused and that the key was absent, so the message is actionable without a re-run.

### Freeze these contracts — do not change them

* `UnitView.config` stays a plain mapping. Do not add a required key to the view.
* `source_units` on both units stays `()`. **They read no other unit's output** and the empty tuple
  carries its reason already — see `plane-r-reasoning-units/STEP-02-to-08-DONE-*.md` §3.
* Do **not** add a new published metric to signal the refusal. Rule 4 above: a field present on
  every run breaks replay for every stored trace.

### Verify

```bash
.venv/bin/python -m pytest tests/reason -q          # 1,392 collected today
.venv/bin/python -m pytest -q                        # 14,534 passed, 0 failed today
```

Your new test must include one that **fails if the refusal is removed** — construct a view whose
config omits `source_reasoner` and assert the refusal, then assert the old behaviour (an empty
string reaching the lookup) is gone.

### Done means

A manifest without `source_reasoner` refuses with a named reason; both units' existing behaviour on
a well-formed manifest is byte-identical; `pytest -q` whole is green; and a short note lands at
`speedrun008/YCW27/layer-2-reasoning/plane-r-reasoning-units/STEP-09-DONE-<slug>.md` saying what was
there, what you did, what it cost, and what it did **not** fix.

---
---

# CA2 · `core.tradeoff` publishes two diagnostics that nothing reads

> **Type:** a reader, not a field · **Files you own:** one new reader module or script, plus tests.
> **Do not edit `tradeoff_unit.py`'s published metrics.**

### What is there now

`reason/reasoners/tradeoff_unit.py` publishes, on every run:

    tradeoff_unit.py:296   "axis_count": len(ranked)
    tradeoff_unit.py        "axes_unavailable"  (added in S5.U02, present only when non-zero)

Grepped 2026-10-01, outside the publishing module and `unit_health.py`: **nothing reads either of
them.** (`confidence.py`'s `situation_trust_axis_count` is a different metric — do not conflate
them.)

And the numbers are already damning. `tradeoff_unit.py:115`, measured on production 2026-10-01:

> *`axis_count` is 1 on 63% of runs and 2 on 37%, **never 3***

`core.tradeoff` is a three-axis comparator that has **never once compared three axes**, and
`tradeoff.cost_vs_benefit` has fired **0 times in 1,200 rows** while
`tests/reason/test_tradeoff_cost_axis.py` passes — on a prior the test supplies itself.

### Why the fix is a reader and not a field

This was decided, not assumed. `reason/unit_health.py`'s header records it:

> *"Having `core.tradeoff` publish which axis it lost would add a field to the output of ~100% of
> runs, and `contracts/reasoning.py:845` states the consequence: every trace in `reasoning_runs`
> would fail replay verification against a run that computed the identical result. The established
> rule is conditional inclusion, and conditional inclusion does not help when the condition holds on
> every run. `axis_count` is ALREADY published on every run and read by nobody — so the fix is a
> reader, not a field."*

**Do not re-litigate this.** If you believe a field is needed, write down why the replay
consequence does not apply and stop — do not build it.

### What to build

A read-only reader that turns those two published metrics into an answerable question, in the shape
this repo already uses twice:

* `scripts/l2_unit_said_nothing.py` and `scripts/l2_fact_writers.py` are the two existing
  read-only probes. Match them: **import the declaration, keep no copy of it.**
* If the answer belongs on the operator page, add it as a **receipt** in
  `genios_engine/platform/receipts.py` using a `_..._SQL(org)` builder beside the three that exist
  (`_UNDECLARED_UNWRITTEN_FACTS_SQL`, `_PLACEHOLDER_COMPONENTS_SQL`, `_UNDECLARED_SILENT_UNITS_SQL`).
* ⛔ **If you add a receipt, it must be able to fail and it must not be permanently red.** The whole
  of `12-AUDIT-D-the-frozen-formula-receipt.md` is about what happens otherwise: *a receipt over
  append-only history needs a lower bound, or it is not a gate but a monument.* `api/routes.py:161`
  computes `ready = not failed` from that list. A claim that cannot clear belongs in
  `reason/unit_health` as a **declaration with a reason and a mover**, not as a red gate.

### The honest framing for whatever you write

The silence is **correct**. `core.impact` publishes nothing because `deal.status` has no writer, and
fabricating a zero would be the lie. Both silent units are already declared in
`reason/unit_health.DECLARED_SILENT` with a reason, a mover (**Harsh**) and a measured share. So your
reader's job is **not** to make the axis fire — it is to make the lost axis *countable*, so that
"this comparison was not possible" stops being indistinguishable from "this comparison found
nothing".

### Verify

`pytest -q` whole, plus your probe run against production read-only. Note in your output which org
you measured and on what date — *an audit is a measurement with a date on it, and a measurement read
six weeks later is a claim.*

### Done means

`axis_count` and `axes_unavailable` have at least one reader; nothing in `tradeoff_unit.py`'s
published metrics changed; no new permanently-red receipt exists; and a note lands at
`speedrun008/YCW27/layer-2-reasoning/STEP-13-DONE-<slug>.md`.

---
---

# CA3 · the parked queue — 1,662 pending · **measure before you build**

> **Type:** investigation first. **Do not write a drain.** One exists.
> **Read-only until you report back.**

### What is there now, and what is NOT missing

The receipt *"the parked queue is not a black hole"* fails at **1,662 pending**, and the obvious
conclusion — that nothing looks at parked events — is **wrong**. The machinery exists and is wired:

    genios_engine/capture/parked/drain.py             drain_parked(engine, *, org_id, limit=200, now)
                                                      parked_aging(engine, *, org_id, now)
    genios_engine/capture/parked/recapture.py         NEEDS_RECAPTURE
    genios_engine/capture/parked/refetch.py
    genios_engine/capture/parked/refetch_policy.py    NEEDS_REFETCH

and `api/routes.py:1121-1127` calls `drain_parked` from `run_sync_sweep` — the heartbeat — with the
comment: *"a park is 'look at this again', so something has to look. Riding the existing heartbeat on
purpose."*

`drain_parked` already classifies every row it examines into: `reinjected`,
`blocked_no_payload`, `needs_refetch`, `needs_recapture`, `stale`, and a `by_reason` breakdown.

### The question nobody has answered

**Which classes are the 1,662 in?** That single number decides whether this is a code unit, an ops
unit, or H2 on the Harsh handoff wearing a different hat — and the three have nothing in common:

| If the 1,662 are mostly… | then the unit is… |
|---|---|
| `needs_refetch` | **H2's deploy** — `NEEDS_REFETCH` holds attachment stubs whose bytes never existed |
| `stale` | a policy decision about what a park means after N days — **Rohit's**, not code |
| `blocked_no_payload` | a real code gap: parked with nothing retained to re-adjudicate from |
| `reinjected` but still pending | a genuine bug in the flip back to `emitted` |
| simply unexamined | ops — `limit=200` per sweep against 1,662, so count the sweeps |

### What to run

```python
# read-only. .env is one level above the repo. psycopg v3. get_engine takes a positional arg.
from genios_engine.capture.parked.drain import parked_aging
# plus, directly:
#   set transaction read only;
#   select status, reason, count(*) from parked_events group by 1,2 order by 3 desc;
#   select min(created_at), max(created_at) from parked_events where status='pending';
```

⛔ `drain_parked` **writes** (it flips `source_events.outcome` back to `emitted`). Do not call it to
investigate. `parked_aging` is the read-only half — that is why it exists.

### Then, and only then

Report the breakdown with its date and write
`speedrun008/YCW27/layer-1-enterprise-signals/12-AUDIT-<slug>.md` in the shape the other audits in
this programme use: PART 0 what the receipt claims, PART 1 what was measured, PART 2 what is actually
broken, PART 3 the plan, with ⛔ ALARMs for anything that is a decision rather than code. **Findings,
not fixes** — then ask before building.

### Done means

The 1,662 have a dimension on them. *A count without its dimension is not a measurement*, and that
receipt has been failing with one number and no breakdown for the whole programme.

---
---

# What is NOT on this list, and why

| Not a brief | Why |
|---|---|
| `0186`–`0190` | a deployment — **Harsh**, `HANDOFF-HARSH.md` H1 |
| OCR / 872 attachments | a deployment + requirements — **Harsh**, H2 |
| backfill 60→365 | a connector setting — **Harsh**, H3 |
| `deal.status` writer | a CRM connector — **Harsh**, H4 |
| 18 cards instructing with an empty draft | the API spend limit froze cards on 2026-09-25 — **Rohit**. The receipt stays red on purpose: *a receipt is not fixed by making it green* |
| roster activation (ALARM A2) | a runbook step — **Rohit**. ⛔ ALARM A5: schedule `core.impact`, `core.cost`, `core.opportunity` **before** switching `core.tradeoff` on, or it compares 1 of 6 axes |
| the 97 `draft` objects | whether `draft` should gate is a decision with a number under it — **Rohit** |
| ConfidenceVector axes | 3 options, recommendation **A** (keep the code's six, correct the Atlas) — **Rohit** |

**State at handoff:** full suite **14,534 passed, 0 failed**. Production receipts **21 PASS, 7 FAIL,
1 ERROR** of 29 — and not one of the failures is a mis-asked question. Every remaining red is a true
statement about a real gap with a named mover, which is what makes this list short.

---
---

# 2026-10-01 · FOUR MORE BRIEFS — L4 round 2

⛔ **Read `speedrun008/YCW27/layer-4-executive/05-RECROSSCHECK-why-the-queue-is-empty.md` first.**
`executive/` needs no build work; these four are about what it **built and never calls**, plus two
findings one layer either side.

⛔ **And none of them produces a card until DECISION #5 is answered.** They are worth building
anyway — U1 most of all, because it is what makes the stop visible — but do not expect a card.

## BRIEF A · the receipt that says the queue is empty, and why

**File** `genios_engine/platform/receipts.py` — a 32nd claim.
**Claim** *"no reasoning era selects zero candidates."*

⛔ **A CONJUNCTION, NOT A COUNT.** A high defer rate is healthy: the old era deferred 8,208 times
and still produced 1,157 decisions. The defect is `count(*) > 0 and count(selected_candidate_id) = 0`
over a window.

⛔ **The lower bound comes from a FUNCTION, never a literal.** `reason/unit_health.neutral_default_boundary()`
is the pattern — a copied date goes stale and the receipt becomes a monument. See
`tests/platform/test_the_frozen_formula_receipt_is_dated.py`.

**Success condition** ⛔ the receipt goes **RED** against production today. "It goes green" is the
wrong test — a receipt that is green on a stopped product is the thing it exists to prevent.

## BRIEF B · `assignment.resolve_approver_seat` reaches a live path

**Files** `genios_engine/executive/sweep.py` (`plan_commitments`) ·
`genios_engine/executive/unreached.py` (delete the entry).

Resolve the approver beside the owner when `context.requires_approval` is set.

⛔ **Three outcomes, and only one may name anybody.** `AuthorityView.resolve` returns `enforced`
(may name a seat), `suggested` (observed behaviour matched — a human must confirm) or
`no_authority_rule` (the org holds no rule, which is **NOT** "anyone may approve"). Eight tests
already pin this. **`None` stays `None`** and the card says *"sign-off needed"* naming nobody,
which is correct.

⛔ **Delete the `unreached.UNREACHED` entry in the SAME commit.**
`tests/test_the_executive_says_what_it_does_not_call` checks both directions — an entry naming a
function that is now called is as much a lie as a function unreached and undeclared. **That test
going red is how you know you forgot.**

## BRIEF C · the escalation names the step it is waiting on

**Files** `genios_engine/executive/monitor.py` (tests first) ·
`genios_engine/executive/escalation.py` (copy) · `unreached.py` (delete the entry).

Today every stalled-commitment escalation says *"your Acme follow-up is stalled"*. It should say
*"stuck on getting it approved"*. `escalation.py` and `deliver/` contain **zero** references to a
blocking step — verified.

⛔ **`monitor.blocking_action` has NO TESTS.** It is the only `UNREACHED` entry in that state.
**Write them first.** Building on an untested function is how an untested function becomes a wrong
one.

⛔ **Timing does not move, and the plan stays immutable.** This is escalation **copy**, not ladder
**policy** — day 1/3/7/14 and `max_rungs: 6` are untouched. And the field goes on the **rung**,
never on the plan: execution objects are frozen and content-addressed so *"why did this escalate on
day 7?"* stays answerable months later.

## BRIEF D · two findings, one either side of L4

| | Finding | File |
|---|---|---|
| **F9** | ⛔ `source_events.occurred_at` max = **2056-04-20** — a date 30 years in the future. Measure the blast radius first (how many reads order or window on it), then bound it at ingest. ⛔ **The bound is the unit; the row is the symptom** | `capture/` |
| **F10** | 708 of 2,681 outputs carry no `ranking_weights_version` — exactly the `legacy.rule` + `legacy.score_gate` count. Either the lane records its weights or it **declares that it has none**, in `unit_health.py`'s shape: a reason and a mover | `reason/` |

## ⛔ DO NOT BUILD

| | Why |
|---|---|
| **G3 brief push** · **G4 preventive push** | both need a **product number** — *how many warnings a founder should see a day* — and `unreached.PULL_ONLY` spells out why a naive one-card-per-finding would spend the whole daily budget on warnings. Building the threshold by guessing it is building a guess |
| the reporting line | ⛔ **not code.** `readiness.py:66` already says what to do: set `org_seats.manager_seat_id`, or file a dated `reports_to` responsibility. It is organisation data |
| ⛔ a fallback inside `llm_decision_maker` | that is **option C of DECISION #5** and it **changes a declared doctrine**. It needs saying out loud, not slipping in |
