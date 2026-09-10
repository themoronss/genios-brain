"""Canonical observation-kind vocabulary + polarity — owned by CONTEXT (layer 2).

The L2 normalizer (context/pipeline.norm_obs_kind) emits these canonical kinds; the
polarity split lives beside the vocabulary it classifies. reason/ (layer 4) imports
this DOWNWARD for derived sentiment; context/attention reads it for the attention
score. (It used to live in reason/signals_derived — which forced context to either
import upward or duplicate the sets.)"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

OBS_POSITIVE: frozenset[str] = frozenset({
    "budget_approved", "buying_intent", "pricing_discussed", "positive_reply",
    "champion_engaged", "next_step_agreed", "verbal_yes", "contract_requested",
    "demo_requested", "stakeholder_added", "security_review_started",
    # ADMIN / FUNDRAISING. Everything above this line is a buyer moving through a pipeline, and
    # for a company whose correspondence is approvals, invoices and investor threads that
    # vocabulary is not thin — it is about somebody else's business. `diligence_started` is the
    # fundraising reading of `security_review_started` and deliberately not the same word: a fund
    # opening diligence is not a customer's security team, and one card must never be written as
    # though it were the other.
    "approval_granted", "intro_made", "diligence_started", "payment_confirmed",
})

OBS_NEGATIVE: frozenset[str] = frozenset({
    "objection", "objection_price", "objection_timing", "objection_security",
    "objection_authority", "objection_integration", "competitor", "going_dark",
    "churn_risk", "negative_reply", "price_pushback", "stakeholder_left",
    "discount_pressure", "budget_freeze", "champion_change", "timeline_slip",
    "closed_lost_mention",
    # `pass_received` is NOT `closed_lost_mention`. A fund passing is frequently reversible — the
    # same accelerator invites a re-application to the next cohort — and filing it as a lost deal
    # is what produced "Save the deal now" on a fundraising rejection.
    "pass_received", "approval_blocked", "payment_overdue", "decision_deferred",
})


#: The complete set the extractor may emit — polarity-bearing kinds plus the neutral ones the
#: prompt has always asked for. Named here rather than duplicated in the prompt so a kind cannot
#: be added to one and forgotten in the other, which is precisely how `verbal_yes` came to be
#: required by a rule and emitted by nothing.
OBS_NEUTRAL: frozenset[str] = frozenset({
    "meeting_request", "followup_sent", "introduction", "question", "proposal_sent",
    "legal_review",
    # The administrative and fundraising moments. Neutral because each is a fact about the
    # exchange, not a verdict on it: an approval REQUEST is neither good nor bad news until it is
    # answered, and `context/waiting.py` reads exactly these to tell "we are waiting on an answer
    # we asked for" apart from "we simply have not written lately".
    "approval_requested", "information_requested", "intro_requested",
    "document_sent", "investor_update_sent", "invoice_sent",
    "meeting_scheduled", "meeting_cancelled", "deadline_stated",
})

#: Where the per-kind MEANING record lives. One row per kind, four answers each.
KINDS_FILE = Path(__file__).resolve().parent / "observations" / "kinds.yaml"


@dataclass(frozen=True, slots=True)
class ObservationMeaning:
    """What one observation kind MEANS, in the three places that used to decide separately."""

    kind: str
    polarity: str = "neutral"
    is_ask: bool = False
    is_progress: bool = False


def load_meanings(path: "Path | None" = None) -> dict[str, ObservationMeaning]:
    """`{kind: meaning}` from `observations/kinds.yaml`.

    THE SPLIT THIS CLOSES. A kind was authorable at the EXTRACTION end — `extract/vocab.py`
    unions a tenant's own kinds into the prompt, so the model will happily emit
    `sample_collected` — and hardcoded at the MEANING end, across three Python literals in three
    files: polarity here, `_ASK_KINDS` in `waiting.py`, `_PROGRESS_KINDS` in `derived.py`. A new
    kind reached the graph and then scored ZERO everywhere: neutral sentiment, not an ask, not
    progress. Not refused and not flagged — silently weightless.

    FAILS SOFT TO AN EMPTY MAP, whose callers fall back to their own literals. A file that will
    not parse must not empty the polarity table and make every observation in the tenant read
    neutral; the shipped sets are what was there yesterday and keeping them is strictly safer.
    """
    import yaml

    target = path or KINDS_FILE
    out: dict[str, ObservationMeaning] = {}
    try:
        if not target.is_file():
            return out
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        for row in (data.get("kinds") or []):
            kind = str((row or {}).get("kind") or "").strip()
            if not kind:
                continue
            polarity = str(row.get("polarity") or "neutral").strip().lower()
            out[kind] = ObservationMeaning(
                kind=kind,
                polarity=polarity if polarity in ("positive", "negative", "neutral") else "neutral",
                is_ask=bool(row.get("is_ask")), is_progress=bool(row.get("is_progress")))
    except Exception:      # noqa: BLE001 — see FAILS SOFT above
        return {}
    return out


#: Read once. The file ships with the engine and cannot change under a running process.
OBSERVATION_MEANINGS: dict[str, ObservationMeaning] = load_meanings()


def kinds_where(**flags) -> frozenset[str]:
    """Every kind whose meaning matches — `kinds_where(is_ask=True)`, `kinds_where(polarity=...)`.

    THE ONE QUERY the three former literals are now expressed as, so "which kinds are asks" has
    one answer rather than three that can drift.
    """
    return frozenset(m.kind for m in OBSERVATION_MEANINGS.values()
                     if all(getattr(m, key, None) == value for key, value in flags.items()))


CANONICAL_OBS_KINDS: frozenset[str] = (
    frozenset(OBSERVATION_MEANINGS) or (OBS_POSITIVE | OBS_NEGATIVE | OBS_NEUTRAL))


#: How the kinds are PRESENTED to the extractor, and the reason this lives here rather than in the
#: prompt: the prompt carried its own hand-typed copy of the list, so `CANONICAL_OBS_KINDS` could
#: grow without the model ever being told the new words existed. `context/extract/vocab.py`
#: computed the tenant-aware union in `signal_kinds()` — and nothing ever called it. Two
#: vocabularies, one of them dead, and the live one frozen at whatever was typed into the prompt.
#:
#: Grouping is not decoration. An unlabelled list of forty tokens makes a model reach for the
#: nearest word; a labelled one makes it ask which KIND of moment this is first, which is the
#: distinction that keeps a fund's pass out of the sales pipeline.
OBS_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Buying", ("budget_approved", "verbal_yes", "next_step_agreed", "contract_requested",
                "demo_requested", "security_review_started", "stakeholder_added",
                "pricing_discussed", "proposal_sent", "buying_intent", "champion_engaged")),
    ("Risk", ("competitor", "discount_pressure", "budget_freeze", "champion_change",
              "legal_review", "timeline_slip", "going_dark", "closed_lost_mention",
              "churn_risk", "stakeholder_left")),
    ("Objection", ("objection", "objection_price", "objection_timing", "objection_security",
                   "objection_authority", "objection_integration")),
    ("Sentiment", ("positive_reply", "negative_reply", "price_pushback")),
    ("Approvals & requests", ("approval_requested", "approval_granted", "approval_blocked",
                              "information_requested", "decision_deferred")),
    ("Money & documents", ("invoice_sent", "payment_confirmed", "payment_overdue",
                           "document_sent", "deadline_stated")),
    ("Fundraising & network", ("intro_requested", "intro_made", "investor_update_sent",
                               "diligence_started", "pass_received")),
    ("Meetings", ("meeting_request", "meeting_scheduled", "meeting_cancelled")),
    ("General", ("followup_sent", "introduction", "question")),
)
