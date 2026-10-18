# L6 · `S10` PLAN — the three gaps nobody had measured

**The last unit of `M14.C2`.** Atlas Layer 7 gaps **#3** (outcome reconciliation), **#5**
(permitted-use propagation), **#6** (company reset). Pinned to the Atlas v2 source:
`Rohit_Updates/Secret War Updates/07-Layer-7-Learning-Atlas-6/03-Current-Successes-Failures-and-Expected-Behavior/README.md`.

⛔ **THE MEASUREMENT CAME FIRST, AND THE PLAN IS DERIVED FROM IT.** These three were marked *"not
measured"*, so there was nothing to plan against until they were. *A plan derived from the code
alone cannot find a gap the code is silent about* — and *the Atlas check comes first.*

---

## 1 · What the Atlas actually asks, verbatim

| Gap | The Atlas's acceptance evidence |
|---|---|
| **#3** | *"Same external event is counted once; unknown outcome stays neutral; correction retracts derived proposal"* — and *"One canonical outcome ID should join recommendation exposure, accepted action, execution, external event, window, and attribution"* |
| **#5** | *"Rejection explains each failed gate; **prohibited evidence never reaches active brain or rendered rationale**"* |
| **#6** | *"reset makes only Runtime inactive/truncates its expiry, leaves all durable rows byte-for-byte active, and **fails promotion** until a separate governed supersession/rollback handles them"* |

---

## 2 · `U10c` · gap #6 — company reset

### ✅ What is true, measured

| Claim | Verdict |
|---|---|
| reset expires Runtime leases only | ✅ `reset.py:70` updates `temporary_memories` and nothing else |
| durable rows byte-for-byte active | ✅ the statement never names `learned_brain_entries` |
| ⛔ **the reset PROPAGATES** | ✅ **the Atlas does not credit this.** `deliver/outbox.py:1050-1068` reads the latest reset at SEND time, compares it with the card's `created_at`, and cancels with *"org corrected its identity after this card was built"* — same connection, same locks as the authority re-proof, and **fail-closed-to-send** on an unreadable table. ⛔ Read, not trusted: the claim was in a comment at `routes.py:5293`, and *a stale comment reads as a measurement* |

### ⛔ The candidate that RETIRED before it was written down

`apply_organization_reset` has three callers, and **two are seat lifecycle, not pivots** —
`routes.py:5302` (`seat_corrected`) and `account_routes.py:521` (`seat_joined`). A seat joining
expires **every** active Runtime lease in the org, with no seat filter.

⛔ **It is not a defect. Both call sites justify it in writing**, and the reasoning is sound:
*"a memory formed under a wrong 'us' set was formed about the wrong world"*, plus *"ONLY A MATERIAL
CHANGE COUNTS… a double-click on a form is not a pivot."*

> ⛔ **Read the call site's own justification before calling a call site a defect.** The mirror of
> *a call site that looks DEAD is not a dead feature.* This would have been the sixth retraction.

### ⛔⛔ The finding, and it is MINE

`feedback_health.py`'s declaration for `reset.latest_reset_at` says:

> *"**A function that names its reader and has no caller is a surface that was never built**, not a
> helper somebody forgot."* · mover: *"MOVES WHEN a surface shows an org's reset history — the
> natural caller, and it does not exist."*

⛔ **The reader exists.** `deliver/outbox.py:1053` asks the exact question the docstring names
(*"has this org pivoted since my evidence was gathered"*) with a byte-for-byte copy of the same
`select created_at from organization_resets … order by created_at desc limit 1`.

⛔⛔ **And it may not call the helper**: `LAYERS.py` gives `deliver` **6** and `feedback` **7**, so
`deliver → feedback` is an upward import `tests/test_layer_topology.py` fails the build on. **The
duplication is forced by the topology, not an oversight** — and the declaration says the opposite.

> ⛔ Third instance in this programme of *the most expensive stale comment is the one that explains
> why something was left undone* — and **this one is mine, written three steps ago.**

⛔ The same shape `contracts/learned_state.py` already fixed one layer over: *"a consumption
contract that only the producing layer may import is a decoy seam; the vocabulary belongs in
`contracts/`, which every layer may read."*

**Repair (mine).** Correct the declaration to the real reason, and add a guard that the two copies
of the query cannot silently diverge.
**Rohit's.** The *"fails promotion"* clause — `feedback/` reads `organization_resets` nowhere, and
blocking promotion after every reset would stop learning for a tenant that merely seated a
teammate. A policy decision, not a tidy-up.

---

## 3 · `U10b` · gap #5 — permitted-use propagation

### ✅ The enforcement path is PROVEN — the Atlas's "unmeasured" is now measured

| Reader of the brain sinks | Selects visibility | Enforces |
|---|---|---|
| `packs/compiler/runtime_brains` → L3 package → **rendered rationale** | ✅ | ✅ `_visibility_allows_package` **is called** (`:363`): scope narrowness **and** `set(target.principals) <= set(source.principals)` — the whole package audience must be able to see the evidence |
| `contracts/learned_state.snapshot_all` (`reason/runner.py:814`) | ✅ | ✅ `_visible` passes open scopes, requires a principal intersection for private/participants, and ⛔ **fails closed on an unknown scope** |
| `contracts/learned_state.snapshot` | ✅ | ✅ — no live caller, already declared in `contract_health` |
| ⛔ `api/brain_routes` — the dashboard Brain page | ❌ | ❌ |
| `api/learning_routes.brains` | ❌ | ⚠️ metadata only — the select has no `value` |
| `feedback/org_rule_ingest` | ❌ | ✅ `brain='organization'` — open by construction |
| `packs/brains/behavior_distill` | ❌ | ✅ ⛔ **decay of its own output**, not evidence: it re-reads subjects it published to retract the unclaimed ones |
| `packs/brains/adaptive_lease` | ❌ | ⚠️ metadata only — no `value` |

### ⛔ The one unguarded reader is UNREACHED, and that is the whole finding

`api/brain_routes._learned_records` renders `value` as a title plus an evidence line, filtered on
`org_id and active and brain = any(('organization','behavior','adaptive'))` — **no visibility
predicate**, and `Depends(_org)` → `get_current_org` admits **any** credential of the org,
including a `member` seat whose own definition in `auth.py:99` is *"reads and acts on the cards
routed to their own seat, **and nothing org-wide**."*

⛔ **But nothing constrained can reach it today:**

```
behavior_distill   :659  Visibility(scope=ORGANIZATION)
adaptive_lease     :257  Visibility(scope=ORGANIZATION)
org_discovery      :530  Visibility(scope=ORGANIZATION)
units.py           :377  Visibility(scope=PRIVATE)  ← the ONLY one, and target=METRICS
                                                      → learning_metrics, which this route never reads
```

> ⛔ **So the defect is LATENT, not live** — and *a guard nobody can exercise is not a repair.* The
> two facts (*every durable producer is open* · *the rendered reader has no filter*) are **only
> safe together**, so they must be declared together and fail the build the day either moves.

**Repair (mine).** Declare the pair; guard it in both directions; add a **correctness receipt**
(`expect(0) is True`) so a constrained row landing in either sink is caught in **production data**,
not only at build time.
**Rohit's.** Whether `brain_routes` should take a seat principal at all — the route has only an org,
and `AuthCtx` carries `email`/`seat_id`. That is an API contract change for the dashboard.

---

## 4 · `U10a` · gap #3 — outcome reconciliation

### ✅ Two of the Atlas's three acceptance clauses are already CLOSED

| Clause | Verdict |
|---|---|
| *"same external event counted once"* | ✅ `migrations/0041_l5_execution.sql:248` — `unique (org_id, execution_id)`, named `execution_outcomes_once`, commented in Layer 7's own words: *"A commitment ends once; a second row would double-count it in every precision calculation Layer 7 runs."* The Atlas's *"duplicate execution outcomes can inflate support"* is **forbidden by the database** |
| *"unknown outcome stays neutral"* | ✅ `label_class` + `counts_against_the_play` — one shared table; `neutral` **and** `unknown` land in `neutral`, and `graded = succeeded + failed` keeps them out of the confidence denominator |
| *"one canonical outcome ID joins the chain"* | ✅ `migrations/0072_counterfactual_ledger.sql` — gap #7, already closed |

### ⛔⛔ The finding: a trap with no tripwire

Six units pass `distinct_days=1` as a **hardcoded constant** into `LearningEvidence`. Five are
harmless — `validate_learning` returns `(True, "artifact")` for `METRICS` and
`KNOWLEDGE_SUGGESTION` before any gate runs. **One is not:**

```
:173 feedback_learning         METRICS               bypassed
:285 outcome_analysis          METRICS               bypassed
:368 actor_outcome_analysis    METRICS               bypassed
:498 recommendation_learning   ⛔ ADAPTIVE            GATED — 1 < min_distinct_days (default 2)
:535 performance_optimization  METRICS               bypassed
:569 knowledge_evolution       KNOWLEDGE_SUGGESTION  bypassed
```

⛔ And `orchestrator.run_learning` runs **`validate_learning` FIRST** and `continue`s on failure —
`preflight` and `govern` never see the object:

```python
ok, reason = validate_learning(obj, policy)
if not ok:
    held += 1; _record_evaluation(..., result="held", sink=reason); continue
gate = preflight(obj, policy, now=now)      # never reached
decision = govern(obj, policy)              # never reached
```

⛔⛔ **So `DURABLE_FROM_A_MEASUREMENT`'s declared authority violation — mine, from `S1` — is
UNREACHABLE under the default policy.** It is not wrong about the code's *shape*: the unit really
does route a measurement into an auto-promoted durable brain that the compiler reads back to the
recommender. It is wrong that the path is **open**. The proposal dies two gates earlier, for a
reason that has nothing to do with Adaptive authority.

> ⛔⛔⛔ **AND THAT MAKES THE OBVIOUS REPAIR DANGEROUS.** Measuring `distinct_days` properly is
> correct for the other five, is what `unit_pattern_learning:411` already does (`len(g["days"])`),
> and the data is in hand — `closed_at` is loaded and `outcome_analysis` already derives
> `first`/`last` from it. ⛔ **A future engineer making that obviously-correct fix would silently
> unblock an auto-promoted durable Adaptive write that trains the recommender on its own score.**

**Repair (mine).** A **tripwire**: assert the arithmetic (`1 < default min_distinct_days`) and that
validation precedes governance, with a failure message that names `DURABLE_FROM_A_MEASUREMENT`.
Correct that declaration to say the path is **blocked by arithmetic, not by design**.
⛔ **Not a fix to `distinct_days` itself** — unblocking the unit changes what the Adaptive brain
contains, which is Rohit's, and this is the fourth time this layer has produced that answer.

**⛔ And a sharper query for Rohit than the one `S1` gave him.** `S6` made it answerable:

```sql
set transaction read only;
select unit, result_state, sink_reason, count(*)
from learning_object_evaluations
where unit = 'recommendation_learning'
group by 1, 2, 3;
```

Every row `held / insufficient_distinct_days` ⇒ the durable Adaptive path has **never once** been
exercised and the blast radius of ADR-10 is **zero**. `select brain, count(*) from
learned_brain_entries group by brain` answers *whether*; this answers *why not*.

---

## 5 · Build order — bottom-up, `U10c` → `U10b` → `U10a`

| | Unit | Artifact | Verify |
|---|---|---|---|
| 1 | `U10c` | `feedback/feedback_health.py` declaration corrected + divergence guard | `pytest tests/feedback/test_the_reset_clock_is_read_one_layer_down.py` |
| 2 | `U10b` | `feedback/target_policy.py` pair declaration + `platform/receipts.py` correctness receipt | `pytest tests/feedback/test_a_constrained_brain_value_is_not_rendered_org_wide.py` |
| 3 | `U10a` | tripwire guard + `DURABLE_FROM_A_MEASUREMENT` corrected | `pytest tests/feedback/test_the_declared_violation_is_blocked_by_arithmetic.py` |

Each unit: mutation-tested, baseline asserted **before and after**, `PYTHONDONTWRITEBYTECODE=1`
with `__pycache__` cleared per invocation. Then the full suite.
