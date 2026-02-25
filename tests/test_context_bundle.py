from core.contracts.context_bundle import ContextBundle, ScopeContext, MemoryContext, PolicyContext, ToolContext


def test_context_bundle_creation():
    bundle = ContextBundle(
        scope=ScopeContext(
            workspace_id="w1",
            actor_id="u1",
            role="founder"
        ),
        memory=MemoryContext(),
        policy=PolicyContext(),
        tools=ToolContext()
    )

    assert bundle.scope.workspace_id == "w1"
    assert bundle.scope.role == "founder"