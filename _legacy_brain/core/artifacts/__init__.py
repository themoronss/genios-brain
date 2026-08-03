"""g-i-6 Artifacts — RENDER what the engine concluded. Never adds reasoning or facts.

Per MD g-i-6 §0 (the law):
- The LLM here is a TRANSLATOR (proof-tree -> plain language), NOT a thinker.
- If an artifact contains a claim NOT in the derivation chain or source facts -> REJECTED.
- Every artifact is 100% grounded or it does not ship.

Pipeline:
    Decision (from g-i-2)
      -> Trace (sourceFacts + rulesFired + graphPath + confidence + uncertainty + asOf)
      -> Narrator (LLM translates chain -> prose, grounded-or-regenerate-or-reject)
      -> Builder (Jinja2 template combines trace + narrative + counterfactuals + uncertainty)
      -> Artifact persisted (audit-ready, asOf-reproducible)

Public API:
    from core.artifacts import (
        Trace, build_trace,
        UncertaintyFlag, UncertaintyKind, collect_uncertainty,
        verify_grounding_of_claims, GroundingVerification,
        narrate, NarratorResult, NarratorRejected,
        build_artifact, Artifact, ArtifactKind,
        render_graph_view, GraphView,
    )
"""

from core.artifacts.builder import Artifact, ArtifactKind, build_artifact
from core.artifacts.graph_view import GraphView, render_graph_view
from core.artifacts.grounding import GroundingVerification, verify_grounding_of_claims
from core.artifacts.narrator import NarratorRejected, NarratorResult, narrate
from core.artifacts.trace import Trace, build_trace
from core.artifacts.uncertainty import UncertaintyFlag, UncertaintyKind, collect_uncertainty

__all__ = [
    "Artifact",
    "ArtifactKind",
    "GraphView",
    "GroundingVerification",
    "NarratorRejected",
    "NarratorResult",
    "Trace",
    "UncertaintyFlag",
    "UncertaintyKind",
    "build_artifact",
    "build_trace",
    "collect_uncertainty",
    "narrate",
    "render_graph_view",
    "verify_grounding_of_claims",
]
