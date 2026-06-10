"""LLM-proposed mapping for custom sources.

Per g-i-1 §1.2.2 — runs ONCE at setup, NOT per-record:
- Volume: tiny (one call per source)
- Cost: justified by accuracy (wrong mapping silently poisons all downstream)
- Model: HIGH-QUALITY (Sonnet/Opus) — NOT Haiku
- LLM cost cap enforced (one call hard ceiling per source setup)

Flow:
1. Try templates.guess_from_introspection() first (free + reliable)
2. If template fails OR confidence < 0.8, call LLM with introspection + canonical schema
3. Return a draft mapping for human confirm
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from anthropic import Anthropic

from core.foundations.config import settings
from core.foundations.telemetry import get_logger
from core.memory.adapters.custom.inspector import Introspection
from core.memory.adapters.custom.templates import (
    TemplateGuess,
    guess_from_introspection,
)
from core.memory.types import FieldMapping

log = get_logger(__name__)

# Hard ceiling: 1 LLM call per source setup (per g-i-1 acceptance)
_MAX_LLM_CALLS_PER_SOURCE_SETUP = 1


@dataclass(frozen=True)
class MappingProposal:
    """LLM (or template) output for a custom source. Subject to human confirm."""

    field_map: dict[str, FieldMapping]
    overall_confidence: float
    reason: str
    source: str  # "template" | "llm"


class ProposerError(Exception):
    """LLM call failed or response unparseable."""


def propose(
    introspection: Introspection,
    *,
    org_id: str | None = None,
) -> MappingProposal:
    """Return a draft mapping. Tries template-match first; LLM only on miss.

    org_id (optional): when provided, the Sonnet LLM call is logged to
    llm_costs with purpose='custom_mapping' so this one-time-but-pricey
    call shows up in the founder's cost dashboard.
    """
    template_guess = guess_from_introspection(introspection)
    if template_guess is not None:
        log.info(
            "mapping_template_hit",
            source_type=introspection.source_type,
            template=template_guess.template_name,
            confidence=template_guess.confidence,
        )
        return _from_template(template_guess)

    log.info("mapping_llm_call", source_type=introspection.source_type)
    return _from_llm(introspection, org_id=org_id)


# ─────────────────────────────────────────────────────────────────────────────
# Template path (no LLM call — common pattern hit)
# ─────────────────────────────────────────────────────────────────────────────


def _from_template(guess: TemplateGuess) -> MappingProposal:
    return MappingProposal(
        field_map=guess.field_map,
        overall_confidence=guess.confidence,
        reason=f"Matched template '{guess.template_name}' (common field names)",
        source="template",
    )


# ─────────────────────────────────────────────────────────────────────────────
# LLM path (one-time per source — high-quality model)
# ─────────────────────────────────────────────────────────────────────────────


_PROMPT = """You are mapping a customer's source schema to a canonical "MemoryItem" shape.

Canonical fields (always 4):
- content     (REQUIRED) — the main text/body of the record (plain text)
- timestamp   (REQUIRED) — when the record was created/updated (ISO 8601 or epoch)
- owner       (optional) — who the record belongs to (person identifier)
- tags        (optional) — labels/categories (list of strings)

The source fields (observed via sampling/introspection):
{fields_json}

Return a JSON object mapping EACH canonical field present in the source to ONE source field:
{{
  "content":   {{"source_field": "...", "transform": null, "confidence": 0.0-1.0, "reason": "..."}},
  "timestamp": {{"source_field": "...", "transform": "epoch_ms_to_iso8601"|null, "confidence": 0.0-1.0, "reason": "..."}},
  "owner":     {{"source_field": "...", "transform": null, "confidence": 0.0-1.0, "reason": "..."}},
  "tags":      {{"source_field": "...", "transform": null, "confidence": 0.0-1.0, "reason": "..."}}
}}

Rules:
- ONLY fields in the source above. Do NOT invent field names.
- If you cannot confidently map a non-required field, OMIT it (don't guess).
- transform = "epoch_ms_to_iso8601" if timestamp is integer milliseconds since epoch.
- transform = "epoch_s_to_iso8601" if timestamp is integer seconds since epoch.
- Otherwise transform = null.
- confidence reflects YOUR certainty (0.0 to 1.0).

Output JSON only. No prose.
"""


def _from_llm(introspection: Introspection, *, org_id: str | None = None) -> MappingProposal:
    if not settings.ANTHROPIC_API_KEY:
        raise ProposerError("ANTHROPIC_API_KEY not configured — cannot call LLM proposer")

    fields_for_prompt = [
        {
            "name": f.name,
            "type": f.inferred_type,
            "nullable": f.nullable,
            "sample": f.sample_value,
        }
        for f in introspection.fields
    ]
    prompt = _PROMPT.format(fields_json=json.dumps(fields_for_prompt, indent=2))

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=settings.ANTHROPIC_SONNET_MODEL,  # quality > cost for this one-time call
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    # Log to llm_costs — Sonnet is the priciest call we make routinely;
    # custom mappings happen rarely but each one ~$0.10–0.30 so visibility
    # matters for budget surprises.
    if org_id:
        from core.foundations.llm_costs import record_llm_call, usage_extract
        it, ot = usage_extract(resp)
        record_llm_call(
            org_id=org_id,
            model=settings.ANTHROPIC_SONNET_MODEL,
            purpose="custom_mapping",
            input_tokens=it, output_tokens=ot,
        )

    raw = "".join(block.text for block in resp.content if block.type == "text")
    raw = raw.strip()
    # Strip optional ```json fences
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProposerError(f"LLM returned unparseable JSON: {raw[:200]}") from e

    valid_source_fields = {f.name for f in introspection.fields}
    field_map: dict[str, FieldMapping] = {}
    reasons: list[str] = []
    for canonical, entry in parsed.items():
        if canonical not in {"content", "timestamp", "owner", "tags"}:
            continue
        src = entry.get("source_field")
        if src not in valid_source_fields:
            log.warning(
                "llm_proposed_unknown_field",
                canonical=canonical,
                proposed=src,
            )
            continue
        field_map[canonical] = FieldMapping(
            source_field=src,
            transform=entry.get("transform"),
            confidence=float(entry.get("confidence", 0.5)),
        )
        reasons.append(f"{canonical}: {entry.get('reason', '')}")

    if "content" not in field_map or "timestamp" not in field_map:
        raise ProposerError(
            "LLM did not map required canonical fields (content + timestamp). "
            f"Got: {sorted(field_map.keys())}"
        )

    overall = min(fm.confidence for fm in field_map.values())

    return MappingProposal(
        field_map=field_map,
        overall_confidence=overall,
        reason=" | ".join(reasons),
        source="llm",
    )
