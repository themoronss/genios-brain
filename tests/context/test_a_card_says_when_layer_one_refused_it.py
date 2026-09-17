"""63 cards are held before their content is read, and nothing anywhere says why.

    pytest tests/context/test_a_card_says_when_layer_one_refused_it.py -q

MEASURED ON THE PILOT, 2026-09-16, after the correlation seam landed. 159 active situations, 96
with a live scored Layer 1 signal, and 63 with none at all:

    commitment_overdue       30        condition_in_review    7
    first_response_overdue   21        reply_owed             2

Layer 3 holds every one of them — `qes_required` and `verified_evidence_required` are the SAME 63
cards, not two separate gaps, because both gates read what Layer 1 published and Layer 1 published
nothing. Layer 2's own grading is not implicated: of the 96 situations that DO reach a signal, 96
have verified spans and zero have spans that failed to verify.

WHY LAYER 1 PUBLISHED NOTHING, and this is the part worth knowing. The 71 events behind those
cards were scored and REFUSED: 528–1920 basis points against a floor of 2500. Across the tenant,
227 of 584 scored signals are dropped that way. `org_qualification_floors` holds ZERO rows for this
org and `qualification_floor_changes` zero — so the floor is the untuned global default, and
nobody has ever set one for this tenant.

THE GATE IS RIGHT AND THE SILENCE IS WRONG. A card whose only evidence Layer 1 declined to publish
should not carry authority — that is the whole point of the floor. But today such a card simply
exists, ranks, and quietly never becomes anything, and no surface in the product says "Layer 1
scored this 1360 against a floor of 2500". That is the same defect this codebase has fixed five
times in other lanes: a refusal that is correct and invisible.

This unit makes the refusal visible. It does NOT lower the floor, and it must not — a floor moved
to make cards appear is a threshold tuned on one tenant, which is the failure the whole layer is
built to avoid. Moving it is a separate, attributed decision with its own route.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.situation_bso import l1_refusal

pytestmark = pytest.mark.unit

ORG = "org1"
CORR = "commitment:node_a_admin"


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table context_correlation_members (org_id text, "
                       "correlation_id text, event_id text)"))
        c.execute(text("create table qualified_signals (org_id text, event_id text, "
                       "signal_id text, state text)"))
        c.execute(text("""create table qualification_drops (org_id text, event_id text,
            signal_id text, signal_type text, importance_bp integer, floor_bp integer)"""))
        yield c


def member(conn, event_id, correlation_id=CORR):
    conn.execute(text("insert into context_correlation_members values (:o,:c,:e)"),
                 {"o": ORG, "c": correlation_id, "e": event_id})


def dropped(conn, event_id, *, score=1360, floor=2500, kind="commitment_made"):
    conn.execute(text("insert into qualification_drops values (:o,:e,:s,:k,:i,:f)"),
                 {"o": ORG, "e": event_id, "s": f"sig_{event_id}", "k": kind,
                  "i": score, "f": floor})


def kept(conn, event_id):
    conn.execute(text("insert into qualified_signals values (:o,:e,:s,'active')"),
                 {"o": ORG, "e": event_id, "s": f"sig_{event_id}"})


def test_a_card_whose_evidence_was_refused_says_so(conn) -> None:
    """THE DEFECT. Before this, the card existed, ranked, and silently never became anything."""
    member(conn, "evt_a"); dropped(conn, "evt_a", score=1360, floor=2500)
    found = l1_refusal(conn, ORG, CORR)
    assert found is not None
    assert found["dropped"] == 1
    assert found["floor_bp"] == 2500
    assert found["highest_bp"] == 1360


def test_it_reports_the_closest_the_evidence_came(conn) -> None:
    """The HIGHEST refused score, not the average. "Its best evidence scored 1920 against a floor
    of 2500" is a sentence somebody can act on; a mean over four signals is not."""
    member(conn, "evt_a"); member(conn, "evt_b")
    dropped(conn, "evt_a", score=600)
    dropped(conn, "evt_b", score=1920)
    assert l1_refusal(conn, ORG, CORR)["highest_bp"] == 1920


def test_it_names_what_kind_of_signal_was_refused(conn) -> None:
    """`commitment_made` refused below the floor is a different story from `relationship_change`
    refused, and a reader deciding whether the floor is wrong needs to know which."""
    member(conn, "evt_a"); dropped(conn, "evt_a", kind="commitment_made")
    assert "commitment_made" in l1_refusal(conn, ORG, CORR)["signal_types"]


def test_a_card_with_a_live_signal_is_not_a_refusal(conn) -> None:
    """The 96 that DO reach Layer 1 must say nothing. A refusal notice on a card that was never
    refused is worse than silence — it is a false explanation."""
    member(conn, "evt_a"); kept(conn, "evt_a")
    assert l1_refusal(conn, ORG, CORR) is None


def test_one_kept_signal_beats_several_refused(conn) -> None:
    """A correlation resting on four events where one qualified is NOT a refused correlation. The
    card has evidence; the other three simply did not clear the bar."""
    member(conn, "evt_a"); member(conn, "evt_b")
    dropped(conn, "evt_a"); kept(conn, "evt_b")
    assert l1_refusal(conn, ORG, CORR) is None


def test_no_evidence_at_all_is_not_a_refusal(conn) -> None:
    """A correlation whose events were never SCORED was not refused — it was never assessed, which
    is a different fact and must not be reported as a judgement Layer 1 made."""
    member(conn, "evt_a")
    assert l1_refusal(conn, ORG, CORR) is None


def test_it_never_reads_a_floor_it_could_change(conn) -> None:
    """THE RULE THIS UNIT REFUSES TO BREAK. It reports the floor Layer 1 applied and holds no
    opinion about whether that floor is right. A floor moved to make cards appear is a threshold
    tuned on one tenant, and moving it is a separate decision with its own attributed route."""
    import ast
    import inspect

    from genios_engine.context import situation_bso

    tree = ast.parse(inspect.getsource(situation_bso.l1_refusal))
    sql = " ".join(lit.value.lower()
                   for call in ast.walk(tree)
                   if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "text"
                   for lit in ast.walk(call)
                   if isinstance(lit, ast.Constant) and isinstance(lit.value, str))
    for forbidden in ("update", "insert", "delete", "org_qualification_floors"):
        assert forbidden not in sql, f"this reader writes or tunes: {forbidden}"
