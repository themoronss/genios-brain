"""The shipped projections a structured object takes into L2 — values, and edges.

Both go through `targets.sift_mapping_targets` first, and that is the whole of W2's residual
sink-hole fix. `commit_structured` writes what these two functions return straight into the
graph — ``write_fact(field=<target>)`` and ``write_edge(edge_type=<edge_type>)`` — so a name that
gets past here is a name that is stored, and `FieldMap.target` is a string a customer types into
`GENIOS_STRUCTURED_MAPPINGS`. Sifting HERE rather than at each call site is what closes both
production paths at once: `capture/pipeline.py`'s structured route and `context/runner.py`'s L2
drain call these two functions and nothing else.
"""

from __future__ import annotations

from typing import Any

from genios_engine.platform.identity import norm_email

from .registry import StructuredMapping
from .targets import sift_mapping_targets

# personal mailbox domains — an attendee here is a person, never evidence of a company
_PERSONAL_DOMAINS = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
                     "yahoo.com", "icloud.com", "proton.me", "protonmail.com"}


def apply_mapping(mapping: StructuredMapping, raw_fields: dict[str, Any]) -> dict[str, Any]:
    """Map a structured source object's fields to target fields per the mapping.

    Deterministic, no LLM. Unknown source fields are ignored (never guessed), and a target name
    the graph cannot be queried by is REFUSED — `sift_mapping_targets` decides which, and hands
    the refused name to the open lane instead of to `write_fact`.

    A dict, still, because `commit_structured` and `GatedEvent.structured_fields` take one; what
    changed is that every key in it is now a name a rule can address. `sift_mapping_targets` is
    pure and idempotent, so putting it on this path costs one pass over the mapping's declared
    fields and nothing else.
    """
    fields = dict(sift_mapping_targets(mapping, raw_fields).fields)
    # WHOSE MONEY, when the mapping knows. Written here rather than in either caller because
    # this module's own docstring states that `capture/pipeline.py`'s structured route and
    # `context/runner.py`'s L2 drain "call these two functions and nothing else" — so one seam
    # covers both production paths.
    #
    # ONLY WHEN DECLARED. An undeclared mapping writes no fact, which keeps "we do not know
    # whose money this is" distinguishable from "it is ours" — the distinction the whole field
    # exists for, and one a default would destroy on every source written before it.
    if mapping.money_direction:
        fields[f"{mapping.namespace}.money_direction"] = mapping.money_direction
    return fields


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
        canonical = norm_email(email)
        if canonical:
            out.append((canonical, name))
    return out


def apply_relations(mapping: StructuredMapping, raw_fields: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve a structured object's declared relations into edge specs the commit layer can
    write: {node_type, canonical_key, display_name, edge_type, direction}. Deterministic, no LLM.
    Person identity is the lowercased email so attendee-persons MERGE with pipeline-created
    persons."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    # The SIFTED relations: `edge_type` and `related_node_type` are written into the graph as an
    # edge kind and a node kind, so a relation naming either in a form no query uses is refused
    # into the open lane exactly as a bad field target is.
    for rel in sift_mapping_targets(mapping, raw_fields).mapping.relations:
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
