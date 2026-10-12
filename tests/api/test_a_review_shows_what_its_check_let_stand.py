"""STEP-13 · one file shows what the expert's CHECK let stand — never the review's raw words.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/api/test_a_review_shows_what_its_check_let_stand.py

Tree `yc2_w27_s13` M35.C3.L-interface.V3.U07 (`api/workstream_routes._review_as_dict`; crosscheck X28). `GET
/v1/workstreams/{file_id}` served `review.as_mapping()` — every word the model wrote, before or without its check,
and still under "valid" after a re-check refused it. "Nothing the expert says reaches the founder unchecked": a
review now shows `says` — the checked card words, only when a check ran and did not refuse — and `check` — its
fate, why, the question it asked and each line's verdict. An unchecked review shows nothing it said; a refused
one shows its check and nothing it said; the raw words are never served.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.contracts import claim_check as C
from tests.api.test_a_file_is_readable import ADMIN, NOW, ORG, _client, _file_id
from tests.api.test_a_file_is_readable import store  # noqa: F401 — the fixture, reused
from tests.api.test_a_file_shows_its_review import _write
from tests.reason.expert.checks import as_written
from tests.reason.expert.test_the_review_store import REVIEW

pytestmark = pytest.mark.pg


def _valid(monkeypatch, store, file_id):
    answer = _client(monkeypatch, store, ADMIN).get(f"/v1/workstreams/{file_id}")
    assert answer.status_code == 200
    return answer.json()["review"]["valid"]


def _held() -> C.CheckedReview:
    shown = as_written(REVIEW)
    return C.CheckedReview(verdicts=(C.LineVerdict("fact:1", C.DROPPED, C.MISQUOTED, "x"),), fate=C.HELD,
                           cited=(), question="Is it so?", because="misquoted (fact 1)",
                           words=C.CardWords(None, shown.words.situation, shown.words.done_when, None, None))


def test_a_checked_review_shows_its_checked_words_and_its_check(monkeypatch, store):
    file_id = _file_id(store, ORG)
    _write(store, ORG, file_id, "ffp-1", checked=_held())
    valid = _valid(monkeypatch, store, file_id)
    assert valid["says"] == _held().words.as_mapping(), "the held move is not among what it says"
    assert valid["check"]["fate"] == C.HELD and valid["check"]["question"] == "Is it so?"
    assert valid["check"]["verdicts"] == [{"line": "fact:1", "verdict": "dropped", "reason": "misquoted",
                                           "detail": "x"}]
    assert "review" not in valid, "the raw words are never served"


def test_an_unchecked_review_shows_nothing_it_said(monkeypatch, store):
    file_id = _file_id(store, ORG)
    _write(store, ORG, file_id, "ffp-1")
    valid = _valid(monkeypatch, store, file_id)
    assert (valid["says"], valid["check"]) == (None, None) and valid["status"] == "valid"


def test_a_review_its_check_refused_shows_its_check_and_nothing_it_said(monkeypatch, store):
    file_id = _file_id(store, ORG)
    refused = C.CheckedReview(verdicts=(C.LineVerdict("fact:1", C.DROPPED, C.UNKNOWN_EVIDENCE, "evt_x"),),
                              fate=C.REFUSED, cited=(), because=C.NOTHING_STANDS,
                              words=C.CardWords(None, None, None, None, None))
    _write(store, ORG, file_id, "ffp-1", checked=refused, at=NOW - timedelta(hours=1))
    valid = _valid(monkeypatch, store, file_id)
    assert valid["says"] is None and valid["check"]["fate"] == C.REFUSED
