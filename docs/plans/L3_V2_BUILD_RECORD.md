# Layer 3 v2 — What Was Built

> **Created:** 2026-09-07 · **Status:** Active

**Purpose:** the unit-by-unit record of what Layer 3 v2 actually is in code — the compiler, the
typed consumers, the Admin corpus, the two brain-content pipelines — plus the gates that are met,
the one row that is **not** met and why, and exactly what is left that needs a real tenant.

**Specification of record:** `Rohit_Updates (Version 2)/Version 2 Updates/03-Layer-3-Plan/`
(docs 00–06). That set is the *design*. **This file is the *result*.**

---

## 1. The one-paragraph version

Layer 3 takes a `BusinessSituationObject` from Layer 2 and compiles the **expertise package** a
decision is made against: the authored corpus's objects, capabilities, heuristics and rules,
narrowed to this situation, addressed by content so the same situation and the same brain snapshot
produce the same bytes. Six waves. Y0 laid the contracts and the per-tenant/per-domain activation
row; Y1 built the three typed consumers that make activation mean something — a rule compiler that
turns authored `when/then` into evaluable predicates, citations that carry the expert's own
sentence onto the decision, and a play cap; Y2 routed and sharpened the Admin corpus; Y3 changed
what the compiler reads; Y4 built the two supply-side pipelines that fill the empty runtime brains
— **N-3**, which reads a founder's uploaded policy into the Organization brain, and **N-4**, which
turns L2.4's measured trends into the Behavior brain, plus the Adaptive lease a card verdict earns;
Y5 gave activation a request path. **J0–J4 are met. J5 is met on six of its seven rows.** The one
that is not is *"a package with a non-empty Org/Behavior/Adaptive slice"*, and it fails for a
reason worth more than the row: the brains are full and **Layer 3 cannot read them**.

```
BSO ──► capability_resolver ──► object_resolver ──► knowledge_retriever ──► expertise_builder
              │                       │                     │                      │
        route the situation     load the objects     heuristics + rules      ExpertisePackage
                                                            │                (content-addressed)
                                              rule_compiler / citations ──► ReasoningDecision
                                                                                   │
runtime brains ─X─ (see §5.1)                                              signals ──► cards
```

---

## 2. Totals

| | |
|---|---|
| Waves | 6 of 6 built (Y0–Y5) |
| Gates | **J0 · J1 · J2 · J3 · J4 met** · **J5 six rows of seven** |
| Tests | **8,817 passing · 0 failing · 0 skipped · 152 xfailed** (real Postgres, virgin scratch db) |
| Migrations | `0107` (activation), `0113` (org-rule discovery), `0114` (signal citations) |
| New packages | `packs/brains/` `packs/compiler/` (extended) `reason/adapters/{citations,rule_compiler}.py` `platform/l3_activation.py` `feedback/{brain_pipeline,org_rule_ingest}.py` |
| Gate instruments | `scripts/brain_content_report.py` (J4) · `scripts/l3_pilot_report.py` (J5) · `scripts/brain_pilot_seed.py` (the population J4 is measured on) |

The suite number is only meaningful against a real database. The hermetic lane silently skips ~800
tests — see §8.

---

## 3. The five laws, and where each is enforced

Each is enforced by a constraint, a test, or a grep — because each records a failure that either
happened or was one edit away.

**1 · L3 NEVER DECIDES.** The compiler produces a package; `reason/decision_maker.py` decides.
`packs/compiler/` contains no scoring and no selection between candidates.

**2 · THE COMPILE IS REPRODUCIBLE — zero runtime LLM on the compile path.**
`grep -riE 'llm|anthropic|model\.call' genios_engine/packs/compiler/*.py` returns comments only.
Verified behaviourally this round: recompiling a seeded pilot at the same `eval_time` reported
`standing: 2` (nothing re-emitted) and left both `expertise_packages.payload` rows **byte-identical**
(md5 unchanged). §6.

**3 · THE EXPERT BRAIN IS HUMAN TERRITORY.** `learned_brain_no_expert` is a CHECK constraint in
migration `0045`, and the review route reports `expert_brain_changed: false` on every response.
Attacked directly this round at the database, on both INSERT and UPDATE — both refused. §6.

**4 · Knowledge is not shipped until L4 consumes it typed.** Held for the Expert corpus: the
authored heuristic's sentence reaches `signals.citations` byte-identical, re-hashed against the
YAML on disk. **Not held for the three runtime brains** — that is the open J5 row. §5.1.

**5 · Activation is per-tenant, per-domain.** `l3_activation` (migration `0107`), one row per
(org, domain), with a request path at `api/admin_routes.py`. `scripts/l3_pilot_report.py` *reports*
activation and cannot flip it — Y1-before-Y5 is an ordering rule, and a report that could activate
would be a way around it.

**Plus:** integer basis points (no float `_bp` anywhere in the new modules), no clocks in logic
(no `datetime.now()` in `packs/brains/`, `packs/compiler/`, `brain_pipeline.py`,
`org_rule_ingest.py`, `citations.py` — every one takes its instant as an argument), and **the model
proposes while deterministic governance decides**: neither N-site writes a brain. N-3's model
proposes candidates that CLG-09 gates on the *document's own words*; N-4 has no model at all.

---

## 4. The layer, wave by wave

### 4.1 Y0 — contracts and the activation row

| Unit | Where | What it is |
|---|---|---|
| Package extensions | `contracts/domain_expertise.py` | `ExpertisePackage`, `BusinessSituationObject`, `Citation`, `citation_statement_hash` |
| L3.1 activation | `platform/l3_activation.py`, migration `0107` | activation as a per-tenant **and per-domain row**, not a boolean in config |
| Activation request path | `api/admin_routes.py` (list / show / activate / deactivate) | closed the Y0 defect: `activate()` existed with **no caller**, so the only way to start a pilot was a hand-written INSERT |

### 4.2 Y1 — the typed consumers (the weld)

| Unit | Where | What it is |
|---|---|---|
| CLG-06 rule compiler | `reason/adapters/rule_compiler.py` | authored `when/then/severity` → evaluable predicates. Refuses by name what Layer 4 does not enforce: a rule authored `enforced_by: L5_validation` is refused as `rule_enforced_by_l5_validation` |
| CLG-08 citations | `reason/adapters/citations.py`, migration `0114` | the expert's own sentence onto `ReasoningDecision.citations` and through to `signals.citations`, with a `statement_hash` |
| CLG-07 play cap | `reason/adapters/expertise.py` | the fake-success detector's other half — a generic "review the situation" play is not an answer |

### 4.3 Y2 — Admin corpus V1

Routing, authoring and sharpening under `Domain Expertise/Admin Expertise/`. What this round added
to it is stated plainly in §5.3, because it bears on a gate row.

### 4.4 Y3 — compiler inputs

Analytic predicates, `pattern_id` routing, and the stale-comment fix in
`packs/compiler/{capability_resolver,context_adapter,expertise_builder}.py`.

### 4.5 Y4 — the two brain-content pipelines

| Unit | Where | What it is |
|---|---|---|
| **L3.2-U1 · N-3** org discovery (CLG-09) | `packs/brains/{org_rule_extract,org_discovery}.py`, `feedback/org_rule_ingest.py`, migration `0113` | a founder's uploaded policy → candidate rules → **CLG-09 gates on the document's own words** → L6 → human review → Organization brain + `authority_rules` |
| **L3.2-U2 · N-4** behavior distillation | `packs/brains/behavior_distill.py` | L2.4's `derived.trend.*` facts → behaviour patterns. **No model.** A statement templated from validated integers, with the window it was measured over |
| Adaptive lease | `packs/brains/adaptive_lease.py`, `feedback/brain_pipeline.py` | a founder's `bad_timing` card verdicts → a Runtime lease with a mandatory TTL, granted **inside the request that wrote the verdict** |
| The collector | `feedback/orchestrator.py:126,134` | `expire_leases` then `brain_pipeline_proposals`, appended to the weekly run's own validate → preflight → govern → persist → publish loop |

**Wired at** (every one of these is reached from a request path, which is the defect L1 shipped six
times):

```
packs/brains/org_discovery      <- api/upload_routes.py:314   (BackgroundTasks, a policy is uploaded)
feedback/org_rule_ingest        <- api/learning_routes.py:157/165 (a human confirms; authority_rules)
packs/brains/adaptive_lease     <- api/intelligence_routes.py:967 (card feedback, same transaction)
packs/brains/behavior_distill   <- feedback/orchestrator.py:134    (the weekly pass)
```

### 4.6 Y5 — pilot activation

`l3_activation` rows, the admin routes above, and `scripts/l3_pilot_report.py` as the J5
instrument.

---

## 5. What is NOT done

### 5.1 J5's brain-slice row — **the layer's real open defect**

> a package with non-empty Org/Behavior/Adaptive slices | **>= 1** | *the brains speak*

**Measured:** on a tenant holding **6 behaviour entries, 5 organization entries and a live adaptive
lease**, `packages_with_a_brain_slice = 0` across 4 compiled packages. It is a **selection and
reader gap, not an empty brain** — three independent faults, each verified by reading the code:

1. **`brain_subject_keys` has no writer.** `packs/compiler/runtime_brains._selectors` reads
   `situation.brain_subject_keys`, which `contracts/domain_expertise.py:506` reads off
   `metadata["brain_subject_keys"]`. `grep -rn brain_subject_keys genios_engine/` returns the
   reader and nothing else. The selector intended to bind a situation to its brain entries is dead.
2. **The subject vocabularies do not meet.** `_relevant` matches the entry's subject *segments*
   against the selectors. A published Behaviour subject is `behavior:<metric>:<node_id>`; a
   correlated situation's entity ids are **email addresses**. They never intersect, and a Behaviour
   entry's value carries no `capability_id` to match on instead.
3. **The Adaptive brain has no reader at all.** `publish_runtime` writes a lease to
   `temporary_memories`; `PostgresRuntimeBrains.snapshot` selects **only** from
   `learned_brain_entries`. `grep -rn temporary_memories genios_engine/packs/ genios_engine/reason/`
   finds one hit — the *producer's* own read inside `adaptive_lease.py`. So
   `ExpertisePackage.adaptive_preferences` is structurally always empty. Doc 02 §1 names the
   Adaptive store as `learned_brain_entries` **+** `temporary_memories`; the build split them and
   the reader was never taught the second one.

This is Law 4 unsatisfied for the runtime brains, and it is the same shape as the defect Y1 closed
for the Expert corpus — *knowledge that died one hop from the surface*. **It was not patched in
this gate round on purpose:** fixing it means choosing a subject vocabulary a situation can select
on, which is a contract decision across L2.7 and L3, and a gate that changes the machinery and then
passes itself on it is the thing these gates exist to catch.

**The fix, when it is taken:**
```
1. teach PostgresRuntimeBrains.snapshot to union temporary_memories (active and expires_at > :now)
   — the Adaptive slice is the cheapest of the three and needs no new vocabulary
2. decide the Behaviour subject key: either write brain_subject_keys onto the situation's metadata
   (a writer, in context/situations.py) or key behaviour entries by capability_id as leases are
3. re-run:  python scripts/l3_pilot_report.py --org <pilot> --days 7 --database-url "<url>"
   and read `packages_with_a_brain_slice`
```

### 5.2 What genuinely needs a real tenant and seven days

Everything else is built and driven. What no code can substitute for:

| Question | Why only a tenant answers it |
|---|---|
| **N-3's model recall on real prose** | the extractor here is the production `LLMOrgRuleExtractor` over a **stubbed transport** — the real PROMPT, the real strict-JSON contract and the real `MAX_RULES` trim all execute, so what is unproven is the MODEL's recall, not the path, the gate or the pipeline |
| **Whether the four canon kinds cover what a founder tags** | `policy`, `sop`, `pricing`, `org_structure`. A document tagged anything else costs no model call (proven) and yields no rules |
| **How many of a founder's rules are percentage-bound** | see §5.4 — a percentage threshold costs the tenant the WHOLE rule today |
| **Whether the six shipped Admin patterns cover a real founder's situations** | corpus coverage is a content question |
| **How many rules a tenant accumulates per week** | seven days of one customer's traffic |

**How to run it, when a tenant is available:**

```bash
# 1. activate ONE tenant for ONE domain — a row, never a global default
curl -XPOST .../v1/admin/l3/activate -d '{"org_id":"<pilot>","domain":"admin"}'

# 2. the founder uploads their operating policy through the product
#    POST /api/org/<pilot>/upload   file=<policy>  tag=policy
#    then confirms each proposal in the console:
#    GET  /v1/learning/objects?state=human_review&target=organization
#    POST /v1/learning/objects/<id>/review {"approve": true}

# 3. let it run seven days with no mid-week switch-off, then read both gates
python scripts/brain_content_report.py --org <pilot> --database-url "<explicit url>"
python scripts/l3_pilot_report.py     --org <pilot> --days 7 --database-url "<explicit url>"

# 4. every refusal is a row and every one is named — read them before concluding
#    select reason_code, count(*) from learning_input_rejections where org_id='<pilot>' group by 1;
```

### 5.3 The Admin corpus's blocking doctrine — a finding, not a gate row

J5's elimination row asks whether *authored doctrine finally binds*. It is **earned**: on a clean
admin pilot, `admin.rule.opportunity_tracking.no_reopening_on_an_inferred_satisfaction` fires
`severity: blocking`, eliminates `admin.pb.opportunity_tracking.reopen_with_the_evidence_named`,
and names itself in `signals.rejected_candidates` with its statement byte-identical to the YAML.

**But that rule was authored in the same round as the gate it satisfies**, and the honest finding
is why one had to be. Enumerating the Admin corpus's rules directly:

| Pre-existing blocking rule | Why it cannot fire today |
|---|---|
| `inbox_and_correspondence.a_draft_may_not_commit_the_principal` | authored `enforced_by: L5_validation` — the rule compiler refuses it by name (`rule_enforced_by_l5_validation`). A blocking rule Layer 4 correctly never runs |
| `commitment_tracking.no_chase_while_we_hold_the_ball` | gated on `commitment.due_at`, which never reaches a company node — see below |
| `approval_coordination.an_unowned_decision_is_not_a_slow_one` | same |

**The root cause, verified by reading both sides:** `context/pipeline.py::_works_at` writes the edge
**person → company**. `context/derived.py::compute_deal_view`'s commitment roll-up selects
`e.from_node_id as company` and joins the next hop off `e.to_node_id` — i.e. it assumes
**company → person**. It therefore reaches a company *never*. This is the **third** instance of an
edge-direction assumption that `derived._person_neighbours` documents in its own docstring and
fixed only for itself; `baselines._account_rows` is the second. It is **pre-existing, tracked code
and was not changed by this round** — changing it would move a gate row mid-gate. It is the highest
-value fix available to Layer 2/3 and it dark-fires two authored blocking rules and the situation
`admin.sit.money_owed_either_way` on **every** tenant.

So: *"the V1 domain ships doctrine that binds nothing"* is **not** true as a statement about the
corpus — six of nine Admin rules are `severity: blocking` and their conditions are well-formed. It
**is** true as a statement about what reaches them.

### 5.4 A percentage threshold costs the tenant the whole rule

*"A discount greater than 15% requires approval from the founder."* has a condition, a consequence
and an authority — a rule by every clause of CLG-09's own definition, and the production PROMPT
offers `20%` as a legal `threshold_as_written`. But `threshold_as_written` is validated by ALG-10,
a **Money** parser, which answers `UNPARSEABLE_TOKEN` for `15%` — and the **whole rule** is dropped,
not just the threshold. It is counted and visible (`threshold_unparseable`) and pinned by
`test_a_percentage_threshold_costs_the_tenant_a_real_rule`. Discount authority is the most common
approval rule a sales-led startup writes down. **Not fixed:** it needs a representation between
Money and nothing — a ratio/basis-points threshold on `GatedRule`, `proposed_value` and
`authority_rules` — which is a contract change across Layer 3 and the L2.1.4 Authority view, and is
worth a decision rather than a patch.

### 5.5 Known-and-accepted

| Item | Status |
|---|---|
| `cards_quoting_the_claim_in_their_own_copy` | reads **0** on every card. The card row is earned through the decision the card is bound to; the renderer's `why` block carries fact/value pairs and never composes the quote into the card's own words. Measured and reported, deliberately not made a check — but a reader of J5 must not come away believing the expert's sentence reached the human's screen when it reached the row behind it |
| Admin-confirmed Organization entries | the J4 row is *discovered + admin-confirmed* as a union; the **discovered** half alone measures 5 ≥ 3. The `admin_console` unit was not driven |
| Three copies of the L6 admission sequence | resolved as a drift detector rather than a refactor — see §6 |

---

## 6. How this was proven

**Every number below was re-measured by the gate, not read from a report.** Populations were driven
through production routes into local scratch Postgres databases; no production database was opened.

### J4 — brains fed · **PASS**, on one tenant

`python scripts/brain_content_report.py --org org_gate_pilot`

```
adaptive         0 active   —
behavior         6 active   distilled 6
organization     5 active   discovered 5
adaptive leases  1 live (1 from card feedback), 1 cleared, 0 EXPIRED AND NOT CLEARED

[PASS] organization entries >= 3                     5
[PASS] behavior entries >= 1                         6
[PASS] adaptive leases from card feedback >= 1       1
[PASS] writes outside the L6 pipeline == 0           0
[PASS] entries with unnameable provenance == 0       0
[PASS] expired leases not cleared == 0               0
[PASS] rows with brain='expert' == 0                 0
VERDICT: PASS
```

The organization half was driven with a **document the gate wrote itself** — a different company's
policy, 10 statements, 5 rules and 5 pieces of prose classified before the run — through
`POST /api/org/{org}/upload` → `BackgroundTasks` → N-3 → CLG-09 → L6 →
`GET /v1/learning/objects?state=human_review` → `POST /v1/learning/objects/{id}/review`. Result: **12
candidates, 5 admitted, 7 refused, every refusal `no_deontic_force`**. No prose leaked.

**Provenance, attacked rather than counted:**

* **A human confirmed each one.** One organization entry traced end to end in
  `learning_transitions`: `→observed → candidate(discovered) → validated(floors_evaluated) →
  governed → human_review → promoted(actor=<the reviewer's email>, human_reviewed) → published`.
  No rung skipped, and the publish is in the same instant and transaction as the promotion.
* **Before any confirmation:** `learning_objects(human_review)=5`, `learned_brain_entries=0`,
  `authority_rules=0`. Nothing reaches a brain from a model's proposal.
* **The floors were not lowered.** `contracts/learning.py` — where they live — is **byte-identical
  to HEAD** and has not been touched since 2026-08-24; `feedback/governance.py` and
  `feedback/units.py` are likewise unmodified. The tenant's `learning_policies` holds **one**
  revision carrying the shipped defaults (`min_observations 3 · min_distinct_days 2 ·
  min_distinct_entities 3 · min_confidence_bp 6000 · max_noise_bp 4000 · max_conflict_bp 3000 ·
  max_runtime_ttl 604800`). The behaviour entry cleared them with real margin: **72 observations
  (24×), 12 distinct days (6×), 6 distinct entities (2×), confidence 6516 bp (+516), noise 0**.
  And the floor is load-bearing: **re-seeding with `min_confidence_bp` raised to 6600 — 84 bp above
  what the data earns — produced 0 behaviour entries** and the seeder said so rather than passing.
* **The lease's expiry is real, on both axes.** At `expires_at - 1s` the delivery consumer is handed
  the lease; at `expires_at + 1s`, **before any sweep**, `learned_state.snapshot(consumer="delivery")`
  returns `{}`. `run_learning` at `expires_at + 1s` reported `expired_leases=1`, the row went
  `active=false`, and `learning_transitions` gained exactly one `temporary → expired`,
  `reason_code=lease_expired`, `actor='clock'`.
* **Law 3, attacked at the database.** Three attempts, three refusals:
  `insert … brain='expert'` → `learned_brain_no_expert`; `update … set brain='expert'` on an existing
  row → the same CHECK (so the constraint holds on UPDATE, not only INSERT); and a second active
  version of one subject → `learned_brain_one_active`. The one-active index was flagged in an
  earlier gate as *a convention* because only `publish_brain` — which deactivates first — ever
  exercised it; it is now exercised through the upload+review door and directly by this attack.

### J5 — pilot activation · six rows of seven

`python scripts/l3_pilot_report.py --org org_gate_j5 --days 7 --at 2026-08-20T12:00:00+00:00`

| Row | Gate | Measured | Verdict |
|---|---|---|---|
| packages compiled, Admin domain | > 0 | **2** | **PASS** |
| a card carrying a heuristic/rule citation | ≥ 1 | **2 of 2 cards** | **PASS** |
| a candidate eliminated by a blocking corpus rule | ≥ 1 | **1**, and it is an **Admin** rule | **PASS** (see §5.3) |
| a package with non-empty Org/Behavior/Adaptive | ≥ 1 | **0** | **FAIL** (§5.1) |
| abstention downgrades on stamped capabilities | ~0 | **0** | **PASS** |
| byte-identical recompile of any package | exact | **both packages unchanged** | **PASS** |
| generic "review the situation" plays | **0** | **0** | **PASS** |

**The citation hop, re-verified from the corpus rather than from the report.** The three quotes
stored on `signals.citations` were re-read out of Postgres, matched against the 560 authored
artifact statements on disk, and re-hashed with `contracts.domain_expertise.citation_statement_hash`:
**3 of 3 byte-identical to the authored YAML, 3 of 3 hashes re-derive.** No claim without a receipt.

**Law 2, re-verified by re-running the compile.** `shadow_compile` at the same `eval_time` reported
`standing: 2` and left both `expertise_packages.payload` rows byte-identical.

**A note on the window.** `--days 7` measures back from *now*. A pilot seeded at an earlier
`eval_time` reads zero on every card/signal row until `--at` is set to the seeded instant. That is
the report behaving correctly and is worth knowing before reading a zero as a failure.

### The collision check — three copies of one governance

Two agents wrote into `learned_brain_entries`, the L6 pipeline and the publisher in parallel. The
tables are clean: **`learned_brain_entries` has exactly one writer module** (`feedback/publisher.py`),
and **exactly one function grants a lease** (`publisher.publish_runtime`); the only other
`temporary_memories` writers set `active = false` (`brain_pipeline.expire_leases`, the clock;
`feedback/reset.py`, an explicit tenant reset).

The real collision is structural: **three separate implementations of the admission sequence** —
`orchestrator.run_learning`, `brain_pipeline.admit_proposals` (the immediate lease, inside a
founder's HTTP request) and `org_rule_ingest.admit_discovery`. They agree today and nothing made
them agree tomorrow. **Resolved with a drift detector**, `tests/feedback/test_one_l6_admission_sequence.py`:
an AST check that all three apply `validate_learning → preflight → govern` **before** `persist`, and
`persist` before `publish`; a source assertion pinning `admit_discovery`'s one *documented*
divergence (the recurrence floors are advisory when governance routes to a human, and the guard
`if not decision.needs_human and not floors_ok` keeps them biting when review is off); and a
whole-engine grep that the two write paths stay singular. Removing `govern()` from the immediate
lease path turns **2** of its tests red.

### The defects this round found

| Defect | Where | Status |
|---|---|---|
| **Every approved brain entry published under a fabricated `learning_id`** | `learning_routes._publish_approved` rebuilt `Visibility.derived_from` as `str(<json array>)`; `Visibility.__post_init__` then ran `tuple()` over that STRING, so the lineage became a tuple of single **characters**, the object hashed differently, and the entry joined back to no proposal. J4's *"writes outside the L6 pipeline"* row, red, on a path whose count row was green. Affected every target — for behaviour and adaptive, empty lineage became the 18-character token `learning_objects_row` | **fixed** (`_derived_from` + a `semantic_hash` identity guard returning the new sink `identity_mismatch`) |
| **That identity guard was untested** | deleting it left **420 of 420 lane tests green** — the round's only surviving mutation | **fixed by this gate**: `test_a_lossy_rehydration_refuses_to_publish_under_a_fabricated_identity` corrupts the stored lineage so the rehydration *succeeds as something else*, and asserts both halves — the sink is `identity_mismatch` **and** nothing was written |
| **`bad_timing` was unsayable through the feedback route** | `intelligence_routes` overwrote whatever the human said with `not_relevant`, while the card surface, the DB CHECK and `feedback/calibrate.py` all already spoke three reasons — so every timing complaint arrived as a quality complaint and starved the Adaptive brain of its only input | **fixed** (`reason` on the body, validated against `deliver/actions.WRONG_REASONS`) |
| **The verdict fell outside its own cohort** | the verdict row took the database's `clock_timestamp()` while the lease cohort counted up to the request's `as_of` — two clocks, milliseconds apart | **fixed** (`occurred_at = :as_of`) |
| **Two live leases on one subject** | `publish_runtime` had no supersession; `learned_state.snapshot` keys by subject, so two live leases are two contradictory statements with nothing to choose between them | **fixed** (supersede on publish, logged `temporary → archived`) |
| **The one-active-version index was a convention** | only `publish_brain` — which deactivates first — ever exercised it | **closed**: exercised through the upload+review door, and attacked directly at the DB |
| **The `l3_activation` writers were unreachable** | `activate()` had no request path; the only way to start a pilot was a hand-written INSERT | **fixed in Y5** (`api/admin_routes.py`) |
| **The citation died one hop from the surface** | the expert's sentence reached the decision and stopped | **fixed in Y1** (migration `0114`) — and re-verified this round against the YAML |
| **The runtime brains die one hop from the package** | §5.1 | **open** |
| **`compute_deal_view` reaches a company never** | §5.3 | **open** — pre-existing, not touched by this round |

### Mutation testing

Each mutation was applied to the working tree, the lane
(`tests/feedback tests/packs tests/reason tests/test_learning_publisher.py
tests/test_learning_publish_path.py tests/test_learning_consumer.py tests/test_l3_pilot_activation.py
tests/test_intelligence_authority_routes.py`, **420 passing**) was re-run on a virgin scratch db,
and the file was restored.

| # | Mutation | Result |
|---|---|---|
| M1 | `_derived_from` reverted to the `str()` coercion | **13 failed** |
| M2 | the `semantic_hash` identity guard deleted | **0 failed — SURVIVED**; a test was written, and it now **fails** |
| M3 | `publish_runtime` no longer supersedes the live lease | **7 failed** |
| M4 | `expire_leases` retires nothing | **3 failed** |
| M6 | the human's `reason` overwritten by the verb default | **7 failed** |
| M7 | the floors-bite-where-nobody-looks guard removed from `admit_discovery` | **1 failed** |
| M8 | CLG-09's deontic gate disabled (prose admitted) | **12 failed** |
| M9 | `govern()` removed from the immediate lease path | **2 failed** (the new drift detector) |

### No tuning

Every threshold, floor and policy row this round touched, diffed against what it was before:

| | |
|---|---|
| `genios_engine/contracts/learning.py` (all L6 floors) | **unmodified vs HEAD**, last touched 2026-08-24 |
| `genios_engine/feedback/governance.py` | **unmodified vs HEAD** |
| `genios_engine/feedback/units.py` (`validate_learning`) | **unmodified vs HEAD** |
| `learning_policies` rows on the measured tenant | **one revision**, carrying the shipped contract defaults exactly |
| `packs/compiler/` thresholds | no numeric constant changed |
| Corpus content | **three Admin rules and one capability were authored this round** (`gatekeeping.evidence_then_a_structural_fix`, `goal_and_progress.no_goal_no_reading`, `opportunity_tracking.no_reopening_on_an_inferred_satisfaction`). One of them earns a gate row. That is content addition, reported as such in §5.3 — not a threshold change, and it is the only place this round's work touched a number a gate reads |

**The diff is otherwise empty.** No floor was lowered, and no gate in this record was passed by
moving one.

---

## 7. Database

| Migration | What |
|---|---|
| `0107_l3_activation.sql` | `l3_activation` — per tenant AND per domain, a row not a flag |
| `0113_org_rule_discovery.sql` | `org_rule_discovery_runs` (N-3's receipt) and the tenant's declared locale |
| `0114_signal_citations.sql` | `signals.citations` — the expert's own words reach the card's row |

Layer 3 reads two tables it does not own: `learned_brain_entries` and `temporary_memories`
(migration `0045`), which carry `learned_brain_no_expert` and `learned_brain_one_active`.

---

## 8. Running it

```bash
createdb <your-own-scratch-db>
GENIOS_TEST_DATABASE_URL="postgresql://<user>@localhost:5432/<your-db>" \
  ./.venv/bin/python -m pytest -q -p no:randomly
dropdb <your-own-scratch-db>
```

**Never run the suite without `GENIOS_TEST_DATABASE_URL`** — the hermetic lane silently skips ~800
real-Postgres tests. A handful of legacy files commit their own rows and are not re-runnable on one
database; use a fresh db for any full-suite run. Baseline on a virgin db: **8,817 passed, 0 skipped,
152 xfailed**.

The gates:

```bash
pytest tests/packs/brains -q
python scripts/brain_pilot_seed.py     --org <pilot> --database-url "<url>"   # writes
python scripts/brain_content_report.py --org <pilot> --database-url "<url>"   # J4, read-only
python scripts/l3_pilot_report.py      --org <pilot> --days 7 --database-url "<url>"  # J5, read-only
```

All three resolve their target through `scripts/_db.py`, which has **no fallback** to the
application's configured URL — on a developer machine that URL is the production tenant database.
The two report scripts open a `set transaction read only` connection.

---

## 9. Where things live

| | |
|---|---|
| The compiler | `genios_engine/packs/compiler/` |
| The typed consumers | `genios_engine/reason/adapters/{rule_compiler,citations,expertise}.py` |
| The brain pipelines | `genios_engine/packs/brains/` + `genios_engine/feedback/{brain_pipeline,org_rule_ingest}.py` |
| Activation | `genios_engine/platform/l3_activation.py`, `genios_engine/api/admin_routes.py` |
| The authored corpus | `Domain Expertise/` (Expert Brain — **git, humans only**) |
| Gate instruments | `scripts/{brain_content_report,brain_pilot_seed,l3_pilot_report}.py` |
| Product-level tests | `tests/feedback/test_org_brain_filled_through_the_routes.py`, `tests/feedback/test_behavior_and_adaptive_brains_filled_through_the_paths.py`, `tests/feedback/test_one_l6_admission_sequence.py`, `tests/reason/adapters/` |

---

## 10. Next

1. **Close J5's brain-slice row** — §5.1. Start with the Adaptive union in
   `PostgresRuntimeBrains.snapshot`; it is the cheapest of the three and needs no new vocabulary.
2. **Fix `compute_deal_view`'s edge direction** — §5.3. One roll-up, three dark authored rules, and
   it is the third instance of an assumption already documented and fixed elsewhere in the same file.
3. **Decide the percentage threshold** — §5.4. A ratio/basis-points representation on `GatedRule`,
   `proposed_value` and `authority_rules`, or an explicit decision to keep dropping those rules.
4. **Then the tenant** — §5.2. Activate one org for the Admin domain, upload one real policy, seven
   days, and read both gate scripts.
