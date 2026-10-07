r"""What `contracts/` deliberately does not call — the shared vocabulary's declared silence.

⛔ SIX OF THE EIGHT ARE BOTH-DIRECTIONS GUARDS AND PROJECTIONS — the shapes a vocabulary package
produces. `contracts/` may depend on `platform` and stdlib only, so this module importing
`platform/reachability.py` is the one import it is allowed to make.

⛔ AND ONE IS A GUARANTEE KEPT BY DISCIPLINE RATHER THAN BY CONSTRUCTION — `build_address`, which
exists *"so no producer can forget"* a token and is bypassed by all three producers.

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


#: ⛔ Public functions in `contracts/` with no production caller — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by `tests/contracts/test_the_contracts_layer_says_what_it_does_not_call.py`: an entry naming a function that
#: is now called is as much a lie as a function that is unreached and undeclared.
UNREACHED: dict[str, tuple[str, str]] = {
    "brain_address.build_address": (
        "⛔ A GUARANTEE THAT IS KEPT BY DISCIPLINE RATHER THAN BY CONSTRUCTION. *'`BrainAddress` "
        "with the tenant token always present, **so no producer can forget it**.'* Measured: zero "
        "callers, and all three producers build `BrainAddress(...)` directly — "
        "`packs/brains/org_discovery.py:505`, `adaptive_lease.py:231`, `behavior_distill.py:624`. "
        "⛔ They each pass `tokens=org_scope(...)`, so the token IS present today; what is absent is "
        "the construction that would make forgetting it impossible. **The helper's whole reason for "
        "existing is bypassed by everything it was written for**, which is milder than a defect and "
        "sharper than a tidy-up.",
        "MOVES WHEN the three producers are routed through it, which is a small change nobody has "
        "asked for — ⛔ or when a fourth producer forgets the token, which is the event it was "
        "written to prevent and the only one that will make it urgent"),

    "outcomes.disagreements": (
        "*'The outcomes the layers imply that the resolution DISCARDED, in rank order.'* Five test "
        "callers. ⛔ `contracts/outcomes.resolve` IS live — `outbox.py` calls it at the drain seam, "
        "*'counted, not acted on'* — and this is the view of what that resolution threw away. A "
        "report about a decision rather than part of making it.",
        "MOVES WHEN an operator surface asks *why was this outcome chosen over the others*. The "
        "resolution already records its own answer; this records the alternatives"),

    "outcomes.unreachable": (
        "*'Outcomes no vocabulary in the projection can produce at all.'* Two test callers. ⛔ A "
        "TOTALITY check over a closed set — the same shape as `deliver/lane_recall."
        "every_lane_is_visible_or_deliberately_silent`, which L5 filed as a build-time guard after "
        "first mis-filing it as a defect. It answers a question about vocabularies, not about data.",
        "MOVES WHEN it is deleted or the projection gains a vocabulary and it is rewritten. ⛔ Not "
        "by being wired: an unreachable outcome is a fact about code, settled at build time"),

    "situation_stages.undeclared_situation_types": (
        "⛔ *'The other direction. Every `Situation*`-shaped contract class with no row.'* — the "
        "second half of a both-directions guard, and this package's own statement of the rule the "
        "whole programme runs on: **declared and written are two directions, and one alone is half "
        "a guard.** Three test callers.",
        "MOVES WITH `situation_stages.resolve`, which is the first direction. ⛔ Shipping one "
        "without the other is exactly the half-guard this function exists to refuse"),

    "situation_stages.resolve": (
        "*'The class a declared row points at, or None if the row has rotted.'* One test caller. "
        "The first direction of the pair above: a declared row whose class has gone. ⛔ Its name is "
        "also one of the most collision-prone in the engine — `resolve` had **48** apparent callers "
        "under the name-only resolver and has one real one.",
        "MOVES WITH `undeclared_situation_types` — see that entry"),

    "learned_state.snapshot": (
        "*'Read the learned state a `consumer` may use for `subject`. **Fail-closed on every "
        "axis**.'* Four test callers. ⛔ The fail-closed reading of a learned state, and nothing in "
        "the engine consumes a learned state through it. "
        "⛔ CORRECTED 2026-10-02 — THIS ENTRY INVENTED A FINDING AND ATTRIBUTED IT TO ANOTHER "
        "LAYER. It said that was *'consistent with L6's own finding that the learning loop "
        "writes more than anything reads'*. **L6's documents contain no such finding.** I put "
        "a measurement I had not taken into another layer's mouth, in a declaration module, "
        "which is the exact defect this programme keeps paying for. "
        "⛔ MEASURED PROPERLY ON 2026-10-02: `feedback/` writes **16** tables and **four are "
        "read by nothing anywhere in the engine or in scripts** — `learning_input_rejections`, "
        "`learning_metrics`, `learning_object_evaluations`, `learning_transitions`. The "
        "direction was right and the attribution was invented, and **a measurement I took is "
        "not a finding somebody else recorded.**",
        "MOVES WHEN a consumer reads learned state on a live path. ⛔ Until then its fail-closed "
        "default is the correct behaviour of a function nobody calls: it cannot leak what it never "
        "serves"),

    "claim_state.fields_in": (
        "⛔ NO DOCSTRING, but three test callers — so unlike the genuinely undocumented ones, "
        "somebody's tests record what they expect of it. `contracts/claim_state` IS live: its "
        "`ClaimState` enum and `_MODEL_MAY_WRITE` table are read by `deliver/claims.py`. This is a "
        "projection over a payload's fields that nothing in the engine asks for.",
        "⛔ MOVES WHEN one line is written above it saying what it is for, OR when a caller appears. "
        "Three tests are evidence of intent and not a substitute for it"),

    "learned_state.may_consume": (
        "⛔ NO DOCSTRING, NO TEST, NO CALLER — the only one of `contracts/`'s eight with nothing "
        "anywhere, and it sits beside `snapshot`, which has four tests. ⛔ **Why it is unreached is "
        "recorded nowhere**, so declaring it deliberate would invent a reason and declaring it a "
        "defect would invent a severity. Its NAME suggests the permission check `snapshot`'s "
        "*'fail-closed on every axis'* refers to, which would make it load-bearing the moment a "
        "consumer appears — but that is a reading of a name, not a measurement.",
        "⛔ MOVES WHEN somebody who knows whether `snapshot` is supposed to consult it writes one "
        "line above it. Flagged in `HANDOFF-CODING-AGENT.md` rather than guessed at here"),

    "measured.median_of": (
        "STEP-10's contract (`yc2_w27_s10 · M29.C1.L-contract.V0.U01`), frozen BEFORE its callers so "
        "four worktrees could build against one shape: the median of what was observed WITH its n, "
        "so no reader can call a number resting on one reply a habit. Unreached between the commit "
        "that froze it and the first unit that measures through it — a declared gap of one commit.",
        "MOVES WHEN `context/waiting.py` measures your reply time through it "
        "(`M29.C1.L-logic.V2.U03`, the next unit on this branch)"),

    "measured.rate_of": (
        "STEP-10's contract, frozen before its callers: `hits` of `total` as a ratio resting on "
        "`total` observations — the connector's rate (introductions made, people who replied, calls "
        "booked) is its first caller, built in a parallel worktree against this frozen shape.",
        "MOVES WHEN the connector's rate (`yc2_w27_s10 · M29.C4.L-logic.V0.U02`, "
        "`context/workstreams.py`) lands on this branch"),
}


def _sources() -> dict[str, str]:
    return engine_sources(_ENGINE)


def contract_functions() -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in `contracts/`."""
    return package_functions(_PKG)


def contract_undeclared() -> tuple[str, ...]:
    """Unreached public functions in `contracts/` that this module does not declare."""
    return undeclared(_PKG, _sources(), frozenset(UNREACHED))


def contract_missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction."""
    return missing(_PKG, frozenset(UNREACHED))


def contract_now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie."""
    return now_called(_sources(), frozenset(UNREACHED))


__all__ = ["UNREACHED", "contract_functions", "contract_missing", "contract_now_called", "contract_undeclared"]
