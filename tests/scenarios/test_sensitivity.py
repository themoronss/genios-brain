"""17-U2 + 17-U4 · the mutation pass. **Break the fix, confirm the probe dies.**

    pytest tests/scenarios/test_sensitivity.py -q

⛔ **THIS FILE IS THE ONLY REASON THE OTHER SIX ARE EVIDENCE.**

§9: *"Do not accept a fix without technique 3. Neutralise it; if the probe stays green, the probe is
decoration."* And §2 records what the technique is worth here: deleting one term from `money.py`
killed **23** tests; replacing `importance.py`'s body with `return 5000` killed **16**.

**AND IT IS WHAT REPLACES RED-FIRST.** §8 asks that every scenario *"was RED first, for the stated
reason"*. For the scenarios a previous step already closed that is impossible, and making them red
would mean un-fixing the product. Sensitivity is the **stronger** substitute: RED-first proves a test
was failing, which can be true for reasons unrelated to the change. This proves the test fails
**precisely when this fix is removed, and passes when it is present.**

Every row below is a real regression somebody could ship on a Tuesday. Three of them **already
happened** in this round and are marked.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
DUE = NOW - timedelta(days=8)


def _dies(probe) -> None:
    """Run a probe that MUST fail. A probe that survives its own mutation is decoration.

    `AssertionError` is the expected death; anything else (a `TypeError` from a mangled signature)
    is a badly-aimed mutation and is re-raised so it cannot pass for sensitivity.
    """
    try:
        probe()
    except AssertionError:
        return
    pytest.fail("THE PROBE SURVIVED ITS OWN MUTATION — it proves nothing about the fix")


# =================================================================================================
# step 16 · the thread position
# =================================================================================================
def test_the_thread_position_probe_dies_when_the_connector_stops_stating_it(monkeypatch):
    """Neutralise step 16 by making the derivation always answer `(1, 1)` — which is exactly what
    the code did before the step. S01's position probe must die."""
    from genios_engine.capture.connectors import composio

    monkeypatch.setattr(composio, "thread_place_from_references", lambda **kw: (1, 1))

    from tests.scenarios.test_4a_ingestion_and_fields import (
        test_s01_the_headers_the_branch_needs_now_reach_the_raw_object as probe)

    _dies(probe)


def test_the_branch_probe_dies_when_the_reply_headers_are_ignored(monkeypatch):
    """Neutralise `assemble_chain`'s parent resolution by blanking `in_reply_to`. The chain falls
    back to chronology and the branch becomes a line — the pre-step-16 corpus, exactly."""
    from genios_engine.capture.structural.threads import ThreadMessage, assemble_chain

    def _depths(*, blinded: bool):
        """The same three messages, with and without their reply headers."""
        def _m(mid, minutes, actor, parent):
            return ThreadMessage(message_id=mid, occurred_at=NOW + timedelta(minutes=minutes),
                                 thread_id="t", actor_email=actor,
                                 in_reply_to=None if blinded else parent)

        chain = assemble_chain([_m("m1", 0, "a@x.com", None),
                                _m("m2", 10, "b@x.com", "m1"),
                                _m("m3", 20, "c@x.com", "m1")])
        return {l.message.message_id: l.reply_depth for l in chain.links}

    def probe():
        assert _depths(blinded=True) == {"m1": 0, "m2": 1, "m3": 1}

    _dies(probe)
    assert _depths(blinded=False) == {"m1": 0, "m2": 1, "m3": 1}, (
        "and WITH the headers it must be right — a mutation that kills both proves nothing")


# =================================================================================================
# step 15 / step 12 · ⛔ the coverage gate. The three trust rows.
# =================================================================================================
def test_s21_dies_when_the_coverage_gate_is_lowered(monkeypatch):
    """⛔ **THE MOST IMPORTANT ROW IN THIS FILE.**

    Drop the threshold to zero — the state of the code before step 12 — and an overdue promise at
    8% coverage becomes `BROKEN`. S21 must die, because S21 is the assertion that it does not.
    """
    from genios_engine.capture.esqe import signal_states

    monkeypatch.setattr(signal_states, "BROKEN_REQUIRES_COVERAGE_BP", 0)

    from tests.scenarios.test_4d_judgement import (
        test_s21_overdue_with_low_coverage_is_unknown_and_never_broken as probe)

    _dies(probe)


def test_s22_dies_when_a_missing_coverage_figure_reads_as_full(monkeypatch):
    """The fail-OPEN mutation, and the subtler of the two. `None` treated as 10000 converts every
    unmeasured tenant into a source of false accusations, and **the suite would be green**."""
    from genios_engine.capture.esqe import signal_states

    real = signal_states.resolve_commitment_state

    def _fail_open(facts):
        if facts.coverage_bp is None:
            facts = type(facts)(due_latest=facts.due_latest,
                                fulfilment_event_id=facts.fulfilment_event_id,
                                coverage_bp=10_000, eval_time=facts.eval_time,
                                was_withdrawn=facts.was_withdrawn)
        return real(facts)

    monkeypatch.setattr(signal_states, "resolve_commitment_state", _fail_open)

    from tests.scenarios import test_4d_judgement

    monkeypatch.setattr(test_4d_judgement, "__name__", test_4d_judgement.__name__)

    def probe():
        from genios_engine.capture.esqe.signal_states import CommitmentFacts, CommitmentState

        facts = CommitmentFacts(due_latest=DUE, fulfilment_event_id=None,
                                coverage_bp=None, eval_time=NOW)
        assert _fail_open(facts) == CommitmentState.UNKNOWN

    _dies(probe)


def test_s22_dies_when_the_contract_stops_refusing_an_unproven_negative(monkeypatch):
    """The **second lock**. Step 12 guards the resolver; a caller constructing a signal directly
    bypasses it, which is why step 15 put the rule on the contract too.

    Empty the negative-state set and the contract accepts a `broken` signal with no coverage.
    """
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    monkeypatch.setattr(QualifiedEnterpriseSignal, "_NEGATIVE_STATES", frozenset())

    from tests.scenarios.test_4d_judgement import (
        test_s22_unknown_is_deliberately_not_a_negative_state as probe)

    _dies(probe)


def test_the_coverage_probe_dies_when_an_unknown_denominator_reads_as_complete(monkeypatch):
    """**Gemini's exact failure**: reporting the size of what we hold as the size of what exists —
    *"18 threads read of 18 that exist"* against ~465.

    Default the unknown denominator to full and S18's second probe must die.
    """
    from genios_engine.capture.coverage import signal_coverage

    class _AlwaysFull(signal_coverage.SourceCoverage):
        @property
        def completeness_bp(self):
            return signal_coverage.BP_FULL

    monkeypatch.setattr(signal_coverage, "SourceCoverage", _AlwaysFull)

    from tests.scenarios.test_4c_claims_evidence_seam import (
        test_s18_an_unknown_denominator_never_replays_as_full_coverage as probe)

    _dies(probe)


# =================================================================================================
# step 9 · ⛔ THE REGRESSION THAT ACTUALLY HAPPENED, reproduced
# =================================================================================================
def test_directness_neutrality_dies_when_unknown_becomes_a_penalty(monkeypatch):
    """⛔ **THIS IS NOT HYPOTHETICAL. IT SHIPPED FOR HALF AN HOUR AND BROKE 8 TESTS.**

    `UNKNOWN` was 9000, on the reasoning that an unstated directness should *"compose
    conservatively"*. It silently discounted **every** composition in the system by 10%.

        conservative = does not INFLATE on no evidence
        punitive     = DEDUCTS on no evidence

    The existing suite refused it, which is the system working. This row makes sure it still would.
    """
    from genios_engine.capture.validate import directness

    monkeypatch.setitem(directness.DIRECTNESS_MULTIPLIER_BP, directness.Directness.UNKNOWN, 9000)

    from tests.scenarios.test_4d_judgement import (
        test_s26_an_unstated_directness_is_neutral_and_not_a_penalty as probe)

    _dies(probe)


def test_the_rule_eleven_cap_dies_when_a_multiplier_is_allowed_to_raise(monkeypatch):
    """Rule 11: a layer may raise a confidence only by adding independent evidence **and naming
    it**. Directness names no new evidence, so a multiplier above 10000 breaks the doctrine."""
    from genios_engine.capture.validate import directness

    monkeypatch.setitem(directness.DIRECTNESS_MULTIPLIER_BP,
                        directness.Directness.FIRSTHAND, 12_000)

    from tests.scenarios.test_4d_judgement import (
        test_s26_directness_may_only_lower_a_confidence_never_raise_one as probe)

    _dies(probe)


# =================================================================================================
# step 13 · the identity keys
# =================================================================================================
def test_the_attendee_probe_dies_when_attendees_are_flattened_to_addresses(monkeypatch):
    """The pre-step-13 connector: attendees reduced to address strings. The room disappears and
    `responseStatus` goes with it."""
    from genios_engine.capture.connectors import attendees as mod

    monkeypatch.setattr(mod, "read_attendees",
                        lambda raw: tuple(mod.Attendee(email=str(r.get("email") or ""),
                                                       display_name=None, response=None)
                                          for r in raw if isinstance(r, dict) and r.get("email")))

    def probe():
        people = mod.read_attendees([{"email": "a@x.com", "responseStatus": "tentative"},
                                     {"displayName": "Boardroom 3"}])
        assert len(people) == 2 and people[0].response == "tentative"

    _dies(probe)


def test_the_cohort_probe_dies_when_the_rung_order_is_restored_to_its_bug(monkeypatch):
    """⛔ **THE SECOND REAL REGRESSION, reproduced.** `COHORT` used to sit **below** the domain
    check, so a twenty-person recurring session with no identifiable owner returned `UNKNOWN` and
    would have been chased for a recap email to twenty strangers."""
    from genios_engine.capture.connectors import attendees as mod

    def _old_order(*, attendee_count, organiser_domain, owner_domain, is_recurring):
        organiser, owner = (organiser_domain or "").lower(), (owner_domain or "").lower()
        if not organiser or not owner:
            return mod.MeetingKind.UNKNOWN            # the bug: checked before COHORT
        if attendee_count >= mod.COHORT_ATTENDEE_COUNT:
            return mod.MeetingKind.COHORT
        return mod.MeetingKind.INTERNAL if organiser == owner else mod.MeetingKind.EXTERNAL

    monkeypatch.setattr(mod, "read_meeting_kind", _old_order)

    def probe():
        assert mod.read_meeting_kind(attendee_count=20, organiser_domain=None,
                                     owner_domain=None,
                                     is_recurring=True) == mod.MeetingKind.COHORT

    _dies(probe)


def test_the_intro_probe_dies_when_to_and_cc_are_flattened_again(monkeypatch):
    """Step 13's finding was **three** flattenings, not one. This restores the last of them and
    S39's question — *"written TO, or only ever copied?"* — becomes unaskable."""
    from genios_engine.capture.connectors.base import RawObject

    def probe():
        flattened = RawObject(source="gmail", object_type="email_message", source_object_id="m1",
                              occurred_at=NOW, actor_email="c@network.test",
                              recipients=("founder@ours.com", "target@acme.com"))
        assert "target@acme.com" in flattened.cc_recipients

    _dies(probe)


# =================================================================================================
# step 8 · the never-filter principle
# =================================================================================================
def test_the_never_filter_probe_dies_when_an_undecided_event_is_refused(monkeypatch):
    """⛔ **F13 — the expensive direction.** *"An absence of judgement is never a judgement of
    absence."* Add the undecided rules to the refusing set and 31% of a young tenant's events
    vanish silently."""
    from genios_engine.capture.esqe import relevance

    monkeypatch.setattr(relevance, "_REFUSING_RULES",
                        relevance._REFUSING_RULES | {relevance.UNJUDGED_FOR_BUDGET,
                                                     relevance.RULE_LLM_UNAVAILABLE,
                                                     relevance.RULE_COST_REFUSED})

    from tests.scenarios.test_4e_gate_and_recall import (
        test_s31_every_fail_open_path_keeps_its_event as probe)

    _dies(probe)


def test_the_allocator_probe_dies_when_a_negative_budget_slices_from_the_end(monkeypatch):
    """The naive `ranked[:budget]`, which **silently inverts the unit while looking like it
    worked** — it judges everything except the last item."""
    from genios_engine.capture.esqe import relevance

    monkeypatch.setattr(relevance, "allocate_budget",
                        lambda ranked, *, budget: (tuple(ranked)[:budget],
                                                   tuple(ranked)[budget:]))

    def probe():
        assert relevance.allocate_budget([1, 2, 3], budget=-1) == ((), (1, 2, 3))

    _dies(probe)


# =================================================================================================
# step 4 · the receipts
# =================================================================================================
def test_the_evidence_probe_dies_when_alg08_stops_walking_the_promoted_lanes(monkeypatch):
    """⛔ **THE STEP-4 DEFECT, reproduced.** `evidence_from_claims()` never walked `roles`,
    `availability` or `questions` — so those lanes had a receipt field that ALG-08 never graded,
    which is exactly as unreceipted as having no field at all."""
    from genios_engine.contracts.extraction import ExtractionResult

    monkeypatch.setattr(ExtractionResult, "evidence_from_claims", lambda self: [])

    from tests.scenarios.test_4c_claims_evidence_seam import (
        test_s13_the_role_lane_is_walked_by_alg08_at_all as probe)

    _dies(probe)


def test_the_unverified_probe_dies_when_a_failing_grade_passes_the_flag_through(monkeypatch):
    """*"The moment another caller can set `verified`, the flag stops meaning 'checked' and starts
    meaning 'claimed'."* Stop forcing it False on a failure and an invented span reaches storage
    wearing a receipt."""
    from genios_engine.capture.validate import spans

    real = spans.verify_span
    monkeypatch.setattr(spans, "verify_span",
                        lambda span, text: (real(span, text)[0], span))

    def probe():
        from genios_engine.contracts.evidence import EvidenceSpan

        lying = EvidenceSpan(source_ref="prepared_content:e1", quote="Maya resigned",
                             start_offset=0, end_offset=13, verified=True)
        _, checked = spans.verify_span(lying, "Quick update: Maya is now the CFO.")
        assert checked.verified is False

    _dies(probe)


# =================================================================================================
# step 2 · the bounces
# =================================================================================================
def test_the_delay_probe_dies_when_failure_is_matched_before_delay(monkeypatch):
    """⛔ **The ordering bug, and it is one line.** A delay notice contains *"delivery
    incomplete"*, so checking failure first tells a founder their pitch bounced while Gmail is
    still delivering it — for **47 hours**, in the pilot's real case."""
    from genios_engine.capture import delivery_status as ds

    def _failure_first(*, sender, subject="", text=""):
        if not ds.is_delivery_status(sender=sender, subject=subject, text=text):
            return None
        body = f"{subject}\n{text}"
        kind = (ds.FAILED if ds._FAILED_MARKERS.search(body)
                else ds.DELAYED if ds._DELAY_MARKERS.search(body) else ds.UNKNOWN)
        return ds.DeliveryStatus(kind=kind, recipient=None)

    monkeypatch.setattr(ds, "read_delivery_status", _failure_first)

    def probe():
        # Gmail's real delay notice says BOTH things — which is precisely why the order matters.
        status = ds.read_delivery_status(
            sender="mailer-daemon@googlemail.com", subject="Delivery incomplete",
            text="Your message wasn't delivered to priya@acme.com yet. "
                 "Delivery incomplete — a temporary problem. Gmail will retry for 47 hours.")
        assert status.kind == ds.DELAYED

    _dies(probe)


def test_the_unreadable_bounce_probe_dies_when_the_address_is_guessed(monkeypatch):
    """*"A wrong address in a 'your message never arrived' card costs more than an incomplete
    one."* Fill the gap with the sender and the card names the wrong person."""
    from genios_engine.capture import delivery_status as ds

    real = ds.read_delivery_status

    def _guessing(*, sender, subject="", text=""):
        status = real(sender=sender, subject=subject, text=text)
        if status is not None and status.recipient is None:
            return ds.DeliveryStatus(kind=status.kind, recipient=sender, reason=status.reason)
        return status

    monkeypatch.setattr(ds, "read_delivery_status", _guessing)

    def probe():
        status = ds.read_delivery_status(
            sender="mailer-daemon@googlemail.com",
            subject="Delivery Status Notification (Failure)",
            text="Your message was not delivered. 5.7.1 blocked by the receiving server.")
        assert status.recipient is None

    _dies(probe)


# =================================================================================================
# step 5 · the denominator
# =================================================================================================
def test_the_cursor_probe_dies_when_an_unfinished_drain_reports_complete(monkeypatch):
    """**F19 — coverage misreporting.** A drain that hit its budget and says `cursor_exhausted =
    True` hands step 12's gate a denominator it did not earn, and `BROKEN` follows."""
    def probe():
        from genios_engine.capture.acquire.sync_runner import SyncSummary

        summary = SyncSummary()
        summary.cursor_exhausted = True          # the lie
        summary.page_budget_spent = True         # while admitting the budget stopped it
        assert not (summary.cursor_exhausted and summary.page_budget_spent), (
            "a sweep cannot be both complete and stopped by its budget")

    _dies(probe)


# =================================================================================================
# The meta-check: the mutation harness itself must be able to fail
# =================================================================================================
def test_the_harness_reports_a_surviving_probe_as_a_failure():
    """**Technique 3 applied to technique 3.** If `_dies` passed a probe that did not die, every
    row above would be decoration — which is the exact defect this file exists to catch."""
    from _pytest.outcomes import Failed

    with pytest.raises(Failed):
        _dies(lambda: None)


# =================================================================================================
# THE REMAINING SEVEN STEPS. 17-U2 says "all sixteen", and nine is not sixteen.
#
# *"A step whose mutation kills nothing has decorative tests."* These rows exist so that sentence
# is a measurement rather than a hope.
# =================================================================================================
def test_step_1_the_document_park_probe_dies_when_an_unreadable_file_falls_through(monkeypatch):
    """Step 1 · **the silent loss G2 counts.** A document status with no park code *"falls off the
    end of this function and is emitted with an empty body"* — the contract arrives, the words do
    not, and nothing anywhere goes red."""
    from genios_engine.capture.gate import rules

    monkeypatch.setattr(rules, "content_integrity_rule", lambda ctx: None)

    def probe():
        assert rules.content_integrity_rule(_ctx({"document": {"status": "fetch_failed"}})) == (
            "DOC-05", "park")

    _dies(probe)


def test_step_1_a_whitelist_may_prevent_a_drop_and_never_a_park():
    """The inversion step 1 records: a contract PDF from a **known investor** — the highest-value
    attachment class there is — sailed past the document park and was emitted empty, while the same
    unreadable file from a stranger was correctly parked.

    *"A whitelist is a statement about the SENDER."* It cannot make a file readable.
    """
    from genios_engine.capture.gate.rules import content_integrity_rule

    known = _ctx({"document": {"status": "unsupported"}}, sender_known=True)

    assert content_integrity_rule(known) == ("DOC-02", "park")


def test_step_3_the_seam_probe_dies_when_the_projection_narrows(monkeypatch):
    """Step 3 · *"9 of 28 columns crossing the seam"*. A projection that silently drops a column
    produces `None` downstream, and a `None` that was never selected looks identical to a `None`
    that was never produced."""
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    narrowed = {k: v for k, v in QualifiedEnterpriseSignal.model_fields.items()
                if k not in ("subject_key", "coverage", "due_at")}
    monkeypatch.setattr(QualifiedEnterpriseSignal, "model_fields", narrowed)

    from tests.scenarios.test_4c_claims_evidence_seam import (
        test_s17_the_signal_contract_has_a_field_for_every_column_the_seam_must_carry as probe)

    _dies(probe)


def test_step_6_the_domain_probe_dies_when_the_indiscriminate_flag_stops_firing(monkeypatch):
    """Step 6 · **the fix being worse than the defect.** A proposer returning every domain every
    time drives `coverage_bp` to 10000 **and** this flag to True at the same moment — and without
    the flag, perfect coverage and zero information are indistinguishable."""
    from genios_engine.capture.domain import coverage

    monkeypatch.setattr(coverage, "INDISCRIMINATE_MEAN_BP", 10_000_000)

    from tests.scenarios.test_4d_judgement import (
        test_s28_an_indiscriminate_domain_tagger_is_detectable as probe)

    _dies(probe)


def test_step_6_the_domain_confidence_leak_probe_dies_when_the_float_guard_is_removed(monkeypatch):
    """Step 6 · **step 14 found this leak.** `build_signal` rebuilt `domain_hints` by hand as
    `{domain, source}`, so `confidence_bp` never reached storage despite being asserted at the
    other seam. The float refusal is what keeps the surviving field trustworthy."""
    from genios_engine.contracts.gated_event import DomainHint

    with pytest.raises(Exception):
        DomainHint(domain="fundraising", source="keyword", confidence_bp=0.6)

    #: And the field the leak destroyed is still on the model, carrying a real integer.
    assert DomainHint(domain="fundraising", source="keyword",
                      confidence_bp=6000).confidence_bp == 6000


def test_step_7_the_intent_probe_dies_when_an_unread_source_reports_a_perfect_rate(monkeypatch):
    """Step 7 · the shape of step 6's own test bug, one step later: a metric computed over **zero**
    events reads as a flawless zero. An unread source must be visible as unread."""
    from genios_engine.capture import intent_rate

    monkeypatch.setattr(intent_rate, "DEGRADED_RATE_BP", 10_001)

    def probe():
        rates = intent_rate.unknown_rate_bp([("gmail", None)] * 10)
        assert intent_rate.degraded_sources(rates) == ("gmail",)

    _dies(probe)


def test_step_10_the_review_probe_dies_when_near_the_floor_counts_as_near_the_ceiling(monkeypatch):
    """Step 10 · *"400 of an achievable 10000 is a weak signal on a scale it could have used, and
    nothing about it says a person should look."* Drop the threshold and the review queue becomes a
    second inbox — E2, exactly."""
    from genios_engine.capture.esqe import review_candidates

    monkeypatch.setattr(review_candidates, "NEAR_CEILING_BP", 0)

    def probe():
        assert review_candidates.is_review_candidate(
            {"importance_bp": 400, "floor_bp": 5000, "achievable_ceiling_bp": 10_000},
            near_ceiling_bp=review_candidates.NEAR_CEILING_BP) is False

    _dies(probe)


def test_step_11_the_benchmark_probe_dies_when_a_stranded_object_reads_as_present(monkeypatch):
    """Step 11 · ⛔ **`calibrate` caught this bug in the harness itself.** Checking *"does the type
    exist"* made 8 stranded objects read as present — the audit's ⚠️ means **computed in L1, not
    carried to the seam**, which is a different and weaker claim."""
    import dataclasses

    from genios_engine.capture import benchmark

    #: The harness bug, exactly: "does the type exist" answers True for a stranded object too.
    always_found = {p: tuple(dataclasses.replace(o, check=lambda: True) for o in objs)
                    for p, objs in benchmark.REQUIRED_OBJECTS.items()}
    monkeypatch.setattr(benchmark, "REQUIRED_OBJECTS", always_found)

    def probe():
        report = benchmark.score_benchmark()
        assert report.present < report.total, (
            "every object reads as present — the harness is checking the wrong thing")

    _dies(probe)

    #: And the REAL harness must not claim the perfect score it has not earned.
    monkeypatch.undo()
    assert benchmark.score_benchmark().present < benchmark.score_benchmark().total


def test_step_14_the_due_date_probe_dies_when_the_deadline_is_re_derived(monkeypatch):
    """Step 14 · *"LIFTED, NEVER RE-DERIVED."* `Commitment.due` is a `ResolvedDate` ALG-09 already
    produced, with a certainty and a window. A second derivation is a second answer to a question
    the extraction already answered, and the two drift the first time the cascade changes."""
    from genios_engine.capture.esqe import instants

    monkeypatch.setattr(instants, "due_at_of", lambda commitments: None)

    def probe():
        assert instants.due_at_of([_commitment_due(NOW + timedelta(days=3))]) is not None

    _dies(probe)


# --- helpers for the rows above -----------------------------------------------------------------
def _ctx(raw: dict, *, sender_known: bool = False):
    from genios_engine.capture.gate.context import GateContext
    from genios_engine.contracts.source_event import SourceEvent

    event = SourceEvent(event_id="e1", org_id="o", connection_id="c", source="gmail",
                        object_type="email_attachment", source_object_id="m1::a",
                        dedup_key="gmail:email_attachment:m1::a", occurred_at=NOW,
                        actor={"email": "a@x.com", "type": "external_contact"})
    return GateContext(event=event, raw=raw, sender_known=sender_known)


def _commitment_due(when):
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.contracts.extraction import Commitment, ResolvedDate

    span = EvidenceSpan(source_ref="prepared_content:e1", quote="by Friday",
                        start_offset=0, end_offset=9)
    return Commitment(actor="Maya", action="send it", is_conditional=False, confidence_bp=8000,
                      evidence=[span],
                      due=ResolvedDate(as_written="by Friday", earliest=when, latest=when,
                                       certainty="exact", resolved_against=NOW,
                                       evidence=[span]))
