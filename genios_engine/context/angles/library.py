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

#: WE OWE THIS PERSON A REPLY AND NOTHING ON THE BOARD SAYS SO — DOES IT MATTER?
#:
#: THE CASE THE FOUNDER NAMED, IN THEIR OWN WORDS. Boardy made many introductions, many of those
#: people REPLIED, and the replies went unanswered. `migrations/0164` records the shape as the
#: reason `ball_in_court_unreported` exists at all: *"a node whose `thread.ball_in_court` fact says
#: the turn is OURS, with no live situation. This is the shape the founder named directly: they
#: replied, we went quiet, and nothing said so."* A deterministic reading for it now exists —
#: `outreach_situations.read_unanswered_replies`, anchor `unanswered` — so what remains in this
#: residue kind is precisely what that reading MISSED. This angle triages the miss.
#:
#: WHICH MAKES IT A COVERAGE QUEUE, NOT A CARD QUEUE, and the distinction is the whole licence for
#: this angle to exist. A residue row means no live situation covers the subject, so there is no
#: card here to rank and none is minted: the verdict orders the work queue `read_residue` returns.
#: The agreed law is *"a model may propose a situation; it may never rank one, and never produces
#: a number a card asserts"* — deciding which unexplained subjects a HUMAN or a later unit should
#: look at first is neither. Whether any of these becomes a card is `is_this_worth_a_card`'s
#: question in Step 5, and this is the input it will read.
#:
#: `noise` IS HOW THE MODEL DISAGREES WITH THE FACT, and it is allowed to. `thread.ball_in_court`
#: is derived from a thread reconstruction that cannot tell a personal note from a no-reply blast,
#: so "the turn is ours" is sometimes true of a newsletter. Saying so removes nothing — an angle
#: cannot delete a residue row, retire a fact or suppress a reading — it only sinks that subject in
#: the queue. Without the option, every blast is forced to `important` or `ambient` and the queue
#: keeps the exact noise it was built to expose.
#:
#: WHAT IT SEES IS EVERYTHING THAT SURVIVES A REPLY, AND THAT WORD IS LOAD-BEARING.
#: `thread.days_waiting` is the field a reader reaches for first and it is the one field that is
#: guaranteed ABSENT here: `waiting.py` lists it in `WAITING_ONLY_FIELDS`, retired through
#: `retire_facts` the moment a counterparty answers — and `ball_in_court = us` MEANS they answered
#: last. Naming it would not error; it would put a permanent blank in front of the model and bill
#: for it. `thread.last_heard_days` and `party.reply_cadence_days` are the two the same module
#: marks as staying true after a reply ("they stay true after a reply and are rewritten every
#: sweep"), which is exactly what this queue needs: how long they have been waiting on US, and
#: what their own rhythm looks like.
#:
#: THE GATE VALUE IS NOT IN `sees` BECAUSE IT IS EMPTY. `residue.detect_residue` writes this kind
#: with `detail = "{}"` — the row's meaning is entirely in its existence. Naming it would add a
#: constant to every slice and to `saw_hash` and tell the model nothing.
REPLY_OWED_TRIAGE = register(Angle(
    angle_id="reply_owed_triage",
    version="1.0.0",
    gate=("ball_in_court_unreported",),
    gate_source=GateSource.RESIDUE,
    sees=(
        # Whose turn it is, from the fact the residue query itself selected on — so the gate
        # cannot admit a subject that lacks it.
        "thread.ball_in_court",
        # When each side last spoke. Written by `derived.py` onto person nodes under the same
        # `if row.subject_node_id in people` guard that writes `thread.ball_in_court`, so they
        # co-locate on the node the gate returns.
        "thread.last_inbound",
        "thread.last_outbound",
        # …and the two waiting-derived fields that OUTLIVE a reply. See the note above: the
        # obvious third one is retired for exactly this population.
        "thread.last_heard_days",
        "party.reply_cadence_days",
        # Who they are to this business. `relationship.nature` is what the counterparty IS;
        # `party.role` is often the structural default — `correlation_organization` prefers the
        # first over the second for that reason and both are cheap.
        "party.role",
        "relationship.nature",
    ),
    returns=("important", "developing", "ambient", "noise", "unknowable"),
    refusal="unknowable",
    # The same walls as every other angle. A verdict here orders a coverage queue and must never
    # read as a measurement — `confidence_bp` reaches no card, by construction: nothing in the
    # card path reads `context_angle_verdicts` for this angle.
    confidence_band=(2_000, 8_000),
    # HIGHER THAN THE CONDITION QUEUE BECAUSE THIS ONE IS UNBOUNDED BY NATURE — every counterparty
    # who ever replied without an answer is a candidate, where conditions are only the sentences a
    # parser refused. It does not need to cover the queue in one sweep: `store.evaluate_angle`
    # charges budget only for subjects it actually ASKS about, and an unchanged slice is free
    # forever, so a backlog drains over a few sweeps and then costs one SELECT.
    max_per_sweep=60,
    cost_tier=CostTier.CHEAP,
    note=("Orders the residue work queue; it mints nothing and ranks no card. `noise` is the "
          "model disagreeing that a reply is owed, which sinks a subject in the queue and "
          "removes nothing — an angle cannot delete a residue row or retire a fact."),
))

__all__ = ["CONDITION_QUEUE_TRIAGE", "REPLY_OWED_TRIAGE"]
