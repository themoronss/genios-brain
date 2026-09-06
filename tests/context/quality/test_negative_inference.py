"""H6 · THE NEGATIVE-INFERENCE LICENCE — the downstream half of typed absence.

**Gate H6** — part of `pytest tests/context/patterns tests/context/quality -q`, and specifically
of its measured row: **`0` negative inferences drawn from `UNKNOWABLE` facts.**

Typing an absence is half the job. The other half is that the places which read a missing fact as
a false, a zero or an absent signal have to ASK — and until they do, `UNKNOWABLE` is a well-typed
value nobody consults, which is indistinguishable from not having built it. Layer 1 shipped six
units in that state.

**The sites, found by reading every negative-inference predicate in the tree.** There are exactly
two shapes of them and both live in `packs/compiler/context_adapter.evaluate`:

    {absent: <fact path>}   "there is no amendment", "they never replied"
    {no_obs: <obs kind>}    "no reply was received", "no contract was requested"

Both answered TRUE whenever the thing was not in the slice, with no reference of any kind to
whether a source that could have carried it was connected. The authored corpus uses them: an org
with no mailbox connected satisfied `{absent: thread.last_inbound}` — *"they never replied"* — on
every situation it had, and `first-touch-unanswered` fired on a blind spot.

**And the licence that already existed and nothing read.** `capture/coverage/model._READINESS`
has computed `can_evaluate_no_reply`, `can_evaluate_no_meeting`, `can_evaluate_payment_state` and
`can_evaluate_usage_drop` since the day it was written, under a comment that says *"absence of
data must never be read as negative evidence — downstream layers get explicit readiness
predicates instead."* Nothing in the codebase has ever read one of them.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.context.quality.inference import (ABSENT_FIELDS_KEY, OBSERVATION_LICENCE_KEY,
                                                     UNKNOWABLE_FIELDS_KEY, absence_metadata,
                                                     may_infer_absent, read_licence,
                                                     read_string_set)
from genios_engine.contracts.domain_expertise import (BusinessSituationObject,
                                                      SituationContextSlice)
from genios_engine.contracts.visibility import Visibility
from genios_engine.packs.compiler.context_adapter import (ContextAdapter, PredicateState,
                                                          PredicateVerdict)

NOW = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)


def _situation(**metadata) -> BusinessSituationObject:
    base = {"domain_ids": ["sales"], "facts": {}, "model_ids": ["sales.model.b2b"]}
    base.update(metadata)
    return BusinessSituationObject(
        org_id="org_1", trace_id="trace_1",
        visibility=Visibility(scope="org", derived_from="test:org"),
        id="situation_1", signal_ids=("signal_1",), type="opportunity",
        confidence_bp=8_200, importance_bp=7_600,
        evidence=({"signal_id": "signal_1", "source": "crm"},),
        entities=({"id": "account_1", "type": "account", "name": "Acme"},),
        metadata=base)


def _context(*, facts=None, missing_fields=(), observations=(), metadata=None
             ) -> SituationContextSlice:
    return SituationContextSlice(
        org_id="org_1", trace_id="trace_context_1",
        visibility=Visibility(scope="org", derived_from="test:context"),
        id="context_1", graph_version=7, selector_version="selector.v1",
        evaluation_time=NOW, root_entity_ids=("account_1",), facts=facts or {},
        observations=observations, neighbor_facts={}, neighbor_observations=(),
        edge_count=0, missing_fields=missing_fields,
        evidence=({"source": "graph", "entity_id": "account_1"},),
        metadata=metadata or {})


def _state(condition, **slice_kw) -> PredicateVerdict:
    return ContextAdapter(_situation(), _context(**slice_kw)).evaluate(condition)


# =================================================================================================
# 1 · SITE ONE — `{absent: ...}`, the fact-path negative inference
# =================================================================================================

def test_absent_over_an_unknowable_field_is_unknown_not_true():
    """**THE GATE ROW.** `{absent: thread.last_inbound}` is the sentence *"they never replied"*.
    With no mailbox connected it is a sentence about our plumbing wearing a finding's clothes, and
    it answered TRUE."""
    verdict = _state({"absent": "thread.last_inbound"},
                     metadata=absence_metadata(unknowable=("thread.last_inbound",)))
    assert verdict.state is PredicateState.UNKNOWN
    assert verdict.missing == ("thread.last_inbound",)


def test_absent_over_a_typed_genuine_absence_is_true_because_that_is_the_product():
    """The other direction, and the reason typing an absence is not merely a safety measure.

    A source could have carried it, everything we can see was checked, and none did. *"There is no
    amendment"* is then a finding, and abstaining on it would throw away the Ownership surface in
    the name of caution.
    """
    verdict = _state({"absent": "contract.amendment"},
                     metadata=absence_metadata(absent=("contract.amendment",)))
    assert verdict.state is PredicateState.TRUE


def test_a_field_typed_absent_but_actually_present_in_the_slice_is_false():
    """The stored absence is a view of the last drain; the slice is now. When they disagree, the
    slice wins — a fact we are holding cannot be absent whatever a row says about it."""
    verdict = _state({"absent": "contract.amendment"},
                     facts={"contract.amendment": {"value": "A-2"}},
                     metadata=absence_metadata(absent=("contract.amendment",)))
    assert verdict.state is PredicateState.FALSE


def test_unknowable_beats_absent_when_a_field_is_somehow_typed_both():
    """Two absence types for one field is a producer bug, and the two answers are a fabricated
    finding and an abstention. The tie is broken toward the abstention, always."""
    verdict = _state({"absent": "contract.amendment"},
                     metadata={**absence_metadata(unknowable=("contract.amendment",),
                                                  absent=("contract.amendment",))})
    assert verdict.state is PredicateState.UNKNOWN


def test_exists_over_an_unknowable_field_is_unknown_too():
    """The mirror predicate. `{exists: x}` over a field no source could carry is not FALSE —
    which is the shape of the defect `_missing_paths` was written to fix, arriving from the
    coverage map instead of the expectation map."""
    assert _state({"exists": "contract.amendment"},
                  metadata=absence_metadata(unknowable=("contract.amendment",))
                  ).state is PredicateState.UNKNOWN


# =================================================================================================
# 2 · SITE TWO — `{no_obs: ...}` and `{neighbor_no_obs: ...}`
# =================================================================================================

def test_no_obs_is_unknown_when_the_domain_could_not_have_carried_the_observation():
    """`{no_obs: pass_received}` says *"they did not pass"*. An observation that never arrived is
    a finding only when a source that would have carried it was connected and flowing — which is
    the licence `can_evaluate_no_reply` has always computed and nothing has ever read."""
    verdict = _state({"no_obs": "pass_received"},
                     metadata=absence_metadata(observation_licensed=False))
    assert verdict.state is PredicateState.UNKNOWN
    assert verdict.missing == ("no_obs:pass_received",)


def test_neighbor_no_obs_is_gated_by_the_same_licence():
    """The neighbourhood variant is the same claim about a different node. Leaving it ungated
    would move every negative inference one hop and change nothing."""
    assert _state({"neighbor_no_obs": "negative_reply"},
                  metadata=absence_metadata(observation_licensed=False)
                  ).state is PredicateState.UNKNOWN


def test_an_observation_that_did_arrive_is_false_regardless_of_the_licence():
    """Coverage gates the ABSENCE, never the presence. A reply we can see is a reply we can see,
    and abstaining on it would make a withdrawn licence suppress positive evidence too."""
    assert _state({"no_obs": "pass_received"}, observations=({"kind": "pass_received"},),
                  metadata=absence_metadata(observation_licensed=False)
                  ).state is PredicateState.FALSE


def test_the_licence_intact_leaves_the_old_answer_exactly_as_it_was():
    """A covered domain must behave as it always did, or this change is a product change wearing
    a correctness change's clothes."""
    assert _state({"no_obs": "pass_received"},
                  metadata=absence_metadata(observation_licensed=True)
                  ).state is PredicateState.TRUE


# =================================================================================================
# 3 · ABSENT KEYS MEAN UNCHANGED BEHAVIOUR — the compatibility rule
# =================================================================================================

@pytest.mark.parametrize("condition,expected", [
    ({"absent": "contract.amendment"}, PredicateState.TRUE),
    ({"exists": "contract.amendment"}, PredicateState.FALSE),
    ({"no_obs": "pass_received"}, PredicateState.TRUE),
    ({"neighbor_no_obs": "pass_received"}, PredicateState.TRUE),
])
def test_a_slice_with_no_absence_data_evaluates_exactly_as_it_did_before(condition, expected):
    """Every caller that has not been taught about absences — a test, a script, a replay of an
    old slice — must get the answer it got yesterday. The licence is withdrawn only where an
    absence was actually TYPED, never on a guess about a slice we know nothing about."""
    assert _state(condition).state is expected


def test_an_unassessed_domain_writes_no_key_rather_than_writing_false():
    """The tri-state, carried out to the metadata. *"We did not assess"* must not arrive at the
    predicate layer as *"no observation absence is a finding"* — that would silently stop every
    `no_obs` rule for a tenant whose coverage row has merely not been filed yet."""
    assert absence_metadata(observation_licensed=None) == {}
    assert absence_metadata() == {}, \
        "an empty key on every slice would change every content-addressed package hash"
    assert absence_metadata(observation_licensed=False) == {OBSERVATION_LICENCE_KEY: False}


def test_the_keys_are_unioned_across_the_slice_and_the_situation_metadata():
    """`ContextAdapter` already unions `missing_fields` from both places. For a set that WITHDRAWS
    a licence, the union is the safer answer, so a field typed on one side and not the other keeps
    the abstention."""
    adapter = ContextAdapter(
        _situation(**{UNKNOWABLE_FIELDS_KEY: ["a.one"]}),
        _context(metadata={UNKNOWABLE_FIELDS_KEY: ["a.two"]}))
    assert adapter.unknowable_fields == frozenset({"a.one", "a.two"})
    assert adapter.evaluate({"absent": "a.one"}).state is PredicateState.UNKNOWN
    assert adapter.evaluate({"absent": "a.two"}).state is PredicateState.UNKNOWN


def test_either_source_can_withdraw_the_observation_licence():
    assert read_licence({OBSERVATION_LICENCE_KEY: True}, {OBSERVATION_LICENCE_KEY: False},
                        key=OBSERVATION_LICENCE_KEY) is False
    assert read_licence(None, {}, key=OBSERVATION_LICENCE_KEY) is True
    assert read_string_set(None, {ABSENT_FIELDS_KEY: ["x.y"]},
                           key=ABSENT_FIELDS_KEY) == frozenset({"x.y"})
    assert may_infer_absent("x.y", unknowable=frozenset({"x.y"})) is False


# =================================================================================================
# 4 · THE PRODUCER — the slice actually carries this, from the real builder
# =================================================================================================

def test_build_context_slice_carries_the_typed_absences_into_the_metadata():
    """The seam that makes the sections above reachable in production rather than only from a
    test that hands the adapter a dict.

    `context.situation_bso.build_context_slice` is the ONLY thing in the tree that constructs a
    `SituationContextSlice`, and `reason/domain_shadow.py` is the only thing that calls it.
    """
    from genios_engine.context.quality.missing import StoredAbsence
    from genios_engine.context.situation_bso import build_context_slice
    from genios_engine.contracts.quality import AbsenceType, MissingFact

    def _stored(fact_path: str, kind: AbsenceType, *, epoch: int = 1,
                stale: bool = False) -> StoredAbsence:
        return StoredAbsence(
            situation_id="sit_1", coverage_domain="sales", coverage_epoch=epoch,
            computed_at=NOW, stale_coverage=stale,
            fact=MissingFact(
                subject_node_id="nd_acme", expected_fact=fact_path, absence_type=kind,
                coverage_ready=True if kind is AbsenceType.GENUINELY_ABSENT else False,
                coverage_basis=("crm",) if kind is AbsenceType.GENUINELY_ABSENT else ()))

    slice_ = build_context_slice(
        org_id="org_1",
        situation={"situation_id": "sit_1", "anchor_node_id": "nd_acme",
                   "situation_type": "opportunity", "domain": "sales"},
        facts={}, observations=[], neighbor=(0, set(), {}), graph_version=7,
        eval_time=NOW, trace_id="trace_1",
        absences=(_stored("deal.amount", AbsenceType.UNKNOWABLE),
                  _stored("commitment.due_at", AbsenceType.GENUINELY_ABSENT),
                  # A finding whose coverage epoch has been superseded is UNVERIFIED, so it must
                  # not reach the predicate layer as a licence.
                  _stored("deal.close_date", AbsenceType.GENUINELY_ABSENT, stale=True)),
        coverage_ready=True)

    # The contract normalises a metadata sequence to a tuple on the way in; compared as a list
    # so the assertion is about the CONTENT rather than about which collection type survived.
    assert list(slice_.metadata[UNKNOWABLE_FIELDS_KEY]) == ["deal.amount"]
    assert list(slice_.metadata[ABSENT_FIELDS_KEY]) == ["commitment.due_at"], \
        "a stale-coverage finding reached the predicate layer as a licensed absence"
    assert slice_.metadata[OBSERVATION_LICENCE_KEY] is True
    assert slice_.metadata["shadow"] is True

    adapter = ContextAdapter(_situation(), slice_)
    assert adapter.evaluate({"absent": "deal.amount"}).state is PredicateState.UNKNOWN
    assert adapter.evaluate({"absent": "commitment.due_at"}).state is PredicateState.TRUE


def test_a_slice_built_with_no_absences_writes_no_absence_keys():
    """The content address must not move for a tenant with nothing typed. A slice's metadata is
    hashed into the expertise package's address, and a key written empty on every slice would
    change every package hash in the tree for a fact nobody has."""
    from genios_engine.context.situation_bso import build_context_slice

    slice_ = build_context_slice(
        org_id="org_1",
        situation={"situation_id": "sit_1", "anchor_node_id": "nd_acme",
                   "situation_type": "opportunity", "domain": "sales"},
        facts={}, observations=[], neighbor=(0, set(), {}), graph_version=7,
        eval_time=NOW, trace_id="trace_1")
    assert slice_.metadata == {"shadow": True}


def test_the_reasoning_pass_reads_the_absences_and_hands_them_to_the_builder():
    """The WIRING assertion, at the source and by name.

    `reason/domain_shadow.shadow_compile` is the production path that compiles every active
    situation, and it is reached from `reason/runner.py`. A refactor that drops these two lines
    puts the whole file above back to proving a mechanism nothing uses — which is the failure
    this assertion exists to make loud rather than silent.
    """
    import inspect

    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow.shadow_compile)
    assert "read_absences(" in source and "read_coverage_lens(" in source, \
        "the shadow pass no longer reads typed absences — the licence is ungated again"
    assert "absences=tuple(absences_by_situation" in source
    assert "coverage_ready=(coverage_lens.ready_for(" in source


# =================================================================================================
# H8 GATE REVIEW · the licence must be ASKED, not re-derived
# =================================================================================================

def test_the_adapter_ASKS_the_licence_rather_than_carrying_its_own_copy(monkeypatch):
    """`may_infer_absent` is documented as "one function rather than an `in` at each of the call
    sites, so 'which absences license an inference' has one answer a reader can see" — and it
    shipped with NO production caller, because the one consumer it was written for spelled the
    `in` out again. Two copies of one rule is how the next consumer gets a third, and the copy
    that decides is not the one a reader finds.

    Asserted by making the licence LIE. If the adapter is asking, an `may_infer_absent` that says
    "yes, you may" turns the abstention into an answer; if it is carrying its own copy, the
    monkeypatch changes nothing and the adapter abstains anyway — which is this test failing.
    """
    import genios_engine.packs.compiler.context_adapter as CA

    condition = {"absent": "thread.last_inbound"}
    unknowable = {"unknowable_fields": ["thread.last_inbound"]}
    abstains = _state(condition, metadata=unknowable)
    assert abstains.state is PredicateState.UNKNOWN, (
        "an UNKNOWABLE absence must abstain — this is the behaviour the licence exists for")

    monkeypatch.setattr(CA, "may_infer_absent", lambda path, *, unknowable: True)
    asked = _state(condition, metadata=unknowable)
    assert asked.state is not PredicateState.UNKNOWN, (
        "the adapter did not consult `may_infer_absent`: a licence nobody asks is a licence that "
        "does not exist, however well typed it is")
