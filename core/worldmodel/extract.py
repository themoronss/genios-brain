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
    """A typed entity extracted from a MemoryItem. Grounded by source_item_id.

    The 5 NodeType slots (entity/event/goal/risk/dependency) are locked by
    plan; richness lives in `attributes` (JSON dict). Keys we ask the LLM
    to populate when stated: subtype, role, org, email, industry, location,
    amount, due, status. Anything else the LLM volunteers also flows
    through — graph_nodes.attributes is free JSON.
    """

    name: str
    type: NodeType
    aliases: list[str]
    source_item_id: str
    attributes: dict[str, str | int | float | None] | None = None


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
2. Relationships — STATED ones ONLY (e.g., "X works at Y", "A depends on B", "demo happened before close").
   DO NOT infer causation. DO NOT extract "influence" — those come from rules or humans.
3. Allowed entity types: entity, event, goal, risk, dependency.
4. Allowed relationship types: temporal (A before B), dependency (A needs B).
5. Output JSON ONLY. No prose.
6. CAP: at most 25 entities and 25 relations per call. Pick the most central
   ones if the text mentions more — partial coverage is better than truncated JSON.

Per-entity attributes (RICH, but only what's stated — never invent):
  subtype:   "person" | "organization" | "product" | "project" | "document"
             | "deal" | "commitment" | "decision" | "topic" | null
  role:      free text, e.g. "founder", "engineer", "customer", "vendor"  (people only)
  org:       company / organization the entity belongs to                  (people only)
  email:     email address if mentioned                                    (people only)
  industry:  e.g. "fintech", "saas"                                        (organizations)
  location:  city / country if mentioned
  amount:    numeric monetary value if mentioned (e.g. "50000")            (deals)
  due:       ISO date or relative ("by Friday") if mentioned               (commitments)
  status:    if explicitly stated ("open", "closed", "pending", "won", "lost")

Predicate style guide (prefer these verbs when applicable; create new only if
the text genuinely doesn't fit any of them):
  works_at, owns, founded, reports_to, manages, member_of, located_in,
  decided_on, agreed_to, committed_to, owes, due_on, valued_at,
  scheduled_for, met_with, mentioned_in, attended, sourced_from,
  blocked_by, depends_on, happened_before, happened_during, succeeded_by,
  has_skill, certified, educated_at, worked_at, applied_for,
  signed, expires_on, paid_for, replied_to, related_to.
Pick the closest verb. Consistency across calls is more important than
expressiveness — rule engines key off the predicate string.

Format:
{{
  "entities": [
    {{"name": "...", "type": "entity|event|goal|risk|dependency",
      "aliases": ["..."],
      "attributes": {{ "subtype": "...", "role": "...", "org": "..." }}
    }}
  ],
  "relations": [
    {{"subject": "name1", "predicate": "works_at",
      "object": "name2", "edge_type": "temporal|dependency"}}
  ]
}}

Output only the JSON object."""


# ─────────────────────────────────────────────────────────────────────────────
# Extraction
# ─────────────────────────────────────────────────────────────────────────────


def extract(item: MemoryItem, *, org_id: str | None = None) -> Extraction:
    """Run extraction on a single MemoryItem. Returns grounded entities + STATED relations.

    Hard grounding gate: anything that cannot reference item.item_id is DISCARDED.
    LLM = Haiku (per g-i-3 blocker decision); volume is per-item so cost matters.

    org_id (optional): when provided, the LLM call is logged to llm_costs
    with purpose='extract' and source_item_id=item.item_id. Extraction
    itself is 0-credit per MD §8.2 but token usage still gets attributed
    to the org so cost visibility + the daily budget breaker work.
    """
    if not item.content or not item.content.strip():
        return Extraction(item_id=item.item_id, entities=[], relations=[])

    if not settings.ANTHROPIC_API_KEY:
        raise ExtractionError("ANTHROPIC_API_KEY not configured")

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = _PROMPT.format(content=item.content[:8000])  # cap input

    # 4096 is the safe headroom for the 25-entity cap above. The old 1024
    # ceiling silently truncated mid-JSON on dense inputs (a resume could
    # easily list 10+ orgs + 15+ skills) and the whole extract was lost.
    resp = None
    try:
        resp = client.messages.create(
            model=settings.ANTHROPIC_HAIKU_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        if org_id:
            from core.foundations.llm_costs import record_llm_call
            record_llm_call(
                org_id=org_id, model=settings.ANTHROPIC_HAIKU_MODEL,
                purpose="extract", input_tokens=0, output_tokens=0,
                success=False, error=str(e)[:500],
                source_item_id=item.item_id,
            )
        raise ExtractionError(f"Anthropic API call failed: {e}") from e

    # Cost row writes BEFORE parsing so a downstream JSON-parse error still
    # counts the tokens we actually paid for.
    if org_id and resp is not None:
        from core.foundations.llm_costs import record_llm_call, usage_extract
        it, ot = usage_extract(resp)
        record_llm_call(
            org_id=org_id, model=settings.ANTHROPIC_HAIKU_MODEL,
            purpose="extract", input_tokens=it, output_tokens=ot,
            credits_billed=0, source_item_id=item.item_id,
        )

    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
    raw = _strip_code_fence(raw)

    parsed = _parse_json_lenient(raw)
    if parsed is None:
        # Capture the full payload — truncated `raw[:200]` from before hid
        # exactly the part we need (the unterminated tail) and made every
        # failure look the same.
        raise ExtractionError(
            f"LLM returned unparseable JSON (len={len(raw)}): {raw}"
        )

    return _build_extraction(parsed, item.item_id)


def _parse_json_lenient(raw: str) -> dict | None:
    """Try strict json.loads, then a minimal repair for Haiku's two real
    failure modes here: trailing commas, and mid-array truncation when
    max_tokens is hit. Returns the parsed dict or None.

    Strategy on truncation: rewind to the last position where the JSON was
    in a consistent state (depth>0, not inside a string, immediately after
    a `}`, `]`, or numeric/bool/null literal), then close the remaining
    open brackets. This drops the half-written tail entry but keeps every
    completed one — better than losing the whole extract.
    """
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    import re as _re
    cleaned = _re.sub(r",\s*([\]}])", r"\1", raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Walk char-by-char tracking opens + the last "safe stop" index.
    # Safe stop = depth > 0, NOT inside a string, and the previous non-
    # whitespace char closed a value (`}`, `]`, digit, quote, or letter
    # like the end of `true`/`false`/`null`).
    opens: list[str] = []
    in_string = False
    escape = False
    last_safe_idx = -1
    last_safe_opens: list[str] = []
    prev_value_close = False
    for i, ch in enumerate(cleaned):
        if escape:
            escape = False
            prev_value_close = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            if in_string:
                in_string = False
                prev_value_close = True
                if opens:
                    last_safe_idx = i
                    last_safe_opens = list(opens)
            else:
                in_string = True
                prev_value_close = False
            continue
        if in_string:
            continue
        if ch in "[{":
            opens.append(ch)
            prev_value_close = False
        elif ch in "]}":
            if opens and ((opens[-1] == "[" and ch == "]") or (opens[-1] == "{" and ch == "}")):
                opens.pop()
            prev_value_close = True
            if opens:
                last_safe_idx = i
                last_safe_opens = list(opens)
        elif ch.isalnum() and prev_value_close is False:
            # value char — track end of literal (digits / true / false / null)
            prev_value_close = True
        elif ch in ", \n\r\t:":
            # neutral separators don't change "safe" state
            pass

    if last_safe_idx < 0:
        return None
    # Build the suffix that closes everything still open at the safe stop.
    suffix = ""
    for opener in reversed(last_safe_opens):
        suffix += "}" if opener == "{" else "]"
    try:
        return json.loads(cleaned[: last_safe_idx + 1] + suffix)
    except json.JSONDecodeError:
        return None


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
        # Attributes: keep only scalar (str/int/float/bool) values. The LLM
        # sometimes nests dicts (e.g. attributes.contact.email) — those get
        # dropped because the graph_nodes.attributes JSON is intended for
        # flat key/value pairs that rule_engine can match against.
        attrs_raw = e.get("attributes")
        attributes: dict[str, str | int | float | bool] | None = None
        if isinstance(attrs_raw, dict):
            attributes = {
                str(k): v for k, v in attrs_raw.items()
                if isinstance(v, (str, int, float, bool)) and v not in (None, "", "null")
            } or None
        entities.append(
            ExtractedEntity(
                name=name,
                type=NodeType(type_str),
                aliases=aliases,
                source_item_id=item_id,
                attributes=attributes,
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
