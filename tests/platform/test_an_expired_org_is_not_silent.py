"""GeniOS-012 U12-01 · a tenant whose plan expired is never silent again.

    PYTHONPATH=. pytest -q tests/platform/test_an_expired_org_is_not_silent.py
    (the end-to-end row is in tests/platform/test_daily_health_pg.py, which needs real Postgres)

Since 7075014c the scheduled sweep skips an EXPIRED tenant entirely (`api/routes._plan_expired`): no capture, no
reasoning, no cards — and nothing said so. The founder's own org stopped on 21 Sep and nobody noticed for a month.
The daily health row now carries the plan state at the end of its day and raises `plan_expired` for an expired
tenant, once a day by the row's own key.
"""
from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from types import SimpleNamespace

from genios_engine.platform import daily_health as DH

END = datetime(2026, 10, 23, 0, 0, tzinfo=timezone.utc)


class _Conn:
    def __init__(self, row):
        self.row = row

    def execute(self, statement, params):
        assert params == {"org": "org_x"}
        return SimpleNamespace(first=lambda: self.row)


def _org(status, expires_days, grace_days=None):
    return SimpleNamespace(plan_status=status,
                           plan_expires_at=END + timedelta(days=expires_days),
                           grace_until=(END + timedelta(days=grace_days)) if grace_days is not None else None)


def test_an_expired_plan_is_read_as_expired_at_the_end_of_the_day():
    plan = DH.plan_state(_Conn(_org("trial", -32)), "org_x", END)
    assert plan["state"] == "expired"


def test_grace_is_not_expired_and_active_is_active():
    assert DH.plan_state(_Conn(_org("trial", -2, grace_days=5)), "org_x", END)["state"] == "grace"
    assert DH.plan_state(_Conn(_org("active", 30)), "org_x", END)["state"] == "active"


def test_an_unreadable_org_is_unknown_never_a_guess():
    assert DH.plan_state(_Conn(None), "org_x", END)["state"] is None


def test_only_expired_raises_the_alert_and_it_says_what_stopped():
    assert DH.plan_alert({"state": "active"}) is None
    assert DH.plan_alert({"state": "grace"}) is None
    assert DH.plan_alert({"state": None}) is None
    alert = DH.plan_alert({"state": "expired", "plan_expires_at": END - timedelta(days=32), "grace_until": None})
    assert alert["kind"] == DH.ALERT_PLAN == "plan_expired"
    assert alert["plan_expires_at"].startswith("2026-09-21") and "skipped" in alert["says"]


def _measured(plan_state):
    return {"cards_by_day": [0] * 15, "lanes_by_day": [{}] * 15,
            "row": {"plan": {"state": plan_state, "plan_expires_at": None, "grace_until": None}}}


def test_the_row_alerts_include_plan_expired_for_an_expired_tenant_only():
    kinds = [a["kind"] for a in DH._alerts(_measured("expired"), None, DH.ceiling_bytes())]
    assert "plan_expired" in kinds
    assert "plan_expired" not in [a["kind"] for a in DH._alerts(_measured("active"), None, DH.ceiling_bytes())]
