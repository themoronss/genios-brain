"""R-1, R-3 and R-4 through the ONE gate — plus the per-site generation cache they need.

**THERE IS EXACTLY ONE C5 GATE, AND IT IS `reason/bundle/gate.RSiteGate`.** This module does not
re-implement activation, budget, retry or receipting; it delegates all four, so a tenant's narrative
spend is one number measured against one ledger, the force-fail switch that K4's doctrine test flips
turns these three sites off as well, and a policy change lands in one place. What lives here is what
that gate deliberately leaves to a caller:

* **the per-site generation cache** (migration 0121). `BundleStore` holds one narrative per published
  decision; these sites need something else. R-1 is keyed on a FACT DIGEST and has no decision at all
  — it runs before the units do. R-3 is asked for on card expand, which for most decisions never
  happens, so a column on a bundle row would be null for the ~75% of cards nobody opens. The gate
  takes a `cached` thunk for exactly this reason and stores nothing itself.
* **the refusal shape.** A site's parser raises :class:`SiteRejection` with a reason code; the gate
  wants `(value, reason_codes, trace_record)`. :func:`run_site` translates, so a site reads as
  "refuse, never repair" and the ledger still gets the codes.
* **the result shape** these two modules already render from.

WHAT A CALLER GETS. Always an answer: the model's when every check passed, the caller's deterministic
template otherwise — the gate never invents a fallback, because a gate that knew what a good plain
narrative looked like would be a gate with an opinion about the product.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from genios_engine.contracts.reasoning import TEMPLATE_FALLBACK, require_generation
from genios_engine.platform.canonical import canonical_dumps, semantic_hash
from genios_engine.platform.l4_activation import FEATURE_BUNDLE
from genios_engine.reason.bundle.budget import cost_micro_usd
from genios_engine.reason.bundle.gate import ConsultResult, RSiteGate, force_failed
from genios_engine.reason.bundle.sites import (
    FALLBACK_OUTCOMES,
    OUTCOME_CACHED,
    OUTCOME_FAILED_GENERATION,
    OUTCOME_FAILED_VALIDATION,
    OUTCOME_FORCE_FAILED,
    OUTCOME_NO_BUDGET,
    OUTCOME_NO_CLIENT,
    OUTCOME_NO_PRECONDITION,
    OUTCOME_NOT_ACTIVATED,
    OUTCOME_RAN,
    OUTCOMES,
    SITE_ALTERNATIVES,
    SITE_EFFECT,
    SITE_INTERPRET,
    require_site,
    tier_for,
)

_log = logging.getLogger(__name__)

# The three sites THIS module runs, under the ids the shared vocabulary already gives them. R-2 and
# R-5 are the bundle group's; naming them here would invite a caller to route one through the wrong
# module.
SITE_R1 = SITE_INTERPRET
SITE_R3 = SITE_ALTERNATIVES
SITE_R4 = SITE_EFFECT
SITES = (SITE_R1, SITE_R3, SITE_R4)

# Re-exported so `interpretation` and `narration` — and their tests — read one vocabulary. These are
# the shared strings, not copies: an alias cannot drift from what it aliases.
OUTCOME_BUDGET = OUTCOME_NO_BUDGET
OUTCOME_PRECONDITION = OUTCOME_NO_PRECONDITION

#: Bumped whenever a site's PROMPT changes. It travels inside `generation` ("llm:<model>@<version>")
#: and inside every cache key, so a prompt edit invalidates the cache instead of serving prose the
#: current prompt would never have produced — doc 09 case 10, closed at the key rather than by
#: remembering to purge.
PROMPT_VERSION = "l4-r-sites.v1"


class SiteRejection(Exception):
    """A generation that did not survive validation. Carries the reason code the ledger records.

    Raised by a site's own parser, never by the transport: "the model said something we refuse to
    render" and "the network failed" are different facts about a run, and one exception type would
    collapse them into one line of the receipt.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = str(reason)
        self.detail = str(detail)[:400]


@dataclass(frozen=True, slots=True)
class SiteReceipt:
    """One consult, in the shape these sites' callers render and their tests read.

    Built FROM the gate's `ConsultResult` rather than beside it, so there is no second record of the
    same consult that could disagree with `l4_r_site_calls`.
    """

    site: str
    outcome: str
    generation: str
    cache_key: str
    tier: str = ""
    model: str = ""
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micro_usd: int = 0
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_site(self.site)
        if self.outcome not in OUTCOMES:
            raise ValueError(f"unknown site outcome {self.outcome!r}")
        require_generation(self.generation, "site generation")
        object.__setattr__(self, "reason_codes", tuple(
            str(code) for code in self.reason_codes if str(code)))

    @property
    def fell_back(self) -> bool:
        return self.outcome in FALLBACK_OUTCOMES

    def as_record(self) -> dict[str, Any]:
        return {"site": self.site, "outcome": self.outcome, "generation": self.generation,
                "cache_key": self.cache_key, "tier": self.tier, "model": self.model,
                "attempts": self.attempts, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "cost_micro_usd": self.cost_micro_usd,
                "reason_codes": list(self.reason_codes)}

    @classmethod
    def of(cls, result: ConsultResult, *, generation: str) -> SiteReceipt:
        return cls(site=result.site, outcome=result.outcome, generation=generation,
                   cache_key=result.cache_key, tier=result.tier, model=(result.model or ""),
                   attempts=result.attempts, input_tokens=result.input_tokens,
                   output_tokens=result.output_tokens, cost_micro_usd=result.cost_micro_usd,
                   reason_codes=result.reason_codes)


@dataclass(frozen=True, slots=True)
class SiteResult:
    """The payload the caller renders, and the receipt for how it got here.

    `payload` is never None and never partial: on every falling-back branch it is what `fallback()`
    returned, which is deterministic prose over numbers the engine already holds.
    """

    payload: Mapping[str, Any]
    receipt: SiteReceipt

    @property
    def generation(self) -> str:
        return self.receipt.generation

    @property
    def fell_back(self) -> bool:
        return self.receipt.fell_back


# =================================================================================================
# THE CACHE (migration 0121)
# =================================================================================================

def cache_key(*, site: str, org_id: str, seed: Mapping[str, Any]) -> str:
    """The content address of one consult: `decision_hash` for R-3/R-4, the fact digest for R-1.

    The prompt version is inside the key by construction, so editing a prompt cannot serve prose the
    new prompt would never have produced; the site id is inside it so two sites reading one decision
    never collide.
    """
    require_site(site)
    return semantic_hash({"site": site, "org_id": str(org_id), "prompt_version": PROMPT_VERSION,
                          "seed": dict(seed)})


@dataclass
class InMemorySiteCache:
    """Process-local cache. Correct, bounded by the process, never shared across workers."""

    _rows: dict[tuple[str, str, str], tuple[Mapping[str, Any], str]] = field(default_factory=dict)

    def get(self, org_id: str, site: str, key: str) -> Mapping[str, Any] | None:
        row = self._rows.get((str(org_id), str(site), str(key)))
        if row is None:
            return None
        payload, generation = row
        return {**dict(payload), "generation": generation}

    def put(self, org_id: str, site: str, key: str, payload: Mapping[str, Any],
            generation: str) -> None:
        self._rows[(str(org_id), str(site), str(key))] = (dict(payload), str(generation))


@dataclass(frozen=True, slots=True)
class PostgresSiteCache:
    """The durable cache, in `l4_r_site_generations`.

    Durable rather than in-process because the cache is what makes the same decision read the same
    tomorrow (doc 09 case 10) and what keeps K4's regeneration rate near zero across workers. Read
    and write both fail SOFT: a cache that is down costs a call; a cache that raises costs a card.
    """

    engine: Any

    def get(self, org_id: str, site: str, key: str) -> Mapping[str, Any] | None:
        if self.engine is None:
            return None
        try:
            from sqlalchemy import text
            with self.engine.connect() as conn:
                row = conn.execute(text(
                    "select payload, generation from l4_r_site_generations "
                    "where org_id = :o and site = :s and cache_key = :k"),
                    {"o": org_id, "s": site, "k": key}).first()
        except Exception:      # noqa: BLE001 — a cache miss is always a legal answer
            _log.exception("R-site cache read failed for org=%s site=%s", org_id, site)
            return None
        if row is None:
            return None
        payload = row.payload
        if isinstance(payload, str):
            import json
            try:
                payload = json.loads(payload)
            except ValueError:
                return None
        if not isinstance(payload, Mapping):
            return None
        return {**dict(payload), "generation": row.generation}

    def put(self, org_id: str, site: str, key: str, payload: Mapping[str, Any],
            generation: str) -> None:
        if self.engine is None:
            return
        try:
            from sqlalchemy import text
            with self.engine.begin() as conn:
                conn.execute(text(
                    "insert into l4_r_site_generations "
                    "(org_id, site, cache_key, payload, generation) "
                    "values (:o, :s, :k, cast(:p as jsonb), :g) "
                    "on conflict (org_id, site, cache_key) do nothing"),
                    {"o": org_id, "s": site, "k": key,
                     "p": canonical_dumps(dict(payload)), "g": generation})
        except Exception:      # noqa: BLE001 — failing to cache must never fail the card
            _log.exception("R-site cache write failed for org=%s site=%s", org_id, site)


# =================================================================================================
# THE GATE, USED
# =================================================================================================

def make_gate(*, org_id: str, engine: Any = None, client: Any = None,
              record_cost: Callable[..., None] | None = None,
              activated: frozenset[str] | None = None, eval_time: Any = None) -> RSiteGate:
    """One tenant's gate for the length of one run, wired to the real store and the real ledger.

    Built once per sweep or per request and reused: `activated_features` is read once so a
    connection blip cannot leave one card narrated and the next not, and the budget advances
    IN PROCESS so the ceiling binds within a sweep rather than only between sweeps. Those are the
    gate's own reasons; this helper exists so R-1, R-3 and R-4 cannot each invent a different way of
    constructing it.
    """
    store = None
    if engine is not None:
        from genios_engine.reason.bundle.store import BundleStore
        store = BundleStore(engine)
    return RSiteGate(org_id=org_id, engine=engine, client=client, store=store,
                     activated=activated, cost_recorder=record_cost, eval_time=eval_time)


def make_site_client(tier: str):
    """The Anthropic client for one tier, or None when no key is configured.

    None is a first-class answer: every site falls back to its template, which is exactly what a
    deployment without a key should do — plainer cards, never missing ones.
    """
    try:
        from genios_engine.platform.config import get_settings
        settings = get_settings()
        if not getattr(settings, "use_real_llm", False) or not settings.anthropic_api_key:
            return None
        from genios_engine.context.llm.client import LLMClient
        return LLMClient(api_key=settings.anthropic_api_key, model=tier_model(tier))
    except Exception:      # noqa: BLE001 — a client we cannot build is a template fallback
        _log.exception("could not build the R-site client for tier=%s", tier)
        return None


def tier_model(tier: str) -> str:
    """The model id for a tier. T1 follows the engine's configured (Haiku-class) model; T2 names the
    Sonnet-class id this repository already uses on its deep-analysis path, so the two agree about
    what "the stronger model" is instead of drifting apart in two files."""
    if tier == "T2":
        return "claude-sonnet-5"
    try:
        from genios_engine.platform.config import get_settings
        return str(get_settings().anthropic_model or "claude-haiku-4-5")
    except Exception:      # noqa: BLE001
        return "claude-haiku-4-5"


def with_correction(prompt: str, feedback: str | None) -> str:
    """The retry's prompt: the original, plus the ONE rule the last answer broke.

    Appended rather than woven in, so the instruction the model reads on attempt two is a superset
    of the one it read on attempt one — a rewritten prompt would make a second failure impossible to
    attribute to either the rule or the rewrite.
    """
    if not feedback:
        return prompt
    return f"{prompt}\n\nCORRECTION — your previous answer was refused. {feedback}"


def run_site(*, site: str, org_id: str, seed: Mapping[str, Any], precondition: bool,
             build_prompt: Callable[[str | None], str],
             parse: Callable[[Mapping[str, Any]], Mapping[str, Any]],
             fallback: Callable[[], Mapping[str, Any]],
             gate: RSiteGate | None = None, cache: Any = None,
             subject_ref: str | None = None,
             feature: str = FEATURE_BUNDLE) -> SiteResult:
    """One site through `RSiteGate.consult`, with this module's cache and refusal shape.

    `build_prompt(feedback)` is called lazily — so a site that will not run never pays to compose a
    prompt — and is handed the ONE rule the previous attempt broke on the retry (see
    :func:`with_correction`); `parse` raises
    :class:`SiteRejection` so a refusal carries its own reason code; `fallback` is called on every
    branch that did not produce a generation and must be pure and deterministic — it is what the
    customer reads when the model is unavailable, over budget, switched off, or wrong.

    `gate=None` means "no gate was wired here", and it is answered the way "no client" is answered:
    the deterministic template, receipted. A missing gate must never read as permission.
    """
    require_site(site)
    key = cache_key(site=site, org_id=org_id, seed=seed)
    tier = tier_for(site)

    def _fallen(outcome: str, *reasons: str, **extra: Any) -> SiteResult:
        return SiteResult(dict(fallback()), SiteReceipt(
            site=site, outcome=outcome, generation=TEMPLATE_FALLBACK, cache_key=key, tier=tier,
            reason_codes=tuple(reasons), **extra))

    if gate is None:
        return _fallen(OUTCOME_NO_CLIENT, "no_gate_wired")

    def _cached():
        if cache is None:
            return None
        return cache.get(org_id, site, key)

    def _validate(payload: Mapping[str, Any]):
        try:
            value = dict(parse(dict(payload)))
        except SiteRejection as rejection:
            return None, (rejection.reason,), {"refused": rejection.reason,
                                               "detail": rejection.detail,
                                               "feedback": _feedback(rejection)}
        return value, (), {"accepted": True}

    result = gate.consult(site=site, cache_key=key, build_prompt=build_prompt,
                          validate=_validate, feature=feature, precondition=precondition,
                          precondition_reason="precondition_absent", cached=_cached,
                          subject_ref=subject_ref)

    if result.outcome == OUTCOME_CACHED and isinstance(result.value, Mapping):
        payload = {name: value for name, value in result.value.items() if name != "generation"}
        generation = str(result.value.get("generation") or TEMPLATE_FALLBACK)
        return SiteResult(payload, SiteReceipt.of(result, generation=generation))

    if result.outcome == OUTCOME_RAN and isinstance(result.value, Mapping):
        generation = require_generation(
            f"llm:{result.model or tier_model(tier)}@{PROMPT_VERSION}")
        payload = dict(result.value)
        if cache is not None:
            cache.put(org_id, site, key, payload, generation)
        return SiteResult(payload, SiteReceipt.of(result, generation=generation))

    return SiteResult(dict(fallback()), SiteReceipt.of(result, generation=TEMPLATE_FALLBACK))


def _feedback(rejection: SiteRejection) -> str:
    """What the ONE retry is told. Specific, and never a hint at the answer.

    The gate carries `feedback` back into the second prompt, so a rejection that says only "invalid"
    buys a re-roll while one that names the rule buys a correction. What it must not do is supply
    content — "you wrote a digit, use the placeholder" is a rule; "say 2800 basis points" would be
    the validator writing the narrative.
    """
    return {
        "bare_number": "Your previous answer contained a digit. Numbers are written as "
                       "{placeholder} names from the list you were given, never as digits.",
        "unresolved_placeholder": "Your previous answer used a placeholder that does not exist. "
                                  "Use only the placeholder names you were given.",
        "unverifiable_quotation": "Your previous answer quoted wording that was not given to you. "
                                  "Quote only the exact wordings offered, or quote nothing.",
        "names_no_recorded_option": "Your previous answer named none of the options that were "
                                    "listed. Explain only those.",
        "over_length": "Your previous answer was too long. Two or three sentences.",
        "no_number_referenced": "Your previous answer used none of the placeholders. Use at least "
                                "one.",
        "classification_outside_enum": "Your previous answer was not one of the listed "
                                       "classifications. Choose exactly one of them.",
        "confidence_outside_band": "Your previous answer's confidence was outside the allowed "
                                   "range.",
    }.get(rejection.reason, "Your previous answer did not meet the stated rules. Follow them "
                            "exactly.")


__all__ = ["FALLBACK_OUTCOMES", "InMemorySiteCache", "OUTCOMES", "OUTCOME_BUDGET",
           "OUTCOME_CACHED", "OUTCOME_FAILED_GENERATION", "OUTCOME_FAILED_VALIDATION",
           "OUTCOME_FORCE_FAILED", "OUTCOME_NOT_ACTIVATED", "OUTCOME_NO_CLIENT",
           "OUTCOME_PRECONDITION", "OUTCOME_RAN", "PROMPT_VERSION", "PostgresSiteCache", "SITES",
           "SITE_R1", "SITE_R3", "SITE_R4", "SiteReceipt", "SiteRejection", "SiteResult",
           "cache_key", "cost_micro_usd", "force_failed", "make_gate", "make_site_client",
           "run_site", "tier_for", "tier_model", "with_correction"]
