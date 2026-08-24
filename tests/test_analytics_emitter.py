"""PostHog emitter (ANALYTICS_V3_PLAN Phase 4).

The emitter's job is to be invisible: it must never slow, break, or alter the action it observes,
and it must never leak content. Those are the properties tested here — plus the one that decides
whether the dashboards can be trusted at all: PostHog and the admin console must derive a person's
plan, paying status and MRR from the same rules, or the two surfaces will quote different numbers
for the same account.
"""
from __future__ import annotations

import queue

import pytest

from genios_engine.platform import analytics as A
from genios_engine.platform.config import get_settings


@pytest.fixture(autouse=True)
def _clean_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _drain_queue():
    out = []
    while True:
        try:
            out.append(A._q.get_nowait())
            A._q.task_done()
        except queue.Empty:
            return out


@pytest.fixture()
def emitter_on(monkeypatch):
    """Enable the emitter but never let it reach the network: the worker thread is stubbed out so
    queued payloads stay inspectable."""
    monkeypatch.setenv("GENIOS_POSTHOG_API_KEY", "phc_test")
    get_settings.cache_clear()
    monkeypatch.setattr(A, "_ensure_worker", lambda: None)
    _drain_queue()
    yield
    _drain_queue()


def test_disabled_without_a_key_emits_nothing(monkeypatch):
    """The default must be off: a self-hosted or dev deployment should never phone home."""
    monkeypatch.setenv("GENIOS_POSTHOG_API_KEY", "")
    get_settings.cache_clear()
    A.capture("org_1", "user_logged_in", {"x": 1})
    assert _drain_queue() == []


def test_event_carries_the_org_as_distinct_id(emitter_on):
    A.capture("org_7", "intelligence_query", {"module_id": "sales", "cached": False})
    [payload] = _drain_queue()
    assert payload["distinct_id"] == "org_7"          # one account = one company, as in the console
    assert payload["event"] == "intelligence_query"
    assert payload["properties"]["module_id"] == "sales"
    assert payload["api_key"] == "phc_test"


def test_every_event_is_stamped_with_its_environment(emitter_on):
    """Local and production share one PostHog project. Without an env stamp a dev restart is
    indistinguishable from real usage, and no filter can separate them afterwards."""
    A.capture("org_7", "api_call", {"path": "/x"})
    [payload] = _drain_queue()
    assert payload["properties"]["env"] == get_settings().env
    assert payload["properties"]["emitter"] == "engine"


def test_person_properties_ride_along_as_set(emitter_on):
    A.capture("org_7", "user_logged_in", None, person={"plan": "startup", "is_internal": False})
    [payload] = _drain_queue()
    assert payload["properties"]["$set"] == {"plan": "startup", "is_internal": False}


def test_a_full_queue_drops_events_instead_of_blocking(monkeypatch):
    """If PostHog stalls, the queue fills. The request path must keep running at full speed and the
    loss must be counted, not hidden — analytics is never worth a blocked customer request."""
    monkeypatch.setenv("GENIOS_POSTHOG_API_KEY", "phc_test")
    get_settings.cache_clear()
    monkeypatch.setattr(A, "_ensure_worker", lambda: None)
    monkeypatch.setattr(A, "_q", queue.Queue(maxsize=2))
    before = A._dropped
    for _ in range(10):
        A.capture("org_1", "api_call", {"path": "/x"})       # must not raise
    assert A._q.qsize() == 2
    assert A._dropped > before


def test_capture_never_raises_even_when_serialisation_would(emitter_on):
    """A bad property must lose one event, never break the action that produced it."""
    class Unserialisable:
        def __repr__(self):                                  # json default=str calls this
            raise RuntimeError("boom")

    A.capture("org_7", "weird_event", {"bad": Unserialisable()})   # queues fine; failure is at POST
    payloads = _drain_queue()
    assert len(payloads) == 1
    # the POST path swallows it too
    A._post(payloads[0])


def test_posthog_and_console_agree_on_mrr(monkeypatch):
    """The single most damaging inconsistency would be PostHog reporting revenue the console does
    not. person_props() prices a plan ONLY when a settled subscription exists, exactly like
    /admin/money."""
    from genios_engine.platform import metrics as M

    class _Row:
        subscription_tier = "startup"
        plan_status = "active"
        is_internal = False
        created_at = None
        activated_at = None
        paid = 0                                             # assigned plan, nothing settled

    class _Conn:
        def execute(self, *a, **k):
            class R:
                @staticmethod
                def first():
                    return _Row()
            return R()

    props = A.person_props(_Conn(), "org_1")
    assert props["mrr_inr"] == 0.0 and props["is_paying"] is False

    _Row.paid = 1                                            # money actually arrived
    props = A.person_props(_Conn(), "org_1")
    assert props["mrr_inr"] == M.mrr_inr("startup", "active") == 25_000.0
    assert props["is_paying"] is True


def test_person_props_degrade_to_empty_on_a_database_error():
    class _Broken:
        def execute(self, *a, **k):
            raise RuntimeError("db down")

    assert A.person_props(_Broken(), "org_1") == {}


def test_no_message_content_is_ever_emitted():
    """Structural guard: the properties we send are counts, ids and money. If someone later adds a
    subject line or a question body to an event, this list is where it has to be argued for."""
    import inspect
    import re

    from genios_engine.api import intelligence_routes, auth_routes, billing_routes
    from genios_engine.capture.acquire import sync_runner

    banned = re.compile(r'"(question|body|subject|snippet|content|text|email_body)"\s*:')
    for module in (intelligence_routes, auth_routes, billing_routes, sync_runner):
        src = inspect.getsource(module)
        for block in re.findall(r"analytics\.capture[_a-z]*\((?:[^()]|\([^()]*\))*\)", src):
            assert not banned.search(block), f"content leaked into an event in {module.__name__}"
