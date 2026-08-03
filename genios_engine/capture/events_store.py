from __future__ import annotations

import hashlib
import json
from typing import Protocol

from sqlalchemy import text

from genios_engine.contracts.events import AgentEvent, HumanEvent
from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class HumanEventStore(Protocol):
    def add(self, ev: HumanEvent) -> None: ...


class AgentEventStore(Protocol):
    def add(self, ev: AgentEvent) -> bool: ...     # True if new, False if duplicate


class InMemoryHumanEventStore:
    def __init__(self) -> None:
        self.events: list[HumanEvent] = []

    def add(self, ev: HumanEvent) -> None:
        self.events.append(ev)


class InMemoryAgentEventStore:
    def __init__(self) -> None:
        self._seen: dict[str, AgentEvent] = {}

    def add(self, ev: AgentEvent) -> bool:
        if ev.idempotency_key in self._seen:
            return False
        self._seen[ev.idempotency_key] = ev
        return True


class PostgresHumanEventStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def add(self, ev: HumanEvent) -> None:
        with self._engine.begin() as c:
            c.execute(text(
                """insert into human_events (id, org_id, type, actor_id, target, detail, occurred_at)
                   values (:id, :org_id, :type, :actor_id, cast(:target as jsonb),
                           cast(:detail as jsonb), :occurred_at)"""),
                {"id": new_id("hev"), "org_id": ev.org_id, "type": ev.type,
                 "actor_id": ev.actor_id, "target": json.dumps(ev.target, default=str),
                 "detail": json.dumps(ev.detail, default=str), "occurred_at": ev.occurred_at})


class PostgresAgentEventStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def add(self, ev: AgentEvent) -> bool:
        with self._engine.begin() as c:
            r = c.execute(text(
                """insert into agent_events
                   (id, org_id, agent_id, client_event_id, action_taken, target_hint, result, occurred_at)
                   values (:id, :org_id, :agent_id, :client_event_id, :action_taken,
                           cast(:target_hint as jsonb), :result, :occurred_at)
                   on conflict (org_id, agent_id, client_event_id) do nothing"""),
                {"id": new_id("aev"), "org_id": ev.org_id, "agent_id": ev.agent_id,
                 "client_event_id": ev.client_event_id, "action_taken": ev.action_taken,
                 "target_hint": json.dumps(ev.target_hint, default=str), "result": ev.result,
                 "occurred_at": ev.occurred_at})
            return r.rowcount > 0


# ── agent registry: per-org agent identity + key + allowed actions ────────────────
class AgentRegistryStore(Protocol):
    def register(self, org_id: str, agent_id: str, raw_key: str,
                 allowed_actions: list[str]) -> None: ...
    def verify(self, org_id: str, agent_id: str, raw_key: str, action: str) -> bool: ...


class InMemoryAgentRegistryStore:
    def __init__(self) -> None:
        self._by: dict[tuple[str, str], tuple[str, set[str]]] = {}

    def register(self, org_id, agent_id, raw_key, allowed_actions):
        self._by[(org_id, agent_id)] = (hash_key(raw_key), set(allowed_actions))

    def verify(self, org_id, agent_id, raw_key, action):
        row = self._by.get((org_id, agent_id))
        return bool(row) and row[0] == hash_key(raw_key) and action in row[1]


class PostgresAgentRegistryStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def register(self, org_id, agent_id, raw_key, allowed_actions):
        # UPSERT on (org_id, agent_id) — only key_hash + allowed_actions move; the dashboard's
        # scope/status/name columns are PRESERVED (a plain DELETE+INSERT wiped them). Also removes
        # the old TOCTOU race (relies on the unique index added in 0017).
        with self._engine.begin() as c:
            c.execute(text(
                "insert into agent_registry (id, org_id, agent_id, key_hash, allowed_actions) "
                "values (:id, :o, :a, :kh, :aa) "
                "on conflict (org_id, agent_id) do update set "
                "key_hash=excluded.key_hash, allowed_actions=excluded.allowed_actions"),
                {"id": new_id("areg"), "o": org_id, "a": agent_id,
                 "kh": hash_key(raw_key), "aa": list(allowed_actions)})

    def verify(self, org_id, agent_id, raw_key, action):
        # status filter: an archived (off-boarded) agent's key must STOP authenticating — archive
        # sets status='archived', and this is where that revocation takes effect.
        with self._engine.connect() as c:
            r = c.execute(text("select key_hash, allowed_actions from agent_registry "
                               "where org_id=:o and agent_id=:a "
                               "and coalesce(status,'active') <> 'archived'"),
                          {"o": org_id, "a": agent_id}).first()
        return bool(r) and r.key_hash == hash_key(raw_key) and action in (r.allowed_actions or [])
