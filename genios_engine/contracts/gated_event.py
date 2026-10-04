from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from genios_engine.contracts.visibility import Visibility


class DomainHint(BaseModel):
    """One domain this message could belong to, and how sure the thing that said so was.

    `source` is WHO said it and `confidence_bp` is HOW SURE — and they are not the same question,
    which is why both are carried. A `scope` prior is a claim about whose account this is; a
    `keyword` is a claim about the words in this message; a `fallback` is the caller saying "this
    is business and nothing matched". Flattening those to one number is how the failure
    `hints.py` records happened: the generic sales vocabulary claimed investor threads, and
    *"six VCs and three accelerator programmes became sales opportunities. Not one of its sixteen
    sales situations was a customer."*
    """

    domain: str
    source: str                              # scope | keyword | history | fallback | proposed
    #: How sure, in INTEGER BASIS POINTS (0..10000). Added 2026-09-24 (step 6).
    #:
    #: `ge`/`le` rather than a plain `int`, because this is the field a model will write into
    #: and an untyped one is exactly where a `0.85` gets in — V-7 then rejects the ENTIRE signal
    #: at the seam for a fault that belongs to one hint. Pydantic refuses a float outright:
    #: `strict` is not needed, the band is, and 1.0 would otherwise coerce to 1 bp and look like
    #: near-total doubt instead of near-total certainty.
    #:
    #: DEFAULTED, not required. Every existing caller built this object with two fields, and a
    #: required third would refuse every cached `GatedEvent` ever written. The default is the
    #: KEYWORD confidence because that is what every historical hint actually was.
    confidence_bp: int = Field(default=6000, ge=0, le=10_000)

    @field_validator("confidence_bp", mode="before")
    @classmethod
    def _integer_basis_points(cls, value: Any) -> Any:
        """A float is REFUSED, never rounded. Rounding would accept 0.85 as 1 bp — a confident
        hint stored as an almost-certainly-wrong one, with nothing anywhere saying so."""
        if isinstance(value, bool) or isinstance(value, float):
            raise TypeError(
                f"domain confidence must be integer basis points, got {value!r} — a ratio here "
                "reaches jsonb and V-7 rejects the whole signal for one hint's sake")
        return value


#: ⛔⛔ **THIS CONTRACT'S OWN RULE, AND THE FIVE FIELDS OF ITS OWN THAT BREAK IT** —
#: `{field: (what happens to it, mover)}`.
#:
#: `coverage_ready`'s comment, below, states the rule:
#:
#:     A dead field on a contract is worse than a missing one: IT INVITES A CONSUMER TO TRUST A
#:     SEAM THAT CARRIES NOTHING, and None reads as "unknown" exactly where a caller most wants a
#:     yes.
#:
#: ⛔ Measured 2026-10-04 across all 21 fields: **five are set on this object and then read by
#: nothing, stored in no column, and absent from the envelope key set.** This object exists to
#: carry L1's verdict across the boundary to L2, so a field nothing on the other side reads is
#: precisely the seam that carries nothing.
#:
#: ⛔⛔ HOW THIS WAS MEASURED, AND IN WHICH DIRECTION IT IS SOUND. The resolver counts attribute
#: LOADS named `X` anywhere in `genios_engine/`, which **over-counts** — a load may be on a
#: different object entirely. So a count of **0 proves a field is never read**, and a count above 0
#: proves nothing by itself. Four of the five below are proven by that sweep. `degraded_compile`
#: shows two loads and **both were checked by hand**: they are `outcome.domains.degraded_compile`
#: and `esqe_outcome.domains.degraded_compile`, the TAGGING result, not this object. ⛔ A first
#: version of the sweep instead excluded the carrying module, which **under**-counted and produced
#: two false positives; the one-sided version is the honest one, and which side it errs on is
#: stated because a resolver that hides its direction reads as a proof.
#:
#: ⛔ `degraded_compile` IS THE WORST OF THE FIVE, because its own comment says the defect was
#: fixed. It records that *"`tag_domains` computed it on the request path, the trace row recorded
#: it, and **the boundary object dropped it** — so L2, which reads the gated event and not our
#: trace rows, could not tell a full compile from a degraded one."* The fix put the field here and
#: stopped: it is in no migration, not in `capture/esqe/signal_store.ENVELOPE_KEYS`, and absent
#: from `contracts/signal.py` — so L2, which reads the STORED signal, still cannot tell. The same
#: defect, one layer along, now wearing a comment that reads as closed.
#:
#: ⛔ AND A TEST'S OWN LABEL WAS THE FALSE WITNESS. `tests/capture/test_g56_verify_probes.py`
#: headed its probe *"D9 — degraded_compile survives to the published envelope"* while asserting
#: `gated.degraded_compile` — the object one layer EARLIER than the envelope it names. The
#: assertion was right and the heading was not. Corrected in place.
#:
#: ⛔ NOT REPAIRED HERE, and the reason is the finding rather than an excuse. Persisting any of
#: these needs a migration (`0186`–`0190` are already unapplied) or a change to the declared
#: round-trip key set plus a field on `QualifiedEnterpriseSignal` — and **there is no reader on the
#: other side for any of them.** Adding storage without one moves a dead field one layer down and
#: makes the same comment true in a new place. What L2 should DO with a degraded compile, a
#: prepared-content reference or an availability marker is a product decision.
#:
#: Checked in BOTH directions by `tests/capture/test_a_carried_field_says_where_it_dies.py`: a
#: field declared dead that something now reads is as much a lie as a dead field nobody declared.
CARRIED_BUT_NOT_PERSISTED: dict[str, tuple[str, str]] = {
    "degraded_compile": (
        "⛔⛔ THE ONE WHOSE COMMENT CLAIMS IT WAS FIXED. Computed by `capture/esqe/domain."
        "tag_domains` as `bool(uncovered)`, carried here by `capture/pipeline`, then dropped: no "
        "column, not in `ENVELOPE_KEYS`, absent from `contracts/signal`. Its two attribute loads "
        "are on the TAGGING object, not on this one — checked by hand. ⛔ `coverage_ready`, the "
        "FIRST half of the same answer, IS a column, so half the verdict crosses the boundary and "
        "half does not",
        "MOVES WHEN L3 has a reader for it. ⛔ Rohit's: *'compile in degraded mode instead of "
        "pretending full expertise'* is behaviour nobody has specified, and storing the flag "
        "before deciding that just relocates the dead field"),
    "prepared_content_ref": (
        "⛔ Set from `prepared.prepared_content_id`, read by nothing, stored nowhere. ✅ ALREADY "
        "DECLARED ELSEWHERE, and well: `contracts/signal.py` carries a GAP FLAG saying *'the link "
        "from a published signal back to the raw bytes it came from is dropped by the spec as "
        "written'* and tells whoever builds L1.6.10 to confirm the longer join is real *'before "
        "the first tenant asks where a number came from'*. ⛔ That flag's claim has HALF EXPIRED "
        "though — it says *'no `payload_ref` / `prepared_content_ref`'* and `payload_ref` is now a "
        "column with readers",
        "MOVES WITH the L1.6.10 provenance join the signal contract's GAP FLAG names. ⛔ Rohit's"),
    "structured_fields": (
        "⛔ Set from the structured lane's extracted fields: zero attribute loads anywhere, no "
        "column, not an envelope key. The name is also a LOCAL in `capture/pipeline`, which IS "
        "used — and that is the distinction a second measurement had to make, because the first "
        "sweep read the local as evidence the field was alive",
        "MOVES WITH linkage_hints — both are gate/triage output that the landing row already "
        "persists under its own columns, so the copy on this object may simply be redundant. "
        "⛔ Deciding that is reading two writers, not a guess"),
    "linkage_hints": (
        "⛔ Set from `_linkage_hints(event)`. ✅ The VALUE is persisted — `capture/landing/"
        "repository` takes it as a keyword and its docstring says *'route/triage_lane/domain_hints/"
        "linkage_hints persist the gate+triage decisions'* — but from a LOCAL, not from this "
        "field. So the data survives and this carrier does not need to",
        "MOVES WITH structured_fields — see that entry"),
    "availability_marker": (
        "⛔ Set from `gate.availability`. The same name is a FUNCTION in `capture/gate/rules`, "
        "which IS called — and conflating the two is what made a first sweep report this field as "
        "read. The field itself has zero attribute loads anywhere",
        "MOVES WHEN an out-of-office marker changes anything downstream. ⛔ "
        "`capture/pipeline` already derives `availability_notice` separately at two sites for the "
        "decisions it does make, so this may be the redundant one of the pair"),
}


class GatedEvent(BaseModel):
    """L1's output to L2 — the QualifiedEnterpriseSignal boundary object (RC-1 / B-01).

    Deterministic only — no LLM classification here. Carries the routing decision (structured
    values vs needs-extraction) plus cheap hints; L2's single combined call produces relevance
    + typed facts.

    The audit's RC-1 named this object as "does not exist"; it existed under this name and was
    missing its qualifying half. Now carried: the full participant set (`recipients`), the
    source-stamped audience (`visibility`), the domain candidates (`domain_hints`), the scoped
    coverage verdict (`coverage_ready`), the authority class (`internal_kind`), and every
    version that produced it. Still deliberately absent, by design not omission:
    `importance_bp` (importance is a REASONING output — L1 stamping it would be the priority/
    importance conflation the spec forbids) and typed role candidates (roles need the
    extraction the envelope feeds; L2's b3-3 prompt owns them).
    """

    event_id: str
    org_id: str
    source: str
    object_type: str
    occurred_at: datetime
    payload_ref: str | None = None
    prepared_content_ref: str | None = None

    route: str                               # "structured" | "needs_extraction"
    structured_fields: dict[str, Any] = Field(default_factory=dict)   # for structured route

    domain_hints: list[DomainHint] = Field(default_factory=list)
    deadline_at: datetime | None = None
    linkage_hints: list[dict[str, Any]] = Field(default_factory=list)
    triage_lane: str = "P2"
    #: Whether the tenant's sources are complete enough for a NEGATIVE inference about this
    #: event's domain ("they did not reply", "no meeting was booked").
    #:
    #: Declared here and never assigned by `_build_gated_event`, the only constructor — so it
    #: was permanently None while `coverage/model.py` computed the real answer and threw it
    #: away. A dead field on a contract is worse than a missing one: it invites a consumer to
    #: trust a seam that carries nothing, and None reads as "unknown" exactly where a caller
    #: most wants a yes.
    coverage_ready: bool | None = None
    #: Whether at least one of this event's domains was NOT covered, so L3 must compile it in
    #: degraded mode instead of pretending full expertise.
    #:
    #: The SECOND half of the answer `coverage_ready` gives, and the same defect one field
    #: along: `capture/esqe/domain.tag_domains` computed it on the request path, the trace row
    #: recorded it, and the boundary object dropped it — so L2, which reads the gated event and
    #: not our trace rows, could not tell a full compile from a degraded one. `None` means no
    #: tagger ran (a pre-S4 row); a freshly gated event always carries a real bool.
    degraded_compile: bool | None = None
    # Company canon (capture.internal_knowledge.INTERNAL_KINDS) — the authority this
    # event carries into the graph. None = observed traffic, ordinary rank.
    internal_kind: str | None = None
    #: The full participant set — who else was on this. Without it L2 cannot tell a
    #: conversation from a broadcast, or an introducer from a counterparty.
    recipients: tuple[str, ...] = ()
    #: Who could see the original (source-stamped at the normalize seam, gate-enforced).
    #: None only for pre-visibility rows; a freshly gated event always carries one — the gate
    #: parks `visibility_unknown` rather than publishing without it.
    visibility: Visibility | None = None
    #: N-05 — an out-of-office / leave / auto-reply message, routed instead of dropped.
    #: `auto_reply` (a responder wrote it: never a real answer, never reply-needed state) or
    #: `leave_notice` (a human announcing an absence). L2 scores everything in it low except the
    #: availability window it carries. None for ordinary mail.
    availability_marker: str | None = None
    versions: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 2                  # v2: + internal_kind (additive only)
