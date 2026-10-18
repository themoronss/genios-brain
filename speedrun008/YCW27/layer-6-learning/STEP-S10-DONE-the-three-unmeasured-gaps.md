# `S10` DONE — the three gaps nobody had measured, and a trap with no tripwire

**The last unit of `M14.C2`.** Atlas Layer 7 **#3** outcome reconciliation · **#5** permitted-use
propagation · **#6** company reset. Plan: [`09-PLAN-S10-the-three-unmeasured-gaps.md`](09-PLAN-S10-the-three-unmeasured-gaps.md).
Pinned to the Atlas v2 source
`Rohit_Updates/Secret War Updates/07-Layer-7-Learning-Atlas-6/03-Current-Successes-Failures-and-Expected-Behavior/README.md`.

⛔ **These three were marked *"not measured"*, so there was nothing to plan against until they
were.** The measurement came first and the plan is derived from it — *a plan derived from the code
alone cannot find a gap the code is silent about.*

```
Atlas Layer 7 after S10    5 CLOSED · 6 PARTLY · ⛔ 0 LIVE · ⛔⛔ 0 UNMEASURED
                           ⛔ none of the three became CLOSED, and that is the honest answer:
                           each has one clause left and every one of them is Rohit's
new tests                  69   (U10c 16 · U10b 37 · U10a 16)
mutations                  27 actionable caught · 0 survived   — after FOUR guard repairs
                           + 1 negative control that correctly survived
receipts                   40 -> 41 · feedback/ correctness 5 -> 6
declarations               +11 (4 permitted-use · 1 blocked-path · 5 unreached · 1 arithmetic)
corrections               ⛔ 5 — two of them MINE, one of them a contract docstring
full suite                15,182 passed · 1,067 skipped · 152 xfailed · 0 failed
                          ⛔ 15,112 + 69 new + 1 (the 41st receipt's parametrised case)
```

---
## `U10c` · Atlas #6 — company reset

### ✅ Three claims measured, and one the Atlas does not credit

| Atlas clause | Verdict |
|---|---|
| *"reset makes only Runtime inactive / truncates its expiry"* | ✅ `reset.py:70` updates `temporary_memories` and names no other table |
| *"leaves all durable rows byte-for-byte active"* | ✅ the statement never touches `learned_brain_entries` |
| ⛔ **the reset PROPAGATES — unlisted in the Atlas** | ✅ `deliver/outbox.py:1050-1068` reads the latest reset at SEND time, compares it with the card's `created_at`, and cancels with *"org corrected its identity after this card was built"* — on the **same connection under the same locks** as the authority re-proof, and **fail-closed-to-send** on an unreadable table (*"an outage of the reset log must not become a delivery outage"*) |
| *"fails promotion until a separate governed supersession"* | ⛔ **not implemented** — nothing in `feedback/` reads `organization_resets`. **Rohit's** |

⛔ The propagation claim lived in a comment at `routes.py:5293`. It was **read, not trusted** —
*a stale comment reads as a measurement*, and this one happened to be true.

### ⛔ The candidate that retired before it was written down

Two of `apply_organization_reset`'s three callers are **seat lifecycle, not pivots** —
`seat_corrected` and `seat_joined` — and the function expires **every** active lease in the org
with no seat filter. ⛔ **Both call sites justify it in writing**, and the reasoning holds:

> *"a memory formed under a wrong 'us' set was formed about the wrong world"* · *"ONLY A MATERIAL
> CHANGE COUNTS… a double-click on a form is not a pivot"*

> ⛔ **Read the call site's own justification before calling a call site a defect.** The mirror of
> *a call site that looks DEAD is not a dead feature.* This would have been the sixth retraction.

### ⛔⛔ The finding, and it was mine

`feedback_health.UNREACHED["reset.latest_reset_at"]` said:

> *"**A function that names its reader and has no caller is a surface that was never built**, not a
> helper somebody forgot."* · *"MOVES WHEN a surface shows an org's reset history — the natural
> caller, and it does not exist."*

⛔ **The reader exists. It is one layer DOWN, and it may not import upward.** `LAYERS` gives
`deliver` 6 and `feedback` 7, so `deliver → feedback` is the import
`tests/test_layer_topology.py` fails the build on — the query is **reimplemented** there instead.
**The duplication is forced by the topology, not an oversight**, and the declaration said the
opposite because *it looked for a caller inside its own package*.

⛔ Third instance in this programme of *the most expensive stale comment is the one that explains
why something was left undone* — and the same decoy-seam shape `contracts/learned_state.py` had
already fixed one layer over: *"a consumption contract that only the producing layer may import is
a decoy seam; the vocabulary belongs in `contracts/`."*

### The repair · `tests/feedback/test_the_reset_clock_is_read_one_layer_down.py` · 16 tests

⛔ **The SQL is read from the AST, never the file text** — and that is not pedantry here:
`outbox.py:1038` carries the comment *"it never read `organization_resets`"*, so a text search
would have been satisfied by **the sentence that says the opposite of what is being asserted**.
Three parametrised cases prove the extractor rejects a comment, a docstring and a plain constant,
and one proves it still finds the real thing inside `text(...)`.

The guard also pins: the two copies ask the **same question** (clause order, not bytes) ·
`LAYERS["deliver"] < LAYERS["feedback"]` · `outbox.py` imports nothing from `feedback` ·
every path the declaration **cites** exists on disk · the cancel reason is **named** ·
and ⛔ no module in `feedback/` has started reading `organization_resets`, so the day Atlas #6's
*"fails promotion"* clause is wired, it is wired deliberately.

### ⛔ One mutation SURVIVED, and the reason is a rule

`M2b` deleted *"the duplication is forced by the topology"* and the guard stayed green: it asserted
`"topology" in why`, and the word was still present **inside the cited path
`tests/test_layer_topology.py`**.

> ⛔ **Assert the PHRASE, not the word.** *A file's NAME can be the counter-evidence* — here it was
> the false witness. Repaired to `"forced by the topology" in why`, and `M2b` is now caught.

⛔ `M2d` removed only the citation and stayed green — **correctly**: the mechanism is asserted
executably by `test_the_upward_import_is_illegal`, so the declaration is free not to cite anything.
It is **not** free to cite something that is gone, which is now its own test (`M6` catches it).

**Mutations: 8 caught · 0 survived** (one survived, was repaired, and is caught) · 1 anchor not
applied and re-run rather than rounded up.

---

## `U10b` · Atlas #5 — permitted-use propagation

### ✅ The enforcement path is PROVEN — the Atlas's "unmeasured" is now measured

| Reader of a brain sink | Carries visibility | Enforces |
|---|---|---|
| `packs/compiler/runtime_brains` → L3 package → **rendered rationale** | ✅ | ✅ `_visibility_allows_package` is wired into a **live** exclusion: scope narrowness **and** `set(package.principals) <= set(entry.principals)` — the whole audience, not one viewer |
| `contracts/learned_state.snapshot_all` (`reason/runner.py:814`) | ✅ | ✅ fail-closed on every axis, ⛔ **including an unknown scope** |
| `contracts/learned_state.snapshot` | ✅ | ✅ — no live caller, already declared |
| ⛔ `api/brain_routes` — the dashboard Brain page | ❌ | ❌ |
| `api/learning_routes.brains` · `packs/brains/adaptive_lease` | ❌ | ⚠️ **metadata only** — neither select has a `value` |
| `feedback/publisher` | ❌ | ✅ **it compares, it never shows** — the byte-identical idempotency read of the row it is superseding |
| `feedback/org_rule_ingest` | ❌ | ✅ **open by construction** — `brain='organization'`, and `org_discovery` declares `ORGANIZATION` |
| `packs/brains/behavior_distill` | ❌ | ✅ **decay of its own output** — it re-reads what it published to RETRACT it; a filter here would leave a constrained row active forever, causing the harm it looks like it prevents |

### ⛔ The one unguarded reader is UNREACHED — and that IS the finding

```
behavior_distill :659   Visibility(scope=ORGANIZATION)
adaptive_lease   :257   Visibility(scope=ORGANIZATION)
org_discovery    :530   Visibility(scope=ORGANIZATION)
units.py         :377   Visibility(scope=PRIVATE)  ← the ONLY one, and target=METRICS
                                                      → learning_metrics, which no brain reader selects
```

⛔ **The two facts are only safe together**, so they are declared together
(`CONSTRAINED_DURABLE_PROPOSALS` ⇄ `UNFILTERED_BRAIN_READERS`) and the day either moves the build
names the other. **The repair is Rohit's**: `brain_routes` has no caller identity at all —
`get_current_org` returns an org string while `AuthCtx` carries `email`/`seat_id`.

### ⛔⛔ And the half no code guard can reach — so it is a RECEIPT

The human approval path rehydrates a persisted proposal: `Visibility(scope=vis.get("scope"),
principals=...)` read back from `learning_objects.visibility`. ⛔ **No amount of AST reading can
know what is in that column.** Receipts **40 → 41**, `feedback/` correctness **5 → 6**:

> *"no active brain value is narrower than the surface that renders it"* · `expect(0) is True`

⛔ The open set is **derived** through `VisibilityScope`, never spelled, and a **NULL** scope counts
— an unrecorded scope is not an open one, the same reading `learned_state._visible` takes.

### ⛔⛔ One fragility underneath BOTH paths, and it was unguarded

The enforcement only runs after `Visibility.model_validate` succeeds — and that is kept alive by a
**two-entry alias table**, `_L6_SCOPE_ALIASES = {"organization": "org"}`, because
`contracts/learning.VisibilityScope.ORGANIZATION` is `"organization"` while the compiler's model
names the same scope `"org"`. **No test guarded the bijection.**

⛔ `runtime_brains`'s own docstring records what the last failure of that exact shape cost:
*"A SILENT TOTAL LOSS … the situation was counted as `error` and its package — the whole package,
not just the brain slice — was never built"*, and *"two defects in series, the second hidden behind
the first."* A new `VisibilityScope` member with no alias reproduces it exactly.

⛔ **And it bit inside this very step**: my own test failed at collection with
`module 'contracts.visibility' has no attribute 'ORGANIZATION'` — I wrote the learning vocabulary
into the compiler's model. The reason is recorded at the line where it bit.

### ⛔ Two mutations SURVIVED. Both were my guard, not the code.

| | What survived, and the rule |
|---|---|
| `M2` | adding `e.visibility` to **one** of `brain_routes`'s **two** value queries. `stale_unfiltered_readers` required **ALL** reads to carry it. ⛔ **`any`, not `all`** — a declaration describes *specific queries* and is already partly false when one changes. The same mistake in reverse as S8's *"removed one marker while two remained in the window"* |
| `M4` | `if False and not _visibility_allows_package(...)`. My test asserted the name appeared among called functions — **and under `if False` the call is still syntactically there.** ⛔ *A call site that looks wired is not a wired call site*, and a guard that passes while the feature is dead reads as coverage |

⛔ `M4`'s repair began by **measuring whether the suite already caught it**: it does —
`tests/test_domain_expertise_compiler.py::test_runtime_brains_are_relevant_tenant_scoped_and_visibility_safe`
builds a `private_preference` entry on production fixtures and asserts it is excluded. **My AST
check was a weaker duplicate.** It now asserts the gate is the *whole* condition of an `if` whose
branch *excludes*, and `M4`/`M4b` are both caught.

**37 tests · mutations 11 caught · 0 survived**, after two guard repairs.

---

## `U10a` · Atlas #3 — outcome reconciliation

### ✅ Two of the Atlas's three acceptance clauses were already CLOSED

| Clause | Verdict |
|---|---|
| *"same external event is counted once"* | ✅ `migrations/0041_l5_execution.sql:248` — `unique (org_id, execution_id)` named `execution_outcomes_once`, commented **in Layer 7's own words**: *"A commitment ends once; a second row would double-count it in every precision calculation Layer 7 runs."* The Atlas's *"duplicate execution outcomes can inflate support"* is **forbidden by the database** |
| *"unknown outcome stays neutral"* | ✅ `label_class` + `counts_against_the_play`, one shared table; `neutral` **and** `unknown` land in `neutral`, and `graded = succeeded + failed` keeps them out of the confidence denominator |
| *"one canonical outcome ID joins the chain"* | ✅ `0072_counterfactual_ledger` — gap #7, closed earlier |

### ⛔⛔ The finding: a trap, and the obvious repair is what springs it

Six units pass `distinct_days=1` as a **hardcoded constant**. Five are harmless — `validate_learning`
returns `(True, "artifact")` for `METRICS` and `KNOWLEDGE_SUGGESTION` before any gate runs:

```
:173 feedback_learning         METRICS               bypassed
:285 outcome_analysis          METRICS               bypassed
:368 actor_outcome_analysis    METRICS               bypassed
:498 recommendation_learning   ⛔ ADAPTIVE            GATED — 1 < min_distinct_days (default 2)
:535 performance_optimization  METRICS               bypassed
:569 knowledge_evolution       KNOWLEDGE_SUGGESTION  bypassed
       …and unit_pattern_learning passes len(g["days"]) — the shape the fix would copy
```

⛔ `orchestrator.run_learning` runs **`validate_learning` FIRST** and `continue`s, so `preflight`
and `govern` **never see the object**:

```python
ok, reason = validate_learning(obj, policy)
if not ok: held += 1; _record_evaluation(..., result="held", sink=reason); continue
gate = preflight(obj, policy, now=now)      # never reached
decision = govern(obj, policy)              # never reached
```

⛔⛔ **So `DURABLE_FROM_A_MEASUREMENT`'s declared authority violation — mine, from `S1` — is
UNREACHABLE under the default policy.** It is not wrong about the code's *shape*: the unit really
does route a measurement into an auto-promoted durable brain the compiler reads back to the
recommender. It was **silent on whether the path is open**, and it is not. Corrected in place.

> ⛔⛔⛔ **AND THAT MAKES THE OBVIOUS REPAIR DANGEROUS.** Measuring `distinct_days` properly is
> correct for the five siblings, is what `unit_pattern_learning` already does, and the data is in
> hand — `closed_at` is loaded and `outcome_analysis` already derives `first`/`last` from it.
> **A future engineer making that obviously-correct fix would silently unblock an auto-promoted
> durable ADAPTIVE write that trains the recommender on its own score.**

### ⛔ Three things would each open it — and all three are asserted

1. **the constant becoming a measurement** — `M1` proves the tripwire fires on exactly that;
2. ⛔ **a stored revision with `min_distinct_days = 1`.** `load_or_seed_policy` assigns the column
   **verbatim** with no clamp, and `migrations/0045` gives the columns DEFAULTS with **no CHECK** —
   the only locked constraint on that table is `learning_policies_knowledge_review_locked`;
3. **`validate_learning` moving after `govern`**, which would let governance promote first.

⛔⛔ **And `LearningPolicy`'s own docstring claimed the opposite** — *"Defaults are protective; a
tenant can only narrow them"* — which **nothing enforces**, in either the loader or the schema.
Corrected, with the reason it matters more than a loose floor. It is latent only because there is
no policy-write surface, the same shape `load_or_seed_policy` already records for the prohibition
lists: *"the moment a policy-write surface exists it becomes a silent authority hole."*
**Fourth stale protective claim this programme has had to correct.**

### ⛔ A second gate behind the first, declared so neither direction surprises anybody

`confidence_bp = efficacy_bp` against `min_confidence_bp = 6000` — a play needs ≥60% efficacy after
the attention discount. **Fixing `distinct_days` alone does not necessarily open the path.**
*A gate that is always red is a gate nobody reads*, and two in series is how the first gets removed
by somebody who never saw the second. The tripwire asserts both, **and** asserts that with both
cleared the path **is** open — a guard has to be honest about what it is protecting.

### ⛔ A sharper query for Rohit than `S1` gave him, and `S6` is why it exists

```sql
set transaction read only;
select unit, result_state, sink_reason, count(*)
from learning_object_evaluations
where unit = 'recommendation_learning'
group by 1, 2, 3;
```

Every row `held / insufficient_distinct_days` ⇒ the durable ADAPTIVE path has **never once** been
exercised and the blast radius of ADR-10 is **zero**. `select brain, count(*) from
learned_brain_entries group by brain` answers *whether*; **this answers why not.**

⛔ And the refusal is **misnamed rather than unnamed**: `insufficient_distinct_days` reads as *"not
enough evidence yet"* when the truth is *"this unit passes a constant"*. Declared in
`BLOCKED_BY_ARITHMETIC` so the ledger can be read correctly.

### ⛔ And the THIRD acceptance clause — measured, and it is not applicable yet

*"correction retracts derived proposal."* ⛔ **No durable proposal is derived from a card
correction**, so there is nothing for a correction to retract: every unit that reads
`card_feedback_verdicts` targets `METRICS`, and the three durable producers derive from trend
facts and leases. ⛔ `behavior_distill` **does** retract — a lapse proposal (`active=False`) through
the same floors, *"the retraction is itself evidence"* — and `api/learning_routes.rollback` is the
human path.

⛔ **So the clause is blocked behind Atlas #1**, the correction SURFACE that does not exist — the
Atlas's own P1 and Rohit's. **`#3` is therefore PARTLY CLOSED, not CLOSED**, and saying so is the
point: two clauses are closed by a database constraint and a shared label table, and the third
cannot be closed by this layer at all.

**16 tests · mutations 8 caught · 0 survived** (`M9` removed only the provenance sentence, which
the guard deliberately leaves free — the runnable query, the thing a reader acts on, survives).

---

## ⛔⛔ A fifth correction, found by a guard I had just written

`tests/feedback/test_one_l6_admission_sequence.py::test_only_the_publisher_writes_a_brain_entry`
asserts *"only the publisher writes a brain entry"* by scanning **every engine LINE** for
`insert into temporary_memories`. It went red on a **comment in `target_policy.py` that I wrote
twenty minutes earlier**, explaining the difference between a writer and a reader by quoting the
publisher's own insert.

> ⛔ **Fourth instance in one session of a text-level guard breaking on the sentence that documents
> the thing it forbids.** The docstring rule from `S9` is in `tests/README.md`; this guard predates
> it.

⛔ **And the line scan had the opposite hole, which is the one that mattered:** a write split across
two source lines — `text("insert into " "temporary_memories (")` — is **one** SQL literal and
**two** lines, and the scan never sees the concatenation. **A second lease writer could have
shipped invisibly by being formatted.**

⛔ So the guard moved to `target_policy.sql_literals`, one shared extractor replacing two local
copies, and the repair is **strictly stricter** — proven, not asserted:

| mutation | result |
|---|---|
| a second lease writer **split across two lines** | ✅ **CAUGHT** — the old scan missed this |
| a second lease writer on one line | ✅ CAUGHT — no regression |
| ⛔ prose *about* the insert | ✅ **correctly SURVIVES** — the negative control that proves the fix is not just "make my build pass" |

> ⛔ **A guard changed to make your own build pass needs a negative control.** Without the third
> row this is indistinguishable from weakening a verify.

---

## The paperwork that came with it

⛔ Five new public functions in `feedback/` were unreached and undeclared, and
`test_every_unreached_public_function_is_declared[feedback]` said so — **the declaration pattern
doing exactly its job on its own author.** Declared with reasons and movers.

⛔ And `feedback_health`'s opening paragraph said *"NINE OF THE TWELVE"* and *"`target_policy`'s
seven"*. `S10` added five entries and made **both** wrong in one commit — the second time that
paragraph has gone stale **by succeeding**. ⛔ **The counts are gone rather than updated**, because
the guard asserts a SET and the paragraph already says so. *A hardcoded count in a document is
wrong the next day.*

---

## Doctrine

| Rule |
|---|
| ⛔ **read the call site's own justification before calling a call site a defect** — the mirror of *a call site that looks DEAD is not a dead feature* |
| ⛔ **assert the PHRASE, not the word** — *a file's NAME can be the counter-evidence*, and here `test_layer_topology.py` was the false witness |
| ⛔ **a citation is a claim, so check it** — every path a declaration cites must exist |
| ⛔ **`any`, not `all`** — a file-wide predicate cannot answer a per-query question |
| ⛔ **a call that is syntactically present is not a call that is made** — `if False and f()` defeated a called-names guard |
| ⛔ **before repairing a guard, measure whether the suite already catches it** — mine was a weaker duplicate of a real behavioural test |
| ⛔ **a guard changed to make your own build pass needs a negative control** |
| ⛔ **a resolver must report its COVERAGE beside its verdict** — and must not read a WRITE as a READ |
| ⛔ **the obvious repair can be the dangerous one** — declare the blocked path, do not open it |
| ⛔ **two gates in series: declare both**, or the first gets removed by somebody who never saw the second |
| ⛔ **a protective claim nothing enforces is the kind that gets built on** |
| **a counted refusal can be MISNAMED rather than unnamed** |
| **the counts come out of the prose, not updated in it** |

---

## ⛔ What is Rohit's, out of `S10`

| | |
|---|---|
| ⛔⛔ **ADR-10, the Adaptive representation** | and `S10` hands it the measurement: `select unit, result_state, sink_reason, count(*) from learning_object_evaluations where unit = 'recommendation_learning' group by 1, 2, 3`. All rows `held / insufficient_distinct_days` ⇒ blast radius **zero** |
| ⛔ **`api/brain_routes` and the seat principal** | the route has no caller identity; giving it one is an API contract change for the dashboard |
| ⛔ **Atlas #6's *"fails promotion"* clause** | `feedback/` reads `organization_resets` nowhere, and blocking promotion after every reset would stop learning for a tenant that merely seated a teammate. Guarded so the day it is wired, it is wired deliberately |
| **a clamp on the stored policy floor** | real improvement, and it changes which proposals **every** tenant admits |
| **moving the reset clock into `contracts/`** | the honest fix for the forced duplication, same as `learned_state` one layer over |
