"""⛔ U03 · Atlas L1-01 — *"only eight canonical source IDs are buildable… catalogued is not
connected."*

The counting is still true, and the registry is **honest** about it: `BUILDABLE_SOURCES` is a
derived view over one descriptor per source, `tests/test_source_registry.py` enforces the
invariants that let four hand-maintained lists drift, and `L1.1-U2` exists so the connect screen
renders one answer. So this is not a gap — it is a stated product position.

⛔ Measuring it properly turned up two things the registry did not say.

1. **`database` and `mysql` are `buildable` with `capability = None` and `object_types = 0`.** A
   tenant can connect one, see a success, and contribute to no pack's coverage while mapping no
   objects. That is the INVERSE of every drift the module was built to close — its docstring lists
   sources that *"carried a coverage capability but NO family"*, and nobody asked the other way.
   **Receipt 48.**
2. ⛔ **The registry's own example had expired.** It said *"`hubspot` advertises the `crm`
   capability that the `sales` pack REQUIRES, while no connector can be built for it"* — and
   `hubspot` is buildable now. The shape of the claim survived; its subject did not.

⛔ AND THE SCORECARD'S NUMBER WAS WRONG. It folded `database/mysql/postgres` together as aliases
and reported *"~7 distinct providers"*. The descriptor carries a declared `aliases` field, and
folding by **it** gives **9**: `gcal` and `gdrive` really do absorb two spellings each, and
`database`, `mysql` and `postgres` are three separate descriptors with three different
capabilities. *The fold was done by reading the names rather than the field that declares it.*

⛔ THE ELEVEN ARE COUNTED HERE, NOT LISTED. Naming one is exactly how the docstring's sentence went
stale, so the guard holds a count and the registry holds no example.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from genios_engine.capture import source_registry as SR
from genios_engine.platform import receipt_coverage as C
from genios_engine.platform import receipts as R

CLAIM = "no live connection feeds a source that satisfies no capability"


def _receipt(org=None):
    found = [r for r in R.receipts(org) if r.claim == CLAIM]
    assert len(found) == 1, f"expected one receipt claiming {CLAIM!r}, got {len(found)}"
    return found[0]


def _canonical_buildable() -> set[str]:
    return {SR.descriptor_of(s).source for s in SR.BUILDABLE_SOURCES}


def _capability_less() -> list[str]:
    return sorted(s for s in _canonical_buildable() if SR.descriptor_of(s).capability is None)


# --------------------------------------------------------------------------------- receipt 48

def test_the_receipt_exists_and_can_go_red():
    receipt = _receipt()
    assert receipt.layer == "L1"
    assert receipt.expect(0) is True
    assert receipt.expect(1) is False


def test_it_counts_LIVE_connections_and_not_every_row():
    """⛔ A revoked or expired connection feeds nothing by design; counting it would make the
    receipt red for a tenant who correctly disconnected."""
    sql = _receipt().sql
    assert "status = 'connected'" in sql
    assert "connections" in sql


def test_the_source_list_is_derived_from_the_registry_and_not_written_down():
    """⛔ A source that gains a capability must leave this query with no edit."""
    sql = _receipt().sql
    for name in _capability_less():
        assert f"'{name}'" in sql, f"{name} has no capability and is not in the query"
    for name in _canonical_buildable() - set(_capability_less()):
        assert f"'{name}'" not in sql, (
            f"{name} advertises a capability and should not be counted as feeding nothing")


def test_the_two_known_members_are_what_the_registry_actually_says():
    """⛔ Asserted through the registry, not as a literal pair: if `mysql` gains a capability this
    test tells you the finding shrank rather than failing on a hardcoded list."""
    orphans = _capability_less()
    assert orphans, "no buildable source lacks a capability any more -- retire receipt 48"
    for name in orphans:
        d = SR.descriptor_of(name)
        assert d.capability is None and d.buildable, name
        assert len(d.object_types) == 0, (
            f"{name} now maps {len(d.object_types)} object type(s); it feeds the structured lane "
            "even without a capability, so the entry needs re-reading")


def test_it_is_org_scoped():
    assert "org_id = :org" in _receipt("org-1").sql
    assert "org_id = :org" not in _receipt(None).sql
    assert _receipt().fleet_wide is False


def test_the_builder_refuses_when_nothing_lacks_a_capability(monkeypatch):
    """⛔⛔ THE ALWAYS-GREEN FAILURE. An empty set renders `in ()`, which matches nothing and
    passes for ever."""
    real = SR.descriptor_of

    def always_capable(source):
        d = real(source)
        return d if d is None else dataclasses.replace(d, capability="crm")

    monkeypatch.setattr(SR, "descriptor_of", always_capable)
    with pytest.raises(AssertionError, match="pass for ever|retire the receipt"):
        R._CONNECTED_TO_NOTHING_SQL(None)


def test_the_builder_refuses_a_member_nobody_can_connect(monkeypatch):
    """⛔ A catalogued source with no capability that is NOT buildable is not this finding -- no
    tenant can connect it. Counting it would report a roadmap gap as a live defect."""
    real = SR.descriptor_of

    def unbuildable(source):
        d = real(source)
        if d is not None and d.capability is None:
            return dataclasses.replace(d, buildable=False)
        return d

    monkeypatch.setattr(SR, "descriptor_of", unbuildable)
    with pytest.raises(AssertionError, match="not buildable either"):
        R._CONNECTED_TO_NOTHING_SQL(None)


def test_the_receipt_declares_the_package_an_operator_would_read():
    package, why = C.RECEIPT_PACKAGE[CLAIM]
    assert package == "capture"
    assert "source_registry" in why or "descriptor" in why


# ------------------------------------------------------- the expired example, and the right fold

def test_hubspot_is_no_longer_presented_as_unbuildable():
    """⛔ The correction, pinned. The docstring may MENTION `hubspot` -- it has to, to say what
    moved -- but it must not present it as the live example of an unbuildable source."""
    assert "hubspot" in SR.BUILDABLE_SOURCES, (
        "`hubspot` is not buildable any more, which makes the old example true again -- re-read "
        "the docstring's correction before trusting it")
    doc = SR.__doc__ or ""
    assert "`hubspot` advertises the `crm` capability that the `sales` pack REQUIRES, while no" \
        not in doc, "the expired example is back"
    assert "IS BUILDABLE NOW" in doc, (
        "the docstring must say what changed, or the next reader cannot tell a correction from a "
        "deletion")


def test_the_registry_names_no_example_at_all_for_the_stale_sentence():
    """⛔ Naming one source is HOW that sentence went stale, so the corrected version holds no
    name and this test keeps it that way."""
    doc = SR.__doc__ or ""
    line = next(l for l in doc.splitlines() if "advertises a capability a pack REQUIRES" in l)
    assert "`" not in line, (
        f"the corrected sentence names something again: {line!r}. The count lives in a test, "
        "which can be re-run; a name in prose cannot")


def test_the_registry_warns_AT_THE_POINT_OF_EDITING_about_the_inverse_direction():
    """⛔ FOUND BY A SURVIVING MUTATION, and kept unlike its cousin in `U01`.

    There, a prose weakening was left surviving because the fact was measured independently from
    the source of truth. ⛔ Here it is different: this docstring is where somebody goes to ADD a
    source, and it is the only place they would learn that a buildable source with no capability
    feeds nothing. A receipt catches it after a tenant has already connected one; the docstring
    catches it before the descriptor is written.
    """
    doc = SR.__doc__ or ""
    assert "capability = None" in doc, (
        "the registry no longer warns that a buildable source can satisfy no capability. The "
        "next person adding a descriptor gets no warning at the point of editing")
    assert "Receipt 48" in doc or "receipt 48" in doc.lower(), (
        "the warning must point at what measures it, or it reads as a note rather than a rule")


def test_the_names_in_the_warning_MATCH_what_is_measured():
    """⛔⛔ FOUND BY A MUTATION THAT SURVIVES BY DESIGN, AND THIS IS THE REAL GAP IT OPENED.

    Giving `mysql` a capability shrinks the finding to one source, and the tests above tolerate
    that on purpose -- they are written against the registry, not against a hardcoded pair. ✅
    Correct. ⛔ But the docstring I added in the SAME file names *"`database` and `mysql`"*, and
    nothing checked those names against the measurement. So the fix for a stale comment would
    have introduced one, two paragraphs further down, in the exact file whose expired `hubspot`
    example this unit was built to correct.

    The named set must equal the measured set, in both directions.
    """
    doc = SR.__doc__ or ""
    paragraph = doc[doc.index("AND THE DIRECTION NOBODY ASKED"):]
    named = set(re.findall(r"`([a-z_0-9]+)`", paragraph)) & set(SR._BY_ID)
    measured = set(_capability_less())
    assert named == measured, (
        f"the registry's warning names {sorted(named)} and the measurement finds "
        f"{sorted(measured)}. A name in prose ages; update the sentence or drop the names and "
        "keep the count, which is what this unit told the sentence above it to do")


def test_the_capability_advertising_unbuildable_sources_are_COUNTED_not_listed():
    """⛔ The honest form of the docstring's claim. A count a test can re-derive, rather than a
    list in prose that ages the moment one connector ships."""
    stranded = sorted(
        name for name, d in {d.source: d for d in SR._BY_ID.values()}.items()
        if d.capability and not d.buildable)
    assert len(stranded) >= 5, (
        f"only {len(stranded)} catalogued source(s) advertise a capability nobody can connect: "
        f"{stranded}. The docstring's claim is about a class, not a case -- if the class is nearly "
        "empty, say so there")
    assert "salesforce" in stranded, (
        "`salesforce` was the clearest heir to the `hubspot` example -- also `crm`, also "
        "unbuildable. If it shipped, the correction's reasoning needs re-reading")


def test_the_alias_fold_gives_nine_canonical_sources_not_seven():
    """⛔ THE SCORECARD'S NUMBER, CORRECTED. Folded by the declared `aliases` field rather than by
    reading the names -- which is what produced ~7."""
    ids = set(SR.BUILDABLE_SOURCES)
    canonical = _canonical_buildable()
    assert len(ids) == 13, sorted(ids)
    assert len(canonical) == 9, sorted(canonical)
    folded = {c for c in canonical if SR.descriptor_of(c).aliases}
    assert folded == {"gcal", "gdrive"}, (
        f"the sources that absorb other spellings are now {sorted(folded)}. The scorecard once "
        "folded database/mysql/postgres together too, and they are three descriptors with three "
        "different capabilities")
    for name in ("database", "mysql", "postgres"):
        assert SR.descriptor_of(name).source == name, (
            f"{name} is an alias now, which would make the old ~7 right -- recount")
