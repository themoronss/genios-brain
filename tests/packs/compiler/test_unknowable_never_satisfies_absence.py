"""L3.1-U1 · typed absence, and the one row J3 states as a count: **0**.

*"`UNKNOWABLE` never satisfies `absence`"* — because "we cannot see it" is not "it is not there",
and treating them alike is how a negative inference gets drawn from a dark connector. An org with
no mailbox connected satisfied `{absent: thread.last_inbound}` — "they never replied" — on every
situation it had.

The older `{absent: ...}` operator already refuses that (`context/quality/inference` withdrew the
licence); these tests hold the line for the NEW `{kind: absence, type: ...}` predicate, which asks
the classifier's own question and must not answer it from silence.
"""
from __future__ import annotations

import pytest
from l3_inputs import build_situation, build_slice

from genios_engine.context.quality.inference import (ABSENT_FIELDS_KEY, OBSERVATION_LICENCE_KEY,
                                                     UNKNOWABLE_FIELDS_KEY, absence_metadata)
from genios_engine.contracts.quality import AbsenceType
from genios_engine.packs.compiler import DomainCompiler, ExpertBrainCatalog, InMemoryRuntimeBrains
from genios_engine.packs.compiler.context_adapter import (ABSENCE_PREDICATE_TYPES, ContextAdapter,
                                                          PredicateState)

FACT = "decision.scheduled"


def _verdict(condition, *, facts=None, neighbor_facts=None, metadata=None):
    return ContextAdapter(
        build_situation(),
        build_slice(facts=facts, neighbor_facts=neighbor_facts, metadata=metadata),
    ).evaluate(condition)


def test_the_only_two_answerable_types_are_the_two_the_slice_carries():
    """`AbsenceType` has five members; `build_context_slice` carries the two that decide whether a
    negative inference is licensed. A predicate naming PRESENT, STALE or NOT_EXPECTED is refused
    by name rather than answered from a set that does not describe it."""
    assert ABSENCE_PREDICATE_TYPES == {AbsenceType.GENUINELY_ABSENT.value,
                                       AbsenceType.UNKNOWABLE.value}
    assert ABSENCE_PREDICATE_TYPES < {member.value for member in AbsenceType}


def test_a_genuinely_absent_fact_satisfies_the_predicate():
    """The positive half, and the whole point of typing an absence: some absences ARE the
    intelligence. A source that could have carried it was connected, everything visible was
    checked, and none of it held the fact."""
    verdict = _verdict({"kind": "absence", "fact": FACT, "type": "GENUINELY_ABSENT"},
                       metadata=absence_metadata(absent=[FACT]))
    assert verdict.state is PredicateState.TRUE


def test_an_unknowable_fact_never_satisfies_genuine_absence():
    """THE ROW. Zero, and it is UNKNOWN rather than FALSE — "no connected source could have
    carried it" is a statement about us, not about the world, so it licenses neither claim."""
    verdict = _verdict({"kind": "absence", "fact": FACT, "type": "GENUINELY_ABSENT"},
                       metadata=absence_metadata(unknowable=[FACT]))
    assert verdict.state is PredicateState.UNKNOWN
    assert verdict.missing == (FACT,)


def test_unknowable_is_itself_askable():
    """The 1:1 mapping doc 00 names works in both directions: a capability may condition on "we
    cannot see this", which is a different and useful situation from "this is not there"."""
    verdict = _verdict({"kind": "absence", "fact": FACT, "type": "UNKNOWABLE"},
                       metadata=absence_metadata(unknowable=[FACT]))
    assert verdict.state is PredicateState.TRUE


def test_a_genuinely_absent_fact_is_definitely_not_unknowable():
    """The one crisp negative in this family: the classifier positively typed it, so the other
    question has a real answer."""
    verdict = _verdict({"kind": "absence", "fact": FACT, "type": "UNKNOWABLE"},
                       metadata=absence_metadata(absent=[FACT]))
    assert verdict.state is PredicateState.FALSE


def test_an_untyped_gap_is_unknown_not_a_finding():
    """The difference from `{absent: ...}`, stated as a test. A slice that carried no absence
    typing for this path has not said the fact is genuinely absent; it has said nothing. This
    predicate will not answer from silence — an untyped gap read as a finding is exactly what
    `context/quality` exists to stop."""
    verdict = _verdict({"kind": "absence", "fact": FACT, "type": "GENUINELY_ABSENT"})
    assert verdict.state is PredicateState.UNKNOWN
    assert verdict.missing == (f"absence:{FACT}",)


def test_the_type_is_required_and_is_never_defaulted_to_the_licensing_one():
    """Defaulting a missing `type:` to GENUINELY_ABSENT would grant the negative-inference licence
    by omission — the one member of the five that licenses anything, handed out for a typo."""
    verdict = _verdict({"kind": "absence", "fact": FACT},
                       metadata=absence_metadata(absent=[FACT]))
    assert verdict.state is PredicateState.UNKNOWN
    assert verdict.missing == ("absence_type:untyped",)


@pytest.mark.parametrize("named", ["present", "stale", "not_expected", "genuinely-absent-ish"])
def test_a_type_the_slice_cannot_answer_is_refused_by_name(named):
    verdict = _verdict({"kind": "absence", "fact": FACT, "type": named},
                       metadata=absence_metadata(absent=[FACT]))
    assert verdict.state is PredicateState.UNKNOWN
    assert verdict.missing == (f"absence_type:{named.replace('-', '_')}",)


def test_a_fact_held_on_a_neighbour_is_not_absent():
    """`situation_bso._missing_paths` counts the neighbourhood as held and `reason/adapters/native`
    borrows a root field from the 1-hop neighbours, so a fact present there is one the reasoner
    can read. Calling it absent would be a finding drawn over evidence we have."""
    verdict = _verdict({"kind": "absence", "fact": FACT, "type": "GENUINELY_ABSENT"},
                       neighbor_facts={FACT: "2026-09-09T10:00:00+00:00"},
                       metadata=absence_metadata(absent=[FACT]))
    assert verdict.state is PredicateState.FALSE


def test_the_older_absent_operator_still_refuses_unknowable_unchanged():
    """MUST NOT REGRESS. The new kind does not replace `{absent: ...}` — seven authored conditions
    use it today — and the law is the same on both."""
    assert _verdict({"absent": FACT},
                    metadata=absence_metadata(unknowable=[FACT])).state is PredicateState.UNKNOWN
    assert _verdict({"absent": FACT},
                    metadata=absence_metadata(absent=[FACT])).state is PredicateState.TRUE


def test_an_unknowable_absence_abstains_a_real_compile_rather_than_routing_it(authoring_root):
    """Reach, on the compile path, for the row that matters most: a capability whose situation
    conditions on a genuine absence must ABSTAIN over a dark connector, not route.

    `SituationContextIncomplete` is the abstention — the resolver raises it when every route it
    saw was unresolved rather than refused — and the receipt names the path.
    """
    from genios_engine.packs.compiler.errors import SituationContextIncomplete
    when = f"[{{kind: absence, fact: {FACT}, type: GENUINELY_ABSENT}}]"
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(authoring_root(when=when)),
                              runtime_brains=InMemoryRuntimeBrains(), require_admission=False)

    with pytest.raises(SituationContextIncomplete) as raised:
        compiler.compile(build_situation(),
                         build_slice(metadata=absence_metadata(unknowable=[FACT])))
    assert f"sales.sit.anchor:{FACT}" in str(raised.value)

    # And the same corpus, the same predicate, over a TYPED absence: it routes.
    package = compiler.compile(build_situation(),
                               build_slice(metadata=absence_metadata(absent=[FACT])))
    assert package.metadata["matched_situation_ids"] == ("sales.sit.anchor",)


def test_the_observation_licence_key_is_untouched_by_this_wave():
    """`no_obs` keeps its own licence and its own key. Two absence questions, two mechanisms — a
    field path can be typed individually, an observation kind cannot, which is why the licence for
    observations is one bit off the domain's coverage."""
    adapter = ContextAdapter(build_situation(), build_slice(
        metadata=absence_metadata(observation_licensed=False)))
    verdict = adapter.evaluate({"no_obs": "reply_received"})
    assert verdict.state is PredicateState.UNKNOWN
    assert verdict.missing == ("no_obs:reply_received",)
    assert OBSERVATION_LICENCE_KEY in absence_metadata(observation_licensed=False)
    assert UNKNOWABLE_FIELDS_KEY in absence_metadata(unknowable=[FACT])
    assert ABSENT_FIELDS_KEY in absence_metadata(absent=[FACT])
