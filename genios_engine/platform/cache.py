from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from genios_engine.platform.config import get_settings

# Redis cache — ported from genios-brain/app/redis_client.py, made GRACEFUL-OPTIONAL and
# engine-native. Rules:
#   • No REDIS_URL (or redis not installed) → NullCache no-op → tests + local run never break.
#     Redis is a production ACCELERATOR, not a hard dependency.
#   • Fail-open: any Redis error degrades to a miss/no-op, never breaks a request.
#   • CACHE ONLY — never a Celery/queue broker (Upstash quota law).
#   • Keys are ORG-SCOPED by construction (okey/l2key helpers) so a cache entry can never
#     leak across tenants — this is the fix for the cross-tenant L2 extraction-cache leak.


class NullCache:
    """Used when Redis is unconfigured. Every op is a safe no-op / miss."""
    enabled = False

    def get(self, key: str) -> str | None:
        return None

    def setex(self, key: str, ttl: int, value: str) -> None:
        return None

    def delete(self, *keys: str) -> None:
        return None

    def incr_window(self, key: str, ttl: int) -> int:
        return 0

    def get_json(self, key: str) -> Any | None:
        return None

    def set_json(self, key: str, ttl: int, value: Any) -> None:
        return None


class RedisCache:
    """Thin wrapper over redis-py. TLS-aware for Upstash (rediss://). All ops fail-open."""
    enabled = True

    def __init__(self, client: Any) -> None:
        self._c = client

    def get(self, key: str) -> str | None:
        try:
            v = self._c.get(key)
            return v if v is None or isinstance(v, str) else v.decode()
        except Exception:
            return None

    def setex(self, key: str, ttl: int, value: str) -> None:
        try:
            self._c.setex(key, ttl, value)
        except Exception:
            pass

    def delete(self, *keys: str) -> None:
        try:
            if keys:
                self._c.delete(*keys)
        except Exception:
            pass

    def incr_window(self, key: str, ttl: int) -> int:
        """Sliding-ish fixed-window counter for RPM: INCR then set TTL on first hit."""
        try:
            n = self._c.incr(key)
            if n == 1:
                self._c.expire(key, ttl)
            return int(n)
        except Exception:
            return 0

    def get_json(self, key: str) -> Any | None:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None

    def set_json(self, key: str, ttl: int, value: Any) -> None:
        try:
            self.setex(key, ttl, json.dumps(value, default=str))
        except Exception:
            pass


@lru_cache(maxsize=1)
def get_cache():
    """Process-cached cache handle. RedisCache if REDIS_URL is set AND redis imports, else
    NullCache. Never raises — a bad URL / missing package degrades to NullCache."""
    url = getattr(get_settings(), "redis_url", "") or ""
    if not url:
        return NullCache()
    try:
        import redis  # lazy: only when a URL is configured
        kwargs = {"decode_responses": True}
        if url.startswith("rediss://"):
            kwargs["ssl_cert_reqs"] = "none"          # Upstash / managed TLS
        client = redis.from_url(url, **kwargs)
        client.ping()                                  # validate once; fail → NullCache
        return RedisCache(client)
    except Exception:
        return NullCache()


# ── org-scoped key helpers (tenant isolation by construction) ──────────────────────────
def okey(org_id: str, *parts: str) -> str:
    return "org:" + org_id + ":" + ":".join(parts)


def l2key(org_id: str, content_hash: str) -> str:
    """L2 extraction cache key — ORG-SCOPED so tenant A's extraction can never be served to
    tenant B (the cross-tenant cache-leak fix)."""
    return f"l2:{org_id}:{content_hash}"
