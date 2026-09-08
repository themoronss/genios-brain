"""C5 · the LLM Decision Policy — the one door every R-site passes through.

`reason/` contained no model call site at all before this wave, which is stricter than the founder
asked for and is the direct cause of "mute". This module opens the first door in the layer, and it
is what makes opening it safe: **no R-site may call a model directly.** Every consult goes through
`RSiteGate.consult`, which runs doc 01 C5's seven steps in order —

    1. is this site permitted for this org?    l4_activation(org, feature)
    2. is the precondition met?                the SITE's own, never "just in case"
    3. is there budget left today?             doc 11 — else deterministic template
    4. is a cached result available?           keyed on decision_hash / fact digest
    5. run the site under its tier and timeout T1/T2 per MAP A
    6. validate the output                     the caller's validator (the V-gauntlet, for R-2)
    7. on any failure: deterministic fallback  recorded — never a retry storm, never silence

— and records the outcome of every one of them, including the ones where no model ran.

**The gate decides nothing about the business.** It answers "may a model be consulted", never "what
should happen". Score, rank, priority, permission, policy, elimination and confidence composition
are all somewhere else and all deterministic. Nothing about a decision changes if every consult
here fails; only the prose gets plainer, and `tests/reason/test_bundle_doctrine.py` is the property
test that says so.

**TWO DELIBERATE DEVIATIONS FROM DOC 01's NUMBERING, both kept and both recorded here rather than
discovered later.**

* *The cache is read BEFORE the budget*, not after. A hit costs nothing, so refusing one for want
  of budget would make a tenant's card go plain on a day whose narrative had already been paid for
  — and the cache is exactly what doc 11 guard 2 relies on to make a re-surfaced decision free.
* *The budget is checked AFTER the prompt is built*, not before. The estimate is a function of the
  prompt's size, and a ceiling checked against a guess at a prompt is a ceiling that binds against
  a number nobody can reproduce. Building a prompt costs no money and no I/O; the check that
  precedes it is "is there a model at all", which does.

Both are tested positionally in `tests/reason/test_bundle_doctrine.py`, because the order IS the
policy.

**ONE retry, then the template.** Doc 05 §4 and doc 11 guard 4. The retry carries the gauntlet's
specific complaint, because the single regeneration is the only chance to turn a near miss into a
narrative and "invalid output" wastes it.

**Nothing here raises.** A consult is an enhancement on top of a decision that is already made and
already stored; an exception escaping this module would turn a model outage into a failed sweep.
Every path returns a `ConsultResult` whose `outcome` says what happened.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from genios_engine.platform.l4_activation import FEATURE_BUNDLE
from genios_engine.platform.logging import get_logger

from .budget import NarrativeBudget, cost_micro_usd, estimate_micro_usd
from .sites import (
    OUTCOME_CACHED,
    OUTCOME_FAILED_GENERATION,
    OUTCOME_FAILED_VALIDATION,
    OUTCOME_FORCE_FAILED,
    OUTCOME_NOT_ACTIVATED,
    OUTCOME_NO_BUDGET,
    OUTCOME_NO_CLIENT,
    OUTCOME_NO_PRECONDITION,
    OUTCOME_RAN,
    max_output_tokens,
    require_site,
    tier_for,
)

_log = get_logger("genios.reason.bundle.gate")

#: The doctrine switch. With this on, every R-site is refused and a full replay must produce
#: BYTE-IDENTICAL DecisionObjects — if it ever does not, the model has acquired decision authority
#: and the wave is reverted (doc 01 C5 acceptance, doc 08 K4). An env var so the property can be
#: checked against a running deployment and not only in a unit test.
FORCE_FAIL_ENV = "GENIOS_L4_FORCE_FAIL_R_SITES"

#: How many generations one consult may spend. One call, one retry. Not configurable: doc 11 guard
#: 4 is "no retry storms", and a retry count read from configuration is a retry storm with an
#: audit trail.
MAX_ATTEMPTS = 2


def force_fail_r_sites() -> bool:
    """Whether every R-site is currently refused. Read at the consult, never cached."""
    return str(os.environ.get(FORCE_FAIL_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}


@contextmanager
def force_failed():
    """Refuse every consult for the duration. The doctrine test's switch, and an operator's."""
    previous = os.environ.get(FORCE_FAIL_ENV)
    os.environ[FORCE_FAIL_ENV] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(FORCE_FAIL_ENV, None)
        else:
            os.environ[FORCE_FAIL_ENV] = previous


@dataclass(frozen=True, slots=True)
class ConsultResult:
    """What one trip through the gate produced, and what it cost.

    `value` is None on every outcome in `FALLBACK_OUTCOMES`: the caller then uses its deterministic
    fallback. It is deliberately not "a fallback the gate produced" — the gate does not know what a
    good plain version of an interpretation or a narrative looks like, and a gate that invented one
    would be a gate with an opinion about the product.
    """

    site: str
    outcome: str
    tier: str
    cache_key: str
    value: Any = None
    reason_codes: tuple[str, ...] = ()
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micro_usd: int = 0
    attempts: int = 0
    #: Every generation the model produced this consult, in order, with the checks that judged it.
    #: Doc 05 §4 records every outcome on the trace; a consult that failed twice has two.
    trace: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.outcome in {OUTCOME_RAN, OUTCOME_CACHED}


class RSiteGate:
    """One tenant's permission to consult a model, for the length of one run.

    Constructed ONCE per sweep and reused across every consult in it, for two reasons that are both
    correctness rather than efficiency: `activated_features` is read once so a connection blip
    cannot leave one decision narrated and the next not, and `NarrativeBudget` advances in process
    so the ceiling binds WITHIN a sweep rather than only between sweeps.
    """

    def __init__(self, *, org_id: str, engine=None, client=None, store=None,
                 budget: NarrativeBudget | None = None,
                 activated: frozenset[str] | None = None,
                 cost_recorder: Callable[..., None] | None = None,
                 eval_time=None) -> None:
        self.org_id = org_id
        self._engine = engine
        self._client = client
        self._store = store
        self._cost_recorder = cost_recorder
        self._activated = (frozenset(activated) if activated is not None
                           else self._read_activation(engine, org_id))
        self._budget = budget or NarrativeBudget.from_settings(
            org_id=org_id, engine=engine, now=eval_time)

    @staticmethod
    def _read_activation(engine, org_id: str) -> frozenset[str]:
        from genios_engine.platform.l4_activation import activated_features
        return activated_features(engine, org_id)

    @property
    def activated(self) -> frozenset[str]:
        return self._activated

    @property
    def budget(self) -> NarrativeBudget:
        return self._budget

    @property
    def model(self) -> str | None:
        """The model snapshot this gate would call, or None when none is configured. Public
        because the narrator has to stamp `generation` with it, and reaching into the client
        through the gate's private attribute would make the stamp depend on an implementation
        detail of a module that is allowed to change."""
        return getattr(self._client, "model", None) if self._client is not None else None

    def permits(self, feature: str = FEATURE_BUNDLE) -> bool:
        """Step 1 alone — for a caller deciding whether to do the WORK of building a prompt."""
        return feature in self._activated

    # ── the seven steps ──────────────────────────────────────────────────────────────────────

    def consult(self, *, site: str, cache_key: str, build_prompt: Callable[[str | None], str],
                validate: Callable[[Mapping[str, Any]], tuple[Any, tuple[str, ...],
                                                              Mapping[str, Any]]],
                feature: str = FEATURE_BUNDLE, precondition: bool = True,
                precondition_reason: str = "precondition_absent",
                cached: Callable[[], Any] | None = None,
                purpose: str | None = None, subject_ref: str | None = None) -> ConsultResult:
        """Run one R-site under the policy. Never raises.

        `validate` returns `(value_or_None, reason_codes, trace_record)`. The trace record is what
        the gate stores beside the outcome — for R-2 it is the gauntlet's row per check, which is
        what makes "the model is bad at root causes on this tenant" answerable from the ledger
        rather than from a re-run.
        """
        require_site(site)
        tier = tier_for(site)
        base = {"site": site, "tier": tier, "cache_key": cache_key}

        # ── 1 · permitted for this org? ──────────────────────────────────────────────────────
        if feature not in self._activated:
            return self._record(ConsultResult(
                outcome=OUTCOME_NOT_ACTIVATED, reason_codes=(f"l4_{feature}_not_activated",),
                **base))

        # ── the doctrine switch, checked before anything is built or spent. ──────────────────
        if force_fail_r_sites():
            return self._record(ConsultResult(
                outcome=OUTCOME_FORCE_FAILED, reason_codes=("r_sites_force_failed",), **base))

        # ── 2 · precondition. Never "just in case" (doc 11 guard 7). ─────────────────────────
        if not precondition:
            return self._record(ConsultResult(
                outcome=OUTCOME_NO_PRECONDITION, reason_codes=(precondition_reason,), **base))

        # ── 3 · cache BEFORE budget. A hit costs nothing, so refusing one for want of budget
        #        would make a tenant's card go plain on a day it had already been paid for. ───
        if cached is not None:
            try:
                hit = cached()
            except Exception as exc:      # noqa: BLE001 — an unreadable cache is an empty cache
                _log.warning("cache read failed for org=%s site=%s: %s", self.org_id, site, exc)
                hit = None
            if hit is not None:
                return self._record(ConsultResult(
                    outcome=OUTCOME_CACHED, value=hit, **base))

        # ── 4 · a model must exist at all. ───────────────────────────────────────────────────
        if self._client is None:
            return self._record(ConsultResult(
                outcome=OUTCOME_NO_CLIENT, reason_codes=("no_model_configured",), **base))

        try:
            prompt = build_prompt(None)
        except Exception as exc:      # noqa: BLE001 — a prompt that cannot be built is a skip
            _log.exception("could not build the %s prompt for org=%s", site, self.org_id)
            return self._record(ConsultResult(
                outcome=OUTCOME_FAILED_GENERATION,
                reason_codes=("prompt_build_failed", type(exc).__name__), **base))

        # ── 5 · budget, against the ACTUAL prompt rather than a guess at one. ────────────────
        ceiling = max_output_tokens(site)
        verdict = self._budget.check(estimate_micro_usd(
            site=site, prompt_chars=len(prompt), max_output_tokens=ceiling))
        if not verdict.allowed:
            return self._record(ConsultResult(
                outcome=OUTCOME_NO_BUDGET, reason_codes=(verdict.reason or "budget_refused",),
                **base))

        # ── 6 · call and validate. One retry, carrying the specific complaint. ───────────────
        spent = 0
        tokens_in = tokens_out = 0
        model = getattr(self._client, "model", None)
        trace: list[Mapping[str, Any]] = []
        feedback: str | None = None
        last_codes: tuple[str, ...] = ()
        # Which KIND of failure the last attempt was. Tracked rather than inferred at the end: an
        # outcome derived from the shape of the trace is an outcome that changes meaning the next
        # time the loop grows a branch.
        last_outcome = OUTCOME_FAILED_GENERATION
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                try:
                    prompt = build_prompt(feedback)
                except Exception:      # noqa: BLE001
                    break
                verdict = self._budget.check(estimate_micro_usd(
                    site=site, prompt_chars=len(prompt), max_output_tokens=ceiling))
                if not verdict.allowed:
                    # The retry itself is unaffordable. The FIRST attempt's failure is still the
                    # reason there is no narrative, so it keeps its outcome; the budget is added
                    # as a second reason code rather than replacing it.
                    last_codes = (*last_codes, verdict.reason or "budget_refused")
                    break
            try:
                result = self._client.call(prompt, max_tokens=ceiling)
            except Exception as exc:      # noqa: BLE001 — a client that raises is a failed call
                _log.warning("%s call raised for org=%s: %s", site, self.org_id, exc)
                trace.append({"attempt": attempt, "error": type(exc).__name__})
                last_codes, last_outcome = ("model_call_raised",), OUTCOME_FAILED_GENERATION
                feedback = None
                continue
            call_in = int(getattr(result, "input_tokens", 0) or 0)
            call_out = int(getattr(result, "output_tokens", 0) or 0)
            tokens_in += call_in
            tokens_out += call_out
            charged = cost_micro_usd(tier=tier, input_tokens=call_in, output_tokens=call_out)
            spent += charged
            self._budget.charge(charged)
            self._record_platform_cost(model=getattr(result, "model", model) or "",
                                       purpose=purpose or f"l4_{site.lower().replace('-', '')}",
                                       input_tokens=call_in, output_tokens=call_out,
                                       ok=bool(getattr(result, "ok", True)),
                                       error=getattr(result, "error", None),
                                       subject_ref=subject_ref)
            if not getattr(result, "ok", False):
                trace.append({"attempt": attempt, "error": str(getattr(result, "error", ""))[:200]})
                last_codes, last_outcome = ("unparseable_generation",), OUTCOME_FAILED_GENERATION
                feedback = ("Your previous answer was not valid JSON. Answer with the JSON object "
                            "only, no prose around it.")
                continue
            try:
                value, codes, record = validate(dict(getattr(result, "parsed", {}) or {}))
            except Exception as exc:      # noqa: BLE001 — a validator that raises is a refusal
                _log.exception("the %s validator raised for org=%s", site, self.org_id)
                value, codes, record = None, ("validator_raised", type(exc).__name__), {}
            trace.append({"attempt": attempt, **dict(record)})
            if value is not None:
                return self._record(ConsultResult(
                    outcome=OUTCOME_RAN, value=value, model=model, input_tokens=tokens_in,
                    output_tokens=tokens_out, cost_micro_usd=spent, attempts=attempt,
                    trace=tuple(trace), **base))
            last_codes, last_outcome = codes, OUTCOME_FAILED_VALIDATION
            feedback = str(record.get("feedback") or "") or None

        # ── 7 · every failure ends in the caller's deterministic fallback, recorded. ─────────
        return self._record(ConsultResult(
            outcome=last_outcome, reason_codes=tuple(last_codes) or ("generation_failed",), model=model,
            input_tokens=tokens_in, output_tokens=tokens_out, cost_micro_usd=spent,
            attempts=len(trace), trace=tuple(trace), **base))

    # ── the receipts ─────────────────────────────────────────────────────────────────────────

    def _record(self, result: ConsultResult) -> ConsultResult:
        """Step 2 of C5's reverse prompt: every gate outcome on the record, skips included."""
        if self._store is not None:
            try:
                self._store.record_call(
                    org_id=self.org_id, site=result.site, outcome=result.outcome,
                    tier=result.tier, cache_key=result.cache_key, model=result.model,
                    input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                    cost_micro_usd=result.cost_micro_usd, attempts=result.attempts,
                    reason_codes=result.reason_codes)
            except Exception as exc:      # noqa: BLE001 — wrapped HERE as well as in the store
                # `BundleStore.record_call` already swallows its own database errors, but the gate
                # accepts ANY store — a fake in a test, a decorated one in an operator script — and
                # a receipt that can abort the thing it is a receipt for turns an accounting
                # failure into a product failure. A lost row mis-states a dashboard; a raised
                # exception here costs the narration.
                _log.warning("could not record the %s consult for org=%s: %s",
                             result.site, self.org_id, exc)
        return result

    def _record_platform_cost(self, *, model: str, purpose: str, input_tokens: int,
                              output_tokens: int, ok: bool, error: object,
                              subject_ref: str | None) -> None:
        """`llm_costs` as well as this layer's own ledger.

        Both, not either. `l4_r_site_calls` is what the narrative budget is measured against and it
        knows the site and the tier; `llm_costs` is what the platform's spend, the admin console and
        the daily cap are measured against, and a layer that spent money without appearing there is
        the exact gap that made reported spend drift below the real bill once already.
        """
        if self._cost_recorder is None:
            return
        try:
            self._cost_recorder(org_id=self.org_id, model=model or "unknown", purpose=purpose,
                                input_tokens=input_tokens, output_tokens=output_tokens,
                                success=ok, error=(str(error)[:400] if error else None),
                                subject_ref=subject_ref)
        except Exception as exc:      # noqa: BLE001 — a ledger write must not fail a consult
            _log.warning("could not record l4 narrative spend for org=%s: %s", self.org_id, exc)


__all__ = ["ConsultResult", "FORCE_FAIL_ENV", "MAX_ATTEMPTS", "RSiteGate", "force_fail_r_sites",
           "force_failed"]
