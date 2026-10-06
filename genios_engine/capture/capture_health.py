r"""What `capture/` deliberately does not call — L1's declared silence.

⛔ WHY THIS EXISTS. Four packages state their own silences in code: `executive/unreached.py`,
`deliver/delivery_health.py`, `reason/unit_health.py` and `context/lane_health.DORMANT_LANES`. The
other seven never had the question asked. Measured 2026-10-01 across every package with the
corrected resolver: **123 top-level public functions are unreached by production and declared
nowhere** — and `capture/` holds **7** of them.

⛔ ONE TABLE, NOT THREE, AND THE SHAPE IS A FINDING. `deliver/` needed three — an un-cut-over
architecture, deliberate silences, and defects — because it carries a second delivery control plane.
`capture/`'s seven are all one kind: **tooling and reports whose reader is a person or a test.**
There is no un-cut-over tier here and no defect. **A package gets the tables its triage needs**, and
inventing `KNOWN_UNWIRED` here to match `deliver/` would mean an empty table asserting nothing.

⛔ AND SIX OF THE SEVEN ARE EXERCISED BY TESTS. That is not an excuse for them; it is the
distinction that makes the seventh worth reading twice. `source_registry.is_buildable` has **no
docstring, no test and no caller** — nothing anywhere records what it is for.

The machinery is `platform/reachability.py`, shared rather than copied: `capture/` is PRODUCT layer
1 and `executive/` is 5, so importing the original would be an UPWARD import that
`tests/test_layer_topology.py` fails the build over.
"""
from __future__ import annotations

from pathlib import Path

from genios_engine.platform.reachability import (engine_sources, missing, now_called,
                                                 package_functions, undeclared)

_PKG = Path(__file__).resolve().parent
_ENGINE = _PKG.parent


#: ⛔ Public functions in `capture/` with no production caller — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by
#: `tests/capture/test_the_capture_layer_says_what_it_does_not_call.py`: an entry naming a function
#: that is now called is as much a lie as a function that is unreached and undeclared. One direction
#: alone is how `mcp/` escaped the import ratchet in L3-01.
UNREACHED: dict[str, tuple[str, str]] = {
    "attention.attention_for": (
        "⛔ BUILT BOTTOM-UP, NOT YET WIRED (STEP-03, the gate keeps everything, `yc2_w27_s03/M21.C1.L-contract.V0.U03`). The one place a gate verdict becomes an attention tier — archive with the rule that archived it, deep with what let it through or the park that holds it. Its caller is the capture pipeline, a later unit of the same block",
        "⛔ MOVES WHEN `yc2_w27_s03/M21.C3.L-logic.V3.U03` makes `capture/pipeline.py` write the tier it returns — then this entry must be deleted, or the stale-declaration guard fails"),

    # ── the benchmark harness · 15 test callers between them ─────────────────────────────────
    "benchmark.score_benchmark": (
        "⛔ A HARNESS, AND ITS CALLER IS A PERSON ASKING HOW GOOD THIS LAYER IS. *'Score every "
        "object against the shipping code. No corpus, no database, no network.'* Eight test "
        "callers. It is not a step in the capture pipeline and never was: the pipeline produces "
        "signals, and this scores them against an audit so somebody can say whether a change "
        "helped. A build-time measurement of the layer, not a part of it.",
        "MOVES WHEN a benchmark number is wanted on a schedule rather than on demand. ⛔ Until then "
        "its absence from the pipeline is the correct state, not a gap — wiring it would score "
        "every object on every sweep to answer a question nobody asked that tick"),

    "benchmark.calibrate": (
        "⛔ THE HARNESS JUDGING ITSELF. T1 — *'if it does not reproduce the audit, the harness is "
        "wrong, not the layer'* — and its own docstring then records why a bare equality check "
        "would be wrong now: *'that instruction was written before steps 1-10 ran, so the target "
        "has legitimately moved and a bare equality check would now fail for the right reason and "
        "the wrong one at once.'* Four test callers. ⛔ A function whose job is to decide whether a "
        "MEASUREMENT may be trusted cannot sensibly run inside the thing it measures.",
        "MOVES WITH `score_benchmark` — see that entry. The two are one tool and neither is wanted "
        "on a tick"),

    "benchmark.behavioural_score_is_quotable": (
        "⛔ A GUARD ON A NUMBER'S ADMISSIBILITY, WHICH IS A QUESTION ABOUT EVIDENCE RATHER THAN "
        "ABOUT PRODUCTION. *'May a BEHAVIOURAL benchmark number be quoted? Two guards, and both "
        "must pass'* — E3, *'a passing harness on 8 messages means nothing'*, and E4, *'N=1 mailbox "
        "with unusually low outbound flatters sent-side prompts.'* Three test callers. It answers "
        "*may I say this in a document*, so its caller is whoever is writing the document.",
        "MOVES WHEN a surface quotes a behavioural benchmark to a customer, at which point the "
        "admissibility check belongs in front of it. ⛔ Nobody has asked for that surface"),

    # ── the degraded-reader report · built, tested, and nothing renders it ───────────────────
    "intent_rate.unknown_rate_bp": (
        "⛔ A REPORT WITH NO RENDERER — and its sibling's docstring names the reader it does not "
        "have. *'{source: unreadable share in basis points}, over readings grouped by source'*, "
        "with a deliberate strictness: *'anything without an `observed_anything` property is "
        "counted as UNREADABLE rather than skipped: a reading that is not a reading is the "
        "strongest'* evidence of a broken reader. Four test callers, no production caller. So the "
        "number is correct, computable, and asked for by nothing.",
        "MOVES WHEN a connector-health surface exists. ⛔ It is the natural reader and it does not "
        "exist; L1 receipts answer *is the source producing* and not *is its READER working*"),

    "intent_rate.degraded_sources": (
        "⛔ AND THIS ONE STATES ITS READER OUTRIGHT: *'the sources whose reader is not working, "
        "sorted worst first. Sorted rather than merely filtered, because the useful question a "
        "person asks of this report is \"which connector do I look at\" and not \"is anything "
        "wrong\".'* A function shaped around a human's question, reached by one test. ⛔ **A "
        "function that names the person who would read it, and has no caller, is a surface that "
        "was never built** — not a helper somebody forgot.",
        "MOVES WITH `unknown_rate_bp`, into the same surface or neither. ⛔ Splitting them would "
        "ship the filter without the ordering that makes it useful"),

    # ── the registry's two reads ────────────────────────────────────────────────────────────
    "source_registry.known_ids": (
        "*'Every accepted source id, canonical and alias.'* Two test callers. The registry's "
        "WRITERS and its lookup are on live paths; this is the full enumeration, which the engine "
        "never needs because every production question is *is THIS id known* rather than *list "
        "them all*. The tests need the enumeration to prove the lookup agrees with it.",
        "MOVES WHEN a surface lists the supported sources — an onboarding screen is the obvious "
        "caller. Until then the enumeration exists to be checked against, which is a real job"),

    "source_registry.is_buildable": (
        "⛔ NO DOCSTRING, NO TEST, NO CALLER — AND THAT IS THE ENTRY. The only one of `capture/`'s "
        "seven with nothing anywhere: six are exercised by tests and this is reached by nothing at "
        "all. ⛔ **Why it is unreached is recorded nowhere in the codebase**, so declaring it "
        "deliberate would invent a reason and declaring it a defect would invent a severity. What "
        "is true is that nobody wrote down what it is for, and that is what this says.",
        "⛔ MOVES WHEN somebody who knows what 'buildable' means for a source writes one line above "
        "it. Flagged in `HANDOFF-HARSH.md` rather than guessed at here — the registry is a "
        "connector concern and Harsh owns the connectors"),
}


def _sources() -> dict[str, str]:
    return engine_sources(_ENGINE)


def capture_functions() -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in `capture/`."""
    return package_functions(_PKG)


def capture_undeclared() -> tuple[str, ...]:
    """Unreached public functions in `capture/` that this module does not declare."""
    return undeclared(_PKG, _sources(), frozenset(UNREACHED))


def capture_missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction."""
    return missing(_PKG, frozenset(UNREACHED))


def capture_now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie."""
    return now_called(_sources(), frozenset(UNREACHED))


__all__ = ["UNREACHED", "capture_functions", "capture_missing", "capture_now_called",
           "capture_undeclared"]
