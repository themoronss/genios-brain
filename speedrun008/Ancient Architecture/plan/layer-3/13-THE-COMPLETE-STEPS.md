# Layer 3 — the complete step list

**2026-09-25** · replaces the eight-step draft in [`10-OVERVIEW.md`](10-OVERVIEW.md)
**Grounded in:** [`12-AUDIT-AGAINST-SPECS.md`](12-AUDIT-AGAINST-SPECS.md) and the four specifications

⛔ **The plan was 8 steps. The specs added 12.** Not because the earlier plan was wrong — it covered
the Intelligence Graph correctly — but because it covered **only** that. The four documents describe
**32 components** in the layer, and the audit found the gaps are **at the seams**, not in the
engines.

---

## The five waves, and why this order

| wave | what it buys | steps |
|---|---|---|
| **0 · Vocabulary** | nothing can be annotated until the names are fixed | 2 |
| **1 · Honesty** | ⛔ **stops the claims that destroy trust** — the specs' own P0 | 4 |
| **2 · Time** | ⛔ **the product's entire value** — noticing what did not happen | 2 |
| **3 · Correlation** | *what kind of link is this*, and why one was rejected | 3 |
| **4 · Quality** | `unknown` stops becoming `false` | 2 |
| **5 · Intelligence Graph** | we stop deciding from scratch every sweep | 4 |
| **6 · Read & ship** | ⛔ **the only wave a founder sees** | 3 |

**Waves 1 and 2 come before everything** because the specs' P0 is *"prevent damaging behaviour"* —
and today the two most damaging outputs are **an absence claim from a broken connector** and **a
commitment that goes unnoticed because no mail arrived.**

---

# WAVE 0 · Vocabulary

### L3-00 · Carry the new layer numbering into `LAYERS.py`
**Harsh:** — · **Model:** none · **Migration:** none

⛔ *"Layer 3"* means **Domain Expertise** in **115 files** and **Context Graph** in this plan;
`executive`/`deliver`/`feedback` are **5/6/7** in the code and **4/5/6** in the new list.
`LAYERS.py` already carries three vocabularies and predicted a fourth. Add the column, guard all
four, keep *"always name the package, never the digit alone."*

### L3-01 · Name the Decision Object
**Harsh:** — · **Model:** none · **Migration:** none

The schema already voted: migration 0031 FKs `signals → reasoning_run_outputs(run_id, decision_hash)`.
`DecisionRef`, `DECISION_OUTCOME_KINDS`, `DECISION_SHAPES`, and a test that no module outside `api/`
writes `decisions`. *(L2-1's defect one layer up: fifteen wrong annotations from two names.)*

---

# WAVE 1 · Honesty — ⛔ the specs' P0

### L3-02 · The coverage record
**Harsh:** ⛔ **migration** · **Model:** none
**Specs:** FX-07 · FX-08 · FX-12 · CC-02 · CL-04 · A8 · §3.2

Measured: `coverage` 138 files, `watermark` 25, `backfill` 62 — but
**`pagination_complete`, `sync_health`, `known_gaps`, `observation_interval` do not exist.**

| unit | |
|---|---|
| 02-U1 | `contracts/coverage.py` — `CoverageRecord`, per **(source, predicate)**, not per connector |
| 02-U2 | `SyncHealth` enum with a totality guard; ⛔ **`success_empty` ≠ `failed` ≠ `partial`** |
| 02-U3 | `known_gaps` and `observation_interval` as half-open `[start, end)` |
| 02-U4 | connectors write it; the control-plane interface, not scraping |

⛔ **FX-08 is why this is first:** *"a rate limit produces an empty adapter result instead of an
error."* Today an outage and an empty mailbox are **the same value**.

### L3-03 · `scoped_absence()` — no absence claim without its six ingredients
**Harsh:** — · **Model:** none · **Migration:** none
**Specs:** LCX-13 · LCX-15 · CG-06 · BS-03 · CQ-HCS-05 · BW-04 · §9.3

One pure function, six predicates, refusing by default:

```
expected item · required source · observation interval · adequate permission+pagination
  · healthy watermark through the interval · no qualifying match after identity/period checks
```

Returns `AbsenceVerdict(supported | unsupported | unknown, scope, reason)`.
**The scope sentence is the output**: *"No matching record in the audit register as of T"* —
never *"this document does not exist."*

| unit | |
|---|---|
| 03-U1 | `context/absence.py` — the gate, pure, no clock inside |
| 03-U2 | every existing absence read routed through it |
| 03-U3 | a test that **breaks each of the six** and proves the claim degrades |

### L3-04 · Knowledge time
**Harsh:** ⛔ **migration** · **Model:** none
**Specs:** LCX-02 · CL-02 · CG-09 · TL-04 · TL-09 · LCW-02 · BW-09

Measured: **`recorded_at` appears in ONE file. `source_updated_at` in zero.**

`/graph/as-of` reads `valid_from`/`valid_to` — that is **effective** time. *"What did GeniOS know on
3 September"* needs **knowledge** time, and a late correction can currently make the system look
like it knew earlier than it did.

| unit | |
|---|---|
| 04-U1 | `recorded_at` on nodes/facts/edges, set by the writer, never by a caller |
| 04-U2 | `source_updated_at` + source revision — **ordering, because timestamps do not totally order** |
| 04-U3 | `/graph/as-of?basis=effective\|knowledge` — two queries, two answers, both named |
| 04-U4 | the LCX-02 probe: as-known excludes the correction, current includes it |

### L3-05 · Evidence lineage — copies stop corroborating
**Harsh:** — · **Model:** none · **Migration:** none
**Specs:** ⛔ **CQ-HCS-01** · LCX-22 · CC-27 · CV-03 · RO-10 · DM-08 · FX-27 · §9.7

⛔ **A live defect, not a design question.** The ladder is **one:60 / two:85 / three+:100**, driven
by `src_count`, deduped **per event** — and **ten forwards of one original are ten events.**

`graph_source_refs.independence_group` **is the column meant to stop this and it is unwritten** —
the same class as `freshness_policy_id`.

| unit | |
|---|---|
| 05-U1 | `independence_group` derived from the original assertion, written on every ref |
| 05-U2 | `src_count` counts **distinct lineages**, not refs |
| 05-U3 | ⛔ CQ-HCS-01 as a test: **ten copies cannot move the score**; one real validator can |

---

# WAVE 2 · Time — ⛔ the product's entire value

### L3-06 · Nothing evaluates when nothing arrives

> ## ⛔ CORRECTED — 2026-09-25, during L3-06
>
> **This claim is false and was the loudest in the plan.** Elapsed time is evaluated at FOUR live
> levels: `platform/scheduler`'s **heavy tick runs L1 → L2/L3/L5 for every org every 6 hours**
> whether or not a message arrived; `reason/runner` applies per-rule cooldowns; `executions.
> next_check_at` **is** a registered due instant with a real due query; and
> `age_uncorrelated_situations` retires quiet situations on time alone. **The heavy tick was already
> pinned** by `test_the_heavy_sweep_still_reasons_for_every_org`.
>
> `due_evaluation` and `next_evaluation` do return zero — **they are not the names this system
> uses.** A grep for two invented words found none of a scheduler thread, a cadence in hours, a
> per-rule cooldown and a column called `next_check_at`. See
> [`findings/step-06-the-timer.md`](findings/step-06-the-timer.md).
**Harsh:** ⛔ **migration** · **Model:** none
**Specs:** ⛔ **five documents independently** — LCX-14 · CL-03 · TL-01 · CC-23 · BW-14 · LCW-04 · §5.4

```
due_evaluation  0 files      next_evaluation  0 files

> ## ⛔ CORRECTED — 2026-09-25, during L3-06
>
> **This claim is false and was the loudest in the plan.** Elapsed time is evaluated at FOUR live
> levels: `platform/scheduler`'s **heavy tick runs L1 → L2/L3/L5 for every org every 6 hours**
> whether or not a message arrived; `reason/runner` applies per-rule cooldowns; `executions.
> next_check_at` **is** a registered due instant with a real due query; and
> `age_uncorrelated_situations` retires quiet situations on time alone. **The heavy tick was already
> pinned** by `test_the_heavy_sweep_still_reasons_for_every_org`.
>
> `due_evaluation` and `next_evaluation` do return zero — **they are not the names this system
> uses.** A grep for two invented words found none of a scheduler thread, a cadence in hours, a
> per-rule cooldown and a column called `next_check_at`. See
> [`findings/step-06-the-timer.md`](findings/step-06-the-timer.md).
```

The sweep is event-driven. **A promise due Thursday, with no mail on Friday, produces nothing** —
and noticing exactly that is what the product is for.

| unit | |
|---|---|
| 06-U1 | `next_evaluation_at` on the situation, with the **predicate** that made it due |
| 06-U2 | `context/periodic.py` drains it — ⛔ **a timer is not a fabricated signal** |
| 06-U3 | ⛔ **one revision per crossing.** TL-01: evaluate just before, at, and just after |
| 06-U4 | repeated ticks over an unchanged slice produce **no** new card *(L2-5's `noop`)* |

⛔ **This compounds L3-02/03.** The honest sentence the specs demand —
*"No reply observed in connected email through Friday 09:00"* — needs **the timer AND the coverage
contract**. Until both land, silence is the only honest output.

### L3-07 · The Freshness Manager
**Harsh:** — · **Model:** none · **Migration:** none
**Specs:** LCX-08 · LCX-12 · GE-HCS-05 · CL-05 · CL-12 · CQ-HCS-02 · LCW-03 · §J

`graph_facts.freshness_policy_id` — **zero writers, zero readers.**

| unit | |
|---|---|
| 07-U1 | `FRESHNESS_POLICIES` per claim type, with a totality guard |
| 07-U2 | ⛔ **reinforcement ≠ repetition** — GE-HCS-05: *a forward of a six-month-old delegation must not reset it* |
| 07-U3 | `review_due_at` — ⛔ **review due is not proof of invalidity** (LCX-08) |
| 07-U4 | ⛔ **no double decay** (§J): freshness OR confidence applies the penalty, one owner, recorded |

---

# WAVE 3 · Correlation — *what kind of link is this?*

### L3-08 · The Cross Tool correlator
**Harsh:** — · **Model:** none · **Migration:** none
**Specs:** ⛔ **CT-01…CT-12** · CC-01…CC-06

⛔ **The only correlator with no module — and the only one whose inputs both exist today.**
Gmail ↔ Calendar is the entire two-connector pilot.

| unit | |
|---|---|
| 08-U1 | `correlation_tool.py` — join on **stable references and scoped entities**, never on title |
| 08-U2 | CT-07: **occurrence identity** — one cancelled instance is not a cancelled series |
| 08-U3 | CT-06: one email mirrored into a task and an event is **one origin**, three artefacts |
| 08-U4 | CT-10: ⛔ **a draft is not a send**; an unresolved provider result is not a failure |

### L3-09 · The typed relation vocabulary
**Harsh:** ⛔ **migration** · **Model:** none
**Specs:** §2 relationship vocabulary · CC-35 · DP-06 · BW-07

**5 of 12 exist.** Missing: `same_entity_as` · `responds_to` · `assigned_to` · `requested_from` ·
`scheduled_for` · `fulfills` · `satisfies_condition`.

The seven absent ones carry the product's meaning — `fulfills` is *"did the document satisfy the
requirement"*, `satisfies_condition` is the whole dormant-opportunity feature.

| unit | |
|---|---|
| 09-U1 | `RELATION_TYPES`, closed, **directed**, totality-guarded both ways |
| 09-U2 | ⛔ **`related_to` may never become `blocks`** — a test that the promotion is impossible |
| 09-U3 | CC-35 / DP-06: **co-occurrence cannot produce `causes` or `blocks`** |

### L3-10 · The correlation decision record
**Harsh:** ⛔ **migration** · **Model:** none
**Specs:** §3.3 `correlation_decision_record` · CC-30 · FX-13 · the whole "localize a failure" table

> *"A candidate rejected for wrong audit period and a candidate not retrieved at all are different
> failures."*

**Today they are the same failure: silence.** Grep finds reason codes in exactly two modules —
`proposal_gate.py` and `interpretation_store.py`, both built in L2-5/L2-6.

| unit | |
|---|---|
| 10-U1 | `disposition: accept \| reject \| hold` with `reason_codes` — L2-2's `<check>:<subject>` shape |
| 10-U2 | ⛔ **retrieval truncation is recorded** (CC-30, FX-13) — a top-k miss is not an absence |
| 10-U3 | `next_evaluation_at` on a `hold` — closes the loop into L3-06 |
| 10-U4 | retention-bounded and access-controlled — ⛔ do not keep deleted content for debugging |

---

# WAVE 4 · Quality — `unknown` stops becoming `false`

### L3-11 · Three-valued predicates and the L2.4 verdict
**Harsh:** — · **Model:** none · **Migration:** none
**Specs:** §3.4 · BW-05 · CQ-HCS-07 · CQ-HCS-08 · RO-06 · DM-04

All eight quality concepts exist as scattered reads. **What is missing is one verdict with
reasons.**

| unit | |
|---|---|
| 11-U1 | `Predicate = true \| false \| unknown` — ⛔ **`unknown` must never silently become `false`** |
| 11-U2 | the eight components named, each returning its own finding *(L2-0's `_reason_table` idiom)* |
| 11-U3 | ⛔ **hard blockers are not scoreable** (RO-06): unresolved authority cannot be out-weighed |
| 11-U4 | CQ-HCS-08: a verdict is **bound to its graph revision** and rejected when the revision moved |

✅ **Two halves are already right and stay:** confidence is `MIN` not average, and the model may
**DESCRIBE never SCORE**.

### L3-12 · The four missing graph views
**Harsh:** — · **Model:** none · **Migration:** none
**Specs:** §3.1 eight views · CG-01 · CG-07 · CG-11 · CG-12

`temporal`, `communication`, `resource`, `knowledge` return **zero** files.

⛔ **These are queries, not tables.** A view is a named read over the one logical graph, and naming
them is what stops each caller inventing its own.

| unit | |
|---|---|
| 12-U1 | `context/views.py` — eight named reads, `GRAPH_VIEWS` totality-guarded |
| 12-U2 | CG-11: ⛔ **resource values carry unit, currency and period** — no summing annual with monthly |
| 12-U3 | CG-12: ⛔ **communication activity is not ownership or progress** |

---

# WAVE 5 · The Intelligence Graph

### L3-13 · ~~`intel_nodes` + `intel_edges`~~ → ⛔ **CORRECTED 2026-09-25: the graph already exists**
**Harsh:** none · **Model:** none · **Migration:** ⛔ **none**

> ⛔ **WHAT THIS ENTRY ORIGINALLY SAID, AND WHY IT WAS WRONG.** It asked for five node kinds
> (`situation · decision · delivery · outcome · interpretation`), six edge kinds, closed
> vocabularies and a migration, on the premise that **"no table holds both a situation and a
> decision."** All three load-bearing premises were measured false:
>
> * **`signals` holds both** — `situation_id` (0182) beside `reasoning_decision_hash` (0031,
>   FK'd to `reasoning_run_outputs`). ⛔ **Both were added by `alter table`**, so the scan that
>   produced the premise — which read `create table` blocks — was blind to them by construction.
> * **Nothing deletes a signal.** L3-14's fallback argument (*"it dies when a signal is
>   archived"*) is false: **0** `delete from signals` in the tree, **12** `update signals set
>   status`. Soft-delete only.
> * **The chain does not stop at the decision.** `executions.decision_hash` →
>   `execution_outcomes.decision_hash` make **situation → decision → delivery → outcome already
>   foreign keys** — four of the five node kinds, today.
>
> Two tables would have been a **second copy of a graph the schema already enforces.**

**What the step actually delivered:** `genios_engine/reason/situation_binding.py` — a closed
`SIGNAL_WRITERS` guard over all five writers of `signals`, checked in both directions, reading each
writer's real column list **out of the AST**.

⛔ **And it found the real defect, which is worse and smaller than the one planned: five writers
insert into `signals` and ONE names `situation_id`** — the feature-flagged compiled lane. So the
column is null on essentially every live row and `card_source.classify` calls every main-path card
**UNINTERPRETED**. Wiring it costs nothing (`runner.run()` already has the map in scope for all
three silent lanes) but would assert **co-location as provenance** and corrupt the cutover
measurement. **→ DECISION FOR ROHIT, handoff §1.4.**

See [step-13](step-13-the-graph-already-exists.md) ·
[findings](findings/step-13-the-graph-already-exists.md).

### L3-14 · Lift `about` out of `signals`
**Harsh:** — · **Model:** none · **Migration:** none

The edge **already exists as data**: `signals` carries `reasoning_decision_hash` (0031, FK'd) and
`situation_id` (0182) in one row. It is a delivery table doing a graph's job — ~~it dies when a
signal is archived~~.

> ⛔ **CORRECTED 2026-09-25 (L3-13).** The struck clause is false and it was this entry's only
> argument. **There is no `delete from signals` anywhere in the tree**; every lifecycle transition
> is `update signals set status=...` (`open · acted · expired · resolved`), and nothing purges the
> reasoning spine either. **The edge cannot die.**
>
> ⛔ **What is actually wrong is that the edge is almost never WRITTEN.** Four of the five
> functions that insert into `signals` never name `situation_id`, so it is null on essentially
> every live row. That is not a storage problem and lifting the column somewhere else does not fix
> it — it is the held decision in handoff §1.4, and it is guarded by
> `reason/situation_binding.SIGNAL_WRITERS`.

### L3-15 · `deliver/` and `feedback/` write back
**Harsh:** — · **Model:** none · **Migration:** none
**Specs:** LCX-23 · LCX-25 · LCX-26 · BS-15 · §14

⛔ Today both are **read-only** against the graph. `execution_outcomes` already has seven terminal
labels waiting.
⛔ **LCX-26 is the rule:** *resolution must be possible from verified evidence even if the customer
never clicked.* **A dismissal is not a resolution** (LCX-25).

### L3-16 · Revision — the five-word action and `supersedes`
**Harsh:** ⛔ **migration** · **Model:** none

`insert · noop · restated · reversed · expired`, keyed `(org_id, situation_id, slice_digest)`.
⛔ **`expired` has no Evidence-Graph equivalent** — a fact needs a source to contradict it, a
conclusion goes stale on its own. And there is **no `discrepancy`**: we have no rank over
ourselves, so recency of the slice decides.

---

# WAVE 6 · Read & ship — ⛔ the only wave a founder sees

### L3-17 · ⛔ The history reaches the situation
**Harsh:** — · **Model:** none · **Migration:** none

```
prior_decision 0 · previous_decision 0 · last_decision 0 · past_decisions 0
```

The correlators read the Intelligence Graph, and the BSO arrives carrying
*"decided 3× · ignored · ignored · dismissed."*
⛔ **Steps L3-00 … L3-16 are plumbing for this one.**

### L3-18 · The surface
**Harsh:** — · **Model:** none · **Migration:** none
**Specs:** ⛔ **E2E-12** · FX-37…FX-42 · BS-12 · DM-14 · §14

| unit | |
|---|---|
| 18-U1 | the card line — *"3rd time · dismissed Tuesday"* |
| 18-U2 | the node side-panel summary; ⛔ **never Intelligence on the graph canvas** |
| 18-U3 | the founder count — *of last month's decisions, how many landed* |
| 18-U4 | ⛔ **structured-to-visible equality** (E2E-12): counts, units, scope, polarity, owner, uncertainty, and **draft ≠ sent** |

⛔ **E2E-12 is the case that proves why the other seventeen steps are not enough:** correct
correlation, correct decision, and the rendered card still said *"six investors ignored you."*

### L3-19 · Turn it on
**Harsh:** — · **Model:** none · **Migration:** none

Cutover switches · the scenario registry with a failure class per spec group · nine+ sensitivity
probes · the parity gate. **L2-8's pattern, applied to twenty steps instead of nine.**

---

# Cost

| | |
|---|---|
| **model calls** | ⛔ **zero, in all twenty steps.** L3 is structure, reads and receipts |
| **`vocabulary_fingerprint`** | unchanged — no prompt is touched |
| **re-extraction** | none |
| **migrations** | ~~**7**~~ → **6** — L3-02, L3-04, L3-06, L3-09, L3-10, L3-16. ⛔ **L3-13's migration was deleted on 2026-09-25**: the tables it would have created already exist as foreign keys |
| **row growth** | tens per tenant per week; the slice digest is the defence against the 995 MB incident |

---

# ⛔ If only three steps could be built

| | | |
|---|---|---|
| **1** | **L3-03** `scoped_absence()` | it stops the output that destroys trust fastest — *"no meeting scheduled"* produced by an outage |
| **2** | **L3-06** the timer | without it the product cannot notice what did **not** happen, which is its whole premise |
| **3** | **L3-17** the read | without it every sweep is the first sweep |

**L3-08 (Cross Tool) is the fourth**, and it is the one that makes a two-connector pilot behave like
a product rather than two inboxes.
