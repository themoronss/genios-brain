r"""Plane D `U04` · no capability is authored, unreachable, and unexplained.

⛔ Seven Customer Support capabilities were authored, admission-stamped, `stable`, not stubs — and
reachable by nothing. The validator could only WARN, because the census is enforced as errors for a
domain that has opted in by authoring a ledger, and this domain had none. Seven warnings among 290
is a fact nobody reads.

**The difference between "deferred, and here is why" and "forgotten" is the entire declared-silence
doctrine**, and this domain had nowhere to say the first.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
CORPUS = REPO / "Domain Expertise"
SUPPORT = CORPUS / "Customer Support Expertise"
LEDGER = SUPPORT / "deferrals.yaml"

THE_SEVEN = (
    "customer_support.diagnosis_and_resolution.issue_reproduction",
    "customer_support.diagnosis_and_resolution.resolution_delivery",
    "customer_support.diagnosis_and_resolution.root_cause_analysis",
    "customer_support.diagnosis_and_resolution.verification_and_closure",
    "customer_support.escalation_and_incident.incident_management",
    "customer_support.escalation_and_incident.major_incident_communication",
    "customer_support.escalation_and_incident.postmortem",
)


def _entries() -> dict[str, dict]:
    data = yaml.safe_load(LEDGER.read_text()) or {}
    return {str(e["capability"]): e for e in (data.get("deferred") or []) if e.get("capability")}


def _validate() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CORPUS / "_tools/validate.py")], cwd=REPO,
                          capture_output=True, text=True)


# ── the file, and the bar it raises ───────────────────────────────────────────────────────────

def test_the_ledger_exists_and_names_its_domain():
    data = yaml.safe_load(LEDGER.read_text()) or {}
    assert data.get("domain") == "customer_support"
    assert data.get("version")


def test_all_seven_are_covered_and_nothing_else_is():
    """⛔ ALL-OR-NOTHING BY CONSTRUCTION. `validate.py` errors on an unrouted capability with no
    deferral ONLY when the ledger exists, so a partial ledger is worse than none — it converts
    seven warnings into seven errors."""
    assert set(_entries()) == set(THE_SEVEN)


@pytest.mark.parametrize("cid", THE_SEVEN)
def test_every_entry_has_a_kind_the_tools_recognise(cid):
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("_dx_lib", CORPUS / "_tools/_lib.py")
    lib = module_from_spec(spec)
    spec.loader.exec_module(lib)                                         # type: ignore[union-attr]
    assert _entries()[cid]["kind"] in lib.DEFERRAL_KINDS


@pytest.mark.parametrize("cid", THE_SEVEN)
def test_every_reason_is_a_sentence_not_a_category(cid):
    """The validator's own bar: under 40 collapsed characters is *"a category is not a reason"*. The
    sentence is the half a reader six months from now actually needs."""
    reason = " ".join(str(_entries()[cid].get("reason") or "").split())
    assert len(reason) >= 40, reason
    assert reason[0].isupper() and reason.rstrip().endswith("."), reason


@pytest.mark.parametrize("cid", THE_SEVEN)
def test_every_reason_says_what_would_unblock_it(cid):
    """⛔ A reason that describes only the absence leaves a reader unable to act. Admin's ledger sets
    the shape: three kinds, *"and the difference between them is who unblocks it."*"""
    entry = _entries()[cid]
    blocked = entry.get("blocked_on") or []
    assert blocked, f"{cid} names no missing type"
    assert all(isinstance(b, str) and b for b in blocked)


def test_all_seven_are_blocked_on_a_type_and_that_is_the_finding():
    """⛔ Not `out_of_v1_scope` and not `no_runtime_trigger`: every one is waiting on a type Layer 1
    or Layer 2 does not emit yet. Measured — the four types named are all in
    `_schema/vocabulary.yaml`'s `planned_substrate`."""
    kinds = {e["kind"] for e in _entries().values()}
    assert kinds == {"blocked_on_l2_type"}


def test_every_blocked_on_type_is_actually_planned_and_not_invented():
    """⛔ A deferral blaming a type nobody has planned blames nothing. This is the assertion that
    keeps the ledger honest against the vocabulary rather than against its author's memory."""
    vocab = yaml.safe_load((CORPUS / "_schema/vocabulary.yaml").read_text()) or {}
    planned = set((vocab.get("planned_substrate") or {}).get("l2_situation_types") or [])
    emitted = set((vocab.get("substrate") or {}).get("l2_situation_types") or [])
    named = {b for e in _entries().values() for b in (e.get("blocked_on") or [])}
    assert named <= planned, sorted(named - planned)
    assert not (named & emitted), f"these ARE emitted, so the deferral is wrong: {named & emitted}"


# ── and the corpus is clean ───────────────────────────────────────────────────────────────────

def test_the_corpus_has_no_errors():
    result = _validate()
    assert result.returncode == 0, result.stdout[-3000:]


def test_the_seven_warnings_are_gone():
    out = _validate().stdout
    assert "this domain has no\n" not in out
    assert "has no deferrals.yaml to say why" not in out


def test_no_capability_in_any_domain_is_now_unexplained():
    """The whole unit, in one assertion, over the whole corpus."""
    out = _validate().stdout
    assert "routed by nothing" not in out, [
        line for line in out.splitlines() if "routed by nothing" in line]


def test_the_generated_registry_was_regenerated_after_the_deferral():
    """⛔ Deferring a capability SUPPRESSES every situation it owns from the generated map, so the
    registry changes. `U02`'s guard now fails when it is not regenerated — this proves the two units
    are consistent with each other rather than each green alone."""
    registry = yaml.safe_load(
        (SUPPORT / "registry/situation-capability-map.yaml").read_text()) or {}
    stats = registry.get("stats") or {}
    assert stats.get("capabilities_deferred") == 7
    assert stats.get("capabilities_unrouted_unreasoned") == 0


def test_the_three_suppressed_situations_were_draft_and_bound_nothing():
    """⛔ THE SUPPRESSION COST, ASSERTED. Deferring three of the seven removes the situations they
    own. All three were `status: draft` and bound zero L2 types, so they routed nothing before and
    route nothing now — which is why this was safe. If that ever stops being true, this fails."""
    owned = {
        "customer_support.diagnosis_and_resolution.root_cause_analysis":
            "issue-under-diagnosis",
        "customer_support.diagnosis_and_resolution.verification_and_closure":
            "ticket-reopened",
        "customer_support.escalation_and_incident.incident_management":
            "major-incident-declared",
    }
    for _, stem in owned.items():
        path = next(SUPPORT.glob(f"capabilities/*/*/situations/{stem}.yaml"))
        doc = yaml.safe_load(path.read_text()) or {}
        assert (doc.get("identity") or {}).get("status") == "draft", stem
        assert not ((doc.get("matches") or {}).get("l2_situation_types") or []), stem


def test_sales_deliberately_has_no_ledger():
    """⛔ Sales has 47 capabilities and zero routed by nothing, so there is nothing to explain.
    Creating an empty ledger would raise its error bar for no present benefit and would be a file
    whose only content is that it exists."""
    assert not (CORPUS / "Sales Expertise/deferrals.yaml").exists()


def test_admins_ledger_was_not_touched():
    """This unit added a file; it did not edit the domain that already did this correctly."""
    admin = yaml.safe_load((CORPUS / "Admin Expertise/deferrals.yaml").read_text()) or {}
    assert admin.get("domain") == "admin"
    assert len(admin.get("deferred") or []) >= 20


def test_the_ledger_says_it_is_not_an_activation():
    """⛔ Support stays on hold. A reader finding this file must not conclude the domain is live."""
    text = LEDGER.read_text()
    assert "NOT AN ACTIVATION" in text.upper()
    assert "on hold" in text
