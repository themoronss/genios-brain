"""Layer 4 · R-1, TEST MODE — the ambiguity interpreter as a language model.

**What R-1 is today** (`reason/interpretation.py`). A deterministic gate decides WHEN a model may
look: the field must be read by the plan, be free text of 24-400 characters, and contain a word
from a CLOSED hedge list ("might", "considering", "shayad" ...) or carry an unresolved Layer 1
conflict; at most three per situation. The model then sees ONE sentence and returns one of six
stances with a confidence of 2,000-8,000. The reading enters the snapshot as `interpretation.*`
and as evidence in the unattributed pool, so it can lower a confidence and never raise one.
It has never fired on the pilot tenant: it runs only when the compiled lane is live AND `bundle`
is activated, and the legacy lane never calls it.

**What this changes, with `GENIOS_L4_LLM_DECISION_MAKER` on.** The two deterministic halves are
handed to the model:

* **WHEN to read** — instead of the hedge list and the length band, the model is shown every
  worded fact on the subject, every unresolved conflict, and the subject's recent messages
  (Layer 1's extraction, the same lines the decision maker reads), and it judges which are
  genuinely ambiguous. One batched call per situation, not one per sentence.
* **WHAT it reads** — whole message summaries, not a single sentence.

**What stays exactly as R-1 decided it**, because each is a safety property rather than a
judgement: the closed stance enum, the 2,000-8,000 band, at most three readings per situation,
the one-hop law (a snapshot that already carries `interpretation.*` is never read again), and the
unattributed evidence pool. The readings enter through R-1's own `augment`.

It runs only for a run that is about to reach the decision maker — `reason/orchestrator.py` calls
it after the units, and re-executes once on the augmented request so every stored hash describes
the snapshot the decision was actually made on. A gate miss never pays for a reading.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Any

from genios_engine.contracts.reasoning import ReasoningRequest
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason.evidence import observed_at_key
from genios_engine.reason.interpretation import (
    AMBIGUITY_CONFLICT,
    AMBIGUITY_LLM,
    CLASSIFICATION_MEANINGS,
    CLASSIFICATIONS,
    HEDGE_MARKERS,
    INTERPRETATION_NAMESPACE,
    MAX_FLAGS_PER_SITUATION,
    MAX_INTERPRETATION_BP,
    MAX_SPAN_CHARS,
    MIN_INTERPRETATION_BP,
    NOT_INTERPRETABLE,
    AmbiguityFlag,
    Interpretation,
    _conflicted_fields,
    _fact_text,
    augment,
    fact_digest,
)
from genios_engine.reason.llm_sites import OUTCOME_RAN, SITE_R1, SiteReceipt

_log = logging.getLogger(__name__)

PROMPT_VERSION = "r1-llm.v1"
COST_PURPOSE = "l4_llm_r1"
#: How many items one call may be shown. The readings kept are still capped at R-1's three.
MAX_ITEMS = 12
_CONFLICT_PREFIX = "situation.conflict."
_MAX_TOKENS = 700
_CACHE_CAP = 4_096
_cache: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
_lock = threading.Lock()


class _Refused(Exception):
    pass


def already_interpreted(request: ReasoningRequest) -> bool:
    """R-1's one-hop law: a snapshot that carries a reading is never read again."""
    return any(name.startswith(INTERPRETATION_NAMESPACE) for name in request.context.facts)


def _short(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def candidate_items(request: ReasoningRequest, business: Sequence[str]) -> list[dict[str, Any]]:
    """Everything worth reading, with no hedge or length gate — the model decides what is ambiguous.

    Conflicts first (Layer 1 already said they are contested), then worded facts by name, then the
    subject's messages newest first; capped at :data:`MAX_ITEMS`.
    """
    snapshot = request.context
    absent = set(snapshot.missing_fields)
    conflicted = _conflicted_fields(snapshot.facts)
    items: list[dict[str, Any]] = []
    for field in sorted(snapshot.facts):
        if (field.startswith(INTERPRETATION_NAMESPACE) or field.startswith(_CONFLICT_PREFIX)
                or field in absent):
            continue
        text = _fact_text(snapshot.facts[field])
        if text is None:
            continue
        items.append({"field": field, "text": text[:MAX_SPAN_CHARS],
                      "conflict": field in conflicted})
    listed = {item["field"] for item in items}
    for field in sorted(conflicted - listed):
        record = snapshot.facts.get(f"{_CONFLICT_PREFIX}{field}")
        items.append({"field": field, "text": _short(record, MAX_SPAN_CHARS), "conflict": True})
    for number, line in enumerate((ln for ln in business if ln.startswith("- message ")), 1):
        items.append({"field": f"mailbox.message_{number}", "text": line[2:][:MAX_SPAN_CHARS],
                      "conflict": False})
    items.sort(key=lambda item: not item["conflict"])          # stable: conflicts first
    return items[:MAX_ITEMS]


def build_prompt(items: Sequence[Mapping[str, Any]], feedback: str | None = None) -> str:
    options = "\n".join(f"  {name} — {CLASSIFICATION_MEANINGS[name]}" for name in CLASSIFICATIONS)
    listing = "\n".join(
        f"{number}. [{item['field']}{' — THE RECORD DISAGREES ABOUT THIS' if item['conflict'] else ''}]"
        f" {item['text']}" for number, item in enumerate(items, 1))
    prompt = (
        "You are R1, the reader inside GeniOS's reasoning layer. Below are numbered items: facts "
        "written in words, disagreements the record could not settle, and summaries of a "
        "counterparty's recent messages. For EACH item decide:\n"
        "1. ambiguous — true only when the wording leaves the writer's position genuinely "
        "uncertain: hedged (words like " + ", ".join(f"'{m}'" for m in HEDGE_MARKERS[:14])
        + ", 'shayad', 'dekhte hain'), speculative, or contradicted by another record. A settled, "
        "plain statement is false.\n"
        "2. classification — the stance the writer takes, exactly one of:\n" + options + "\n"
        f"3. confidence_bp — an integer {MIN_INTERPRETATION_BP}-{MAX_INTERPRETATION_BP}: how sure "
        "you are of the stance.\n"
        "You are not advising anyone and you are not judging importance, urgency or risk. If an "
        "item carries no stance, answer NOT_INTERPRETABLE — do not guess.\n\n"
        f"ITEMS:\n{listing}\n\n"
        "Answer with ONLY this JSON, one entry per item:\n"
        '{"readings": [{"item": <number>, "ambiguous": true|false, '
        '"classification": "<one of the names above>", "confidence_bp": <integer>}]}')
    if feedback:
        prompt += f"\n\nCORRECTION — your previous answer was refused. {feedback}"
    return prompt


def parse_readings(parsed: Any, count: int) -> list[dict[str, Any]]:
    """Refuses rather than repairs, exactly as R-1's `_parse` does."""
    readings = parsed.get("readings") if isinstance(parsed, Mapping) else None
    if not isinstance(readings, list):
        raise _Refused("'readings' must be a list")
    out: list[dict[str, Any]] = []
    for entry in readings:
        if not isinstance(entry, Mapping):
            raise _Refused("each reading must be an object")
        item = entry.get("item")
        if isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= count:
            raise _Refused(f"'item' must be a number from 1 to {count}")
        classification = str(entry.get("classification") or "").strip().upper()
        if classification not in CLASSIFICATIONS:
            raise _Refused("classification must be one of the listed names")
        confidence = entry.get("confidence_bp")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) \
                or not MIN_INTERPRETATION_BP <= int(confidence) <= MAX_INTERPRETATION_BP:
            raise _Refused(f"confidence_bp must be {MIN_INTERPRETATION_BP}-{MAX_INTERPRETATION_BP}")
        ambiguous = entry.get("ambiguous")
        if not isinstance(ambiguous, bool):
            raise _Refused("'ambiguous' must be true or false")
        out.append({"item": item, "classification": classification,
                    "confidence_bp": int(confidence), "ambiguous": ambiguous})
    return out


def _consult(request: ReasoningRequest, items: Sequence[Mapping[str, Any]], llm: Any
             ) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    from genios_engine.reason import llm_decision_maker as llm_dm

    model = str(getattr(llm, "model", "") or "unknown")
    key = semantic_hash({"prompt": PROMPT_VERSION, "model": model, "org": str(request.org_id),
                         "context": request.context.context_snapshot_id, "items": list(items)})
    meta: dict[str, Any] = {"model": model, "key": key, "input_tokens": 0, "output_tokens": 0}
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return [dict(r) for r in hit], meta
    if not llm_dm._take_budget(request.org_id):
        return None, meta
    subject_ref = f"node:{request.context.root_entity_id}"
    feedback: str | None = None
    for attempt in range(2):
        prompt = build_prompt(items, feedback)
        try:
            res = llm.call(prompt, max_tokens=_MAX_TOKENS)
        except Exception as exc:      # noqa: BLE001 — no reading is the honest fallback
            llm_dm._record_cost(org_id=request.org_id, model=model, subject_ref=subject_ref,
                                input_tokens=0, output_tokens=0, success=False,
                                error=str(exc)[:300], purpose=COST_PURPOSE)
            return None, meta
        llm_dm._debug_dump(request, attempt, prompt, res, tag="r1")
        meta["input_tokens"] += int(getattr(res, "input_tokens", 0) or 0)
        meta["output_tokens"] += int(getattr(res, "output_tokens", 0) or 0)
        llm_dm._record_cost(org_id=request.org_id, model=model, subject_ref=subject_ref,
                            input_tokens=getattr(res, "input_tokens", 0),
                            output_tokens=getattr(res, "output_tokens", 0),
                            success=bool(getattr(res, "ok", False)),
                            error=getattr(res, "error", None), purpose=COST_PURPOSE)
        if not getattr(res, "ok", False):
            if not getattr(res, "raw", ""):
                return None, meta
            feedback = "Your previous answer was not valid JSON. Return only the JSON object."
            continue
        try:
            readings = parse_readings(res.parsed, len(items))
        except _Refused as refusal:
            feedback = f"{refusal}. Follow the requested JSON shape exactly."
            continue
        with _lock:
            _cache[key] = [dict(r) for r in readings]
            _cache.move_to_end(key)
            while len(_cache) > _CACHE_CAP:
                _cache.popitem(last=False)
        return readings, meta
    return None, meta


def interpret_request(request: ReasoningRequest, llm: Any) -> ReasoningRequest:
    """R-1 with the model deciding what is ambiguous. Returns the SAME request when nothing is added.

    Never raises: a failed reading is no reading, and the run proceeds exactly as it would have
    without R-1 — the same silence R-1's own gate falls back to.
    """
    if llm is None or already_interpreted(request):
        return request
    try:
        from genios_engine.reason import llm_decision_maker as llm_dm
        items = candidate_items(request, llm_dm.business_context(request))
        if not items:
            return request
        readings, meta = _consult(request, items, llm)
        if not readings:
            return request
        kept = [r for r in readings
                if r["classification"] != NOT_INTERPRETABLE
                and (r["ambiguous"] or items[r["item"] - 1]["conflict"])]
        kept.sort(key=lambda r: (not items[r["item"] - 1]["conflict"], r["item"]))
        generation = f"llm:{meta['model']}@{PROMPT_VERSION}"
        observed = observed_at_key(None)
        interpretations = []
        for reading in kept[:MAX_FLAGS_PER_SITUATION]:
            item = items[reading["item"] - 1]
            flag = AmbiguityFlag(
                field=item["field"],
                kind=AMBIGUITY_CONFLICT if item["conflict"] else AMBIGUITY_LLM,
                span=item["text"],
                digest=fact_digest(org_id=request.org_id,
                                   entity_ref=request.context.root_entity_id,
                                   field=item["field"], value=item["text"], observed=observed),
                observed_at=observed)
            interpretations.append(Interpretation(
                flag=flag, classification=reading["classification"],
                confidence_bp=reading["confidence_bp"], generation=generation,
                receipt=SiteReceipt(site=SITE_R1, outcome=OUTCOME_RAN, generation=generation,
                                    cache_key=meta["key"], model=meta["model"],
                                    input_tokens=meta["input_tokens"],
                                    output_tokens=meta["output_tokens"])))
        return augment(request, interpretations)
    except Exception:      # noqa: BLE001 — R-1 is an aid to the decision, never a reason to lose it
        _log.exception("LLM R-1 failed for %s — reasoning uninterpreted",
                       request.context.root_entity_id)
        return request


def _reset_for_tests() -> None:
    with _lock:
        _cache.clear()


__all__ = ["COST_PURPOSE", "MAX_ITEMS", "PROMPT_VERSION", "already_interpreted",
           "build_prompt", "candidate_items", "interpret_request", "parse_readings"]
