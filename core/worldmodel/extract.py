"""Grounded entity + stated-relationship extraction from MemoryItems.

Per MD g-i-3 §3.1.1:
- NER/LLM-extract typed entities from MemoryItem.content
- Extract STATED relationships only (e.g. "X reports to Y", "A depends on B")
- Causal/influence relationships are NOT extracted here (asserted only via rules/humans)
- Hard grounding gate: entities/relations MUST map to source_item_id, else DISCARD
- LLM call (Haiku) for v1; spaCy fallback can come later if cost demands

This module exposes a pure extract() function; the caller wires it to a session
to persist NodeRow / FactRow updates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from anthropic import Anthropic

from core.foundations.config import settings
from core.foundations.telemetry import get_logger
from core.graph.schema import AssertionSource, EdgeType, NodeType
from core.memory.types import MemoryItem

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExtractedEntity:
    """A typed entity extracted from a MemoryItem. Grounded by source_item_id."""

    name: str
    type: NodeType
    aliases: list[str]
    source_item_id: str


@dataclass(frozen=True)
class ExtractedRelation:
    """A STATED relationship between two entities. Causal/influence excluded.

    edge_type is restricted to TEMPORAL or DEPENDENCY at this layer —
    INFLUENCE never emitted by extraction (per MD hard rule).
    """

    subject: str
    predicate: str
    object: str
    edge_type: EdgeType
    source_item_id: str


@dataclass(frozen=True)
class Extraction:
    """Result of extracting from one MemoryItem."""

    item_id: str
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]


class ExtractionError(Exception):
    """LLM call failed or response unparseable."""


# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────


_PROMPT = """Extract STATED entities and STATED relationships from this text.

Text:
\"\"\"
{content}
\"\"\"

Rules:
1. Entities — extract people, accounts, projects, events, goals, risks, dependencies.
2. Relationships — STATED ones ONLY (e.g., "X is on Y team", "A depends on B", "demo happened before close").
   DO NOT infer causation. DO NOT extract "influence" — those come from rules or humans.
3. Allowed entity types: entity, event, goal, risk, dependency
4. Allowed relationship types: temporal (A before B), dependency (A needs B)
5. Output JSON ONLY. No prose.

Format:
{{
  "entities": [
    {{"name": "...", "type": "entity|event|goal|risk|dependency", "aliases": ["..."]}}
  ],
  "relations": [
    {{"subject": "name1", "predicate": "depends_on|happened_before|...", "object": "name2", "edge_type": "temporal|dependency"}}
  ]
}}

Output only the JSON object."""


# ─────────────────────────────────────────────────────────────────────────────
# Extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract(item: MemoryItem) -> Extraction:
    """Run extraction on a single MemoryItem. Returns grounded entities + STATED relations.

    Hard grounding gate: anything that cannot reference item.item_id is DISCARDED.
    LLM = Haiku (per g-i-3 blocker decision); volume is per-item so cost matters.
    """
    if not item.content or not item.content.strip():
        return Extraction(item_id=item.item_id, entities=[], relations=[])

    if not settings.ANTHROPIC_API_KEY:
        raise ExtractionError("ANTHROPIC_API_KEY not configured")

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = _PROMPT.format(content=item.content[:8000])  # cap input

    resp = client.messages.create(
        model=settings.ANTHROPIC_HAIKU_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
    raw = _strip_code_fence(raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"LLM returned unparseable JSON: {raw[:200]}") from e

    return _build_extraction(parsed, item.item_id)


def _build_extraction(parsed: dict[str, object], item_id: str) -> Extraction:
    """Validate + filter LLM output. Discard anything ungrounded or with disallowed type."""
    entities: list[ExtractedEntity] = []
    entities_raw = parsed.get("entities", []) or []
    if not isinstance(entities_raw, list):
        entities_raw = []
    for e in entities_raw:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name", "")).strip()
        type_str = str(e.get("type", "")).strip().lower()
        if not name or type_str not in {t.value for t in NodeType}:
            continue
        aliases_raw = e.get("aliases", [])
        aliases = (
            [str(a) for a in aliases_raw if isinstance(a, str)]
            if isinstance(aliases_raw, list)
            else []
        )
        entities.append(
            ExtractedEntity(
                name=name,
                type=NodeType(type_str),
                aliases=aliases,
                source_item_id=item_id,
            )
        )

    relations: list[ExtractedRelation] = []
    allowed_edge_types = {EdgeType.TEMPORAL.value, EdgeType.DEPENDENCY.value}
    relations_raw = parsed.get("relations", []) or []
    if not isinstance(relations_raw, list):
        relations_raw = []
    for r in relations_raw:
        if not isinstance(r, dict):
            continue
        edge_type_str = str(r.get("edge_type", "")).strip().lower()
        if edge_type_str not in allowed_edge_types:
            log.info(
                "extraction_relation_dropped", reason="disallowed_edge_type", got=edge_type_str
            )
            continue
        subj = str(r.get("subject", "")).strip()
        obj = str(r.get("object", "")).strip()
        pred = str(r.get("predicate", "")).strip()
        if not subj or not obj or not pred:
            continue
        relations.append(
            ExtractedRelation(
                subject=subj,
                predicate=pred,
                object=obj,
                edge_type=EdgeType(edge_type_str),
                source_item_id=item_id,
            )
        )

    return Extraction(item_id=item_id, entities=entities, relations=relations)


# Convenience constant for callers building Facts from ExtractedRelations
EXTRACTION_ASSERTION_SOURCE = AssertionSource.SOURCE


# ─── helpers ────────────────────────────────────────────────────────────────


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    return s
