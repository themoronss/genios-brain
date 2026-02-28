from layers.layer1_retrieval.retrieval_engine import RetrievalEngine


def test_layer1_returns_context_bundle():
    engine = RetrievalEngine()

    bundle = engine.run(
        intent="Follow up with Investor X",
        workspace_id="w1",
        actor_id="u1"
    )

    assert bundle.scope.workspace_id == "w1"
    assert bundle.memory.preferences["tone"] == "confident"
    assert len(bundle.policy.rules) > 0
    assert "gmail" in bundle.tools.snapshots
    assert bundle.tools.snapshots["gmail"]["thread_exists"] is True