"""The delivery admission contract — what Layer 5.2 is allowed to answer, and nothing else.

Layer 5 decides **whether a person should be told something**.  This contract is the vocabulary
of the question that comes after: *given that they should be told, may it happen now, to them,
on this channel?*  Those are genuinely different questions and conflating them is how a system
starts either paging people at 3am or quietly deciding on their behalf that a churn alert was
not worth their evening.

Exactly three answers exist, and the set is deliberately closed:

  ``SEND``      the moment is fine — hand it to the adapter.
  ``DEFER``     the message is right, the moment is wrong.  It waits until ``not_before``.
  ``SUPPRESS``  it must never travel this way.  Not later, not louder.

**Why DEFER is not a failure.**  This is the single most important distinction in the file.
The outbox already has a retry ladder for *failures* — a webhook timing out, a 500 from Slack —
and that ladder is bounded, because a channel that never works must eventually stop being tried.
Deferral is the opposite kind of event: nothing is broken, the recipient is simply asleep.  If
deferral consumed retry attempts, a message queued at 22:00 would burn its four attempts against
quiet hours and be declared permanently undeliverable by breakfast — the exact message the
recipient most wanted.  ``deliver/outbox.py`` therefore routes a DEFER through a path that moves
the clock and touches nothing else, and ``tests/test_delivery_gate.py`` locks that behaviour.

**Why the composition rule is "most restrictive wins".**  Several units judge the same delivery
independently — policy asks whether it is permitted, timing asks whether the moment is humane —
and a delivery must satisfy *all* of them.  ``combine`` is therefore an intersection, not a vote:
one SUPPRESS ends it, and among deferrals the *latest* window is the binding one, because
satisfying the earliest would violate the other.  Adding a fourth unit later is adding a decision
to the fold; it can only ever make the system quieter, never louder, which is the correct
direction for a mechanism that spends human attention.

Import rule: this module sits in ``contracts/`` and may import nothing above ``platform``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from genios_engine.contracts.execution import ChannelClass
from genios_engine.contracts.validators import (
    freeze_mapping,
    require_aware,
    require_bool,
    require_enum,
    require_identifier,
)

DELIVERY_VERSION = "delivery.v1"
DELIVERY_OBJECT_VERSION = "delivery-object.v1"
DELIVERY_RESULT_VERSION = "delivery-result.v1"

#: The three urgency names, weakest first.  This orders them; it does not *assign* them —
#: ``deliver/bands.py`` cuts a band from a score using the pack's own thresholds, and those
#: thresholds stay the single tenant-facing dial.  Ordering and assignment are different
#: concerns, and only the second one is configurable, so stating the order here duplicates no
#: knob: a tenant who redefines what "critical" means redefines it in exactly one place.
BAND_ORDER: tuple[str, ...] = ("standard", "high", "critical")

#: Channel classes whose arrival makes a device buzz in somebody's pocket.
#:
#: Only ``CHAT`` for now, and the omissions are deliberate rather than pending.  ``IN_APP`` and
#: ``DIGEST`` are surfaces a person visits when *they* choose to; gating them on quiet hours
#: would delay a dashboard card that was never going to wake anyone.  ``EMAIL`` is absent
#: because email is the channel people already treat as asynchronous — an inbox at 03:00 is not
#: an interruption, it is a queue — and the day an email adapter ships with different semantics,
#: this set is the one line that changes.
INTRUSIVE_CHANNEL_CLASSES: frozenset[ChannelClass] = frozenset({ChannelClass.CHAT})


class DeliveryVerdict(str, Enum):
    """The closed set of answers to "may this be delivered now?"."""

    SEND = "send"
    DEFER = "defer"
    SUPPRESS = "suppress"


class DeliveryResultStatus(str, Enum):
    """The public lifecycle of one materialised delivery.

    The outbox has a few implementation-specific states (for example ``failed_terminal``).
    Those names must not leak into the cross-layer contract, so they are projected onto this
    smaller, stable vocabulary by ``deliver/results.py``.
    """

    QUEUED = "queued"
    DEFERRED = "deferred"
    DELIVERED = "delivered"
    SUPPRESSED = "suppressed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: How much each verdict constrains the delivery.  ``combine`` folds on this, so the ordering
#: *is* the composition law: nothing a unit can return may loosen what another unit decided.
_RESTRICTIVENESS: Mapping[DeliveryVerdict, int] = MappingProxyType({
    DeliveryVerdict.SEND: 0,
    DeliveryVerdict.DEFER: 1,
    DeliveryVerdict.SUPPRESS: 2,
})


@dataclass(frozen=True, slots=True)
class DeliveryCandidate:
    """One delivery awaiting admission — the subject every unit judges.

    Deliberately thin.  It carries what a unit needs to decide *whether this may travel now* and
    nothing about what it says: no headline, no facts, no payload.  A timing unit that could read
    the message body would eventually be asked to make an exception for an important-sounding one,
    and at that point "should I interrupt?" has quietly become a second reasoning engine sitting
    below the real one.  Loudness was decided upstairs; this layer only decides admissibility.
    """

    org_id: str
    subject_id: str                  # the outbox key — a card id, digest key, or exec: reminder
    channel: str                     # the concrete adapter: 'slack'
    channel_class: ChannelClass      # the intent: chat, digest, in_app, agent
    band: str                        # standard | high | critical
    interrupt: bool                  # Layer 5's judgement that this is worth someone's attention
    recipient: str | None = None     # seat id; None = an org-wide surface with no single owner

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "org_id", require_identifier(self.org_id, "org id"))
        setattr_(self, "subject_id", require_identifier(self.subject_id, "subject id"))
        setattr_(self, "channel", require_identifier(self.channel, "channel"))
        setattr_(self, "channel_class",
                 require_enum(self.channel_class, ChannelClass, "channel class"))
        setattr_(self, "interrupt", require_bool(self.interrupt, "interrupt"))
        band = require_identifier(self.band, "band")
        if band not in BAND_ORDER:
            raise ValueError(f"band must be one of {BAND_ORDER}, got {band!r}")
        setattr_(self, "band", band)
        if self.recipient is not None:
            setattr_(self, "recipient", require_identifier(self.recipient, "recipient"))

    @property
    def band_rank(self) -> int:
        return BAND_ORDER.index(self.band)

    @property
    def intrusive(self) -> bool:
        """Does landing this message cost the recipient attention they did not choose to spend?

        This — not ``interrupt`` — is what quiet hours key on.  Layer 5 sets ``interrupt`` to mean
        "this deserves attention"; a high-band card is pushed to Slack with ``interrupt=False``,
        and it still pings a phone at midnight.  Gating on the channel's physics rather than on
        the sender's intent is what closes that gap.
        """
        return self.channel_class in INTRUSIVE_CHANNEL_CLASSES

    def at_least(self, band: str) -> bool:
        """True when this candidate is at or above ``band`` — the break-glass comparison."""
        if band not in BAND_ORDER:
            raise ValueError(f"band must be one of {BAND_ORDER}, got {band!r}")
        return self.band_rank >= BAND_ORDER.index(band)

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "subject_id": self.subject_id, "channel": self.channel,
                "channel_class": self.channel_class.value, "band": self.band,
                "interrupt": self.interrupt, "recipient": self.recipient}


@dataclass(frozen=True, slots=True)
class DeliveryObject:
    """The typed Layer 5.2 input materialised on an outbox row.

    Layer 5 owns the recipient, priority and interruption decision. Layer 5.2 adds a concrete
    destination, payload and retry policy. Keeping this immutable contract beside the admission
    contract makes the existing "outbox row is the delivery object" design explicit without a
    second persistence table or a second write that could drift.
    """

    delivery_id: str
    org_id: str
    subject_id: str
    channel: str
    channel_class: ChannelClass
    band: str
    interrupt: bool
    payload: Mapping[str, Any]
    recipient: str | None = None
    retry_minutes: tuple[int, ...] = ()
    created_at: datetime | None = None
    schema_version: str = DELIVERY_OBJECT_VERSION

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "delivery_id", require_identifier(self.delivery_id, "delivery id"))
        setattr_(self, "org_id", require_identifier(self.org_id, "org id"))
        setattr_(self, "subject_id", require_identifier(self.subject_id, "subject id"))
        setattr_(self, "channel", require_identifier(self.channel, "channel"))
        setattr_(self, "channel_class",
                 require_enum(self.channel_class, ChannelClass, "channel class"))
        setattr_(self, "interrupt", require_bool(self.interrupt, "interrupt"))
        band = require_identifier(self.band, "band")
        if band not in BAND_ORDER:
            raise ValueError(f"band must be one of {BAND_ORDER}, got {band!r}")
        setattr_(self, "band", band)
        if self.recipient is not None:
            setattr_(self, "recipient", require_identifier(self.recipient, "recipient"))
        setattr_(self, "payload", freeze_mapping(self.payload))
        retry = tuple(self.retry_minutes)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
               for value in retry):
            raise ValueError("retry_minutes must contain positive integers")
        if tuple(sorted(set(retry))) != retry:
            raise ValueError("retry_minutes must be sorted and unique")
        setattr_(self, "retry_minutes", retry)
        if self.created_at is not None:
            setattr_(self, "created_at", require_aware(self.created_at, "created_at"))
        setattr_(self, "schema_version",
                 require_identifier(self.schema_version, "delivery object schema version"))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "delivery_id": self.delivery_id,
            "org_id": self.org_id,
            "subject_id": self.subject_id,
            "recipient": self.recipient,
            "channel": self.channel,
            "channel_class": self.channel_class.value,
            "band": self.band,
            "interrupt": self.interrupt,
            "payload": self.payload,
            "retry_minutes": self.retry_minutes,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """The stable Layer 5.2 output consumed by analytics and Layer 6 learning.

    It is a projection of durable outbox state, not a second mutable copy. ``metrics`` carries
    transport facts only (attempts, deferrals and latency); it may never contain a new score or
    recommendation.
    """

    delivery_id: str
    org_id: str
    subject_id: str
    channel: str
    status: DeliveryResultStatus
    attempts: int
    deferrals: int
    recipient: str | None = None
    delivered_at: datetime | None = None
    reason_code: str | None = None
    metrics: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    schema_version: str = DELIVERY_RESULT_VERSION

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "delivery_id", require_identifier(self.delivery_id, "delivery id"))
        setattr_(self, "org_id", require_identifier(self.org_id, "org id"))
        setattr_(self, "subject_id", require_identifier(self.subject_id, "subject id"))
        setattr_(self, "channel", require_identifier(self.channel, "channel"))
        setattr_(self, "status",
                 require_enum(self.status, DeliveryResultStatus, "delivery result status"))
        for name in ("attempts", "deferrals"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.recipient is not None:
            setattr_(self, "recipient", require_identifier(self.recipient, "recipient"))
        if self.delivered_at is not None:
            setattr_(self, "delivered_at", require_aware(self.delivered_at, "delivered_at"))
        if self.reason_code is not None:
            setattr_(self, "reason_code", require_identifier(self.reason_code, "reason code"))
        setattr_(self, "metrics", freeze_mapping(self.metrics))
        setattr_(self, "metadata", freeze_mapping(self.metadata))
        setattr_(self, "schema_version",
                 require_identifier(self.schema_version, "delivery result schema version"))

    def to_semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "delivery_id": self.delivery_id,
            "org_id": self.org_id,
            "subject_id": self.subject_id,
            "recipient": self.recipient,
            "channel": self.channel,
            "status": self.status.value,
            "attempts": self.attempts,
            "deferrals": self.deferrals,
            "delivered_at": self.delivered_at,
            "reason_code": self.reason_code,
            "metrics": self.metrics,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class DeliveryDecision:
    """One unit's verdict on one delivery, with the reason it reached it.

    ``unit`` and ``reason_code`` are both mandatory and both identifiers.  When somebody asks
    "why didn't I get told about this?" — and that question is asked far more often, and far more
    angrily, than "why did I get told about this?" — the answer has to already be in the row.
    A bare boolean would make every such question a debugging session against a clock that has
    since moved on.
    """

    verdict: DeliveryVerdict
    unit: str
    reason_code: str
    not_before: datetime | None = None
    detail: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        setattr_ = object.__setattr__
        setattr_(self, "verdict", require_enum(self.verdict, DeliveryVerdict, "delivery verdict"))
        setattr_(self, "unit", require_identifier(self.unit, "deciding unit"))
        setattr_(self, "reason_code", require_identifier(self.reason_code, "delivery reason code"))
        if self.not_before is not None:
            setattr_(self, "not_before", require_aware(self.not_before, "not_before"))
        setattr_(self, "detail", freeze_mapping(self.detail))

        # The two halves of the same invariant.  A DEFER without a clock is a message that waits
        # forever; a SEND *with* one is a unit that meant to defer and forgot to say so.  Both are
        # silent-loss bugs in production, so both are construction-time errors here.
        if self.verdict is DeliveryVerdict.DEFER and self.not_before is None:
            raise ValueError(
                f"{self.unit} deferred '{self.reason_code}' without a not_before: "
                "a deferral with no clock never wakes up")
        if self.verdict is not DeliveryVerdict.DEFER and self.not_before is not None:
            raise ValueError(
                f"{self.unit} returned {self.verdict.value} with a not_before; "
                "only a deferral carries a clock")

    # ---- derived -----------------------------------------------------------------------

    @property
    def restrictiveness(self) -> int:
        return _RESTRICTIVENESS[self.verdict]

    @property
    def blocks_delivery(self) -> bool:
        return self.verdict is not DeliveryVerdict.SEND

    def is_satisfied_at(self, now: datetime) -> bool:
        """Has this constraint stopped biting by ``now``?

        A deferral whose window has already opened is satisfied — the constraint was "not before
        08:00", and it is 08:30.  Written as a comparison rather than assumed away because clocks
        skew, sweeps get paused, and a deferral that outlived its own reason must not keep a
        message hostage; the failure mode of the alternative is a queue that silently never
        drains.  A suppression is never satisfied by the passage of time, which is exactly what
        distinguishes it from a deferral.
        """
        if self.verdict is DeliveryVerdict.SEND:
            return True
        if self.verdict is DeliveryVerdict.SUPPRESS:
            return False
        return require_aware(now, "now") >= self.not_before        # type: ignore[operator]

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict.value, "unit": self.unit,
                "reason_code": self.reason_code, "not_before": self.not_before,
                "detail": self.detail}

    def describe(self) -> str:
        when = f" until {self.not_before.isoformat()}" if self.not_before else ""
        return f"{self.verdict.value}{when} · {self.unit}:{self.reason_code}"

    # ---- constructors ------------------------------------------------------------------

    @classmethod
    def send(cls, unit: str, reason_code: str, **detail: Any) -> DeliveryDecision:
        return cls(verdict=DeliveryVerdict.SEND, unit=unit, reason_code=reason_code,
                   detail=detail)

    @classmethod
    def defer(cls, unit: str, reason_code: str, not_before: datetime,
              **detail: Any) -> DeliveryDecision:
        return cls(verdict=DeliveryVerdict.DEFER, unit=unit, reason_code=reason_code,
                   not_before=not_before, detail=detail)

    @classmethod
    def suppress(cls, unit: str, reason_code: str, **detail: Any) -> DeliveryDecision:
        return cls(verdict=DeliveryVerdict.SUPPRESS, unit=unit, reason_code=reason_code,
                   detail=detail)

    # ---- composition -------------------------------------------------------------------

    @staticmethod
    def combine(*decisions: DeliveryDecision) -> DeliveryDecision:
        """Fold independent judgements into the one a delivery must actually obey.

        Intersection semantics, and the tie-breaks are all *deterministic* rather than merely
        correct.  Two units that both suppress must always name the same reason in the audit row,
        or the same delivery blocked twice would be explained two different ways depending on
        dictionary ordering — the kind of nondeterminism that turns an incident review into
        an argument.  So: first SUPPRESS in argument order wins; among DEFERs the latest window
        wins, breaking ties on argument order; otherwise the first SEND.
        """
        if not decisions:
            raise ValueError("combine() requires at least one decision")
        if any(not isinstance(item, DeliveryDecision) for item in decisions):
            raise TypeError("combine() takes DeliveryDecision instances")

        strongest = max(item.restrictiveness for item in decisions)
        binding = [item for item in decisions if item.restrictiveness == strongest]
        if strongest == _RESTRICTIVENESS[DeliveryVerdict.DEFER]:
            # max() keeps the first maximum, so equal windows resolve to argument order.
            return max(binding, key=lambda item: item.not_before)   # type: ignore[arg-type,return-value]
        return binding[0]


__all__ = ["BAND_ORDER", "DELIVERY_OBJECT_VERSION", "DELIVERY_RESULT_VERSION",
           "DELIVERY_VERSION", "INTRUSIVE_CHANNEL_CLASSES", "DeliveryCandidate",
           "DeliveryDecision", "DeliveryObject", "DeliveryResult", "DeliveryResultStatus",
           "DeliveryVerdict"]
