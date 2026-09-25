"""Which of the facts Layer 2 publishes are actually ASKED FOR by an authored capability.

⛔ THE ENGINE IS NOT THE CONSTRAINT. Every step of this plan has been written on the premise that
the output is thin because the engine is under-built. Measured on 2026-09-25 against the corpus:

    substrate fact paths the vocabulary declares to authors   141
    named by at least one of the 1,425 authored capabilities   71
    named by NONE of them                                      70

Half of what Layer 2 computes and writes into the graph on every sweep is never asked for by
anything downstream. That is not a bug in `genios_engine` — nothing here is broken, and no wiring
change closes it. The gap is in the AUTHORED CORPUS, and its owner is whoever writes capabilities.

THE SHARPEST CASE, and the reason this file exists rather than a note in a plan document.
`context/correlation_history.py` computes four facts every sweep, one of which is
`derived.history.prior_card_verdict` — *"we already told them this and they marked it wrong."* Its
own docstring calls that "the single most useful thing this file can say". It is declared in
`substrate.fact_paths`, in the same list as `derived.momentum`, `derived.engagement` and
`derived.sentiment`, which authors use 83, 191 and 154 times between them.

    derived.history.*  is used ZERO times, in 1,425 files.

⛔ THIS REPORTS, IT DOES NOT REFUSE. A field may legitimately be declared ahead of the capability
that will use it — that is how a substrate is grown, and a gate here would make publishing a new
fact impossible until an author had already consumed it, which is backwards. What the pin in
`tests/test_the_corpus_asks_for_what_the_engine_publishes.py` protects is the DIRECTION: the
unconsumed count may fall, and may not silently rise.

⛔ AND THE LEAF CHECK IS DELIBERATELY WEAK EVIDENCE, NOT A SECOND ANSWER. 13 of the 70 have a leaf
name (`created_at`, `replied`) that appears somewhere in the corpus. A leaf match is exactly the
blunt-grep family this project has caught nine times — `document.created_at` and some unrelated
`created_at` are not the same field — so they are reported SEPARATELY as ambiguous and never
counted as consumed. The conservative number is 57; the exact-path number is 70; both are real and
they answer slightly different questions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Demand:
    """What the corpus asks for, against what the vocabulary offers it."""

    declared: tuple[str, ...]
    consumed: tuple[str, ...]
    unconsumed: tuple[str, ...]
    #: Unconsumed by exact path, but whose LEAF name appears somewhere. Weak evidence, reported
    #: so that the headline number is never quietly inflated by a coincidence.
    ambiguous: tuple[str, ...]

    @property
    def strict_unconsumed(self) -> tuple[str, ...]:
        """The conservative reading — unconsumed and not even leaf-reachable."""
        return tuple(f for f in self.unconsumed if f not in set(self.ambiguous))


#: A leaf shorter than this is too common a word to be evidence of anything (`replied`, `intent`).
_MIN_LEAF = 9


def field_paths(vocabulary_yaml: str) -> tuple[str, ...]:
    """The `substrate.fact_paths` list, in declaration order.

    Parsed by INDENTATION rather than with a YAML loader on purpose: the list is dense with
    explanatory comments that carry the reason each field exists, and this function is used by a
    test whose whole job is to be readable beside them. It stops at the next key at the same depth,
    so a field added under a later section is not silently absorbed into this one.
    """
    if "  fact_paths:" not in vocabulary_yaml:
        return ()
    out: list[str] = []
    for line in vocabulary_yaml.split("  fact_paths:", 1)[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            field = stripped[2:].split("#")[0].strip()
            if field:
                out.append(field)
        elif (stripped and not stripped.startswith("#") and stripped.endswith(":")
              and len(line) - len(line.lstrip()) <= 2):
            break
    return tuple(out)


def measure(declared: tuple[str, ...], corpus_text: str) -> Demand:
    """Split `declared` by whether the corpus names each field.

    `corpus_text` is every authored capability concatenated. A field is CONSUMED only when its
    full declared path appears — `derived.history.times_seen`, not `times_seen` — because the
    path is what the compiler resolves and a leaf is just a word.
    """
    consumed, unconsumed, ambiguous = [], [], []
    for field in declared:
        if field in corpus_text:
            consumed.append(field)
            continue
        unconsumed.append(field)
        leaf = field.rsplit(".", 1)[-1]
        if len(leaf) >= _MIN_LEAF and leaf in corpus_text:
            ambiguous.append(field)
    return Demand(tuple(declared), tuple(consumed), tuple(unconsumed), tuple(ambiguous))


def families(fields: tuple[str, ...]) -> dict[str, int]:
    """`{family: count}` — the second dotted segment, which is how the vocabulary groups them."""
    out: dict[str, int] = {}
    for field in fields:
        parts = field.split(".")
        key = parts[1] if len(parts) > 1 else parts[0]
        out[key] = out.get(key, 0) + 1
    return out


#: ⛔ The four the engine works hardest for and nobody reads. Named so that the day a capability
#: asks for one, the pinning test fails and whoever did it is told to come back and rewrite the
#: docstring above — which is the only way a measured claim stops being true on schedule.
HISTORY_FIELDS: tuple[str, ...] = (
    "derived.history.times_seen",
    "derived.history.days_since_prior",
    "derived.history.prior_outcome",
    "derived.history.prior_card_verdict",
)

__all__ = ["Demand", "HISTORY_FIELDS", "families", "field_paths", "measure"]
