"""STEP-14 · a discrepancy names its field in words — "Which is right? Maria Exconde's role", never `party.role`.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_a_discrepancy_names_its_field_in_words.py -q

Tree `yc2_w27_s14` M43.C4.L-logic.V0.U04 (`reason/verify/passes.compose`; STEP-14 §4, §8.4 item 6, s14-F10). Production
showed *"Which is right? Maria Exconde: party.role"* — the verify pass printed the graph's field name on the
founder's card. The field is said in words from ONE closed map (`FIELD_WORDS`); a field the map does not name is
not asked at all — no card, counted (`unnamed_field`), the discrepancy left open for the list to show.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.reason.verify import passes as P
from tests.test_p4_verify_unit import _row

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


def test_a_discrepancy_on_a_named_field_says_it_in_words():
    sit = P.compose(_row(field="party.role", display_name="Maria Exconde", node_type="person"), seat_id="seat_owner")
    assert sit["headline"] == "Which is right? Maria Exconde's role"
    assert "party.role" not in sit["headline"] + sit["body"]
    status = P.compose(_row(), seat_id="seat_owner")
    assert status["headline"] == "Which is right? Acme — deal's deal status"


def test_a_field_the_map_does_not_name_is_not_asked():
    assert P.compose(_row(field="derived.momentum"), seat_id="seat_owner") is None
    assert P.compose(_row(field="party.zodiac_sign"), seat_id="seat_owner") is None


def test_every_word_is_a_founders_word():
    """The map is closed and says no field name: every value reads as words, none carries a dot or an underscore."""
    assert P.FIELD_WORDS and all("." not in w and "_" not in w for w in P.FIELD_WORDS.values())
    assert P.FIELD_WORDS["party.role"] == "role"


class _Conn:
    def execute(self, *_a, **_k):
        return SimpleNamespace(rowcount=0)


class _Engine:
    @contextmanager
    def begin(self):
        yield _Conn()

    @contextmanager
    def connect(self):
        yield _Conn()


def test_the_pass_counts_what_it_could_not_ask_and_asks_the_rest(monkeypatch):
    rows = [_row(id="disc_named", field="party.role", display_name="Maria Exconde"),
            _row(id="disc_unnamed", field="derived.momentum")]
    monkeypatch.setattr(P, "watermark", lambda *_a: NOW)
    monkeypatch.setattr(P.V, "rows", lambda *_a, **_k: rows)
    monkeypatch.setattr(P, "_active_seats", lambda *_a: {})
    monkeypatch.setattr(P, "recipient", lambda *_a: "seat_owner")
    advanced = []
    monkeypatch.setattr(P, "advance", lambda _c, _o, _p, to: advanced.append(to))
    sent, counts = [], {}
    emitted = P.run_verify(_Engine(), None, "org_1", now=NOW, counts=counts,
                           emit=lambda *_a, **kw: sent.append(kw) or ("card", "moment"))
    assert emitted == 1 and [s["key"] for s in sent] == ["discrepancy:disc_named"]
    assert counts == {"unnamed_field": 1}
    assert advanced == [rows[-1].updated_at], "the watermark moves past both: the unnamed one is not retried every pass"
