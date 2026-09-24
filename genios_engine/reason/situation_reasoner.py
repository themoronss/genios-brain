"""L2-5 · the Context Reasoner — one call per SITUATION, behind the gate that already exists.

⛔ **IT REGISTERS AS AN R-SITE AND BUILDS NO METERING, CACHING, BUDGET OR FALLBACK.**
`reason/llm_sites.py` states why:

    THERE IS EXACTLY ONE C5 GATE, AND IT IS `reason/bundle/gate.RSiteGate`. This module does not
    re-implement activation, budget, retry or receipting; it delegates all four, so a tenant's
    spend is one number measured against one ledger.

**A parallel gate would split the tenant's spend across two ledgers — the one thing that module
says it exists to prevent.** So this file supplies four things and nothing else: a precondition, a
prompt, a seed the gate keys its cache on, and a validator. `run_site` does the rest.

⛔ **R-1 ALREADY HOLDS THE CONTRACT, AND IT IS STRONGER THAN ANYTHING THE PLAN WROTE.**
`reason/interpretation.py`:

    The model returns `{classification, confidence_bp}` AS EVIDENCE; a unit reads it like any
    other input; THE FORMULA DECIDES. The model never says "this is urgent."
    ⛔ IT CANNOT RAISE CONFIDENCE.

Copied verbatim as `clamp_confidence`.

⛔ **THE COST CHECK RAN BEFORE THE PROMPT AND CORRECTED THE PLAN TWICE.**

    the plan          "same month → ~40 calls"     a 10× saving over per-event
    measured          159 active situations         2.9× over 465 events
                      (situation_bso.l1_refusal)

    all Haiku, p50 slice          $0.52 / sweep     ~$15.64 / month, daily
    all Sonnet, p50 slice         $1.04 / sweep     2×, and this is the whole argument
    "low+low never calls"         saves $0.10       ~$3 / month

**So the low+low rule is NOT a cost rule**, whatever §2 calls it. It is a QUALITY rule: a
low-confidence reading of a low-importance situation is a wrong answer nobody needed, and a wrong
card costs more than no card. L1 wrote the same sentence about promises — *"telling a founder they
broke a promise they kept is the failure that loses trust rather than quality."*

⛔ **IT LIVES IN `reason/`, NOT IN `context/`, AND THE TOPOLOGY TEST IS WHY.** The first draft put
it in Layer 2 and `test_import_direction` said:

    genios_engine/context/situation_reasoner.py (layer 2) imports genios_engine.reason (layer 4)
    — upward

**A lower layer may never import a higher one**, and the whole R-site apparatus — the gate, the
runner, the budget, the cache — is Plane R. The pre-flight correction had already said the right
thing and the first draft did not follow it: *"step-05 must register an R-site behind
`RSiteGate`, not build a gate."* An R-site lives where R-sites live. Everything this module reads
DOWNWARD — `context/proposal_gate`, `contracts/claim_state` — is allowed and unchanged.

PURE. No clock, no client, no connection. `run_site` is handed the pieces; this module decides
only what to ask and whether to ask at all.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

#: ⛔ ITS OWN VERSION, NOT L1's. *"A change here must not invalidate every extraction in the
#: corpus"* — `vocabulary_fingerprint` keys the extraction cache and moving it re-extracts
#: everything. This keys only R-6.
PROMPT_VERSION = "l2r.v1"

#: Below this, the model's own confidence is too low to act on. Integer basis points — V-8, and
#: declared rather than inlined because a number nobody can find is a number nobody can change.
CONFIDENCE_FLOOR_BP = 5_000
#: Below this, the situation is not worth a stronger model even when the reading is uncertain.
IMPORTANCE_FLOOR_BP = 5_000


class Step(str, Enum):
    """What to do with a situation, decided BEFORE anything is spent."""

    #: Confident enough. Haiku's reading stands, after the validator.
    ACCEPT = "accept"
    #: Uncertain AND consequential — worth Sonnet, once.
    ESCALATE = "escalate"
    #: ⛔ Uncertain and inconsequential. **No call at all**, and `unknown` recorded as the answer.
    UNKNOWN = "unknown"


def next_step(*, confidence_bp: int | None, importance_bp: int | None) -> Step:
    """The quadrant, on two numbers and no guessing.

    ⛔ **`None` IS NOT A LOW NUMBER — IT IS NOBODY HAVING MEASURED**, and it lands on `UNKNOWN`
    rather than on an assumed middle. L1's step 12 drew the same line for coverage: *"`None` is
    not a low number — it is nobody having measured — and it must land on the same side as low."*
    Reading an unscored situation as a confident one is how a model gets asked about something
    nobody has any basis to act on.
    """
    if confidence_bp is None or importance_bp is None:
        return Step.UNKNOWN
    if int(confidence_bp) >= CONFIDENCE_FLOOR_BP:
        return Step.ACCEPT
    return Step.ESCALATE if int(importance_bp) >= IMPORTANCE_FLOOR_BP else Step.UNKNOWN


def should_consult(step: Step) -> bool:
    """⛔ `UNKNOWN` never reaches a model. It is an ANSWER — L2-6's fourth outcome — and it
    commits, rather than being retried as though the model had failed."""
    return step is not Step.UNKNOWN


def consult_seed(*, situation_id: str, slice_digest: str) -> Mapping[str, str]:
    """What the GATE keys its cache on. U4: *"the reasoner supplies a slice digest and the gate
    does the rest."*

    The slice digest and not the situation id alone: two sweeps over an unchanged slice must not
    pay twice, and a situation whose facts moved must not read yesterday's answer. R-1 is keyed on
    a fact digest for the same reason and has no decision at all.
    """
    return {"situation": str(situation_id), "slice": str(slice_digest),
            "prompt": PROMPT_VERSION}


def slice_digest(context_slice: Any) -> str:
    """The slice's content address, shortened. It is already content-addressed — reusing that is
    what keeps the cache key and the replay agreeing about what "the same slice" means."""
    raw = getattr(context_slice, "semantic_hash", None)
    if raw:
        return str(raw)[:16]
    return hashlib.sha256(repr(context_slice).encode()).hexdigest()[:16]


def clamp_confidence(*, proposed_bp: int | None, current_bp: int | None) -> int | None:
    """⛔ **R-1's LAW, VERBATIM: IT CANNOT RAISE CONFIDENCE.**

    A model may lower what we claim to know and may never raise it. The moment it can, a confident
    generation becomes indistinguishable from evidence — and `EvidenceSpan.verified` records what
    that costs one layer down: *"the moment another caller can set that flag, it stops meaning
    'checked' and starts meaning 'claimed'."*

    `current_bp is None` returns `None`: nobody measured, and a model does not get to be the first.
    """
    if current_bp is None:
        return None
    if proposed_bp is None:
        return int(current_bp)
    return min(int(proposed_bp), int(current_bp))


def FALLBACK() -> dict:                                       # noqa: N802 — a name, not a class
    """⛔ SILENCE, NOT A NEUTRAL READING. R-1: *"a default reading would be a fact the model never
    stated, injected into the evidence layer where the formula would weigh it. The fallback for an
    interpretation is silence — the run proceeds exactly as it would have without R-1."*"""
    return {}


@dataclass(frozen=True, slots=True)
class WeighedSlice:
    """What is about to be sent, and whether anybody should be told how big it is."""

    payload: str
    tokens: int
    #: `None` when it fits. Otherwise the sentence, WITH BOTH NUMBERS.
    over: str | None


def weigh_before_sending(slice_json: str) -> WeighedSlice:
    """⛔ **L2-3 MEASURED THIS BUDGET FOR THIS CALLER AND THIS CALLER NEVER READ IT.**

    L2-3: *"`SLICE_TOKEN_BUDGET` is a LINE TO NOTICE, not a cap: nothing truncates, nothing
    refuses. A slice over it is reported so L2-5's cost check argues about a number instead of a
    feeling."* L2-5 shipped sending a slice to a model without ever asking what it weighed — the
    same "built and never switched on" shape this layer has been closing since L2-0, committed by
    the sequence itself.

    ⛔ **IT REPORTS AND RETURNS THE PAYLOAD UNCHANGED.** *"Dropping facts to hit a number is how a
    reasoner concludes from evidence nobody chose to remove."*
    """
    from genios_engine.context.slice_weight import CHARS_PER_TOKEN, SliceWeight, over_budget

    weight = SliceWeight(chars=len(slice_json), tokens=len(slice_json) // CHARS_PER_TOKEN)
    return WeighedSlice(payload=slice_json, tokens=weight.tokens, over=over_budget(weight))


def build_prompt(*, situation_type: str, slice_json: str, feedback: str | None = None) -> str:
    """One situation, the fields it may propose, and nothing else.

    The field list comes from `claim_state.model_writable_fields()` rather than from a string here,
    because L2-2 built it for this caller: *"deriving it by hand at the call site is how the list
    and the rule stop agreeing."* A prompt that offers a field the validator refuses is a prompt
    that buys a refusal.
    """
    from genios_engine.contracts.claim_state import model_writable_fields

    allowed = ", ".join(sorted(model_writable_fields()))
    correction = f"\n\nYour previous answer was refused: {feedback}" if feedback else ""
    return (
        f"You are reading ONE business situation of type `{situation_type}` and proposing an "
        f"interpretation of it.\n\n"
        f"CONTEXT (the only thing you may reason from):\n{slice_json}\n\n"
        f"Return a JSON object whose keys are drawn ONLY from: {allowed}\n\n"
        f"RULES:\n"
        f"- Every interpretation you propose must cite the evidence ids it rests on.\n"
        f"- You may not propose an observation, a receipt, or who may see this.\n"
        f"- You may LOWER a confidence and never raise one.\n"
        f"- If the context does not support a conclusion, return an empty object. "
        f"That is a valid and useful answer.\n"
        f"- Every number is an integer in basis points. No decimals."
        f"{correction}")


def reason_over_situation(*, org_id: str, situation_id: str, situation_type: str,
                          context_slice: Any, slice_json: str,
                          confidence_bp: int | None, importance_bp: int | None,
                          resolve_refs, held_facts=None, coverage_ready: bool | None = True,
                          expected_facts=(), gate=None, cache=None,
                          on_over_budget=None) -> tuple[Step, Any]:
    """Decide, then — only if it is worth deciding with a model — consult one.

    Returns `(step, payload)`. `payload` is `None` when nothing was asked, which is different from
    an empty payload: *nothing was asked* and *the model declined* are different facts, and only
    the second cost anything.

    `on_over_budget` is called with the sentence when the slice exceeds `SLICE_TOKEN_BUDGET` —
    **handed in**, so the caller decides what to do with it and this module still holds no I/O.
    Nothing is truncated either way.
    """
    from genios_engine.context.proposal_gate import as_gate_validator
    from genios_engine.platform.l4_activation import FEATURE_SITUATION_REASONER
    from genios_engine.reason.bundle.sites import SITE_SITUATION
    from genios_engine.reason.llm_sites import run_site

    step = next_step(confidence_bp=confidence_bp, importance_bp=importance_bp)
    if not should_consult(step):
        # ⛔ NOT AN ERROR AND NOT A FAILURE. The quadrant answered, and the answer was "we do not
        # know, and finding out is not worth it". Recorded by the caller; nothing is spent.
        return step, None

    weighed = weigh_before_sending(slice_json)
    validate = as_gate_validator(resolve_refs=resolve_refs, held_facts=held_facts,
                                 coverage_ready=coverage_ready, expected_facts=expected_facts)

    def _parse(payload: Mapping[str, Any]) -> dict:
        value, codes, _record = validate(dict(payload))
        if value is None:
            from genios_engine.reason.llm_sites import SiteRejection

            raise SiteRejection(codes[0] if codes else "l2_refused", detail=", ".join(codes))
        return dict(value)

    if weighed.over is not None and on_over_budget is not None:
        on_over_budget(weighed.over)

    result = run_site(
        site=SITE_SITUATION, org_id=org_id,
        seed=dict(consult_seed(situation_id=situation_id,
                               slice_digest=slice_digest(context_slice))),
        precondition=True,
        build_prompt=lambda feedback: build_prompt(
            situation_type=situation_type, slice_json=slice_json, feedback=feedback),
        parse=_parse, fallback=FALLBACK, gate=gate, cache=cache,
        feature=FEATURE_SITUATION_REASONER, subject_ref=situation_id)
    return step, result


__all__ = ["CONFIDENCE_FLOOR_BP", "FALLBACK", "IMPORTANCE_FLOOR_BP", "PROMPT_VERSION",
           "Step", "WeighedSlice", "weigh_before_sending",
           "build_prompt", "clamp_confidence", "consult_seed", "next_step",
           "reason_over_situation", "should_consult", "slice_digest"]
