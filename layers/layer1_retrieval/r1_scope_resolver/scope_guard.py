"""
R1.3 — Scope Guard

Validates retrieval stays within tenant boundaries.
Produces ScopeContext for the ContextBundle.
"""

from core.contracts.context_bundle import ScopeContext
from layers.layer1_retrieval.r1_scope_resolver.workspace_resolver import resolve_workspace
from layers.layer1_retrieval.r1_scope_resolver.actor_resolver import resolve_actor


def resolve_scope(workspace_id: str, actor_id: str) -> ScopeContext:
    """
    Full scope resolution: validate workspace + actor, produce ScopeContext.

    Args:
        workspace_id: Workspace to resolve.
        actor_id: Actor to resolve.

    Returns:
        ScopeContext with resolved permissions.

    Raises:
        ValueError: If workspace or actor is invalid.
        PermissionError: If actor doesn't belong to workspace.
    """
    workspace = resolve_workspace(workspace_id)
    actor = resolve_actor(actor_id)

    return ScopeContext(
        workspace_id=workspace["workspace_id"],
        actor_id=actor["actor_id"],
        role=actor["role"],
        permissions=actor.get("permissions", []),
    )


def check_permission(scope: ScopeContext, required_permission: str) -> bool:
    """Check if scope has a required permission."""
    return required_permission in scope.permissions
