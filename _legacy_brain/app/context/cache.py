import hashlib
import json
from uuid import UUID
from datetime import datetime
from app.redis_client import redis_client


def _json_serializer(obj):
    """
    Custom JSON serializer for objects not serializable by default.
    """
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


CACHE_TTL_SECONDS = int(__import__("os").getenv("GENIOS_CACHE_TTL_SECONDS", "300"))


def _generate_cache_key(org_id: str, entity: str = "", situation: str = "") -> str:
    """
    Generate a cache key for the context bundle.

    Format: ctx:{org_id}:{hash}
    Hash includes entity + situation so different entities never share a cache
    entry (fixes the "situation-only key" bug from L1 diagram).
    """
    normalized = f"{org_id}:{(entity or '').strip().lower()}:{(situation or '').strip().lower()[:100]}"
    hash_digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"ctx:{org_id}:{hash_digest}"


def get_cached_context(org_id: str, entity: str = "", situation: str = ""):
    """
    Retrieve cached context bundle from Redis.
    """
    cache_key = _generate_cache_key(org_id, entity, situation)

    try:
        cached_data = redis_client.get(cache_key)

        if cached_data:
            # Parse JSON string back to dict
            return json.loads(cached_data)

        return None
    except Exception as e:
        # Log error but don't fail - just return None to trigger fresh generation
        print(f"Cache read error: {e}")
        return None


def set_cached_context(org_id: str, entity: str = "", situation: str = "", bundle: dict = None):
    """
    Store context bundle in Redis cache.
    TTL default 300s (5 min) — env-overridable via GENIOS_CACHE_TTL_SECONDS.
    """
    cache_key = _generate_cache_key(org_id, entity, situation)

    try:
        cached_data = json.dumps(bundle or {}, default=_json_serializer)
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, cached_data)

        return True
    except Exception as e:
        # Log error but don't fail the request
        print(f"Cache write error: {e}")
        return False
