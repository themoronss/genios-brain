from __future__ import annotations

import concurrent.futures as _futures
from typing import Any

# Hard wall-clock deadline for any single Composio call. A stalled Google/Composio round-trip must
# never block a sync worker indefinitely (there is no SDK-level guarantee), so we run each execute
# on a helper thread and give up after this many seconds — the caller's retry/backoff takes over.
_EXEC_TIMEOUT_S = 90.0


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

    def _raw_execute(self, slug: str, arguments: dict[str, Any]) -> Any:
        return self._c().tools.execute(slug, arguments, user_id=self._user_id,
                                       dangerously_skip_version_check=True)

    def execute(self, slug: str, arguments: dict[str, Any]) -> dict:
        # Bounded by a hard deadline so a hung network call can't wedge the worker forever.
        with _futures.ThreadPoolExecutor(max_workers=1) as ex:
            res = ex.submit(self._raw_execute, slug, arguments).result(timeout=_EXEC_TIMEOUT_S)
        if isinstance(res, dict):
            return res.get("data", {}) if isinstance(res.get("data"), dict) else res
        return {}
