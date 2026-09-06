"""L2.6 · the declarative pattern registry — where a graph pattern becomes a candidate reality.

Anchor-based detection asks *"what is this about?"*. A pattern asks *"do these five things hold
together right now?"*, and only the second produces a situation worth interrupting somebody for.

    contract.py   the schema — a pattern is DATA, validated at parse time
    slice.py      what one anchor's evaluation may see, injected, frozen
    matcher.py    the pure evaluator and the per-condition evidence
    candidate.py  a match, assembled — carried, never re-derived
    scorer.py     match strength and quality, kept apart; promote or hold
    registry.py   registration-time refusal, and the two fire-rate guards
    seed/         the six shipped patterns, as files

THE REGISTRY RUNS BESIDE ANCHOR-BASED DETECTION, NOT INSTEAD OF IT. Doc 06 is explicit: *"keep
anchor-based detection running alongside. Compare fire sets on a pilot for 7 days before
switching. Do not delete the anchor path in this wave."* Nothing in this package writes
`context_situations`, and `context/situations.py` is untouched, so no existing behaviour changes.
The migration path is stated in `store.py`.
"""
from __future__ import annotations

from genios_engine.context.patterns.candidate import SituationCandidate, build_candidate
from genios_engine.context.patterns.contract import Pattern, PatternError
from genios_engine.context.patterns.matcher import (ConditionEvidence, ConditionFailure,
                                                    MatchResult, evaluate, match)
from genios_engine.context.patterns.registry import (FireObservation, PatternRegistry,
                                                     RegistrationError, activation_decision,
                                                     seed_registry)
from genios_engine.context.patterns.scorer import CandidateScore, score_candidate
from genios_engine.context.patterns.slice import GraphSlice

__all__ = ["CandidateScore", "ConditionEvidence", "ConditionFailure", "FireObservation",
           "GraphSlice", "MatchResult", "Pattern", "PatternError", "PatternRegistry",
           "RegistrationError", "SituationCandidate", "activation_decision", "build_candidate",
           "evaluate", "match", "score_candidate", "seed_registry"]
