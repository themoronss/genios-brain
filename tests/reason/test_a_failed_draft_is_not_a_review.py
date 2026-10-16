"""A week whose draft the model failed is a failed week, never a reviewed one.

    pytest tests/reason/test_a_failed_draft_is_not_a_review.py -q

⛔ `yc2_w27_s18` M50.C3.L-logic.V2.U07 (the 13 Oct audit's T5-7, s5t-F5). `run_company_brief_reviews`
claims a tenant's ISO week before it asks, so a draft the model failed — cut at its ceiling, not JSON,
unreachable — loses the week: the next try is next week. And it was counted `reviewed`, so the tick's
receipt said every tenant was reviewed while none had a draft. A model failure (`model:…`) and a raised
error are now `failed`, and only a draft that ran — proposing something or nothing — is `reviewed`.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from genios_engine.reason import brief_drafter as D
from genios_engine.reason import brief_review as R

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)
ORGS = ["org_ok", "org_cut", "org_junk", "org_quiet", "org_raised"]


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self, log):
        self.log = log

    def execute(self, statement, params=None):
        self.log.append((str(statement), params))
        if params is None:
            return _Rows([(org,) for org in ORGS])
        return _Rows([("claimed",)])


class _Engine:
    def __init__(self):
        self.log = []

    @contextmanager
    def connect(self):
        yield _Conn(self.log)

    @contextmanager
    def begin(self):
        yield _Conn(self.log)


def _draft(engine, org, llm, *, now, cost_sink=None, proposed_by="weekly"):
    if org == "org_ok":
        return D.DraftOutcome(proposed=2)
    if org == "org_cut":
        return D.DraftOutcome(skipped="model:truncated: the model hit max_tokens (max_tokens=4000)")
    if org == "org_junk":
        return D.DraftOutcome(skipped="model:unparseable JSON")
    if org == "org_quiet":
        return D.DraftOutcome(skipped="no_patterns")
    raise RuntimeError("transport down")


def test_a_model_failure_and_an_error_are_failed_weeks_never_reviews(monkeypatch):
    monkeypatch.setattr(D, "draft_company_brief", _draft)
    engine = _Engine()
    out = R.run_company_brief_reviews(engine, now=NOW, llm=object())
    assert (out["reviewed"], out["failed"], out["proposed"]) == (2, 3, 2), out
    finished = {p["o"]: p["out"] for s, p in engine.log if p and "out" in p}
    assert finished == {"org_ok": "proposed", "org_cut": finished["org_cut"], "org_quiet": "no_patterns",
                        "org_junk": "model:unparseable JSON", "org_raised": "error:RuntimeError"}
    assert finished["org_cut"].startswith("model:truncated")
