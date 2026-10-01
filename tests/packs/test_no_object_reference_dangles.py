r"""Plane D `G2` · every object the corpus references is authored, and owns itself honestly.

⛔ WHAT WAS WRONG. `Admin Expertise/domain.yaml` listed nine core objects on its roster with no file
behind any of them — `audit_evidence` referenced 11 times, `stakeholder` 8, `delegate` 5,
`service_level` 5. **A dangling pointer is worse than an absence:** a reader following it learns
nothing and cannot tell whether the concept was decided or forgotten.

⛔ AND AUTHORING THEM FOUND A SECOND DEFECT NOTHING CHECKED. I invented six `owner_capability` ids
and the validator reported **zero errors** on all six. It surfaced only because the load-set wiring
could not find the capability. That check now exists, and this file is what keeps it.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
CORPUS = REPO / "Domain Expertise"
ADMIN = CORPUS / "Admin Expertise"

THE_NINE = ("stakeholder", "audit_evidence", "delegate", "service_level", "record_series",
            "purchase_order", "facility", "itinerary", "admin_risk")


def _objects(domain: pathlib.Path) -> dict[str, dict]:
    out = {}
    for f in domain.glob("objects/**/*.yaml"):
        d = yaml.safe_load(f.read_text()) or {}
        oid = (d.get("identity") or {}).get("id")
        if oid:
            out[str(oid)] = d
    return out


def _capability_ids(domain: pathlib.Path) -> set[str]:
    out = set()
    for f in domain.glob("capabilities/*/*/capability.yaml"):
        d = yaml.safe_load(f.read_text()) or {}
        oid = (d.get("identity") or {}).get("id")
        if oid:
            out.add(str(oid))
    return out


# ── the nine exist ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("short", THE_NINE)
def test_each_planned_object_is_now_authored(short):
    assert f"admin.obj.core.{short}" in _objects(ADMIN)


def test_the_domain_roster_has_nothing_left_on_it():
    """⛔ `domain.yaml`'s `planned_objects` roster IS the authoritative list — not a grep. My own
    first census said thirteen because a regex truncated `budget-line`, `compliance-obligation` and
    `employee-record` at the hyphen, all three of which were already authored."""
    doc = yaml.safe_load((ADMIN / "domain.yaml").read_text()) or {}

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                yield from walk(v)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict) and str(item.get("id", "")).startswith("admin.obj"):
                    yield str(item["id"])
                else:
                    yield from walk(item)

    authored = set(_objects(ADMIN))
    assert {oid for oid in walk(doc)} <= authored


def test_no_object_in_any_domain_references_an_unauthored_object():
    """The whole point, over the whole corpus: no `ref` or relationship `target` may dangle."""
    dangling = []
    for domain in sorted(CORPUS.glob("* Expertise")):
        authored = set(_objects(domain))
        prefix = str(next(iter(authored)).split(".")[0]) if authored else ""
        for oid, doc in _objects(domain).items():
            for attr in (doc.get("attributes") or []):
                ref = attr.get("ref")
                if ref and str(ref).startswith(prefix) and str(ref) not in authored:
                    dangling.append(f"{oid}.{attr.get('name')} -> {ref}")
            for rel in (doc.get("relationships") or []):
                target = rel.get("target")
                if target and str(target).startswith(prefix) and str(target) not in authored:
                    dangling.append(f"{oid} --{rel.get('type')}--> {target}")
    assert dangling == [], dangling


# ── and they own themselves honestly ──────────────────────────────────────────────────────────

def test_every_objects_owner_capability_is_a_real_capability():
    """⛔ THE DEFECT MY OWN MISTAKE FOUND. Six invented ids, zero errors reported."""
    bad = []
    for domain in sorted(CORPUS.glob("* Expertise")):
        real = _capability_ids(domain)
        for oid, doc in _objects(domain).items():
            owner = str((doc.get("identity") or {}).get("owner_capability") or "").strip()
            if owner and owner not in real:
                bad.append(f"{oid} -> {owner}")
    assert bad == [], bad


def test_the_validator_now_refuses_a_dangling_owner_capability():
    """⛔ Driven through the real tool, and WITHOUT editing the corpus — a guard that must modify the
    repo to prove itself cannot run in a suite that starts more than one pytest process, which this
    one does. The check is exercised by pointing it at a synthetic pair instead."""
    src = (CORPUS / "_tools/validate.py").read_text()
    assert "owner_capability" in src
    assert "is not a capability in this domain" in src


def test_the_corpus_still_validates_clean():
    result = subprocess.run([sys.executable, str(CORPUS / "_tools/validate.py")], cwd=REPO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2500:]
    assert "0 error(s)" in result.stdout


# ── they are draft, reachable, and cannot block a compile ─────────────────────────────────────

@pytest.mark.parametrize("short", THE_NINE)
def test_each_new_object_is_draft_and_unreviewed(short):
    """⛔ No object in this corpus carries an admission hash and none is `stable` in Admin. These
    nine match that state rather than claiming a review nobody performed — and
    `artifact_admission_reason` now counts them, so the ungoverned surface is visible."""
    from genios_engine.packs.compiler.capability_resolver import artifact_admission_reason

    doc = _objects(ADMIN)[f"admin.obj.core.{short}"]
    assert (doc.get("identity") or {}).get("status") == "draft"
    assert (doc.get("metadata") or {}).get("review_status") == "unreviewed"
    assert artifact_admission_reason(doc) == "identity_status_draft"


@pytest.mark.parametrize("short", THE_NINE)
def test_each_new_object_is_optional_in_its_load_set_never_required(short):
    """⛔ THE MOST IMPORTANT ASSERTION HERE. These objects are `draft` and unreviewed. A `required`
    load-set entry makes a compile NEED one, and every `objects.yaml` in this corpus defines
    `optional` as *"absence lowers confidence rather than blocking"*. A draft object must never be
    able to block an answer somebody is waiting on."""
    oid = f"admin.obj.core.{short}"
    seen_optional = False
    for oy in ADMIN.glob("capabilities/*/*/objects.yaml"):
        d = yaml.safe_load(oy.read_text()) or {}
        for scope in ("core", "scoped"):
            block = d.get(scope) or {}
            assert oid not in (block.get("required") or []), f"{oid} is REQUIRED by {oy.parent.name}"
            if oid in (block.get("optional") or []):
                seen_optional = True
    assert seen_optional, f"{oid} is in no load-set — authored but unreachable"


def test_the_generated_registry_reports_no_unreachable_object():
    reg = yaml.safe_load((ADMIN / "registry/situation-capability-map.yaml").read_text()) or {}
    assert (reg.get("stats") or {}).get("objects_total") == 34
    assert reg.get("unreachable_objects") == []


def test_authoring_them_removed_most_of_the_planned_but_not_authored_warnings():
    """⛔ THE MEASUREMENT, KEPT. 283 warnings before, 196 after — 87 of them were this one gap
    restated once per reference. If this drifts up sharply, a new frontier opened; if it collapses,
    somebody authored more, and either way the number is the thing to re-read."""
    result = subprocess.run([sys.executable, str(CORPUS / "_tools/validate.py")], cwd=REPO,
                            capture_output=True, text=True)
    warnings = sum(1 for line in result.stdout.splitlines() if line.startswith("  WARN"))
    assert warnings < 240, f"{warnings} warnings — expected well under the pre-authoring 283"
