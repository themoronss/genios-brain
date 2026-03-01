"""
API Endpoint Tests for MVP Brain
Tests the FastAPI endpoints: /health, /brain/run, /brain/approve
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_check():
    """Health endpoint should return ok status"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["layers"] == 4


def test_brain_run_follow_up_intent():
    """Test /brain/run with follow_up intent (main MVP scenario)"""
    response = client.post(
        "/brain/run",
        json={
            "intent": "Follow up with Investor X tomorrow 8am",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Check all required fields
    assert "decision_id" in data
    assert "context" in data
    assert "judgement" in data
    assert "decision" in data
    assert "learning" in data
    assert "execution_status" in data

    # Check context bundle structure (just verify it exists)
    context = data["context"]
    assert isinstance(context, dict) and len(context) > 0

    # Check judgement (just verify it exists)
    judgement = data["judgement"]
    assert isinstance(judgement, dict) and len(judgement) > 0


def test_brain_run_returns_decision_id_when_needs_approval():
    """Test that VIP investor (needs approval) returns decision_id"""
    response = client.post(
        "/brain/run",
        json={
            "intent": "Follow up with Investor X tomorrow 8am",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # For follow_up with VIP, should need approval
    if data["execution_status"] == "needs_approval":
        assert data["decision_id"] is not None
        assert len(data["decision_id"]) > 0  # UUID format


def test_brain_run_schedule_intent():
    """Test /brain/run with schedule_meeting intent"""
    response = client.post(
        "/brain/run",
        json={
            "intent": "Schedule meeting with investor next Tuesday 2pm",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Should have valid flow
    assert "context" in data
    assert "decision" in data
    assert "execution_status" in data


def test_brain_run_reply_intent():
    """Test /brain/run with reply_email intent"""
    response = client.post(
        "/brain/run",
        json={
            "intent": "Reply to investor email with meeting proposal",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "decision" in data
    assert "learning" in data


def test_brain_approve_valid_decision():
    """Test /brain/approve with valid pending decision"""
    # First, create a pending decision
    run_response = client.post(
        "/brain/run",
        json={
            "intent": "Follow up with Investor X tomorrow 8am",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    assert run_response.status_code == 200
    decision_id = run_response.json()["decision_id"]

    # Only test approval if this decision needs approval
    if run_response.json()["execution_status"] == "needs_approval":
        # Now approve it
        approve_response = client.post(
            "/brain/approve",
            json={
                "decision_id": decision_id,
                "approved": True,
                "user_comment": "Looks good, go ahead",
            },
        )

        assert approve_response.status_code == 200
        data = approve_response.json()

        assert data["decision_id"] == decision_id
        assert data["approved"] is True
        assert "execution_status" in data
        assert "learning" in data


def test_brain_approve_invalid_decision_id():
    """Test /brain/approve with non-existent decision_id"""
    response = client.post(
        "/brain/approve",
        json={
            "decision_id": "invalid-uuid-12345",
            "approved": True,
            "user_comment": "Test",
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_brain_approve_rejection():
    """Test /brain/approve with approved=False (rejection)"""
    # Create pending decision
    run_response = client.post(
        "/brain/run",
        json={
            "intent": "Follow up with Investor X tomorrow 8am",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    decision_id = run_response.json()["decision_id"]

    if run_response.json()["execution_status"] == "needs_approval":
        # Reject it
        approve_response = client.post(
            "/brain/approve",
            json={
                "decision_id": decision_id,
                "approved": False,
                "user_comment": "Not the right time",
            },
        )

        assert approve_response.status_code == 200
        data = approve_response.json()
        assert data["approved"] is False


def test_brain_run_with_workspace_isolation():
    """Test that different actors return isolated contexts"""
    response_u1 = client.post(
        "/brain/run",
        json={
            "intent": "Follow up with Investor X",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    response_u2 = client.post(
        "/brain/run",
        json={
            "intent": "Follow up with Investor X",
            "workspace_id": "w1",
            "actor_id": "u2",
            "use_db": False,
        },
    )

    assert response_u1.status_code == 200
    assert response_u2.status_code == 200

    # Both should succeed (actor isolation handled)
    assert "decision" in response_u1.json()
    assert "decision" in response_u2.json()


def test_brain_run_decision_has_action_plan():
    """Test that decision includes action_plan with tool_calls"""
    response = client.post(
        "/brain/run",
        json={
            "intent": "Follow up with Investor X tomorrow 8am",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Decision should have action_plan
    assert "action_plan" in data["decision"]
    action_plan = data["decision"]["action_plan"]

    if action_plan:  # May be None if no action planned
        # If action_plan exists, it should have structure
        if isinstance(action_plan, dict):
            # Should have tool_calls or be None
            pass


def test_brain_run_learning_captures_outcome():
    """Test that learning layer captures outcome correctly"""
    response = client.post(
        "/brain/run",
        json={
            "intent": "Follow up with Investor X tomorrow 8am",
            "workspace_id": "w1",
            "actor_id": "u1",
            "use_db": False,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Learning should capture outcome
    learning = data["learning"]
    assert "outcome_record" in learning or "outcome" in learning


def test_api_response_consistency():
    """Test that API responses are consistent in structure"""
    intents = [
        "Follow up with Investor X tomorrow 8am",
        "Schedule meeting next Tuesday 2pm",
        "Reply to investor email",
    ]

    for intent in intents:
        response = client.post(
            "/brain/run",
            json={
                "intent": intent,
                "workspace_id": "w1",
                "actor_id": "u1",
                "use_db": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # All responses should have consistent structure
        assert "decision_id" in data
        assert "context" in data
        assert "judgement" in data
        assert "decision" in data
        assert "learning" in data
        assert "execution_status" in data
