"""Fail-closed Layer 3 errors with operator-readable causes."""


class DomainCompilerError(RuntimeError):
    pass


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
    "NoExpertiseRoute",
    "RequiredKnowledgeMissing",
    "SituationContextConflict",
    "SituationContextIncomplete",
]
