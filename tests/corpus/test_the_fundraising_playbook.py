"""STEP-11 · the Founder Office's fundraising capability: Sales' investor doctrine, moved and deepened.

    .venv/bin/python -m pytest tests/corpus/test_the_fundraising_playbook.py -q

Tree `yc2_w27_s11 · M30.C6.L-data.V1.U01`. Investor relations sat in the Sales corpus only because a
compiled signal could carry authority in no other lane; an investor is not a customer, and the
Founder Office (`06` D2) is where the doctrine now lives, under its own ids. It is deepened into what
a seasoned chief of staff knows about a raise:

  * ONE playbook — the spine — declares the stages, the closed list STEP-12's expert picks a file's
    current stage from. Each stage carries a typical duration as a PRIOR with its source (a
    profession's value, never a measurement of this founder and never called normal, `06` D37),
    what quiet means at that stage, and the event that ends it;
  * the moves — the wave gone silent, the conditional deferral, a warm intro, before an investor
    call, reopen after a pass — each with steps that say when they are done, a success signal and a
    window to wait for it, the window's source named;
  * the heuristics the moves rest on, each a claim with its reason;
  * the two situations Sales routed, re-identified, with `matches` exactly as Sales had them so
    routing behaviour does not change, loading Founder Office objects only and saying what doing
    nothing costs.

Every file is a draft nobody has reviewed: the founder reviews it line by line (`06` D45) and only
that review admits it — no `admission` block is written here. Validated by the corpus's own
validators (`_tools/validate.build_validators`), so the authoring tool and this test cannot disagree.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "Domain Expertise" / "_tools"
ROOT = REPO / "Domain Expertise" / "Founder Office Expertise"
CAP_DIR = ROOT / "capabilities" / "01-fundraising" / "investor-relations"

CAPABILITY = "founder_office.fundraising.investor_relations"
SPINE = "founder_office.pb.investor_relations.run_an_investor_conversation"

#: The closed list, in order — first contact to a decision. `closed` and `passed` are terminal.
STAGES = ("first_contact", "first_call", "partner_meeting", "diligence", "term_sheet",
          "closed", "passed")
TERMINAL = ("closed", "passed")

#: The moves (playbooks with steps and no stages).
MOVES = frozenset({
    "founder_office.pb.investor_relations.the_wave_gone_silent",
    "founder_office.pb.investor_relations.the_conditional_deferral",
    "founder_office.pb.investor_relations.a_warm_intro_to_an_investor",
    "founder_office.pb.investor_relations.before_an_investor_call",
    "founder_office.pb.investor_relations.reopen_after_a_pass",
})

#: The two heuristics moved from Sales, under their new ids; others may join them.
MOVED_HEURISTICS = frozenset({
    "founder_office.heu.investor_relations.investors_do_not_chase",
    "founder_office.heu.investor_relations.a_pass_is_a_date_not_a_verdict",
})

#: Sales' `matches` at `6f0c86d4`, pinned literally: the route must not change when the file moves.
SALES_MATCHES = {
    "founder_office.sit.live_investor_relationship": {
        "l2_situation_types": ["investor_relationship"], "scope": "account",
        "when": [{"absent": "commitment.due_at"}]},
    "founder_office.sit.live_investor_contact": {
        "l2_situation_types": ["investor_contact"], "scope": "person",
        "when": [{"absent": "commitment.due_at"}]},
}

#: A prior is a profession's value. These words make it a habit or a norm (`06` D37).
_NORMAL = re.compile(r"\bnormal(ly)?\b|\busual for you\b|\byou usually\b", re.IGNORECASE)
#: A Sales id in any form — whole value or inside prose.
_SALES_ID = re.compile(r"\bsales\.[a-z0-9_]+\.[a-z0-9_]+")


# ── loading ────────────────────────────────────────────────────────────────────────────────────

def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), f"{path} does not parse to a mapping"
    return data


def _corpus() -> dict[str, tuple[Path, dict]]:
    """Every authored document in the Founder Office corpus with an identity, by id."""
    out: dict[str, tuple[Path, dict]] = {}
    for path in sorted(ROOT.rglob("*.yaml")):
        if "registry" in path.relative_to(ROOT).parts:
            continue
        data = yaml.safe_load(path.read_text())
        ident = (data or {}).get("identity") if isinstance(data, dict) else None
        if isinstance(ident, dict) and ident.get("id"):
            out[str(ident["id"])] = (path, data)
    return out


CORPUS = _corpus()


def _knowledge() -> dict:
    return _load(CAP_DIR / "knowledge.yaml")


def _objects_manifest() -> dict:
    return _load(CAP_DIR / "objects.yaml")


def _ids(block: dict | None) -> list[str]:
    block = block or {}
    return list(block.get("core") or []) + list(block.get("scoped") or [])


def _playbook_ids() -> list[str]:
    return _ids(_knowledge().get("playbooks"))


def _heuristic_ids() -> list[str]:
    return _ids(_knowledge().get("heuristics"))


def _object_ids() -> list[str]:
    manifest = _objects_manifest()
    out: list[str] = []
    for bucket in ("core", "scoped"):
        for key in ("required", "optional"):
            out += list((manifest.get(bucket) or {}).get(key) or [])
    return out


def _situation_files() -> dict[str, tuple[Path, dict]]:
    out = {}
    for path in sorted((CAP_DIR / "situations").glob("*.yaml")):
        data = _load(path)
        out[str(data["identity"]["id"])] = (path, data)
    return out


def _doc(artifact_id: str) -> dict:
    assert artifact_id in CORPUS, f"{artifact_id} is referenced and not authored"
    return CORPUS[artifact_id][1]


def _unit_files() -> list[Path]:
    """Every file this capability is made of: its folder, the knowledge it lists, the objects it loads."""
    files = sorted(CAP_DIR.rglob("*.yaml"))
    for artifact_id in _playbook_ids() + _heuristic_ids() + _object_ids():
        files.append(CORPUS[artifact_id][0])
    return sorted(set(files))


def _authored_documents() -> list[tuple[Path, dict]]:
    """The documents that carry identity and metadata — everything but the two manifests."""
    return [(p, _load(p)) for p in _unit_files() if p.name not in ("objects.yaml", "knowledge.yaml")]


@pytest.fixture(scope="module")
def validators():
    sys.path.insert(0, str(TOOLS))
    try:
        import validate
        return validate.build_validators()
    finally:
        sys.path.remove(str(TOOLS))


def _schema_kind(path: Path) -> str:
    if path.name == "capability.yaml":
        return "capability"
    if path.name == "objects.yaml":
        return "capability_objects"
    if path.name == "knowledge.yaml":
        return "capability_knowledge"
    rel = path.relative_to(ROOT).parts
    if "situations" in rel:
        return "situation"
    return "object" if rel[0] == "objects" else "artifact"


# ── the capability is authored, and nobody has admitted it ─────────────────────────────────────

def test_the_capability_is_authored_draft_unreviewed_and_unadmitted():
    cap = _load(CAP_DIR / "capability.yaml")
    ident, meta = cap["identity"], cap["metadata"]
    assert ident["id"] == CAPABILITY
    assert ident.get("stub") is False, "still a stub: nothing compiles through it"
    assert ident["status"] == "draft"
    assert (meta["review_status"], meta["reviewed_by"], meta["created_by"],
            meta["last_updated"]) == ("unreviewed", "", "ai", "2026-10-09")
    assert "admission" not in cap, "only the founder's review admits (`06` D45)"
    assert 4 <= len(cap.get("outcomes") or []) <= 6
    assert 4 <= len(cap.get("failure_modes") or []) <= 6
    assert cap.get("kpis"), "a capability with no measure is not being run"


def test_it_keeps_programmes_apart_and_hands_off_only_inside_its_domain():
    cap = _load(CAP_DIR / "capability.yaml")
    assert any("founder_office.programs_and_applications.program_applications" in o
               for o in cap["outcomes"]), "programme conversations must be handed to their own capability"
    handoffs = [c for side in (cap.get("handoffs") or {}).values() for c in side]
    assert handoffs and all(c.startswith("founder_office.") for c in handoffs), handoffs


def test_every_document_is_a_draft_nobody_has_reviewed_or_admitted():
    for path, doc in _authored_documents():
        ident, meta = doc["identity"], doc["metadata"]
        where = path.relative_to(ROOT)
        assert ident["status"] == "draft", where
        assert meta["review_status"] == "unreviewed", where
        assert meta.get("reviewed_by") == "", where
        assert meta.get("created_by") == "ai", where
        assert meta.get("last_updated") == "2026-10-09", where
        assert "admission" not in doc, f"{where} carries an admission block"


def test_every_file_passes_the_corpus_own_schema(validators):
    for path in _unit_files():
        errors = [e.message for e in validators[_schema_kind(path)].iter_errors(_load(path))]
        assert errors == [], f"{path.relative_to(ROOT)}: {errors[:3]}"


def test_the_knowledge_belongs_to_this_capability():
    for artifact_id in _playbook_ids() + _heuristic_ids():
        ident = _doc(artifact_id)["identity"]
        assert ident["owner_capability"] == CAPABILITY, artifact_id
        assert ident["scope"] == "capability", artifact_id
    assert all(i.startswith("founder_office.pb.investor_relations.") for i in _playbook_ids())
    assert all(i.startswith("founder_office.heu.investor_relations.") for i in _heuristic_ids())


# ── the spine: one playbook declares the stages ────────────────────────────────────────────────

def test_exactly_one_playbook_declares_the_stages():
    staged = [i for i in _playbook_ids() if "stages" in _doc(i)]
    assert staged == [SPINE], f"the closed list must live in one playbook, found {staged}"


def test_the_stages_are_the_closed_list_each_with_a_sourced_prior():
    stages = _doc(SPINE)["stages"]
    assert tuple(s["name"] for s in stages) == STAGES
    for stage in stages:
        name = stage["name"]
        prior = stage["typical_duration_days"]
        assert isinstance(prior, int) and not isinstance(prior, bool), name
        assert str(stage.get("label") or "").strip(), f"{name} has no label"
        assert len(str(stage.get("source") or "").strip()) > 10, f"{name}'s prior names no source"
        assert str(stage.get("quiet_means") or "").strip(), f"{name} does not say what quiet means"
        assert str(stage.get("leaves_when") or "").strip(), f"{name} does not say what ends it"
        if name in TERMINAL:
            assert "terminal" in stage["leaves_when"].lower(), f"{name} is terminal and must say so"
        else:
            assert prior > 0, f"{name} is a stage a conversation moves through; its prior cannot be 0"


def test_the_spine_says_what_success_waiting_and_doing_nothing_mean():
    spine = _doc(SPINE)
    assert str(spine.get("success_signal") or "").strip()
    assert isinstance(spine.get("outcome_window_days"), int) and spine["outcome_window_days"] >= 1
    assert str(spine.get("do_nothing_consequence") or "").strip()
    assert spine["steps"] and all(str(s.get("done_when") or "").strip() for s in spine["steps"])


def test_the_spine_says_when_a_quiet_investor_file_is_dormant():
    """`06` D33 moved dormancy into the playbooks: an investor file is dormant, not waiting, after the
    spine's own number of quiet days — a prior with its source — and `then` says what a professional
    does with it. Never sooner than the outcome window, and never inside a stage a conversation is
    still typically in: a file is not dormant while a typical deal, or the stage it sits in, may still
    be running."""
    spine = _doc(SPINE)
    stop = spine.get("stop")
    assert isinstance(stop, dict), "the spine declares no stop rule"
    days = stop.get("dormant_after_days")
    assert type(days) is int and days >= 1, f"dormant_after_days is not whole days: {days!r}"
    for field in ("source", "then"):
        assert len(str(stop.get(field) or "").strip()) > 40, f"the stop rule has no real {field}"
    assert days >= spine["outcome_window_days"], (
        f"dormant after {days} quiet days, inside the {spine['outcome_window_days']}-day outcome window")
    live = [s for s in spine["stages"] if s["name"] not in TERMINAL]
    assert all(days > s["typical_duration_days"] for s in live), (
        f"dormant after {days} quiet days, inside a stage that typically lasts longer")


def test_no_move_says_when_to_stop():
    """One kind of work, one stop rule — the spine's. A move is a play made inside the work."""
    for move in MOVES:
        assert "stop" not in _doc(move), f"{move} declares a stop rule"


def test_the_reader_hands_the_expert_the_stop_rule_as_a_prior():
    """What STEP-12's expert reads (`playbook_for`, over the shipped corpus): the number as a
    `playbook_prior` resting on no observation of this founder (n = 0) — never a measurement, never
    normal (`06` D37) — with its source and its words."""
    from genios_engine.contracts.measured import PLAYBOOK_PRIOR
    from genios_engine.packs.compiler.playbook_reader import playbook_for

    stop = _doc(SPINE)["stop"]
    answer = playbook_for("investor")
    assert answer.reason is None and answer.playbook.playbook_id == SPINE
    rule = answer.playbook.stop
    assert rule is not None, "the reader found no stop rule on the spine"
    assert rule.dormant_after.source == PLAYBOOK_PRIOR == "playbook_prior"
    assert (rule.dormant_after.value, rule.dormant_after.n, rule.dormant_after.unit) == (
        stop["dormant_after_days"], 0, "days")
    assert not rule.dormant_after.normal
    assert rule.dormant_after.says().endswith("a playbook's prior, not measured here")
    assert rule.cited == " ".join(stop["source"].split())
    assert rule.then == " ".join(stop["then"].split())


def test_the_object_reads_dormancy_from_the_spine():
    """The scoped object names no dormancy clock of its own: its `dormant` state defers to the spine's
    stop rule, so the two cannot disagree about when an investor file is dormant."""
    obj = _doc("founder_office.obj.investor_relations.investor_conversation")
    [dormant] = [v for v in obj["states"]["values"] if v["name"] == "dormant"]
    assert "stop rule" in dormant["description"]
    assert "entered_when" not in dormant, "a predicate here would be a second dormancy clock"


def test_the_object_holds_the_spine_s_stages():
    """The scoped object and the spine name one stage model; `unknown` is the honest default."""
    obj = _doc("founder_office.obj.investor_relations.investor_conversation")
    [stage] = [a for a in obj["attributes"] if a["name"] == "stage"]
    assert stage["allowed_values"] == [*STAGES, "unknown"]
    assert stage.get("default") == "unknown"


# ── the moves ──────────────────────────────────────────────────────────────────────────────────

def test_the_moves_are_all_here():
    assert set(_playbook_ids()) == MOVES | {SPINE}


@pytest.mark.parametrize("move", sorted(MOVES))
def test_every_move_has_steps_a_success_signal_and_a_window(move):
    doc = _doc(move)
    assert "stages" not in doc, f"{move} is a move, not the spine"
    assert doc["steps"], move
    for step in doc["steps"]:
        assert str(step.get("done_when") or "").strip(), f"{move} step {step['order']} is a wish"
    assert str(doc.get("success_signal") or "").strip(), move
    window = doc.get("outcome_window_days")
    assert isinstance(window, int) and not isinstance(window, bool) and window >= 1, move


@pytest.mark.parametrize("playbook", sorted(MOVES | {SPINE}))
def test_every_window_names_its_source(playbook):
    """A window is a prior like a stage's duration. The schema gives it no `source` field, so the
    playbook's references carry it: one reference whose note names `outcome_window_days`."""
    notes = [str(r.get("note") or "") for r in _doc(playbook).get("references") or []]
    sourced = [n for n in notes if "outcome_window_days" in n]
    assert sourced and all(len(n) > 40 for n in sourced), (
        f"{playbook} waits {_doc(playbook)['outcome_window_days']} days on nobody's authority")


# ── the heuristics ─────────────────────────────────────────────────────────────────────────────

def test_the_heuristics_are_claims_with_reasons():
    ids = set(_heuristic_ids())
    assert MOVED_HEURISTICS <= ids, "a moved heuristic was dropped"
    assert len(ids) > len(MOVED_HEURISTICS), "the moves rest on more than the two Sales carried"
    for heuristic_id in ids:
        claim = _doc(heuristic_id)["heuristic"]
        for field in ("statement", "why", "breaks_down_when"):
            assert str(claim.get(field) or "").strip(), f"{heuristic_id} has no {field}"


# ── the situations: moved, re-identified, routed exactly as before ────────────────────────────

def test_the_two_situations_bind_exactly_as_sales_did():
    situations = _situation_files()
    assert set(situations) == set(SALES_MATCHES)
    for sid, (_path, doc) in situations.items():
        assert doc["matches"] == SALES_MATCHES[sid], f"{sid} would route differently"
        assert doc["identity"]["owner_capability"] == CAPABILITY


def test_each_situation_says_what_doing_nothing_costs_and_loads_founder_objects_only():
    for sid, (_path, doc) in _situation_files().items():
        assert str(doc.get("do_nothing_consequence") or "").strip(), sid
        loaded = [o for key in ("load", "optional", "never_load")
                  for o in (doc["objects"].get(key) or [])]
        assert loaded and all(o.startswith("founder_office.obj.") for o in loaded), (sid, loaded)
        assert all(o in CORPUS for o in loaded), sid
        assert not doc.get("also_serves"), f"{sid} reaches outside the capability: {doc['also_serves']}"


def test_the_load_set_is_founder_objects_and_all_authored():
    ids = _object_ids()
    assert "founder_office.obj.core.company" in _objects_manifest()["core"]["required"]
    assert ("founder_office.obj.investor_relations.investor_conversation"
            in _objects_manifest()["scoped"]["required"])
    assert "founder_office.obj.core.contact" in ids
    assert all(i.startswith("founder_office.obj.") and i in CORPUS for i in ids), ids


# ── the registry routes it, and nothing defers it ──────────────────────────────────────────────

def test_the_registry_routes_both_types_here_and_the_deferral_is_gone():
    registry = _load(ROOT / "registry" / "situation-capability-map.yaml")
    for situation_type, sid in (("investor_relationship", "founder_office.sit.live_investor_relationship"),
                                ("investor_contact", "founder_office.sit.live_investor_contact")):
        route = (registry.get("map") or {}).get(situation_type)
        assert route, f"{situation_type} does not route to the Founder Office"
        assert route["situations"] == [sid]
        assert route["capabilities"] == [CAPABILITY]
    assert CAPABILITY not in (registry.get("deferred_capabilities") or {})
    deferred = {d["capability"] for d in _load(ROOT / "deferrals.yaml")["deferred"]}
    assert CAPABILITY not in deferred, "it routes now; a deferral would suppress both situations"


# ── what the text may not say ──────────────────────────────────────────────────────────────────

def test_no_sales_id_is_referenced_anywhere_in_the_founder_office_corpus():
    """A cross-domain reference cannot resolve. Every id-shaped VALUE in the corpus is checked; the
    prose of this capability's own files is checked too, so the old ids are not even remembered."""
    def values(node):
        if isinstance(node, dict):
            for v in node.values():
                yield from values(v)
        elif isinstance(node, list):
            for v in node:
                yield from values(v)
        elif isinstance(node, str):
            yield node

    for path in sorted(ROOT.rglob("*.yaml")):
        for value in values(yaml.safe_load(path.read_text())):
            assert not re.fullmatch(r"sales(\.[a-z0-9_]+){2,}", value.strip()), (
                f"{path.relative_to(ROOT)} references {value}")
    for path in _unit_files():
        found = _SALES_ID.findall(path.read_text())
        assert not found, f"{path.relative_to(ROOT)} names {found}"


def test_no_prior_is_called_normal():
    for path in _unit_files():
        found = _NORMAL.findall(path.read_text())
        assert not found, f"{path.relative_to(ROOT)} calls something normal (`06` D37)"


def test_the_corpus_validates_with_no_errors():
    result = subprocess.run([sys.executable, str(TOOLS / "validate.py")], capture_output=True,
                            text=True, cwd=str(REPO))
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1000:]
    assert re.search(r"^0 error\(s\)", result.stdout, re.MULTILINE), result.stdout[-1500:]
