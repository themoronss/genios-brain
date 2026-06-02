"""Tests for feedback_capture (→ Correction → g-i-3) and mcp_server tool registry."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.delivery.feedback_capture import (
    FeedbackAction,
    capture_feedback,
)
from core.delivery.mcp_server import MCPServer, MCPTool, default_tool_definitions
from core.delivery.store import FeedbackActionRow
from core.foundations.db import Base
from core.worldmodel.store import CorrectionRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


# ── feedback_capture ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_thumbs_up_no_correction(session: Session) -> None:
    """👍 records the signal but does NOT create a Correction."""
    out = capture_feedback(
        session,
        org_id="o",
        user_id="alice",
        decision_id="dec_1",
        insight_id=None,
        action=FeedbackAction.THUMBS_UP,
    )
    session.commit()
    assert out.correction_id is None
    assert out.routed_to_g_i_3 is False

    # Feedback row persisted
    rows = session.query(FeedbackActionRow).all()
    assert len(rows) == 1
    # Correction NOT created
    assert session.query(CorrectionRow).count() == 0


@pytest.mark.unit
def test_thumbs_down_creates_correction(session: Session) -> None:
    out = capture_feedback(
        session,
        org_id="o",
        user_id="alice",
        decision_id="dec_1",
        insight_id=None,
        action=FeedbackAction.THUMBS_DOWN,
        engine_decision_loader=lambda _: {"conclusion": "churn_risk_high"},
    )
    session.commit()
    assert out.correction_id is not None
    assert out.routed_to_g_i_3 is True

    correction = session.get(CorrectionRow, out.correction_id)
    assert correction is not None
    assert correction.decision_id == "dec_1"
    assert correction.actor == "alice"


@pytest.mark.unit
def test_edit_creates_correction_with_diff(session: Session) -> None:
    out = capture_feedback(
        session,
        org_id="o",
        user_id="alice",
        decision_id="dec_1",
        insight_id=None,
        action=FeedbackAction.EDIT,
        edit_diff={"recommend": "send_only_one_email"},
        engine_decision_loader=lambda _: {"recommend": "send_email_campaign"},
    )
    session.commit()
    assert out.correction_id is not None

    correction = session.get(CorrectionRow, out.correction_id)
    assert correction is not None
    assert "recommend" in correction.diff
    assert correction.diff["recommend"]["human"] == "send_only_one_email"
    assert correction.diff["recommend"]["engine"] == "send_email_campaign"


@pytest.mark.unit
def test_thumbs_down_requires_decision_id(session: Session) -> None:
    with pytest.raises(ValueError):
        capture_feedback(
            session,
            org_id="o",
            user_id="alice",
            decision_id=None,
            insight_id=None,
            action=FeedbackAction.THUMBS_DOWN,
        )


@pytest.mark.unit
def test_never_show_no_correction(session: Session) -> None:
    """never_show is a suppression signal — no correction (g-i-4 prioritizer reads this)."""
    out = capture_feedback(
        session,
        org_id="o",
        user_id="alice",
        decision_id=None,
        insight_id="ins_1",
        action=FeedbackAction.NEVER_SHOW,
    )
    session.commit()
    assert out.correction_id is None
    assert session.query(CorrectionRow).count() == 0


@pytest.mark.unit
def test_feedback_linked_back_to_correction(session: Session) -> None:
    out = capture_feedback(
        session,
        org_id="o",
        user_id="alice",
        decision_id="dec_1",
        insight_id=None,
        action=FeedbackAction.THUMBS_DOWN,
    )
    session.commit()
    fb = session.get(FeedbackActionRow, out.feedback_id)
    assert fb is not None
    assert fb.correction_id == out.correction_id


# ── MCPServer ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_mcp_register_and_dispatch() -> None:
    called: list[dict[str, Any]] = []

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        called.append(args)
        return {"ok": True, "echo": args}

    server = MCPServer()
    server.register(
        MCPTool(
            name="test.tool",
            description="for tests",
            input_schema={"type": "object"},
            handler=handler,
        )
    )

    listed = server.list_tools()
    assert len(listed) == 1
    assert listed[0]["name"] == "test.tool"

    result = server.dispatch("test.tool", {"x": 1})
    assert result == {"ok": True, "echo": {"x": 1}}
    assert called == [{"x": 1}]


@pytest.mark.unit
def test_mcp_dispatch_unknown_raises() -> None:
    server = MCPServer()
    with pytest.raises(KeyError):
        server.dispatch("nonexistent.tool", {})


@pytest.mark.unit
def test_mcp_duplicate_register_rejected() -> None:
    server = MCPServer()
    t = MCPTool(name="x", description="", input_schema={}, handler=lambda _: {})
    server.register(t)
    with pytest.raises(ValueError):
        server.register(t)


@pytest.mark.unit
def test_default_tools_have_4_intelligence_endpoints() -> None:
    """Smoke-check the default toolset has query/explain/feedback/graph_view."""
    tools = default_tool_definitions(
        query_handler=lambda _: {},
        explain_handler=lambda _: {},
        feedback_handler=lambda _: {},
        graph_view_handler=lambda _: {},
    )
    names = {t.name for t in tools}
    assert names == {
        "intelligence.query",
        "intelligence.explain",
        "intelligence.feedback",
        "intelligence.graph_view",
    }
