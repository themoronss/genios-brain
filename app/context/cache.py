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


def _generate_cache_key(org_id: str, situation: str) -> str:
    """
    Generate a cache key for the context bundle.

    Format: ctx:{org_id}:{hash}
    Hash: First 16 characters of sha256(situation)

    Args:
        org_id: Organization ID
        situation: The situation text

    Returns:
        Cache key string
    """
    # Create hash from situation only
    hash_digest = hashlib.sha256(situation.encode()).hexdigest()[:16]

    return f"ctx:{org_id}:{hash_digest}"


def get_cached_context(org_id: str, situation: str):
    """
    Retrieve cached context bundle from Redis.

    Args:
        org_id: Organization ID
        situation: The situation text

    Returns:
        Cached context bundle (dict) or None if not found
    """
    cache_key = _generate_cache_key(org_id, situation)

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


def set_cached_context(org_id: str, situation: str, bundle: dict):
    """
    Store context bundle in Redis cache.

    Args:
        org_id: Organization ID
        situation: The situation text
        bundle: The context bundle to cache

    Returns:
        True if successful, False otherwise
    """
    cache_key = _generate_cache_key(org_id, situation)

    try:
        # Convert dict to JSON string with custom serializer
        cached_data = json.dumps(bundle, default=_json_serializer)

        # Store with 60 second TTL
        redis_client.setex(cache_key, 60, cached_data)

        return True
    except Exception as e:
        # Log error but don't fail the request
        print(f"Cache write error: {e}")
        return False
