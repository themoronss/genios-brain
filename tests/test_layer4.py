from core.orchestrator.brain_orchestrator import BrainOrchestrator


def test_learning_layer():
    brain = BrainOrchestrator()

    result = brain.run(
        intent="follow_up_investor",
        workspace_id="w1",
        actor_id="u1"
    )

    learning = result["learning"]

    assert learning.outcome == "approved"
    assert len(learning.memory_updates) == 1
    assert learning.memory_updates[0].field == "last_successful_intent"