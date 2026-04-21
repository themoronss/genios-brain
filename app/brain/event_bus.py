"""Event bus on Redis Streams.

Why Redis Streams: durable, consumer groups, ack+redelivery — enough for the
reasoning loop at our scale. Same interface you'd expose over NATS, so a
later swap stays contained to this file.

Upstash-friendly: short-poll `XREADGROUP BLOCK 1000ms` (no infinite block —
serverless cuts idle conns). Every publish caps the stream length so memory
stays bounded.
"""
from __future__ import annotations

import json
import logging
import socket
from typing import Iterable

import redis.exceptions

from app import config
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_STREAM = config.GENIOS_EVENT_STREAM
_GROUP = config.GENIOS_EVENT_GROUP
_MAXLEN = config.GENIOS_EVENT_MAXLEN
_CONSUMER = f"brain-{socket.gethostname()}"


def _ensure_group() -> None:
    """Create consumer group if it doesn't exist (MKSTREAM creates the stream too)."""
    try:
        redis_client.xgroup_create(name=_STREAM, groupname=_GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            return
        raise


def publish(event_type: str, payload: dict) -> str:
    """Append an event to the stream. Returns the Redis entry id.

    Payload is JSON-encoded in a single 'data' field so the consumer reads
    one value regardless of schema drift.
    """
    body = {
        "event_type": event_type,
        "data": json.dumps(payload, default=str),
    }
    return redis_client.xadd(_STREAM, body, maxlen=_MAXLEN, approximate=True)


def consume_batch(count: int = 100, block_ms: int = 1000) -> list[tuple[str, dict]]:
    """Pull up to `count` pending entries for this consumer.

    Returns list of (entry_id, parsed_payload). Empty list if nothing ready.
    Caller must `ack(entry_id)` for each successfully processed entry.
    """
    _ensure_group()
    try:
        resp = redis_client.xreadgroup(
            groupname=_GROUP,
            consumername=_CONSUMER,
            streams={_STREAM: ">"},
            count=count,
            block=block_ms,
        )
    except redis.exceptions.ResponseError as e:
        # Group/stream dropped — recreate and retry once.
        logger.warning(f"xreadgroup error: {e}; recreating group")
        _ensure_group()
        return []

    if not resp:
        return []

    out: list[tuple[str, dict]] = []
    for _stream_name, entries in resp:
        for entry_id, body in entries:
            try:
                payload = json.loads(body.get("data", "{}"))
                payload["_event_type"] = body.get("event_type")
            except Exception as e:
                logger.warning(f"bad event {entry_id}: {e}")
                payload = {"_event_type": body.get("event_type"), "_error": str(e)}
            out.append((entry_id, payload))
    return out


def ack(entry_ids: Iterable[str]) -> int:
    ids = list(entry_ids)
    if not ids:
        return 0
    return redis_client.xack(_STREAM, _GROUP, *ids)


def stream_length() -> int:
    try:
        return redis_client.xlen(_STREAM)
    except redis.exceptions.ResponseError:
        return 0
