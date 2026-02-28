from core.orchestrator.brain_orchestrator import BrainOrchestrator


def test_orchestrator_pipeline():
    brain = BrainOrchestrator()

    result = brain.run(
        intent="Follow up with Investor X",
        workspace_id="w1",
        actor_id="u1"
    )

    assert "context" in result
    assert "judgement" in result

    assert result["judgement"].needs_approval is True