"""Selective reflection trigger.

Per MD g-i-2 §2.3.2:
    stakes = irreversibility x blast_radius            # domain-scored, 0..1
    reflect_if:  stakes * (1 - confidence) > theta_reflect

Reflection is COST-bounded — running on every output ~doubles cost for modest gain.
Triggers ONLY when stakes-weighted uncertainty crosses the threshold.

Per MD: prefer FLAG-to-human over silent auto-fix. So this module decides WHEN
to reflect, but the engine's policy is "if reflection still uncertain → flag",
not "auto-correct based on reflection."
"""

from __future__ import annotations

from dataclasses import dataclass

# Default — tunable per module via config later
DEFAULT_THETA_REFLECT = 0.5


@dataclass(frozen=True)
class ReflectionTrigger:
    """Captures the inputs to a reflect/don't-reflect decision (for audit + tests)."""

    confidence: float
    irreversibility: float  # 0=fully reversible, 1=cannot undo
    blast_radius: float  # 0=affects nobody, 1=affects everyone in org
    theta_reflect: float

    @property
    def stakes(self) -> float:
        return self.irreversibility * self.blast_radius

    @property
    def score(self) -> float:
        return self.stakes * (1.0 - self.confidence)

    @property
    def fires(self) -> bool:
        return self.score > self.theta_reflect


def should_reflect(
    *,
    confidence: float,
    irreversibility: float,
    blast_radius: float,
    theta_reflect: float = DEFAULT_THETA_REFLECT,
) -> ReflectionTrigger:
    """Decide whether to run a reflection pass on this output.

    All scores in [0, 1]. Returns a ReflectionTrigger so callers can log the
    inputs even when reflection doesn't fire.
    """
    for name, v in (
        ("confidence", confidence),
        ("irreversibility", irreversibility),
        ("blast_radius", blast_radius),
        ("theta_reflect", theta_reflect),
    ):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]; got {v}")

    return ReflectionTrigger(
        confidence=confidence,
        irreversibility=irreversibility,
        blast_radius=blast_radius,
        theta_reflect=theta_reflect,
    )
