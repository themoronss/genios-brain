"""Layer 5 — Executive Intelligence. Decision intelligence ONLY.

This layer answers: what is happening, why it matters, what should happen, how urgent,
on what evidence, and what happens if nothing is done. It NEVER answers who executes,
when to notify, which channel, or which tool — those are Layer 6 (deliver) questions,
and that boundary is the explicit architectural decision of the L5 spec.

Everything here is deterministic composition over already-stored truth (signals,
facts, suppressions, outcomes). No LLM writes a decision; when phrasing is added
later it goes behind executive.validate's invention validator.
"""
