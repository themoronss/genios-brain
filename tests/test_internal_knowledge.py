"""Layer 1 · Internal Knowledge — the company asserting things about itself.

The behaviour under test is AUTHORITY. Before this, every unstructured event landed at
authority_rank 2, so an uploaded pricing sheet carried exactly the weight of a stranger's
email mentioning a price — and a rank-3 system-of-record row beat the company's own
written policy. These tests pin the fix at each hop it has to survive: vocabulary →
landing → the L1→L2 seam → the graph write.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.intake import ingest_internal_knowledge
from genios_engine.capture.internal_knowledge import (CANON_AUTHORITY_RANK,
                                                      INTERNAL_KINDS,
                                                      OBSERVED_AUTHORITY_RANK,
                                                      authority_rank_for, is_canon,
                                                      normalize_kind)
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.source_registry import descriptor_of
from genios_engine.context.pipeline import FACT_CONF_BY_RANK

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def _raw(**kw) -> RawObject:
    base = dict(source="upload", object_type="document_chunk", source_object_id="f1:chunk_0",
                occurred_at=NOW, raw={"body": "list price is 299/mo"})
    return RawObject(**{**base, **kw})


# ── vocabulary ───────────────────────────────────────────────────────────────────

def test_company_memory_is_not_an_internal_kind() -> None:
    """Memory is DERIVED from what the graph already saw. Re-ingesting it as a source
    would launder yesterday's inference into today's evidence — it belongs to L2."""
    assert "memory" not in INTERNAL_KINDS
    assert normalize_kind("memory") is None


def test_unrecognised_tag_is_not_canon() -> None:
    """The upload `tag` has always been free text. An unknown tag must stay an ordinary
    label at observed authority — guessing here would hand rank 4 to a typo."""
    assert normalize_kind("q3-misc-notes") is None
    assert authority_rank_for("q3-misc-notes") == OBSERVED_AUTHORITY_RANK
    assert authority_rank_for(None) == OBSERVED_AUTHORITY_RANK
    assert not is_canon("")


def test_aliases_keep_existing_tags_meaningful() -> None:
    """Orgs already tagged files 'SOPs' / 'Price List' / 'OKRs'. Those are canon; only
    the spelling differs."""
    assert normalize_kind("SOPs") == "sop"
    assert normalize_kind("Price List") == "pricing"
    assert normalize_kind("price-list") == "pricing"
    assert normalize_kind("OKRs") == "goal"
    assert normalize_kind("org chart") == "org_structure"


def test_canon_outranks_system_of_record() -> None:
    """The whole point: rank 4 beats the 3 that structured connectors write, which beats
    the 2 that extraction writes. graph_store resolves a conflict by rank."""
    assert authority_rank_for("policy") == CANON_AUTHORITY_RANK
    assert CANON_AUTHORITY_RANK > 3 > OBSERVED_AUTHORITY_RANK


def test_every_rank_has_a_confidence() -> None:
    """A rank with no entry in FACT_CONF_BY_RANK is a KeyError at the fact write."""
    assert CANON_AUTHORITY_RANK in FACT_CONF_BY_RANK
    assert FACT_CONF_BY_RANK[CANON_AUTHORITY_RANK] > FACT_CONF_BY_RANK[OBSERVED_AUTHORITY_RANK]


def test_the_registry_publishes_the_kinds_as_object_types() -> None:
    """One vocabulary, not two: the `internal` source's object types ARE the kinds."""
    internal = descriptor_of("internal")
    assert internal is not None
    assert internal.family == "internal"
    assert set(internal.object_types) == INTERNAL_KINDS
    assert internal.deliberate is True


# ── landing ──────────────────────────────────────────────────────────────────────

def test_a_canon_tag_promotes_the_family() -> None:
    """An uploaded price list is the company's own record, whichever door it came
    through. Leaving it in `knowledge` would file it beside a customer's shared doc."""
    event = to_source_event(_raw(internal_kind="pricing"), org_id="o1", connection_id="upload")
    assert event.source_family == "internal"
    assert event.internal_kind == "pricing"


def test_an_untagged_upload_is_unchanged() -> None:
    """Back-compat: the descriptor's family stays the default for observed traffic."""
    event = to_source_event(_raw(), org_id="o1", connection_id="upload")
    assert event.source_family == "knowledge"
    assert event.internal_kind is None


def test_an_unknown_tag_does_not_promote() -> None:
    event = to_source_event(_raw(internal_kind="whatever"), org_id="o1", connection_id="upload")
    assert event.source_family == "knowledge"
    assert event.internal_kind is None


# ── the writing door ─────────────────────────────────────────────────────────────

def _write(repo, *, body: str, title: str = "Refund Policy", kind: str = "policy", **kw):
    return ingest_internal_knowledge(org_id="o1", kind=kind, title=title, body=body,
                                     repo=repo, **kw)


def test_writing_knowledge_lands_as_canon() -> None:
    repo = InMemorySourceEventRepository()
    res = _write(repo, body="Refunds are accepted within 30 days.")
    assert res.outcome == "emitted"
    assert res.event.source == "internal"
    assert res.event.source_family == "internal"
    assert res.event.internal_kind == "policy"
    assert res.event.object_type == "policy"


def test_deliberate_knowledge_is_never_noise_dropped() -> None:
    """W-05 whitelists deliberately-provided material before the N-code drops. A policy
    written as one short line must not be gated as a thin/automated message."""
    repo = InMemorySourceEventRepository()
    res = _write(repo, body="No refunds after 30 days.")
    assert res.outcome == "emitted"
    assert res.gated is not None
    assert res.gated.internal_kind == "policy"     # authority survives the L1→L2 seam


def test_restating_identical_canon_is_a_duplicate() -> None:
    """Same assertion, same content → the graph already holds it. Not an error."""
    repo = InMemorySourceEventRepository()
    body = "Refunds are accepted within 30 days."
    assert _write(repo, body=body).outcome == "emitted"
    assert _write(repo, body=body).outcome == "duplicate"


def test_editing_canon_supersedes_it() -> None:
    """A policy is MUTABLE, like a CRM deal. Editing must re-land so the graph updates —
    the same content_version mechanism that unfroze deal.stage."""
    repo = InMemorySourceEventRepository()
    first = _write(repo, body="Refunds within 30 days.")
    second = _write(repo, body="Refunds within 14 days.")
    assert second.outcome == "emitted"
    assert first.event.dedup_key != second.event.dedup_key
    # ...but it is the SAME assertion, not a competing one: identity is the key, and the
    # content hash rides on top of it.
    assert first.event.source_object_id == second.event.source_object_id == "policy:refund-policy"


def test_the_title_slug_does_not_fork_one_policy_into_two() -> None:
    repo = InMemorySourceEventRepository()
    a = _write(repo, title="Refund Policy", body="x")
    b = _write(repo, title="refund  policy", body="y")
    assert a.event.source_object_id == b.event.source_object_id


def test_an_explicit_key_survives_a_retitle() -> None:
    """`key` is what makes a retitle an EDIT rather than a second competing policy.

    It still re-lands: the title is prepended into the prepared text L2 extracts from, so
    renaming a document genuinely changes what the graph is asked to read. Hashing the
    body alone would let a retitle silently never take effect."""
    repo = InMemorySourceEventRepository()
    a = _write(repo, title="Refund Policy", body="x", key="refunds")
    b = _write(repo, title="Returns & Refunds (2026)", body="x", key="refunds")
    assert a.event.source_object_id == b.event.source_object_id == "policy:refunds"
    assert b.outcome == "emitted"
    assert _write(repo, title="Returns & Refunds (2026)", body="x",
                  key="refunds").outcome == "duplicate"


def test_a_bad_kind_is_refused_not_demoted() -> None:
    """The caller asked for canon. Silently landing it at observed authority would be
    the same class of bug this whole step exists to fix."""
    repo = InMemorySourceEventRepository()
    with pytest.raises(ValueError, match="unknown internal knowledge kind"):
        _write(repo, kind="vibes", body="x")


def test_empty_canon_is_refused() -> None:
    repo = InMemorySourceEventRepository()
    with pytest.raises(ValueError, match="empty assertion"):
        _write(repo, body="   ")


# ── the seam actually carries it ─────────────────────────────────────────────────
#
# The quiet failure mode for this whole feature is a column that exists and is written
# but never READ: every canon event would then reach L2 as internal_kind=None and land at
# rank 2 again, with nothing failing. These pin both halves of the round trip.

def test_capture_persists_internal_kind() -> None:
    from genios_engine.capture.landing import pg_repository
    sql = str(pg_repository._INSERT)
    assert "internal_kind" in sql
    assert ":internal_kind" in sql


def test_the_l2_drain_reads_internal_kind() -> None:
    import inspect

    from genios_engine.context import runner
    assert "se.internal_kind" in inspect.getsource(runner._pull)
    assert "internal_kind" in inspect.getsource(runner._process_one)


def test_l2_accepts_the_authority_the_seam_carries() -> None:
    """process_event must take internal_kind — otherwise the drain has nowhere to hand
    the authority it just read."""
    import inspect

    from genios_engine.context.pipeline import process_event
    assert "internal_kind" in inspect.signature(process_event).parameters
