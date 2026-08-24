"""Small dependency-free protocol for independently testable reasoning modules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from genios_engine.contracts.reasoning import ReasonerResult, ReasonerSpec, ReasoningRequest


@runtime_checkable
class Reasoner(Protocol):
    """A pure reasoner.

    Implementations receive all semantic input explicitly. They must not read a database, network,
    system clock, random generator, environment variable, global mutable state, or language model.
    """

    @property
    def spec(self) -> ReasonerSpec:
        ...

    def evaluate(self, request: ReasoningRequest,
                 prior_results: Mapping[str, ReasonerResult]) -> ReasonerResult:
        ...


class ReasonerError(RuntimeError):
    """Typed failure raised by a reasoner for invalid deterministic input."""


class MissingContextError(ReasonerError):
    def __init__(self, *fields: str) -> None:
        self.fields = tuple(sorted(set(fields)))
        super().__init__("missing required context: " + ", ".join(self.fields))


class OrchestrationError(RuntimeError):
    """The declared capability cannot be executed safely.

    Raised for deployment faults — a malformed manifest, an unschedulable plan — never for a
    reasoner's own failure, which becomes a typed FAILED result inside the trace instead.
    """
