"""
R1.2 — Actor Resolver

Resolve actor role and permissions.
"""


# MVP: hardcoded actor registry.
# In production this queries an actors/users table.
_ACTOR_REGISTRY: dict[str, dict] = {
    "u1": {
        "actor_id": "u1",
        "role": "founder",
        "permissions": ["read", "write", "approve", "send_email", "schedule"],
    },
    "u2": {
        "actor_id": "u2",
        "role": "employee",
        "permissions": ["read", "write"],
    },
}


def resolve_actor(actor_id: str) -> dict:
    """
    Look up actor role and permissions.

    Args:
        actor_id: The actor identifier.

    Returns:
        Dict with role and permissions.

    Raises:
        ValueError: If actor not found.
    """
    actor = _ACTOR_REGISTRY.get(actor_id)
    if not actor:
        raise ValueError(f"Unknown actor: {actor_id}")
    return actor
