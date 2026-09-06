"""D2 · every park code the gate can emit reaches exactly one drain, and is counted.

THE DEFECT THIS FILE EXISTS FOR. `capture/gate/rules.py::content_integrity_rule` grew three park
codes — ``DOC-07`` (an OCR engine ran and read nothing), ``DOC-08`` (audio arrived and no speech
engine is wired), ``DOC-09`` (a speech engine ran and produced no transcript) — and
`capture/parked/drain.py` was never told about them. They are in neither `RE_ADJUDICABLE` nor
`NEEDS_REFETCH`, so:

  * `drain_parked` falls off the end of its loop for them: not re-adjudicated, not refetched, not
    even counted as `needs_refetch`;
  * `parked_aging` labels them ``"terminal"``, which is a claim nobody made;
  * the refetch claim (`reason_code = any(:reasons)`) never selects them;
  * `read_aging` — the query `scripts/l1_s1_report.py`'s first metric IS — filters on the same
    set, so the G2 report cannot see them at all.

A whole class of documents therefore sits at ``status='pending'`` forever while every surface
that could show it reads clean. That is the same silent loss the parked queue was built to remove,
one level up: not a lost attachment, a lost *reason*.

WHY THE COVERAGE TEST IS DRIVEN FROM `content_integrity_rule` RATHER THAN FROM A LIST. A list of
park codes in a test is a second place to forget. Driving the real gate rule with every
`DocumentStatus` the router can produce means the next status that earns a park code fails HERE,
at the wiring, instead of six months later in a backlog nobody can see.
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone

import pytest

from genios_engine.capture.documents.base import DocumentStatus
from genios_engine.capture.gate import gate as GATE_MODULE
from genios_engine.capture.gate import rules as RULES_MODULE
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.rules import REASON_LABELS, content_integrity_rule
from genios_engine.capture.parked.drain import NEEDS_REFETCH, RE_ADJUDICABLE
from genios_engine.capture.parked.recapture import NEEDS_RECAPTURE
from genios_engine.contracts.source_event import Actor, SourceEvent

#: Every status under which a document arrives EMPTY and says why. `accepted` is excluded because
#: it is the one status that does not park — `documents/base.py` refuses an accepted document with
#: no text, so it never reaches the integrity rule.
EMPTY_DOCUMENT_STATUSES = tuple(s for s in DocumentStatus if s is not DocumentStatus.ACCEPTED)


def _ctx(status: str) -> GateContext:
    event = SourceEvent(
        event_id="evt_doc", org_id="org_1", connection_id="conn_1", source="gmail",
        object_type="email_attachment", source_object_id="m1::att1",
        dedup_key="gmail:email_attachment:m1::att1",
        actor=Actor(type="external_contact", email="counsel@acme.com"),
        occurred_at=datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc))
    return GateContext(event=event, raw={"subject": "MSA.pdf", "document": {"status": status}})


@pytest.mark.parametrize("status", EMPTY_DOCUMENT_STATUSES, ids=lambda s: s.value)
def test_every_empty_document_status_parks_under_a_code_some_drain_owns(status):
    """The wiring assertion: a park code with no drain is a document nobody will ever look at
    again, and it is invisible because `by_reason` counts a bucket it then walks past."""
    verdict = content_integrity_rule(_ctx(status.value))
    assert verdict is not None, f"{status.value} must park, not fall through to an empty emit"
    reason_code, action = verdict
    assert action == "park"

    _assert_exactly_one_owner(reason_code)


def _assert_exactly_one_owner(reason_code: str) -> None:
    owners = [name for name, codes in _DRAIN_CLASSES if reason_code in codes]
    assert owners, (f"{reason_code} ({REASON_LABELS.get(reason_code)}) is parked by the gate and "
                    "claimed by no drain — it can never leave 'pending'")
    assert len(owners) == 1, f"{reason_code} is claimed by two drains: {owners}"


#: The complete set of drain classes. Adding a fourth without adding it here is caught by
#: `test_every_drain_class_is_listed_here`, so this tuple cannot silently go stale.
_DRAIN_CLASSES = (("RE_ADJUDICABLE", RE_ADJUDICABLE),
                  ("NEEDS_REFETCH", NEEDS_REFETCH),
                  ("NEEDS_RECAPTURE", NEEDS_RECAPTURE))


def test_the_drain_classes_never_overlap():
    """Exactly one drain per code is the property that makes `drain_parked`'s branch order a
    decision rather than an accident."""
    for i, (a_name, a) in enumerate(_DRAIN_CLASSES):
        for b_name, b in _DRAIN_CLASSES[i + 1:]:
            assert not (a & b), f"{a_name} and {b_name} both claim {sorted(a & b)}"


# ── the ratchet: enumerate the park SITES, not one rule ───────────────────────────────────────

def park_codes_from_the_gate() -> frozenset[str]:
    """Every reason code `capture/gate/` can PARK under, read out of its own source.

    THE DEFECT THIS FUNCTION ENDS. The parametrised test above drives `content_integrity_rule`
    with every `DocumentStatus`, and that is not the same set as "every park code". The rule has
    a branch no status reaches — ``MUT-01``, the versionless-mutable park — and `gate/gate.py`
    parks under two codes of its own (``visibility_unknown`` at S0.6, ``mapping_missing`` at
    S1.5). Only `mapping_missing` was claimed. ``MUT-01`` and ``visibility_unknown`` were in no
    drain class at all: `drain_parked` counted them into `by_reason` and walked past,
    `parked_aging` labelled them ``"terminal"`` — a claim nobody made — and no G2 metric could
    see them, so a tenant's held events accumulated at ``status='pending'`` while every surface
    read clean. That is the *exact* paragraph `drain.py` writes about DOC-07/08/09, happening
    again to two codes that are not documents.

    Two syntactic shapes carry a park in that package and both are matched:
    a `reason_code=` keyword in a call whose other arguments include the literal ``"park"``, and
    the ``(code, "park")`` tuple `content_integrity_rule` returns.
    """
    found: set[str] = set()
    for module in (GATE_MODULE, RULES_MODULE):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                literals = {a.value for a in node.args
                            if isinstance(a, ast.Constant) and isinstance(a.value, str)}
                literals |= {k.value.value for k in node.keywords
                             if isinstance(k.value, ast.Constant)
                             and isinstance(k.value.value, str)}
                if "park" in literals:
                    found.update(str(k.value.value) for k in node.keywords
                                 if k.arg == "reason_code" and isinstance(k.value, ast.Constant))
            elif isinstance(node, ast.Tuple) and len(node.elts) == 2:
                code, action = node.elts
                if (isinstance(code, ast.Constant) and isinstance(code.value, str)
                        and isinstance(action, ast.Constant) and action.value == "park"):
                    found.add(code.value)
    return frozenset(found)


def test_the_enumeration_finds_the_park_sites_it_is_meant_to():
    """Guard on the guard. An AST walk that matched nothing would make the ratchet below pass
    over an empty set — the most convincing kind of green there is."""
    codes = park_codes_from_the_gate()
    assert len(codes) >= 10, sorted(codes)
    for expected in ("MUT-01", "visibility_unknown", "mapping_missing", "DOC-05",
                     "llm_junk_unconfident", "low_relevance"):
        assert expected in codes, (
            f"{expected} is a park site the enumeration missed: {sorted(codes)}")


@pytest.mark.gate
def test_every_park_code_the_gate_can_emit_is_claimed_by_exactly_one_drain():
    """THE RATCHET. Not "every DocumentStatus" — every park SITE."""
    for reason_code in sorted(park_codes_from_the_gate()):
        _assert_exactly_one_owner(reason_code)


def test_every_drain_class_is_listed_in_this_file():
    """A fourth class added to the package and not to `_DRAIN_CLASSES` would make the ratchet
    report a code as orphaned when it is owned — or, worse, keep passing while the new class
    goes unchecked for overlap."""
    import genios_engine.capture.parked.drain as D
    import genios_engine.capture.parked.recapture as RC
    listed = {id(codes) for _name, codes in _DRAIN_CLASSES}
    for module in (D, RC):
        for name in dir(module):
            value = getattr(module, name)
            if (isinstance(value, frozenset) and name.isupper()
                    and value and all(isinstance(v, str) for v in value)):
                assert id(value) in listed, (
                    f"{module.__name__}.{name} looks like a drain class and is not listed in "
                    "_DRAIN_CLASSES, so nothing checks it for overlap or coverage")


@pytest.mark.parametrize("reason_code", ["DOC-07", "DOC-08", "DOC-09"])
def test_the_three_late_document_codes_are_refetchable(reason_code):
    """Named individually so the failure message says WHICH code was orphaned.

    All three describe an attachment whose bytes we could not turn into text — a scan the engine
    read as noise, audio with no speech engine, a transcript that came back empty. The retained
    payload is the same empty stub `_attachment_stub` writes, so re-adjudicating it re-parks it;
    only the connector can answer them, which is the definition of NEEDS_REFETCH.
    """
    assert reason_code in NEEDS_REFETCH
