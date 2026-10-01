"""Fail-closed Layer 3 errors with operator-readable causes."""


class DomainCompilerError(RuntimeError):
    pass


class UnsupportedCoverage(Exception):
    """Not an error — an honest "we do not cover this yet".

    Every other exception here means the compiler found something WRONG: a stale registry, a
    route with no required objects, a limit blown. An all-stub route means nothing is wrong —
    the corpus simply has not been authored for this situation yet, which for a product mid
    build-out is the common case, not a defect. Raising `AuthoringIntegrityError` for it made a
    live cutover indistinguishable from a crash: `domain_shadow.py`'s catch-all folded both into
    the same `counts["error"]`, so the route-coverage metric could never separate "broken" from
    "not built yet" — and the metric this exists to support (route disposition coverage) needs
    exactly that separation to mean anything.

    Deliberately NOT a `DomainCompilerError` subclass — inheriting from the error hierarchy
    would put it one bare `except DomainCompilerError` away from being silently swallowed again.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        # no_route: nothing in the catalog claims this situation at all.
        # all_stub: every capability that WOULD claim it is an unauthored stub.
        # unreviewed: authored but has not cleared review-state admission (see L3-03).
        # unsupported_domain: the situation's domain has no corpus folder (e.g. fundraising).
        if reason not in {"no_route", "all_stub", "unreviewed", "unsupported_domain"}:
            raise ValueError(f"unknown UnsupportedCoverage reason: {reason!r}")
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


class AuthoringIntegrityError(DomainCompilerError):
    pass


class NoExpertiseRoute(DomainCompilerError):
    """No capability claims this situation — and WHICH of the four reasons, said structurally.

    ⛔ WHAT WAS WRONG. This class was `pass`. It carried nothing, so the only way to tell its four
    quite different causes apart was to read the sentence it was constructed with, and
    `scripts/corpus_route_probe.py` did exactly that::

        text_ = str(exc)
        if "unknown domains" in text_:   key = "unknown_domain_hint"
        elif "no authored" in text_:     key = "no_route_predicate"
        else:                            key = "no_route_type"

    Three tests over four causes, with an `else` catch-all. Measured against the four real messages
    on 2026-09-30: `domain_not_activated` — *"this tenant has not switched this domain on"* — was
    reported as `no_route_type`, *"nobody authored a route for it"*. The raise site's own comment
    says those two *"are a different fact … and the operator fixes them in different places"*, and
    the tool that measures routing coverage merged them.

    ⛔ AND THE RIGHT PATTERN IS FOURTEEN LINES UP, IN THIS FILE. `UnsupportedCoverage` validates its
    reason against a closed set at construction, with a docstring explaining that folding distinct
    causes into one count meant the metric *"could never separate 'broken' from 'not built yet'."*
    The same argument applies here and had not been applied.

    ⛔ FOUR REASONS, FOUR DIFFERENT PEOPLE:

        unknown_domain_hint      the situation names a domain with no corpus folder at all.
                                 A ROUTING bug — whoever set the hint.
        domain_not_activated     the domain exists and this tenant has not switched it on.
                                 An OPERATIONS fact — platform/l3_activation. Often correct.
        predicate_rejected       a situation binds the type and its authored `when` refused this
                                 instance. The predicate's AUTHOR — and possibly nobody: a
                                 predicate that correctly declines is not a defect.
        no_situation_binds_type  no situation in any domain binds this L2 type. An AUTHORING gap;
                                 somebody must own the type. This is the bucket the five declared
                                 `unrouted_l2_types` live in.

    ⛔ `reason` IS REQUIRED. A default would let a new raise site mint an unlabelled refusal that
    reads as one of the four, and not guessing which is the entire point of the field.

    ⛔ `situation_type` RIDES ALONG. `domain_shadow` catches this inside a loop that still holds the
    row, so it could supply the type itself — and then two places would decide what the pair means.
    A raise that knows its own type and does not say so invites its caller to guess.
    """

    #: Closed, and ordered from "our bug" to "nobody's bug". A fifth cause is a fifth entry here,
    #: deliberately visible in a diff rather than absorbed by an `else`.
    REASONS: frozenset[str] = frozenset({
        "unknown_domain_hint",
        "domain_not_activated",
        "predicate_rejected",
        "no_situation_binds_type",
    })

    def __init__(self, message: str, *, reason: str, situation_type: str | None = None) -> None:
        if reason not in self.REASONS:
            raise ValueError(
                f"unknown NoExpertiseRoute reason: {reason!r}; the four are "
                f"{sorted(self.REASONS)}")
        self.reason = reason
        #: `None` only where the caller genuinely does not have it. A count keyed on `None` is
        #: still a count, and it is honest about which slice it could not dimension — which is
        #: what "a count without its dimension is not a measurement" asks for.
        self.situation_type = situation_type
        super().__init__(message)


class SituationContextIncomplete(DomainCompilerError):
    pass


class SituationContextConflict(DomainCompilerError):
    pass


class RequiredKnowledgeMissing(DomainCompilerError):
    pass


class BrainPolicyViolation(DomainCompilerError):
    pass


class ExpertisePublicationConflict(DomainCompilerError):
    pass


__all__ = [
    "AuthoringIntegrityError",
    "BrainPolicyViolation",
    "DomainCompilerError",
    "ExpertisePublicationConflict",
    "UnsupportedCoverage",
    "NoExpertiseRoute",
    "RequiredKnowledgeMissing",
    "SituationContextConflict",
    "SituationContextIncomplete",
]
