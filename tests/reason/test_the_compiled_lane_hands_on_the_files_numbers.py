"""STEP-12 · the compiled lane hands each situation its file's measured normals (`03` F104's call).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_the_compiled_lane_hands_on_the_files_numbers.py -q

Tree `yc2_w27_s12` M33.C1.L-integration.V1.U09. M33.C1.L-logic.V0.U04 built the seam —
`expertise_capability_manifest(baselines=…)` hands the adapter the file's normals, so a corpus
`{baseline: write_interval}` threshold answers instead of UNKNOWN. A seam nothing calls measures nothing:
`reason/domain_shadow.shadow_compile` reads every anchor's measured baselines once a pass (`baselines`,
each with its n) and hands each situation its anchor's. A cold start is a default, never a measurement,
and is not read; an anchor with none is handed none.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.reason.test_a_programme_is_not_decided_as_an_investor import (  # noqa: F401 — a fixture
    FUND, NOW, _by_counterparty, _tenant, admitted)

pytestmark = pytest.mark.pg


@pytest.fixture
def world(pg_store, admitted, monkeypatch, request):
    from genios_engine.reason import domain_shadow
    org = f"m33u09_{request.node.name[5:28]}"
    registry = _tenant(pg_store, org)
    monkeypatch.setattr(domain_shadow, "expert_catalog", lambda: admitted)
    handed: dict[str, object] = {}
    original = domain_shadow.expertise_capability_manifest

    def _recorded(package, **kw):
        handed[kw["situation"].metadata.get("anchor_node_id") or kw["context"].root_entity_ids[0]] = \
            kw.get("baselines")
        return original(package, **kw)
    monkeypatch.setattr(domain_shadow, "expertise_capability_manifest", _recorded)
    with pg_store.engine.connect() as c:
        anchor = c.execute(text("select anchor_node_id from context_situations where org_id = :o "
                                "and situation_id = any(:s) limit 1"),
                           {"o": org, "s": list(_by_counterparty(pg_store, org)[FUND])}).scalar()
    try:
        yield pg_store, org, registry, anchor, handed
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from baselines where org_id = :o"), {"o": org})


def _baseline(store, org, key, value, n, cold=False):
    with store.engine.begin() as c:
        c.execute(text("insert into baselines (org_id, key, value, sample_size, cold_start, computed_at) "
                       "values (:o, :k, :v, :n, :c, now()) on conflict (org_id, key) do update set "
                       "value = excluded.value, sample_size = excluded.sample_size, "
                       "cold_start = excluded.cold_start"),
                  {"o": org, "k": key, "v": value, "n": n, "c": cold})


def _compile(store, org, registry):
    from genios_engine.reason import domain_shadow
    return domain_shadow.shadow_compile(store=store, org_id=org, eval_time=NOW, registry=registry,
                                        live_domains=frozenset({"founder_office"}))


def test_each_situation_is_handed_its_anchors_measured_normals(world):
    from genios_engine.contracts.measured import MEASURED_HERE
    store, org, registry, anchor, handed = world
    _baseline(store, org, f"write_interval:{anchor}", 3.0, 6)
    _baseline(store, org, f"contact_rate_per_account:{anchor}", 1.5, 9)
    _baseline(store, org, f"momentum:{anchor}", 1.2, 6)                 # a derived ratio: not a baseline
    _compile(store, org, registry)
    numbers = handed[anchor]
    assert set(numbers) == {"write_interval", "contact_rate_per_account"}
    write = numbers["write_interval"]
    assert (write.value, write.n, write.source, write.normal) == (3.0, 6, MEASURED_HERE, True)
    assert numbers["contact_rate_per_account"].n == 9


def test_a_cold_start_is_a_default_and_is_not_handed(world):
    store, org, registry, anchor, handed = world
    _baseline(store, org, f"write_interval:{anchor}", 3.0, 2, cold=True)
    _compile(store, org, registry)
    assert not handed[anchor], "a cold start's default reached the threshold as a measurement"


def test_an_anchor_with_no_numbers_is_handed_none(world):
    """⛔ THE NEGATIVE CONTROL: no baseline rows — the call carries none, as it did before F104."""
    store, org, registry, anchor, handed = world
    _compile(store, org, registry)
    assert handed and handed[anchor] is None
