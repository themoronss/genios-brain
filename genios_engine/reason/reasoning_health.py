r"""What `reason/` deliberately does not call — L2/L4's reasoning plane's declared silence.

⛔ `reason/` ALREADY DECLARES SILENCES — `unit_health.py` holds four grains of them, plus
`REASONING_ERAS` and `neutral_default_boundary()`. **This is a different question about the same
package**: not *which lane is quiet* but *which function nothing calls*, and `unit_health.py` is
excluded from this scan for the reason every declaration module is.

⛔ THE HIGHEST-VALUE ENTRY IS `situation_reasoner.clamp_confidence`: *"R-1'S LAW, VERBATIM: IT CANNOT
RAISE CONFIDENCE"*, seven test callers, and the live reasoner clamps **inline** instead. **Two
implementations of a one-way law is the shape that lets one of them start raising.**

⛔ AND THE CLEAREST DELETE CANDIDATE IN THE PROGRAMME IS HERE: `baselines.load_baselines` is a
*"back-compat"* shim with no callers, no tests and no script — **nothing is compatible with it any
more.**

The machinery is `platform/reachability.py`, shared rather than copied. ⛔ Three wiring mechanisms
are subtracted before anything reaches this table — a **call**, a **decorator**, a **reference**
(`Depends(f)`, a dispatch table, a registry) — and a fourth cannot be: **duck-typed dispatch**
(`store.purge_expired()` on a variable) is invisible to any static walk, so every entry below was
hand-checked against it. One function was rescued that way; sixteen candidates turned out to be name
collisions.
"""
from __future__ import annotations

from pathlib import Path

from genios_engine.platform.reachability import (engine_sources, missing, now_called,
                                                 package_functions, undeclared)

_PKG = Path(__file__).resolve().parent
_ENGINE = _PKG.parent


#: ⛔ Public functions in `reason/` with no production caller — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by `tests/reason/test_the_reasoning_layer_says_what_it_does_not_call.py`.
UNREACHED: dict[str, tuple[str, str]] = {
    "fingerprint.verdict_key": (
        "⛔ BUILT BOTTOM-UP, NOT YET WIRED (STEP-02, `yc2_w27_s02/M20.C1.L-contract.V0.U01`). How a human verdict enters a fingerprint — which feedback, at which version — so a verdict that lands re-decides its subject. Its caller is the inputs reader, the next unit of the same category",
        "⛔ MOVES WHEN `yc2_w27_s02/M20.C1.L-data.V1.U02` (`reason/fingerprint_inputs.py`) reads a tenant's verdicts through it — then this entry must be deleted"),

    "change_gate.should_skip": (
        "⛔ BUILT BOTTOM-UP, NOT YET WIRED (STEP-02, the change gate, `yc2_w27_s02/M20.C3.L-logic.V0.U01`). The one rule that decides whether a subject's decision may be skipped — same fingerprint, and for a live card an open signal with more than a day of authority left. Pure, and its callers are the lanes, which are later units of the same block",
        "MOVES WITH `fingerprint_store.load_all` — the same two units wire the store and the rule, in the same lanes"),

    "fingerprint_store.load_all": (
        "⛔ BUILT BOTTOM-UP, NOT YET WIRED (STEP-02, the change gate, `yc2_w27_s02/M20.C2.L-data.V1.U02`). The sweep's ONE read of a tenant's `reasoning_fingerprints` rows — what each subject's last decision was made on — for `change_gate.should_skip` to compare against. Its callers are the lanes, which are later units of the same block",
        "⛔ MOVES WHEN `yc2_w27_s02/M20.C3.L-integration.V2.U02` wires the compiled lane to the gate (and `M20.C4.L-integration.V3.U01` the legacy and native lanes) — then this entry must be deleted, or the stale-declaration guard fails"),

    "fingerprint_store.record_decided": (
        "⛔ BUILT BOTTOM-UP, NOT YET WIRED (STEP-02, `yc2_w27_s02/M20.C2.L-data.V1.U02`). The upsert after a run: the fingerprint the decision saw, the run, the outcome a later skip replays, the instant — and the skips zeroed. A lane calls it after every decision it pays for",
        "MOVES WITH `fingerprint_store.load_all` — the same two units wire both, in the same lanes"),

    "fingerprint_store.record_skipped": (
        "⛔ BUILT BOTTOM-UP, NOT YET WIRED (STEP-02, `yc2_w27_s02/M20.C2.L-data.V1.U02`). The skip receipt: `last_checked_at` and `skips + 1`, so a skipped subject still shows the sweep looked and a subject re-decided on an unchanged fingerprint is visible to `scripts/pipeline_health.py`",
        "MOVES WITH `fingerprint_store.load_all` — the same two units wire both, in the same lanes"),

    "baselines.load_baselines": (
        "⛔ *'Back-compat: just the reply_cadence baseline used by `{baseline}` threshold resolution'* — and NOTHING is compatible with it any more: no callers, no tests, not even a script. ⛔ **A back-compat shim is wanted only while something old still calls it**, and the thing it was kept for is gone. L4's `STEP-08` worked on `build_baselines` next door and did not need this",
        "⛔ MOVES WHEN it is deleted. It is the clearest delete candidate in this table, and it is left declared rather than removed because deleting a public function is a boundary change nobody asked for"),

    "baselines.load_node_metrics": (
        "*'One query for ALL of a node's baseline keys → (baselines, derived_facts).'* No callers and no tests. ⛔ The batched read beside the single one above, and the live path reads baselines through neither — so this is the faster shape of a read nothing performs here",
        "MOVES WITH `load_baselines`, or when a caller wants every baseline key at once. ⛔ One query instead of N is only worth wiring where the N exists"),

    "plan.plan_capability": (
        "⛔ SIXTEEN TEST CALLERS — the most exercised function in this table — and its docstring says exactly who it is for: *'Convenience entry point for tooling that wants a plan without holding a planner.'* So it is correctly uncalled by the engine: the engine HOLDS a planner, and this exists for everything that does not",
        "⛔ MOVES WHEN tooling stops wanting it, or when a surface plans a capability on demand. Never by being wired into the sweep — the sweep already has the planner this helper exists to avoid constructing"),

    "plan.describe_plans": (
        "⛔ NO DOCSTRING, NO TEST, NO CALLER — the only one in `reason/` with nothing anywhere, and it sits beside a function with sixteen test callers. ⛔ **Why it is unreached is recorded nowhere**; its name suggests the human-readable view of what `plan_capability` returns, which would make it the renderer for a tool that has no renderer — but that is a reading of a name",
        "⛔ MOVES WHEN somebody who knows what it should describe writes one line above it. Flagged in `HANDOFF-CODING-AGENT.md`"),

    "cutover.is_armed": (
        "⛔ *'Read the CODE, not the table. A flip that forgets to update `SWITCHES` fails the build'* — a both-directions guard over a cutover's own switch list. Three test callers, and they are the correct ones: it asks a question about source, so its answer cannot differ between two runs of the same build",
        "MOVES WHEN the cutover is taken and the switches are retired. ⛔ Never by being wired: it reads code, and code does not change on a tick"),

    "cutover.evaluate_parity": (
        "*'The gate, against one sweep's tallies. Pure — no clock, no I/O.'* Four test callers. ⛔ The parity gate for a cutover nobody has taken — the same situation `deliver/`'s tier 4 is in, and the reason both are declared rather than wired: **an uncalled function on an un-cut-over path is not a bug; it is an unguarded cutover**",
        "⛔ MOVES WHEN the cutover it gates is taken. `deliver/`'s equivalent carries a guard so the cutover cannot be taken without it; this one should gain the same when somebody arms it"),

    "situation_reasoner.clamp_confidence": (
        "⛔ *'R-1'S LAW, VERBATIM: IT CANNOT RAISE CONFIDENCE.'* Seven test callers. A one-way clamp stated as law and tested as law, and the live reasoner clamps inline. ⛔ **Two implementations of a one-way law is the shape that lets one of them start raising** — which is precisely what the law forbids",
        "⛔ MOVES WHEN the reasoner clamps through this function instead of inline. That is a small change with a real safety payoff, and it is the highest-value item in this table"),

    "actionability.undeclared_reason_codes": (
        "*'Rule reason codes no pack gives an actionability requirement — the drift this module'* exists to catch. One test caller. ⛔ A both-directions guard over pack declarations, answering a question about authored content rather than about a run",
        "MOVES WHEN pack compilation fails on an undeclared reason code rather than reporting it. ⛔ That is a product decision about whether an incomplete pack may ship"),

    "output_lane.reachable_lanes": (
        "*'Every lane `route` can actually return, computed by enumerating its inputs.'* One test caller. ⛔ A totality check over the router — the same shape as `deliver/lane_recall.every_lane_is_visible_or_deliberately_silent`, which L5 first mis-filed as a defect before measuring that it takes no production data",
        "MOVES WHEN it is deleted or the router gains a lane and it is rewritten. ⛔ Not by being wired: it enumerates code"),

    "narration.rejected_options": (
        "*'The elimination chain of one `ReasoningDecision`, in the shape R-3 narrates.'* Four test callers. ⛔ The narration of WHY the other candidates lost, built to a named spec and read by nothing — the card shows the winner",
        "MOVES WHEN a card or a brief shows the elimination chain. ⛔ R-3 describes the shape, so the spec exists and the surface does not"),

    "simulation.simulate": (
        "*'Run scenarios in stable order; never query or mutate the graph and never authorize del'*ivery. Three test callers. ⛔ Every one of those refusals is load-bearing — a simulation that could authorize a delivery would be a product action — and the stable order is what makes two runs comparable",
        "MOVES WHEN scenarios are run on a schedule or from a surface. ⛔ Its refusals make it safe to wire, which is the opposite of most entries here"),

    "replay.replay_execution": (
        "⛔ NO DOCSTRING, one test caller — and replay is one of this layer's load-bearing properties: `reason/replay.py` exists so a decision can be reproduced from its persisted snapshot. ⛔ The function that replays ONE execution has no production caller, and nothing records whether that is because replay is an operator action or because it was never finished",
        "⛔ MOVES WHEN an operator can replay an execution without a Python shell, or when one line above it says replay is deliberately manual. **Either answer is fine; the silence is not**"),

    "telemetry.aggregate": (
        "*'Roll several runs into per-unit worst observed cost, for capability tuning.'* One test caller. ⛔ Telemetry IS written per run; this is the roll-up that would make it tunable, and the tuning loop reads raw rows instead",
        "MOVES WHEN capability tuning reads the roll-up. ⛔ `feedback/calibrate` tunes from judgments rather than costs, so this is a second tuning input nobody has wanted yet"),

    "telemetry.slowest_first": (
        "⛔ NO DOCSTRING, one test caller. The ordering beside the roll-up above, and the name is the whole specification — which is why this is a thin entry rather than an unknown one",
        "MOVES WITH `aggregate` — ⛔ an ordering without the thing it orders is nothing"),

}


def _sources() -> dict[str, str]:
    return engine_sources(_ENGINE)


def reasoning_functions() -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in `reason/`."""
    return package_functions(_PKG)


def reasoning_undeclared() -> tuple[str, ...]:
    """Unreached public functions in `reason/` that this module does not declare."""
    return undeclared(_PKG, _sources(), frozenset(UNREACHED))


def reasoning_missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction."""
    return missing(_PKG, frozenset(UNREACHED))


def reasoning_now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie."""
    return now_called(_sources(), frozenset(UNREACHED))


__all__ = ["UNREACHED", "reasoning_functions", "reasoning_missing", "reasoning_now_called", "reasoning_undeclared"]
