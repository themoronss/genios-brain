"""L2-5 · the durable home for a Context Reasoner reading — one writer, and it never raises.

⛔ **A RECEIPT MAY NOT KILL ITS SUBJECT.** `BundleStore.record_call` states the rule this obeys:

    Never raises because this is a receipt, and a receipt that can abort the thing it is a
    receipt for turns an accounting failure into a product failure. A lost row costs a
    mis-stated rate on a dashboard; a raised exception here would cost the narration pass.

L2-7 learned the same thing the hard way when an unguarded measurement could kill the delivery
pass on a tenant whose migration had not landed. **A reading is worth less than the sweep.**

⛔ **AND IT NAMES EVERY COLUMN IT STORES.** *"A column no writer names is null forever"* —
`started_at` on `l1_sync_runs`, the sentence L1's steps 14 and 18 both wrote down, and the reason
migration 0183 and this file must be read together.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Mapping, Sequence

from genios_engine.platform.ids import new_id

_log = logging.getLogger(__name__)

TABLE = "situation_interpretations"


def record_interpretation(engine, *, org_id: str, situation_id: str, slice_digest: str,
                          context_slice: Mapping[str, Any] | Any, proposal: Mapping[str, Any],
                          outcome: str, reasoning_trace: str | None,
                          valid_until: datetime | None,
                          reason_codes: Sequence[str] = ()) -> None:
    """One row per (situation, slice). Never raises.

    `unknown` gets a row like any other outcome: **a reading that declined to conclude is an
    answer**, and a sweep that asked nothing must not look like a sweep that was never run. That
    is the same distinction L2-0 drew between a refusal that scored nothing and one that was never
    scored.
    """
    if engine is None:
        return
    try:
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text(
                f"insert into {TABLE} (interpretation_id, org_id, situation_id, slice_digest, "
                " context_slice, proposal, outcome, reason_codes, reasoning_trace, valid_until) "
                "values (:id,:o,:sit,:dig,cast(:slice as jsonb),cast(:prop as jsonb),:out,"
                "        cast(:codes as jsonb),:trace,:until) "
                # A re-sweep over an unchanged slice UPDATES rather than duplicating; a sweep
                # after the facts moved has a different digest and writes its own row, so the
                # history of what was believed when survives.
                "on conflict (org_id, situation_id, slice_digest) do update set "
                "  proposal=excluded.proposal, outcome=excluded.outcome, "
                "  reason_codes=excluded.reason_codes, reasoning_trace=excluded.reasoning_trace, "
                "  valid_until=excluded.valid_until"), {
                    "id": new_id("interp"), "o": org_id, "sit": situation_id,
                    "dig": slice_digest,
                    "slice": json.dumps(
                        context_slice.to_semantic_dict()
                        if hasattr(context_slice, "to_semantic_dict") else context_slice,
                        default=str),
                    "prop": json.dumps(dict(proposal or {}), default=str),
                    "out": str(outcome),
                    "codes": json.dumps([str(c) for c in (reason_codes or ())]),
                    "trace": reasoning_trace or None,
                    "until": valid_until,
                })
    except Exception as exc:      # noqa: BLE001 — see the module docstring
        _log.warning("could not record the interpretation for situation=%s: %s",
                     situation_id, exc)


__all__ = ["TABLE", "record_interpretation"]
