"""R-2 · the narrator — the five prose sections for ONE fixed decision.

The order is the doctrine, and it is not negotiable:

    the decision is fixed  ->  the material is gathered  ->  the numbers are computed
    ->  a model may be consulted (through the gate, never directly)
    ->  the gauntlet judges the raw generation
    ->  code attaches the citations, code substitutes the numbers
    ->  the constructor refuses anything that got past all of that

Nothing in this module can change what was decided. `ReasoningBundle.for_decision` derives
`decision_id` and `action_id` from the decision and REFUSES either as an argument, so there is no
expression in this file that can name an action; and `ReasoningDecision.with_bundle` re-enters the
decision's constructor, which checks the match again. That is why a model can write freely here.

**Citations are attached by code, never generated.** The model may QUOTE an authored claim and V-2
checks the quotation is byte-identical, but the `citations` tuple on the bundle is the decision's
own, copied. A model that could add a citation could add a source.

**A cache hit is an answer, not a shortcut.** Doc 11 guard 2 and loop L-2: the same decision
re-surfaced tomorrow must read exactly as it read today, so the cache is keyed on the decision hash
and a hit ends the consult before any prompt is built.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.reasoning import (
    BUNDLE_PROSE_FIELDS,
    ReasonerResult,
    ReasoningBundle,
    ReasoningDecision,
    ReasoningRequest,
    placeholders,
)
from genios_engine.platform.l4_activation import FEATURE_BUNDLE
from genios_engine.platform.logging import get_logger

from .gate import ConsultResult, RSiteGate
from .gauntlet import GauntletReport, run_gauntlet
from .grounding import Grounding, build_grounding
from .numbers import Catalogue, build_catalogue
from .prompt import build_prompt
from .sites import SITE_NARRATE
from .store import BundleStore, StoredBundle
from .template import template_bundle

_log = get_logger("genios.reason.bundle.narrator")

#: Why a decision was not narrated at all. Distinct from "narrated with the template": one is a
#: plainer card, the other is no card content, and K4's first row measures the second.
SKIP_NO_ACTION = "decision_committed_to_no_action"
SKIP_NO_GROUNDING = "decision_carries_no_evidence_or_citation"


@dataclass(frozen=True, slots=True)
class Narration:
    """One decision's narrative, and everything that produced it."""

    bundle: ReasoningBundle
    consult: ConsultResult
    catalogue: Catalogue
    grounding: Grounding
    gauntlet: GauntletReport | None = None
    cached: bool = False

    @property
    def is_fallback(self) -> bool:
        return self.bundle.generation == "template_fallback"

    def gauntlet_records(self) -> list[dict[str, Any]]:
        return self.gauntlet.as_records() if self.gauntlet is not None else []


def narrate(decision: ReasoningDecision, results: Sequence[ReasonerResult] = (), *,
            gate: RSiteGate, eval_time: datetime,
            request: ReasoningRequest | None = None,
            store: BundleStore | None = None, run_id: str | None = None,
            store_decision_hash: str | None = None,
            evidence_refs: Sequence[str] | None = None, locale: str = "en",
            subject_ref: str | None = None) -> Narration | None:
    """Narrate one PUBLISHED decision. Returns None when there is nothing to narrate.

    None rather than an empty bundle for the two cases where a narrative would have to invent
    something: a decision that committed to no action (there is no action id, so Law 2 forbids
    minting one) and a decision with no evidence and no citation at all (the constructor refuses a
    narrative grounded in nothing, which is the ungrounded explanation this group exists to
    replace). Both are counted by the caller rather than logged and forgotten.
    """
    if decision.action_id is None:
        _log.debug("not narrating a %s decision: %s", decision.outcome.value, SKIP_NO_ACTION)
        return None

    catalogue = build_catalogue(decision, results, eval_time=eval_time)
    grounding = build_grounding(decision, results, request=request)
    citations = tuple(decision.citations)
    refs = tuple(evidence_refs) if evidence_refs is not None else grounding.evidence_refs
    if not refs and not citations:
        _log.debug("not narrating decision %s: %s", decision.decision_id, SKIP_NO_GROUNDING)
        return None

    cache_key = decision.semantic_hash

    def _cached() -> StoredBundle | None:
        if store is None:
            return None
        return store.get(org_id=gate.org_id, decision_hash=cache_key,
                         expect_action_id=decision.action_id)

    def _prompt(feedback: str | None) -> str:
        return build_prompt(decision, catalogue=catalogue, grounding=grounding,
                            citations=citations, feedback=feedback, locale=locale)

    report_box: dict[str, GauntletReport] = {}

    def _validate(parsed: Mapping[str, Any]) -> tuple[Any, tuple[str, ...], Mapping[str, Any]]:
        """The V-gauntlet, then the constructor. In that order, and both.

        The gauntlet runs on the RAW mapping so every check's outcome is recorded even when an
        earlier one already failed — doc 05 §4 asks for the outcomes in order, and a constructor
        that raises on the first problem can report exactly one. The constructor then runs anyway:
        it holds V-3's id half, which the gauntlet structurally cannot check, and it is the last
        thing between a generation and a customer.
        """
        generation = {name: parsed[name] for name in BUNDLE_PROSE_FIELDS
                      if isinstance(parsed.get(name), str) and parsed.get(name).strip()}
        extra = sorted(set(map(str, parsed)) - set(BUNDLE_PROSE_FIELDS))
        judged = dict(generation)
        for name in extra:
            judged[name] = parsed[name]
        report = run_gauntlet(judged, decision=decision, catalogue=catalogue,
                              grounding=grounding, citations=citations)
        report_box["report"] = report
        record: dict[str, Any] = {"gauntlet": report.as_records(), "feedback": report.feedback()}
        if not report.passed:
            return None, report.reason_codes, record
        used = catalogue.subset(
            [name for text in generation.values() for name in placeholders(text)])
        try:
            bundle = ReasoningBundle.for_decision(
                decision, **generation,
                citations=citations, evidence_refs=refs, numbers_used=used,
                generation=_generation_label(gate))
        except Exception as exc:      # noqa: BLE001 — the constructor is a validator here
            record["constructor_error"] = f"{type(exc).__name__}: {exc}"
            record["feedback"] = f"- constructor rejected the bundle: {exc}"
            return None, ("constructor_refused",), record
        return bundle, (), record

    consult = gate.consult(
        site=SITE_NARRATE, cache_key=cache_key, feature=FEATURE_BUNDLE,
        build_prompt=_prompt, validate=_validate, cached=_cached,
        purpose="l4_bundle", subject_ref=subject_ref)

    if isinstance(consult.value, StoredBundle):
        # A HIT still refreshes the pointer. The same situation re-decided next sweep publishes a
        # NEW signal whose `reasoning_decision_hash` nothing joins to yet; without this the card
        # would never carry the prose that already exists for it, and the sweep would re-list the
        # decision on every run forever.
        if store is not None and store_decision_hash:
            try:
                store.put(org_id=gate.org_id, decision_hash=cache_key,
                          bundle=consult.value.bundle, gauntlet=list(consult.value.gauntlet),
                          attempts=consult.value.attempts,
                          cost_micro_usd=consult.value.cost_micro_usd, run_id=run_id,
                          store_decision_hash=store_decision_hash)
            except Exception:      # noqa: BLE001 — a stale pointer is not a failed narration
                _log.exception("could not refresh the narrative pointer for org=%s decision=%s",
                               gate.org_id, cache_key)
        return Narration(bundle=consult.value.bundle, consult=consult, catalogue=catalogue,
                         grounding=grounding, cached=True)
    if isinstance(consult.value, ReasoningBundle):
        narration = Narration(bundle=consult.value, consult=consult, catalogue=catalogue,
                              grounding=grounding, gauntlet=report_box.get("report"))
    else:
        # Doc 05 §6 — the honest plain version, labelled so nobody mistakes it for a narrative.
        narration = Narration(
            bundle=template_bundle(decision, catalogue=catalogue, grounding=grounding,
                                   citations=citations, evidence_refs=refs),
            consult=consult, catalogue=catalogue, grounding=grounding,
            gauntlet=report_box.get("report"))

    if store is not None:
        try:
            store.put(org_id=gate.org_id, decision_hash=cache_key, bundle=narration.bundle,
                      gauntlet=narration.gauntlet_records(), attempts=consult.attempts,
                      cost_micro_usd=consult.cost_micro_usd, run_id=run_id,
                      store_decision_hash=store_decision_hash)
        except Exception:      # noqa: BLE001 — a narrated decision must not fail on its receipt
            _log.exception("could not store the narrative for org=%s decision=%s",
                           gate.org_id, cache_key)
    return narration


def _generation_label(gate: RSiteGate) -> str:
    """`llm:<model>@<version>`, from the client the gate actually holds.

    The model id is split on the last `-` so a dated Anthropic snapshot
    (`claude-haiku-4-5-20251001`) records as `llm:claude-haiku-4-5@20251001` — which is what makes
    "did the narrative change when we moved model" answerable from the column rather than from a
    deploy log. A model id with no dated suffix records `@unversioned`, honestly.
    """
    model = str(gate.model or "").strip()
    if not model:
        return "llm:unknown@unversioned"
    head, _, tail = model.rpartition("-")
    if head and tail.isdigit():
        return f"llm:{head}@{tail}"
    return f"llm:{model}@unversioned"


__all__ = ["Narration", "SKIP_NO_ACTION", "SKIP_NO_GROUNDING", "narrate"]
