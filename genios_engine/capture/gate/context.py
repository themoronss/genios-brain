from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.contracts.source_event import SourceEvent


@dataclass
class GateContext:
    event: SourceEvent
    prepared: PreparedContent | None = None
    raw: dict[str, Any] = field(default_factory=dict)      # subject, headers, snippet, flags
    is_structured: bool = False
    structured_fields: dict[str, Any] = field(default_factory=dict)
    #: The version stamp a MUTABLE object arrived with — `updatedAt`, `etag`, `updated`.
    #:
    #: It lives on `RawObject` and is folded into the dedup key, but never reached the gate, so a
    #: rule about versioning had nothing to read. Carrying it explicitly is what lets the gate
    #: tell "this changing object has no version" (undedupable, freezes at first sight) from
    #: "this source does not version because it does not change".
    content_version: str | None = None
    sender_known: bool = False                             # deterministic (CRM/linkage)
    active_domains: list[str] = field(default_factory=list)
    in_scope: bool = True


@dataclass
class GateResult:
    action: str                          # route | drop | park | short_circuit
    reason_code: str | None = None
    route: str | None = None             # needs_extraction | structured
    whitelist_code: str | None = None
