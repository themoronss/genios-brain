"""STEP-13b · what the GeniOS Engine hands the expert for one file — every line an id, a family, a source.

    .venv/bin/python -m pytest -q tests/contracts/test_an_engine_read.py

Tree `yc2_w27_s13b · M37.C1.L-contract.V0.U01`, STEP-13b §8.4 item 1. The expert reads three sources at
once — the file's data, the GeniOS Engine and its own expertise — and the check can only verify an engine
line it can name. So the engine's lines arrive in closed families with closed id prefixes (`cap:` `sig:`
`pb:` `rule:` `cons:` `frame:` `org:` `pat:` `pref:` `ru:`), each with its source and whether a named
human reviewed it (`06` D-s13b-6: read ungated, labelled "not yet reviewed"); the read counts what each
family's limit cut, names the corpus situations that MAY apply and the file's situations it could not
read, and carries a version — `eng-` and the hash of what it shows. Pure and frozen; read back as written.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from genios_engine.contracts import engine_read as E

pytestmark = pytest.mark.unit

INVESTOR = "founder_office.fundraising.investor_relations"


def _line(family: str = E.CAPABILITY, ref: str | None = None, **kw) -> E.EngineLine:
    refs = {E.CAPABILITY: f"cap:{INVESTOR}#f2", E.SIGNALS: "sig:founder_office.sit.live_investor_relationship",
            E.PLAYBOOK: "pb:founder_office.heu.investor_relations.investors_do_not_chase",
            E.RULE: "rule:admin.rule.commitment_tracking.no_chase_while_we_hold_the_ball",
            E.CONSTRAINT: "cons:admin.rule.commitment_tracking.no_chase_while_we_hold_the_ball",
            E.FRAME: "frame:sales.mm.the_status_quo", E.ORGANIZATION: "org:approval_threshold@v3",
            E.BEHAVIOUR: "pat:reply_window.investor@v1", E.ADAPTIVE: "pref:bad_timing.mornings@m_17",
            E.UNIT: "ru:core.risk"}
    fields = dict(ref=ref or refs[family], family=family, words="Treating a pass as terminal.",
                  source=INVESTOR, source_version="sha256:abc", reviewed=False)
    if family == E.CONSTRAINT:
        fields["verdict"] = E.HOLDS
    fields.update(kw)
    return E.EngineLine(**fields)


# ── the families ───────────────────────────────────────────────────────────────────────────────

def test_the_families_are_closed_and_each_has_its_own_prefix():
    assert E.FAMILIES == (E.CAPABILITY, E.SIGNALS, E.PLAYBOOK, E.RULE, E.CONSTRAINT, E.FRAME,
                          E.ORGANIZATION, E.BEHAVIOUR, E.ADAPTIVE, E.UNIT)
    assert {E.PREFIX[f] for f in E.FAMILIES} == {"cap:", "sig:", "pb:", "rule:", "cons:", "frame:",
                                                 "org:", "pat:", "pref:", "ru:"}
    assert len(set(E.PREFIX.values())) == len(E.FAMILIES)


def test_each_family_is_authored_learned_or_measured():
    authored = {E.CAPABILITY, E.SIGNALS, E.PLAYBOOK, E.RULE, E.CONSTRAINT, E.FRAME}
    assert {f for f in E.FAMILIES if E.ORIGIN_OF[f] == E.AUTHORED} == authored
    assert {f for f in E.FAMILIES if E.ORIGIN_OF[f] == E.LEARNED} == {E.ORGANIZATION, E.BEHAVIOUR,
                                                                      E.ADAPTIVE}
    assert {f for f in E.FAMILIES if E.ORIGIN_OF[f] == E.MEASURED} == {E.UNIT}
    assert E.ORIGINS == (E.AUTHORED, E.LEARNED, E.MEASURED)


def test_a_family_is_read_off_its_ref():
    for family in E.FAMILIES:
        assert E.family_of(_line(family).ref) == family
    assert E.family_of("evt_c4712b6b8ec4802296eb9578") is None
    assert E.family_of("num:days_quiet") is None
    assert E.family_of("sit:abc") is None, "a situation of the dossier is data, not engine"


@pytest.mark.parametrize("family", list(E.FAMILIES))
def test_every_family_reads_back_as_written(family):
    line = _line(family, cites=("evt_b", "evt_a", "evt_b"))
    raw = line.as_mapping()
    assert raw["origin"] == E.ORIGIN_OF[family]
    assert E.EngineLine.from_mapping(raw) == line
    assert line.cites == ("evt_b", "evt_a"), "cites keep their order, each once"


# ── a line ─────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ref", [
    "pb:founder_office.heu.x",                     # a playbook ref on a capability line
    "cap:",                                        # nothing after the prefix
    f"cap:{INVESTOR}",                             # a capability line names its question or a failure
    f"cap:{INVESTOR}#f0",                          # failure modes count from one
    f"cap:{INVESTOR}#x1",
    f"cap:{INVESTOR} #q",                          # an id is printed in brackets: no space
    f"cap:[{INVESTOR}]#q",
])
def test_a_ref_outside_its_family_s_grammar_is_refused(ref):
    with pytest.raises(ValueError):
        _line(E.CAPABILITY, ref=ref)


@pytest.mark.parametrize("family", [f for f in E.FAMILIES if f != E.CAPABILITY])
def test_a_prefix_with_nothing_after_it_names_nothing(family):
    with pytest.raises(ValueError):
        _line(family, ref=E.PREFIX[family])
    with pytest.raises(ValueError):
        _line(family, ref=E.PREFIX[family] + "two words")


def test_a_line_carries_its_own_family_s_prefix_and_no_other():
    with pytest.raises(ValueError):
        _line(E.PLAYBOOK, ref=f"cap:{INVESTOR}#q")
    with pytest.raises(ValueError):
        _line(E.UNIT, ref="rule:core.risk")
    with pytest.raises(ValueError):
        _line(E.ADAPTIVE, ref="pat:bad_timing@m_17")


def test_a_capability_ref_names_its_question_or_a_failure_mode():
    assert _line(ref=f"cap:{INVESTOR}#q").ref.endswith("#q")
    assert _line(ref=f"cap:{INVESTOR}#f12").ref.endswith("#f12")


def test_an_unknown_family_and_an_empty_line_are_refused():
    with pytest.raises(ValueError):
        _line(family="doctrine", ref="doctrine:x")
    for field in ("words", "source", "source_version"):
        with pytest.raises(ValueError):
            _line(**{field: "  "})
    with pytest.raises(ValueError):
        _line(reviewed="yes")
    with pytest.raises(ValueError):
        _line(cites=("evt a",))


def test_words_are_folded_to_one_line():
    assert _line(words="  Treating a pass\n as   terminal. ").words == "Treating a pass as terminal."


def test_a_constraint_says_its_verdict_and_no_other_line_does():
    assert E.VERDICTS == (E.HOLDS, E.FAILS, E.UNKNOWN)
    for verdict in E.VERDICTS:
        assert _line(E.CONSTRAINT, verdict=verdict).verdict == verdict
    with pytest.raises(ValueError):
        _line(E.CONSTRAINT, verdict=None)
    with pytest.raises(ValueError):
        _line(E.CONSTRAINT, verdict="true")
    with pytest.raises(ValueError):
        _line(E.RULE, verdict=E.HOLDS)


def test_an_unreviewed_authored_line_says_so_in_d6_s_words():
    assert E.NOT_REVIEWED == "not yet reviewed"
    assert _line(E.PLAYBOOK, reviewed=False).label == E.NOT_REVIEWED
    assert _line(E.PLAYBOOK, reviewed=True).label is None
    assert _line(E.ORGANIZATION, reviewed=False).label is None, "a learned line is not a corpus draft"
    assert _line(E.UNIT, reviewed=False).label is None


def test_a_measurement_is_never_reviewed():
    with pytest.raises(ValueError):
        _line(E.UNIT, reviewed=True)


# ── the read ───────────────────────────────────────────────────────────────────────────────────

def _read(**kw) -> E.EngineRead:
    fields = dict(lines=(_line(E.CAPABILITY), _line(E.PLAYBOOK), _line(E.CONSTRAINT, verdict=E.UNKNOWN)),
                  cut={E.PLAYBOOK: 3},
                  may_apply=(E.MayApply(situation="admin.sit.overdue_commitment",
                                        capability="admin.commitments.commitment_tracking",
                                        missing=("commitment.due_at",)),),
                  not_read=(E.NotRead(situation_type="opportunity", domain="sales",
                                      reason=E.SWITCHED_OFF, corpora=("sales",)),))
    fields.update(kw)
    return E.EngineRead(**fields)


def test_every_family_s_cut_is_counted_and_a_family_that_cut_nothing_says_zero():
    read = _read()
    assert set(read.cut) == set(E.FAMILIES)
    assert read.cut[E.PLAYBOOK] == 3 and read.cut[E.UNIT] == 0
    assert read.cut_total == 3
    assert _read(cut={E.PLAYBOOK: 3, E.CAPABILITY: 2}).cut_total == 5, "every family's cut, summed"
    for bad in ({"doctrine": 1}, {E.PLAYBOOK: -1}, {E.PLAYBOOK: True}, {E.PLAYBOOK: 1.5}):
        with pytest.raises(ValueError):
            _read(cut=bad)


def test_one_ref_is_one_line():
    with pytest.raises(ValueError):
        _read(lines=(_line(E.CAPABILITY), _line(E.CAPABILITY)))


def test_the_read_is_looked_up_by_ref_and_by_family():
    read = _read()
    assert read.refs == tuple(line.ref for line in read.lines)
    assert read.by_ref[f"cap:{INVESTOR}#f2"].family == E.CAPABILITY
    assert [line.family for line in read.of_family(E.CONSTRAINT)] == [E.CONSTRAINT]
    assert not read.empty and E.EngineRead().empty


def test_why_a_situation_was_not_read_is_closed():
    assert E.NOT_READ_REASONS == (E.SWITCHED_OFF, E.NO_ROUTE, E.UNKNOWN_DOMAIN)
    with pytest.raises(ValueError):
        E.NotRead(situation_type="opportunity", domain="sales", reason="off")
    with pytest.raises(ValueError):
        E.MayApply(situation=" ", capability=None, missing=())


def test_the_version_is_the_hash_of_what_it_shows():
    read = _read()
    assert read.version.startswith("eng-") and len(read.version) == len("eng-") + 12
    assert _read().version == read.version, "the same lines, the same version"
    moved = _read(lines=(_line(E.CAPABILITY, words="Reading the relationship as a deal."),
                         _line(E.PLAYBOOK), _line(E.CONSTRAINT, verdict=E.UNKNOWN)))
    assert moved.version != read.version, "a changed word is a changed engine"
    assert _read(cut={E.PLAYBOOK: 4}).version != read.version, "what a limit cut is part of the read"
    assert _read(may_apply=()).version != read.version
    assert _read(not_read=()).version != read.version
    reviewed = _read(lines=(_line(E.CAPABILITY, reviewed=True), _line(E.PLAYBOOK),
                            _line(E.CONSTRAINT, verdict=E.UNKNOWN)))
    assert reviewed.version != read.version, "a review is part of what the expert is told"


def test_the_read_reads_back_as_written():
    read = _read()
    raw = read.as_mapping()
    assert raw["version"] == read.version
    back = E.EngineRead.from_mapping(raw)
    assert back == read and back.version == read.version


def test_a_stored_read_whose_content_moved_is_refused_not_re_versioned():
    raw = _read().as_mapping()
    raw["lines"][0]["words"] = "Something nobody showed the expert."
    with pytest.raises(ValueError):
        E.EngineRead.from_mapping(raw)


def test_the_contract_is_pure():
    """No database, no clock, no model: the module imports the standard library, `platform` and
    `contracts` only."""
    tree = ast.parse(Path(E.__file__).read_text())
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    imported |= {a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
    ours = {m for m in imported if m.startswith("genios_engine")}
    assert all(m.startswith(("genios_engine.platform", "genios_engine.contracts")) for m in ours), ours
    assert not imported & {"sqlalchemy", "datetime", "time", "anthropic", "httpx", "random"}
