from core.orchestrator.brain_orchestrator import BrainOrchestrator


def test_learning_layer():
    brain = BrainOrchestrator()

    result = brain.run(
        intent="Follow up with Investor X",
        workspace_id="w1",
        actor_id="u1"
    )

    learning = result["learning"]

    assert learning.outcome == "approved"
    assert len(learning.memory_updates) >= 1
    assert any(u.field == "last_successful_intent" for u in learning.memory_updates)