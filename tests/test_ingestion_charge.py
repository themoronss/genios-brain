"""Reading the mailbox is billed by UNIT, in one row per sweep.

The rule: the customer pays for what entered their graph. An email the junk gate threw away did
work and gave them nothing, so it is free — which also means a noisy mailbox costs LESS than a
clean one of the same size, not more.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


class _Conn:
    def __init__(self, sink):
        self.sink = sink

    def execute(self, *_a, **_kw):
        return SimpleNamespace(first=lambda: None, scalar=lambda: 0)


class _Engine:
    def __init__(self, sink):
        self.sink = sink

    def begin(self):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            yield _Conn(self.sink)
        return _cm()


def _charge(monkeypatch, outcomes):
    from genios_engine.api import routes
    from genios_engine.platform import billing

    charged = []
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_Engine(charged)))
    monkeypatch.setattr(billing, "charge_units",
                        lambda _c, org, action, units, **kw: charged.append(
                            (org, action, units, kw)) or True)
    routes._charge_ingestion("org_1", {"outcomes": outcomes})
    return charged


def test_committed_messages_are_charged(monkeypatch):
    charged = _charge(monkeypatch, {"committed": 900, "committed_facts": 340})
    assert len(charged) == 1, "one row per sweep, not one per message"
    org, action, units, kw = charged[0]
    assert (org, action, units) == ("org_1", "message_read", 1_240)
    assert kw["bucket"] == "ingest"


def test_junk_is_not_charged(monkeypatch):
    """`parked_low_relevance` IS the junk gate's verdict. Charging for it would bill the customer
    for spam and make a dirty mailbox more expensive than a clean one."""
    assert _charge(monkeypatch, {"parked_low_relevance": 3_000}) == []


def test_failures_and_no_ops_are_not_charged(monkeypatch):
    assert _charge(monkeypatch, {"extract_failed": 40, "error": 12, "no_op": 500,
                                 "skipped_no_llm": 88, "retry_pending": 7}) == []


def test_a_sweep_that_read_nothing_files_no_row(monkeypatch):
    assert _charge(monkeypatch, {}) == []


def test_a_mixed_sweep_charges_only_what_entered_the_graph(monkeypatch):
    charged = _charge(monkeypatch, {
        "committed": 1_200, "committed_observation": 300,      # billable
        "parked_low_relevance": 2_500, "no_op": 90, "error": 3,  # free
    })
    assert charged[0][2] == 1_500


def test_the_charge_can_never_break_a_sync(monkeypatch):
    """Billing sits on the ingestion path. If it can raise, it can stop a customer's mail."""
    from genios_engine.api import routes
    from genios_engine.platform import billing

    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_Engine([])))
    monkeypatch.setattr(billing, "charge_units",
                        lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("db down")))
    routes._charge_ingestion("org_1", {"outcomes": {"committed": 10}})   # must not raise


def test_a_result_that_is_not_a_dict_is_ignored(monkeypatch):
    from genios_engine.api import routes
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_Engine([])))
    routes._charge_ingestion("org_1", None)                             # must not raise


def test_a_dirty_mailbox_costs_less_than_a_clean_one(monkeypatch):
    """5,000 messages either way; the one that is half spam is charged half as much."""
    clean = _charge(monkeypatch, {"committed": 5_000})[0][2]
    dirty = _charge(monkeypatch, {"committed": 2_500, "parked_low_relevance": 2_500})[0][2]
    assert dirty * 2 == clean
