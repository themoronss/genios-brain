"""The angles this build ships with — declarations, and nothing else.

Registered at import the way `domain_spec._SPECS` is, so a build that includes this package
includes its questions and a test may register its own beside them. Every angle here reads a queue
the deterministic layer BUILT BY REFUSING, which is the only kind of queue this layer is allowed
to ask a model about: `angles/contract.py` states the rule and the gate enforces it.
"""
from genios_engine.context.angles.contract import Angle, CostTier, GateSource, register

#: IS THERE ANYTHING TO DO IN THIS COUNTERPARTY'S REVIEW QUEUE RIGHT NOW?
#:
#: THE QUEUE IS A REFUSAL, AND THAT IS WHY A MODEL MAY SEE IT. `correlation_timeline.
#: parse_condition` returns None for anything it cannot match to a date, a count or a named event,
#: and its docstring names the danger in the same breath: *"A parser that reached for the nearest
#: plausible reading would turn every rhetorical aside — 'let's talk once things settle down' —
#: into a predicate that eventually evaluates true and nags somebody about a throwaway line."*
#: Those refusals are published to `derived.timeline.condition_review` with the counterparty's own
#: sentence attached, and `condition_situations` turns them into a flat queue somebody is supposed
#: to read. Twenty-four of them sat on the pilot, in no order, with no way to tell which mattered.
#:
#: THIS ANGLE MUST NOT DO WHAT THE PARSER REFUSED TO DO. It is not asked to produce a predicate —
#: that is the failure above, and a model is better at it than the parser only in the sense that
#: it will always produce one. `condition.predicate` stays absent, `missing=["condition.predicate"]`
#: stays on every card, and the coverage score keeps saying "not evaluable". The question asked
#: here is the one the parser was never asked and does not answer: given these sentences and what
#: has happened with this person since, is any of it worth opening TODAY.
#:
#: THE VERDICT IS ABOUT THE QUEUE, NOT ABOUT ONE CONDITION, and that is forced by the data rather
#: than chosen. `correlation_timeline._fact_rows` writes ONE fact per node whose value is a LIST
#: (`{"review": [...]}`, up to `MAX_PER_NODE` = 6), so `store._slices` — which keys by
#: `f.subject_node_id` — admits one subject per counterparty, not one per condition. A four-way
#: enum answering for a node cannot say which of three entries is met, so it does not pretend to:
#: the answers are about the node's queue and the fields carried back say `queue`. Where a node
#: holds a single condition, which is the ordinary case, the two granularities coincide.
#:
#: `all_courtesies` IS THE POINT, NOT A SPARE OPTION. It is how the model AGREES with the parser
#: — "always happy to take a look and reconsider" is a courtesy, not a trigger — and without it
#: every rhetorical aside is forced into `something_is_met` or `nothing_yet`, which is precisely
#: the nagging the parser exists to prevent. If most of the pilot's queue comes back
#: `all_courtesies`, the finding is that a 24-item review queue does not need a human afternoon,
#: and nobody can currently know that.
#:
#: `unknowable` IS THE OTHER HONEST EXIT, and it is load-bearing because of what `sees` cannot
#: reach. A condition about the TENANT'S OWN business — "once you have two enterprise references"
#: — is not answerable from a relationship slice, and `correlation_timeline.build_world` says why
#: the graph is not the place to go looking: *"`graph_source_refs.evidence` stores `{"text": ...}`
#: with no offsets, so a fact read back from the graph cannot produce an `EvidenceSpan` that
#: anybody can check."* Refusing costs one call and closes the question; widening `sees` until a
#: model is reading the tenant's whole graph would cost the property that makes this reviewable.
#:
#: WHAT LEAVES THE TENANT IS FIVE NAMED FIELDS. The gate row carries the sentences, who said them
#: and what was promised; the other four say what has happened between the two parties since.
#: Each is written to the COUNTERPARTY node — `DormantCondition.subject_node_id` is "the resolved
#: counterparty, never a raw name", and `derived.py` writes `thread.last_*` onto exactly those
#: person nodes — so `store._seen`, which reads `subject_node_id = :s` and nothing else, actually
#: finds them. An angle naming fields that live on another node would not error; it would ask a
#: model about blanks and bill for it.
CONDITION_QUEUE_TRIAGE = register(Angle(
    angle_id="condition_queue_triage",
    version="1.0.0",
    gate=("derived.timeline.condition_review",),
    gate_source=GateSource.FACTS,
    sees=(
        # The refusals themselves: each sentence, its actor, its action, when it was said. Already
        # in hand from the gate, so `_seen` reuses it and it costs no second read.
        "derived.timeline.condition_review",
        # …and what has happened between the two parties since. A relationship slice, not a graph:
        # four fields, each already written to this same node by a pass that runs every sweep.
        "thread.last_inbound",
        "thread.last_outbound",
        "party.role",
        "relationship.nature",
    ),
    returns=("something_is_met", "nothing_yet", "all_courtesies", "unknowable"),
    refusal="unknowable",
    # Banded where `llm_interpretation` bands its own readings. A verdict here is an opinion about
    # sentences the parser declined to formalise; it must never outrank the satisfaction
    # `correlation_timeline` computes deterministically, which carries two evidence spans and
    # refuses to exist without them.
    confidence_band=(2_000, 8_000),
    # Counterparties, not conditions — see the granularity note above. The pilot's whole queue is
    # twenty-four conditions across fewer nodes than that. The ceiling is not a guess at volume:
    # it is the number above which somebody should be asked why this queue is that big.
    max_per_sweep=40,
    cost_tier=CostTier.CHEAP,
    note=("Orders the review queue; it does not resolve it. A verdict is carried as "
          "`condition.queue_reading` onto the node's existing cards and never mints a "
          "satisfaction — `condition_satisfied` requires BOTH evidence spans, and a model "
          "judging from facts can quote the promise but not the event that met it."),
))

__all__ = ["CONDITION_QUEUE_TRIAGE"]
