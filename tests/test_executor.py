"""
Test Execution Adapter for Gmail/Calendar tool call execution.
"""

from core.execution.executor import ExecutionAdapter, ExecutionResult
from core.contracts.decision_packet import (
    ActionPlan,
    ActionStep,
    ToolCallDraft,
)


def test_executor_simulation_mode():
    """Test executor in simulation mode (no real API calls)."""
    executor = ExecutionAdapter(use_real_tools=False)

    # Create action plan with Gmail draft call
    plan = ActionPlan(
        steps=[
            ActionStep(
                description="Draft follow-up email",
                tool="gmail",
                order=1,
            ),
        ],
        tool_calls=[
            ToolCallDraft(
                tool_name="gmail",
                method="draft_reply",
                payload={
                    "thread_id": "t_123",
                    "subject": "Follow-up",
                    "body": "Test body",
                },
            ),
        ],
    )

    # Execute in simulation
    result = executor.execute(plan, execution_mode="auto_execute")

    assert result.status == "simulated" or result.status == "success"
    assert len(result.errors) == 0


def test_executor_propose_only_mode():
    """Test executor does not execute in propose_only mode."""
    executor = ExecutionAdapter(use_real_tools=False)

    plan = ActionPlan(
        tool_calls=[
            ToolCallDraft(
                tool_name="gmail",
                method="draft_reply",
                payload={"thread_id": "t_123"},
            ),
        ],
    )

    result = executor.execute(plan, execution_mode="propose_only")

    assert result.status == "success"
    assert len(result.tool_results) == 0


def test_executor_needs_approval_mode():
    """Test executor does not execute in needs_approval mode."""
    executor = ExecutionAdapter(use_real_tools=False)

    plan = ActionPlan(
        tool_calls=[
            ToolCallDraft(
                tool_name="gmail",
                method="send",
                payload={"to": "test@example.com"},
            ),
        ],
    )

    result = executor.execute(plan, execution_mode="needs_approval")

    assert result.status == "pending"
    assert len(result.tool_results) == 0


def test_executor_calendar_simulation():
    """Test Calendar execution in simulation mode."""
    executor = ExecutionAdapter(use_real_tools=False)

    plan = ActionPlan(
        tool_calls=[
            ToolCallDraft(
                tool_name="calendar",
                method="create",
                payload={
                    "summary": "Team Meeting",
                    "start_time": "2026-03-02T10:00:00Z",
                    "end_time": "2026-03-02T11:00:00Z",
                    "attendees": ["john@example.com"],
                },
            ),
        ],
    )

    result = executor.execute(plan, execution_mode="auto_execute")

    # Simulates without real API
    assert result.status in ("success", "simulated")
    assert len(result.errors) == 0


def test_executor_approval_gate_tool():
    """Test executor handles approval_gate tool correctly."""
    executor = ExecutionAdapter(use_real_tools=False)

    plan = ActionPlan(
        tool_calls=[
            ToolCallDraft(
                tool_name="approval_gate",
                method="request_approval",
                payload={"approver": "founder"},
            ),
        ],
    )

    result = executor.execute(plan, execution_mode="auto_execute")

    assert result.status == "success"
    assert result.tool_results.get("approval_gate") == {"status": "pending_approval"}
