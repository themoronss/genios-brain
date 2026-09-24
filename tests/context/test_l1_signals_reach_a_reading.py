"""M9.C1.L-integration.V2.U03 — the proof that the seam was the defect, not the join.

    pytest tests/context/test_l1_signals_reach_a_reading.py -q

`gather_l1_signals` is NOT MODIFIED by this milestone, and that is the claim under test. Its join
was always correct — *"the correlation already decided which events are one thing; the anchor is
one node inside it"* — and it found nothing for fourteen of eighteen situation types because the
readings that mint those situations never wrote the membership their own facts implied.

If declaring the events is the whole fix, then the untouched join starts answering. If it does
not, the diagnosis was wrong and this milestone is built on a mistaken premise. This file is where
that is settled.

MEASURED BEFORE, on the pilot 2026-09-15: 238 live qualified signals, 99 of 99 correlation-member
events carrying one, and 20 of 94 situations able to reach one — Layer 3 holding the other 73 at
`QES_REQUIRED` before their content was ever examined.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.outreach_situations import _Finding, _declare_finding_events
from genios_engine.context.situation_bso import gather_l1_signals

pytestmark = pytest.mark.unit

ORG = "org1"
CORR = "outreach:node_a"


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table context_correlation_members (org_id text, "
                       "correlation_id text, event_id text, joined_via text, "
                       "joined_at timestamp, primary key (org_id, correlation_id, event_id))"))
        c.execute(text("create table context_correlations (org_id text, correlation_id text, "
                       "event_count integer)"))
        # The columns `_L1_SELECT` reads. Kept in step with the projection deliberately: this
        # schema is hand-written, so it drifts from `migrations/0089`+`0177` unless a change to
        # the projection is made here at the same time. The insert below names its columns for
        # the same reason — a positional insert breaks silently the next time one is added.
        c.execute(text("""create table qualified_signals (
            org_id text, signal_id text, event_id text, state text,
            importance_bp integer, importance_version text, importance_components text,
            evidence_refs text, conflict_ids text, signal_type text, coverage_ready boolean,
            subject_key text, domain_hints text, confidence_bp integer, occurred_at timestamp, expires_at timestamp, secondary_types text, extraction_ref text, internal_kind text)"""))
        yield c


def signal(conn, event_id, signal_id, *, state="active", importance=3080,
           version="alg17-v1"):
    conn.execute(text(
        "insert into qualified_signals (org_id, signal_id, event_id, state, importance_bp, "
        "  importance_version, importance_components, evidence_refs, conflict_ids, signal_type, "
        "  coverage_ready, subject_key) "
        "values (:o,:s,:e,:st,:i,:v,'{}','[]','[]','deadline_stated',0,:subj)"),
        {"o": ORG, "s": signal_id, "e": event_id, "st": state, "i": importance,
         "v": version, "subj": f"subject:{event_id}"})


def test_before_the_seam_a_reading_reaches_no_signal(conn) -> None:
    """The state 73 cards were in: the signal exists, the situation exists, and the join between
    them has nothing to match on."""
    signal(conn, "evt_a", "sig_1")
    assert gather_l1_signals(conn, ORG, CORR) is None


def test_declaring_the_events_is_the_whole_fix(conn) -> None:
    """THE CLAIM. `gather_l1_signals` is untouched; only the membership changed."""
    signal(conn, "evt_a", "sig_1")
    _declare_finding_events(conn, org_id=ORG,
                            finding=_Finding(correlation_id=CORR, concerns_node="node_a",
                                             event_ids=("evt_a",)))
    found = gather_l1_signals(conn, ORG, CORR)
    assert found is not None, "the untouched join still finds nothing — the diagnosis was wrong"
    assert found.signal_ids == ("sig_1",)


def test_the_importance_now_comes_from_layer_one(conn) -> None:
    """THE GATE ITSELF. `QES_REQUIRED` holds a situation whose importance did not come from a
    qualified signal. This is the number that stops it being a default constant."""
    signal(conn, "evt_a", "sig_1", importance=3080)
    _declare_finding_events(conn, org_id=ORG,
                            finding=_Finding(correlation_id=CORR, concerns_node="node_a",
                                             event_ids=("evt_a",)))
    found = gather_l1_signals(conn, ORG, CORR)
    assert found.importance_bp == 3080
    assert found.scored_count == 1


def test_several_events_average_rather_than_pick(conn) -> None:
    """A reading rests on many events and the situation is one thing. The existing derivation
    decides how they combine; this only proves all of them arrive."""
    signal(conn, "evt_a", "sig_1", importance=2000)
    signal(conn, "evt_b", "sig_2", importance=4000)
    _declare_finding_events(conn, org_id=ORG,
                            finding=_Finding(correlation_id=CORR, concerns_node="node_a",
                                             event_ids=("evt_a", "evt_b")))
    found = gather_l1_signals(conn, ORG, CORR)
    assert set(found.signal_ids) == {"sig_1", "sig_2"}
    assert found.signal_count == 2


def test_an_expired_signal_is_provenance_but_never_the_score(conn) -> None:
    """ALG-19's rule, which this milestone must not disturb: a superseded or expired signal stays
    in the situation's account of itself and must not set a live situation's importance."""
    signal(conn, "evt_a", "sig_old", state="expired", importance=9000)
    _declare_finding_events(conn, org_id=ORG,
                            finding=_Finding(correlation_id=CORR, concerns_node="node_a",
                                             event_ids=("evt_a",)))
    found = gather_l1_signals(conn, ORG, CORR)
    assert "sig_old" in found.signal_ids, "an expired signal stopped being a receipt"
    assert found.importance_bp is None, "an expired signal set a live situation's score"


def test_gather_l1_signals_was_not_modified() -> None:
    """The milestone's premise, pinned. If this function had to change, the seam was not the
    defect and the other units in M9 need re-examining."""
    import ast
    import inspect

    from genios_engine.context import situation_bso

    src = inspect.getsource(situation_bso.gather_l1_signals)
    tree = ast.parse(src)
    calls = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
             for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert "_declare_finding_events" not in calls, (
        "the reader now writes membership — the fix moved into the wrong layer")
