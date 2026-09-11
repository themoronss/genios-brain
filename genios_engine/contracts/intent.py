"""C-INTENT · why a message was sent, and how it was written.

WHAT THIS IS NOT, FIRST, BECAUSE IT IS THE EASIEST THING TO GET WRONG. This is NOT a fifteenth
member of :class:`~genios_engine.contracts.signal.SignalType`. That enum answers *"what business
event happened"* — a deadline was stated, a commitment was made — and `esqe/classifier.py` picks
ONE primary from it by a fixed precedence. Intent answers a different question: *"what kind of
exchange is this"*. Folding the two would force a ranking between "promotional" and "escalation",
and neither answer is right, because a promotional email can also state a deadline. A message is
BOTH, and this contract is what lets it be both: intent travels BESIDE `signal_type`, never
inside it.

WHY IT IS NEEDED. Measured on the pilot, 2026-09-11: of 889 captured events, **815 carried no
domain at all** — the four domain regexes (`fundraising`, `sales`, `support`, `admin`) matched
8% of the mail. And nothing anywhere answered "is this a vendor pitch, an interview thread, a
receipt". The system classified EVENTS and never the EXCHANGE, which is the same hole that
leaves `party.role` at one fact and `thread.objective` at zero.

TWO STANDINGS, AND THE LINE BETWEEN THEM IS THE WHOLE DESIGN. Some of these fields are READ off
the message — the category, the tone, whether a human wrote it, whether it asks for a reply.
Those are observations and carry a receipt. Others are JUDGEMENTS about what is likely — whether
this exchange is worth the reader's attention. A judgement is marked as one, ranks below an
observation wherever the two meet, and may never be presented as a fact. `contracts/extraction`
draws the same line for business facts and this follows it deliberately.

WHAT IS DELIBERATELY ABSENT. "How much respect does this person have for us", "what are their
values", "will this convert" — these are claims about a RELATIONSHIP over time, or about the
future. One message cannot carry them, and a field that invites a model to invent them would be
a fact-shaped guess in a contract whose whole job is to keep the two apart. Engagement is offered
as a banded JUDGEMENT and nothing stronger.

UNKNOWN IS A REAL ANSWER AND IS NEVER GUESSED. Every enum here carries an explicit `unknown`
member, and every optional field is `None` when the message does not say. An intent the model
could not read must arrive as absent, because the gate downstream treats a missing intent as "do
not filter on this" and a wrong one as permission to delete somebody's mail.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from genios_engine.contracts.evidence import EvidenceSpan

#: The longest a free-text motive may be. It is a phrase a reader scans, not a summary.
MAX_MOTIVE_CHARS = 160


class IntentCategory(str, Enum):
    """WHAT KIND OF EXCHANGE this message is. Readable from the message itself.

    The one axis the junk gate can act on: `AUTOMATED` and `PROMOTIONAL` are what a founder means
    by "noise", and they are separated because they fail differently. An automated message is
    machinery and nobody is waiting; a promotional message has a human behind it who WILL follow
    up, and deleting it silently is how a real vendor conversation disappears.
    """

    #: Machinery. A digest, a platform notification, a build result, a delivery receipt.
    AUTOMATED = "automated"
    #: Somebody is selling to us, and a person is behind it. Cold outreach, a vendor pitch.
    PROMOTIONAL = "promotional"
    #: A record of something that already happened. An invoice, a receipt, a calendar invite,
    #: a confirmation. Not noise — it is often the only evidence an obligation exists.
    TRANSACTIONAL = "transactional"
    #: The business actually being done. A customer, a deal, a supplier, an obligation.
    WORKING = "working"
    #: A person, about the relationship rather than a transaction. An introduction, a
    #: congratulation, a check-in, a thank-you.
    RELATIONAL = "relational"
    #: Read, and genuinely unclear. NOT the default for an unread message — see the module note.
    UNKNOWN = "unknown"


class Tone(str, Enum):
    """The register the message is written in. An observation about the words, not about the
    sender: a curt message from a busy person is `DIRECT`, not evidence of a bad relationship."""

    NEUTRAL = "neutral"
    WARM = "warm"
    DIRECT = "direct"
    URGENT = "urgent"
    FRUSTRATED = "frustrated"
    APOLOGETIC = "apologetic"
    UNKNOWN = "unknown"


class Formality(str, Enum):
    """How the message is composed. Useful downstream because a reply should match the register
    it is answering, and because a templated blast reads differently from a written note."""

    FORMAL = "formal"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    TEMPLATED = "templated"
    UNKNOWN = "unknown"


class Band(str, Enum):
    """A judgement expressed in three steps rather than a number.

    Deliberately not basis points. A model asked for 0..10000 produces a false precision that
    every downstream reader then treats as measured — the same mistake `relevance.py` refuses
    when it says of its own gate *"Do not return any score, rating, probability or number"*.
    Three bands can be argued with; 6,400 cannot.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class MessageIntent(BaseModel):
    """Why this message was sent and how it was written. One per message, never per claim.

    The OBSERVED half (category, tone, formality, the three booleans, `motive`) is read off the
    message and carries `evidence`. The JUDGED half (`engagement`) is a reading of what the
    observed half implies and is marked as such by living in its own field with its own band.
    """

    # ── observed: what kind of exchange, and how it is written ────────────────────────────
    category: IntentCategory = IntentCategory.UNKNOWN
    tone: Tone = Tone.UNKNOWN
    formality: Formality = Formality.UNKNOWN

    #: WHAT THE SENDER WANTS, in a phrase. `None` when the message does not make it plain —
    #: never a restatement of the subject line, and never "unknown" as a string.
    motive: str | None = None

    # ── observed: who it was aimed at ─────────────────────────────────────────────────────
    #: Written TO this tenant, as opposed to a list. `None` = the message does not show it.
    #: This is the single most useful field for telling a vendor blast from a vendor who has
    #: actually read our site, and it is why `PROMOTIONAL` alone is not enough to delete on.
    addressed_personally: bool | None = None
    #: A person composed this, as opposed to a system. `None` = cannot tell.
    human_authored: bool | None = None
    #: The sender is waiting on us. `None` = cannot tell. An automated message that asks for
    #: nothing and a working message that asks for a decision are the two ends of this.
    asks_for_reply: bool | None = None

    # ── judged: what the observed half implies ────────────────────────────────────────────
    #: Whether this exchange is worth the reader's attention, as a JUDGEMENT. It may inform a
    #: ranking and may never, on its own, delete anything: `contracts/abstention`'s rule that an
    #: inference must not act with an observation's authority is the same rule here.
    engagement: Band = Band.UNKNOWN

    #: The spans the OBSERVED half rests on. Empty is legal — a message may be classified from
    #: its shape (headers, a templated body) with nothing worth quoting — but a `motive` without
    #: one is refused below, because a stated purpose is a claim about words and must show them.
    evidence: list[EvidenceSpan] = Field(default_factory=list)

    @field_validator("motive")
    @classmethod
    def _motive_is_a_phrase_or_nothing(cls, value: str | None) -> str | None:
        """An empty, whitespace or placeholder motive is ABSENT, not a value.

        `unknown`/`n/a` written into a field is the failure `contracts/extraction` names for
        business values: it satisfies a completeness check while telling the reader nothing, and
        every consumer downstream then has to know the sentinel. Absent is honest and typed.
        """
        if value is None:
            return None
        cleaned = " ".join(str(value).split())
        if not cleaned or cleaned.casefold() in {
                "unknown", "none", "null", "n/a", "not known", "unclear", "-"}:
            return None
        return cleaned[:MAX_MOTIVE_CHARS]

    @property
    def observed_anything(self) -> bool:
        """Did the reader learn ANYTHING about this exchange.

        A record where every axis is `unknown` and every boolean is `None` is the model saying
        "I could not read this", and it must be distinguishable from one that says "this is an
        automated receipt nobody is waiting on" — the second is information, the first is not.
        """
        return (self.category is not IntentCategory.UNKNOWN
                or self.tone is not Tone.UNKNOWN
                or self.formality is not Formality.UNKNOWN
                or self.motive is not None
                or self.addressed_personally is not None
                or self.human_authored is not None
                or self.asks_for_reply is not None)

    @property
    def is_noise(self) -> bool:
        """May the gate treat this as junk ON THIS EVIDENCE ALONE?

        ONLY an automated message that asks nothing of us. Promotional is deliberately excluded:
        a human is behind it, they will follow up, and `capture/gate/rules` already records what
        over-matching costs — `support@` and `hello@` are a real small business. A transactional
        message is excluded outright because an invoice IS the evidence an obligation exists.

        `asks_for_reply is False` and not `not asks_for_reply`: `None` means the reader could not
        tell, and "could not tell" must never read as "nobody is waiting".
        """
        return (self.category is IntentCategory.AUTOMATED
                and self.asks_for_reply is False
                and self.human_authored is not True)


#: What an absent reading looks like. Importable so a caller never has to spell the empty record
#: and so `MessageIntent()` changing shape cannot silently change what "we did not read" means.
UNREAD = MessageIntent()


__all__ = ["MAX_MOTIVE_CHARS", "UNREAD", "Band", "Formality", "IntentCategory", "MessageIntent",
           "Tone"]
