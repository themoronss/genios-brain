"""The NEGATIVE-INFERENCE LICENCE, as the layers above it see it.

Typing an absence is only half the job. The other half is that the places which today read a
missing fact as a false, a zero or an absent signal have to ASK — and until they do, `UNKNOWABLE`
is a well-typed value nobody consults, which is indistinguishable from not having built it.

There are exactly two shapes of negative inference in this codebase, and both live in
`packs/compiler/context_adapter.evaluate`:

    {absent: <fact path>}   "there is no amendment", "they never replied"
    {no_obs: <obs kind>}    "no reply was received", "no contract was requested"

Both answer TRUE today whenever the thing is not in the slice — with no reference of any kind to
whether a source that could have carried it was connected. An org with no mailbox connected
therefore satisfies `absent: thread.last_inbound` on every situation it has, and the authored
rules that read it (`first-touch-unanswered`, `unworked-accounts-are-nobodys-win`,
`personalisation-is-evidence-not-a-merge-field`) fire on a blind spot.

This module is the seam between the two sides. It names the metadata keys ONCE, so the producer
(`context.situation_bso.build_context_slice`, filling them from `situation_absences`) and the
consumer (`ContextAdapter`) cannot disagree by typo, and it states the default: **absent keys mean
unchanged behaviour**. A slice built before this landed, or by a caller that has no absence data,
evaluates exactly as it did — the licence is withdrawn only where an absence was actually typed
`UNKNOWABLE`, never on a guess about a slice we know nothing about.

PURE. No database, no clock, no contract import: `ContextAdapter` is the one compiler component
allowed to look inside a context slice, and it must not acquire a dependency on Layer 2's storage
in order to ask a question about a set of strings.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

#: Fact paths whose absence is `UNKNOWABLE` — no connected source could have carried them.
#: A predicate over one of these is UNKNOWN, never TRUE and never FALSE.
UNKNOWABLE_FIELDS_KEY = "unknowable_fields"

#: Fact paths whose absence is `GENUINELY_ABSENT` under a coverage epoch that still stands.
#: These are the ONLY paths on which "there is no owner" may be asserted.
ABSENT_FIELDS_KEY = "genuinely_absent_fields"

#: One bit: may an OBSERVATION absence be read as a finding at all? Observation kinds have no
#: field path to type individually — `no_obs: pass_received` names a thing that never happened,
#: not a field that is empty — so the licence for them is the situation's domain coverage, which
#: is exactly what `capture.coverage.model._READINESS` computes as `can_evaluate_no_reply` and
#: friends and which nothing has ever read.
OBSERVATION_LICENCE_KEY = "observation_absence_licensed"


def absence_metadata(*, unknowable: Iterable[str] = (), absent: Iterable[str] = (),
                     observation_licensed: bool | None = None) -> dict[str, Any]:
    """The producer side: the three keys, or nothing.

    A key is omitted rather than written empty when there is nothing to say, because an empty
    `unknowable_fields` and a missing one mean the same thing to the consumer and writing the
    empty one would put a growing pile of `[]` into every content-addressed slice — and a slice's
    metadata is hashed into the expertise package's address.

    `observation_licensed=None` likewise omits the bit: "we did not assess the domain" must not
    arrive as "observation absences are not licensed", which would silently stop every `no_obs`
    rule for a tenant whose coverage row simply has not been filed yet.
    """
    out: dict[str, Any] = {}
    unknowable = tuple(sorted(set(unknowable)))
    absent = tuple(sorted(set(absent)))
    if unknowable:
        out[UNKNOWABLE_FIELDS_KEY] = list(unknowable)
    if absent:
        out[ABSENT_FIELDS_KEY] = list(absent)
    if observation_licensed is not None:
        out[OBSERVATION_LICENCE_KEY] = bool(observation_licensed)
    return out


def read_string_set(*sources: Mapping[str, Any] | None, key: str) -> frozenset[str]:
    """The consumer side: one key, unioned across the slice and the situation metadata.

    Union rather than "whichever is present", because `ContextAdapter` already combines
    `missing_fields` from both places and a field typed on one and not the other must keep the
    SAFER answer. For a set that WITHDRAWS a licence, the union is the safer answer.
    """
    out: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for value in source.get(key) or ():
            out.add(str(value))
    return frozenset(out)


def read_licence(*sources: Mapping[str, Any] | None, key: str) -> bool:
    """One boolean, and it is an AND across the sources.

    Any source that says the licence is withdrawn withdraws it. An absent key is not a vote —
    unchanged behaviour is the default, per this module's opening — so a slice that says nothing
    leaves whatever the other one said, and two silent sources leave the licence intact.
    """
    for source in sources:
        if isinstance(source, Mapping) and source.get(key) is False:
            return False
    return True


def may_infer_absent(path: str, *, unknowable: frozenset[str]) -> bool:
    """May a layer say "there is no <path>"? False when the absence is `UNKNOWABLE`.

    One function rather than an `in` at each of the call sites, so "which absences license an
    inference" has one answer a reader can see — the same reason `NEGATIVE_INFERENCE_TYPES` is
    data in the contract rather than an `if`.
    """
    return path not in unknowable


__all__ = ["ABSENT_FIELDS_KEY", "OBSERVATION_LICENCE_KEY", "UNKNOWABLE_FIELDS_KEY",
           "absence_metadata", "may_infer_absent", "read_licence", "read_string_set"]
