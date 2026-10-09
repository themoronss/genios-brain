"""STEP-11 · `06` D45 — the founder reviews a playbook line by line, and only then is it admitted.

    .venv/bin/python -m pytest tests/scripts/test_playbook_review_sheet.py -q

Tree `yc2_w27_s11 · M30.C7.L-integration.V2.U02`. `scripts/playbook_review_sheet.py sheet --kind K`
writes one line per thing a professional would have to stand behind — the capability's words, each
playbook's purpose, steps and stages (each prior with its source), success, window, do-nothing and stop,
each heuristic's claim, each situation's sentences — and `apply` admits only when every line says
`accept`: stamps the review on each file and the corpus's own hash (`_tools/admit.py`) on the
capability and its situations. An edit or a reject is listed back and nothing is written; a sheet made
for yesterday's words is refused. Run on a small Founder Office corpus in a temporary root.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "playbook_review_sheet.py"
CAP = "founder_office.programs_and_applications.program_applications"


@pytest.fixture(scope="module")
def tool():
    import sys
    spec = importlib.util.spec_from_file_location("playbook_review_sheet", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module            # a dataclass looks its module up while it is defined
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"))


@pytest.fixture
def root(tmp_path) -> Path:
    root = tmp_path / "Domain Expertise"
    dom = root / "Founder Office Expertise"
    _write(dom / "domain.yaml", """
identity:
  id: founder_office
  name: Founder Office
  version: 1.0.0
  status: draft
""")
    _write(dom / "registry/situation-capability-map.yaml", "domain: Founder Office Expertise\nmap: {}\n")
    cap = dom / "capabilities/02-programs-and-applications/program-applications"
    _write(cap / "capability.yaml", f"""
# The founder's applications — a comment the review must not lose.
identity:
  id: {CAP}
  name: Program Applications
  domain: founder_office
  subdomain: programs_and_applications
  version: 0.1.0
  status: draft
  stub: false
description: Applications to programmes, from submission to onboarding.
question: Where does this application stand?
outcomes:
  - Each application's stage named from what the programme last sent.
failure_modes:
  - Reading a programme as an investor.
metadata:
  owner: Founder Office
  created_by: ai
  reviewed_by: ""
  last_updated: "2026-10-09"
  review_status: unreviewed
""")
    _write(cap / "objects.yaml", f"capability: {CAP}\ncore: {{required: [], optional: []}}\n"
                                 "scoped: {required: [], optional: []}\n")
    _write(cap / "knowledge.yaml", f"""
capability: {CAP}
playbooks: {{core: [], scoped: [founder_office.pb.program_applications.follow_an_application]}}
heuristics: {{core: [], scoped: [founder_office.heu.program_applications.a_batch_is_silent]}}
mental_models: {{core: [], scoped: []}}
rules: {{core: [], scoped: []}}
decision_frameworks: {{core: [], scoped: []}}
""")
    _write(dom / "playbooks/program_applications/follow-an-application.yaml", f"""
identity:
  id: founder_office.pb.program_applications.follow_an_application
  name: Follow an application
  kind: playbook
  domain: founder_office
  scope: capability
  owner_capability: {CAP}
  version: 0.1.0
  status: draft
purpose:
  statement: Carry an application from submission to a decision.
when_to_use:
  signals:
    - An application was submitted.
steps:
  - order: 1
    name: Note the decision date
    done_when: The date is on file.
stages:
  - name: applied
    label: Applied
    typical_duration_days: 21
    quiet_means: Batches decide together.
    leaves_when: An interview invitation arrives.
    source: "https://www.ycombinator.com/apply"
success_signal: The programme's decision mail arrives.
outcome_window_days: 30
do_nothing_consequence: The cohort fills and the next intake is six months away.
stop:
  dormant_after_days: 90
  source: practitioner judgement — unverified; for the founder's review
  then: Reapply next cycle.
metadata:
  owner: Founder Office
  last_updated: "2026-10-09"
  review_status: unreviewed
  reviewed_by: ""
""")
    _write(dom / "heuristics/program_applications/a-batch-is-silent.yaml", f"""
identity:
  id: founder_office.heu.program_applications.a_batch_is_silent
  name: A batch is silent
  kind: heuristic
  domain: founder_office
  scope: capability
  owner_capability: {CAP}
  version: 0.1.0
  status: draft
purpose:
  statement: Why a programme's silence in review is not a no.
heuristic:
  statement: A programme that reviews in batches is silent until the batch decides.
  why: Reviewers read a cohort together.
metadata:
  owner: Founder Office
  last_updated: "2026-10-09"
  review_status: unreviewed
""")
    return root


def _sheet(tool, root) -> dict:
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
    return tool.sheet(ExpertBrainCatalog(root), "program")


def _apply(tool, root, sheet, reviewer="rohit"):
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
    return tool.apply(ExpertBrainCatalog(root), root, sheet, reviewer, today="2026-10-09")


def _snapshot(root: Path) -> dict[str, str]:
    return {str(p): p.read_text() for p in sorted(root.rglob("*.yaml"))}


def test_the_sheet_has_a_line_for_everything_said(tool, root):
    lines = _sheet(tool, root)["lines"]
    fields = {(l["artifact"].rsplit(".", 1)[1], l["field"]) for l in lines}
    assert {("program_applications", "description"), ("program_applications", "outcomes[1]"),
            ("program_applications", "failure_modes[1]"), ("follow_an_application", "purpose"),
            ("follow_an_application", "steps[1]"), ("follow_an_application", "stages[1]"),
            ("follow_an_application", "success_signal"), ("follow_an_application", "stop"),
            ("follow_an_application", "outcome_window_days"),
            ("follow_an_application", "do_nothing_consequence"),
            ("a_batch_is_silent", "heuristic.statement"), ("a_batch_is_silent", "heuristic.why")} <= fields
    assert len({l["id"] for l in lines}) == len(lines)
    assert all(l["decision"] == "" and l["fingerprint"] for l in lines)


def test_a_stage_line_shows_its_prior_and_its_source(tool, root):
    [stage] = [l for l in _sheet(tool, root)["lines"] if l["field"] == "stages[1]"]
    assert "typically 21 days — a prior" in stage["text"]
    assert "source: https://www.ycombinator.com/apply" in stage["text"]
    assert "normal" not in stage["text"] and "usually" not in stage["text"]


def test_an_unanswered_line_admits_nothing(tool, root, capsys):
    before = _snapshot(root)
    assert _apply(tool, root, _sheet(tool, root)) == 1
    assert _snapshot(root) == before
    assert "NOT ADMITTED" in capsys.readouterr().out


def test_one_reject_admits_nothing_and_is_listed_with_its_note(tool, root, capsys):
    sheet = _sheet(tool, root)
    for line in sheet["lines"]:
        line["decision"] = "accept"
    sheet["lines"][0].update(decision="reject", note="say what the founder actually applies to")
    before = _snapshot(root)
    assert _apply(tool, root, sheet) == 1
    assert _snapshot(root) == before
    out = capsys.readouterr().out
    assert "reject" in out and "say what the founder actually applies to" in out


def test_a_sheet_for_yesterday_s_words_is_refused(tool, root, capsys):
    sheet = _sheet(tool, root)
    for line in sheet["lines"]:
        line["decision"] = "accept"
    heuristic = root / "Founder Office Expertise/heuristics/program_applications/a-batch-is-silent.yaml"
    heuristic.write_text(heuristic.read_text().replace("Reviewers read a cohort together.",
                                                       "Reviewers read a cohort at once."))
    before = _snapshot(root)
    assert _apply(tool, root, sheet) == 2
    assert _snapshot(root) == before and "STALE" in capsys.readouterr().out


def test_every_line_accepted_admits_and_names_the_reviewer(tool, root):
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog
    from genios_engine.packs.compiler.capability_resolver import (_admission_reason,
                                                                  artifact_admission_reason)
    sheet = _sheet(tool, root)
    for line in sheet["lines"]:
        line["decision"] = "accept"
    assert _apply(tool, root, sheet) == 0
    record = ExpertBrainCatalog(root).domain("founder_office")
    assert _admission_reason(record.capabilities[CAP]) is None
    for doc in record.artifacts.values():
        assert artifact_admission_reason(doc.content) is None, doc.id
        assert doc.content["metadata"]["reviewed_by"] == "rohit"
        assert doc.content["metadata"]["reviewed_at"] == "2026-10-09"
    capability = (root / "Founder Office Expertise/capabilities/02-programs-and-applications/"
                  "program-applications/capability.yaml").read_text()
    assert capability.startswith("# The founder's applications — a comment the review must not lose.")


def test_a_review_names_its_reviewer(tool, root):
    sheet = _sheet(tool, root)
    for line in sheet["lines"]:
        line["decision"] = "accept"
    with pytest.raises(SystemExit):
        _apply(tool, root, sheet, reviewer="  ")


def test_the_sheet_is_plain_yaml_a_founder_can_fill(tool, root, tmp_path):
    out = tmp_path / "program.review.yaml"
    assert tool.main(["--root", str(root), "sheet", "--kind", "program", "--out", str(out)]) == 0
    filled = yaml.safe_load(out.read_text())
    assert filled["capability"] == CAP and filled["lines"]
    for line in filled["lines"]:
        line["decision"] = "accept"
    out.write_text(yaml.safe_dump(filled, sort_keys=False, allow_unicode=True))
    assert tool.main(["--root", str(root), "apply", str(out), "--reviewer", "rohit"]) == 0
