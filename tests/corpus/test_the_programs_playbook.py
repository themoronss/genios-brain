"""STEP-11 · what a chief of staff knows about an application to a programme — authored, sourced, unreviewed.

    .venv/bin/python -m pytest tests/corpus/test_the_programs_playbook.py -q

Tree `yc2_w27_s11 · M30.C6.L-data.V1.U02`. On the golden set an accelerator's interview (F17), an
accelerator's review (F24) and a government portal (F01, F02) all formed an `investor_relationship`,
because Layer 1 hints programmes into `fundraising`; no Layer 2 situation type is an application and
none will be minted (`06` D32). So this capability owns NO situation: it stays deferred
(`no_runtime_trigger`) and is read by the EXPERT for a file whose kind of work is `program`
(`playbook_for(file)`, STEP-12's dossier). What it holds is what that expert will know:

* ONE playbook — the spine — declares the closed list of stages STEP-12 picks a file's stage from,
  each with a typical duration that is a PRIOR naming its source, what quiet means at that stage and
  the event that ends it; and what success is, how long to wait for it, and what doing nothing costs.
* four moves (playbooks with steps, no stages), each saying what success is and how long to wait;
* the claims (heuristics) the moves rest on;
* one scoped object whose states are the spine's stages.

Every line is the founder's to review (`06` D45), so every artifact is `draft`, `unreviewed`, and
carries no admission stamp — only the founder's review admits. A prior is a profession's value,
never a measurement of this founder, and never called normal (`06` D37). The corpus's own validators
judge the shapes (`_tools/validate.build_validators`), so the authoring tool and this test cannot
disagree about what a valid file is.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "Domain Expertise"
TOOLS = CORPUS / "_tools"
DOMAIN = CORPUS / "Founder Office Expertise"

CAPABILITY = "founder_office.programs_and_applications.program_applications"
CAPABILITY_DIR = DOMAIN / "capabilities" / "02-programs-and-applications" / "program-applications"
#: Where this capability's own artifacts and its scoped object live (the corpus's folder convention).
ARTIFACT_DIRS = (DOMAIN / "playbooks" / "program_applications",
                 DOMAIN / "heuristics" / "program_applications")
OBJECT_DIR = DOMAIN / "objects" / "program-applications"

#: The closed list STEP-12's expert names a file's stage from, in order. `interview` must be one (F17).
STAGES = ("applied", "under_review", "interview", "decision", "onboarding", "in_programme", "declined")
SPINE = "founder_office.pb.program_applications.follow_an_application"
MOVES = frozenset({
    "founder_office.pb.program_applications.work_back_from_the_deadline",
    "founder_office.pb.program_applications.read_the_decision_mail",
    "founder_office.pb.program_applications.prepare_for_the_interview",
    "founder_office.pb.program_applications.documents_after_acceptance",
})
HEURISTICS = frozenset({
    "founder_office.heu.program_applications.a_programme_is_not_an_investor",
    "founder_office.heu.program_applications.a_batch_is_silent_until_it_decides",
    "founder_office.heu.program_applications.the_deadline_is_the_only_fixed_point",
    "founder_office.heu.program_applications.a_rejection_carries_a_reapplication_date",
    "founder_office.heu.program_applications.the_portal_is_the_record",
})
APPLICATION = "founder_office.obj.program_applications.application"
#: capability.yaml + objects.yaml + knowledge.yaml, the object, the spine, the moves, the claims.
EXPECTED_FILES = 3 + 1 + 1 + len(MOVES) + len(HEURISTICS)

#: What a prior's source says when no published page supports the number.
PRACTITIONER = "practitioner judgement — unverified; for the founder's review"

#: The deferral, word for word as `M30.C1.L-contract.V0.U01` wrote it. This unit keeps it exactly.
DEFERRAL_REASON = ("No Layer 2 situation type is an application to a programme; the expert reads this "
                   "capability for a file whose kind of work is `program` (STEP-12).")

#: An id from another domain, or a core object this unit may not load (another unit authors them).
FOREIGN_ID = re.compile(r"\bsales\.[a-z0-9_]+\.[a-z0-9_]+|\bfounder_office\.obj\.core\.")
#: A prior described as this founder's habit rather than a profession's typical value (`06` D37).
HABIT_WORDS = re.compile(r"\bnormal(ly)?\b|usual for you|your usual|you usually|\bhabit", re.I)
URL = re.compile(r"https?://[^\s'\"),;]+")


# ── loading ────────────────────────────────────────────────────────────────────────────────────

def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def _own_files() -> list[Path]:
    """Every YAML file this capability authored: its folder, its artifacts, its scoped object.

    Counted, so a scan over them can never pass because there was nothing to scan."""
    files = sorted(CAPABILITY_DIR.rglob("*.yaml"))
    for folder in (*ARTIFACT_DIRS, OBJECT_DIR):
        files += sorted(folder.rglob("*.yaml"))
    assert len(files) == EXPECTED_FILES, f"{len(files)} files, expected {EXPECTED_FILES}"
    return files


def _artifacts() -> dict[str, dict]:
    """Every playbook and heuristic in the domain that names this capability as its owner."""
    out = {}
    for folder in ("playbooks", "heuristics", "mental-models", "rules", "decision-frameworks"):
        for path in sorted((DOMAIN / folder).rglob("*.yaml")):
            doc = _load(path)
            if (doc.get("identity") or {}).get("owner_capability") == CAPABILITY:
                out[doc["identity"]["id"]] = doc
    return out


def _playbooks() -> dict[str, dict]:
    """The spine and the four moves — exactly those, so no check below passes over an empty set."""
    found = {i: d for i, d in _artifacts().items() if d["identity"]["kind"] == "playbook"}
    assert set(found) == {SPINE} | MOVES, sorted(set(found) ^ ({SPINE} | MOVES))
    return found


def _spine() -> dict:
    return _playbooks()[SPINE]


def _strings(node, trail=()):
    """(dotted location, value) for every string in a document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, (*trail, str(key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _strings(value, (*trail, str(i)))
    elif isinstance(node, str):
        yield ".".join(trail), node


@pytest.fixture(scope="module")
def validators():
    sys.path.insert(0, str(TOOLS))
    try:
        import validate
        return validate.build_validators()
    finally:
        sys.path.remove(str(TOOLS))


# ── the capability ─────────────────────────────────────────────────────────────────────────────

def test_the_capability_is_authored_and_unadmitted():
    """No longer a stub, and not admitted: draft, unreviewed, nobody named, no stamp. The engine's own
    admission rule agrees — the capability carries no authority until the founder's review."""
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
    from genios_engine.packs.compiler.capability_resolver import _admission_reason, _hollow

    doc = _load(CAPABILITY_DIR / "capability.yaml")
    assert doc["identity"]["id"] == CAPABILITY
    assert doc["identity"].get("stub", False) is False, "the capability is still a stub"
    assert doc["identity"]["status"] == "draft"
    assert doc["metadata"]["review_status"] == "unreviewed"
    assert doc["metadata"]["reviewed_by"] == ""
    assert "admission" not in doc, "only the founder's review admits; the lead stamps it after"
    for key in ("outcomes", "failure_modes", "kpis", "handoffs"):
        assert doc.get(key), f"the capability carries no {key}"

    catalog = ExpertBrainCatalog(default_authoring_root())
    capability = catalog.domain("founder_office").capabilities[CAPABILITY]
    assert _admission_reason(capability) == "identity_status_draft"
    assert not _hollow(capability)


def test_it_is_still_deferred_and_says_why():
    deferred = {d["capability"]: d for d in _load(DOMAIN / "deferrals.yaml")["deferred"]}
    entry = deferred[CAPABILITY]
    assert entry["kind"] == "no_runtime_trigger"
    assert " ".join(entry["reason"].split()) == DEFERRAL_REASON
    registry = _load(DOMAIN / "registry" / "situation-capability-map.yaml")
    assert CAPABILITY in (registry.get("deferred_capabilities") or {}), (
        "the generated registry no longer lists the deferral — regenerate it with _tools/index.py")


def test_it_owns_no_situation():
    """No Layer 2 type is an application (`06` D32): no situation is authored, and nothing routes here."""
    assert not list(CAPABILITY_DIR.glob("situations/*.yaml"))
    for path in DOMAIN.rglob("situations/*.yaml"):
        doc = _load(path)
        assert (doc.get("identity") or {}).get("owner_capability") != CAPABILITY, path
        assert CAPABILITY not in (doc.get("also_serves") or []), path
    registry = _load(DOMAIN / "registry" / "situation-capability-map.yaml")
    for route, entry in (registry.get("map") or {}).items():
        assert CAPABILITY not in (entry.get("capabilities") or []), route


# ── the spine: the stages ──────────────────────────────────────────────────────────────────────

def test_exactly_one_playbook_declares_the_stages():
    """One kind of work, one closed list. A second playbook with stages would leave STEP-12's expert
    two lists to pick a file's stage from."""
    staged = sorted(i for i, d in _playbooks().items() if "stages" in d)
    assert staged == [SPINE]
    assert tuple(stage["name"] for stage in _spine()["stages"]) == STAGES


def test_every_stage_carries_a_sourced_prior_and_what_quiet_means():
    for stage in _spine()["stages"]:
        name = stage["name"]
        prior = stage["typical_duration_days"]
        assert type(prior) is int and prior >= 0, f"{name}: the prior is not whole days: {prior!r}"
        for field in ("label", "source", "quiet_means", "leaves_when"):
            assert str(stage.get(field) or "").strip(), f"{name}: no {field}"


def test_every_source_is_a_page_read_or_says_it_is_judgement():
    """A prior names a page its playbook lists among its references — or says, in so many words, that
    no page supports it. A URL a reference does not list is a citation nobody can check."""
    checked = 0
    for pid, doc in _playbooks().items():
        listed = {ref.get("url") for ref in doc.get("references") or [] if ref.get("url")}
        for stage in doc.get("stages") or []:
            source = stage["source"]
            urls = set(URL.findall(source))
            assert urls or PRACTITIONER in source, f"{pid} · {stage['name']}: no page and no label"
            assert urls <= listed, f"{pid} · {stage['name']}: cites {sorted(urls - listed)} unlisted"
            checked += 1
    assert checked == len(STAGES)


def test_the_spine_and_every_move_say_what_success_is_and_how_long_to_wait():
    for pid, doc in _playbooks().items():
        assert str(doc.get("success_signal") or "").strip(), f"{pid}: no success_signal"
        window = doc.get("outcome_window_days")
        assert type(window) is int and window >= 1, f"{pid}: outcome_window_days {window!r}"
    assert str(_spine().get("do_nothing_consequence") or "").strip()


def test_every_step_says_when_it_is_done():
    """A step nobody can tell is finished is a wish."""
    for pid, doc in _playbooks().items():
        steps = doc.get("steps") or []
        assert len(steps) >= 3, f"{pid}: {len(steps)} steps"
        assert [s["order"] for s in steps] == list(range(1, len(steps) + 1)), pid
        for step in steps:
            assert str(step.get("done_when") or "").strip(), f"{pid} · step {step['order']}"


# ── the knowledge, the object, and the manifests ───────────────────────────────────────────────

def test_the_moves_and_the_claims_are_authored_and_listed():
    artifacts = _artifacts()
    heuristics = {i for i, d in artifacts.items() if d["identity"]["kind"] == "heuristic"}
    assert heuristics == HEURISTICS, sorted(heuristics ^ HEURISTICS)
    assert {i for i, d in artifacts.items()
            if d["identity"]["kind"] not in ("playbook", "heuristic")} == set()
    for hid in HEURISTICS:
        claim = artifacts[hid]["heuristic"]
        for field in ("statement", "why", "breaks_down_when"):
            assert str(claim.get(field) or "").strip(), f"{hid}: no {field}"

    knowledge = _load(CAPABILITY_DIR / "knowledge.yaml")
    assert knowledge["capability"] == CAPABILITY
    assert set(knowledge["playbooks"]["scoped"]) == {SPINE} | MOVES
    assert set(knowledge["heuristics"]["scoped"]) == HEURISTICS
    for key in ("playbooks", "heuristics", "mental_models", "rules", "decision_frameworks"):
        assert not (knowledge.get(key) or {}).get("core"), f"{key}: a core artifact is listed"


def test_the_application_moves_through_the_spines_stages():
    """The object's lifecycle and the playbook's stages are one list, or the expert and the object
    disagree about where an application can be."""
    manifest = _load(CAPABILITY_DIR / "objects.yaml")
    assert manifest["capability"] == CAPABILITY
    assert manifest["scoped"]["required"] == [APPLICATION]
    assert not manifest["core"]["required"] and not manifest["core"].get("optional")

    [path] = sorted(OBJECT_DIR.glob("*.yaml"))
    application = _load(path)
    assert application["identity"]["id"] == APPLICATION
    assert application["identity"]["owner_capability"] == CAPABILITY
    states = application["states"]
    names = tuple(value["name"] for value in states["values"])
    assert names == STAGES
    assert states["initial"] == STAGES[0]
    assert set(states["terminal"]) <= set(STAGES) and "declined" in states["terminal"]
    for transition in states["transitions"]:
        assert {transition["from"], transition["to"]} <= set(STAGES), transition
        assert transition["from"] not in states["terminal"], f"a terminal state leaves: {transition}"


def test_every_artifact_is_draft_unreviewed_and_unadmitted():
    """`06` D45: the founder reviews every line; nothing here may look reviewed before that."""
    docs = {APPLICATION: _load(next(OBJECT_DIR.glob("*.yaml"))), **_artifacts()}
    for oid, doc in docs.items():
        identity, meta = doc["identity"], doc["metadata"]
        assert identity["status"] == "draft", oid
        assert identity["scope"] == "capability" and identity["owner_capability"] == CAPABILITY, oid
        assert meta["review_status"] == "unreviewed" and meta["reviewed_by"] == "", oid
        assert meta["created_by"] == "ai" and meta["last_updated"] == "2026-10-09", oid
        assert "admission" not in doc, oid


# ── what may not appear ────────────────────────────────────────────────────────────────────────

def test_no_other_domain_and_no_core_object_is_named():
    """Handoffs and references stay inside the Founder Office, and the core objects are another unit's."""
    for path in _own_files():
        hits = FOREIGN_ID.findall(path.read_text())
        assert not hits, f"{path.relative_to(DOMAIN)} names {hits}"


def test_handoffs_name_only_this_domains_capabilities():
    declared = {_load(p)["identity"]["id"] for p in DOMAIN.glob("capabilities/*/*/capability.yaml")}
    handoffs = _load(CAPABILITY_DIR / "capability.yaml")["handoffs"]
    named = [cid for side in ("upstream", "downstream", "parallel") for cid in handoffs.get(side) or []]
    assert named, "no handoff at all"
    assert set(named) <= declared - {CAPABILITY}, sorted(set(named) - declared)


def test_no_prior_is_called_normal_or_a_habit():
    """A prior is what a typical programme does — never what is normal, and never this founder's habit."""
    for path in _own_files():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            assert not HABIT_WORDS.search(line), f"{path.relative_to(DOMAIN)}:{number}: {line.strip()}"


def test_the_capability_states_no_numbers():
    """Rule 7: thresholds are Layer 4's arithmetic. The numbers live in the playbooks, as sourced priors."""
    doc = _load(CAPABILITY_DIR / "capability.yaml")
    for where, text in _strings(doc):
        if where in ("identity.version", "metadata.last_updated"):
            continue
        assert not re.search(r"\d", text), f"capability.yaml {where}: {text!r}"


# ── the corpus's own judgment ──────────────────────────────────────────────────────────────────

def test_every_file_passes_its_own_schema(validators):
    sys.path.insert(0, str(TOOLS))
    try:
        from _lib import classify
    finally:
        sys.path.remove(str(TOOLS))
    for path in _own_files():
        kind = classify(path, DOMAIN)
        errors = [e.message for e in validators[kind].iter_errors(_load(path))]
        assert not errors, f"{path.relative_to(DOMAIN)} [{kind}]: {errors[:3]}"


def test_the_corpus_validates_with_no_errors():
    result = subprocess.run([sys.executable, str(TOOLS / "validate.py")], cwd=REPO,
                            capture_output=True, text=True)
    mine = [line for line in result.stdout.splitlines()
            if "ERROR" in line and ("program" in line or "Founder" in line)]
    assert result.returncode == 0, mine or result.stdout[-2000:]
    assert re.search(r"^0 error\(s\)", result.stdout, re.M), result.stdout[-2000:]
