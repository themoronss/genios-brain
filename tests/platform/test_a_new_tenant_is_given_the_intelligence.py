"""A tenant that signed up and connected got the legacy lane and nothing else.

    pytest tests/platform/test_a_new_tenant_is_given_the_intelligence.py -q

MEASURED, READ-ONLY, ON PRODUCTION on 10 September 2026. An org registered at 14:46:38,
authorised Gmail at 14:47:53 and Google Calendar at 14:48:53. At 15:00 its entire footprint was
`tenant_packs 0 · l3_activation 0 · source_coverage 0 · config_snapshots 0 · source_events 0`,
and its `connections` row read `disconnected`.

`l3_activation` held exactly ONE row across the whole database — `(pilot org, admin)`,
`enabled_by: 'harsh'`, `notes: 'pilot run 2'`. Nothing in the product had ever written one. So
"the new account gets worse intelligence than the old one" was never a regression: it was the
only behaviour the product had, and the pilot was the exception a human had made by hand.

This file pins the three properties that fix has to keep: it must SWITCH A NEW TENANT ON, it
must not overrule an operator who already decided, and it must not be able to fail anybody's
signup, connect or sync.
"""

from __future__ import annotations

import pytest

from genios_engine.platform import corpus, intelligence_onboarding as onb
from genios_engine.platform.intelligence_onboarding import (
    PROVISIONED_BY,
    Provisioned,
    provision_intelligence,
)

pytestmark = pytest.mark.unit

ORG = "org_new"


# =============================================================================================
# The corpus decides which domains are ready — not this module, and not a Python literal.
# =============================================================================================
def test_every_shipped_corpus_declares_whether_it_is_ready():
    """`default_on` is required with a `why` a reviewer can argue with (the schema enforces the
    pair). All three shipped corpora declare themselves ready; the test is that the DECLARATION
    exists, not that the answer is yes."""
    declared = {d for d, _ in corpus.authored_domains()
                if isinstance((_ or {}).get("activation"), dict)}

    assert declared == set(corpus.authored_domain_ids())


def test_a_corpus_that_says_nothing_stays_off(monkeypatch):
    """THE SAFETY PROPERTY. Dropping a half-written domain into the tree must not start it
    talking to customers."""
    monkeypatch.setattr(corpus, "authored_domains",
                        lambda: iter([("half_written", {"identity": {"id": "half_written"}}),
                                      ("ready", {"activation": {"default_on": True,
                                                                "why": "x" * 30}})]))

    assert corpus.default_on_domains() == ("ready",)


def test_default_on_false_is_a_decision_and_is_honoured(monkeypatch):
    monkeypatch.setattr(corpus, "authored_domains",
                        lambda: iter([("paused", {"activation": {"default_on": False,
                                                                 "why": "x" * 30}})]))

    assert corpus.default_on_domains() == ()


# =============================================================================================
# What provisioning does, and what it refuses to do.
# =============================================================================================
class _Engine:
    """The narrowest thing `provision_intelligence` needs: one SELECT answering "does this
    tenant already hold a pack". `has_packs=True` is what every tenant looks like after the
    first call, and it is the path the 6-hourly sweep takes forever after."""

    def __init__(self, *, has_packs: bool = False, broken: bool = False):
        self.has_packs, self.broken = has_packs, broken
        self.queries: list[str] = []

    def connect(self):
        if self.broken:
            raise OSError("db down")
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        self.queries.append(str(statement))
        return self

    def first(self):
        return (1,) if self.has_packs else None


class _Recorder:
    """Stands in for the two writers. Neither is worth a real database here: what is under test
    is WHICH domains are asked for and which are skipped."""

    def __init__(self, existing=()):
        self.existing = set(existing)
        self.activated: list[tuple[str, str, str]] = []

    def get(self, engine, org_id, domain):
        return object() if domain in self.existing else None

    def activate(self, engine, org_id, *, domain, by, notes=None, **kw):
        self.activated.append((org_id, domain, by))
        return object()


@pytest.fixture
def wired(monkeypatch):
    rec = _Recorder()
    packed: list[str] = []
    monkeypatch.setattr(corpus, "authored_domains",
                        lambda: iter([(d, {"activation": {"default_on": True, "why": "x" * 30}})
                                      for d in ("admin", "sales")]))
    import genios_engine.platform.l3_activation as l3
    monkeypatch.setattr(l3, "L3_DOMAINS", ("admin", "sales", "customer_support"))
    monkeypatch.setattr(l3, "get_l3_activation", rec.get)
    monkeypatch.setattr(l3, "activate", rec.activate)
    import genios_engine.packs.wiring as w
    monkeypatch.setattr(w, "make_registry", lambda *a, **k: object())
    monkeypatch.setattr(w, "ensure_defaults", lambda reg, org: packed.append(org))
    return rec, packed


def test_a_new_tenant_gets_the_packs_and_every_ready_domain(wired):
    rec, packed = wired

    out = provision_intelligence(_Engine(), ORG)

    assert packed == [ORG]
    assert out.packs is True
    assert out.activated == ("admin", "sales")
    assert {by for _, _, by in rec.activated} == {PROVISIONED_BY}
    assert out.errors == ()


def test_a_second_run_changes_nothing(wired):
    """Idempotence is what lets this sit on the sweep. `_run_l2` calls it on every tick for
    every org; a call that re-activated would rewrite `enabled_at` and hand the J5 report a
    window starting today."""
    rec, _ = wired
    provision_intelligence(_Engine(), ORG)
    rec.existing.update({"admin", "sales"})

    out = provision_intelligence(_Engine(has_packs=True), ORG)

    assert out.activated == ()
    assert out.already_decided == ("admin", "sales")
    assert out.changed is False


def test_a_domain_an_operator_switched_off_stays_off(wired):
    """`get_l3_activation` returns a record for a pair that was STAMPED OFF, and this must read
    that as "already decided". Re-activating is described by `l3_activation.activate` as "a new
    pilot period with a new decision behind it" — a background pass is not a decision."""
    rec, _ = wired
    rec.existing.add("sales")

    out = provision_intelligence(_Engine(), ORG)

    assert out.activated == ("admin",)
    assert out.already_decided == ("sales",)
    assert [d for _, d, _ in rec.activated] == ["admin"]


def test_a_corpus_the_engine_does_not_know_is_named_not_raised(monkeypatch, wired):
    rec, _ = wired
    monkeypatch.setattr(corpus, "authored_domains",
                        lambda: iter([("admin", {"activation": {"default_on": True,
                                                                "why": "x" * 30}}),
                                      ("ghost", {"activation": {"default_on": True,
                                                                "why": "x" * 30}})]))

    out = provision_intelligence(_Engine(), ORG)

    assert out.activated == ("admin",)
    assert any("ghost" in e for e in out.errors)


# =============================================================================================
# It may never fail a caller. Signup, connect and sync all run through this.
# =============================================================================================
def test_a_pack_failure_does_not_stop_the_activation(monkeypatch, wired):
    rec, _ = wired
    import genios_engine.packs.wiring as w
    monkeypatch.setattr(w, "make_registry", lambda *a, **k: (_ for _ in ()).throw(OSError("db")))

    out = provision_intelligence(_Engine(), ORG)

    assert out.packs is False
    assert out.activated == ("admin", "sales")
    assert any(e.startswith("packs:") for e in out.errors)


def test_one_domain_failing_does_not_take_the_others(monkeypatch, wired):
    rec, _ = wired

    def boom(engine, org_id, *, domain, by, notes=None, **kw):
        if domain == "admin":
            raise RuntimeError("deadlock")
        return rec.activate(engine, org_id, domain=domain, by=by, notes=notes)

    import genios_engine.platform.l3_activation as l3
    monkeypatch.setattr(l3, "activate", boom)

    out = provision_intelligence(_Engine(), ORG)

    assert out.activated == ("sales",)
    assert any("admin" in e for e in out.errors)


def test_no_engine_is_an_error_not_an_exception():
    out = provision_intelligence(None, ORG)

    assert isinstance(out, Provisioned)
    assert out.changed is False
    assert out.errors


def test_a_total_outage_still_returns(monkeypatch, wired):
    assert onb.PROVISIONED_BY == PROVISIONED_BY      # the module imports and is addressable
    import genios_engine.platform.l3_activation as l3
    monkeypatch.setattr(l3, "get_l3_activation",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))

    out = provision_intelligence(_Engine(broken=True), ORG)

    assert out.packs is False
    assert out.activated == ()
    assert len(out.errors) == 3, "the pack read, and one per domain, each named"


def test_a_tenant_that_already_has_packs_never_builds_a_registry(wired, monkeypatch):
    """THE STEADY STATE. `_run_l2` calls this on every tick for every org; `make_registry`
    content-addresses every builtin and every authored corpus on construction, so the ordinary
    path must be one SELECT and nothing else."""
    import genios_engine.packs.wiring as w
    monkeypatch.setattr(w, "make_registry",
                        lambda *a, **k: pytest.fail("registry built for a packed tenant"))
    engine = _Engine(has_packs=True)

    out = provision_intelligence(engine, ORG)

    assert out.packs is True
    assert len(engine.queries) == 1
    assert "from tenant_packs" in engine.queries[0]
