r"""What `packs/` deliberately does not call — L2's corpus plane's declared silence.

⛔ ALL THREE ARE ONE REPORT. `substrate_demand` measures what the corpus DEMANDS against what
it declares, and nothing in the pipeline consumes that measurement — the same shape as
`capture/intent_rate`. One table, because one kind: **a corpus report whose reader is a person.**

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


#: ⛔ Public functions in `packs/` with no production caller — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by `tests/packs/test_the_packs_layer_says_what_it_does_not_call.py`: an entry naming a function that
#: is now called is as much a lie as a function that is unreached and undeclared.
UNREACHED: dict[str, tuple[str, str]] = {
    "substrate_demand.measure": (
        "⛔ THE REPORT ITSELF, AND IT MEASURES THE CORPUS RATHER THAN RUNNING IT. *'Split `declared` "
        "by whether the corpus names each field.'* Four test callers, no production caller. A pack "
        "compile does not need to know which demanded fields the corpus is missing; a person "
        "deciding what to author next does.",
        "MOVES WHEN a corpus-coverage surface exists, or when a pack compile is made to FAIL on an "
        "undemanded field rather than report it. ⛔ The second would be a product decision about "
        "whether an incomplete corpus may ship"),

    "substrate_demand.field_paths": (
        "*'The `substrate.fact_paths` list, in declaration order.'* Five test callers — the most "
        "exercised of the three, because the ORDER is the thing tests pin: a report that reordered "
        "its rows between runs could not be diffed.",
        "MOVES WITH `measure` — it is that function's input and has no separate reader"),

    "substrate_demand.families": (
        "*'`{family: count}` — the second dotted segment, which is how the vocabulary groups "
        "them.'* One test caller. The grouping a human reads the report BY, which is why it exists "
        "separately from the flat list.",
        "MOVES WITH `measure`. ⛔ Shipping the grouping without the report would be a legend with "
        "no chart"),
}


def _sources() -> dict[str, str]:
    return engine_sources(_ENGINE)


def pack_functions() -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in `packs/`."""
    return package_functions(_PKG)


def pack_undeclared() -> tuple[str, ...]:
    """Unreached public functions in `packs/` that this module does not declare."""
    return undeclared(_PKG, _sources(), frozenset(UNREACHED))


def pack_missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction."""
    return missing(_PKG, frozenset(UNREACHED))


def pack_now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie."""
    return now_called(_sources(), frozenset(UNREACHED))


__all__ = ["UNREACHED", "pack_functions", "pack_missing", "pack_now_called", "pack_undeclared"]
