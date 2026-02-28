"""
R1.1 — Workspace Resolver

Resolve workspace metadata and validate workspace exists.
"""


# MVP: hardcoded workspace registry.
# In production this queries a workspaces table in Supabase.
_WORKSPACE_REGISTRY: dict[str, dict] = {
    "w1": {
        "workspace_id": "w1",
        "name": "GeniOS Demo Workspace",
        "plan": "pro",
        "connected_tools": ["gmail", "calendar"],
    },
}


def resolve_workspace(workspace_id: str) -> dict:
    """
    Look up workspace metadata.

    Args:
        workspace_id: The workspace identifier.

    Returns:
        Dict with workspace info.

    Raises:
        ValueError: If workspace not found.
    """
    ws = _WORKSPACE_REGISTRY.get(workspace_id)
    if not ws:
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return ws
