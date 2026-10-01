"""Five days of total model failure, and nothing said so.

    pytest tests/platform/test_the_provider_refusing_calls_is_noticed.py -q

Between 25 and 30 September 2026 every model call in GeniOS failed — 2,062, then 1,836, then
2,993, then 3,152 in a day — all on one 400: *"You have reached your specified API usage limits."*
It had happened once before, 16–17 September, and recovered on its own. Neither occurrence
alerted.

`llm_costs.success` and `llm_costs.error` recorded every one of them. Nothing read the column.

⛔ WHAT MUST NOT BE "SIMPLIFIED" LATER, and each of these has its own test below:

  * a success CLEARS the streak — one answered call proves the provider is up;
  * OUR failures (`unparseable JSON`, `extraction_call_failed`) never raise this alert, and never
    clear the streak either — a bad prompt in the middle of an outage must not hide it;
  * the cooldown exists because the real outage produced three thousand failures a day, and an
    alert per failure is three thousand messages nobody reads;
  * `temperature is deprecated` is deliberately NOT a provider refusal — that one was ours, and it
    is fixed at the call site.
"""

from __future__ import annotations

import pytest

from genios_engine.platform import provider_health as ph

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean():
    ph._WATCH.reset()          # noqa: SLF001 — the counter this module exists to drive
    yield
    ph._WATCH.reset()          # noqa: SLF001


# =================================================================================================
# 1 · which errors are theirs
# =================================================================================================
@pytest.mark.parametrize("error", [
    "Error code: 400 - {'message': 'You have reached your specified API usage limits.'}",
    "rate_limit_error: too many requests",
    "Error code: 529 - overloaded_error",
    "insufficient_quota",
    "your credit balance is too low",
    "authentication_error: invalid x-api-key",
    "permission_error",
])
def test_provider_refusals_are_recognised(error):
    assert ph.is_provider_refusal(error) is True


@pytest.mark.parametrize("error", [
    None,
    "",
    "unparseable JSON",
    "extraction_call_failed",
    "extraction_parse_failed",
    "`temperature` is deprecated for this model.",
])
def test_our_own_failures_are_not_provider_refusals(error):
    """⛔ The last one matters most: `temperature` was OUR bug, fixed in
    `context/llm/client.NO_SAMPLING_PREFIXES`. Alerting on it would point the on-call at the
    provider's console for a defect in our own request."""
    assert ph.is_provider_refusal(error) is False


# =================================================================================================
# 2 · the streak
# =================================================================================================
def _fail(n: int, error: str = "You have reached your specified API usage limits") -> int:
    """Returns how many times the watch said "alert now" across n failures."""
    fired = 0
    for _ in range(n):
        if ph._WATCH.observe(success=False, error=error, model="m", purpose="p"):  # noqa: SLF001
            fired += 1
    return fired


def test_a_short_run_of_refusals_does_not_alert():
    """Transient 429s under retry must not page anybody."""
    assert _fail(ph.STREAK_TO_ALERT - 1) == 0


def test_the_streak_alerts_exactly_once():
    assert _fail(ph.STREAK_TO_ALERT) == 1


def test_the_cooldown_stops_three_thousand_messages():
    """The real outage produced 3,152 failures in one day."""
    assert _fail(ph.STREAK_TO_ALERT + 500) == 1


def test_one_success_clears_the_streak():
    _fail(ph.STREAK_TO_ALERT - 1)
    ph._WATCH.observe(success=True, error=None, model="m", purpose="p")   # noqa: SLF001
    assert ph._WATCH.streak == 0                                          # noqa: SLF001
    assert _fail(ph.STREAK_TO_ALERT - 1) == 0


def test_our_own_failure_neither_alerts_nor_clears():
    """⛔ A bad prompt landing in the middle of an outage must not reset the count and hide it."""
    _fail(ph.STREAK_TO_ALERT - 1)
    before = ph._WATCH.streak                                             # noqa: SLF001
    ph._WATCH.observe(success=False, error="unparseable JSON",            # noqa: SLF001
                      model="m", purpose="p")
    assert ph._WATCH.streak == before                                     # noqa: SLF001
    assert _fail(1) == 1, "the next real refusal should still reach the threshold"


# =================================================================================================
# 3 · the wire, and the contract that it cannot break its caller
# =================================================================================================
def test_observe_raises_the_alert_through_ops_alert(monkeypatch):
    sent: list[tuple] = []
    from genios_engine.platform import ops_alert
    monkeypatch.setattr(ops_alert, "notify", lambda event, **f: sent.append((event, f)))

    for _ in range(ph.STREAK_TO_ALERT):
        ph.observe(success=False, error="You have reached your specified API usage limits",
                   model="claude-haiku-4-5", purpose="l1_relevance", org_id="org_x")

    assert len(sent) == 1
    event, fields = sent[0]
    assert event == "provider_refusing_calls"
    assert fields["purpose"] == "l1_relevance"
    assert "spend limit" in fields["what_to_check"]


def test_observe_never_raises(monkeypatch):
    """It sits inside the accounting write the whole ledger depends on."""
    from genios_engine.platform import ops_alert

    def boom(*a, **k):
        raise RuntimeError("webhook down")

    monkeypatch.setattr(ops_alert, "notify", boom)
    for _ in range(ph.STREAK_TO_ALERT):
        ph.observe(success=False, error="rate_limit_error", model="m", purpose="p")


def test_record_cost_calls_the_watch(monkeypatch):
    """Both halves of the weld: if the call is dropped from `record_cost`, this fails."""
    import inspect

    from genios_engine.context.graph_store import GraphStore

    source = inspect.getsource(GraphStore.record_cost)
    assert "provider_health" in source, "record_cost no longer observes provider health"
    assert "observe(" in source
