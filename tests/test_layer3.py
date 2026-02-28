from core.orchestrator.brain_orchestrator import BrainOrchestrator


def test_decision_layer_execution_mode():
    brain = BrainOrchestrator()

    result = brain.run(
        intent="Follow up with Investor X",
        workspace_id="w1",
        actor_id="u1"
    )

    decision = result["decision"]

    assert decision.intent_type == "follow_up"
    assert decision.execution_mode == "needs_approval"
    assert len(decision.action_plan.steps) >= 2