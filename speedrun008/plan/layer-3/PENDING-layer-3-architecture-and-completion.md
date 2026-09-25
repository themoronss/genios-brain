# PENDING · Layer 3 — how it works, how it integrates, and what is left

**For: Harsh.** Branch `speedrun008` · written 2026-09-25 · engine code **26/26 steps complete**,
`13,301 passed · 0 regressions`.

> ## ⛔ SCOPE DECISION, 2026-09-25 — READ THIS FIRST
>
> **Only the ADMIN domain is in scope and only Admin gets activated.** Sales and Customer Support
> stay on hold until Rohit says otherwise. Do not activate them, do not fix their drafts, do not
> author against them. Where a number below is three-domain, the Admin-only number is given beside
> it, because they are different and the Admin one is the one that matters.

This file exists so you can pick Layer 3 up without reading twenty findings files. Every number in
it was measured against the tree on 2026-09-25, not remembered. Where something is a claim I could
not verify, it says so.

---

# PART 1 · WHAT LAYER 3 IS

## 1.1 The six layers, and where L3 sits

| layer | what it turns into what |
|---|---|
| **L1 · Signal Qualification** | raw events → qualified signals with scores |
| **L2 · Context** | signals → **business situations** (the Context Graph is the truth) |
| **L3 · Domain Expertise** | a situation → an **ExpertisePackage** — the authored knowledge that applies to it |
| **L4 · Reasoning** | a package → a **Decision Object** |
| **L5 · Executive** | a decision → an **execution** |
| **L6/L7 · Delivery & Learning** | an execution → a **card**, and its outcome back into the system |

⛔ **A numbering trap you will hit.** "Layer 3" means **Domain Expertise** in 115 files, but the
code's directory numbering puts `packs` (Plane D) at 3 and `reason` (Plane R) at 4.
`genios_engine/LAYERS.py` carries the translation table — read it before you trust any number in a
spec document. This was L3-00 and it is the reason that step exists.

## 1.2 The two graphs — the thing people get wrong

| | **Evidence Graph** | **Intelligence Graph** |
|---|---|---|
| holds | what **SOURCES** said | what **WE** concluded |
| tables | `graph_nodes` · `graph_facts` · `graph_edges` + 7 more | `context_situations` → `signals` → `reasoning_run_outputs` → `executions` → `execution_outcomes` |
| visible to a founder | yes — the graph canvas | ⛔ **no, and deliberately** |
| ranks its claims | yes — `authority_rank` | no. **We have no rank over ourselves** |

⛔ **The Intelligence Graph has no tables of its own and must not get any.** This was L3-13. The
plan asked for `intel_nodes` + `intel_edges`; all five node kinds already exist as foreign keys:

```
context_situations.situation_id
  ├→ situation_interpretations.situation_id      (0183)  ← interpretation
  └→ signals.situation_id                        (0182)  ← the delivery join
        └→ signals.reasoning_decision_hash       (0031, FK) ← decision
              └→ executions.decision_hash        (0041)  ← delivery
                    └→ execution_outcomes.decision_hash    ← outcome
```

**Nothing deletes a signal** — 0 `delete from signals` in the tree, 12 `update signals set status`.
So the chain cannot die, and building tables over it would be a second copy of a graph the schema
already enforces.

---

# PART 2 · HOW IT ACTUALLY RUNS, END TO END

## 2.1 The call chain, with real line numbers

```
context/runner.py                    the L2 sweep
      │  writes context_situations, and publishes derived.* facts
      │  (including correlation_history at runner.py:752)
      ▼
reason/domain_shadow.shadow_compile(store, org_id, live_domains=…)      :554
      │  reads every ACTIVE situation
      ▼
packs/compiler/  →  capability_resolver  →  object_resolver  →  knowledge_retriever
      │  picks the capabilities, loads their objects, retrieves their knowledge
      ▼
        ExpertisePackage                        ← THIS IS LAYER 3's OUTPUT
      ▼
reason/adapters/expertise.py                    builds the CapabilityManifest
      │  roster_v2=False → _default_dag()  → 6 units
      │  roster_v2=True  → _roster_specs() → the full family, bound to the corpus's own fields
      ▼
reason/orchestrator + the 23 reasoning units    → ReasoningDecision
      ▼
reason/audit.persist_execution()                → reasoning_runs / _run_outputs
      ▼
reason/domain_shadow._emit_capability_signal()  :327  → a `signals` row carrying situation_id
      ▼
deliver/pipeline.py                             → a card
```

## 2.2 ⛔ The switch that turns Admin on — and the trap it shipped with

`shadow_compile` takes **`live_domains`**, and its docstring is worth quoting because it names a
defect you would otherwise re-discover:

> *"`l3_activation` landed with a reader, a fail-closed gate, an erasure row, an admin API and a J5
> report — **and no caller**. `runner.py` still read `get_settings().use_domain_compiler` and
> nothing else, so an operator could POST an activation, see it in the console, read `EFFECTS`
> telling them the compiler's live pass now compiles that corpus, and **get a shadow pass**."*

That is fixed. What matters for you:

* **`live=True`** is the GLOBAL flag (`platform/config.use_domain_compiler`) — **all tenants at
  once or nobody.** Set in no environment. Do not use it.
* **`live_domains`** is `platform/l3_activation.activated_domains(engine, org)` — **per tenant, per
  corpus.** This is what makes *"Admin on, Sales off"* expressible.
* They are **OR-ed PER SITUATION**, never globally: *"a tenant with `admin` activated runs its Admin
  situations live and its Sales situations in shadow, in the same sweep, from the same read."*

⛔ **So Rohit's Admin-only decision is directly expressible and needs no code.** One activation row.

## 2.3 What "live" actually flips — three things together

From the same docstring, and all three must flip or the brain cannot reach a user:

1. a real **publisher**, so `expertise_packages` is written instead of the package being dropped;
2. **`require_admission=True`** — only capabilities a named reviewer accepted may carry authority;
3. **`ExecutionMode.LIVE`** and an emitted `signals` row carrying the capability's identity.

---

# PART 3 · THE COMPONENTS, AND HOW THEY INTEGRATE

## 3.1 The reasoning unit framework — `reason/unit.py`

Every unit has the same anatomy, deliberately:

```
Input → Validator → Retriever → Analyzer(plugins) → Calculator → Evaluator → Builder → Metrics
```

Two departures from the architecture diagram, both forced:

* **The Retriever does not fetch.** Units may not touch a database, network or clock — that is what
  makes a decision replayable months later. Retrieval already happened when L2 froze the snapshot.
* **The stages are methods, not files.** `evaluate()` is a template method that cannot be
  overridden, so no unit can skip validation or invent its own result shape.

**23 units are registered** (17 `CORE_UNITS` + 6 `SUPPLEMENTARY_UNITS`).

## 3.2 ⛔ Six units vs the roster — the number everyone gets wrong

```python
_default_dag(...)   → (context, risk, constraint, priority, confidence, planning)   # SIX
_roster_specs(...)  → the full family, gated per unit by what the corpus reads      # roster_v2
```

**On the six-unit path the units also run half-blind:** `core.risk` reads `drop_bp` from
`core.temporal` and `coverage_bp` from `core.relationship`, and neither is scheduled — so two of its
three plugins have been correctly silent since it shipped.

### ⛔ But measured for ADMIN with `roster_v2` on: **15 of 20 roster units BIND. 5 drop.**

| dropped unit | role it needs | candidates | in the vocabulary? |
|---|---|---|---|
| `core.relationship` | `status_field` | `deal.status` | ✅ |
| `core.policy` | 4 roles | `deal.value`, `deal.approval_status`, `contact.do_not_contact`, `contact.consent_status` | 1 of 4 |
| `core.opportunity` | `status_field`, `owner_field` | `deal.status`, `deal.owner` | 1 of 2 |
| `core.resource` | `owner_field` | `deal.owner` | ⛔ not declared |
| `core.scheduling` | `quiet_until_field` | `schedule.quiet_until` | ⛔ not declared |

⛔ **Four of the five drops are CORRECT** — these are DEAL-shaped units and **Admin has no deals.**
The selector dropping them with a receipt is the selector working.

⛔ **And do not "fix" `core.relationship` by binding it to an Admin field.** The module refuses this
in words: *"Only a genuine status qualifies… binding it to `thread.ball_in_court` would put **a
false reading in the trace to keep a unit busy**."* `core.risk` running on 2 of 3 plugins for Admin
is **honest silence, not a bug.**

## 3.3 The corpus — what a capability actually is

`Domain Expertise/Admin Expertise/` — **59 capabilities, all `stable`, 34 situations.**

A capability folder is four things:

```
capabilities/<group>/<capability>/
    capability.yaml   the expertise — identity · purpose · heuristic{statement, why,
                      confidence_bp, applies_when, breaks_down_when, reads}
    knowledge.yaml    the knowledge block
    objects.yaml      the LOAD-SET — core/scoped × required/optional
    situations/       the situations this capability owns
```

**`reads:` is the seam.** It lists the substrate fact paths the heuristic may reason from, and
`reason/adapters/citations.py:159` turns each into an `object:<id>` tag for retrieval.

`objects.yaml` is the other half: `required` blocks the compile if missing; `optional` **lowers
confidence rather than blocking** — Layer 3 strategy S8, *"a situation the compiler cannot fully
feed should still produce the answer the requester is waiting on, at a lower confidence, not
withhold it."*

## 3.4 The admission ceremony — two rules, do not mix them

| | a CAPABILITY needs | a SITUATION needs |
|---|---|---|
| | `identity.status == stable` | `identity.status == stable` |
| | `metadata.review_status == approved` | `metadata.review_status == approved` |
| | `metadata.reviewed_by` non-empty | `metadata.reviewed_by` non-empty |
| | ⛔ `admission.accepted_content_hash` matching the bytes | — (no hash; the file carries no block) |
| if it fails | **dropped in live mode** | ⛔ **flagged, not removed** |

**Why the asymmetry is deliberate:** a situation's DETECTION belongs to Layer 2 and is
evidence-backed whatever a reviewer thinks of the copy; only its prescriptive words are unreviewed.
So the gap lands in `admission_gaps` → `plan.admitted=False` → `review_state='draft'` →
`deliver/pipeline._apply_abstention` **downgrades the card to an OBSERVATION.**

> **The intelligence still ships; it stops instructing.** Removing the situation would delete the
> finding to punish its prose.

⛔ **Never pass a `SourceDocument` to `situation_admission_reason` — pass `document.content`.** The
old signature answered `identity_status_absent` for anything else, which reported *"all 69
situations inadmissible"* twice and cost a debugging pass against a number that was never real. It
now raises `TypeError` instead.

---

# PART 4 · ADMIN'S MEASURED STATE

## 4.1 Corpus health — ⛔ it is genuinely well written

```
admin              total=59  admitted=59  inadmissible=0  hollow=0   situations=34  unreviewed=8
customer_support   total=49  admitted=49  inadmissible=0  hollow=0   situations=20  unreviewed=16
sales              total=47  admitted=47  inadmissible=0  hollow=0   situations=15  unreviewed=0
```

**59 of 59 admitted. Zero hollow.** Routing: `admin → admin`, no dark route, nothing unresolved.

⛔ **"211 capabilities" is a file count, not a capability count** — 59 capability + 59 knowledge +
59 objects + 34 situations = 211. **It is 59.**

## 4.2 ⛔ The 8 "draft" situations are TWO different things — this is the biggest trap in the file

**FOUR are declared `pending_l2_types` in `registry/situation-capability-map.yaml`. DO NOT FLIP THEM.**

| situation | the file's own note |
|---|---|
| `admin.sit.obligation_falls_due` | *"deliberately the most explicit about **why it must not be faked**… this one would cost a **false assurance**"* |
| `admin.sit.spend_against_a_commitment` | *"one situation for what the mailbox can see, one **named gap** for what only a finance system can"* |
| `admin.sit.employee_lifecycle_event` | *"a start date exists in an offer letter and in an HR system; **neither is connected**"* |
| `admin.sit.asset_in_custody` | *"authored as a **named gap** so `index.py` reports the subdomain as blocked on a type"* |

These are **placeholders for capability that does not exist**, tracked deliberately in
`deferrals.yaml` with three kinds (`out_of_v1_scope` · `blocked_on_l2_type` · `no_runtime_trigger`),
each carrying a sentence rather than a category. Flipping them makes cards **instruct** about things
the system cannot see.

**FOUR are finished and only need a signature.** Their notes are the most rigorous in the corpus:

| situation | state | its own note |
|---|---|---|
| `admin.sit.campaign_awaiting_reply` | `review_status: unreviewed` | *"**EVERY PREDICATE HAS A LIVE WRITER**, checked against the tenant… Live read 2026-09-09: two campaigns, 7 and 6 recipients"* |
| `admin.sit.condition_awaiting_review` | `unreviewed` | *"5 stored rows, 16 findings, every one carrying a real sentence"* |
| `admin.sit.organization_gone_quiet` | `unreviewed` | *"EVERY PREDICATE HAS A LIVE WRITER"* |
| `admin.sit.document_under_control` | `approved`, `reviewed_by: harsh` | *"authored as an explicit gap… **and now bound**"* |

⛔ **These need `reviewed_by` to carry a real human name.** Nobody should forge it — the whole point
of the ceremony is that *"an author flipping a field in a text editor"* must not grant production
authority. **Rohit or you sign; then one word per file, `draft → stable`.**

## 4.3 The substrate — what Admin asks for

| | |
|---|---|
| fact paths the vocabulary declares to authors | **141** |
| ⛔ **Admin's capabilities name** | **46** |
| Admin never names | **95** (79 strict) |
| of those, **no domain at all** names | **61** |

The 61 group into families that **are** an assistant's job:

| family | fields | a card could then say |
|---|---|---|
| `mailbox.*` | **17** | *"the oldest thread in your backlog is 23 days old and p90 doubled this fortnight"* |
| `knowledge.*` | **9** | *"four people asked this in ten days; it was answered once"* |
| `document.*` | **8** | *"the contract was last modified by someone outside the company"* |
| `escalation.*` | **7** | *"this was escalated, named a receiver, and the receiver has not replied"* |
| `derived.history.*` | **4** | *"we already sent this card and they marked it wrong"* |

⛔ **The engine computes and writes every one of these on every sweep.** `correlation_history` runs
at `context/runner.py:752`. Nothing reads them.

### ⛔ What this does NOT do — a correction, so you do not repeat my mistake

My first cross-check claimed adding these `reads:` would **wake the dormant reasoning units**.
**Measured, that is false.** The roster gates on deal/contact/schedule roles (§3.2), not on these
families. Adding `reads: mailbox.*` changes **what a capability can SAY**, not **which units RUN**.
Both are worth doing; they are separate mechanisms reading separate lists.

---

# PART 5 · WHAT IS PENDING

## 5.1 Blocked on a human, not on code

| | what | who |
|---|---|---|
| **P1** | Sign or refuse the **4 finished** draft situations (§4.2). One word per file after the signature | ⛔ **Rohit / Harsh** |
| **P2** | Confirm `roster_v2` is activated for the pilot. It is in `L4_DEFAULT_FEATURES`, so `make_tenant_live` switches it on at provisioning — **one read-only query to confirm** | Harsh |
| **P3** | Activate `admin` for the pilot tenant — `platform/l3_activation`, one row. **Do not activate `sales` or `customer_support`** | Harsh, on Rohit's word |
| **P4** | The **item-2 authoring**: add `reads:` for the unread families to the Admin capabilities that should own them | ⛔ **an author — see §5.3** |

## 5.2 Blocked on Layer 1 / Layer 2, not on Layer 3

These five fields are named by roster units and **do not exist in the vocabulary at all**, so no
authoring can bind them:

```
deal.owner · deal.approval_status · contact.do_not_contact · contact.consent_status
schedule.quiet_until
```

⛔ **Four of the five units that want them are deal-shaped and Admin does not need them.** Record
this as a Layer 1/2 question for the day Sales comes off hold, not as an Admin gap.

## 5.3 ⛔ P4 — what the authoring actually needs, and why I cannot do it alone

Adding `reads: mailbox.backlog_oldest_days` is one line and I can write it. **The value is not in
that line.** It is in the three things around it, and all three are expert judgement:

| block | the question it answers | why it cannot be inferred |
|---|---|---|
| `heuristic.statement` | what should the founder DO | this is the sentence that prints on the card |
| `heuristic.why` | why is that the right read | a card that instructs without a why is an order |
| `heuristic.breaks_down_when` | ⛔ **when is this rule WRONG** | *the most valuable block in the file* — e.g. a backlog grows after a holiday and that is not a problem |

**The proposed order**, one family at a time:

1. agree the **owner capability** for each family — the natural candidates from Admin's own
   subdomains are `admin.executive_support.inbox_and_correspondence` for `mailbox.*`,
   `admin.records_and_documentation.document_control` / `version_control` for `document.*`,
   `admin.records_and_documentation.knowledge_base_maintenance` for `knowledge.*`. ⛔ **`escalation.*`
   has no obvious owner in Admin's ten groups — that one needs a decision.**
2. for the first family, a **full draft** goes to Rohit — statement, why, applies_when,
   breaks_down_when, reads, confidence_bp — he corrects it;
3. the rest follow that pattern, faster.

## 5.4 Carried over from the whole branch

Everything blocked on you across all three layers is one file:
[`speedrun008/DO-THIS-NOW.md`](../../DO-THIS-NOW.md) — the scratch Postgres variable (⛔ 991 skipped
tests are that one line), nine migrations in number order, the backfill window, and the six
measurements.

---

# PART 6 · HOW TO VERIFY ANY OF THIS YOURSELF

```bash
# corpus health, the rules the compiler actually admits with
.venv/bin/python -c "
from genios_engine.reason.domain_shadow import expert_catalog
from genios_engine.packs.compiler.capability_resolver import corpus_health
for d,x in corpus_health(expert_catalog()).items(): print(d, x)"

# which situations are unreviewed, and WHY each one is
.venv/bin/python scripts/unroutable_report.py --corpus-only

# what the corpus asks for, against what the engine publishes
.venv/bin/python -m pytest tests/test_the_corpus_asks_for_what_the_engine_publishes.py -q

# the whole suite — expect 13,301 passed and the same 14 pre-existing failures
.venv/bin/python -m pytest -q -p no:randomly
```

---

# PART 7 · TRAPS — each one cost a debugging pass already

1. **`situation_admission_reason` takes `document.content`, not the document.** Twice this reported
   the entire corpus inadmissible.
2. **A `draft` situation may be deliberate.** Check `pending_l2_types` and `deferrals.yaml` before
   flipping anything.
3. **`signals.situation_id` is null on almost every row. DO NOT "fix" it.** Considered and refused
   2026-09-25: four of the five signal writers never reason over the situation, so writing it claims
   a provenance that does not exist and corrupts the cutover measurement. `reason/situation_binding`
   holds the reason and the build will stop you.
4. **Never run the test suite against production.** It drops and recreates the schema.
5. **Never suppress a `git stash` error.** A prior stash-pop corrupted five files. Recover with
   `git stash show -p stash@{0}`, **never `pop`**.
6. **An assertion about text near a thing is not an assertion about the thing.** Ten occurrences on
   this branch. If you write a guard, parse the structure — AST, column lists, positions — never
   `"word" in source`.
