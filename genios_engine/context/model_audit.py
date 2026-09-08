"""One durable audit envelope for the model calls Layer 2 is still allowed to make.

The row stores the prompt hash and the complete returned artifact, not the prompt itself.  Source
text remains in its governed source store; replay can prove which prompt bytes were used and can
reuse the parsed output without calling a newer model.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy import text

from genios_engine.platform.canonical import semantic_hash, stable_id


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
    response_hash = semantic_hash({"parsed": parsed, "raw": raw})
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
                " subject_ref, created_at) values "
                "(:o,:model,:purpose,:it,:ot,:ok,:error,:subject,:at)"), {
                    "o": org_id, "model": model_snapshot, "purpose": f"l2:{site}",
                    "it": int(getattr(result, "input_tokens", 0) or 0),
                    "ot": int(getattr(result, "output_tokens", 0) or 0),
                    "ok": bool(getattr(result, "ok", False)),
                    "error": str(getattr(result, "error", "") or "")[:400] or None,
                    "subject": subject_ref, "at": called_at,
                })
    return run_id


__all__ = ["model_run_id", "record_model_run"]
