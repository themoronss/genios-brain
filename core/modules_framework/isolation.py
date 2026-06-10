"""Per-(org, module) isolation enforcement.

Per MD g-i-5 §5.1.2:
- Rules, graph fragments, weights, corrections all namespaced by (org_id, module_id)
- Sales rules NEVER fire in a Finance decision unless explicit cross-domain link
  (cross-domain is post-v1)
- A module bug must NOT corrupt another module's state

Implementation: a small guard object that callers consult before merging
module data or evaluating rules. Cheap, deterministic.
"""

from __future__ import annotations


class IsolationError(Exception):
    """Cross-module / cross-org access attempted. Block + log."""


class IsolationGuard:
    """Carries the active (org_id, module_id) and rejects out-of-context use."""

    def __init__(self, *, org_id: str, module_id: str) -> None:
        if not org_id or not module_id:
            raise IsolationError("IsolationGuard requires non-empty org_id and module_id")
        self._org_id = org_id
        self._module_id = module_id

    @property
    def org_id(self) -> str:
        return self._org_id

    @property
    def module_id(self) -> str:
        return self._module_id

    def require_org(self, claimed_org_id: str) -> None:
        """Caller asserts they're operating in this org. Mismatch -> IsolationError."""
        if claimed_org_id != self._org_id:
            raise IsolationError(
                f"Cross-org access blocked: guard={self._org_id} != claimed={claimed_org_id}"
            )

    def require_module(self, claimed_module_id: str) -> None:
        """Caller asserts they're operating with this module. Mismatch -> IsolationError."""
        if claimed_module_id != self._module_id:
            raise IsolationError(
                f"Cross-module access blocked: guard={self._module_id} != claimed={claimed_module_id}"
            )

    def require_both(self, *, org_id: str, module_id: str) -> None:
        self.require_org(org_id)
        self.require_module(module_id)
