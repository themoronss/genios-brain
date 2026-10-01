"""U04 · a held situation names the evidence that would free it.

    pytest tests/context/test_a_hold_asks_for_what_would_free_it.py -q

On the pilot, 504 situations held against 28 admitted, and every hold was a question nobody asked.

⛔ THE TESTS THAT MATTER ARE THE EXCLUSIONS AND THE COLLAPSE. Four of seven hold reasons must raise
NOTHING, and the two that are really one question must file ONE need. Both are easy to get wrong in
the direction that looks more helpful and is worse.
"""

from __future__ import annotations

import pytest

from genios_engine.context.hold_needs import (COVERAGE_HOLD, L1_EVIDENCE_HOLDS, NEED_WORTHY_HOLDS,
                                              needs_from_hold, needs_from_holds, subject_for_hold)
from genios_engine.context.situation_publisher import HoldReason
from genios_engine.contracts.domain_expertise import SituationCandidate

pytestmark = pytest.mark.unit

_QES = HoldReason.QES_REQUIRED.value
_SPAN = HoldReason.VERIFIED_EVIDENCE_REQUIRED.value


#: The contract refuses a candidate with no evidence AND no signal, so every REAL candidate carries
#: both. This default is therefore the minimum a candidate can legally be, not a convenience.
_MIN_EVIDENCE = ({"source_ref": "prepared_content:EV-1", "quote": "x"},)


def _candidate(*, evidence=_MIN_EVIDENCE, signal_ids=("SIG-1",), org_id="org_x"):
    return SituationCandidate(
        org_id=org_id, trace_id="t", visibility={}, id="SIT-1",
        signal_ids=tuple(signal_ids), type="contract_renewal",
        confidence_bp=5000, importance_bp=5000, evidence=tuple(evidence))


class _Row:
    """A duck-typed stand-in for what the PUBLISH path actually passes.

    `situation_bso.l1_refusal` records the split in its own words: *"the importance sweep passes
    dataclass-ish rows; the PUBLISH path passes SQLAlchemy `RowMapping`s"*. So a subject-less input is
    unreachable through `SituationCandidate` — whose constructor demands a signal and evidence — and
    reachable through a row. That is why the guard exists and why it is tested like this.
    """

    def __init__(self, *, org_id="org_x", evidence=(), signal_ids=()):
        self.org_id = org_id
        self.evidence = evidence
        self.signal_ids = signal_ids


# =================================================================================================
# 1 · ⛔ the four exclusions — the design is what does NOT become a need
# =================================================================================================
@pytest.mark.parametrize("reason", [
    HoldReason.CONFLICT_OPEN.value,
    HoldReason.CROSS_DOMAIN_CONTRADICTION.value,
    HoldReason.IDENTITY_REVIEW_REQUIRED.value,
    HoldReason.PATTERN_EVIDENCE_REQUIRED.value,
])
def test_a_hold_that_is_not_an_evidence_question_raises_nothing(reason):
    """Two of these are contradictions — more evidence adds a third fact to a disagreement between
    two. One is a judgement about records we hold. One is OUR missing pattern rule, and fetching the
    tenant's documents cannot supply it."""
    assert needs_from_hold(_candidate(), [reason], trace_id="t") == []


def test_the_worthy_set_is_closed_and_is_three_of_seven():
    assert NEED_WORTHY_HOLDS == {_QES, _SPAN, COVERAGE_HOLD}
    assert len(list(HoldReason)) == 7


def test_a_situation_held_only_on_a_contradiction_keeps_waiting_for_a_ruling():
    """A need here would close successfully while the situation stayed held — teaching the system
    that its questions are always answered, which is worse than not asking."""
    assert needs_from_hold(_candidate(), [HoldReason.CONFLICT_OPEN.value,
                                          HoldReason.IDENTITY_REVIEW_REQUIRED.value],
                           trace_id="t") == []


# =================================================================================================
# 2 · ⛔ the pair collapses into ONE need
# =================================================================================================
def test_the_pair_is_one_question_not_two():
    """`situation_bso` measured it: 480 of 504 holds carry BOTH, and "it is one: both are downstream
    of `l1` being `None`. Feeding the bundle clears both." Two needs would be 960 rows for 480
    questions, two fetches for one answer, and two charges."""
    needs = needs_from_hold(_candidate(), [_QES, _SPAN], trace_id="t")
    assert len(needs) == 1


def test_either_half_of_the_pair_alone_asks_the_same_question():
    """The need id must not depend on WHICH of the pair fired, or a situation that was held on one
    and is later held on both files a second row for the same question."""
    a = needs_from_hold(_candidate(), [_QES], trace_id="t")[0]
    b = needs_from_hold(_candidate(), [_SPAN], trace_id="t")[0]
    both = needs_from_hold(_candidate(), [_QES, _SPAN], trace_id="t")[0]
    assert a.need_id == b.need_id == both.need_id


def test_the_pair_and_a_coverage_hold_are_two_needs():
    """Different questions. One asks whether Layer 1 published; the other whether we looked at all
    of a source."""
    needs = needs_from_hold(_candidate(), [_QES, _SPAN, COVERAGE_HOLD], trace_id="t")
    assert len(needs) == 2
    assert len({n.need_id for n in needs}) == 2


# =================================================================================================
# 3 · the subject the executor can act on
# =================================================================================================
def test_a_document_span_wins_because_re_extraction_is_cheaper():
    cand = _candidate(evidence=({"source_ref": "chunk:DOC-9:3"},), signal_ids=("SIG-1",))
    assert subject_for_hold(cand) == "document:DOC-9"


def test_without_a_document_span_it_falls_back_to_the_signal():
    assert subject_for_hold(_candidate(signal_ids=("SIG-7",))) == "signal:SIG-7"


def test_the_first_document_span_wins_over_a_later_one_deterministically():
    """Two sweeps over one candidate must name one subject, or the need id moves and the queue grows
    a second row for the same question."""
    cand = _candidate(evidence=({"source_ref": "chunk:DOC-A:1"}, {"source_ref": "chunk:DOC-B:2"}))
    assert subject_for_hold(cand) == "document:DOC-A"


def test_a_prepared_content_span_is_never_called_a_thread():
    """⛔ An event id is not a thread id. Inventing that mapping would file a need whose fetch names a
    thread that does not exist — a need that can never be met and never honestly closed."""
    cand = _candidate(evidence=({"source_ref": "prepared_content:EV-4"},), signal_ids=("SIG-2",))  # noqa: E501
    subject = subject_for_hold(cand)
    assert subject == "signal:SIG-2"
    assert "thread:" not in subject


def test_a_real_candidate_can_never_be_subjectless():
    """`SituationCandidate.__post_init__` refuses both an empty `signal_ids` and an empty `evidence`,
    so the signal fallback always fires for a real candidate. Worth asserting: it is the reason the
    common path never files a need it cannot execute."""
    with pytest.raises(ValueError, match="at least one qualified signal"):
        _candidate(signal_ids=())
    assert subject_for_hold(_candidate()) is not None


def test_a_subjectless_row_files_nothing():
    """Reachable through the PUBLISH path, which passes rows rather than candidates. The executor
    would have nothing to fetch for and no way to know when it was done — a row that sits open
    forever, which is the state this step exists to end."""
    assert subject_for_hold(_Row()) is None
    assert needs_from_hold(_Row(), [_QES], trace_id="t") == []


def test_a_malformed_span_does_not_crash_the_sweep():
    cand = _candidate(evidence=({"source_ref": "chunk::"}, {"source_ref": ""}),
                      signal_ids=("SIG-3",))
    assert subject_for_hold(cand) == "signal:SIG-3"


# =================================================================================================
# 4 · the subject reaches a fetch Layer 1 can actually plan
# =================================================================================================
@pytest.mark.parametrize(("evidence", "signal_ids", "expected_kind"), [
    (({"source_ref": "chunk:DOC-9:1"},), ("SIG-1",), "reextract"),
    (_MIN_EVIDENCE, ("SIG-1",), "backfill_window"),
])
def test_layer_one_can_plan_a_fetch_for_every_need_filed(evidence, signal_ids, expected_kind):
    """⛔ THE END-TO-END GUARD. A need whose subject `plan_fetch` returns `None` for closes immediately
    as "no Layer 1 fetch answers this" — a question filed and abandoned in one pass."""
    from genios_engine.capture.acquire.evidence_need import plan_fetch

    need = needs_from_hold(_candidate(evidence=evidence, signal_ids=signal_ids),
                           [_QES], trace_id="t")[0]
    assert plan_fetch(need) == expected_kind


# =================================================================================================
# 5 · the coverage need names its source
# =================================================================================================
def test_a_coverage_need_narrows_to_the_named_source():
    """⛔ Coverage is per source and never blended. A coverage need answered from a DIFFERENT source
    has not improved that source's coverage — it has made the gap harder to see, because something
    arrived and the hold cleared."""
    needs = needs_from_hold(_candidate(), [f"{COVERAGE_HOLD}:gmail"], trace_id="t")
    assert needs[0].acceptable_sources == ("gmail",)
    assert needs[0].accepts("drive") is False
    assert "gmail" in needs[0].question


def test_an_unnamed_coverage_gap_still_files_but_does_not_pretend_to_know():
    needs = needs_from_hold(_candidate(), [COVERAGE_HOLD], trace_id="t")
    assert needs[0].acceptable_sources == ()
    assert "unnamed source" in needs[0].question


# =================================================================================================
# 5 · ⛔ a paraphrase can never close a span hold
# =================================================================================================
def test_a_paraphrase_can_never_close_a_verified_span_hold():
    """The hold is specifically about a span, and a span has to be checkable byte-for-byte against
    source text. A summary of a message is not the message."""
    need = needs_from_hold(_candidate(), [_SPAN], trace_id="t")[0]
    for source in ("model_paraphrase", "email_summary", "chat_message"):
        assert need.accepts(source) is False


def test_every_need_says_why_it_matters():
    for reasons in ([_QES], [_SPAN], [COVERAGE_HOLD], [_QES, COVERAGE_HOLD]):
        for need in needs_from_hold(_candidate(), reasons, trace_id="t"):
            assert need.why_it_matters.strip()
            assert need.state == "open"


# =================================================================================================
# 6 · a sweep's worth of holds
# =================================================================================================
def test_two_situations_held_on_one_subject_are_one_need():
    """One question, one fetch, one charge."""
    a, b = _candidate(), _candidate()
    needs = needs_from_holds([(a, [_QES]), (b, [_SPAN])], trace_id="t")
    assert len(needs) == 1


def test_different_tenants_never_share_a_need():
    needs = needs_from_holds([(_candidate(org_id="org_a"), [_QES]),
                              (_candidate(org_id="org_b"), [_QES])], trace_id="t")
    assert len(needs) == 2


def test_a_sweep_of_unworthy_holds_files_nothing():
    needs = needs_from_holds([(_candidate(), [HoldReason.CONFLICT_OPEN.value])], trace_id="t")
    assert needs == []


def test_the_need_id_is_stable_across_sweeps():
    """Holds are re-derived every sweep. Without a stable id the table would measure how long we
    have been waiting, not what for."""
    a = needs_from_hold(_candidate(), [_QES], trace_id="sweep-1")[0]
    b = needs_from_hold(_candidate(), [_QES], trace_id="sweep-2")[0]
    assert a.need_id == b.need_id


# =================================================================================================
# 7 · ⛔ it flows through data, never by calling capture
# =================================================================================================
def test_this_module_does_not_reach_into_capture():
    """A publication pass that fetched inline would make admission wait on a network."""
    import inspect

    from genios_engine.context import hold_needs

    source = inspect.getsource(hold_needs)
    assert "genios_engine.capture" not in source
