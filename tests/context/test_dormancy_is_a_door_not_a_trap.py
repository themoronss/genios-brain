"""A situation that goes quiet and comes back must be able to come back.

`age_uncorrelated_situations` moves any synthetic-correlation row to `dormant` after its domain's
window, and both Layer 3 doors filter `status in ('active','partial')` — `reason/runner.py` says
why in as many words: "Dormancy is the only mechanism that stops a stale situation compiling into
a card." That mechanism is correct and both doors honour it.

The other half was missing in two of the four writers. Every producer of a synthetic correlation
upserts on `(org_id, correlation_id)`, and `meeting_touch` and `periodic` set every column EXCEPT
`status`. So once a row went dormant, re-minting it refreshed `last_seen_at`, confidence and
coverage and left the status where the ageing pass put it. The row then carried current timestamps
and current numbers and could never reach a card again — the worst shape a defect can take,
because nothing about it looks wrong.

`meeting_touch`'s id is `corr_touch_{domain}_{node}`, stable for the life of the meeting node, so
the trap is reachable rather than theoretical.
"""
import re

import pytest

from genios_engine.context.situations import SITUATION_STATUS_ON_CONFLICT

WRITERS = {
    "support_situations": "genios_engine/context/support_situations.py",
    "document_register": "genios_engine/context/document_register.py",
    "meeting_touch": "genios_engine/context/meeting_touch.py",
    "periodic": "genios_engine/context/periodic.py",
}


def _source(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# ── the clause itself ────────────────────────────────────────────────────────────────────────

def test_a_re_minted_situation_returns_to_active() -> None:
    """The half that was missing. Without it dormancy is a one-way door."""
    assert "else 'active' end" in SITUATION_STATUS_ON_CONFLICT


def test_a_human_close_still_survives_the_next_drain() -> None:
    """Which is why this is a CASE and not `status = 'active'`. `POST /situations/{id}/resolve`
    records `resolved_by='human'`, and `decide_lifecycle`'s rule is that a human resolution
    sticks until new evidence — the provenance must not be erased by a re-derivation."""
    for column in ("status", "resolved_by", "resolved_at"):
        assert f"{column} = case when context_situations.resolved_by = 'human'" \
            in re.sub(r"\s+", " ", SITUATION_STATUS_ON_CONFLICT), column


def test_nothing_but_the_decision_columns_is_preserved() -> None:
    """Confidence, coverage, evidence and last_seen are this sweep's either way — observations
    do not care what somebody decided. Only the three columns that record the DECISION are held."""
    preserved = set(re.findall(r"(\w+) = case when", SITUATION_STATUS_ON_CONFLICT))
    assert preserved == {"status", "resolved_by", "resolved_at"}


# ── every writer uses it, and none carries a second copy ─────────────────────────────────────

@pytest.mark.parametrize("name", sorted(WRITERS))
def test_every_synthetic_correlation_writer_uses_the_shared_clause(name: str) -> None:
    """Four writers of one column, and two of them did not have it. Naming the clause once is
    what stops the next writer being the third — the same drift `evidence_score`'s `voice_count`
    and `identity_score`'s merge count each paid for separately."""
    source = _source(WRITERS[name])
    assert "SITUATION_STATUS_ON_CONFLICT" in source


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_no_writer_hand_rolls_its_own_copy(name: str) -> None:
    """A second, subtly different spelling is how the two correct ones and the two broken ones
    came to disagree in the first place."""
    source = _source(WRITERS[name])
    assert "then context_situations.status else 'active' end" not in source, (
        f"{name} carries a literal copy instead of the shared clause")


# ── and the behaviour, not only the text ─────────────────────────────────────────────────────

def test_a_dormant_situation_comes_back_when_its_reading_fires_again() -> None:
    """The property, driven through the real upsert rather than read off the source.

    A source scan can tell you the clause is present; only this can tell you it WORKS.
    """
    from datetime import datetime, timezone

    from sqlalchemy import create_engine, text

    from genios_engine.context.support_situations import _upsert

    now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table context_situations (situation_id text primary key, org_id text, "
            "correlation_id text, anchor_node_id text, situation_type text, domain text, "
            "status text, confidence_overall int, confidence_evidence int, "
            "confidence_freshness int, confidence_consistency int, confidence_identity int, "
            "coverage int, missing text, inputs text, first_seen_at timestamp, "
            "last_seen_at timestamp, computed_at timestamp, resolved_by text, "
            "resolved_at timestamp, unique (org_id, correlation_id))"))

    fields = dict(org_id="o", corr="corr_touch_admin_n1", node_id="n1", stype="t",
                  domain="admin", now=now, coverage=50, missing=[], inputs={},
                  evidence=70, freshness=80, identity=100,
                  first_seen=now, last_seen=now)
    with engine.begin() as c:
        _upsert(c, **fields)
        c.execute(text("update context_situations set status='dormant'"))
    with engine.begin() as c:
        _upsert(c, **fields)
    with engine.connect() as c:
        row = c.execute(text("select status, resolved_by from context_situations")).first()
    assert row.status == "active", "a reading that fires again revives its situation"
    assert row.resolved_by is None


def test_a_human_close_is_not_revived_by_the_next_sweep() -> None:
    """The other half, and the reason the clause is a CASE. A card somebody handled must not
    come straight back — that is the failure the two correct writers already carried."""
    from datetime import datetime, timezone

    from sqlalchemy import create_engine, text

    from genios_engine.context.support_situations import _upsert

    now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table context_situations (situation_id text primary key, org_id text, "
            "correlation_id text, anchor_node_id text, situation_type text, domain text, "
            "status text, confidence_overall int, confidence_evidence int, "
            "confidence_freshness int, confidence_consistency int, confidence_identity int, "
            "coverage int, missing text, inputs text, first_seen_at timestamp, "
            "last_seen_at timestamp, computed_at timestamp, resolved_by text, "
            "resolved_at timestamp, unique (org_id, correlation_id))"))

    fields = dict(org_id="o", corr="corr_support_n1", node_id="n1", stype="t", domain="admin",
                  now=now, coverage=50, missing=[], inputs={}, evidence=70, freshness=80,
                  identity=100, first_seen=now, last_seen=now)
    with engine.begin() as c:
        _upsert(c, **fields)
        c.execute(text("update context_situations set status='resolved', resolved_by='human'"))
    with engine.begin() as c:
        _upsert(c, **fields)
    with engine.connect() as c:
        row = c.execute(text(
            "select status, resolved_by, confidence_evidence from context_situations")).first()
    assert row.status == "resolved" and row.resolved_by == "human"
    assert row.confidence_evidence == 70, "the FACTS still refresh underneath the decision"
