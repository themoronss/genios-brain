"""L2.7.7 · the vocabulary M-4 speaks, and the shapes it hands to deterministic code.

THE ONE RULE THIS FILE ENCODES: **the model describes, the code decides.** M-4 is handed a
message and a list of obligations and answers two DESCRIPTIVE questions — *what kind of
statement is this* (`verdict`) and *how plainly does it say the thing is finished*
(`certainty`) — plus a verbatim quote it must point at. It is never handed the close, it never
sees the authority table, and it never produces the number that is compared to the floor.

`ResolutionDescription` is therefore deliberately NOT a decision: it has no `decision`, no
`applied`, no status. `ResolutionClaim` is the decision, and every field on it that carries
weight (`authority_bp`, `certainty_bp`, `effective_bp`) was computed here from a LABEL the model
chose out of a closed set — never read off a number the model wrote.

WHY A LABEL RATHER THAN THE `confidence_bp` DOC 07 PRINTS. Doc 07's M-4 return shape names
`confidence_bp`; doc 12's first cross-cutting rule says *"No `_bp` output, ever. No LLM at L2
produces a number that feeds ranking."* The two cannot both be honoured literally, so the model
names a band and `CERTAINTY_BP` below turns that band into basis points. A model that returns a
`confidence_bp` anyway is not an error — the field is READ AND DISCARDED, and
`tests/context/lifecycle/test_resolution.py` pins that it is discarded — because silently
trusting it is exactly how a described certainty becomes a scored one. Recorded as **A-16** in
`docs/plans/L2_MISSING_UNIT_SPECS.md` §3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# ── what the model may say ───────────────────────────────────────────────────────────────────

#: The four verdicts, exactly as doc 07 L2.7.7-U1 lists them. A verdict outside this set is a
#: parse failure, not a fifth outcome: an unknown word from a model is an unknown INTENT, and
#: guessing which of the four it meant is guessing about closing a live thread.
VERDICT_RESOLVED = "RESOLVED"
VERDICT_PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
VERDICT_NOT_RESOLVED = "NOT_RESOLVED"
VERDICT_CONTRADICTED = "CONTRADICTED"
VERDICTS: frozenset[str] = frozenset({VERDICT_RESOLVED, VERDICT_PARTIALLY_RESOLVED,
                                      VERDICT_NOT_RESOLVED, VERDICT_CONTRADICTED})

#: HOW PLAINLY the message says it. This is the description that replaces a model-authored score.
#: The bands are ordered and the gap between the first two is deliberate — an implied completion
#: is a reading, an explicit one is a report.
CERTAINTY_EXPLICIT = "EXPLICIT_COMPLETION"     # "we signed yesterday", "ho gaya, sign kar diya"
CERTAINTY_IMPLIED = "IMPLIED_COMPLETION"       # "you should have everything you need now"
CERTAINTY_INTENT = "INTENT_ONLY"               # "we should wrap this up", "kal kar denge"
CERTAINTY_AMBIGUOUS = "AMBIGUOUS"              # irony, one-liners, no checkable specifics
CERTAINTIES: frozenset[str] = frozenset({CERTAINTY_EXPLICIT, CERTAINTY_IMPLIED,
                                         CERTAINTY_INTENT, CERTAINTY_AMBIGUOUS})

#: Band → basis points. INTENT_ONLY is ZERO and not merely low: doc 12 case 1 calls a
#: forward-looking modal a HARD NEGATIVE SIGNAL, and a hard negative that still contributes 2000
#: bp is a soft one. `judge.py` also refuses an INTENT_ONLY carrying a RESOLVED verdict outright,
#: so the zero is a second lock on the same door rather than the only one.
CERTAINTY_BP: dict[str, int] = {
    CERTAINTY_EXPLICIT: 9000,
    CERTAINTY_IMPLIED: 6500,
    CERTAINTY_INTENT: 0,
    CERTAINTY_AMBIGUOUS: 3000,
}

# ── who said it (deterministic — never the model's answer) ───────────────────────────────────

ROLE_OWNER = "owner"          # the obligation's own owner
ROLE_INTERNAL = "internal"    # org-internal, but not the owner
ROLE_EXTERNAL = "external"    # the counterparty. "we're done" from a vendor is a CLAIM
ROLE_MACHINE = "machine"      # a no-reply / service account. Ignored entirely, at the gate

#: Doc 07's speaker-authority table in integer basis points — 1.0 / 0.8 / 0.6, and the fourth row
#: has no weight because it never reaches a weighting: `authority.py` refuses it at the gate.
#: Integers because doctrine 2 forbids a float anywhere a decision is computed, and because
#: `9000 * 6000 // 10000` is exactly 5400 on every machine while `9000 * 0.6` is a promise.
AUTHORITY_BP: dict[str, int] = {ROLE_OWNER: 10_000, ROLE_INTERNAL: 8_000, ROLE_EXTERNAL: 6_000}

# ── what deterministic code decides ──────────────────────────────────────────────────────────

DECISION_APPLY = "apply"      # strong enough to move the situation's lifecycle
DECISION_REVIEW = "review"    # a human queue entry, NEVER a card (doc 12, cross-cutting rule 7)
DECISION_REJECT = "reject"    # nothing happened here worth storing a queue entry for

#: Above this, a statement may close a situation by itself.
#:
#: The number is derived from the table above rather than chosen: the LOWEST product that must
#: close is an org-internal explicit completion, 9000 * 8000 // 10000 = 7200, and the HIGHEST
#: that must NOT is an external explicit completion, 9000 * 6000 // 10000 = 5400 — doc 12 case 3,
#: *"a vendor-stated close is below floor without corroboration"*. 7000 sits between them with
#: room on both sides, and every band under EXPLICIT lands beneath it for every speaker, which is
#: the asymmetry doc 12 demands: an IMPLIED completion by the owner (6500) is a nudge we may
#: skip, never a thread we close.
CLOSE_FLOOR_BP = 7_000

#: Below THIS a claim is not even worth a human's attention — an ambiguous line from a
#: counterparty (1800) is noise, and a review queue that collects noise is a queue nobody reads.
#: Between the two floors is the queue.
REVIEW_FLOOR_BP = 3_000

#: Doc 12 case 4: *never auto-close on a single short message.* A completion statement carrying
#: enough context to be checkable is rarely shorter than this; sarcasm ("well that's sorted then
#: 🙄") almost always is. A short message can still reach the REVIEW queue — it is the automatic
#: CLOSE that it can never earn. Measured on the message, not on the quote: the quote is short by
#: construction, and it is the surrounding message that makes it checkable.
SHORT_MESSAGE_CHARS = 80

#: The prompt and the answer shape are versioned separately, and both are stored on every claim.
#: A claim whose prompt version is unknown cannot be re-derived, only re-guessed — the same
#: reason `importance_version` exists one module over.
PROMPT_VERSION = "m4.1.0"
SCHEMA_VERSION = "m4-schema.1.0"


@dataclass(frozen=True, slots=True)
class Obligation:
    """One thing this situation is still waiting on, as M-4 is shown it.

    `obligation_id` is what `scope` must name. Doc 12 case 8 — a resolution of a DIFFERENT thing
    in the same thread — is closed by requiring the model to name which of these it is talking
    about, and by `judge.py` rejecting a verdict that names none of them.
    """

    obligation_id: str
    subject: str
    #: The address the obligation belongs to, lower-cased. `None` when the graph never recorded
    #: one — in which case nobody can speak with OWNER authority about it, and `authority.py`
    #: says so rather than guessing that the sender must be the owner.
    owner_email: str | None = None


@dataclass(frozen=True, slots=True)
class Message:
    """The message that landed on the situation, and the identity of whoever wrote it.

    `text` is the PREPARED text — the same string L1's spans are measured against — because the
    offsets M-4 returns are verified with L1's own ALG-08 validator and a validator run against a
    different rendering of the same message would fail every span it was handed.
    """

    event_id: str
    text: str
    sender_email: str | None
    occurred_at: datetime
    #: `prepared_content:<event_id>`, the literal shape `EvidenceSpan.source_ref` documents.
    source_ref: str = ""

    def __post_init__(self) -> None:
        if not self.source_ref:
            object.__setattr__(self, "source_ref", f"prepared_content:{self.event_id}")


@dataclass(frozen=True, slots=True)
class ResolutionDescription:
    """What M-4 said. A DESCRIPTION — it carries no decision and no weight.

    `raw_confidence_bp` exists so that a model which returns one anyway is recorded rather than
    trusted: it is stored on the claim for later comparison and never enters a threshold. See the
    module docstring (A-16).
    """

    verdict: str
    certainty: str
    scope: tuple[str, ...]
    quote: str
    start_offset: int
    end_offset: int
    #: What the model THOUGHT the speaker was. Recorded, never used — `authority.py` derives the
    #: role from the sender's identity, which is a fact we hold, not a reading of the prose.
    speaker_role_said: str | None = None
    raw_confidence_bp: int | None = None


@dataclass(frozen=True, slots=True)
class ResolutionClaim:
    """The deterministic verdict on one description: what it means, and what we may do with it.

    Every number here was computed by `judge.py` from a label and the authority table. `reason`
    is the receipt — doctrine 3 — and it is stored, so *"why did this situation close"* and *"why
    did this one only reach the queue"* are answerable from the row without re-running anything.
    """

    situation_id: str
    event_id: str
    stated_at: datetime
    verdict: str
    certainty: str
    scope: tuple[str, ...]
    speaker_email: str | None
    speaker_role: str
    authority_bp: int
    certainty_bp: int
    effective_bp: int
    decision: str
    reason: str
    quote: str = ""
    source_ref: str = ""
    start_offset: int = 0
    end_offset: int = 0
    span_verdict: str = ""
    raw_confidence_bp: int | None = None
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION
    model: str = ""

    @property
    def closes(self) -> bool:
        """Whether this claim, on its own, moves the situation out of ACTIVE."""
        return self.decision == DECISION_APPLY and self.verdict in (
            VERDICT_RESOLVED, VERDICT_PARTIALLY_RESOLVED)


@dataclass(frozen=True, slots=True)
class DetectionSweep:
    """What one drain's resolution pass actually did — the operator's ledger for this site.

    `budget_exhausted` is a FIELD and not a log line for the reason doc 11 gives: an org above a
    budget otherwise looks exactly like an org with nothing to resolve, and the miss it caused is
    invisible to everyone including the tenant.
    """

    situations_examined: int = 0
    gated_out: int = 0
    calls: int = 0
    claims_written: int = 0
    resolved: int = 0
    partial: int = 0
    reopened: int = 0
    queued_for_review: int = 0
    budget_exhausted: bool = False
    fell_back_to_fact: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_record(self) -> dict:
        return {"situations_examined": self.situations_examined, "gated_out": self.gated_out,
                "calls": self.calls, "claims_written": self.claims_written,
                "resolved": self.resolved, "partial": self.partial, "reopened": self.reopened,
                "queued_for_review": self.queued_for_review,
                "budget_exhausted": self.budget_exhausted,
                "fell_back_to_fact": self.fell_back_to_fact, "notes": list(self.notes)}
