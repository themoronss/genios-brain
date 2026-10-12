"""What the GeniOS Engine hands the expert for ONE file — its Domain and Reasoning Expertise, line by line (STEP-13b).

`speedrun008/YC-II W27/` STEP-13b §8.4 item 1, tree `yc2_w27_s13b` M37.C1.L-contract.V0.U01. Rohit, 12 Oct
(`06` D64): the expert reasons from three sources at once — the file's DATA, the GeniOS ENGINE and its OWN
expertise — each labelled, so the check verifies what is checkable and the founder sees where every line
came from. The dossier already prints the data with ids; this is the shape of the second source:

  * an `EngineLine` — one thing the engine knows that bears on the file: its id (printed in brackets, so
    the expert can cite it and the check can hold it), its FAMILY, its words, its SOURCE (the corpus
    artifact and its content hash, the learned entry and its version, or the unit and its version), and
    whether a named human REVIEWED it;
  * an `EngineRead` — the lines in the order they are shown, what each family's limit CUT (counted, never
    silent), the corpus situations that MAY apply and are not shown (a predicate the anchor's facts could
    not answer — never shown unchecked), the file's situations it could NOT read and why, and its VERSION:
    `eng-` and the hash of everything it shows.

THE FAMILIES ARE CLOSED, AND EACH OWNS ONE ID PREFIX, so a citation names its family by its first word and
the check can tell an engine id from an evidence id without a lookup:

  family          prefix   what it is                                                     origin
  capability      cap:     a capability's question (`#q`) and failure modes (`#f<n>`)     authored
  signals         sig:     a corpus situation's signals of progress and decay             authored
  playbook        pb:      playbooks and heuristics — as the dossier already prints        authored
                           the kind's
  rule            rule:    an authored rule's statement                                   authored
  constraint      cons:    that rule's compiled constraint and its predicate's verdict    authored
                           (holds · fails · unknown)
  frame           frame:   a mental model or decision framework                           authored
  organization    org:     the Organization brain — what the tenant's rules say           learned
  behaviour       pat:     the Behaviour brain — a pattern measured on its people         learned
  adaptive        pref:    the Adaptive brain — a preference learned from the founder     learned
  unit            ru:      a reasoning unit's reading of the file, in levels              measured

READ, NEVER GATED (`06` D3, D-s13b-6). Admission gates what may carry authority on a CARD, not what the
expert may READ: an authored line no named human reviewed is shown, and says so — `label` is D6's words,
"not yet reviewed". A learned line is the company's own history and a measured one is code's reading;
neither is a corpus draft, so neither carries the label, and a measurement is never "reviewed".

Pure and frozen: no I/O, no clock, no model. `as_mapping` is what is kept; `from_mapping` reads it back as
written — and refuses a stored read whose content no longer hashes to the version it was kept under.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from genios_engine.platform.canonical import semantic_hash

# ── the families — one name to a line (`tests/test_no_missing_module_deps` reads names by assignment) ─
CAPABILITY = "capability"
SIGNALS = "signals"
PLAYBOOK = "playbook"
RULE = "rule"
CONSTRAINT = "constraint"
FRAME = "frame"
ORGANIZATION = "organization"
BEHAVIOUR = "behaviour"
ADAPTIVE = "adaptive"
UNIT = "unit"
#: In the order a dossier shows them: the Domain Expertise authored, then learned, then the units.
FAMILIES: tuple[str, ...] = (CAPABILITY, SIGNALS, PLAYBOOK, RULE, CONSTRAINT, FRAME, ORGANIZATION,
                             BEHAVIOUR, ADAPTIVE, UNIT)
#: Each family's one id prefix.
PREFIX: Mapping[str, str] = MappingProxyType({
    CAPABILITY: "cap:", SIGNALS: "sig:", PLAYBOOK: "pb:", RULE: "rule:", CONSTRAINT: "cons:",
    FRAME: "frame:", ORGANIZATION: "org:", BEHAVIOUR: "pat:", ADAPTIVE: "pref:", UNIT: "ru:"})

# ── where a line comes from ────────────────────────────────────────────────────────────────────
AUTHORED = "authored"          # the corpus — a human (or a drafting model, unreviewed) wrote it
LEARNED = "learned"            # the tenant's brains — Layer 6 published it from the company's history
MEASURED = "measured"          # a reasoning unit read it off the file's facts, now
ORIGINS: tuple[str, ...] = (AUTHORED, LEARNED, MEASURED)
ORIGIN_OF: Mapping[str, str] = MappingProxyType({
    CAPABILITY: AUTHORED, SIGNALS: AUTHORED, PLAYBOOK: AUTHORED, RULE: AUTHORED, CONSTRAINT: AUTHORED,
    FRAME: AUTHORED, ORGANIZATION: LEARNED, BEHAVIOUR: LEARNED, ADAPTIVE: LEARNED, UNIT: MEASURED})

#: `06` D3's words, extended by D-s13b-6 to every corpus line a named human has not reviewed.
NOT_REVIEWED = "not yet reviewed"

# ── a constraint's verdict: its rule's predicate, read over the file's anchor ─────────────────────
HOLDS = "holds"                # the rule's condition is met on this file
FAILS = "fails"                # it is not
UNKNOWN = "unknown"            # the anchor's facts cannot say — never read as either
VERDICTS: tuple[str, ...] = (HOLDS, FAILS, UNKNOWN)

# ── why one of the file's situations was not read ──────────────────────────────────────────────
SWITCHED_OFF = "switched_off"      # routed only to corpora the tenant has not switched on
NO_ROUTE = "no_route"              # no authored registry routes its type
UNKNOWN_DOMAIN = "unknown_domain"  # its domain names no authored corpus
NOT_READ_REASONS: tuple[str, ...] = (SWITCHED_OFF, NO_ROUTE, UNKNOWN_DOMAIN)

#: A capability line names its question or one of its failure modes, counted from one.
_CAPABILITY_REF = re.compile(r"^cap:[^\s\[\]#]+#(?:q|f[1-9]\d*)$")
#: Anything printed in brackets: no space, no bracket.
_PRINTABLE = re.compile(r"^[^\s\[\]]+$")


def family_of(ref: str | None) -> str | None:
    """The family a ref belongs to by its prefix, or None for a ref that is no engine line's."""
    text = str(ref or "")
    return next((f for f in FAMILIES if text.startswith(PREFIX[f])), None)


def _text(value: Any, name: str) -> str:
    folded = " ".join(str(value if value is not None else "").split())
    if not folded:
        raise ValueError(f"{name} is required")
    return folded


def _ref(ref: Any, family: str) -> str:
    text = str(ref or "")
    prefix = PREFIX[family]
    if family_of(text) != family or len(text) == len(prefix) or not _PRINTABLE.match(text):
        raise ValueError(f"a {family} line's id is `{prefix}<id>` with no space or bracket, not {ref!r}")
    if family == CAPABILITY and not _CAPABILITY_REF.match(text):
        raise ValueError(f"a capability line names its question (#q) or a failure mode (#f<n>), not {ref!r}")
    return text


def _cites(values: Any) -> tuple[str, ...]:
    out: list[str] = []
    for value in values or ():
        text = str(value or "")
        if not _PRINTABLE.match(text):
            raise ValueError(f"a cited id is printed in brackets: no space, no bracket — not {value!r}")
        if text not in out:
            out.append(text)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class EngineLine:
    """One thing the engine knows that bears on the file — its id, family, words and source."""
    ref: str                           # the id, printed in brackets: `cap:<capability>#f2`, `ru:core.risk`
    family: str                        # one of FAMILIES
    words: str                         # what it says, on one line
    source: str                        # the corpus artifact, the learned entry or the unit it is read from
    source_version: str                # that source's content hash, or its version
    reviewed: bool                     # a named human reviewed it (authored and learned lines only)
    cites: tuple[str, ...] = ()        # the data ids it rests on — a unit's findings' source events
    verdict: str | None = None         # a constraint's: holds · fails · unknown; None on every other line

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"a family is one of {FAMILIES}, not {self.family!r}")
        object.__setattr__(self, "ref", _ref(self.ref, self.family))
        object.__setattr__(self, "words", _text(self.words, "an engine line's words"))
        object.__setattr__(self, "source", _text(self.source, "an engine line's source"))
        object.__setattr__(self, "source_version", _text(self.source_version,
                                                         "an engine line's source version"))
        if not isinstance(self.reviewed, bool):
            raise ValueError("reviewed is True or False")
        if self.reviewed and ORIGIN_OF[self.family] == MEASURED:
            raise ValueError("a measurement is code's reading of the file — nobody reviews it")
        object.__setattr__(self, "cites", _cites(self.cites))
        if self.family == CONSTRAINT:
            if self.verdict not in VERDICTS:
                raise ValueError(f"a constraint says its verdict, one of {VERDICTS}, not {self.verdict!r}")
        elif self.verdict is not None:
            raise ValueError("only a constraint line carries a verdict")

    @property
    def origin(self) -> str:
        return ORIGIN_OF[self.family]

    @property
    def label(self) -> str | None:
        """D6's words on an authored line no named human reviewed; None otherwise."""
        return NOT_REVIEWED if self.origin == AUTHORED and not self.reviewed else None

    def as_mapping(self) -> dict[str, Any]:
        return {"ref": self.ref, "family": self.family, "origin": self.origin, "words": self.words,
                "source": self.source, "source_version": self.source_version,
                "reviewed": self.reviewed, "cites": list(self.cites), "verdict": self.verdict}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "EngineLine":
        return cls(ref=raw.get("ref"), family=raw.get("family"), words=raw.get("words"),
                   source=raw.get("source"), source_version=raw.get("source_version"),
                   reviewed=raw.get("reviewed"), cites=tuple(raw.get("cites") or ()),
                   verdict=raw.get("verdict"))


@dataclass(frozen=True, slots=True)
class MayApply:
    """A corpus situation the file's situation routes to whose predicate the anchor's facts could not
    answer: named, never shown — an unchecked line is no line."""
    situation: str                     # the corpus situation
    capability: str | None             # its owner capability
    missing: tuple[str, ...] = ()      # what the predicate needed and the facts did not hold

    def __post_init__(self) -> None:
        object.__setattr__(self, "situation", _text(self.situation, "a corpus situation"))
        if self.capability is not None:
            object.__setattr__(self, "capability", _text(self.capability, "a capability"))
        object.__setattr__(self, "missing", tuple(str(m) for m in self.missing or ()))

    def as_mapping(self) -> dict[str, Any]:
        return {"situation": self.situation, "capability": self.capability,
                "missing": list(self.missing)}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "MayApply":
        return cls(situation=raw.get("situation"), capability=raw.get("capability"),
                   missing=tuple(raw.get("missing") or ()))


@dataclass(frozen=True, slots=True)
class NotRead:
    """One of the file's situations the engine read nothing for, and why."""
    situation_type: str
    domain: str
    reason: str                        # one of NOT_READ_REASONS
    corpora: tuple[str, ...] = ()      # the corpora it routes to, when they are switched off

    def __post_init__(self) -> None:
        object.__setattr__(self, "situation_type", _text(self.situation_type, "a situation type"))
        object.__setattr__(self, "domain", _text(self.domain, "a domain"))
        if self.reason not in NOT_READ_REASONS:
            raise ValueError(f"a reason is one of {NOT_READ_REASONS}, not {self.reason!r}")
        object.__setattr__(self, "corpora", tuple(str(c) for c in self.corpora or ()))

    def as_mapping(self) -> dict[str, Any]:
        return {"situation_type": self.situation_type, "domain": self.domain, "reason": self.reason,
                "corpora": list(self.corpora)}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "NotRead":
        return cls(situation_type=raw.get("situation_type"), domain=raw.get("domain"),
                   reason=raw.get("reason"), corpora=tuple(raw.get("corpora") or ()))


def _cut(raw: Mapping[str, Any] | None) -> Mapping[str, int]:
    counted = dict.fromkeys(FAMILIES, 0)
    for family, n in (raw or {}).items():
        if family not in FAMILIES:
            raise ValueError(f"a cut is counted per family, one of {FAMILIES}, not {family!r}")
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError(f"a cut is a count, not {n!r}")
        counted[family] = n
    return MappingProxyType(counted)


@dataclass(frozen=True, slots=True)
class EngineRead:
    """Everything the engine shows for one file, in the order shown, with what was left out."""
    lines: tuple[EngineLine, ...] = ()
    cut: Mapping[str, int] = field(default_factory=dict)
    may_apply: tuple[MayApply, ...] = ()
    not_read: tuple[NotRead, ...] = ()

    def __post_init__(self) -> None:
        lines = tuple(self.lines or ())
        refs = [line.ref for line in lines]
        twice = sorted({r for r in refs if refs.count(r) > 1})
        if twice:
            raise ValueError(f"one ref is one line, and these are several: {twice}")
        object.__setattr__(self, "lines", lines)
        object.__setattr__(self, "cut", _cut(self.cut))
        object.__setattr__(self, "may_apply", tuple(self.may_apply or ()))
        object.__setattr__(self, "not_read", tuple(self.not_read or ()))

    @property
    def refs(self) -> tuple[str, ...]:
        return tuple(line.ref for line in self.lines)

    @property
    def by_ref(self) -> Mapping[str, EngineLine]:
        return MappingProxyType({line.ref: line for line in self.lines})

    def of_family(self, family: str) -> tuple[EngineLine, ...]:
        return tuple(line for line in self.lines if line.family == family)

    @property
    def cut_total(self) -> int:
        return sum(self.cut.values())

    @property
    def empty(self) -> bool:
        return not self.lines

    def _content(self) -> dict[str, Any]:
        return {"lines": [line.as_mapping() for line in self.lines], "cut": dict(self.cut),
                "may_apply": [m.as_mapping() for m in self.may_apply],
                "not_read": [n.as_mapping() for n in self.not_read]}

    @property
    def version(self) -> str:
        """What a review was made against: `eng-` and twelve hex of the hash of everything shown."""
        return "eng-" + semantic_hash(self._content())[:12]

    def as_mapping(self) -> dict[str, Any]:
        return {**self._content(), "version": self.version}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "EngineRead":
        read = cls(lines=tuple(EngineLine.from_mapping(r) for r in raw.get("lines") or ()),
                   cut=dict(raw.get("cut") or {}),
                   may_apply=tuple(MayApply.from_mapping(r) for r in raw.get("may_apply") or ()),
                   not_read=tuple(NotRead.from_mapping(r) for r in raw.get("not_read") or ()))
        kept = raw.get("version")
        if kept is not None and kept != read.version:
            raise ValueError(f"a read kept as {kept} now hashes to {read.version}: its content moved")
        return read


__all__ = ["ADAPTIVE", "AUTHORED", "BEHAVIOUR", "CAPABILITY", "CONSTRAINT", "EngineLine", "EngineRead",
           "FAILS", "FAMILIES", "FRAME", "HOLDS", "LEARNED", "MEASURED", "MayApply", "NOT_READ_REASONS",
           "NOT_REVIEWED", "NO_ROUTE", "NotRead", "ORGANIZATION", "ORIGINS", "ORIGIN_OF", "PLAYBOOK",
           "PREFIX", "RULE", "SIGNALS", "SWITCHED_OFF", "UNIT", "UNKNOWN", "UNKNOWN_DOMAIN", "VERDICTS",
           "family_of"]
