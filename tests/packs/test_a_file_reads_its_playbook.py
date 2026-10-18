"""STEP-11 · a file reads its kind's playbook — stages, moves, claims, do-nothing, stop, review state.

    .venv/bin/python -m pytest tests/packs/test_a_file_reads_its_playbook.py -q

Tree `yc2_w27_s11 · M30.C5.L-logic.V2.U01`, STEP-11 §8.4 (8). `packs/compiler/playbook_reader.
playbook_for(kind)` is the read model STEP-12's dossier calls per file: the kind's SPINE playbook (the
one of its capability's playbooks that declares `stages`), each stage's typical duration as a labelled
prior, the other playbooks as moves, the heuristics as claims, what doing nothing costs, when the work
is dormant, and whether a named human reviewed it — D3's "playbook not yet reviewed" when not. A kind
with nothing authored answers with the reason, never with a borrowed playbook.

Built against a small Founder Office corpus written by the test, so the read model is pinned before
the real playbooks are reviewed; `test_every_kind_of_work_has_an_answer` reads the shipped corpus.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from genios_engine.contracts.company_brief import WORK_KINDS
from genios_engine.contracts.measured import PLAYBOOK_PRIOR
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
from genios_engine.packs.compiler import playbook_reader as R

CAP = "founder_office.programs_and_applications.program_applications"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _corpus(tmp_path: Path, *, spine_reviewed: bool = False, second_spine: bool = False,
            stub: bool = False, oddities: bool = False) -> ExpertBrainCatalog:
    root = tmp_path / "Domain Expertise"
    dom = root / "Founder Office Expertise"
    _write(dom / "domain.yaml", "identity: {id: founder_office, name: Founder Office, "
                                "version: 1.0.0, status: draft}\n")
    _write(dom / "registry/situation-capability-map.yaml", "domain: Founder Office Expertise\nmap: {}\n")
    cap = dom / "capabilities/02-programs-and-applications/program-applications"
    _write(cap / "capability.yaml", f"""
identity: {{id: {CAP}, name: Program Applications, domain: founder_office,
            subdomain: programs_and_applications, version: 0.1.0, status: draft, stub: {str(stub).lower()}}}
description: Applications to programmes, from submission to onboarding.
question: Where does this application stand?
""")
    _write(cap / "objects.yaml", f"capability: {CAP}\ncore: {{required: [], optional: []}}\n"
                                 "scoped: {required: [], optional: []}\n")
    spines = ["founder_office.pb.program_applications.follow_an_application"]
    if second_spine:
        spines.append("founder_office.pb.program_applications.another_spine")
    pbs = spines + ["founder_office.pb.program_applications.prepare_the_interview"]
    heus = ["founder_office.heu.program_applications.a_batch_is_silent"]
    if oddities:
        pbs.append("founder_office.pb.program_applications.a_zero_day_wait")
        heus.append("founder_office.heu.program_applications.a_claim_with_no_words")
        heus.append("founder_office.heu.program_applications.never_written")
    _write(cap / "knowledge.yaml", f"""
capability: {CAP}
playbooks: {{core: [], scoped: [{', '.join(pbs)}]}}
heuristics: {{core: [], scoped: [{', '.join(heus)}]}}
mental_models: {{core: [], scoped: []}}
rules: {{core: [], scoped: []}}
decision_frameworks: {{core: [], scoped: []}}
""")
    status, review, who = (("stable", "approved", "rohit") if spine_reviewed
                           else ("draft", "unreviewed", ""))
    for pid in spines:
        _write(dom / f"playbooks/program_applications/{pid.rsplit('.', 1)[1]}.yaml", f"""
identity: {{id: {pid}, name: Follow an application, kind: playbook, domain: founder_office,
            scope: capability, owner_capability: {CAP}, version: 0.1.0, status: {status}}}
purpose: {{statement: Carry an application from submission to a decision.}}
when_to_use: {{signals: [An application was submitted.]}}
steps:
  - {{order: 1, name: Note the decision date, done_when: The date is on file.}}
stages:
  - {{name: applied, label: Applied, typical_duration_days: 21, quiet_means: Batches decide together.,
      leaves_when: An interview invitation arrives., source: "https://www.ycombinator.com/apply"}}
  - {{name: interview, typical_duration_days: 7, source: a named reference}}
success_signal: The programme's decision mail arrives.
outcome_window_days: 30
do_nothing_consequence: The cohort fills and the next intake is six months away.
stop: {{dormant_after_days: 90, source: practitioner judgement — unverified, then: Reapply next cycle.}}
metadata: {{owner: Founder Office, last_updated: "2026-10-09", review_status: {review}, reviewed_by: "{who}"}}
""")
    _write(dom / "playbooks/program_applications/prepare_the_interview.yaml", f"""
identity: {{id: founder_office.pb.program_applications.prepare_the_interview, name: Prepare the interview,
            kind: playbook, domain: founder_office, scope: capability, owner_capability: {CAP},
            version: 0.1.0, status: draft}}
purpose: {{statement: Walk into a programme's interview with the three answers it tests.}}
when_to_use: {{signals: [An interview was offered.]}}
steps:
  - {{order: 1, name: Confirm who joins, done_when: Names are on file.}}
  - {{order: 2, name: Rehearse the ten-minute version, description: Rehearse the ten-minute version twice.}}
success_signal: The interview happens with every founder present.
outcome_window_days: 7
metadata: {{owner: Founder Office, last_updated: "2026-10-09", review_status: unreviewed}}
""")
    _write(dom / "heuristics/program_applications/a-batch-is-silent.yaml", f"""
identity: {{id: founder_office.heu.program_applications.a_batch_is_silent, name: A batch is silent,
            kind: heuristic, domain: founder_office, scope: capability, owner_capability: {CAP},
            version: 0.1.0, status: draft}}
purpose: {{statement: Why a programme's silence in review is not a no.}}
heuristic: {{statement: A programme that reviews in batches is silent until the batch decides.,
             why: Reviewers read a cohort together.}}
metadata: {{owner: Founder Office, last_updated: "2026-10-09", review_status: unreviewed}}
""")
    if oddities:
        _write(dom / "playbooks/program_applications/a-zero-day-wait.yaml", f"""
identity: {{id: founder_office.pb.program_applications.a_zero_day_wait, name: A zero-day wait,
            kind: playbook, domain: founder_office, scope: capability, owner_capability: {CAP},
            version: 0.1.0, status: draft}}
purpose: {{statement: A move whose window and success the contract cannot hold.}}
when_to_use: {{signals: [Never.]}}
steps:
  - {{order: 1, name: Wait}}
success_signal: "   "
outcome_window_days: 0
metadata: {{owner: Founder Office, last_updated: "2026-10-09", review_status: unreviewed}}
""")
        _write(dom / "heuristics/program_applications/a-claim-with-no-words.yaml", f"""
identity: {{id: founder_office.heu.program_applications.a_claim_with_no_words, name: No words,
            kind: heuristic, domain: founder_office, scope: capability, owner_capability: {CAP},
            version: 0.1.0, status: draft}}
purpose: {{statement: A heuristic file whose claim was never written.}}
heuristic: {{statement: "", why: Nothing.}}
metadata: {{owner: Founder Office, last_updated: "2026-10-09", review_status: unreviewed}}
""")
    return ExpertBrainCatalog(root)


def test_a_program_file_reads_its_spine_moves_and_claims(tmp_path):
    answer = R.playbook_for("program", catalog=_corpus(tmp_path))
    assert answer.reason is None
    pb = answer.playbook
    assert (pb.kind, pb.capability_id, pb.playbook_id) == (
        "program", CAP, "founder_office.pb.program_applications.follow_an_application")
    assert [s.name for s in pb.stages] == ["applied", "interview"]
    assert pb.stages[0].typical.source == PLAYBOOK_PRIOR and pb.stages[0].typical.normal is False
    assert pb.stages[0].cited == "https://www.ycombinator.com/apply"
    assert (pb.success_signal, pb.outcome_window_days) == ("The programme's decision mail arrives.", 30)
    assert pb.do_nothing_consequence == "The cohort fills and the next intake is six months away."
    [move] = pb.moves
    assert move.name == "Prepare the interview"
    assert move.steps == ("Confirm who joins", "Rehearse the ten-minute version twice.")
    assert (move.success_signal, move.outcome_window_days) == (
        "The interview happens with every founder present.", 7)
    [claim] = pb.claims
    assert claim.statement.startswith("A programme that reviews in batches")
    assert claim.why == "Reviewers read a cohort together."


def test_the_stop_rule_is_a_prior_with_its_source(tmp_path):
    stop = R.playbook_for("program", catalog=_corpus(tmp_path)).playbook.stop
    assert (stop.dormant_after.value, stop.dormant_after.source, stop.dormant_after.n) == (
        90, PLAYBOOK_PRIOR, 0)
    assert stop.cited.startswith("practitioner judgement")
    assert stop.then == "Reapply next cycle."


def test_unreviewed_says_so_in_d3_s_words(tmp_path):
    pb = R.playbook_for("program", catalog=_corpus(tmp_path)).playbook
    assert (pb.reviewed, pb.review_label) == (False, "playbook not yet reviewed")


def test_a_reviewed_spine_on_an_unadmitted_capability_is_still_unreviewed(tmp_path):
    """Both halves of the ceremony: the capability admitted AND the spine reviewed by a named human."""
    pb = R.playbook_for("program", catalog=_corpus(tmp_path, spine_reviewed=True)).playbook
    assert pb.reviewed is False and pb.review_label == R.REVIEW_LABEL


@pytest.mark.parametrize("kind, reason", [(None, R.NO_KIND), ("", R.NO_KIND),
                                          ("clinic", R.UNKNOWN_KIND),
                                          ("partner", R.NO_CAPABILITY),
                                          ("intro", R.NOT_AUTHORED)])
def test_a_kind_with_nothing_to_read_says_why(tmp_path, kind, reason):
    answer = R.playbook_for(kind, catalog=_corpus(tmp_path))
    assert (answer.playbook, answer.reason) == (None, reason)


def test_a_stub_capability_is_not_read(tmp_path):
    assert R.playbook_for("program", catalog=_corpus(tmp_path, stub=True)).reason == R.NOT_AUTHORED


def test_two_spines_are_refused_not_chosen_between(tmp_path):
    answer = R.playbook_for("program", catalog=_corpus(tmp_path, second_spine=True))
    assert (answer.playbook, answer.reason) == (None, R.SEVERAL_SPINES)


def test_the_kinds_are_the_brief_s_kinds():
    """D31's list lives in the brief's contract; this map may not drift from it."""
    assert tuple(R.KIND_CAPABILITY) == WORK_KINDS


def test_every_mapped_capability_is_declared_by_its_own_domain():
    """A capability id names its domain first: `founder_office.…` the Founder Office's, `admin.…` Admin's."""
    import yaml
    from genios_engine.packs.compiler.authoring import default_authoring_root
    declared = set()
    for folder in ("Founder Office Expertise", "Admin Expertise"):
        doc = yaml.safe_load((default_authoring_root() / folder / "domain.yaml").read_text())
        domain = doc["identity"]["id"]
        declared |= {f"{domain}.{s['id']}.{c}" for s in doc["subdomains"] for c in s["capabilities"]}
    assert {c for c in R.KIND_CAPABILITY.values() if c} <= declared


def test_a_vendor_file_reads_admin_s_renewal_management():
    """`09` G5 / `06` D18: a vendor's renewal is Admin's work, not the Founder Office's. On the shipped
    corpus the capability is authored and none of its playbooks declares stages yet — so a vendor file
    reads no spine, and the answer says exactly that (an authoring step, never a borrowed playbook)."""
    assert R.KIND_CAPABILITY["vendor"] == "admin.contract_and_vendor.renewal_management"
    answer = R.playbook_for("vendor")
    assert (answer.playbook, answer.reason) == (None, R.NO_SPINE)


def test_a_kind_reads_its_capability_in_that_capability_s_own_domain(tmp_path):
    """The lookup follows the capability id's domain: an Admin capability with a staged playbook is read."""
    _corpus(tmp_path)                    # the Founder Office beside it, as the shipped root has
    dom = tmp_path / "Domain Expertise" / "Admin Expertise"
    cap_id = "admin.contract_and_vendor.renewal_management"
    _write(dom / "domain.yaml", "identity: {id: admin, name: Admin, version: 1.0.0, status: draft}\n")
    _write(dom / "registry/situation-capability-map.yaml", "domain: Admin Expertise\nmap: {}\n")
    cap = dom / "capabilities/05-contract-and-vendor-administration/renewal-management"
    _write(cap / "capability.yaml", f"""
identity: {{id: {cap_id}, name: Renewal Management, domain: admin, subdomain: contract_and_vendor,
            version: 0.1.0, status: draft, stub: false}}
description: Deciding each renewal before its notice date.
question: Do we still want it, at this price?
""")
    _write(cap / "objects.yaml", f"capability: {cap_id}\ncore: {{required: [], optional: []}}\n"
                                 "scoped: {required: [], optional: []}\n")
    pid = "admin.pb.renewal_management.renewals_as_annual_re_decisions"
    _write(cap / "knowledge.yaml", f"""
capability: {cap_id}
playbooks: {{core: [], scoped: [{pid}]}}
heuristics: {{core: [], scoped: []}}
mental_models: {{core: [], scoped: []}}
rules: {{core: [], scoped: []}}
decision_frameworks: {{core: [], scoped: []}}
""")
    _write(dom / "playbooks/renewal_management/renewals-as-annual-re-decisions.yaml", f"""
identity: {{id: {pid}, name: Renewals as annual re-decisions, kind: playbook, domain: admin,
            scope: capability, owner_capability: {cap_id}, version: 0.1.0, status: draft}}
purpose: {{statement: Decide each renewal before its notice date.}}
when_to_use: {{signals: [A renewal notice arrived.]}}
steps:
  - {{order: 1, name: Check usage before the notice date, done_when: Usage is on file.}}
stages:
  - {{name: notice_received, typical_duration_days: 14, source: a named reference}}
success_signal: The renewal is decided before its date.
outcome_window_days: 30
metadata: {{owner: Admin, last_updated: "2026-10-10", review_status: unreviewed}}
""")
    answer = R.playbook_for("vendor", catalog=ExpertBrainCatalog(tmp_path / "Domain Expertise"))
    assert answer.reason is None and answer.playbook.capability_id == cap_id
    assert answer.playbook.playbook_id == pid


def test_every_kind_of_work_has_an_answer_on_the_shipped_corpus():
    """Not a playbook for every kind — an ANSWER: the playbook, or the reason there is none."""
    for kind in WORK_KINDS:
        answer = R.playbook_for(kind)
        assert (answer.playbook is None) == (answer.reason is not None), kind


def test_the_read_model_shape_is_plain_data(tmp_path):
    import json
    shape = R.playbook_for("program", catalog=_corpus(tmp_path)).as_dict()
    assert json.loads(json.dumps(shape)) == shape
    assert shape["playbook"]["stages"][0]["typical"]["says"] == \
        "21 days — a playbook's prior, not measured here"


def test_what_the_contract_cannot_hold_is_read_as_unsaid(tmp_path):
    """A zero-day window and a blank success are no window and no success; a heuristic with no
    words, or listed and never written, is no claim — none of them reaches the expert as if said."""
    pb = R.playbook_for("program", catalog=_corpus(tmp_path, oddities=True)).playbook
    [odd] = [m for m in pb.moves if m.artifact_id.endswith("a_zero_day_wait")]
    assert (odd.outcome_window_days, odd.success_signal) == (None, None)
    assert [c.artifact_id.rsplit(".", 1)[1] for c in pb.claims] == ["a_batch_is_silent"]
