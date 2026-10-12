"""One durable audit envelope for the model calls Layer 2 is still allowed to make.

The row stores the prompt hash and the complete returned artifact, not the prompt itself.  Source
text remains in its governed source store; replay can prove which prompt bytes were used and can
reuse the parsed output without calling a newer model.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import text

from genios_engine.platform.canonical import semantic_hash, stable_id


def _decimals(value: Any) -> Any:
    """The parsed answer with every float read as its decimal text — what the model WROTE.

    `platform/canonical` refuses floats in a semantic artifact, and rightly: a float in a decision
    is a value that cannot be compared to itself across a version. But this is the model's answer,
    not ours, and the call is already paid for — refusing it here dropped the audit row and, in the
    resolution pass, the rest of the org's pass with it (STEP-18 B21, `03` F32). `repr` is the
    shortest text that reads back as the same float, so `0.85` hashes as `0.85` and never as the
    binary fraction; a non-finite one (`nan`, `inf`) is hashed as its name. Nothing else changes, so
    an answer with no float hashes exactly as it always did.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return Decimal(repr(value)) if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {key: _decimals(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_decimals(item) for item in value]
    return value


def _response_hash(parsed: Mapping[str, Any], raw: str) -> str:
    """The audit row's `response_hash`: the parsed answer and the raw text, canonically hashed."""
    return semantic_hash({"parsed": _decimals(dict(parsed)), "raw": raw})


def model_run_id(*, org_id: str, site: str, subject_ref: str,
                 prompt_version: str, prompt_hash: str, model_snapshot: str,
                 called_at: datetime) -> str:
    return stable_id("l2model", {
        "org_id": org_id, "site": site, "subject_ref": subject_ref,
        "prompt_version": prompt_version, "prompt_hash": prompt_hash,
        "model_snapshot": model_snapshot, "called_at": called_at,
    })


def record_model_run(
    engine,
    *,
    org_id: str,
    site: str,
    subject_ref: str,
    prompt_version: str,
    prompt: str,
    result: Any,
    called_at: datetime,
    max_tokens: int,
    latency_ms: int | None = None,
) -> str:
    """Persist before a model result is allowed to influence graph/situation state."""
    if called_at.tzinfo is None or called_at.utcoffset() is None:
        raise ValueError("called_at must be timezone-aware")
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    parsed = getattr(result, "parsed", None)
    parsed = dict(parsed) if isinstance(parsed, Mapping) else {}
    raw = str(getattr(result, "raw", "") or "")
    response_hash = _response_hash(parsed, raw)
    model_snapshot = str(getattr(result, "model", "") or "unknown")
    run_id = model_run_id(
        org_id=org_id, site=site, subject_ref=subject_ref,
        prompt_version=prompt_version, prompt_hash=prompt_hash,
        model_snapshot=model_snapshot, called_at=called_at)
    with engine.begin() as conn:
        inserted = conn.execute(text(
            "insert into l2_model_runs "
            "(run_id, org_id, site, subject_ref, prompt_version, prompt_hash, model_snapshot, "
            " max_tokens, input_tokens, output_tokens, success, error, parsed_output, raw_output, "
            " response_hash, latency_ms, called_at) values "
            "(:id,:o,:site,:subject,:pv,:ph,:model,:max,:it,:ot,:ok,:error,"
            " cast(:parsed as jsonb),:raw,:rh,:latency,:at) "
            "on conflict (run_id) do nothing"), {
                "id": run_id, "o": org_id, "site": site, "subject": subject_ref,
                "pv": prompt_version, "ph": prompt_hash,
                "model": model_snapshot,
                "max": max_tokens, "it": int(getattr(result, "input_tokens", 0) or 0),
                "ot": int(getattr(result, "output_tokens", 0) or 0),
                "ok": bool(getattr(result, "ok", False)),
                "error": str(getattr(result, "error", "") or "")[:400] or None,
                "parsed": json.dumps(parsed, sort_keys=True), "raw": raw,
                "rh": response_hash, "latency": latency_ms, "at": called_at,
            }).rowcount or 0
        if inserted:
            conn.execute(text(
                "insert into llm_costs "
                "(org_id, model, purpose, input_tokens, output_tokens, success, error, "
                " subject_ref, cache_read_tokens, cache_write_tokens, created_at) values "
                "(:o,:model,:purpose,:it,:ot,:ok,:error,:subject,:crt,:cwt,:at)"), {
                    "o": org_id, "model": model_snapshot, "purpose": f"l2:{site}",
                    "it": int(getattr(result, "input_tokens", 0) or 0),
                    "ot": int(getattr(result, "output_tokens", 0) or 0),
                    "ok": bool(getattr(result, "ok", False)),
                    "error": str(getattr(result, "error", "") or "")[:400] or None,
                    "subject": subject_ref, "at": called_at,
                    # Recorded, never priced: `input_tokens` above is already cost-equivalent.
                    "crt": int(getattr(result, "cache_read_tokens", 0) or 0),
                    "cwt": int(getattr(result, "cache_write_tokens", 0) or 0),
                })
    return run_id


__all__ = ["model_run_id", "record_model_run"]
