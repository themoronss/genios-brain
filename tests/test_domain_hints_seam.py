"""Regression: the L1→L2 domain-hint seam must survive the Postgres jsonb round-trip.

The bug this guards against: pg_repository serialized list[DomainHint] with
json.dumps(..., default=str), which stored each hint as its str() repr
("domain='sales' source='keyword'") instead of an object. L2's resolve_domain reads
.domain off each item; a string has none, so EVERY event fell back to `general` and
domain-scoped correlation silently never happened on Postgres. The in-memory repo kept
the real objects, so no existing test caught it. This test exercises the exact
serialize -> jsonb-parse -> resolve path.
"""
from __future__ import annotations

import json

from genios_engine.capture.domain.hints import domain_hints
from genios_engine.capture.landing.pg_repository import _dump_list
from genios_engine.context.correlation import DEFAULT_DOMAIN, resolve_domain


def _roundtrip(hints):
    # _dump_list produces the exact JSON text written to the jsonb column; json.loads
    # mirrors what SQLAlchemy hands back when L2 reads the column (list[dict]).
    return json.loads(_dump_list(hints))


def test_source_prior_survives_roundtrip():
    hints = domain_hints("hubspot", None)          # HubSpot -> sales prior
    assert hints and hints[0].domain == "sales"
    parsed = _roundtrip(hints)
    assert parsed == [{"domain": "sales", "source": "scope"}]   # objects, not repr strings
    assert resolve_domain(parsed) == "sales"       # NOT the general fallback


def test_keyword_hint_survives_roundtrip():
    hints = domain_hints("gmail", "can we revisit the pricing on this deal")
    parsed = _roundtrip(hints)
    assert resolve_domain(parsed) == "sales"


def test_no_hints_falls_back_to_general():
    assert _dump_list(None) is None
    assert resolve_domain(None) == DEFAULT_DOMAIN


def test_old_repr_string_shape_would_have_failed():
    # Documents the exact defect: had we stored str(hint), resolve_domain sees strings
    # with no .domain and returns the general fallback — the silent bug.
    broken = [str(h) for h in domain_hints("hubspot", None)]
    assert resolve_domain(broken) == DEFAULT_DOMAIN
