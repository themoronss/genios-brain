r"""What `feedback/` deliberately does not call — L6/L7's learning plane's declared silence.

⛔ MOST OF THESE ARE BUILD-TIME PROPERTY GUARDS, and that distinction is the whole value of
reading them rather than counting them. `attribution.timing_never_grades_accuracy`,
`every_legacy_reason_still_grades_the_way_it_did` and every `target_policy` entry take no
production data and answer questions about a **frozen map** or the **checked-in AST** — identical
on every run. ⛔ The counts that used to open this paragraph (*"nine of the twelve"*, *"target
policy's seven"*) are gone rather than updated: `S10` added five entries and made both wrong in one
commit, which is the second time this paragraph has gone stale by succeeding. *A hardcoded count in
a document is wrong the next day.* L5 learned this the hard way with `lane_recall`: **a function that takes no data cannot be
measuring production**, and wiring one would re-derive a settled answer on every tick.

⛔ AND THE COUNT IN THIS PARAGRAPH IS WHY THE GUARD ASSERTS A SET. It read *"two of the five"*
until `target_policy` landed, which is correct prose going stale the moment the work succeeds —
exactly the shape of **a membership list shrinks every time the work succeeds; an invariant does
not**. No test asserts a number here; `tests/platform/test_every_package_says_what_it_does_not_call.py`
compares the declared SET against the measured one, in both directions.

The machinery is `platform/reachability.py`, shared rather than copied. ⛔ Three wiring mechanisms
are subtracted before anything reaches this table: a **call**, a **decorator** (a route handler has
no Python caller by design) and a **reference** (`Depends(f)`, a dispatch table, a registry). The
third is the biggest — engine-wide it rescued **46** functions that looked unreached, including
`platform/auth.require_owner` with **35** references.
"""
from __future__ import annotations

from pathlib import Path

from genios_engine.platform.reachability import (engine_sources, missing, now_called,
                                                 package_functions, undeclared)

_PKG = Path(__file__).resolve().parent
_ENGINE = _PKG.parent


#: ⛔ Public functions in `feedback/` with no production caller — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by `tests/feedback/test_the_feedback_layer_says_what_it_does_not_call.py`: an entry naming a function that
#: is now called is as much a lie as a function that is unreached and undeclared.
UNREACHED: dict[str, tuple[str, str]] = {
    "attribution.timing_never_grades_accuracy": (
        "⛔ A BUILD-TIME PROPERTY GUARD, NOT A DEFECT. *'Every reason this map calls a "
        "timing-or-fit complaint must be absent from the precision'* denominator. It reads the "
        "frozen attribution map and nothing else, so its answer cannot differ between two runs of "
        "the same build. Three test callers, which are the correct and only ones. ⛔ **A function "
        "that takes no production data cannot be measuring production** — L5 filed two of "
        "`lane_recall`'s three the same way after first mis-filing them as defects.",
        "MOVES WHEN it is deleted, or when the attribution map changes and it is rewritten. ⛔ "
        "Never by being wired into a sweep: it would re-derive the same answer about unchanged "
        "code for every org on every tick"),

    "attribution.every_legacy_reason_still_grades_the_way_it_did": (
        "⛔ THE SAME SHAPE, AND ITS DOCSTRING IS A PROMISE ABOUT HISTORY: *'The three original "
        "reasons must keep their precision roles exactly.'* A regression guard on a vocabulary, "
        "with one test caller. It protects a past decision from a future edit, which is a "
        "build-time job by definition.",
        "MOVES WITH `timing_never_grades_accuracy` — the two guard one map from opposite sides and "
        "neither is wanted at runtime"),

    "attribution.route": (
        "*'Judgment rows to a ranked layer report. Total over any input.'* Eight test callers — the "
        "most exercised function in this table — and no production caller. ⛔ So the ranking is "
        "correct, well covered, and asked for by nothing: the report it produces has no renderer, "
        "the same shape as `capture/intent_rate` and `packs/substrate_demand`.",
        "MOVES WHEN a precision-by-layer surface exists. ⛔ `calibrate` consumes the RAW judgments "
        "directly, so the ranked view is for a reader rather than for the loop"),

    # ───────────────────────────────────── the permitted-use guards (`S10`, Atlas L7 #5) (4)
    # ⛔ BUILD-TIME PROPERTY GUARDS over the visibility seam, filed exactly like the four above.
    # They read the engine's AST and `text(...)` literals, touch no production data, and their
    # answers are identical on every run for one checkout. The half that CANNOT be answered from
    # source — a visibility rehydrated from `learning_objects.visibility` by the approval path —
    # is a RECEIPT instead: *"no active brain value is narrower than the surface that renders it"*.
    "target_policy.constrained_durable_proposals": (
        "Durable proposals whose visibility is not an open scope. ⛔ Returns `()` and the "
        "emptiness is LOAD-BEARING: `api/brain_routes.py` renders both brain sinks org-wide with "
        "no principal check, and that is safe only because every producer declares "
        "`Visibility(scope=ORGANIZATION)`. The two facts are declared together in "
        "`CONSTRAINED_DURABLE_PROPOSALS` / `UNFILTERED_BRAIN_READERS`",
        "MOVES WITH `api/brain_routes.py` — the day it takes a seat principal and intersects "
        "`visibility.principals`, this pair stops needing to be read together"),
    "target_policy.unresolved_proposal_visibilities": (
        "The call sites whose visibility the resolver could NOT resolve. ⛔ It exists so the "
        "resolver reports its own COVERAGE beside its verdict: an earlier version of this work "
        "resolved 1 of 11 sites and would have reported *'nothing constrained'* from that "
        "sample. *A resolver that answers for 1 of 104 answers nothing*",
        "MOVES WHEN a reader needs per-site coverage at runtime rather than at build time"),
    "target_policy.undeclared_unfiltered_readers": (
        "Files that read a brain VALUE without its visibility and are not declared. The positive "
        "direction of `UNFILTERED_BRAIN_READERS`",
        "MOVES WITH `stale_unfiltered_readers` — the two halves of one both-ways check"),
    "target_policy.stale_unfiltered_readers": (
        "Declared files whose declaration has stopped being true. ⛔ It uses `any`, not `all`: a "
        "mutation adding `visibility` to ONE of `brain_routes`'s two value queries SURVIVED the "
        "first version, because a file-wide predicate cannot answer a per-query question",
        "MOVES WITH `undeclared_unfiltered_readers` — the two halves of one both-ways check"),

    # ───────────────────────────────── the blocked-path guard (`S10`, Atlas L7 #3/#11) (1)
    "target_policy.durable_units_pinning_distinct_days": (
        "⛔ Units that write a DURABLE brain while pinning `evidence.distinct_days` to a literal. "
        "Exactly one does — `unit_recommendation_learning`, whose constant `1` against a default "
        "`min_distinct_days` of 2 is the only thing keeping `DURABLE_FROM_A_MEASUREMENT`'s "
        "declared authority violation unreachable. ⛔ A build-time guard precisely because the "
        "obvious repair (measure the days, as `unit_pattern_learning` already does) would open "
        "that path silently — see `BLOCKED_BY_ARITHMETIC`",
        "⛔ MOVES WHEN Rohit ratifies ADR-10 and the Adaptive representation is decided"),

    "reset.latest_reset_at": (
        "*'Most recent reset timestamp for the org, or None.'* Two test callers. "
        "⛔⛔ CORRECTED 2026-10-02 BY `S10` — THIS ENTRY USED TO READ *'a function that names its "
        "reader and has no caller is a surface that was never built'*, AND IT NAMED NO READER "
        "BECAUSE IT LOOKED FOR ONE INSIDE THIS PACKAGE. **The reader exists, one layer DOWN.** "
        "`deliver/outbox.py` asks at SEND time exactly the question this docstring names — *'has "
        "this org pivoted since my evidence was gathered'* — and cancels a card built before the "
        "latest reset, on the same connection and under the same locks as the authority re-proof. "
        "⛔ IT MAY NOT CALL THIS FUNCTION: `LAYERS` gives `deliver` 6 and `feedback` 7, so "
        "`deliver -> feedback` is an upward import `tests/test_layer_topology.py` fails the build "
        "on, and the query is reimplemented there instead. **The duplication is forced by the "
        "topology, not an oversight.** ⛔ Same decoy-seam shape `contracts/learned_state.py` "
        "already fixed one layer over — *'a consumption contract that only the producing layer "
        "may import is a decoy seam; the vocabulary belongs in `contracts/`'* — and moving this "
        "clock there is the honest repair, not wiring a caller inside `feedback/`. "
        "⛔ *The most expensive stale comment is the one that explains why something was left "
        "undone* — and this one was mine, written three steps earlier.",
        "MOVES WITH `deliver/outbox.py`'s copy of the query. "
        "`tests/feedback/test_the_reset_clock_is_read_one_layer_down.py` fails if either side "
        "stops asking the same question, or if the upward import ever becomes legal — so the two "
        "copies cannot silently diverge and the forced duplication cannot quietly stop being "
        "forced"),

    # ───────────────────────────────────────────────────────────── the target-policy guards (4)
    # ⛔ ALL FOUR ARE BUILD-TIME PROPERTY GUARDS, the same filing as `attribution`'s two above.
    # They read `units.py`'s AST and compare it with `target_policy.UNIT_TARGETS`. None of them
    # touches production data, so **a function that takes no production data cannot be measuring
    # production** and wiring one into the weekly sweep would re-derive a fact about unchanged
    # source code for every org on every tick.
    "target_policy.undeclared_units": (
        "⛔ A BUILD-TIME PROPERTY GUARD. *'Units the registry runs that this module does not "
        "declare.'* Direction one of two: `ALL_ANALYSIS_UNITS` is the source of truth and a new "
        "unit that picks a sink without declaring it fails the build. One test caller, which is "
        "the correct and only one.",
        "MOVES WHEN a surface shows an operator which unit writes which sink. ⛔ Never into the "
        "sweep: the answer is a property of the checked-in source, identical on every run"),

    "target_policy.missing_units": (
        "⛔ THE SECOND DIRECTION, and the one that caught my own resolver. *'Declared entries "
        "naming a unit the registry no longer runs.'* `ALL_ANALYSIS_UNITS` is an `ast.AnnAssign`, "
        "not an `ast.Assign`; the first version of `registered_units` matched only `Assign`, "
        "returned an empty tuple, and THIS function reported all eleven declarations as stale. "
        "⛔ **A totality guard that runs one way is half a guard** — and the half I nearly skipped "
        "is the half that found the bug.",
        "MOVES WITH `undeclared_units` — the two check one mapping from opposite sides and neither "
        "is wanted at runtime"),

    "target_policy.drifted_units": (
        "⛔ THE CHECK WITH TEETH, and the reason the module exists. *'(unit, declared, measured) "
        "wherever the declaration no longer matches the code.'* A unit's `LearningTarget` decides "
        "its SINK — `METRICS` is published as a measurement, `RUNTIME` becomes an expiring lease, "
        "and a brain target becomes a durable versioned row with no expiry column at all — so a "
        "one-word edit to a target changes whether a proposal expires, waits for a human, or "
        "becomes permanent. Nothing asserted that mapping before this.",
        "MOVES WHEN the mapping is enforced at construction rather than checked after the fact — "
        "⛔ which would need `LearningObject` to know which unit built it, and it deliberately "
        "does not"),

    "target_policy.durable_from_a_measurement": (
        "⛔⛔ THE DECLARED VIOLATION'S DERIVATION. *'Units whose declared target is a durable "
        "brain while their siblings call it a metric.'* It returns exactly "
        "`unit_recommendation_learning`, and the test asserts that SET equals "
        "`DURABLE_FROM_A_MEASUREMENT` in both directions. ⛔ Four units of the same shape "
        "(`feedback_learning`, `outcome_analysis`, `actor_outcome_analysis`, "
        "`performance_optimization`) target `METRICS`; this one emits `efficacy_bp` into "
        "`ADAPTIVE`, which `govern` auto-promotes and the pack compiler reads back into the "
        "package the recommender reasons from — the Atlas boundary *'No self-training from "
        "recommendation score'*.",
        "⛔ MOVES WHEN Rohit ratifies one of the three repairs in "
        "`speedrun008/YCW27/layer-6-learning/07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md` "
        "§2 — add TTL/decay to ADAPTIVE, prohibit durable ADAPTIVE publication, or retarget this "
        "unit to METRICS. All three change what the Adaptive brain CONTAINS, so none is mine"),

    # ───────────────────────────────────────── the delegation guards, S4 (3)
    # ⛔ THE SAME FILING AS THE FOUR ABOVE: build-time property guards over the checked-in AST,
    # identical on every run. They answer *"is the producer that does this unit's job still
    # wired?"* — a question about source code, not about a tenant.
    "target_policy.undelegated_silent_units": (
        "⛔ A BUILD-TIME PROPERTY GUARD. *'Units that propose nothing, name a target, and explain "
        "it nowhere.'* A unit in `ALL_ANALYSIS_UNITS` that returns nothing must be either a "
        "declared stub (`None` in `UNIT_TARGETS`) or a declared placeholder (an entry in "
        "`DELEGATED`). ⛔ Anything else is the state that made the GeniOS Atlas record Layer 7 gap "
        "#2 as *'direct personalization evolution is missing'* when both components were built one "
        "package down — and that made THIS programme repeat the same verdict on 2026-10-02.",
        "MOVES WHEN a surface shows an operator which Layer 7 components produce and which "
        "delegate. ⛔ Never into the weekly sweep: the answer is a property of the checked-in "
        "source and cannot differ between two runs of the same build"),

    "target_policy.stale_delegations": (
        "⛔ THE SECOND DIRECTION. *'A delegation naming a unit that is no longer silent, or "
        "gone.'* If `_cohort_candidate` ever gains a body these units start proposing, and there "
        "would be TWO producers for one brain subject — the shape "
        "`reason/situation_reasoner.clamp_confidence` was filed under in L5, where *two "
        "implementations of a one-way law is the shape that lets one of them start raising*. "
        "⛔ A totality guard that runs one way is half a guard.",
        "MOVES WITH `undelegated_silent_units` — the two check one declaration from opposite "
        "sides and neither is wanted at runtime"),

    "target_policy.broken_delegations": (
        "⛔⛔ THE GUARD WITH TEETH, and the reason `S4` is a declaration rather than a build. It "
        "asserts FIVE links: the producer file and function exist, the producer is not itself a "
        "`return []`, `brain_pipeline.brain_pipeline_proposals` calls it, "
        "`orchestrator.run_learning` calls that driver, and ⛔ **the producer still emits the "
        "TARGET the table declares** — the sink, and therefore whether a proposal expires, waits "
        "for a human, or becomes permanent. Losing any one link silently returns the layer to the "
        "state the Atlas recorded: a registry that lists the component and a product that "
        "produces nothing. ⛔ It also closes a blind spot in `S1`'s guard, which read "
        "`UNIT_TARGETS` only and so could not see a producer in another package.",
        "⛔ MOVES WHEN a producer is reached by something other than `brain_pipeline_proposals` — "
        "then `DRIVER_ENTRY` / `DRIVER_HOP` stop describing the chain and the guard must be "
        "re-pointed rather than relaxed"),

    "calibrate.muted_rules": (
        "⛔ NO DOCSTRING, NO TEST, NO CALLER — and that is the entry. The only one of `feedback/`'s "
        "five with nothing anywhere. ⛔ **Why it is unreached is recorded nowhere in the codebase**, "
        "so declaring it deliberate would invent a reason and declaring it a defect would invent a "
        "severity. `calibrate` DOES mute rules on a live path; what is unreached is this read of "
        "which ones are muted.",
        "⛔ MOVES WHEN somebody who knows whether a muted-rule list is wanted writes one line above "
        "it. The auto-mute loop is live, so a reader for its output is plausible and nobody has "
        "asked for one"),
}


def _sources() -> dict[str, str]:
    return engine_sources(_ENGINE)


def feedback_functions() -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in `feedback/`."""
    return package_functions(_PKG)


def feedback_undeclared() -> tuple[str, ...]:
    """Unreached public functions in `feedback/` that this module does not declare."""
    return undeclared(_PKG, _sources(), frozenset(UNREACHED))


def feedback_missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction."""
    return missing(_PKG, frozenset(UNREACHED))


def feedback_now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie."""
    return now_called(_sources(), frozenset(UNREACHED))


__all__ = ["UNREACHED", "feedback_functions", "feedback_missing", "feedback_now_called", "feedback_undeclared"]
