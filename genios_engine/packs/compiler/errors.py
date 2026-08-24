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
    pass


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
