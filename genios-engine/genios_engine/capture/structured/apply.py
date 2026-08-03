from __future__ import annotations

from typing import Any

from .registry import StructuredMapping

# personal mailbox domains — an attendee here is a person, never evidence of a company
_PERSONAL_DOMAINS = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
                     "yahoo.com", "icloud.com", "proton.me", "protonmail.com"}


def apply_mapping(mapping: StructuredMapping, raw_fields: dict[str, Any]) -> dict[str, Any]:
    """Map a structured source object's fields to target fields per the mapping.
    Deterministic, no LLM. Unknown source fields are ignored (never guessed)."""
    out: dict[str, Any] = {}
    for fm in mapping.fields:
        if fm.source_field in raw_fields:
            out[fm.target] = raw_fields[fm.source_field]
    return out


def _emails_from(value: Any) -> list[tuple[str, str | None]]:
    """Normalise an attendees-style field into (email, display_name) pairs. Accepts a bare
    string, a list of strings, or a list of {email, displayName} dicts (Google/CRM shapes)."""
    items = value if isinstance(value, list) else [value]
    out: list[tuple[str, str | None]] = []
    for it in items:
        if isinstance(it, str):
            email, name = it, None
        elif isinstance(it, dict):
            email, name = it.get("email") or it.get("address"), it.get("displayName") or it.get("name")
        else:
            continue
        if email and "@" in str(email):
            out.append((str(email).strip().lower(), name))
    return out


def apply_relations(mapping: StructuredMapping, raw_fields: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve a structured object's declared relations into edge specs the commit layer can
    write: {node_type, canonical_key, display_name, edge_type, direction}. Deterministic, no LLM.
    Person identity is the lowercased email so attendee-persons MERGE with pipeline-created persons."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rel in mapping.relations:
        raw_val = raw_fields.get(rel.source_field)
        if raw_val in (None, "", []):
            continue
        if rel.identity == "email":
            for email, name in _emails_from(raw_val):
                key = (rel.edge_type, email)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"node_type": rel.related_node_type, "canonical_key": email,
                            "display_name": name or email, "edge_type": rel.edge_type,
                            "direction": rel.direction})
    return out
