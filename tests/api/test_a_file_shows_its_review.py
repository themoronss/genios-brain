"""STEP-12 · one file shows the expert's latest review of it, and its status — read only.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/api/test_a_file_shows_its_review.py -q

`GET /v1/workstreams/{file_id}` (tree `yc2_w27_s12` M32.C3.L-interface.V3.U05) carries `review`: the file's
latest STANDING review — what the expert last concluded, valid, refused or truncated, with its reason,
what triggered it, the model, the prompt version and its cost — and its latest VALID review, the one a
decision may read. A failed or carried attempt judged nothing and is not shown here (the health check
counts those). A file never reviewed says so; another tenant's reviews never show; reading writes nothing.

RESTATED by STEP-13 (`yc2_w27_s13` M35.C3.L-interface.V3.U07, crosscheck X28): the route served the review's raw
words as "valid" — unchecked, and still "valid" after a re-check refused it. Now a review shows what its CHECK
let stand (`says`, the checked card words) and the check itself (`check`: fate, verdicts, the question asked);
the raw words are data, never shown — as a refused answer's always were. `tests/api/test_a_review_shows_what_its_check_let_stand.py`.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.reason.expert import store as R
from tests.api.test_a_file_is_readable import ADMIN, NOW, ORG, OTHER, _client, _file_id
from tests.api.test_a_file_is_readable import store  # noqa: F401 — the fixture, reused
from tests.reason.expert.test_the_review_store import REVIEW

pytestmark = pytest.mark.pg


def _write(store, org, file_id, fp, *, status=R.VALID, reason=None, review=REVIEW, at=NOW, checked=None):
    with store.engine.begin() as c:
        R.write_review(c, org_id=org, file_id=file_id, fingerprint=fp, model="claude-sonnet-5",
                       prompt_version="expert-review.v2", dossier_digest="sha256:d", status=status,
                       reason=reason, review=review, input_tokens=9000, output_tokens=900,
                       cost_micro_usd=27_000, at=at, inputs={"events": ["evt_1"]},
                       triggers=[{"kind": "first_look", "says": "never judged"}], checked=checked)


def _review(monkeypatch, store, file_id):
    answer = _client(monkeypatch, store, ADMIN).get(f"/v1/workstreams/{file_id}")
    assert answer.status_code == 200
    return answer.json()["review"]


def test_a_file_never_reviewed_says_so(monkeypatch, store):
    assert _review(monkeypatch, store, _file_id(store, ORG)) == {"latest": None, "valid": None}


def test_a_file_shows_its_latest_review_and_its_status(monkeypatch, store):
    file_id = _file_id(store, ORG)
    from tests.reason.expert.checks import as_written
    _write(store, ORG, file_id, "ffp-1", at=NOW - timedelta(days=2), checked=as_written(REVIEW))
    _write(store, ORG, file_id, "ffp-2", status=R.REFUSED, reason="number_not_in_dossier: 4317",
           review=REVIEW.as_mapping(), at=NOW - timedelta(days=1))   # its words kept as data
    review = _review(monkeypatch, store, file_id)
    latest, valid = review["latest"], review["valid"]
    assert (latest["fingerprint"], latest["status"], latest["reason"]) == (
        "ffp-2", "refused", "number_not_in_dossier: 4317")
    assert latest["says"] is None, "a refused answer's words are data, never shown as a review"
    assert latest["triggers"] == [{"kind": "first_look", "says": "never judged"}]
    assert (valid["fingerprint"], valid["status"]) == ("ffp-1", "valid")
    assert valid["says"] == as_written(REVIEW).words.as_mapping() and "review" not in valid
    assert (valid["model"], valid["prompt_version"], valid["cost_micro_usd"]) == (
        "claude-sonnet-5", "expert-review.v2", 27_000)
    assert valid["reviewed_at"] == (NOW - timedelta(days=2)).isoformat()


def test_a_failed_or_carried_attempt_is_not_the_files_review(monkeypatch, store):
    file_id = _file_id(store, ORG)
    _write(store, ORG, file_id, "ffp-1", at=NOW - timedelta(days=2))
    _write(store, ORG, file_id, "ffp-2", status=R.FAILED, reason="model_call_raised", review=None,
           at=NOW - timedelta(hours=1))
    review = _review(monkeypatch, store, file_id)
    assert review["latest"]["fingerprint"] == review["valid"]["fingerprint"] == "ffp-1"


def test_another_tenants_review_never_shows(monkeypatch, store):
    mine, theirs = _file_id(store, ORG), _file_id(store, OTHER)
    _write(store, OTHER, theirs, "ffp-theirs")
    _write(store, OTHER, mine, "ffp-under-my-file-id")           # the same id, another tenant's row
    assert _review(monkeypatch, store, mine) == {"latest": None, "valid": None}


def test_reading_writes_no_review(monkeypatch, store):
    file_id = _file_id(store, ORG)
    _write(store, ORG, file_id, "ffp-1")

    def count():
        with store.engine.connect() as c:
            return c.execute(text("select count(*) from expert_reviews where org_id = :o"),
                             {"o": ORG}).scalar()
    before = count()
    _review(monkeypatch, store, file_id)
    assert count() == before == 1
