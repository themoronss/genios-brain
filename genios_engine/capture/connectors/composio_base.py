from __future__ import annotations

from typing import Any


class ComposioExec:
    """Shared Composio client + execute for every source connector. Composio sits
    BEHIND our SourceConnector interface (auth + data delivery only). Returns the
    `data` dict of the tool response. Version check skipped for the trial (TODO: pin)."""

    def __init__(self, *, api_key: str, user_id: str) -> None:
        self._api_key = api_key
        self._user_id = user_id
        self._client: Any = None

    def _c(self) -> Any:
        if self._client is None:
            from composio import Composio        # lazy: only on real runs
            self._client = Composio(api_key=self._api_key)
        return self._client

    def execute(self, slug: str, arguments: dict[str, Any]) -> dict:
        res = self._c().tools.execute(slug, arguments, user_id=self._user_id,
                                      dangerously_skip_version_check=True)
        if isinstance(res, dict):
            return res.get("data", {}) if isinstance(res.get("data"), dict) else res
        return {}
