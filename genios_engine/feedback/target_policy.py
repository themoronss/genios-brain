r"""Which analysis unit may propose which learning target — declared, and checked against the code.

⛔ WHY THIS MODULE EXISTS. `units.ALL_ANALYSIS_UNITS` runs eleven analysis units and each one
chooses a `LearningTarget`. That choice decides the SINK: `METRICS` is published as a measurement,
`RUNTIME` becomes an expiring lease in `temporary_memories`, and `ORGANIZATION` / `BEHAVIOR` /
`ADAPTIVE` are written by `publisher.publish_brain` into `learned_brain_entries` as a **durable,
versioned, active row with no expiry column at all**. Nothing asserted which unit may choose which,
so a unit's sink could change in a one-word edit and no build would notice.

⛔ THE DRIFT THIS WAS BUILT FOR. Four units whose `proposed_value` is rates and counts
(`feedback_learning`, `outcome_analysis`, `actor_outcome_analysis`, `performance_optimization`)
target `METRICS`. `recommendation_learning` emits `success_rate_bp`,
`attention_per_outcome_bp` and `efficacy_bp` — the same shape — and targets **`ADAPTIVE`**, the one
durable brain with no expiry contract, which `governance.govern` auto-promotes with no human review.
That pair is declared below in `DURABLE_FROM_A_MEASUREMENT`. **Declared is not accepted**: the
repair changes what the Adaptive brain contains and is therefore not this module's to make.

⛔ THE MEASUREMENT IS AN AST WALK, NOT A GREP. `grep 'target=LearningTarget'` finds nine of the
eleven: `behavior_evolution` and `adaptive_evolution` pass their target as a keyword argument
*through* `_cohort_candidate`, so the attribute appears in the call rather than in a constructor.
**A grep for a keyword argument misses the call that passes it through.**

This module imports only `ast` and `pathlib` from outside its package, exactly as
`platform/reachability.py` does — but it deliberately does **not** import that module, because
`_is_declaration_module` treats any importer of it as a declared-silence module and this is not one.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_UNITS_PY = Path(__file__).resolve().parent / "units.py"
#: `genios_engine/`. Delegated producers live in another package, and this module reads them as
#: TEXT rather than importing them — see `test_this_module_does_not_import_the_reachability
#: _machinery`, which asserts this file imports nothing from the engine at all.
_ENGINE = Path(__file__).resolve().parent.parent

#: Targets whose publication writes a DURABLE row. Mirrors `publisher._BRAIN_TARGETS`, and
#: `test_the_durable_set_matches_the_publisher` asserts it has not drifted from it — a copy that
#: can disagree with the thing it copies is worse than no copy.
DURABLE_BRAIN_TARGETS: frozenset[str] = frozenset({"ORGANIZATION", "BEHAVIOR", "ADAPTIVE"})

#: Every analysis unit and the target it proposes — `{unit: (target, why)}`.
#:
#: ⛔ Checked in BOTH directions against the AST by
#: `tests/feedback/test_a_unit_may_not_write_a_durable_brain_from_a_measurement.py`: a unit missing
#: from this map fails the build, an entry naming a unit that no longer exists fails the build, and
#: a declared target that no longer matches the code fails the build. A new unit therefore cannot
#: pick a sink silently.
#:
#: `None` as a target means the unit proposes nothing today — it is a stub, and its `why` says so.
UNIT_TARGETS: dict[str, tuple[str | None, str]] = {
    "unit_feedback_learning": (
        "METRICS",
        "Per rule: what humans actually said about its cards. A rate and its counts — a "
        "measurement, published, never reviewed"),
    "unit_outcome_analysis": (
        "METRICS",
        "Per (capability, play): success / neutral / negative counts plus attention cost. Its own "
        "docstring ends '→ a metric'"),
    "unit_actor_outcome_analysis": (
        "METRICS",
        "The same rows as `outcome_analysis` grouped by person rather than play, private to them"),
    "unit_pattern_learning": (
        "ORGANIZATION",
        "A repeated enterprise pattern is a CLAIM about the company, not a measurement — which is "
        "why it is the one unit that targets a durable brain and why `govern` sends it to human "
        "review when `organization_requires_review` is set"),
    "unit_preference_learning": (
        None,
        "⛔ `return []`. Its docstring said *'Empty until the inbox lands'* until 2026-10-02, and "
        "⛔ **THE INBOX LANDED**: `learning_event_inbox` (migration 0046) exists, is written in "
        "production by `reason/moments/store.record_feedback` (reached from "
        "`api/moment_routes.py:746`), and is loaded into EVERY weekly batch as `batch.inbox`. "
        "⛔ What has not landed is an inbox event of the KIND this unit needs: every row written "
        "today carries `payload.kind == \"moment_feedback\"` — a card action, not an explicit "
        "first-person instruction with a subject, a scope and exceptions. **The gap is a `kind`, "
        "not a table**, and that decides who can close it: a table is a migration, a `kind` is a "
        "SURFACE where a founder states a preference, and there is none. "
        "⛔ `LearningTarget` has no `PREFERENCE` member either, so a bounded personal preference "
        "would arrive as `BEHAVIOR` with a resolved `subject_principal`. The sink exists; the "
        "input does not. ⛔ MOVES WHEN that surface exists — **not** when a model is pointed at "
        "the text: the Atlas is explicit that *'adding a model directly to empty units would "
        "produce eloquent ungrounded preferences. First wire typed evidence.'* Atlas Layer 7 #1, "
        "its own P1"),
    "unit_temporary_memory": (
        None,
        "⛔ `return []`. Its docstring said *'Empty until the inbox lands'* until 2026-10-02 — "
        "⛔ **the inbox landed; the `kind` did not.** See `unit_preference_learning`. "
        "⛔ EVERYTHING DOWNSTREAM IS ALREADY BUILT, which is what makes the missing input the whole "
        "of the gap: the Atlas's worked example *'Pause outreach for seven days'* (`L7-18`) needs "
        "`LearningTarget.RUNTIME`, `govern()` routing Runtime to `TEMPORARY`, `publish_runtime` "
        "writing `temporary_memories` with a `NOT NULL expires_at`, `preflight`'s three expiry "
        "checks and `expire_leases` — **all five exist**, and `learning_event_inbox` even carries a "
        "`lease_until` column for exactly this. ⛔ MOVES WHEN a surface lets a founder state a "
        "dated directive. "
        "The RUNTIME lease path IS live, through "
        "`packs/brains/adaptive_lease`, which is why this stub costs nothing today. "
        "⛔ AND IT IS A STUB, NOT A `DELEGATED` PLACEHOLDER, AND THE DIFFERENCE IS THE INPUT. This "
        "unit wants an **explicit human directive** — *'Explicit directive → a Runtime lease with "
        "a mandatory expiry'* — from a structured inbox that does not exist. `adaptive_lease` "
        "INFERS a lease from `card_feedback_verdicts`. **Same sink, different input**, so one does "
        "not do the other's job and recording it as a delegation would be a lie about which "
        "capability exists. Atlas gap #1's residue, with `unit_preference_learning`"),
    "unit_behavior_evolution": (
        "BEHAVIOR",
        "⛔ A PLACEHOLDER, NOT A GAP — CORRECTED 2026-10-02. It proposes nothing (it delegates to "
        "`_cohort_candidate`, whose entire body is `return []`) and **the work it names is built "
        "and wired one package down**: `packs/brains/behavior_distill.distill` reads L2.4's trend "
        "facts, gates them and proposes, and `feedback/brain_pipeline.brain_pipeline_proposals` "
        "appends its output to the same weekly run. See `DELEGATED`."),
    "unit_adaptive_evolution": (
        "ADAPTIVE",
        "⛔ THE SAME SHAPE, AND THE SAME CORRECTION. `packs/brains/adaptive_lease.lease_proposals` "
        "turns card verdicts into **RUNTIME** leases with a mandatory 7-day expiry, through the "
        "same driver — which is why the Adaptive brain's leased half is bounded and only "
        "`unit_recommendation_learning`'s durable half is not. See `DELEGATED`."),
    "unit_recommendation_learning": (
        "ADAPTIVE",
        "⛔⛔ THE DECLARED VIOLATION — see `DURABLE_FROM_A_MEASUREMENT`. Play efficacy weighed "
        "against attention cost, into a durable brain, auto-promoted"),
    "unit_performance_optimization": (
        "METRICS",
        "Delivery, pre-delivery failure and engagement, separated. Rates and counts"),
    "unit_knowledge_evolution": (
        "KNOWLEDGE_SUGGESTION",
        "A sustained-poor-outcome human-review suggestion. ⛔ `govern` sends it to HUMAN_REVIEW "
        "unconditionally and the comment says this 'cannot be removed from policy' — Layer 7 never "
        "mutates the Expert Brain"),
}

#: ⛔⛔ Units that route a MEASUREMENT into a DURABLE brain. Declared so it cannot ship silently;
#: `{unit: (what the Atlas forbids, mover)}`.
#:
#: ⛔ DECLARED IS NOT ACCEPTED. Every repair — adding TTL/decay to `ADAPTIVE`, prohibiting durable
#: `ADAPTIVE` publication, or retargeting this unit to `METRICS` — changes what the Adaptive brain
#: CONTAINS, and `packs/compiler/runtime_brains.py` reads that brain into the compiled expertise
#: package. That is a contract decision, not a tidy-up.
DURABLE_FROM_A_MEASUREMENT: dict[str, tuple[str, str]] = {
    "unit_recommendation_learning": (
        "⛔ ATLAS AUTHORITY BOUNDARY, VERBATIM: Recommendation Learning may 'compare play efficacy "
        "and attention cost' with **'No self-training from recommendation score.'** This unit "
        "publishes `efficacy_bp` into the `adaptive` brain; `packs/compiler/runtime_brains.py` "
        "selects `brain in ('organization','behavior','adaptive')` INTO the compiled expertise "
        "package; and the recommender reasons from that package. ⛔ The score trains the thing "
        "that produced it. "
        "⛔ AND IT CANNOT EXPIRE: `contracts/learning.py` permits `expires_at` only when the "
        "target is RUNTIME, `publish_brain` inserts no expiry column, and "
        "`governance.preflight` applies THREE expiry checks to RUNTIME and NONE to ADAPTIVE. "
        "`packs/brains/adaptive_lease.py` states the principle this breaks: *'a lease that never "
        "expires is a permanent memory wearing a temporary label… it is the entire difference "
        "between this brain and the Organization brain.'* "
        "⛔ AND NO HUMAN SEES IT: `govern` returns PROMOTED / 'auto_promote', because the proposal "
        "is organization-visible with no principal — which `preflight` explicitly allows as "
        "'org-derived'.",
        "⛔ MOVES WHEN Rohit ratifies one of the three repairs in "
        "`speedrun008/YCW27/layer-6-learning/07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md` "
        "§2. ⛔ Never by this module. ⛔ CORRECTED BY `S10`: THIS ENTRY WAS SILENT ON WHETHER THE "
        "PATH IS OPEN, AND IT IS NOT — see `BLOCKED_BY_ARITHMETIC` below for the gate that "
        "closes it and for the sharper production query `S6` made answerable. The code-level "
        "readers are the pack compiler, `contracts/learned_state.py` and `api/brain_routes.py`"),
}

#: ⛔⛔ THE DECLARED VIOLATION ABOVE IS UNREACHABLE TODAY, AND NOT BY DESIGN — `{unit: (the gate,
#: the arithmetic, mover)}`.
#:
#: ⛔ `orchestrator.run_learning` runs `validate_learning` FIRST and `continue`s on failure, so
#: `preflight` and `govern` never see the object:
#:
#:     ok, reason = validate_learning(obj, policy)
#:     if not ok: held += 1; _record_evaluation(..., result="held", sink=reason); continue
#:     gate = preflight(obj, policy, now=now)      # never reached
#:     decision = govern(obj, policy)              # never reached
#:
#: ⛔⛔ AND THAT MAKES THE OBVIOUS REPAIR DANGEROUS. Measuring `distinct_days` properly is correct
#: for the five sibling constants, is what `unit_pattern_learning` already does (`len(g["days"])`),
#: and the data is in hand — `closed_at` is loaded and `unit_outcome_analysis` already derives
#: `first`/`last` from it. **A future engineer making that obviously-correct fix would silently
#: unblock an auto-promoted durable ADAPTIVE write that trains the recommender on its own score.**
#: `tests/feedback/test_the_declared_violation_is_blocked_by_arithmetic.py` is the tripwire.
#:
#: ⛔ THREE THINGS WOULD EACH OPEN IT, and the guard asserts all three:
#:   1. the constant becoming a measurement;
#:   2. a stored revision with `min_distinct_days = 1` — `load_or_seed_policy` assigns the column
#:      verbatim with no clamp and `migrations/0045` has no CHECK (the only locked constraint on
#:      that table is `learning_policies_knowledge_review_locked`). Latent only because no
#:      policy-write surface exists;
#:   3. `validate_learning` moving after `govern`, which would let governance promote first.
#:
#: ⛔ AND THERE IS A SECOND GATE BEHIND THE FIRST, declared so neither direction is a surprise:
#: `confidence_bp = efficacy_bp` against `min_confidence_bp = 6000`. Fixing `distinct_days` alone
#: does not necessarily open the path — a play still needs >=60% efficacy after the attention
#: discount. *A gate that is always red is a gate nobody reads*, and two of them in series is how
#: the first gets removed by somebody who never saw the second.
BLOCKED_BY_ARITHMETIC: dict[str, tuple[str, str, str]] = {
    "unit_recommendation_learning": (
        "validate_learning -> insufficient_distinct_days",
        "the unit passes `evidence=LearningEvidence(..., distinct_days=1)` as a CONSTANT while "
        "`LearningPolicy.min_distinct_days` defaults to 2, so `1 < 2` holds for every cohort and "
        "the proposal is recorded `result_state='held'`, "
        "`sink_reason='insufficient_distinct_days'` before governance runs. \u26d4 The reason "
        "reads as *'not enough evidence yet'* when the truth is *'this unit passes a constant'* "
        "\u2014 a counted refusal that is MISNAMED rather than unnamed",
        "\u26d4 MOVES WHEN Rohit ratifies ADR-10. The measurement that sizes the decision is now "
        "available because `S6` built the evaluation ledger: `select unit, result_state, "
        "sink_reason, count(*) from learning_object_evaluations where unit = "
        "'recommendation_learning' group by 1, 2, 3` \u2014 every row `held / "
        "insufficient_distinct_days` means the durable ADAPTIVE path has never once been "
        "exercised and the blast radius is ZERO. `select brain, count(*) from "
        "learned_brain_entries group by brain` answers WHETHER; this answers WHY NOT"),
}


#: ⛔ The two hops that carry a delegated producer's output into the weekly run.
#: `orchestrator.run_learning` → `brain_pipeline.brain_pipeline_proposals` → the producer.
#: `run_learning` is itself driven by the heartbeat (`api/routes.py`'s maintenance sweep calls
#: `run_learning_sweep`), which is asserted by `tests/test_learning_orchestrator.py`.
DRIVER_ENTRY = ("feedback/orchestrator.py", "run_learning")
DRIVER_HOP = ("feedback/brain_pipeline.py", "brain_pipeline_proposals")

#: ⛔⛔ UNITS IN THE CANONICAL REGISTRY WHOSE JOB IS DONE ELSEWHERE — `{unit: (producer, why,
#: mover)}`, where `producer` is `<package path>.<function>` under `genios_engine/`.
#:
#: ⛔ WHY THIS TABLE EXISTS, AND WHAT IT COST TO NOT HAVE IT. The GeniOS Design Atlas records
#: Layer 7 gap #2 as *"Direct personalization evolution is missing. Behavior and Adaptive cohort
#: builder returns no proposals"*, citing these two units. **It is not missing.** The stub
#: (`365cf7a6`, 2026-08-08, *"the ten analysis units"*) predates the real implementation
#: (`ed1b10c3`, 2026-09-07, *"Layer 3 v2 … the four brains"*) by a month: the work was built one
#: package down and the placeholder was never removed or declared.
#:
#: ⛔ **Two readers have now reached the Atlas's wrong conclusion from the same evidence** — the
#: Atlas itself, and this programme on 2026-10-02, which recorded gap #2 as "the only fully LIVE
#: one" before reading `brain_pipeline_proposals`. *A call site that looks wired is not a wired
#: call site — and a call site that looks DEAD is not a dead feature.*
#:
#: ⛔ The placeholders are DECLARED rather than deleted. Deleting them would take the Atlas's
#: component names out of `ALL_ANALYSIS_UNITS` — the one list a reader scans to see which Layer 7
#: components exist — and they cost nothing, returning `()`.
#: ⛔ `{unit: (producer, the target the PRODUCER emits, why, mover)}`.
#:
#: ⛔⛔ THE TARGET IS IN THIS TABLE BECAUSE `durable_from_a_measurement()` CANNOT SEE THESE
#: PRODUCERS. That function reads `UNIT_TARGETS`, which is `units.py`'s registry — and
#: `brain_pipeline_proposals` appends proposals from two producers in ANOTHER PACKAGE straight into
#: the same run. Without this column, "which producer may write which brain" was guarded for eleven
#: units and unguarded for the two that actually produce. *One guard over eleven packages catches
#: the twelfth — and a guard that stops at a package boundary catches nothing across it.*
DELEGATED: dict[str, tuple[str, str, str, str]] = {
    "unit_behavior_evolution": (
        "packs/brains/behavior_distill.py::distill",
        "BEHAVIOR",
        "⛔ ATLAS COMPONENT *Behavior Evolution* — *'Learn stable ways a person/team works | "
        "Population and identity scoped'* — IS BUILT, 776 lines. `distill` reads L2.4's published "
        "trend facts, gates them against the tenant's own `LearningPolicy` floors, labels them "
        "(deterministically: `brain_pipeline_proposals` passes `labeler=None`, so N-4 spends "
        "nothing on a model) and returns proposals plus every refusal, because *'a batch that "
        "proposed nothing because everything was refused and a batch that had nothing to read are "
        "different states'*. ⛔ It takes no `now` on purpose, so the same facts mint the same "
        "content-addressed proposal on any day and `publish_brain` can answer "
        "`no_material_change` instead of a version a week. "
        "⛔ IT TARGETS A DURABLE BRAIN AND THAT IS CORRECT HERE: a behaviour pattern is a CLAIM "
        "about how a person or team works, not a measurement — the same category as "
        "`unit_pattern_learning`'s ORGANIZATION proposals — and the Atlas's boundary for this "
        "component is *'population and identity scoped'*, not *'decays and expires'*. That is why "
        "it is not an entry in `DURABLE_FROM_A_MEASUREMENT`.",
        "⛔ MOVES WHEN somebody decides this unit should produce in its own right — which would "
        "make TWO producers for one brain subject, the shape `clamp_confidence` was filed under in "
        "L5. ⛔ Never by wiring `_cohort_candidate`: there is nothing left for it to do"),

    "unit_adaptive_evolution": (
        "packs/brains/adaptive_lease.py::lease_proposals",
        "RUNTIME",
        "⛔ ATLAS COMPONENT *Adaptive Evolution* — *'Learn short-horizon play/timing effectiveness "
        "| Decays, expires, and rolls back'* — IS BUILT, 301 lines, and it is the one place the "
        "Atlas's TTL requirement is actually met: `lease_proposals` emits a **RUNTIME** target, "
        "which `govern()` routes to `TEMPORARY` and `publish_runtime` writes to "
        "`temporary_memories`, whose `expires_at` is `NOT NULL`. 7 days, clamped to the tenant's "
        "`max_runtime_ttl_seconds`, enforced by the column, by `preflight`'s three expiry checks "
        "and by `expire_leases`. ⛔ *'A lease that never expires is a permanent memory wearing a "
        "temporary label.'*",
        "⛔ MOVES WHEN the Adaptive TTL decision in "
        "`speedrun008/YCW27/layer-6-learning/07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md` "
        "§2 is ratified — if durable ADAPTIVE publication is prohibited, this unit's name becomes "
        "the natural home for the lease path and the delegation collapses"),
}


#: ⛔ The visibility scopes that need no reader-side principal check — `contracts/learning
#: .VisibilityScope`'s two open members. Everything else is CONSTRAINED and only legal where the
#: reader intersects principals.
OPEN_SCOPES: frozenset[str] = frozenset({"ORGANIZATION", "PUBLIC"})

#: ⛔⛔ DURABLE PROPOSALS WHOSE VISIBILITY IS CONSTRAINED — `{producer: (scope, why)}`.
#:
#: **EMPTY, AND THAT EMPTINESS IS LOAD-BEARING.** Atlas Layer 7 gap #5 asks that *"prohibited
#: evidence never reaches active brain or rendered rationale"*. Measured 2026-10-02 by `S10`:
#:
#:   * the DECISION path enforces it. `packs/compiler/runtime_brains._visibility_allows_package`
#:     is called (`:363`) and requires both scope narrowness and
#:     `set(package.principals) <= set(entry.principals)` — the whole audience must be able to see
#:     the evidence. `contracts/learned_state._visible` is fail-closed on every axis, including an
#:     UNKNOWN scope.
#:   * ⛔ the RENDERED path does not. `api/brain_routes` selects `value` from both sinks filtered
#:     only on `org_id`/`active`/`brain`, and `Depends(get_current_org)` admits any credential of
#:     the org — including a `member` seat, whose own definition in `platform/auth.py` is *"reads
#:     and acts on the cards routed to their own seat, **and nothing org-wide**."*
#:
#: ⛔ **The two facts are only safe TOGETHER.** Nothing constrained can reach that reader today
#: because every producer that writes a durable sink declares an open scope. The day one does not,
#: `tests/feedback/test_a_constrained_brain_value_is_not_rendered_org_wide.py` fails and names
#: `UNFILTERED_BRAIN_READERS` — because the repair is then required in the reader, not here.
#:
#: ⛔ The single constrained `LearningObject` in the engine (`units.unit_actor_outcome_analysis`,
#: `Visibility(PRIVATE, principals=(assignee,))`) targets `METRICS`, which `publish` routes to
#: `learning_metrics` — a table no brain reader selects. That is why it is correct AND absent here.
CONSTRAINED_DURABLE_PROPOSALS: dict[str, tuple[str, str]] = {}

#: ⛔⛔ READERS OF A BRAIN SINK THAT DROP VISIBILITY — `{file: (what it omits, why that is safe
#: today, mover)}`. Checked in BOTH directions: a reader listed here that has STARTED filtering is
#: as much a lie as one that drops visibility and is undeclared.
#:
#: ⛔ DECLARED IS NOT ACCEPTED. The repair — giving the route a seat principal and intersecting it
#: against `visibility.principals` — changes an API contract the dashboard depends on, and the
#: route has no caller identity at all today (`get_current_org` returns an org string, while
#: `AuthCtx` carries `email`/`seat_id`). That is Rohit's, not a tidy-up.
UNFILTERED_BRAIN_READERS: dict[str, tuple[str, str, str]] = {
    "api/brain_routes.py": (
        "`_learned_records` selects `e.value` from `learned_brain_entries` and `_memory_records` "
        "selects `m.value` from `temporary_memories`, both WITHOUT `visibility_scope` / "
        "`visibility`, and render the value as a title plus an evidence line",
        "⛔ SAFE ONLY BECAUSE NOTHING CONSTRAINED CAN ARRIVE: `behavior_distill`, `adaptive_lease` "
        "and `org_discovery` each construct `Visibility(scope=ORGANIZATION)`, and "
        "`CONSTRAINED_DURABLE_PROPOSALS` is empty and guarded empty. A constrained row in either "
        "sink would be rendered to every seat of the org",
        "MOVES WITH `CONSTRAINED_DURABLE_PROPOSALS` — the day a producer declares a constrained "
        "durable scope, this reader must gain a principal intersection first"),

    # ── The three that drop visibility and are CORRECT to. Declared, not excluded by a cleverer
    # regex: a reader special-cased inside the resolver is a reader nobody reads.
    "feedback/publisher.py": (
        "`publish_brain` runs `select version, value from learned_brain_entries … for update` on "
        "the row it is about to supersede",
        "⛔ IT COMPARES, IT NEVER SHOWS. The read is the byte-identical idempotency check, scoped "
        "to the SAME `(org, brain, subject)` as the proposal already in hand, and its result "
        "decides `no_material_change` against `max+1`. Nothing leaves the function. A visibility "
        "predicate here would make a constrained predecessor invisible to its own successor and "
        "turn a supersede into a second active version",
        "MOVES WHEN the publisher renders or returns a predecessor's value instead of comparing "
        "it"),
    "feedback/org_rule_ingest.py": (
        "`select subject, value from learned_brain_entries where brain = 'organization'` for the "
        "approval-subject rules",
        "⛔ OPEN BY CONSTRUCTION, not by omission: the filter pins `brain = 'organization'`, and "
        "`packs/brains/org_discovery` constructs `Visibility(scope=ORGANIZATION)` for every "
        "proposal that can land there. The scope cannot be narrower than the brain",
        "MOVES WITH `org_discovery`'s declared scope — an organization proposal that is not "
        "org-visible makes this read a leak"),
    "packs/brains/behavior_distill.py": (
        "`_PUBLISHED_SUBJECTS_SQL` selects `subject, value` for `brain = 'behavior'` with no "
        "visibility",
        "⛔ IT IS DECAY OF ITS OWN OUTPUT, NOT EVIDENCE. `distill` re-reads the subjects this "
        "module published in order to RETRACT the ones this batch did not re-claim, reading only "
        "`metric` / `direction` / `active` off its own statements. A retraction cannot widen "
        "anybody's visibility, and skipping a constrained row would leave it active forever — "
        "the filter would cause the harm it looks like it prevents",
        "MOVES WHEN this read feeds a proposal's EVIDENCE rather than its retraction"),
}


#: ⛔⛔ CALL SITES WHOSE VISIBILITY COMES FROM STORAGE, NOT FROM SOURCE — `{file: why}`.
#:
#: `durable_proposal_visibilities()` resolves 10 of the engine's 11 `LearningObject(...)` sites.
#: The eleventh is the HUMAN APPROVAL path, which rehydrates a persisted proposal —
#: `Visibility(scope=vis.get("scope"), principals=tuple(vis.get("principals") or ()))` — so its
#: scope is a value in `learning_objects.visibility` and no amount of AST reading can know it.
#:
#: ⛔ THAT IS WHY THE CODE GUARD IS NOT ENOUGH AND THE RECEIPT IS NOT OPTIONAL. The one way a
#: constrained durable row can appear is: a constrained durable proposal is persisted, and a human
#: later approves it. The producers close the first half (`CONSTRAINED_DURABLE_PROPOSALS` is empty
#: and guarded empty); the receipt *"no active brain value is visible to fewer people than the
#: dashboard shows it to"* closes the second, because only the DATABASE can answer it.
#:
#: ⛔ Declared rather than skipped: an unresolved site that is merely tolerated is a hole, and the
#: resolver would then be reporting "nothing constrained" from a sample it never covered.
VISIBILITY_FROM_STORAGE: dict[str, str] = {
    "api/learning_routes.py":
        "the review-to-publish path reconstructs the stored `LearningObject` to re-run current "
        "policy before publishing exactly one version. Its visibility is DATA — read back from "
        "`learning_objects.visibility`, which is what makes the receipt the only honest check",
}


def _callee(fn: ast.AST) -> str | None:
    return fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)


def _kwarg(call: ast.Call, name: str) -> ast.AST | None:
    return next((k.value for k in call.keywords if k.arg == name), None)


def _scope_of(node: ast.AST | None, helpers: dict[str, ast.FunctionDef]) -> str | None:
    """The `VisibilityScope` member a `visibility=` argument resolves to, or None.

    ⛔ RESOLVES ONE LEVEL OF INDIRECTION ON PURPOSE. `units.py` passes `_org_visibility()`, a
    module-level helper whose whole body is `return Visibility(scope=ORGANIZATION)`. Reading only
    the direct form would have resolved 1 of 12 call sites and then reported "nothing constrained"
    from that sample — *a resolver that answers for 1 of 104 answers nothing*, and the coverage
    assertion in the test is what makes this one honest.
    """
    if isinstance(node, ast.Call):
        name = _callee(node.func)
        if name == "Visibility":
            scope = _kwarg(node, "scope")
            if isinstance(scope, ast.Attribute):
                return scope.attr
            if isinstance(scope, ast.Name):
                return scope.id
            return None
        fn = helpers.get(name or "")
        if fn is not None:
            for inner in ast.walk(fn):
                if isinstance(inner, ast.Call) and _callee(inner.func) == "Visibility":
                    return _scope_of(inner, {})
    return None


def durable_proposal_visibilities() -> tuple[tuple[str, str, str, str | None], ...]:
    """Every `LearningObject(...)` in the engine as `(file, unit, target, scope-or-None)`.

    ⛔ A `None` scope is NOT read as "open" — the test fails on it, because an unresolved scope is
    exactly the shape that turns a wrong answer into a plausible one.
    """
    out: list[tuple[str, str, str, str | None]] = []
    for path in sorted(_ENGINE.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):          # pragma: no cover - not reachable in-tree
            continue
        helpers = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _callee(node.func) == "LearningObject"):
                continue
            target = _kwarg(node, "target")
            unit = _kwarg(node, "unit")
            out.append((
                str(path.relative_to(_ENGINE)),
                unit.value if isinstance(unit, ast.Constant) else "<computed>",
                target.attr if isinstance(target, ast.Attribute) else "<computed>",
                _scope_of(_kwarg(node, "visibility"), helpers)))
    return tuple(out)


def constrained_durable_proposals() -> tuple[tuple[str, str, str], ...]:
    """`(file, unit, scope)` for every durable proposal whose visibility is not an open scope."""
    return tuple((f, u, s) for f, u, t, s in durable_proposal_visibilities()
                 if t in DURABLE_BRAIN_TARGETS and s is not None and s not in OPEN_SCOPES)


def unresolved_proposal_visibilities() -> tuple[tuple[str, str, str], ...]:
    """`(file, unit, target)` for every proposal whose visibility this module could not resolve."""
    return tuple((f, u, t) for f, u, t, s in durable_proposal_visibilities() if s is None)


#: The two tables a published brain value lives in. `publisher.publish_brain` writes the first
#: and `publish_runtime` the second; every reader of learned content selects from one of them.
BRAIN_SINKS: tuple[str, ...] = ("learned_brain_entries", "temporary_memories")


def sql_literals(source: str) -> tuple[str, ...]:
    """Every string literal handed to a ``text(...)`` call — prose excluded.

    ⛔ WHY THIS IS SHARED RATHER THAN GREPPED, AND IT COST A FAILING BUILD TO LEARN AGAIN.
    `tests/feedback/test_one_l6_admission_sequence.py` asserted *"only the publisher writes a brain
    entry"* by scanning every engine LINE for `insert into temporary_memories` — and it broke on a
    COMMENT in this module explaining the difference between a writer and a reader. Fourth time in
    one session that a text-level guard matched the sentence documenting the thing it forbids.
    ⛔ It also had the opposite hole: an insert split across two source lines
    (`"insert into " "temporary_memories ("`) matched NOTHING, because the line scan never sees
    the concatenated literal. Reading the AST closes both — strictly more precise, not laxer.

    Collected from the whole call subtree, so `text("..." + CONST + "...")` is read too.
    """
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and _callee(node.func) == "text"):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                out.append(inner.value)
    return tuple(out)


def brain_sink_value_readers() -> tuple[tuple[str, bool], ...]:
    """`(file, carries_visibility)` for every `text(...)` query that selects a brain sink's VALUE.

    ⛔ THE VALUE, NOT THE ROW. A query that reads only metadata — `memory_id`, `version`,
    `created_at` — does not put learned content in front of anybody, and `api/learning_routes.brains`
    and `packs/brains/adaptive_lease` are both that shape. Widening this to every select would
    bury the two readers that actually render content among readers that cannot.
    """
    out: list[tuple[str, bool]] = []
    for path in sorted(_ENGINE.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):          # pragma: no cover - not reachable in-tree
            continue
        del tree
        for blob in sql_literals(path.read_text(encoding="utf-8")):
            sql = " ".join(blob.lower().split())
            # ⛔ A READ, NOT A WRITE. The first version of this matched any query naming a sink and
            # reported `feedback/publisher.py` as a reader that drops visibility — it is the
            # WRITER, and its `insert into temporary_memories (… value …)` has a `value` column in
            # the column list. A producer is not a reader, and a resolver that cannot tell them
            # apart would have put the publisher in a table about who may SEE a brain value.
            if not any(f"from {s}" in sql for s in BRAIN_SINKS):
                continue
            if not re.search(r"(^|[ ,.])([a-z]\.)?value([ ,]|$)", sql):
                continue
            out.append((str(path.relative_to(_ENGINE)), "visibility" in sql))
    return tuple(out)


def undeclared_unfiltered_readers() -> tuple[str, ...]:
    """Files that read a brain VALUE without its visibility and are not declared."""
    return tuple(sorted({f for f, vis in brain_sink_value_readers()
                         if not vis and f not in UNFILTERED_BRAIN_READERS}))


def stale_unfiltered_readers() -> tuple[str, ...]:
    """Declared files where the declaration has stopped being true — ANY value read now carrying
    visibility, or no value read left at all.

    ⛔ `any`, NOT `all`, AND THAT IS A REPAIR. The first version required EVERY read in the file to
    carry visibility, and a mutation adding `e.visibility` to ONE of `api/brain_routes.py`'s two
    value queries SURVIVED — the declaration describes *specific queries*, and it is already
    partly false once one of them changes. It is the same mistake in reverse as S8's invalid
    mutation, *"removed one marker while two remained in the window"*: a window-wide predicate
    cannot answer a per-query question.
    """
    measured = brain_sink_value_readers()
    out = []
    for f in UNFILTERED_BRAIN_READERS:
        reads = [vis for g, vis in measured if g == f]
        if not reads or any(reads):
            out.append(f)
    return tuple(sorted(out))


def hardcoded_distinct_days() -> tuple[tuple[str, str, int | None], ...]:
    """`(unit, target, constant)` for every `LearningObject` whose evidence pins `distinct_days`.

    ⛔ A `None` constant means the unit COMPUTES it — `unit_pattern_learning` passes
    `len(g["days"])`, which is the shape the others should have and the reason the fix looks
    obvious. Only a unit that pins a literal AND targets a durable brain is a blocked path.
    """
    out: list[tuple[str, str, int | None]] = []
    tree = ast.parse(_UNITS_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _callee(node.func) == "LearningObject"):
            continue
        unit = _kwarg(node, "unit")
        target = _kwarg(node, "target")
        evidence = _kwarg(node, "evidence")
        days: int | None = None
        if isinstance(evidence, ast.Call):
            value = _kwarg(evidence, "distinct_days")
            if isinstance(value, ast.Constant) and isinstance(value.value, int):
                days = value.value
        out.append((unit.value if isinstance(unit, ast.Constant) else "<computed>",
                    target.attr if isinstance(target, ast.Attribute) else "<computed>", days))
    return tuple(out)


def durable_units_pinning_distinct_days() -> tuple[str, ...]:
    """Units that write a DURABLE brain while pinning `distinct_days` to a literal."""
    return tuple(sorted(u for u, t, d in hardcoded_distinct_days()
                        if t in DURABLE_BRAIN_TARGETS and d is not None))


def _module_functions(path: Path) -> dict[str, ast.FunctionDef]:
    """Every top-level function in one engine source file, by name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _called_names(node: ast.AST) -> frozenset[str]:
    """Every function NAME called inside `node`, whether bare or through an attribute.

    ⛔ Both forms are needed: `run_learning` calls `brain_pipeline_proposals(...)` bare, while
    `brain_pipeline_proposals` calls `behavior_distill.distill(...)` through the module object. A
    resolver that handled only one of the two would report half this chain as broken.
    """
    names: set[str] = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        if isinstance(call.func, ast.Name):
            names.add(call.func.id)
        elif isinstance(call.func, ast.Attribute):
            names.add(call.func.attr)
    return frozenset(names)


def _targets_in(node: ast.AST) -> frozenset[str]:
    """Every `LearningTarget.X` named anywhere inside `node`.

    ⛔ One resolver for both questions — a unit's own target and a delegated producer's — so the
    two can never disagree about what counts as naming a target.
    """
    return frozenset(
        d.attr for d in ast.walk(node)
        if isinstance(d, ast.Attribute) and isinstance(d.value, ast.Name)
        and d.value.id == "LearningTarget")


def undelegated_silent_units() -> tuple[str, ...]:
    """⛔ Units that propose nothing, name a target, and explain it nowhere.

    A unit in `ALL_ANALYSIS_UNITS` that returns nothing is either a **declared stub** (`None` in
    `UNIT_TARGETS`, with its reason) or a **declared placeholder** (an entry in `DELEGATED`, naming
    the producer that does its job). ⛔ Anything else is the state that produced the Atlas's wrong
    verdict twice: a named component, a silent unit, and no record of which it is.
    """
    out = []
    for unit in registered_units():
        declared, _why = UNIT_TARGETS.get(unit, (None, ""))
        if declared is None:                       # a declared stub, reason already required
            continue
        if _proposes_something(unit):
            continue
        if unit not in DELEGATED:
            out.append(unit)
    return tuple(out)


def stale_delegations() -> tuple[str, ...]:
    """⛔ The second direction: a delegation naming a unit that is no longer silent, or gone."""
    registered = frozenset(registered_units())
    out = []
    for unit in sorted(DELEGATED):
        if unit not in registered or _proposes_something(unit):
            out.append(unit)
    return tuple(out)


def broken_delegations() -> tuple[tuple[str, str], ...]:
    """⛔⛔ THE GUARD WITH TEETH — `(unit, what is broken)` for every delegation that is not live.

    Five links, and losing any one of them silently returns the layer to the state the Atlas
    recorded: a registry that lists the component and a product that produces nothing.

        1 the producer file and function exist
        2 the producer is not itself a `return []`
        3 `brain_pipeline_proposals` calls that producer
        4 `run_learning` calls `brain_pipeline_proposals`
        5 ⛔ the producer still emits the TARGET this table declares — the sink, and therefore
          whether the proposal expires, waits for a human, or becomes permanent
    """
    out: list[tuple[str, str]] = []
    entry_path, entry_fn = DRIVER_ENTRY
    hop_path, hop_fn = DRIVER_HOP

    entry = _module_functions(_ENGINE / entry_path).get(entry_fn)
    hop = _module_functions(_ENGINE / hop_path).get(hop_fn)
    if entry is None:
        return ((entry_fn, f"{entry_path} no longer defines {entry_fn}"),)
    if hop is None:
        return ((hop_fn, f"{hop_path} no longer defines {hop_fn}"),)
    if hop_fn not in _called_names(entry):                                           # link 4
        out.append((entry_fn, f"{entry_fn} no longer calls {hop_fn} — every delegated "
                              "producer's output stops reaching the weekly run"))

    hop_calls = _called_names(hop)
    for unit, (producer, target, _why, _mover) in sorted(DELEGATED.items()):
        rel, _, func = producer.partition("::")
        path = _ENGINE / rel
        if not path.exists():                                                        # link 1
            out.append((unit, f"producer file is gone: {rel}"))
            continue
        module = _module_functions(path)
        node = module.get(func)
        if node is None:
            out.append((unit, f"{rel} no longer defines {func}"))
            continue
        if _returns_only_empty(node) or not _called_names(node):                     # link 2
            # ⛔ TWO SHAPES OF STUB. `return []` / `return ()` is one; `return (), ()` — written to
            # match these producers' `(proposals, refusals)` signature — is the other, and it is a
            # two-element tuple that `_returns_only_empty` reads as non-empty. **A stub of either
            # shape calls nothing**, which is what the second half of this condition catches.
            out.append((unit, f"{producer} does no work — the delegation points at a stub"))
        if func not in hop_calls:                                                    # link 3
            out.append((unit, f"{hop_fn} no longer calls {func}"))
        # link 5 — the target is read from the whole MODULE, not the one function: both producers
        # build their `LearningObject` in a private `_proposal` / `_lease` helper that `func` then
        # calls, so a function-scoped walk would find no target at all and report every delegation
        # as broken. ⛔ The same mistake as grepping for a keyword argument, one level up.
        emitted = _targets_in(ast.parse(path.read_text(encoding="utf-8")))
        if emitted != frozenset({target}):
            out.append((unit, f"{producer}'s module emits {sorted(emitted) or 'no target'}, "
                              f"not the declared {target!r} — the SINK changed"))
    return tuple(out)


def _unit_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name.startswith("unit_")}


def measured_unit_targets() -> dict[str, tuple[str, ...]]:
    """`{unit: (every `LearningTarget.X` named anywhere in its body,)}` — read from the AST.

    Walking the whole body rather than the `LearningObject(...)` call is deliberate: two units pass
    their target as a keyword argument through `_cohort_candidate`, and a constructor-only walk
    would report them as choosing nothing.
    """
    tree = ast.parse(_UNITS_PY.read_text(encoding="utf-8"))
    return {name: tuple(sorted(_targets_in(node)))
            for name, node in _unit_functions(tree).items()}


def registered_units() -> tuple[str, ...]:
    """The units `ALL_ANALYSIS_UNITS` actually runs, in canonical order, read from the AST.

    ⛔ `ALL_ANALYSIS_UNITS` is an ANNOTATED assignment, so it is an `ast.AnnAssign` with a single
    `.target` and not an `ast.Assign` with `.targets`. The first version of this function matched
    only `ast.Assign` and returned an empty tuple — which `missing_units()` then reported as all
    eleven declarations being stale. **The both-directions check caught its own resolver**, which
    is the whole argument for writing the second direction.
    """
    tree = ast.parse(_UNITS_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        named = (isinstance(node, ast.AnnAssign)
                 and isinstance(node.target, ast.Name)
                 and node.target.id == "ALL_ANALYSIS_UNITS")
        if not named and isinstance(node, ast.Assign):
            named = any(isinstance(t, ast.Name) and t.id == "ALL_ANALYSIS_UNITS"
                        for t in node.targets)
        if named and node.value is not None:
            return tuple(e.id for e in ast.walk(node.value) if isinstance(e, ast.Name))
    return ()


def undeclared_units() -> tuple[str, ...]:
    """Units the registry runs that this module does not declare — a new unit picking a sink."""
    return tuple(u for u in registered_units() if u not in UNIT_TARGETS)


def missing_units() -> tuple[str, ...]:
    """⛔ Declared entries naming a unit the registry no longer runs — the second direction."""
    registered = frozenset(registered_units())
    return tuple(sorted(u for u in UNIT_TARGETS if u not in registered))


def drifted_units() -> tuple[tuple[str, str | None, tuple[str, ...]], ...]:
    """⛔ `(unit, declared, measured)` wherever the declaration no longer matches the code.

    A stub declares `None` and must name no target; a non-stub must name exactly its declared one.
    This is the check with teeth: a one-word edit to a unit's sink fails the build.
    """
    measured = measured_unit_targets()
    out = []
    for unit, (declared, _why) in sorted(UNIT_TARGETS.items()):
        found = measured.get(unit, ())
        if declared is None:
            if found:
                out.append((unit, declared, found))
        elif found != (declared,):
            out.append((unit, declared, found))
    return tuple(out)


def durable_from_a_measurement() -> tuple[str, ...]:
    """⛔ Units whose declared target is a durable brain while their siblings call it a metric.

    Derived, not listed: a unit is reported when its declared target is in
    `DURABLE_BRAIN_TARGETS` and it is NOT the one unit whose output is a claim about the company
    (`pattern_learning`) or a stub that proposes nothing.
    """
    measured = measured_unit_targets()
    claims = {"unit_pattern_learning"}
    return tuple(sorted(
        unit for unit, (declared, _why) in UNIT_TARGETS.items()
        if declared in DURABLE_BRAIN_TARGETS and unit not in claims and measured.get(unit)
        and _proposes_something(unit)))


def _returns_only_empty(node: ast.FunctionDef) -> bool:
    """Whether every `return` in the function hands back a literal empty list or tuple.

    ⛔ TUPLES ARE INCLUDED BECAUSE THE DELEGATED PRODUCERS RETURN ONE. `behavior_distill.distill`
    and `adaptive_lease.lease_proposals` both return `(proposals, refusals)`, so a stub written
    for their signature would be `return (), ()` and a list-only check would call it real.

    ⛔ AND IT STILL CANNOT SEE EVERY STUB: `return (), ()` is a two-element tuple, so this returns
    False for it. That is why `broken_delegations`' link 2 **also** requires the producer's body to
    contain at least one call — a stub of any shape has none. *A helper that answers a narrower
    question than its name asks is the defect, so the narrower answer is named here rather than
    relied on silently.*
    """
    returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
    return bool(returns) and all(
        isinstance(r.value, (ast.List, ast.Tuple)) and not r.value.elts for r in returns)


def _proposes_something(unit: str) -> bool:
    """Whether the unit can emit a proposal today.

    ⛔ TWO WAYS A UNIT PROPOSES NOTHING, and the first version of this function only saw one of
    them: it detected delegation to a helper whose body is `return []` and reported
    `unit_preference_learning` — whose own body *is* `return []` — as proposing something. **A
    helper that answers a narrower question than its name asks is the defect this module exists to
    catch**, reproduced inside the module itself.
    """
    tree = ast.parse(_UNITS_PY.read_text(encoding="utf-8"))
    node = _unit_functions(tree).get(unit)
    if node is None:
        return False
    if _returns_only_empty(node):                     # 1 · it returns `[]` itself
        return False
    helpers = {c.func.id for c in ast.walk(node)
               if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    for other in tree.body:                           # 2 · it delegates to one that does
        if (isinstance(other, ast.FunctionDef) and other.name in helpers
                and _returns_only_empty(other)):
            return False
    return True


__all__ = ["DELEGATED", "DRIVER_ENTRY", "DRIVER_HOP", "DURABLE_BRAIN_TARGETS",
           "DURABLE_FROM_A_MEASUREMENT", "UNIT_TARGETS",
           "broken_delegations", "drifted_units", "durable_from_a_measurement",
           "measured_unit_targets", "missing_units", "registered_units", "stale_delegations",
           "undeclared_units", "undelegated_silent_units"]
