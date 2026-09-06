"""L1.2.6-U1 · per-source cadence.

The unit under test is a lookup, so the only interesting assertions are about the DECISIONS
around it: that a source nobody tuned still gets a reviewed default rather than zero, that a
tenant-authored override cannot ask for a 5-second poll, and that operator configuration which
does not parse fails LOUDLY instead of silently becoming the default — a config typo that
degrades to the old global interval reproduces the exact bug this unit removes.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.acquire.cadence import (
    DEFAULT_CADENCE_POLICY,
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    Cadence,
    CadencePolicy,
    CadenceRequest,
    SourceCadence,
    connection_override_seconds,
    load_cadence_policy,
    parse_duration_seconds,
    resolve_cadence,
)
from genios_engine.contracts.connection import Connection

ORG = "org_cadence"


@pytest.mark.parametrize("source,expected_seconds,expected_origin", [
    ("gmail", 15 * 60, "policy"),        # webhook is primary; the poll is a fast safety net
    ("gcal", 3600, "policy"),
    ("hubspot", 2 * 3600, "policy"),
    ("notion", 12 * 3600, "policy"),     # a quarterly page does not repay hourly listing
    ("gdrive", 6 * 3600, "policy"),
    ("database", 3600, "policy"),
    ("slack", 6 * 3600, "default"),      # unknown source → the historical global interval
])
def test_cadence_is_per_source(source, expected_seconds, expected_origin):
    got = resolve_cadence(CadenceRequest(source))
    assert got == Cadence(source, expected_seconds, expected_origin)


def test_shipped_policy_uses_at_least_three_distinct_cadences():
    """The group acceptance gate asks for >= 3 distinct poll cadences in use. One global interval
    for every source is the defect; two would still put gmail and notion in the same bucket."""
    assert len({e.interval_seconds for e in DEFAULT_CADENCE_POLICY.entries}) >= 3
    gmail = resolve_cadence(CadenceRequest("gmail")).interval_seconds
    notion = resolve_cadence(CadenceRequest("notion")).interval_seconds
    assert gmail != notion and gmail < notion


@pytest.mark.parametrize("override,expected_seconds,expected_origin", [
    (30 * 60, 30 * 60, "override"),                        # in range → honoured verbatim
    (MIN_INTERVAL_SECONDS, MIN_INTERVAL_SECONDS, "override"),
    (MAX_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS, "override"),
    (5, MIN_INTERVAL_SECONDS, "override_clamped"),         # a 5s poll is a rate-limit ban
    (10 ** 9, MAX_INTERVAL_SECONDS, "override_clamped"),   # a year is not a cadence
])
def test_connection_override_beats_policy_and_is_clamped(override, expected_seconds, expected_origin):
    got = resolve_cadence(CadenceRequest("gmail", override))
    assert (got.interval_seconds, got.origin) == (expected_seconds, expected_origin)


@pytest.mark.parametrize("raw,expected", [
    ("900", 900), ("900s", 900), ("15m", 900), ("2h", 7200), ("1d", 86400), (" 12H ", 43200),
])
def test_parse_duration_seconds(raw, expected):
    assert parse_duration_seconds(raw) == expected


@pytest.mark.parametrize("raw", ["", "15min", "-5m", "m", "1.5h", "fifteen"])
def test_parse_duration_rejects_junk(raw):
    with pytest.raises(ValueError):
        parse_duration_seconds(raw)


def test_operator_spec_overlays_rather_than_replaces():
    """Retuning gmail must not silently drop notion back to the coarse catch-all."""
    policy = load_cadence_policy("gmail=5m,default=8h")
    assert policy.interval_for("gmail") == 300
    assert policy.interval_for("notion") == 12 * 3600      # untouched entry survives
    assert policy.interval_for("slack") == 8 * 3600        # `default=` moves the fallback
    assert resolve_cadence(CadenceRequest("gmail"), policy=policy).origin == "policy"


@pytest.mark.parametrize("spec", [None, "", "   "])
def test_empty_spec_is_the_shipped_policy(spec):
    assert load_cadence_policy(spec) is DEFAULT_CADENCE_POLICY


@pytest.mark.parametrize("spec", [
    "gmail",              # no '=' — an operator wrote a source and forgot the value
    "gmail=zzz",          # unparseable duration
    "gmail=5s",           # below the floor
    "gmail=30d",          # above the ceiling
])
def test_bad_operator_spec_raises_instead_of_degrading(spec):
    with pytest.raises(ValueError):
        load_cadence_policy(spec)


def _conn(config) -> Connection:
    return Connection(org_id=ORG, connection_id="con_1", source_type="gmail", config=config)


@pytest.mark.parametrize("config,expected", [
    ({}, None),
    ({"cadence_seconds": 300}, 300),
    ({"cadence_minutes": 30}, 1800),
    ({"cadence": "45m"}, 2700),
    ({"cadence_seconds": 300, "cadence_minutes": 30}, 300),   # the precise key wins
    ({"cadence_seconds": 0}, None),                           # 0 is "unset", not "poll forever"
    ({"cadence_seconds": -60}, None),
    ({"cadence_seconds": True}, None),                        # bool is an int; never a cadence
    ({"cadence_seconds": "fast"}, None),
    ({"cadence": "soon"}, None),                              # tenant JSON never crashes a sweep
    ({"cadence": ["15m"]}, None),
])
def test_connection_override_is_read_out_of_untyped_config(config, expected):
    assert connection_override_seconds(_conn(config)) == expected


def test_policy_lookup_is_ordered_and_typed():
    policy = CadencePolicy(entries=(SourceCadence("x", 120),), default_seconds=600)
    assert policy.has("x") and not policy.has("y")
    assert policy.interval_for("x") == 120 and policy.interval_for("y") == 600
