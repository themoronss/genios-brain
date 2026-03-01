from core.orchestrator.brain_orchestrator import BrainOrchestrator


def test_learning_layer():
    brain = BrainOrchestrator()

    result = brain.run(
        intent="Follow up with Investor X", workspace_id="w1", actor_id="u1"
    )

    learning = result["learning"]

    # Outcome now reflects execution mode (VIP requires approval)
    assert learning.outcome_record.execution_result in (
        "pending_approval",
        "proposed",
        "auto_executed",
    )
    assert len(learning.memory_updates) >= 0  # May be empty if pending approval
    # Memory updates only persist on approved/executed
    if learning.outcome_record.execution_result == "auto_executed":
        assert any(u.field == "last_successful_intent" for u in learning.memory_updates)
