r"""`R.U04` · ALARM A6, retired — an absent `source_reasoner` is a branch, not a fault.

⛔ WHAT THE ALARM CLAIMED. `priority.py` carried a comment, and `STATUS.md` carried it as **ALARM
A6** queued as *"mine, on request"*:

> *"The read is `or ""`, so a manifest that FORGETS `source_reasoner` yields an empty source string
> rather than a refusal — the unit then reads a prior metric from `""`, gets the sentinel, and is
> silent. Safe today because every manifest sets it. Changing `or ""` to a refusal changes
> behaviour and is its own unit."*

⛔ MEASURED 2026-10-01, ALL THREE CLAIMS ARE WRONG.

1. *"every manifest sets it"* — `sales.deal_cooling`, the only built-in capability, schedules
   `core.confidence` with the key **absent**. `core.priority` sets it to `core.temporal`.
2. *"reads a prior metric from `\"\"`"* — it does not. Both units guard first:
   `if not source: return None`, before any lookup.
3. ⛔ *"change `or \"\"` to a refusal"* — **that fix would have been the defect.** Falsy is the
   BRANCH SELECTOR. `_source_reasoner`'s docstring: *"Falsy config (absent, empty, None) means 'no
   source declared' and routes to the derived path."* `confidence.py:27`: *"Two branches, one
   output… The bridge is not a fallback; it is a declaration by the capability author."*

So the alarm asked for a change that would break the designed path of every capability that
legitimately declares no source. **This file exists so the retired claim cannot be acted on later** —
a comment that describes a defect reads as a measurement somebody already took, which is how a whole
unit got specified on a stale comment earlier in this programme.

⛔ WHAT IS GENUINELY TRUE, AND IS NOT A FAULT TODAY. A key deliberately omitted and a key forgotten
are indistinguishable. It costs nothing because **neither unit requires a source** — both have a
designed derived path — so a forgotten key always lands somewhere real. It would begin to cost
something the day a unit is written that cannot work without one, and that unit should declare the
requirement; the shared accessor should not refuse on its behalf.
"""
from __future__ import annotations

import inspect

from genios_engine.packs.capabilities import BUILTIN_CAPABILITIES
from genios_engine.reason.reasoners import confidence as C
from genios_engine.reason.reasoners import priority as P


def _specs(reasoner_id: str):
    return [spec
            for cap in BUILTIN_CAPABILITIES
            for spec in getattr(cap, "reasoners", ())
            if getattr(spec, "reasoner_id", None) == reasoner_id]


# --------------------------------------------------------------------------------------------
# claim 1 — "every manifest sets it"
# --------------------------------------------------------------------------------------------

def test_a_shipped_manifest_deliberately_omits_the_key() -> None:
    """⛔ The measurement that retired the alarm's justification."""
    specs = _specs("core.confidence")
    assert specs, "core.confidence must be scheduled by a built-in for this to mean anything"
    assert all("source_reasoner" not in dict(getattr(s, "config", {}) or {}) for s in specs), (
        "core.confidence is shipped WITHOUT source_reasoner; if that changes, the alarm's "
        "justification changes with it and this test should be re-read, not deleted")


def test_the_other_unit_does_declare_one() -> None:
    """Both branches are exercised by the one shipped capability, which is why the design works."""
    specs = _specs("core.priority")
    assert specs
    assert all(dict(getattr(s, "config", {}) or {}).get("source_reasoner") == "core.temporal"
               for s in specs)


# --------------------------------------------------------------------------------------------
# claim 2 — "reads a prior metric from the empty string"
# --------------------------------------------------------------------------------------------

def _guards_before_lookup(func) -> bool:
    """The guard must precede every `view.prior` read in the function body.

    ⛔ AN AST-FREE STRUCTURAL READ ON PURPOSE, AND NARROWED TO ONE FUNCTION. A whole-file grep for
    `view.prior` matches docstrings that discuss it — including this module's. Source of one
    function, docstring stripped by `inspect.getdoc` comparison, is the smallest thing that answers
    the question.
    """
    src = inspect.getsource(func)
    doc = inspect.getdoc(func) or ""
    body = src.split('"""')[-1] if doc else src
    guard = body.find("if not source")
    read = body.find("view.prior")
    return guard != -1 and (read == -1 or guard < read)


def test_neither_unit_ever_looks_up_the_empty_string() -> None:
    assert _guards_before_lookup(P._declared_source), (
        "priority._declared_source must return before reading view.prior")
    assert _guards_before_lookup(C._bridged_confidence_bp), (
        "confidence._bridged_confidence_bp must return before reading view.prior")


def test_the_accessor_treats_every_falsy_shape_the_same() -> None:
    """absent, empty, None — one branch, so the two urgency plugins cannot disagree about which
    branch they are in."""
    class _View:
        def __init__(self, cfg): self.config = cfg
    for cfg in ({}, {"source_reasoner": ""}, {"source_reasoner": None}):
        assert P._source_reasoner(_View(cfg)) == ""        # type: ignore[arg-type]
    assert P._source_reasoner(_View({"source_reasoner": "core.temporal"})) == "core.temporal"  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------------
# claim 3 — the proposed fix would have been the defect
# --------------------------------------------------------------------------------------------

def test_the_falsy_branch_is_documented_as_a_branch_not_a_fallback() -> None:
    """⛔ If someone later 'fixes' `or \"\"` into a refusal, this is the test that should stop them.

    It asserts on the accessor's own contract, which is the thing the change would violate: a falsy
    config must yield the derived branch rather than raising.
    """
    class _View:
        config: dict = {}
    assert P._source_reasoner(_View()) == "", (
        "a manifest that declares no source must route to the derived path, NOT refuse -- "
        "ALARM A6 asked for the refusal and ALARM A6 was wrong; see this module's docstring")
    assert P._declared_source(_View()) is None            # type: ignore[arg-type]


def test_the_retraction_is_recorded_where_the_claim_was() -> None:
    """A retired claim deleted silently is a claim that comes back. It is retracted in place."""
    src = inspect.getsource(P)
    assert "RETIRED 2026-10-01" in src
    assert "that fix would be a defect" in src.lower()
