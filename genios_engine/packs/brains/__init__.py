"""Layer 3 · the CONTENT pipelines for the three runtime brains.

The Expert Brain is Git (`Domain Expertise/`) and is full. Organization, Behavior and Adaptive
live in `learned_brain_entries` / `temporary_memories`, their machinery has existed since
migration 0045, and both tables are empty — because nothing produces proposals. This package is
the supply side.

**NOTHING HERE WRITES A BRAIN, AND NOTHING HERE CAN.** Every unit is a pure producer of
`LearningObject` proposals. The promotion pipeline that judges them is Layer 6, and the import
ratchet (`tests/test_layer_topology.py::test_import_direction`) makes that direction one-way on
purpose: a producer must not be able to call the governance that judges it. The drivers live on
the Layer 6 side — `feedback/brain_pipeline.py` (the evidence route: the weekly batch and the
immediate Adaptive lease) and `feedback/org_rule_ingest.py` (the declaration route: N-3's canon
documents) — and they reuse `governance.preflight`, `governance.govern`,
`units.validate_learning`, `publisher.persist` and `publisher.publish` rather than re-deciding
anything.

LAW 3 lives underneath all of it: `BrainTarget` and `LearningTarget` carry no `expert` member,
the publisher never writes one, and `learned_brain_entries` refuses one at the database
(`learned_brain_no_expert`). None of those three may be weakened to make anything here pass.
"""
