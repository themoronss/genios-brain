"""Shared schemas between layers — the testable seams.

The package deliberately re-exports nothing. Every module here is imported by its own path, so
the import graph says which seam a caller actually depends on and `tests/test_layer_topology.py`
can read that dependency out of the source. A convenience surface in this file would collapse
all of it into one edge and make every contract look like a dependency of every layer. What the
file carries instead is the map — the one place a reader learns which module owns which seam.

source_event  · L1 → landing (immutable normalized envelope)
trace         · per-event, per-stage visibility (the debug core)
parked        · park ≠ delete — a reviewable, recoverable refusal with its reason

The L1 chain, in the order one message travels it. Each module owns only what a value must be
true of once it exists; the algorithm that produces it lives in `capture/` (universal rule 5:
the validator runs at the seam that produced the object).

visibility    · who could see the ORIGINAL — carried forward so no insight outruns its evidence
evidence      · C-01 EvidenceSpan — the receipt a claim carries so it can be checked
units         · C-02 Money (integer minor units + ISO code), C-03 ResolvedDate (window + certainty)
extraction    · C-04..C-09 — the five claim types and the whole S2 result for one message
conflict      · C-10 — two sources disagree; both sides kept, no `winner`; `require_no_float`
signal        · C-11 SignalType and C-12 QualifiedEnterpriseSignal — L1's ONLY output
publication   · V-1..V-7 at L1.6.10 — the gate that emits, parks or rejects one of those signals
"""
