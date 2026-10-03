# 19 · PENDING — who owns what, and what it unblocks

**Written for:** Rohit. **Date:** 2026-10-01. **One page, because `STATUS.md` is 2,100 lines and
the live list is buried in it.**

⛔ **Read this before STATUS.md.** This is the whole programme's remaining work, by owner. Nothing
here is a summary of finished work — for that, read
[`07-LEDGER-every-step-what-why-how-outcome.md`](07-LEDGER-every-step-what-why-how-outcome.md).

---

## THE SHAPE OF IT

    MINE        ⛔ 0 items — STEP-17 closed 2026-10-01. NOTHING IS LEFT ON MY LIST.
    ROHIT'S     7 items     4 decisions, 2 data gaps, 1 push    ⛔ STEP-16 WITHDRAWN
    HARSH'S     6 items     5 deployments + 1 test run
    BLOCKED     3 items     mine, each waiting on one of the above — and only on those

⛔ **Nothing on my list blocks anything on anyone else's.** And **one item on Harsh's list is
breaking a write path right now** — `H1`.

---

# ⛔ MINE — `STEP-17` closed L5 on 2026-10-01. ⛔ **L6's SECOND PASS re-opened my list 2026-10-02**

> ⛔ **This header said "NOTHING" and it was true for one day.** The L6 re-crosscheck found twelve
> things and forced a correction on L5. **10 units planned, 1 already measured, 0 built** —
> `layer-6-learning/06-PLAN-the-second-pass.md`.

> ⛔ **THIS TABLE WAS STALE FOR THREE STEPS AND THE CAUSE WAS MY OWN TOOLING.** It still listed
> plan v1's `U01`–`U10`, with `U03`/`U04`/`U05` as *"planned"* when the Atlas check had **retracted**
> them. My `S2`–`S4` edits used a plain `str.replace()` with **no assertion that the anchor
> matched**, so three updates silently did nothing while the narrative blocks beside them landed.
> ⛔ **An edit that cannot fail cannot be trusted** — the same defect class this programme is
> about, in the script doing the correcting. Every anchored edit in this session's scripts now
> asserts its match count; the three that did not are the three that were lost.

| | Unit | State |
|---|---|---|
| `U01` | the 27 skips in `tests/feedback` | ⛔ **MEASURED** — all `GENIOS_TEST_DATABASE_URL`; **two files entirely** → **HARSH (`H7`)** |
| ⛔ **`S1`** | a unit may not write a durable brain from a measurement | ✅ **DONE** · 27 tests · 4/4 mutations |
| ⛔ **`S2`** | the value withheld for a ledger that exists | ✅ **DONE** · 18 tests · 6/6 · ⛔ found **`F21`**: the North Star ledger has no writer |
| ⛔ **`S3`** | a policy that did not load may not learn | ✅ **DONE** · 40 tests · 8/8 · ⛔ **Atlas #10 CLOSED** |
| ⛔ **`S4`** | a silent unit names the producer that does its job | ✅ **DONE** · 23 tests · 8/8 · ⛔ **Atlas #2 CLOSED by REFUTATION** |
| ⛔ **`S5`** | the inbox landed; the `kind` did not | ✅ **DONE** · 27 tests · 8/8 · ⛔ the layer's **first CORRECTNESS receipt**; **Atlas #1 NARROWED** |
| ⛔ **`S6`** | every refusal is named; an illegal lifecycle edge | ✅ **DONE** · 46 tests · 9/9 · ⛔ **`governed → published` was ILLEGAL**; `U03` un-retracted · `F34`–`F36` |
| ⛔ **`S7`** | the count becomes data; a lost seam gets a name | ✅ **DONE** · 20 + 55 tests · 9/9 + 8/8 · ⛔⛔ **`context/` is the worst-covered package** · `F37`–`F41` |
| ⛔ **`S8`** | the scorecard reaches the learning layer | ✅ **DONE** · 21 tests · 2/2 · `L1-to-L6`, **56** claims · ⛔ 4 EXPIRED + **four cells hid a defect** · `F42`–`F45` |
| ⛔ **`S9`** | the paperwork — and a finding of mine refuted | ✅ **DONE** · +10 tests · 2/2 · ⛔⛔ **`F17` RETRACTED as my own false finding** · `F16` `F18` closed · `F46`–`F49` |
| ⛔⛔ **`S10`** | the three gaps nobody had measured — the LAST unit of `M14.C2` | ✅ **DONE** · 69 tests · 27/27 · ⛔⛔ **0 of 11 Atlas gaps unmeasured**, and **none of the three became CLOSED** — one clause left each, all three Rohit's. ⛔ `#3`: the durable ADAPTIVE path is blocked by **arithmetic**, and the obvious repair opens it → a **tripwire**. ⛔ `#5`: enforcement **proven**, rendered surface **unreached**, receipt **41**. ⛔ `#6`: the reset **propagates**; my `latest_reset_at` declaration was wrong. ⛔ **4 of my own guards repaired** → [`layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md`](layer-6-learning/STEP-S10-DONE-the-three-unmeasured-gaps.md) |

⛔ **`M14.C2` IS COMPLETE — 10 of 10 units DONE, 0 failed at every step.**

⛔⛔ **AND `context/` IS AUDITED (2026-10-02)** — the package `S7`'s number put last. ⛔ The gap
was **receipts, not tests**: 306 test files import it. **9 write-only tables declared engine-wide,
receipt 42 added, six of the audit's own findings retracted.** New on Harsh's list: **§H8** (three
read-only checks and one decision). New on Rohit's: ⛔ `graph_nodes` has **46 external readers and
no receipt** — the top of the ranked gap list, left as a measurement rather than closed with an
invented claim. What is left in
Layer 7 is six PARTLY rows whose residues are all decisions, listed below.

⛔⛔ **AND `api/` IS AUDITED (2026-10-03)** — step `1.1` of `21-PLAN-TO-PRODUCTION.md`. ⛔ **Eleven
candidates raised, eleven retired**: every one died on reading the code or the declaration beside
it, and **two of the three columns I called `api/` worst on were my own mis-signal** (25 route
handlers are decorator-excluded by design). ✅ The survivor: **`learning_objects` is write-once
except `state` and nothing asserted it** — now guarded both ways, with **no receipt deliberately**,
because the data cannot answer it without reimplementing `semantic_hash` in SQL.
**Next: `1.2 platform/`** — 12,651 lines, 1 receipt, 29 tables written, 25 uncovered.

⛔⛔ **AND `platform/` IS AUDITED (2026-10-03)** — step `1.2`. ⛔ **15 candidates, 15 retirements**,
and the survivor is a park the health check **excludes by construction**: `warm_lane` sets
`parked_at` for a row whose attempts ran out and every reader filters it out, so a stuck tenant
reports a clean lane. **Receipt 43** closes it. ⛔ The fifteenth retirement was mine and five
minutes old — Atlas `L2-02` is **declared** in `LINEAGE_UNPROTECTED`, and its mover is now a
read-only query on Harsh's page (`H8.5`). **Next: `1.3 reason/`** — 41,363 lines, 29 uncovered
tables, 14 modules no test names.

⛔⛔ **AND `reason/` IS AUDITED (2026-10-03)** — step `1.3`. ⛔ **20 candidates, 20 retirements, 0
receipts**: every derivable claim was already enforced or receipted. ⛔⛔ **The finding was the
audit's own measurement** — the *"no test names it"* column was wrong **19 of 33 times**, six
repairs each over-corrected, and the guard written for it altered its own subject's score. **It is
deleted**, with the reasoning kept on every page. ⛔ Two live modules with no test survive as real
work: `api/identity_routes.py` and `reason/team/away.py` (**`1.3b`**). **Next: `1.4 capture/`**, then
**`2.1` Atlas L2's nine claims** — the largest remaining block.

✅⛔ **AND `1.3b` IS DONE (2026-10-03)** — the two modules the deleted naming column left behind.
⛔⛔ **One of them was guarding health information with no test**: `reason/team/away.py` promises
*"no leave reason ever leaves this module"* and maps `sick` to `leave`, and a single line changed
would have told every seat why a colleague is off. ⛔ The other, `api/identity_routes.py`, had an
untested gate on a **destructive** merge. 32 tests, 17/17 mutations. ⛔ Not on anybody's list — both
are closed. **Next: `1.4 capture/` or `2.1` Atlas L2's nine claims.**

✅⛔⛔ **PHASE 1 IS CLOSED (2026-10-03)** — five coverage steps, ⛔ **52 candidates raised and 52
retired**, three receipts and six guard suites. `1.4 capture/` added **receipt 44**, which turns
`journey.py`'s own sentence — *"why did I never see X?"* — into a production check with five
derivations and nothing spelled. ⛔ **Nothing from Phase 1 is on anybody's list**: every finding was
either closed with a guard or declared with a reason. **Next: `2.1` Atlas L2's nine open claims**,
the largest remaining block — and `L2-02`'s mover is already `H8.5` on Harsh's page.

### ⛔ New on Rohit's list, out of `S10`

| | What, and why it is not mine |
|---|---|
| ⛔⛔ **ADR-10 — the Adaptive representation** | `S10` hands it the measurement that sizes it: `select unit, result_state, sink_reason, count(*) from learning_object_evaluations where unit = 'recommendation_learning' group by 1, 2, 3` (read-only). All rows `held / insufficient_distinct_days` ⇒ the durable ADAPTIVE path has **never once** been exercised and the blast radius is **zero**. ⛔ Until it is ratified, **do not "fix" `distinct_days`** — the tripwire explains why |
| ⛔ **`api/brain_routes` and the seat principal** | the route depends on `get_current_org` and has no caller identity; `AuthCtx` carries `email`/`seat_id`. Giving it one is an API contract change the dashboard depends on. Safe today because every durable producer declares an open scope — declared as a pair, and receipt 41 watches the data |
| ⛔ **Atlas `#6`'s *"fails promotion"* clause** | `feedback/` reads `organization_resets` nowhere, and blocking promotion after every reset would stop learning for a tenant that merely seated a teammate (`seat_joined` calls the same function). Guarded so the day it is wired, it is wired deliberately |
| **a clamp on the stored policy floor** | `load_or_seed_policy` takes every stored column verbatim and `migrations/0045` has no CHECK — `LearningPolicy`'s docstring claimed the opposite and is corrected. A clamp changes which proposals **every** tenant admits |
| **move the reset clock into `contracts/`** | the honest fix for the duplication the topology forces, exactly as `feedback/consumer.py` → `contracts/learned_state.py` already did one layer over |
| ⛔ `U03` `U04` `U05` | **RETRACTED / demoted** — invented from the ledgers, not from the Atlas | `08-PLAN-v2` §8 |

```
L6 M14.C2   10 units · ⛔ 6 DONE · S7 next · 0 failed at every step
suite       15,027 passed · 1,067 skipped · 152 xfailed · 0 failed
Atlas L7    5 CLOSED · 3 PARTLY · ⛔ 0 LIVE · 3 unmeasured
receipts    35 → 38 · ⛔ feedback/ correctness 0 → 3 · unread ledgers 4 → 2
```

⛔⛔ **Rohit, `context/` is the next layer to re-measure and that is your call, not a choice I
should make quietly.** Guards per package is DATA now (`platform/receipt_coverage.py`, both
directions guarded) and the derived number points somewhere the programme has never looked:

```
context     2 receipts   2 correctness   50,877 lines   ⛔⛔ 25,438 lines per guard   WORST
capture     5            5               47,184                9,436
reason      8            5               41,363                5,170
deliver     7            5               10,020                1,431   ← STEP-10's subject
feedback    9            5                4,040                  448
packs       1            0                8,188   ⛔ one PRESENCE receipt, zero correctness
```

⛔ `STEP-10` spent a whole step on `deliver/` because a hand-derived 4,715 pointed there.
**`context/` is 5.4× worse than that figure**, and `deliver/` is now the third-best covered package
in the product. ⛔ `packs/` has one presence receipt and no correctness question at all — the state
`feedback/` was in before `S5`.

⛔⛔ **Rohit, ONE read-only query, and it answers two questions at once:**

```sql
set transaction read only;
select from_state, to_state, count(*) from learning_transitions group by 1, 2;
```

A `governed → published` row means a brain value **was** published before today's fix, and the
illegal-edge receipt stays red until that history is accounted for. ⛔ **No rows at all** means **no
brain value has ever been published** — which is `L7-27`'s question (*"stored learned version is
never consumed by Layer 3"*) and the same answer the Adaptive decision (`#11`) needs.

⛔ **2026-10-02 · the Atlas check changed the list.** Running it first **retracted `U03`, `U04`
and `U05`** — invented from the ledgers rather than from the specification — and found two defects
they did not contain. `S1` is **DONE** (27 tests, 4/4 mutations caught). The live plan is
`layer-6-learning/08-PLAN-v2-from-the-atlas.md`; `S2` is next.

⛔⛔ **Rohit, Atlas Layer 7 #1 is a SURFACE, and it is the Atlas's own P1.** A founder needs
somewhere to say *"pause outreach for seven days"* or *"always cc my co-founder on investor
threads"*. ⛔ **Everything behind that sentence already exists** — `learning_event_inbox` (0046)
with its idempotency and its `lease_until` column, `LearningTarget.RUNTIME`, `govern()` →
`TEMPORARY`, `publish_runtime` → `temporary_memories` with `expires_at NOT NULL`, `preflight`'s
three expiry checks, `expire_leases`. ⛔ **And the inbox is already carrying rows nobody reads** —
written by `reason/moments/store.record_feedback` from `api/moment_routes.py:746`, loaded into every
weekly batch, counted as `inbox_unconsumed` and dropped. ⛔ **Not a model:** the Atlas's own warning
is now quoted in the code — *"adding a model directly to empty units would produce eloquent
ungrounded preferences. First wire typed evidence."*
→ `layer-6-learning/STEP-S5-DONE-the-inbox-landed-and-nothing-consumes-it.md`

⛔ **2026-10-02 · Atlas Layer 7 now: 5 CLOSED · 3 PARTLY · ⛔ 0 LIVE · 3 unmeasured.** `S4` closed
gap #2 **by refutation** — *"direct personalization evolution is missing"* is wrong; both components
are built one package down (`packs/brains/behavior_distill`, `packs/brains/adaptive_lease`) and
appended to the same weekly run. ⛔ **No Atlas Layer 7 gap is fully live any more.** The three
PARTLY ones are `#1` (the preference + temporary-memory inboxes — surfaces that do not exist), `#4`
(population caps) and ⛔ `#11` (the durable ADAPTIVE residue, **yours**).

⛔⛔ **Rohit, the product's headline number has no producer.** `macv_ledger` (migration `0012`)
calls itself *"the North Star … the number the customer can verify"* and has `period`, `deal_id`,
`amount`. Measured 2026-10-02: **five occurrences in the whole repository and not one is a read or a
write** — the migration, the cascade FK, `api/account_routes.py`'s **deletion list**, the retention
test, and `docs/LAYER_MAP.md`, which claimed `feedback/` writes it. ⛔ **The only code that touches
it deletes it.** `/v1/insights/stats` is correct to return `value_recovered_inr: null` and now says
so truthfully (`value_state: "unavailable_macv_ledger_has_no_writer"`, bound to a test that fails
the moment a writer appears). ⛔ **Not a quiet fix:** what counts as recovered value, which deals
attribute, and the *"anti-inflation double-count rule"* are product decisions.
→ `layer-6-learning/STEP-S2-DONE-the-north-star-has-no-writer.md`

⛔⛔ **Rohit, one decision and one query:** `unit_recommendation_learning` publishes `efficacy_bp`
into the **durable** `ADAPTIVE` brain, **auto-promoted with no human review**, and
`packs/compiler/runtime_brains.py` reads that brain **into the compiled expertise package the
recommender reasons from**. The Atlas boundary for that exact unit is *"No self-training from
recommendation score."* Four sibling units of the same shape target `METRICS`. Three repairs, all
yours because all three change what the brain contains —
`layer-6-learning/07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md` §2. And the production blast
radius needs one read-only query: `select brain, count(*) from learned_brain_entries group by
brain`, inside `set transaction read only`.

⛔ **The headline:** `feedback/` **runs** — wired into the heartbeat, weekly per tenant. It has
**4 receipts and all four are presence checks**, satisfied by a single successful tick, while the
**four append-only ledgers that would answer the correctness questions have no reader.**
`3,111 / 4 = 778` lines per guard is the **best ratio in the product**, which is why guards-per-line
never found it.

⛔ **And a correction I owe on L5:** `Receipt.layer` is a hand-written digit, not a package.
`deliver/` carried **5** receipts and **4** working, not 2 and 1 — `1,886` lines per guard was
already true before the pass began. 11 documents + 1 test docstring marked in place.
→ `layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`

---

# L5 — closed 2026-10-01, and it was the last of them

**Every package now states what it does not call**: ten declaration modules, **109 declared
entries**, one parametrised guard over eleven packages — so a *new* package forgetting its
declaration fails the build, which nine hand-written copies could never have caught.

⛔ **The scope was 109, not 147.** Four wiring mechanisms, measured before a single entry was
written: a call, a decorator, ⛔ **a reference** (46 of them — `platform/auth.require_owner` has 35,
and declaring those would have been 46 lies), and ⛔ **duck-typed dispatch, which cannot be measured
at all** and so was hand-checked entry by entry.

⛔ **`scripts/` was decided by me**, because the question was open and the work was authorised.
`SCRIPTS_ARE_CALLERS = True` in `platform/reachability.py` is one constant to flip; all thirteen
functions it rescues are diagnostics or ops reads, and `tests/` is excluded for the opposite reason —
nobody runs a test to learn something about production.

**The findings are in** `layer-5-delivery/STEP-17-DONE-nine-packages-nobody-asked.md`. The sharpest:
⛔ **the EvidenceNeed executor cannot read its own queue** — `capture/` is layer 1, `context/` is 2,
and `need_executor.py:125` already says *"which this layer may not import."* Four functions, one of
them with **22 test callers**, broken at a layer boundary rather than by an oversight.

---

# ⛔ ROHIT'S — the stable list

> ⛔ **THIS HEADER SAID "eight items" AND THE COUNT WAS WRONG BY 2026-10-02.** L6's ten steps and
> the `context/` audit added five more, and the items were named differently in four files —
> *"DECISION #5"* here, *"U6c"* in L4's folder, *"the reporting line"* in prose. ⛔ **Every item now
> has a stable `R#`**, introduced in [`21-PLAN-TO-PRODUCTION.md`](21-PLAN-TO-PRODUCTION.md) and
> mirrored here, so one item cannot be worked twice or dropped silently. *A membership list shrinks
> every time the work succeeds; an invariant does not — so this list carries ids, not a count.*

| id | item | ⛔ what it costs to leave open | gate |
|---|---|---|---|
| **`R1`** | **DECISION #5** — the spend limit vs `GENIOS_L4_LLM_DECISION_MAKER` | ⛔ **no card since 2026-09-25 11:09 UTC.** Recommendation **B** (`false`) now, **C** as a unit, **A** when affordable | ⛔ **PHASE 0** |
| **`R2`** | **activation** — turn **Admin** on for one tenant | ⛔ the lower half of the stack runs correctly over an **empty queue**, which proves nothing. Five switches: `l1_semantic_activation`, `l2_v2_activation`, `l3_activation`, `l4_activation`, `pattern_activation` | ⛔ **PHASE 0** |
| **`R3`** | ⛔⛔ **ADR-10** — the Adaptive representation | ⛔ **Until it is ratified, do not let anybody "fix" `feedback/units.distinct_days`** — that constant is the only thing keeping an auto-promoted durable ADAPTIVE write closed, and the obvious repair opens it. Sizing query is in the tripwire's mover |
| **`R4`** | ⛔ the correction / preference **SURFACE** | Atlas L7's own **P1**. `learning_event_inbox` is written in production and loaded into every weekly batch; **no unit consumes it**, because a `kind` is a surface and there is none |
| **`R5`** | ⛔ the **MACV writer** | `macv_ledger` is the number the customer verifies, and it is referenced only by the delete list |
| **`R6`** | `api/brain_routes` — a seat principal | the route depends on `get_current_org` and has **no caller identity**; `AuthCtx` carries `email`/`seat_id`. Safe today only because every durable producer declares an open scope |
| **`R7`** | Atlas `#6` — should a reset **fail promotion**? | blocking promotion after every reset would stop learning for a tenant that merely **seated a teammate** (`seat_joined` calls the same function) |
| **`R8`** | **`U6c` / `U6d`** (L4) | does `CREATED` belong in a state set · ⛔ **how many warnings a day should a founder see** — blocks the preventive push, *"the vision's USP"* |
| **`R9`** | ⛔ does **`scripts/` count as a caller**? | flag is already `True` **on my call**, recorded as such. 147 → 123 scope. ⛔ On 2026-10-02 it caught a real failure in my own declaration — **recommendation: ratify it** |
| **`R10`** | **ConfidenceVector axes** (L2 `S7`) | code's six vs the Atlas's six, **2 of 6** overlap. ⛔ Recommendation: **keep the code's six and correct the Atlas** — `identity → authority` is not a rename, it is a different measurement. Blocks M13, not M11 |
| **`R11`** | **`L2-08`** — should the `draft` objects gate? | an Atlas cell and a corpus question |
| **`R12`** | who owns the **5 unrouted L2 types** | 3 of 5 are not obviously Admin's. ⛔ **Visibility is ours; ownership is yours** |
| **`R13`** | a **clamp** on the stored policy floor | `load_or_seed_policy` takes every column verbatim and `0045` has **no CHECK**; `LearningPolicy`'s docstring claimed the opposite and is corrected. A clamp changes what **every** tenant admits |
| **`R14`** | move the **reset clock** into `contracts/` | the honest fix for a duplication the layer topology forces — same as `feedback/consumer.py` → `contracts/learned_state.py` |
| **`R15`** | ⛔ the three tables that survive a **`/reset`** | `agent_metering`, `delivery_rate_windows`, `domain_requests` are in neither declared list. Our read: they probably **should** survive — then they belong in `RETAINED_AFTER_ERASURE` **with that reasoning**. → `HANDOFF-HARSH.md` §H8.4 |

## ⛔ Data gaps (2)

| id | item | ⛔ what it unblocks |
|---|---|---|
| **`D1`** | the reporting line — `org_seats.manager_seat_id`, or a dated `reports_to` | ⛔ **124 day-7 escalations have never fired** |
| **`D2`** | one in-force authority rule with an approver | ⛔ **794 actions, 410 want `requires_approval`, `authority_rules` has ZERO rows.** Also unblocks `U2b` |

## And one thing only you can do

| id | | |
|---|---|---|
| **`P`** | ⛔ **`git push origin speedrun008`** | **17 commits, working tree clean, suite 15,220 passed · 0 failed.** `git push` is refused for me by the auto-mode classifier and the refusal covers later turns, tools and sub-agents — **so it is not retried or worked around.** You run it |

## ⛔ Four read-only queries that are yours

All inside `set transaction read only`, and ⛔ **never** `GENIOS_ALLOW_PROD_WRITE` to run a report.

```sql
select from_state, to_state, count(*) from learning_transitions group by 1, 2;
select brain, count(*) from learned_brain_entries group by brain;
select revision, blocked_targets is null, blocked_subject_prefixes is null from learning_policies;
-- ⛔ the one that sizes R3 (ADR-10), answerable only because S6 built the ledger:
select unit, result_state, sink_reason, count(*) from learning_object_evaluations
 where unit = 'recommendation_learning' group by 1, 2, 3;
```

---

# ⛔ ROHIT'S — the original eight, kept for the record

## The original table, as it stood on 2026-10-01

## Decisions (5)

| | Decision | What it costs to leave open |
|---|---|---|
| ⛔ ~~**STEP-16**~~ | ~~should a per-recipient hourly ceiling exist?~~ | ⛔⛔ **WITHDRAWN 2026-10-01 — there was no decision.** One already exists and is live: `timing.py`, 3/hour, **deferring**. `rate_limiter.py` is its **race-free** version, and the race **cannot happen today** (one uvicorn process, `max_workers=1`). **A** and **B** were both wrong; **C** was already what the code said. **Your attention was spent on a question I manufactured by reading one module.** Full retraction: `layer-5-delivery/STEP-16-WITHDRAWN-the-hourly-ceiling-already-exists.md` |
| ⛔ **DECISION #5** | the Anthropic spend limit vs `GENIOS_L4_LLM_DECISION_MAKER=true` | **No card has been produced since 2026-09-25 11:09 UTC.** Recommendation **B** (`false`) now, **C** as a unit, **A** when affordable. ⛔ The DEFER is *declared* — it is not a defect in `executive/` |
| **U6c** (L4) | does `CREATED` belong in a state set? | a product question; `is_terminal`/`is_open`/`is_live` are three spellings of one closed table and answering for one while two disagree is how the set drifts |
| **U6d** (L4) | **how many warnings a day should a founder see?** | blocks the preventive push — *"the vision's USP"* exists and has to be requested. ⛔ Same shape as STEP-16 |
| **L2-08 / the 97 `draft` objects** | should they gate? | an Atlas cell and a corpus question |

## Data gaps (2)

| | Item | What it unblocks |
|---|---|---|
| **the reporting line** | `org_seats.manager_seat_id`, or a dated `reports_to` responsibility | ⛔ **124 day-7 escalations have never fired** |
| **one in-force authority rule with an approver** | — | ⛔ turns the *unattributed-approvals* receipt green. **410 of 794 actions carry `requires_approval` against ZERO rows in `authority_rules`** |

## ⛔ ONE ONE-LINE POLICY CALL — and `STEP-17` waits on it

| | Question | What I measured |
|---|---|---|
| ⛔ **does `scripts/` count as a caller?** | a function whose only caller is an ops CLI currently reads as *unreached* | **13 of the 147** are rescued by counting it, and **every one is a diagnostic or ops read** — `unit_health` ×5, `uncited_lanes` ×2, `slice_weight` ×2, `l2_activation`, `stage_timer`, `journey`, `lane_health`. ⛔ **My recommendation: yes** — `tests/` is excluded because nobody runs a test to learn something about production, and **a script an operator runs is exactly that.** But it is a policy that applies to all eleven packages, so it is yours |

⛔ **Seven of those thirteen are a package's own declaration-module helpers** and would be
self-excluded anyway, so this call genuinely resolves **six**. The scope is **147 → 123** either way.

## And one thing only you can do (1)

| | |
|---|---|
| ⛔ **push** | every commit of this programme is local. `git push` is refused here by the auto-mode classifier, and the refusal explicitly covers later turns, tools and sub-agents — **so it is not retried or worked around.** You run it |

Also open and **not blocking anything**: the **709 `low_relevance` parks**.

---

# ⛔ HARSH'S — six items, and the first one is breaking writes

| | Item | What it unblocks |
|---|---|---|
| 🔴 **H1** | apply migrations **`0186`–`0190`**, in order, in one window | ⛔ **`insert_card` FAILS ON WRITE without `0190`** — masked only because no signal has been routed since the spend limit. **Clearing one without the other turns a silent outage into a loud one.** Also: the *lane* receipt moves from **ERROR** to a real answer (`STEP-12`) |
| 🔴 **H2** | the OCR stack — `pytesseract`+`Pillow` in requirements **and** `tesseract-ocr` apt in the image, **both together** | 1,696 rows become readable; an L1 receipt can go green |
| 🟠 **H3** | widen the pilot backfill window 60 → 365 days | benchmark prompts P3 and P4 become answerable at all |
| 🟠 **H4** | a writer for `deal.status` | `core.relationship` → `core.impact` → `cost_vs_benefit`, a four-deep chain |
| 🟡 **H5** | an approval-workflow source | 6 fact paths, 2 units |
| ⛔ 🟠 **H6** | **run `pytest tests/test_delivery_spine.py -q` where a database exists** | ⛔ **NEW 2026-10-01.** Four tests give `spine.recover_expired_claims` its **first tests ever**; they **skip here** because no DB is configured. **A skip is not a pass.** One command, no deployment. Any failure is a **real finding**, not a regression — the function has never run |

⛔ **H6 is the only item on this page that changes what we KNOW rather than what production does.**

---

# ⛔ BLOCKED — mine, each waiting on somebody above

| | Item | Blocked on |
|---|---|---|
| **U2b** | the approver column + contract field + wiring | ⛔ **H1** *and* an in-force authority rule |
| **U6b** | move `is_terminal` to `contracts/execution` | ⛔ nobody asked — it changes a public boundary |
| **STEP-12** | the lane receipt cannot run | ⛔ **H1** (`0190`) |

---

## WHERE THE PROGRAMME STANDS

    full suite      14,768 tests · 0 failed        (14,534 when YCW27 began)
    receipts        35      L5: 5   L4: 7          lines per L5 guard: 4,715 -> 1,886
    ⛔ CORRECTED 2026-10-02 — "L5" is a LABEL, not a package. deliver/ holds 8 receipts
    ⛔ (4 labelled L5 + 4 labelled L6) = 1,252 lines per guard. 4,715 was never true.
    declared        deliver/ 22  ·  executive/ 10 + 4 PULL_ONLY
    KNOWN_UNWIRED   ⛔ 0 — deliver/ has no known-unwired defects left
    Atlas scorecard 45 claims · 7 superseded · 1 OMISSION · 4 imprecise

**L5 closed 14 steps on 2026-10-01.** ⛔ **Every one of them had its premise corrected by its own
first measurement** — which is the plan working, not failing:

| Step | Planned | ⛔ Measured |
|---|---|---|
| 05 | 4 unreached, one table | **24**, three kinds |
| 13 | *"nothing changes in L4"* | **five more** missing, and a wholly unreached module |
| 14 | three unwired functions | **one** — two take no data at all |
| 06 | *"the cutover has no measurement"* | it has one, under a name I did not search for |
| 07 | two stale comments | **four**, one inside the test that guards the behaviour |
| 08 | *"wire it"*, one line | one line needing **two** decisions |
| 09 | *"wire it or declare it"* | a **three**-part unit; neither candidate sink was right |
| 15 | *"bound it on `expires_at`"* | ⛔ **the bound would have caused harm — retracted** |
| 10 | four receipt candidates | **two of five could not fail** |
| 11 | *"a document correction, not code"* | plus a cross-layer break two targeted runs had missed |

⛔ **Three fixes retracted across the programme because they would have caused harm** — L4's F9 and
F10, and L5's `expires_at` bound. **All three were caught by reading the thing being changed before
changing it.**
