"""A number the expert may read, with what it rests on (STEP-10, `06` D37).

Every number a file shows — a reply time, a gap, a rate — is a `Measured`: its value, how many
observations it rests on (`n`), the level it was measured at (`basis` — the person, their firm, the
tenant, the file), and where it came from (`source`: `measured_here`, computed from this tenant's own
history, or `playbook_prior`, an authored prior — STEP-11). A number is called NORMAL only at
`NORMAL_AT` observations or more; below that it is `sparse`, and it is shown as what it is — *"once,
1.9 days"* — never as a habit. Pure and frozen: no I/O, no clock.

WHY ONE CONTRACT. On the golden set the only reply times that existed rested on ONE reply counted
twice, and nothing beside them said so (`STEP-10` §8.1). A number that travels without its n reads as a
measurement whatever it rests on; this type makes the n travel with it, so every reader — the read
model, the route, the health check, the expert's dossier — can refuse to call a sparse number normal.

THREE KINDS OF NUMBER, and each says itself differently (`stat`, `M29.C1.L-contract.V0.U05`). Frozen
first as medians only, the contract worded a connector's rate as *"usually 0.625 ratio (n=8,
connector)"* and its count of introductions as *"3 times, median 3 count"* — found by the worker that
built the rate. A MEDIAN is a habit only at `NORMAL_AT`; a RATE is *"5 of 8"*, exact, and never a habit
(`k` carries the 5, so the words never round); a COUNT is what it counts — *"8"*, *"none"* — exact,
never sparse and never normal, and zero is a count, not "not measured".
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

#: The observations a number needs before it may be called normal (`06` D37).
NORMAL_AT = 5

MEASURED_HERE = "measured_here"
PLAYBOOK_PRIOR = "playbook_prior"
SOURCES: tuple[str, ...] = (MEASURED_HERE, PLAYBOOK_PRIOR)

MEDIAN, RATE, COUNT = "median", "rate", "count"
STATS: tuple[str, ...] = (MEDIAN, RATE, COUNT)


@dataclass(frozen=True, slots=True)
class Measured:
    """One number, what it rests on, and where it came from."""
    value: float | None
    n: int
    basis: str
    source: str = MEASURED_HERE
    unit: str = ""
    stat: str = MEDIAN
    k: int | None = None               # a rate's hits — "k of n" — kept so its words never round

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}, not {self.source!r}")
        if self.stat not in STATS:
            raise ValueError(f"stat must be one of {STATS}, not {self.stat!r}")
        if self.n < 0:
            raise ValueError("n cannot be negative")
        if not str(self.basis or "").strip():
            raise ValueError("a measured number names its basis")
        if self.stat == COUNT:
            if self.value is None or self.value != self.n:
                raise ValueError("a count is what it counts: its value is its n, zero included")
        elif self.source == MEASURED_HERE and (self.n == 0) != (self.value is None):
            raise ValueError("a number measured here has a value exactly when n > 0")
        if self.stat == RATE and self.value is not None and (
                self.k is None or not 0 <= self.k <= self.n):
            raise ValueError("a rate says how many of its n: 0 <= k <= n")

    @property
    def sparse(self) -> bool:
        """Too few observations to call it normal. A count is exact, never sparse."""
        return self.stat != COUNT and self.n < NORMAL_AT

    @property
    def normal(self) -> bool:
        """It may be read as a habit: a median or a rate measured here, with a value, on enough
        observations. A count is never a habit."""
        return (self.stat != COUNT and self.source == MEASURED_HERE and self.value is not None
                and not self.sparse)

    def says(self) -> str:
        """The words a reader may show — never "usually" below `NORMAL_AT`."""
        unit = f" {self.unit}" if self.unit else ""
        if self.value is None:
            return "not measured"
        v = f"{self.value:g}"
        if self.source == PLAYBOOK_PRIOR:
            return f"{v}{unit} — a playbook's prior, not measured here"
        if self.stat == COUNT:
            return f"{self.n}{unit}" if self.n else "none"
        if self.stat == RATE:
            return f"{self.k} of {self.n}"
        if self.n == 1:
            return f"once: {v}{unit}"
        if self.sparse:
            return f"{self.n} times, median {v}{unit} — too few to call normal"
        return f"usually {v}{unit} (n={self.n}, {self.basis})"

    def as_dict(self) -> dict:
        return {"value": self.value, "n": self.n, "basis": self.basis, "source": self.source,
                "unit": self.unit, "stat": self.stat, "k": self.k, "sparse": self.sparse,
                "says": self.says()}


def median_of(values: Iterable[float], *, basis: str, unit: str = "days",
              ndigits: int = 2) -> Measured:
    """The median of what was observed, with how many there were. No values: not measured."""
    observed = [float(v) for v in values]
    return Measured(value=round(median(observed), ndigits) if observed else None,
                    n=len(observed), basis=basis, unit=unit)


def rate_of(hits: int, total: int, *, basis: str, ndigits: int = 3) -> Measured:
    """`hits` of `total`, as a ratio resting on `total` observations. None of any: not measured."""
    if hits < 0 or total < 0 or hits > total:
        raise ValueError(f"a rate needs 0 <= hits <= total, not {hits} of {total}")
    return Measured(value=round(hits / total, ndigits) if total else None, n=total, basis=basis,
                    unit="ratio", stat=RATE, k=hits if total else None)


def count_of(k: int, *, basis: str, unit: str = "") -> Measured:
    """How many there are — exact, zero included (`"none"`), never sparse and never a habit. A
    negative count is refused by `Measured` itself (n cannot be negative)."""
    return Measured(value=k, n=k, basis=basis, unit=unit, stat=COUNT)


__all__ = ["COUNT", "MEASURED_HERE", "MEDIAN", "Measured", "NORMAL_AT", "PLAYBOOK_PRIOR", "RATE",
           "SOURCES", "STATS", "count_of", "median_of", "rate_of"]
