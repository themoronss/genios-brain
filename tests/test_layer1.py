from layers.layer1_retrieval.retrieval_engine import RetrievalEngine


def test_layer1_returns_context_bundle():
    engine = RetrievalEngine()

    bundle = engine.run(
        intent="follow_up_investor",
        workspace_id="w1",
        actor_id="u1"
    )

    assert bundle.scope.workspace_id == "w1"
    assert bundle.memory.preferences["tone"] == "confident"
    assert bundle.policy.rules[0]["id"] == "P_VIP_APPROVAL"
    assert bundle.tools.snapshots["gmail"]["thread_exists"] is True