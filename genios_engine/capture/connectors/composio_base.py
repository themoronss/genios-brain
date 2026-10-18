from __future__ import annotations

import concurrent.futures as _futures
from typing import Any

# Hard wall-clock deadline for any single Composio call. A stalled Google/Composio round-trip must
# never block a sync worker indefinitely (there is no SDK-level guarantee), so we run each execute
# on a helper thread and give up after this many seconds — the caller's retry/backoff takes over.
_EXEC_TIMEOUT_S = 90.0


class ProviderRefused(RuntimeError):
    """Composio answered, and the answer was "no".

    Composio reports a tool failure IN the envelope — `{"successful": false, "error": …}` — rather
    than by raising. Read as data, that envelope has no messages and no next page, which is exactly
    what a provider that has run out of mail returns: `run_sync` then files the sweep as finished
    and empty (`cursor_exhausted=True`, no error), and an expired login reads as a quiet inbox. A
    refusal therefore raises, so the run is retried and, failing that, recorded with its error —
    UNKNOWN, never absent.
    """

    def __init__(self, slug: str, error: Any) -> None:
        self.slug = slug
        self.error = error
        super().__init__(f"composio {slug} refused: {error or 'no detail'}")


def raise_if_refused(slug: str, res: Any) -> Any:
    """`res` unchanged, unless it is Composio's failure envelope — then `ProviderRefused`."""
    if isinstance(res, dict) and res.get("successful") is False:
        raise ProviderRefused(slug, res.get("error"))
    return res


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
            # Composio(api_key=...) with no `timeout=` reads as timeout=None from kwargs.get(...),
            # which the SDK's own NotGiven-check treats as "given" — the underlying httpx client
            # ends up with timeout=None (NO bound on connect/read/write) instead of the SDK's
            # documented 60s default. A single stalled socket then hangs forever, and since the
            # scheduler processes connections sequentially on one thread, that one hang freezes
            # every org's sync permanently. Pass it explicitly so httpx actually enforces a bound.
            self._client = Composio(api_key=self._api_key, timeout=60)
        return self._client

    def _raw_execute(self, slug: str, arguments: dict[str, Any]) -> Any:
        return self._c().tools.execute(slug, arguments, user_id=self._user_id,
                                       dangerously_skip_version_check=True)

    def execute(self, slug: str, arguments: dict[str, Any]) -> dict:
        # Bounded by a hard deadline so a hung network call can't wedge the worker forever. NOT a
        # `with ThreadPoolExecutor(...)` block on purpose — its __exit__ calls shutdown(wait=True),
        # which re-blocks on the SAME hung worker thread the instant .result(timeout=...) gives up,
        # making the deadline cosmetic. shutdown(wait=False) lets the caller actually return; the
        # now-explicitly-timeout'd Composio client (see _c()) means the worker exits on its own soon
        # after anyway.
        ex = _futures.ThreadPoolExecutor(max_workers=1)
        try:
            res = ex.submit(self._raw_execute, slug, arguments).result(timeout=_EXEC_TIMEOUT_S)
        finally:
            ex.shutdown(wait=False)
        raise_if_refused(slug, res)
        if isinstance(res, dict):
            return res.get("data", {}) if isinstance(res.get("data"), dict) else res
        return {}
