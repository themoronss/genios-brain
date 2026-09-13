"""Every tenant's L1 → L4 lane is switched on without anyone running a script.

    pytest tests/platform/test_every_tenant_is_switched_on.py -q

MEASURED ON PRODUCTION 2026-09-13: a tenant signed up, connected Gmail, synced two months and got
14 facts from 1,665 events, because `l1_semantic_activation` had no row for it and nothing in the
product ever wrote one. `make_tenant_live` is that writer. It must switch a new tenant on in wave
order, never overrule an operator who switched something off, and never fail a caller.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from genios_engine.platform import intelligence_onboarding as onb
from genios_engine.platform.intelligence_onboarding import (L4_DEFAULT_FEATURES, PROVISIONED_BY,
                                                            Provisioned, make_tenant_live)

pytestmark = pytest.mark.unit

ORG = "org_new"


class _State:
    """The four switch tables, in memory. `order` records every write as it happens."""

    def __init__(self, *, l1=None, l2=None, l4=None, fail=()):
        self.l1, self.l2, self.l4 = l1, l2, dict(l4 or {})
        self.order: list[str] = []
        self.fail = set(fail)

    def _maybe_fail(self, name):
        if name in self.fail:
            raise RuntimeError(f"{name} down")

    def get_l1(self, engine, org_id):
        return self.l1

    def activate_l1(self, engine, org_id, *, by, notes=None, **kw):
        self._maybe_fail("l1.semantic")
        self.order.append("l1.semantic")
        self.l1 = SimpleNamespace(by=by)

    def get_l2(self, engine, org_id):
        return self.l2

    def activate_l2(self, engine, org_id, *, switch, by, notes=None, **kw):
        self._maybe_fail(f"l2.{switch}")
        self.order.append(f"l2.{switch}")

    def get_l4(self, engine, org_id, feature):
        return self.l4.get(feature)

    def activate_l4(self, engine, org_id, *, feature, by, notes=None, **kw):
        self._maybe_fail(f"l4.{feature}")
        self.order.append(f"l4.{feature}")
        self.l4[feature] = SimpleNamespace(by=by)


def _l2_record(*, analytic_on=None, analytic_off=None, patterns_on=None, patterns_off=None):
    from genios_engine.platform.l2_activation import L2Activation
    return L2Activation(org_id=ORG, enabled_by="harsh", analytic_enabled_at=analytic_on,
                        analytic_disabled_at=analytic_off, patterns_enabled_at=patterns_on,
                        patterns_disabled_at=patterns_off)


@pytest.fixture
def state(monkeypatch):
    s = _State()
    import genios_engine.platform.activation as l1
    import genios_engine.platform.l2_activation as l2
    import genios_engine.platform.l4_activation as l4
    monkeypatch.setattr(l1, "get_semantic_activation", lambda e, o: s.get_l1(e, o))
    monkeypatch.setattr(l1, "activate_semantic", s.activate_l1)
    monkeypatch.setattr(l2, "get_l2_activation", lambda e, o: s.get_l2(e, o))
    monkeypatch.setattr(l2, "activate", s.activate_l2)
    monkeypatch.setattr(l4, "get_l4_activation", s.get_l4)
    monkeypatch.setattr(l4, "activate", s.activate_l4)
    provisioned: list[str] = []

    def _provision(engine, org_id, *, by=PROVISIONED_BY):
        provisioned.append(org_id)
        s.order.append("l3.provision")
        return Provisioned(packs=True, activated=("admin", "sales"))

    monkeypatch.setattr(onb, "provision_intelligence", _provision)
    s.provisioned = provisioned
    return s


def test_a_new_tenant_is_switched_on_in_wave_order(state):
    out = make_tenant_live(object(), ORG)

    assert state.order == (["l1.semantic", "l2.analytic", "l2.patterns", "l3.provision"]
                           + [f"l4.{f}" for f in L4_DEFAULT_FEATURES])
    assert out.errors == ()
    assert out.changed is True
    assert state.l1.by == PROVISIONED_BY


def test_a_second_run_writes_nothing(state):
    make_tenant_live(object(), ORG)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    state.l2 = _l2_record(analytic_on=now, patterns_on=now)
    state.order.clear()

    out = make_tenant_live(object(), ORG)

    assert state.order == ["l3.provision"]
    assert out.switched_on == ()


def test_l1_an_operator_switched_off_stays_off(state):
    """`get_semantic_activation` returns a record for a tenant stamped OFF. That is a decision."""
    state.l1 = SimpleNamespace(live=False)

    out = make_tenant_live(object(), ORG)

    assert "l1.semantic" not in state.order
    assert "l1.semantic" not in out.switched_on


def test_one_l2_switch_switched_off_leaves_the_other_free(state):
    from datetime import datetime, timezone
    state.l2 = _l2_record(analytic_on=datetime.now(timezone.utc),
                          analytic_off=datetime.now(timezone.utc))

    make_tenant_live(object(), ORG)

    assert "l2.analytic" not in state.order
    assert "l2.patterns" in state.order


def test_one_switch_failing_does_not_stop_the_rest(state):
    state.fail = {"l2.analytic"}

    out = make_tenant_live(object(), ORG)

    assert "l1.semantic" in state.order and "l4.brief" in state.order
    assert len(out.errors) == 1 and out.errors[0].startswith("l2.analytic")


def test_no_engine_is_an_error_not_an_exception():
    out = make_tenant_live(None, ORG)

    assert out.errors and out.changed is False
