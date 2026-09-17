"""The transport that turns a declared angle into one model call — and nothing more.

`angles/contract.py` says what may be asked and `angles/store.py` decides when. Neither knows a
model exists: `evaluate_angle(..., asker=None)` is the default and the sweep never supplies one,
which is what makes "a tenant cannot reach a model by accident" a property rather than a promise.
This is the piece a caller opts into.

NOTHING THE MODEL WRITES IS EVER ECHOED. It returns a WORD from the angle's own `returns` and a
number; both are validated by `AngleVerdict.of` before anything is stored, and a word outside the
enum becomes the angle's declared REFUSAL rather than an error — `store.evaluate_angle` would
otherwise count it as `failed`, which hides a model that is answering confidently in the wrong
vocabulary. `framing/headline.py` takes the same position one site over: the model picks from a
closed set and the system supplies every word that makes a claim.

THE PROMPT IS BUILT FROM THE DECLARATION, NOT WRITTEN PER ANGLE. `angle.sees` names the fields, so
the prompt cannot show a field the declaration did not admit; `angle.returns` is the answer list;
`angle.refusal` is named as the honest exit. Adding an angle therefore costs no prompt engineering
and cannot widen what leaves the tenant — the review of `sees` IS the review of the prompt.

DETERMINISTIC BY CONSTRUCTION. Fields are sorted and the instruction block is byte-identical
across subjects, which is what makes the cache prefix worth anything and what lets two runs at one
instant produce the same prompt hash for the audit.

COST IS A TIER, NOT A GUESS. `angle.cost_tier` picks the client: `CHEAP` for a classification over
a compact slice, `CAPABLE` for a judgement over prose. A caller that supplies one client gets that
one for both, which is the correct default for a tenant who has not chosen.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from genios_engine.context.angles.contract import Angle, CostTier

#: Enough for a word and a number with room for a malformed reply to be seen rather than truncated
#: into looking valid. The answer is two fields; anything longer is a model ignoring the format.
class AskerUnavailable(RuntimeError):
    """The model was not reached at all. Raised so `evaluate_angle` counts it as `failed`, which
    is a different fact from a question nobody could answer."""


MAX_TOKENS = 200

#: The instruction block is identical for every subject of every angle, so it is the cacheable
#: prefix. Only the slice below it changes.
_RULES = (
    "You classify one subject for an automated system. Answer ONLY with JSON:\n"
    '{"verdict": "<one of the allowed answers>", "confidence_bp": <integer 0-10000>}\n\n'
    "Rules:\n"
    "- `verdict` MUST be exactly one of the allowed answers. Never invent one.\n"
    "- If the evidence does not settle the question, use the refusal answer. Refusing is a "
    "correct result, not a failure, and is preferred over a guess.\n"
    "- `confidence_bp` is your confidence in basis points: 10000 is certain, 5000 is even.\n"
    "- Judge ONLY from the evidence given. Do not assume facts that are not shown.\n"
    "- Write no prose, no explanation, no markdown. JSON only.\n"
)


def build_prompt(angle: Angle, subject_ref: str, seen: Mapping[str, Any]) -> tuple[str, int]:
    """`(prompt, cache_prefix_chars)`.

    The subject ref is deliberately NOT shown: it is an internal node id that identifies nothing a
    model can reason about, and including it would put a tenant's key material in a prompt for no
    gain. What the model sees is exactly `angle.sees` and the question.
    """
    question = angle.question or angle.angle_id.replace("_", " ")
    head = (f"{_RULES}\nQUESTION: {question}\n"
            f"ALLOWED ANSWERS: {', '.join(angle.returns)}\n"
            f"REFUSAL ANSWER: {angle.refusal}\n")
    lines = [f"- {name}: {json.dumps(seen.get(name), default=str)}" for name in sorted(angle.sees)]
    return head + "\nEVIDENCE:\n" + "\n".join(lines) + "\n", len(head)


class Usage:
    """What one call actually cost, so the audit is a receipt rather than a placeholder.

    THE STORE CANNOT KNOW ANY OF THIS. `Asker` returns `(word, confidence)` and nothing else, so
    `store._record` filled the envelope with `model="unknown"`, `max_tokens=0` and zero tokens —
    and the live run proved it twice over: the row was useless AND it violated
    `l2_model_runs_max_tokens_check`, so every audit row for every verdict was lost. The asker is
    the only thing that holds these facts; it now says so out loud.
    """

    #: The attribute NAMES are the contract. `model_audit.record_model_run` reads `model`,
    #: `input_tokens`, `output_tokens`, `ok`, `error`, `raw` and `parsed` off whatever it is
    #: handed — the store was handing it the verdict STRING, so every one of those getattrs took
    #: its default and the receipt said `model="unknown"`, zero tokens, `success=False`.
    __slots__ = ("model", "max_tokens", "input_tokens", "output_tokens", "ok", "error", "raw",
                 "parsed")

    def __init__(self) -> None:
        self.model, self.max_tokens = "", MAX_TOKENS
        self.input_tokens = self.output_tokens = 0
        self.ok, self.error, self.raw, self.parsed = False, None, "", {}

    def as_record(self) -> dict[str, Any]:
        return {"model_snapshot": self.model or "unknown", "max_tokens": self.max_tokens,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "success": self.ok, "error": self.error, "raw_output": self.raw}


def model_asker(cheap: Any, capable: Any = None):
    """An `Asker` backed by a model client. `capable` defaults to `cheap`.

    THE TWO FAILURES ARE DIFFERENT AND MUST STAY DIFFERENT. `store.evaluate_angle` counts a
    raised exception as `failed` and a returned refusal as `refused`:

      * a TRANSPORT failure — no network, no API key, a missing SDK, a 500 — is the machinery
        breaking, and it RAISES. The first live call here returned `ok=False` with "No module
        named 'anthropic'", and an earlier cut of this function turned that into `unknowable` at
        floor confidence: indistinguishable from a model that had read the evidence and honestly
        could not tell. Running the full pass that way would have produced seventy "refusals"
        and reported them as answers.
      * a model that ANSWERED in the wrong vocabulary, or returned nothing parseable, is the
        question failing rather than the machinery, and returns the declared refusal.

    The rule is whether a model was reached at all.
    """
    last = Usage()

    def ask(angle: Angle, subject_ref: str, seen: Mapping[str, Any]) -> tuple[int | str, int]:
        client = capable if (capable is not None and angle.cost_tier is CostTier.CAPABLE) else cheap
        prompt, prefix = build_prompt(angle, subject_ref, seen)
        kwargs: dict[str, Any] = {"max_tokens": MAX_TOKENS}
        if getattr(client, "supports_prompt_cache", False):
            kwargs["cache_prefix_chars"] = prefix
        result = client.call(prompt, **kwargs)
        last.model = str(getattr(result, "model", "") or getattr(client, "model", "") or "")
        last.max_tokens = MAX_TOKENS
        last.input_tokens = int(getattr(result, "input_tokens", 0) or 0)
        last.output_tokens = int(getattr(result, "output_tokens", 0) or 0)
        last.ok = bool(getattr(result, "ok", False))
        last.error = getattr(result, "error", None)
        last.raw = str(getattr(result, "raw", "") or "")[:2000]
        last.parsed = getattr(result, "parsed", None) or {}

        low, high = angle.confidence_band
        error = str(getattr(result, "error", "") or "")
        parsed = getattr(result, "parsed", None) or {}
        if not getattr(result, "ok", False) and not parsed:
            # NO MODEL WAS REACHED. Raising is what makes this land in `failed` rather than
            # `refused`, so a broken key or a missing SDK cannot be read as a tenant whose
            # questions were all unanswerable.
            raise AskerUnavailable(f"{angle.angle_id}: the model was not reached — {error[:200]}")
        word = str(parsed.get("verdict") or "").strip()
        if word not in angle.returns:
            return angle.refusal, low
        try:
            confidence = int(parsed.get("confidence_bp"))
        except (TypeError, ValueError):
            # A usable verdict with an unusable number is still a verdict. The band's floor is the
            # honest reading of "it answered but told us nothing about how sure it was";
            # `Angle.clamp` would raise on a non-integer and lose the answer with it.
            confidence = low
        return word, max(low, min(high, confidence))

    ask.last = last          # read by `store._record` to file a real receipt
    return ask


__all__ = ["AskerUnavailable", "MAX_TOKENS", "Usage", "build_prompt", "model_asker"]
