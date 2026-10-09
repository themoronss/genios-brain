r"""Plane D `G5` · the corpus is judged on cases, half of which it must REFUSE to answer.

⛔ WHY THIS EXISTS. Before it, *"the expertise is correct"* was a claim with nothing under it. The
corpus validates with 0 errors, every capability is admitted, every object is authored and reachable
— and **none of that is evidence that the expertise gives the right answer.** A schema check proves
a file is well-formed; it cannot prove a situation routes where a professional would look.

⛔ AND HALF THE CASES ARE MUST-ABSTAIN. A corpus evaluated only on what it should answer gets tuned
until it answers everything. The expensive failures here are not wrong answers — they are confident
answers to questions the evidence could not settle, which is what the abstention vocabulary, the
admission ceremony and the `unrouted_l2_types` census all exist to prevent. **A case expecting
`abstain` that resolves is a worse failure than the reverse.**

Deterministic and model-free: every case is decided by the routing data and the admission gates.
Under the API spend limit that is not a limitation, it is the only kind of evaluation that can run.
"""
from __future__ import annotations

import pathlib

import pytest
import yaml

from genios_engine.packs.compiler.capability_resolver import situation_admission_reason

REPO = pathlib.Path(__file__).resolve().parents[2]
CORPUS = REPO / "Domain Expertise"
EVAL = CORPUS / "_eval"


def _cases():
    out = []
    for f in sorted(EVAL.glob("*.cases.yaml")):
        doc = yaml.safe_load(f.read_text()) or {}
        for case in (doc.get("cases") or []):
            out.append((doc.get("domain"), case))
    return out


ALL = _cases()
BY_ID = {c["id"]: (d, c) for d, c in ALL}


def _bound_types() -> dict[str, set[str]]:
    """L2 situation type -> the domains whose situations bind it. Read from the corpus, not a map."""
    bound: dict[str, set[str]] = {}
    for dom in sorted(CORPUS.glob("* Expertise")):
        name = dom.name.replace(" Expertise", "").lower().replace(" ", "_")
        for sit in dom.glob("capabilities/*/*/situations/*.yaml"):
            doc = yaml.safe_load(sit.read_text()) or {}
            for t in ((doc.get("matches") or {}).get("l2_situation_types") or []):
                bound.setdefault(str(t), set()).add(name)
    return bound


def _corpus_domains() -> set[str]:
    return {d.name.replace(" Expertise", "").lower().replace(" ", "_")
            for d in CORPUS.glob("* Expertise")}


# ── the file itself is held to a standard ─────────────────────────────────────────────────────

def test_there_are_cases_at_all():
    assert len(ALL) >= 15, f"only {len(ALL)} cases — this is a floor, not coverage"


def test_at_least_half_the_cases_are_must_abstain():
    """⛔ THE DESIGN CONSTRAINT, ASSERTED. A suite that drifts towards answer-cases is a suite being
    tuned to answer everything, and the drift is invisible one case at a time."""
    abstain = sum(1 for _, c in ALL if c.get("expect") == "abstain")
    assert abstain * 2 >= len(ALL), f"{abstain} abstain of {len(ALL)} — the balance has drifted"


@pytest.mark.parametrize("case_id", sorted(BY_ID))
def test_every_case_states_why_it_is_a_case(case_id):
    """⛔ A case with no reason is a regression test for CURRENT behaviour rather than an assertion
    about CORRECT behaviour, and the two diverge the first time current behaviour is wrong."""
    _, case = BY_ID[case_id]
    why = " ".join(str(case.get("why") or "").split())
    assert len(why) >= 40, f"{case_id}: {why!r}"


@pytest.mark.parametrize("case_id", sorted(BY_ID))
def test_every_case_declares_one_of_the_two_expectations(case_id):
    _, case = BY_ID[case_id]
    assert case.get("expect") in ("resolve", "abstain")
    if case["expect"] == "abstain":
        assert case.get("reason"), f"{case_id}: an abstention with no named reason is a shrug"


def test_case_ids_are_unique():
    assert len(BY_ID) == len(ALL)


# ── the resolve cases ─────────────────────────────────────────────────────────────────────────

RESOLVE = [(d, c) for d, c in ALL if c.get("expect") == "resolve" and c.get("situation_type")]


@pytest.mark.parametrize("domain,case", RESOLVE, ids=lambda x: x if isinstance(x, str) else x["id"])
def test_a_situation_that_must_route_is_bound_by_some_situation(domain, case):
    bound = _bound_types()
    stype = case["situation_type"]
    assert stype in bound, (
        f"{case['id']}: nothing in any domain binds {stype!r} — the corpus is disconnected from the "
        f"substrate for this type. {case.get('why')}")
    hints = {h.lower() for h in (case.get("domain_hints") or [])}
    if hints:
        assert bound[stype] & hints, (
            f"{case['id']}: {stype!r} is bound by {sorted(bound[stype])}, none of which is a hinted "
            f"domain {sorted(hints)}")


# ── the abstain cases, which matter more ──────────────────────────────────────────────────────

ABSTAIN_TYPE = [(d, c) for d, c in ALL
                if c.get("expect") == "abstain" and c.get("reason") == "no_situation_binds_type"]


@pytest.mark.parametrize("domain,case", ABSTAIN_TYPE,
                         ids=lambda x: x if isinstance(x, str) else x["id"])
def test_a_type_that_must_abstain_is_bound_by_nothing(domain, case):
    """⛔ THE WORSE FAILURE DIRECTION. If one of these starts resolving, somebody widened a route to
    catch it — which is how an unowned situation type acquires an owner nobody chose."""
    bound = _bound_types()
    stype = case["situation_type"]
    assert stype not in bound, (
        f"{case['id']}: {stype!r} is now bound by {sorted(bound.get(stype, ()))}. If that is "
        f"deliberate, delete this case and say so; if it is not, a route was widened past its "
        f"subject. {case.get('why')}")


ABSTAIN_HINT = [(d, c) for d, c in ALL
                if c.get("expect") == "abstain" and c.get("reason") == "unknown_domain_hint"]


@pytest.mark.parametrize("domain,case", ABSTAIN_HINT,
                         ids=lambda x: x if isinstance(x, str) else x["id"])
def test_a_hint_naming_no_corpus_stays_unknown(domain, case):
    """The refusal must be attributable to the HINT, because a hint nobody owns and a type nobody
    authored are fixed by different people."""
    hints = {h.lower() for h in (case.get("domain_hints") or [])}
    assert hints and not (hints & _corpus_domains()), (
        f"{case['id']}: {sorted(hints)} now names a real corpus. {case.get('why')}")


# ── admission: a draft situation may not instruct ─────────────────────────────────────────────

def _situations() -> dict[str, dict]:
    out = {}
    for dom in CORPUS.glob("* Expertise"):
        for f in dom.glob("capabilities/*/*/situations/*.yaml"):
            doc = yaml.safe_load(f.read_text()) or {}
            sid = (doc.get("identity") or {}).get("id")
            if sid:
                out[str(sid)] = doc
    return out


ADMISSION = [c for _, c in ALL if c.get("kind") == "admission"]


@pytest.mark.parametrize("case", ADMISSION, ids=lambda c: c["id"])
def test_a_named_draft_situation_cannot_instruct(case):
    doc = _situations().get(case["situation_id"])
    assert doc is not None, f"{case['id']}: {case['situation_id']} no longer exists"
    assert situation_admission_reason(doc) == case["reason"], case.get("why")


def test_no_draft_situation_anywhere_may_instruct():
    """⛔ The same claim over the whole corpus, so a newly drafted situation cannot acquire the
    authority to instruct by being added after the single-file case was written."""
    offenders = [sid for sid, doc in _situations().items()
                 if str((doc.get("identity") or {}).get("status")) == "draft"
                 and situation_admission_reason(doc) is None]
    assert offenders == [], offenders


# ── deferral: structural, not a label ─────────────────────────────────────────────────────────

def _deferred(domain_dir: pathlib.Path) -> set[str]:
    path = domain_dir / "deferrals.yaml"
    if not path.is_file():
        return set()
    doc = yaml.safe_load(path.read_text()) or {}
    return {str(e["capability"]) for e in (doc.get("deferred") or []) if e.get("capability")}


def _routed(domain_dir: pathlib.Path) -> set[str]:
    reg = yaml.safe_load((domain_dir / "registry/situation-capability-map.yaml").read_text()) or {}
    text = yaml.safe_dump(reg)
    return {line.strip("- ").strip() for line in text.splitlines() if ".cap." in line}


def test_every_deferred_capability_is_absent_from_its_generated_map():
    """⛔ `deferrals.yaml` CLAIMS a deferral is structural — the capability appears in no route and
    its situations are suppressed. That is a claim about the GENERATOR, and nothing checked it. A
    deferred capability still routable means unreviewed expertise reaching a reader through a door
    somebody believed they had closed."""
    bad = []
    for dom in sorted(CORPUS.glob("* Expertise")):
        deferred = _deferred(dom)
        if not deferred:
            continue
        reg_text = (dom / "registry/situation-capability-map.yaml").read_text()
        # ⛔ THE `map:` SECTION ONLY. My first version searched everything before
        # `routed_l2_types:`, which includes the `deferred_capabilities:` block — so it found all 31
        # deferrals listed in the list of deferrals and called each one a routing leak. The test was
        # wrong, not the corpus; recorded because a crude slice that happens to fail looks exactly
        # like a real finding.
        route_map = reg_text.split("\nmap:", 1)[1].split("\ndeferred_capabilities:", 1)[0]
        for cid in sorted(deferred):
            if cid in route_map:
                bad.append(f"{dom.name}: {cid} is deferred and still appears in the route map")
    assert bad == [], bad


def test_a_deferred_capabilitys_situations_are_suppressed():
    """The other half of structural: not merely absent from routes, but its situations removed."""
    bad = []
    for dom in sorted(CORPUS.glob("* Expertise")):
        deferred = _deferred(dom)
        if not deferred:
            continue
        reg_text = (dom / "registry/situation-capability-map.yaml").read_text()
        for f in dom.glob("capabilities/*/*/situations/*.yaml"):
            doc = yaml.safe_load(f.read_text()) or {}
            ident = doc.get("identity") or {}
            if str(ident.get("owner_capability")) in deferred:
                sid = str(ident.get("id"))
                if f"\n  {sid}:" in reg_text:
                    bad.append(f"{dom.name}: {sid} is owned by a deferred capability and still mapped")
    assert bad == [], bad


# ── STEP-11 · a deferral case names ONE capability, and that one is checked ───────────────────

DEFERRAL = [c for _, c in ALL if c.get("kind") == "deferral_is_structural"]


@pytest.mark.parametrize("case", DEFERRAL, ids=lambda c: c["id"])
def test_a_named_deferred_capability_is_deferred_and_unrouted(case):
    """⛔ THESE CASES WERE READ BY NOTHING (`03` F123, found building STEP-11). `kind:
    deferral_is_structural` was declared in a case file and no test took it: the two global tests
    above check every deferral at once, so a case naming ONE capability passed whether or not that
    capability was deferred. Each named capability is now checked by name: listed in its domain's
    `deferrals.yaml`, and absent from its generated route map."""
    cid = case["capability"]
    domain_dir = next((d for d in sorted(CORPUS.glob("* Expertise")) if cid in _deferred(d)), None)
    assert domain_dir is not None, f"{case['id']}: {cid} is in no domain's deferrals.yaml"
    reg_text = (domain_dir / "registry/situation-capability-map.yaml").read_text()
    route_map = reg_text.split("\nmap:", 1)[1].split("\ndeferred_capabilities:", 1)[0]
    assert cid not in route_map, f"{case['id']}: {cid} is deferred and still routed"


# ── STEP-11 · a kind of work reads its playbook, or says why it cannot ────────────────────────

PLAYBOOK = [c for _, c in ALL if c.get("kind") == "playbook"]


@pytest.mark.parametrize("case", PLAYBOOK, ids=lambda c: c["id"])
def test_a_kind_of_work_reads_its_playbook_or_says_why_not(case):
    """`packs/compiler/playbook_reader.playbook_for` is what STEP-12's expert reads for a file of one
    kind of work (STEP-11 §8.4 item 8). A resolve case names what the kind's playbook must hold — its
    spine, stages, moves, claims, authored runtime values, review state; an abstain case the named
    reason there is none. ⛔ Here too the abstention is the case that matters more: one resolving is a
    file of one kind handed a playbook written for another, or for a kind nobody gave."""
    from genios_engine.packs.compiler.playbook_reader import playbook_for

    answer = playbook_for(case.get("work_kind"))
    if case["expect"] == "abstain":
        assert answer.playbook is None, (
            f"{case['id']}: {case.get('work_kind')!r} read {answer.playbook.playbook_id}. "
            f"{case.get('why')}")
        assert answer.reason == case["reason"], f"{case['id']}: {answer.reason!r}"
        return
    playbook = answer.playbook
    assert playbook is not None, f"{case['id']}: no playbook — {answer.reason}. {case.get('why')}"
    if case.get("playbook"):
        assert playbook.playbook_id == case["playbook"], playbook.playbook_id
    missing = {
        "stages": set(case.get("stages_include") or ()) - {s.name for s in playbook.stages},
        "moves": set(case.get("moves_include") or ()) - {m.artifact_id for m in playbook.moves},
        "claims": set(case.get("claims_include") or ()) - {c.artifact_id for c in playbook.claims},
    }
    assert not any(missing.values()), f"{case['id']}: {missing}"
    for field in case.get("authored") or ():
        assert getattr(playbook, field) not in (None, "", ()), f"{case['id']}: {field} unsaid"
    if "reviewed" in case:
        assert playbook.reviewed is case["reviewed"], f"{case['id']}: reviewed={playbook.reviewed}"
        assert (playbook.review_label is None) is case["reviewed"], playbook.review_label
