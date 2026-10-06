"""The material fingerprint — what a decision depends on, with time taken out (STEP-02, the change gate).

Every sweep re-decides every subject, and on a sweep that brought nothing new it pays the decider and
R-1 again for the same answer (`speedrun008/YC-II W27/` STEP-02 §8.1). The gate
(`reason/change_gate.should_skip`) skips a subject whose fingerprint is the one its last decision was
made on; this module says what goes into that fingerprint.

THE DECISION'S OWN REQUEST, NOT A LIST OF GUESSED INPUTS. A lane builds a context snapshot and a
capability manifest and hands both to the decider; that is everything the decision reads. Measured on
all 40 golden cases: a request repeated on a sweep 15 minutes later that brought nothing new differs
only in what the clock and the writers re-stamp — `evaluation_time`, `graph_version`, each fact's
`occurred_at` (the derived and waiting passes re-write every fact every drain, with the same value —
read as a rung relative to the evaluation instant, a re-stamp to "now" never moves),
each evidence item's `evidence_id` (and so the evidence list's order), and the compiled capability's
derived `version` and `expertise_id`. With those out, every repeated request was identical.

THREE THINGS CAN CHANGE THE RIGHT ANSWER WITHOUT TOUCHING THE REQUEST, and `MaterialInputs` carries
them: the pack's `authority_revision` (a calibration, a pack change), the human verdicts on the
subject's cards, and WHO DECIDES — the formula, or the LLM decider and its model, and whether R-1
reads the request first. The third was found wiring the legacy lane: a test that switches the decider
on between two sweeps was skipped as unchanged, so switching `GENIOS_L4_LLM_DECISION_MAKER` in
production would have kept every old decision until some other input moved.

A CLOCK IS COMPARED BY ITS RUNG. A deadline or an elapsed time is read relative to the evaluation
instant and reduced to its rung on a ladder — deadline hours on Layer 4's own urgency ladder, elapsed
days on `DAY_LADDER` — so a wait crossing from 6 to 7 days re-decides, and 15 minutes never does.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from genios_engine.reason.reasoners.timeline_unit import URGENCY_LADDER

#: Hours until a deadline: the rungs `timeline_unit.urgency_from_hours` already decides urgency on.
HOUR_LADDER: tuple[int, ...] = tuple(hours for hours, _ in URGENCY_LADDER)

#: Elapsed days — how long a thread has waited, since a meeting, since contact. Seven is a rung:
#: STEP-02 §4's *"Theresa's wait crosses from 6 to 7 days"* is exactly the change that must re-decide.
DAY_LADDER: tuple[int, ...] = (0, 1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90, 180, 365)


def verdict_key(feedback_id: str, verdict_version: int) -> str:
    """One human verdict, as the fingerprint carries it: which feedback, at which version."""
    if not feedback_id:
        raise ValueError("a verdict key needs its feedback id")
    return f"{feedback_id}:{int(verdict_version)}"


@dataclass(frozen=True)
class MaterialInputs:
    """What can change the right answer without touching the decision's request.

    `authority_revision` — `tenant_packs.authority_revision` of the pack the decision runs under.
    `verdicts` — `verdict_key`s of the human verdicts on the subject's cards, held in one order.
    `decider` — who decides: `"formula"`, or `"llm:<model>"`, with `"+r1"` when R-1 reads first.
    """

    authority_revision: int | None = None
    verdicts: tuple[str, ...] = field(default_factory=tuple)
    decider: str = "formula"

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdicts", tuple(sorted(set(self.verdicts))))


# ── the fingerprint ─────────────────────────────────────────────────────────────────────────────
import hashlib as _hashlib                               # noqa: E402 — kept beside its only reader
import json as _json                                     # noqa: E402
import re as _re                                         # noqa: E402
from datetime import datetime as _datetime, timezone as _timezone   # noqa: E402
from decimal import Decimal as _Decimal, InvalidOperation as _InvalidOperation   # noqa: E402

from genios_engine.platform.canonical import canonicalize as _canonicalize  # noqa: E402

#: Bumped whenever what goes into a fingerprint changes. Every stored fingerprint then differs from
#: the next sweep's, so every subject is decided once more — the safe direction for a change here.
FINGERPRINT_VERSION = 1

#: Re-stamped by the clock or the writers on every sweep, never by the world (STEP-02 §8, measured).
#:
#: ⛔ `occurred_at` IS NOT DROPPED — it is reduced to its rung like every other instant. The derived
#: and waiting passes re-stamp it to the drain's instant every sweep, which reads as "0 hours away"
#: on every sweep and so never moves the fingerprint; a SOURCE fact's `occurred_at` is when the world
#: said it, and its age crossing a rung (5 → 7 days old) is a change a decision may read. Dropping it
#: was the first draft; this file's own mutation check showed the rung already did the dropping's
#: job, and only the rung keeps the age.
_DROP_FROM_CONTEXT = frozenset({"evaluation_time", "graph_version"})
_DROP_FROM_RECORDS = frozenset({"fact_version_id", "evidence_id", "valid_from", "recorded_at",
                                "created_at", "updated_at"})
_DROP_FROM_CAPABILITY = frozenset({"version"})
_DROP_FROM_CAPABILITY_METADATA = frozenset({"expertise_id"})
_TIMESTAMP = _re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?"
                         r"(?:Z|[+-]\d{2}:?\d{2})?$")


def _rung(value, ladder: tuple[int, ...]) -> str:
    reached = [step for step in ladder if value >= step]
    return f">={reached[-1]}" if reached else f"<{ladder[0]}"


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, dict) and set(value) == {"$decimal"}:
        try:
            return _Decimal(value["$decimal"])
        except (_InvalidOperation, TypeError):
            return None
    return None


def _instant(text: str) -> _datetime | None:
    if not _TIMESTAMP.match(text):
        return None
    try:
        moment = _datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=_timezone.utc)


def _relative(moment: _datetime, now: _datetime) -> dict:
    """A moment, as the decision reads it: hours until it on the urgency ladder, or days since."""
    hours = (moment - now).total_seconds() / 3600
    if hours >= 0:
        return {"$until_hours": _rung(hours, HOUR_LADDER)}
    return {"$days_ago": _rung(-hours / 24, DAY_LADDER)}


def _clock_field(name: str | None) -> tuple[int, ...] | None:
    if not name:
        return None
    if "days" in name:
        return DAY_LADDER
    if name.endswith("_hours"):
        return HOUR_LADDER
    return None


def _scrub(value, now: _datetime, field: str | None = None):
    """Time out, rungs in. `field` is the fact a value belongs to, so a clock is known by its name."""
    if isinstance(value, dict):
        if set(value) == {"$datetime"}:
            moment = _instant(value["$datetime"])
            return _relative(moment, now) if moment else value
        if set(value) == {"$date"}:
            moment = _instant(value["$date"])
            return _relative(moment, now) if moment else value
        ladder, number = _clock_field(field), _number(value)
        if ladder and number is not None:
            return {"$rung": _rung(number, ladder)}
        named = value.get("field") if isinstance(value.get("field"), str) else None
        out = {}
        for key, item in value.items():
            if key in _DROP_FROM_RECORDS:
                continue
            out[key] = _scrub(item, now, named if key == "value" and named else
                              field if key == "value" else key if key not in ("facts",) else None)
        return out
    if isinstance(value, list):
        return [_scrub(item, now, field) for item in value]
    if isinstance(value, str):
        moment = _instant(value)
        return _relative(moment, now) if moment else value
    ladder, number = _clock_field(field), _number(value)
    if ladder and number is not None:
        return {"$rung": _rung(number, ladder)}
    return value


def _facts(mapping, now: _datetime):
    """A facts mapping, each record scrubbed under its own fact name."""
    if not isinstance(mapping, dict):
        return _scrub(mapping, now)
    return {name: _scrub(record, now, name) for name, record in mapping.items()}


def material_fingerprint(capability, snapshot, *, config_snapshot_id: str | None, mode,
                         inputs: MaterialInputs) -> str:
    """The fingerprint of one decision's inputs: its capability and context snapshot with time
    taken out, the pack config it runs under, its mode, and `inputs`. Never `evaluation_time`.

    Pure. Raises `platform.canonical.CanonicalizationError` on an artifact canonicalization refuses
    (a float); a caller that cannot fingerprint must decide, never skip.
    """
    now = snapshot.evaluation_time
    context = _canonicalize(snapshot.to_semantic_dict())
    context = {key: item for key, item in context.items() if key not in _DROP_FROM_CONTEXT}
    for key in ("facts", "neighbor_facts"):
        if key in context:
            context[key] = _facts(context[key], now)
    for key in ("observations", "evidence", "metadata"):
        if key in context:
            context[key] = _scrub(context[key], now)
    # The evidence list is sorted by evidence id, and an evidence id carries its observation time —
    # so the same evidence re-stamped comes back in another order. Compared as a set.
    context["evidence"] = sorted(context.get("evidence") or (),
                                 key=lambda item: _json.dumps(item, sort_keys=True))
    manifest = _canonicalize(capability.to_semantic_dict())
    manifest = {key: item for key, item in manifest.items() if key not in _DROP_FROM_CAPABILITY}
    if isinstance(manifest.get("metadata"), dict):
        manifest["metadata"] = {key: item for key, item in manifest["metadata"].items()
                                if key not in _DROP_FROM_CAPABILITY_METADATA}
    payload = {"fingerprint_version": FINGERPRINT_VERSION, "capability": manifest,
               "context": context, "config_snapshot_id": config_snapshot_id,
               "mode": getattr(mode, "value", mode),
               "inputs": {"authority_revision": inputs.authority_revision,
                          "verdicts": list(inputs.verdicts), "decider": inputs.decider}}
    # ⛔ NOT `semantic_hash(payload)`. The payload is ALREADY canonical — its decimals, dates and
    # instants are the tagged scalars `canonicalize` emits — and canonicalizing it again refuses
    # every one of them as a reserved key. A snapshot holding one decimal value (they do: the golden
    # cases carry `$decimal` evidence) would have made the fingerprint raise on every sweep.
    material = _json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                           allow_nan=False)
    return "fp_" + _hashlib.sha256(material.encode("utf-8")).hexdigest()
