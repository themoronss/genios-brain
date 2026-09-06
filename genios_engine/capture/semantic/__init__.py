"""L1.4 · the semantic extraction engine — where cleaned text becomes typed meaning.

Group law, from doc 04: *the model DESCRIBES. It never SCORES, never ROUTES, never DECIDES
VISIBILITY.* This is the one package in Layer 1 that is allowed to call a model at all, and
the permission is narrow: LLM-2, the extractor, one site. Everything else in here — the
profile registry, the closed vocabularies, the schema generator, the open lane, the evidence
binder, the injection guard, the batch planner and the cost governor — exists so that the single
call is cheap, safe, replayable, affordable and pinned to a shape.

Scores stay integer basis points throughout, and the model is never asked for one. A model
that can emit a priority is a model whose mood ranks a founder's morning.
"""
