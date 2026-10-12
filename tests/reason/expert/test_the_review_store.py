"""STEP-12 · the review store — written once per file per fingerprint, read back without the model.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_the_review_store.py -q

`reason/expert/store.py` (tree `yc2_w27_s12` M32.C3.L-data.V1.U03), over `expert_reviews` (0197). The expert
reviews a file once per fingerprint, so its review is kept on that key: a second write for a fingerprint
that has a standing row is refused — a valid review is the record, and a refusal (on substance, or cut at
the token ceiling) stands until the file moves, STEP-12 §8.4 item 4. A row that FAILED, or that was
carried because the day's budget was spent (D7: "carries the rest"), is not the expert's verdict: its
retry may replace it. A valid row reads back as the same `ExpertReview` that was written; the latest
valid review of a file is one read; nothing here asks a model.

M32.C3.L-data.V1.U10: every row keeps what the file WAS when it was judged — its fingerprint's inputs
(0198) — and a retry replaces them with the rest; a file's latest STANDING review (valid, refused or
truncated) is what the last judgment saw, the row the triggers diff against.

M32.C3.L-data.V1.U11: and what triggered it (0199) — each trigger's kind and what moved, any object
with those two, or a mapping; a retry replaces them with the rest.
"""
from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert import store as R

pytestmark = pytest.mark.pg

ORG, OTHER = "org_s12_review_store", "org_s12_review_store_other"
FILE = "node_kestrel"
AT = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
REVIEW = ExpertReview.from_mapping({
    "facts": [{"claim": "Rahul asked for the data room", "evidence": ["evt_1"]}],
    "frames": {"primary": "a fund doing diligence", "rivals": ["a polite stall"]},
    "expected_vs_actual": {"stage": "diligence", "expected": "the data room shared",
                           "actual": "not shared"},
    "scenarios": {"do_nothing": "the round slows", "act": "diligence moves",
                  "best": "a term sheet", "worst": "a pass", "signals_to_watch": ["a call request"]},
    "appraisal": {"stakes": "high", "urgency": "medium", "reversibility": "reversible",
                  "reasons": ["the fund asked"]},
    "mode": "act", "next_move": {"who": "the founder", "what": "share the data room",
                                 "for_whom": "Rahul", "by_when": "2026-10-12"},
    "wait_or_stop": "if no reply in a week, ask once", "done_when": "the room is shared"})
INPUTS = {"file_id": FILE, "events": ["evt_1"], "booked": [], "whose_move": "ours", "quiet": ">=1"}
TRIGGERS = (("new_evidence", "new since the last review: evt_1"),)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                      {"o": org, "e": f"{org}@example.test"})
    yield eng
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("delete from orgs where id = :o"), {"o": org})


def _write(c, fp: str, *, status=R.VALID, reason=None, review=REVIEW, at=AT, org=ORG, cost=26_100,
           inputs=INPUTS, triggers=None, checked=None):
    said = [{"kind": k, "says": s} for k, s in TRIGGERS] if triggers is None else list(triggers)
    return R.write_review(c, org_id=org, file_id=FILE, fingerprint=fp, model="claude-sonnet-5",
                          prompt_version="expert-review.v1", dossier_digest="sha256:d", status=status,
                          reason=reason, review=review, input_tokens=9000, output_tokens=900,
                          cost_micro_usd=cost, at=at, inputs=inputs, triggers=said, checked=checked)


def test_a_valid_review_reads_back_as_the_review_that_was_written(engine):
    with engine.begin() as c:
        assert _write(c, "ffp-1") is True
    with engine.connect() as c:
        stored = R.read_review(c, ORG, FILE, "ffp-1")
        latest = R.latest_valid(c, ORG, FILE)
    assert stored == R.StoredReview(
        file_id=FILE, fingerprint="ffp-1", model="claude-sonnet-5", prompt_version="expert-review.v1",
        dossier_digest="sha256:d", status=R.VALID, reason=None, review=REVIEW, raw=REVIEW.as_mapping(),
        input_tokens=9000, output_tokens=900, cost_micro_usd=26_100, reviewed_at=AT, inputs=INPUTS,
        triggers=TRIGGERS)
    assert latest == stored


def test_once_per_fingerprint_a_second_write_is_refused(engine):
    with engine.begin() as c:
        assert _write(c, "ffp-1") is True
        assert _write(c, "ffp-1", status=R.REFUSED, reason="unknown_evidence", review=None) is False
    with engine.connect() as c:
        assert R.read_review(c, ORG, FILE, "ffp-1").status == R.VALID


@pytest.mark.parametrize("first", [R.REFUSED, R.TRUNCATED])
def test_a_refusal_stands_until_the_file_moves(engine, first):
    with engine.begin() as c:
        assert _write(c, "ffp-1", status=first, reason=f"why {first}", review=None) is True
        assert _write(c, "ffp-1") is False
    with engine.connect() as c:
        assert R.read_review(c, ORG, FILE, "ffp-1").status == first
        assert R.reviewed(c, ORG, FILE, "ffp-1") is True
        assert R.latest_valid(c, ORG, FILE) is None
        no_words = c.execute(text("select review is null from expert_reviews "
                                  "where org_id = :o and fingerprint = 'ffp-1'"), {"o": ORG}).scalar()
    assert no_words is True                       # SQL null, never a JSON null that reads as words


@pytest.mark.parametrize("first", [R.FAILED, R.OVER_BUDGET])
def test_a_failed_or_carried_review_is_retried_and_replaced(engine, first):
    with engine.begin() as c:
        assert R.write_review(c, org_id=ORG, file_id=FILE, fingerprint="ffp-1", model="m-before",
                              prompt_version="pv-before", dossier_digest="sha256:before", status=first,
                              reason=f"why {first}", review=None, input_tokens=1, output_tokens=2,
                              cost_micro_usd=3, at=AT, inputs={"events": ["evt_before"]},
                              triggers=[{"kind": "first_look", "says": "never judged"}]) is True
    with engine.connect() as c:
        assert R.reviewed(c, ORG, FILE, "ffp-1") is False             # the pass asks again
    with engine.begin() as c:
        assert _write(c, "ffp-1", at=AT + timedelta(days=1)) is True
        _write(c, "ffp-2", at=AT + timedelta(days=1))                 # the same answer, never retried
    with engine.connect() as c:
        stored = R.read_review(c, ORG, FILE, "ffp-1")
        fresh = R.read_review(c, ORG, FILE, "ffp-2")
        assert R.reviewed(c, ORG, FILE, "ffp-1") is True
    assert replace(stored, fingerprint="ffp-2") == fresh            # every column is the retry's
    assert stored.inputs == INPUTS                                  # what the file was, the retry's too
    assert stored.triggers == TRIGGERS                              # and what triggered it
    assert stored.status == R.VALID and stored.review == REVIEW


def test_a_refused_rows_words_are_kept_as_data_never_as_a_review(engine):
    with engine.begin() as c:
        _write(c, "ffp-1", status=R.REFUSED, reason="number_not_in_dossier: 32", review=REVIEW)
        _write(c, "ffp-2", status=R.REFUSED, reason="unknown_evidence: evt_9",
               review={"mode": "act", "facts": [{"claim": "x", "evidence": ["evt_9"]}]})
    with engine.connect() as c:
        stored = R.read_review(c, ORG, FILE, "ffp-1")
        loose = R.read_review(c, ORG, FILE, "ffp-2")
    assert stored.review is None and stored.raw == REVIEW.as_mapping()
    assert stored.reason == "number_not_in_dossier: 32"
    assert loose.review is None and loose.raw == {"mode": "act",
                                                  "facts": [{"claim": "x", "evidence": ["evt_9"]}]}


def test_the_latest_valid_review_of_a_file_skips_every_other_status(engine):
    with engine.begin() as c:
        _write(c, "ffp-1", at=AT)
        _write(c, "ffp-2", at=AT + timedelta(days=1))
        _write(c, "ffp-3", status=R.REFUSED, reason="unknown_evidence", review=None,
               at=AT + timedelta(days=2))
        _write(c, "ffp-4", org=OTHER, at=AT + timedelta(days=3))
    with engine.connect() as c:
        latest = R.latest_valid(c, ORG, FILE)
        assert R.latest_valid(c, ORG, "node_nobody") is None
        assert R.read_review(c, ORG, FILE, "ffp-4") is None              # another tenant's
        assert R.reviewed(c, ORG, FILE, "ffp-9") is False
    assert latest.fingerprint == "ffp-2"


def test_two_valid_reviews_at_one_instant_read_the_same_way_every_time(engine):
    with engine.begin() as c:
        _write(c, "ffp-b", at=AT)
        _write(c, "ffp-a", at=AT)
        _write(c, "ffp-c", at=AT)
    with engine.connect() as c:
        assert R.latest_valid(c, ORG, FILE).fingerprint == "ffp-c"


def test_a_write_says_what_it_is_or_is_refused(engine):
    with engine.begin() as c:
        with pytest.raises(ValueError, match="status"):
            _write(c, "ffp-1", status="skipped")
        with pytest.raises(ValueError, match="reason"):
            _write(c, "ffp-1", status=R.TRUNCATED, reason=None, review=None)
        with pytest.raises(ValueError, match="review"):
            _write(c, "ffp-1", review=None)
        with pytest.raises(ValueError, match="review"):
            _write(c, "ffp-1", review=REVIEW.as_mapping())         # a valid row is a parsed review
        with pytest.raises(ValueError, match="reason"):
            _write(c, "ffp-1", status=R.FAILED, reason="  ", review=None)
        with pytest.raises(ValueError, match="inputs"):
            _write(c, "ffp-1", inputs=None)                          # what the file was, always
        with pytest.raises(ValueError, match="inputs"):
            _write(c, "ffp-1", inputs=["evt_1"])
        with pytest.raises(ValueError, match="trigger"):
            _write(c, "ffp-1", triggers=[{"kind": "new_evidence"}])     # what moved, always
        with pytest.raises(ValueError, match="trigger"):
            _write(c, "ffp-1", triggers=[{"kind": " ", "says": "x"}])
        with pytest.raises(ValueError, match="trigger"):
            _write(c, "ffp-1", triggers=["new_evidence"])
    assert R.STANDING + R.RETRYABLE == R.STATUSES


def test_a_review_keeps_what_triggered_it_from_any_trigger_shaped_thing(engine):
    """A `reason/expert/triggers.Trigger`, or anything with its kind and what moved, or a mapping."""
    with engine.begin() as c:
        _write(c, "ffp-1", triggers=[SimpleNamespace(kind="date_closing_in", says="the next meeting: "
                                                                                  "<=168 → <=72"),
                                     {"kind": "founder_asked", "says": "the founder asked about it"}])
        _write(c, "ffp-2", triggers=())
    with engine.connect() as c:
        assert R.read_review(c, ORG, FILE, "ffp-1").triggers == (
            ("date_closing_in", "the next meeting: <=168 → <=72"),
            ("founder_asked", "the founder asked about it"))
        assert R.read_review(c, ORG, FILE, "ffp-2").triggers == ()
        assert R.latest_standing(c, ORG, FILE).triggers is not None


def test_a_row_from_before_0198_and_0199_reads_as_not_kept_never_as_empty(engine):
    """`triggers.triggers_for` reads a review whose inputs were not kept as a first look: None is
    "not kept", and an empty list would say "nothing" — two different answers."""
    with engine.begin() as c:
        _write(c, "ffp-1")
        c.execute(text("update expert_reviews set inputs = null, triggers = null "
                       "where org_id = :o and fingerprint = 'ffp-1'"), {"o": ORG})
    with engine.connect() as c:
        old = R.read_review(c, ORG, FILE, "ffp-1")
    assert old.inputs is None and old.triggers is None


def test_the_latest_standing_review_is_what_the_last_judgment_saw(engine):
    """Valid, refused or truncated — whichever was last; a failed or carried row judged nothing."""
    with engine.begin() as c:
        _write(c, "ffp-1", at=AT, inputs={"events": ["evt_1"]})
        _write(c, "ffp-2", status=R.REFUSED, reason="unknown_evidence", review=None,
               at=AT + timedelta(days=1), inputs={"events": ["evt_1", "evt_2"]})
        _write(c, "ffp-3", status=R.FAILED, reason="model_call_raised", review=None,
               at=AT + timedelta(days=2), inputs={"events": ["evt_1", "evt_2", "evt_3"]})
        _write(c, "ffp-4", status=R.OVER_BUDGET, reason="the day's $2 was spent", review=None,
               at=AT + timedelta(days=3), inputs={"events": ["evt_4"]})
        _write(c, "ffp-5", org=OTHER, at=AT + timedelta(days=4))
    with engine.connect() as c:
        last = R.latest_standing(c, ORG, FILE)
        assert R.latest_standing(c, ORG, "node_nobody") is None
        assert R.latest_valid(c, ORG, FILE).fingerprint == "ffp-1"
    assert (last.fingerprint, last.status, last.inputs) == ("ffp-2", R.REFUSED,
                                                           {"events": ["evt_1", "evt_2"]})
    with engine.begin() as c:
        _write(c, "ffp-6", status=R.TRUNCATED, reason="truncated_at_the_token_ceiling", review=None,
               at=AT + timedelta(days=5))
    with engine.connect() as c:
        assert R.latest_standing(c, ORG, FILE).status == R.TRUNCATED     # a cut answer stands too
    with engine.begin() as c:
        _write(c, "ffp-7", at=AT + timedelta(days=5))
    with engine.connect() as c:
        assert R.latest_standing(c, ORG, FILE).fingerprint == "ffp-7"   # a tie: the newest fingerprint


# ── STEP-13 · M35.C1.L-contract.V1.U03: a valid review keeps its check ─────────────────────────
def _checked(fate="shown", headline="share the data room"):
    from genios_engine.contracts import claim_check as C
    return C.CheckedReview(
        verdicts=(C.LineVerdict("fact:1", C.KEPT),), fate=fate, cited=("evt_1",),
        words=C.CardWords(headline=headline, situation="a fund doing diligence",
                          done_when="the room is shared", draft=None, to=None, evidence=("evt_1",)))


def test_a_valid_reviews_check_reads_back_as_it_was_written(engine):
    with engine.begin() as c:
        assert _write(c, "ffp-1", checked=_checked()) is True
    with engine.connect() as c:
        stored = R.read_review(c, ORG, FILE, "ffp-1")
    assert stored.checked == _checked() and stored.review == REVIEW


def test_a_check_is_written_onto_the_standing_valid_row_alone(engine):
    with engine.begin() as c:
        _write(c, "ffp-1")
        _write(c, "ffp-2", status=R.REFUSED, reason="nothing_stands: fact:1 uncited", review=None)
    with engine.begin() as c:
        assert R.write_check(c, org_id=ORG, file_id=FILE, fingerprint="ffp-1",
                             checked=_checked(headline="share the room")) is True
        assert R.write_check(c, org_id=ORG, file_id=FILE, fingerprint="ffp-2", checked=_checked()) is False, \
            "a refusal has no review to check"
        assert R.write_check(c, org_id=ORG, file_id=FILE, fingerprint="ffp-none", checked=_checked()) is False
    with engine.connect() as c:
        one, two = R.read_review(c, ORG, FILE, "ffp-1"), R.read_review(c, ORG, FILE, "ffp-2")
    assert one.checked.words.headline == "share the room" and one.review == REVIEW
    assert two.checked is None


def test_a_check_rides_only_on_a_valid_row(engine):
    with pytest.raises(ValueError, match="no review to check"):
        with engine.begin() as c:
            _write(c, "ffp-1", status=R.REFUSED, reason="uncited_fact", review=None, checked=_checked())


def test_a_row_from_before_0200_reads_with_no_check(engine):
    with engine.begin() as c:
        _write(c, "ffp-1")
    with engine.connect() as c:
        assert R.read_review(c, ORG, FILE, "ffp-1").checked is None


def test_a_retried_review_that_succeeds_keeps_its_check(engine):
    """A failed row's retry may replace it (`RETRYABLE`): the valid review that replaces it carries its
    check, never the failed row's none."""
    with engine.begin() as c:
        _write(c, "ffp-1", status=R.FAILED, reason="the call failed", review=None)
    with engine.begin() as c:
        assert _write(c, "ffp-1", checked=_checked()) is True
    with engine.connect() as c:
        assert R.read_review(c, ORG, FILE, "ffp-1").checked == _checked()
