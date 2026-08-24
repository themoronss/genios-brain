"""Layer 4 deterministic reasoning.

Capabilities declare a bounded context, versioned micro-reasoner DAG, candidate plays, policies,
and outcome semantics.  The orchestrator is the only decision authority; language models may render
an explanation downstream but never select, rank, score, or execute a play.
"""
