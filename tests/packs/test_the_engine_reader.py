"""STEP-13b · the Domain Expertise of a file — what the GeniOS Engine knows about its situations and its kind.

    .venv/bin/python -m pytest -q tests/packs/test_the_engine_reader.py

Tree `yc2_w27_s13b · M37.C2.L-logic.V1.U01`, STEP-13b §8.4 item 1. Measured 12 Oct: the expert reads only its
kind's playbook (22 of 94 authored answers' files) — 26 answers' files hold an investor situation and print no
playbook (s13b-F8), and no capability's doctrine is printed anywhere (s13b-F9); the compiled lane never
reaches a covered or held file (s13b-F7). `packs/compiler/engine_reader.engine_for` reads, for each of the
file's situations, the corpus situations its registries route it to in the tenant's switched-on corpora —
by ROUTE, not through the publisher — each one's `matches.when` read by the compiler's own three-state
evaluator over the anchor's facts (TRUE prints, UNKNOWN is named "may apply", FALSE is silent), and for each
that applies its owner capability's question and failure modes (`cap:`), its signals (`sig:`), the
capability's playbooks and heuristics (`pb:` — the kind's stay where the dossier prints them), its rules
(`rule:`) with each compiled constraint's verdict (`cons:`) and its framing blocks (`frame:`); and for the
file's kind, its capability's doctrine. Read, never gated (D-s13b-6): an unreviewed line says so. Bounded
per family, every cut counted; a version, and the file's ROUTE KEY (no predicate) beside it.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest

from genios_engine.contracts import engine_read as E
from genios_engine.packs.compiler import engine_reader as R
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
LIVE = frozenset({"admin", "founder_office"})
INVESTOR = "founder_office.fundraising.investor_relations"
INVESTOR_SIT = "founder_office.sit.live_investor_relationship"
COMMITMENTS = "admin.executive_support.commitment_tracking"


def _sit(kind: str, domain: str) -> R.FileSituation:
    return R.FileSituation(situation_type=kind, domain=domain)


# ── a small corpus, written by the test ────────────────────────────────────────────────────────

CAP = "ops.work.follow_through"
CAP2 = "ops.work.second"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _corpus(tmp_path: Path, *, heuristics: int = 2, question: str = "Is it done?",
            reviewed: bool = False, decay: bool = True) -> ExpertBrainCatalog:
    root = tmp_path / "Domain Expertise"
    dom = root / "Ops Expertise"
    _write(dom / "domain.yaml", "identity: {id: ops, name: Ops, version: 1.0.0, status: draft}\n")
    _write(dom / "registry/situation-capability-map.yaml", f"""
domain: Ops Expertise
map:
  follow_through:
    situations: [ops.sit.always, ops.sit.when_owed]
    capabilities: [{CAP}, {CAP2}]
  only_when:
    situations: [ops.sit.when_owed]
    capabilities: [{CAP2}]
""")
    status, review, who = ("stable", "approved", "rohit") if reviewed else ("draft", "unreviewed", "")
    for cap, name in ((CAP, "follow-through"), (CAP2, "second")):
        base = dom / f"capabilities/01-work/{name}"
        _write(base / "capability.yaml", f"""
identity: {{id: {cap}, name: {name}, domain: ops, version: 1.0.0, status: {status}, stub: false}}
description: Doing what was said.
question: "{question}"
failure_modes:
  - Reading a send as a delivery.
  - Chasing the side that already answered.
metadata: {{review_status: {review}, reviewed_by: "{who}"}}
""")
        _write(base / "objects.yaml", f"capability: {cap}\ncore: {{required: [], optional: []}}\n"
                                      "scoped: {required: [], optional: []}\n")
    heus = [f"ops.heu.work.h{i}" for i in range(heuristics)]
    _write(dom / "capabilities/01-work/follow-through/knowledge.yaml", f"""
capability: {CAP}
playbooks: {{core: [], scoped: [ops.pb.work.close_the_loop]}}
heuristics: {{core: [], scoped: [{', '.join(heus)}]}}
mental_models: {{core: [], scoped: [ops.mm.work.two_sided]}}
rules: {{core: [], scoped: [ops.rule.work.no_chase_while_ours]}}
decision_frameworks: {{core: [], scoped: []}}
""")
    _write(dom / "capabilities/01-work/second/knowledge.yaml", f"""
capability: {CAP2}
playbooks: {{core: [], scoped: []}}
heuristics: {{core: [], scoped: []}}
mental_models: {{core: [], scoped: []}}
rules: {{core: [], scoped: []}}
decision_frameworks: {{core: [], scoped: []}}
""")
    for sid, owner, when in (("ops.sit.always", CAP, "[]"),
                             ("ops.sit.when_owed", CAP2, "[{path: thread.ball_in_court, op: '=', value: them}]")):
        _write(dom / f"capabilities/01-work/situations/{sid.rsplit('.', 1)[1]}.yaml", f"""
identity: {{id: {sid}, name: {sid}, domain: ops, owner_capability: {owner}, version: 1.0.0, status: {status}}}
matches: {{l2_situation_types: [follow_through], when: {when}}}
signals_of_progress: [positive_reply]
signals_of_decay: {"[negative_reply, timeline_slip]" if decay else "[]"}
metadata: {{review_status: {review}, reviewed_by: "{who}"}}
""")
    _write(dom / "playbooks/work/close-the-loop.yaml", f"""
identity: {{id: ops.pb.work.close_the_loop, name: Close the loop, kind: playbook, domain: ops, version: 1.0.0,
            status: {status}}}
steps:
  - {{order: 1, name: Confirm both sides answered}}
  - {{order: 2, description: Nudge the silent side once}}
metadata: {{review_status: {review}, reviewed_by: "{who}"}}
""")
    for i, hid in enumerate(heus):
        _write(dom / f"heuristics/work/h{i}.yaml", f"""
identity: {{id: {hid}, name: h{i}, kind: heuristic, domain: ops, version: 1.0.0, status: {status}}}
heuristic: {{statement: "Silence after an introduction is mutual politeness number {i}.", why: Both wait.}}
metadata: {{review_status: {review}, reviewed_by: "{who}"}}
""")
    _write(dom / "rules/work/no-chase.yaml", f"""
identity: {{id: ops.rule.work.no_chase_while_ours, name: No chase while ours, kind: rule, domain: ops,
            version: 1.0.0, status: {status}}}
rule:
  statement: A commitment MUST NOT be chased while the ball is ours.
  when: [{{path: thread.ball_in_court, op: '=', value: us}}]
  then: Discharge it, or renegotiate its date.
  enforced_by: L4_constraint
metadata: {{review_status: {review}, reviewed_by: "{who}"}}
""")
    _write(dom / "mental-models/work/two-sided.yaml", f"""
identity: {{id: ops.mm.work.two_sided, name: Two-sided silence, kind: mental_model, domain: ops,
            version: 1.0.0, status: {status}}}
purpose: {{statement: "Both parties wait for the other to look interested first."}}
metadata: {{review_status: {review}, reviewed_by: "{who}"}}
""")
    return ExpertBrainCatalog(root)


def _engine(catalog, situations=(("follow_through", "ops"),), *, anchor=None, kind=None,
            activated=frozenset({"ops"}), **kw) -> R.FileEngine:
    return R.engine_for([_sit(t, d) for t, d in situations], kind=kind, activated=activated,
                        anchor=anchor, catalog=catalog, **kw)


def _anchor(**facts) -> R.Anchor:
    return R.Anchor(facts={k: {"value": v} for k, v in facts.items()}, evaluation_time=NOW)


def test_a_situation_reads_its_routes_capability_doctrine_signals_playbooks_rules_and_frames(tmp_path):
    engine = _engine(_corpus(tmp_path), anchor=_anchor(**{"thread.ball_in_court": "us"}))
    refs = engine.read.refs
    assert f"cap:{CAP}#q" in refs and f"cap:{CAP}#f1" in refs and f"cap:{CAP}#f2" in refs
    assert "sig:ops.sit.always" in refs
    assert "pb:ops.pb.work.close_the_loop" in refs and "pb:ops.heu.work.h0" in refs
    assert "rule:ops.rule.work.no_chase_while_ours" in refs
    assert "cons:ops.rule.work.no_chase_while_ours" in refs
    assert "frame:ops.mm.work.two_sided" in refs
    by = engine.read.by_ref
    assert by[f"cap:{CAP}#q"].words == "Is it done?"
    assert by[f"cap:{CAP}#f1"].words == "Reading a send as a delivery."
    assert "positive_reply" in by["sig:ops.sit.always"].words and "timeline_slip" in by["sig:ops.sit.always"].words
    assert "Confirm both sides answered" in by["pb:ops.pb.work.close_the_loop"].words
    assert "mutual politeness number 0" in by["pb:ops.heu.work.h0"].words
    assert by["frame:ops.mm.work.two_sided"].words.startswith("Two-sided silence")


def test_the_families_are_printed_in_their_order(tmp_path):
    families = [line.family for line in _engine(_corpus(tmp_path), anchor=_anchor()).read.lines]
    assert families == sorted(families, key=E.FAMILIES.index)


def test_a_line_says_its_source_and_whether_a_named_human_reviewed_it(tmp_path):
    draft = _engine(_corpus(tmp_path), anchor=_anchor()).read.by_ref[f"cap:{CAP}#q"]
    assert draft.source == CAP and len(draft.source_version) == 64, "the content hash"
    assert draft.reviewed is False and draft.label == E.NOT_REVIEWED
    pb = _engine(_corpus(tmp_path), anchor=_anchor()).read.by_ref["pb:ops.heu.work.h0"]
    assert pb.source == "ops.heu.work.h0" and pb.label == E.NOT_REVIEWED


def test_a_reviewed_artifact_is_read_as_reviewed(tmp_path):
    read = _engine(_corpus(tmp_path, reviewed=True), anchor=_anchor()).read
    assert read.by_ref["pb:ops.heu.work.h0"].reviewed is True
    assert read.by_ref["sig:ops.sit.always"].reviewed is True
    # a capability is admitted only by its accepted content hash, which this corpus never writes
    assert read.by_ref[f"cap:{CAP}#q"].reviewed is False


def test_a_constraint_says_what_its_rule_s_predicate_reads_on_this_anchor(tmp_path):
    cat = _corpus(tmp_path)
    holds = _engine(cat, anchor=_anchor(**{"thread.ball_in_court": "us"})).read.by_ref
    fails = _engine(cat, anchor=_anchor(**{"thread.ball_in_court": "them"})).read.by_ref
    unknown = _engine(cat, anchor=_anchor()).read.by_ref
    ref = "cons:ops.rule.work.no_chase_while_ours"
    assert (holds[ref].verdict, fails[ref].verdict, unknown[ref].verdict) == (E.HOLDS, E.FAILS, E.UNKNOWN)
    assert "Discharge it" in holds[ref].words
    assert "thread.ball_in_court" in unknown[ref].words, "an unknown verdict names what it could not read"


def test_a_predicate_true_prints_unknown_is_named_and_false_is_silent(tmp_path):
    cat = _corpus(tmp_path)
    shown = _engine(cat, anchor=_anchor(**{"thread.ball_in_court": "them"})).read
    assert f"cap:{CAP2}#q" in shown.refs and "sig:ops.sit.when_owed" in shown.refs
    unknown = _engine(cat, anchor=_anchor()).read
    assert f"cap:{CAP2}#q" not in unknown.refs and "sig:ops.sit.when_owed" not in unknown.refs
    assert [(m.situation, m.capability, m.missing) for m in unknown.may_apply] == [
        ("ops.sit.when_owed", CAP2, ("thread.ball_in_court",))]
    silent = _engine(cat, anchor=_anchor(**{"thread.ball_in_court": "us"})).read
    assert f"cap:{CAP2}#q" not in silent.refs and silent.may_apply == ()


def test_with_no_anchor_read_only_an_unconditional_route_prints(tmp_path):
    read = _engine(_corpus(tmp_path), anchor=None).read
    assert "sig:ops.sit.always" in read.refs and "sig:ops.sit.when_owed" not in read.refs
    assert [m.situation for m in read.may_apply] == ["ops.sit.when_owed"]
    assert read.by_ref["cons:ops.rule.work.no_chase_while_ours"].verdict == E.UNKNOWN


def test_a_situation_routed_only_to_a_switched_off_corpus_is_named_so(tmp_path):
    read = _engine(_corpus(tmp_path), activated=frozenset({"admin"}), anchor=_anchor()).read
    assert read.lines == ()
    assert [(n.situation_type, n.reason, n.corpora) for n in read.not_read] == [
        ("follow_through", E.SWITCHED_OFF, ("ops",))]


def test_a_type_no_registry_routes_and_an_unknown_domain_are_named(tmp_path):
    read = _engine(_corpus(tmp_path), situations=(("nothing_routes_this", "ops"), ("follow_through", "mars")),
                   anchor=_anchor()).read
    assert [(n.situation_type, n.domain, n.reason) for n in read.not_read] == [
        ("nothing_routes_this", "ops", E.NO_ROUTE), ("follow_through", "mars", E.UNKNOWN_DOMAIN)]


def test_an_unclassified_domain_looks_everywhere_switched_on(tmp_path):
    read = _engine(_corpus(tmp_path), situations=(("follow_through", "general"),), anchor=_anchor()).read
    assert "sig:ops.sit.always" in read.refs


def test_every_line_once_however_many_situations_route_to_it(tmp_path):
    read = _engine(_corpus(tmp_path), situations=(("follow_through", "ops"), ("follow_through", "general")),
                   anchor=_anchor(**{"thread.ball_in_court": "them"})).read
    assert len(read.refs) == len(set(read.refs))


def test_each_family_is_bounded_and_its_cut_counted(tmp_path):
    engine = _engine(_corpus(tmp_path, heuristics=6), anchor=_anchor(), limits={E.PLAYBOOK: 3})
    assert len(engine.read.of_family(E.PLAYBOOK)) == 3
    assert engine.read.cut[E.PLAYBOOK] == 4, "one playbook and six heuristics, three shown"
    assert engine.read.cut[E.CAPABILITY] == 0


def test_a_long_line_is_cut_on_a_word(tmp_path):
    engine = _engine(_corpus(tmp_path, question="Is it done " + "and dusted " * 80 + "?"), anchor=_anchor())
    words = engine.read.by_ref[f"cap:{CAP}#q"].words
    assert len(words) <= R.LINE_CHARS + 1 and words.endswith("…") and "dust…" not in words


def test_a_line_exactly_at_the_limit_is_not_cut(tmp_path):
    exact = "x" * R.LINE_CHARS
    words = _engine(_corpus(tmp_path, question=exact), anchor=_anchor()).read.by_ref[f"cap:{CAP}#q"].words
    assert words == exact and not words.endswith("…")


def test_a_situation_with_only_progress_signals_still_prints_them(tmp_path):
    """`progress or decay` — not `and` — gates a signals line: either one alone is enough."""
    sig = _engine(_corpus(tmp_path, decay=False), anchor=_anchor(**{"thread.ball_in_court": "us"})
                 ).read.by_ref["sig:ops.sit.always"]
    assert "positive_reply" in sig.words and "decay" not in sig.words


def test_an_unknown_situation_reached_by_two_routes_is_named_once(tmp_path):
    """`ops.sit.when_owed` routes from both `follow_through` and `only_when`; its predicate is
    UNKNOWN on a blank anchor either time — named once, not twice."""
    cat = _corpus(tmp_path)
    read = _engine(cat, situations=(("follow_through", "ops"), ("only_when", "ops")), anchor=_anchor()).read
    matches = [m for m in read.may_apply if m.situation == "ops.sit.when_owed"]
    assert len(matches) == 1


def test_capability_of_an_unauthored_id_is_none_not_a_crash(tmp_path):
    cat = _corpus(tmp_path)
    assert R._capability(cat, "mars.unknown.capability") == (None, None)
    assert R._capability(cat, None) == (None, None)


def test_lines_dedupe_by_ref_and_drop_empty_text():
    lines = R._Lines({})
    lines.add(E.FRAME, "frame:x", "first", source="s", version="v", reviewed=False)
    lines.add(E.FRAME, "frame:x", "second", source="s", version="v", reviewed=False)  # ref already seen
    lines.add(E.FRAME, "frame:y", "   ", source="s", version="v", reviewed=False)  # empty after the cut
    assert [line.words for line in lines.lines()] == ["first"]


# ── the version and the route key ──────────────────────────────────────────────────────────────

def test_the_same_file_reads_the_same_engine(tmp_path):
    cat = _corpus(tmp_path)
    one, two = _engine(cat, anchor=_anchor()), _engine(cat, anchor=_anchor())
    assert one.read.version == two.read.version and one.route_key == two.route_key
    assert one.route_key.startswith("route-") and one.read.version.startswith("eng-")


def test_the_route_key_moves_with_the_corpus_and_not_with_the_facts(tmp_path):
    cat = _corpus(tmp_path)
    key = _engine(cat, anchor=_anchor()).route_key
    assert _engine(cat, anchor=_anchor(**{"thread.ball_in_court": "them"})).route_key == key, (
        "the route key reads no predicate — computed for every file, cheaply")
    assert R.route_key([_sit("follow_through", "ops")], kind=None, activated=frozenset({"ops"}),
                       catalog=cat) == key
    edited = _corpus(tmp_path / "edited", question="Has it gone out?")
    assert _engine(edited, anchor=_anchor()).route_key != key, "a changed capability re-keys the file"
    assert R.route_key([_sit("nothing_routes_this", "ops")], kind=None, activated=frozenset({"ops"}),
                       catalog=cat) == R.ROUTE_NONE


def test_the_version_moves_with_what_is_shown(tmp_path):
    cat = _corpus(tmp_path)
    assert _engine(cat, anchor=_anchor(**{"thread.ball_in_court": "us"})).read.version != \
        _engine(cat, anchor=_anchor(**{"thread.ball_in_court": "them"})).read.version


# ── the shipped corpus ─────────────────────────────────────────────────────────────────────────

def _shipped(situations, *, kind=None, anchor=None, activated=LIVE) -> R.FileEngine:
    return R.engine_for([_sit(t, d) for t, d in situations], kind=kind, activated=activated,
                        anchor=anchor if anchor is not None else R.Anchor(evaluation_time=NOW))


def test_an_investor_file_the_brief_names_no_kind_for_reads_the_investor_capability():
    """s13b-F8, F9: 26 authored answers' files hold an investor situation and print no playbook."""
    read = _shipped([("investor_relationship", "fundraising")]).read
    refs = set(read.refs)
    assert f"cap:{INVESTOR}#q" in refs
    assert {f"cap:{INVESTOR}#f{n}" for n in range(1, 7)} <= refs, "its six failure modes"
    assert "Treating a pass as terminal" in read.by_ref[f"cap:{INVESTOR}#f2"].words
    assert f"sig:{INVESTOR_SIT}" in refs
    assert "pb:founder_office.heu.investor_relations.investors_do_not_chase" in refs
    assert "pb:founder_office.pb.investor_relations.run_an_investor_conversation" in refs
    assert all(line.label == E.NOT_REVIEWED for line in read.lines
               if line.source.startswith("founder_office.")), "the Founder Office is drafts: labelled"


def test_an_investor_file_of_the_investor_kind_reads_its_doctrine_and_leaves_the_playbook_where_it_is():
    read = _shipped([("investor_relationship", "fundraising")], kind="investor").read
    assert f"cap:{INVESTOR}#q" in read.refs
    assert not [r for r in read.refs if r.startswith("pb:founder_office.")], (
        "the kind's playbooks and heuristics are the dossier's WHAT A PROFESSIONAL KNOWS — never twice")


def test_the_kind_s_capability_is_read_without_a_situation_and_without_its_corpus_switched_on():
    read = _shipped([], kind="investor", activated=frozenset()).read
    assert f"cap:{INVESTOR}#q" in read.refs and f"cap:{INVESTOR}#f1" in read.refs


def test_the_kind_s_capability_is_not_duplicated_when_a_situation_shares_it():
    """The investor situation's own owner capability IS the kind's capability — read once, not twice."""
    fe = _shipped([("investor_relationship", "fundraising")], kind="investor")
    assert fe.capabilities.count(INVESTOR) == 1, "the kind and the situation name one capability"


def test_an_investor_situation_with_an_agreed_next_step_does_not_route():
    anchor = R.Anchor(facts={"commitment.due_at": {"value": "2026-10-01T00:00:00Z"}}, evaluation_time=NOW)
    read = _shipped([("investor_relationship", "fundraising")], anchor=anchor).read
    assert f"cap:{INVESTOR}#q" not in read.refs, "its predicate `absent: commitment.due_at` is FALSE"


def test_an_account_file_reads_admin_s_unconditional_route_and_its_rule():
    read = _shipped([("account_admin", "admin")]).read
    assert f"cap:{COMMITMENTS}#q" in read.refs and "sig:admin.sit.live_account_admin" in read.refs
    cons = read.by_ref["cons:admin.rule.commitment_tracking.no_chase_while_we_hold_the_ball"]
    # Its `when` ANDs `{exists: commitment.due_at}` with a `path:` read of `thread.ball_in_court`.
    # `ContextAdapter.evaluate` answers `exists:` on a path the anchor neither holds nor has
    # declared missing or unknowable with a definite FALSE, not UNKNOWN (its own module docstring
    # names this the upstream gap: "this branch concludes absence from silence") — so the rule's
    # `when` is FALSE on the first condition and the second is never reached.
    assert cons.verdict == E.FAILS, "exists: on an undeclared path reads false, not unknown"
    # `money_owed_either_way`'s own `when` is just `{exists: commitment.due_at}` — FALSE here for
    # the same reason, so it is silently dropped (FALSE prints nothing). `vendor_relationship_live`
    # asks a genuine `path:` predicate the anchor cannot answer at all, so it is the one UNKNOWN.
    assert {m.situation for m in read.may_apply} >= {"admin.sit.vendor_relationship_live"}


def test_a_sales_opportunity_on_a_founder_s_tenant_is_named_switched_off():
    read = _shipped([("opportunity", "sales")]).read
    assert [(n.situation_type, n.reason, n.corpora) for n in read.not_read] == [
        ("opportunity", E.SWITCHED_OFF, ("sales",))]


def test_the_reader_is_pure():
    """No database, no clock, no model: `engine_for` is a function of its inputs and the catalog."""
    tree = ast.parse(Path(R.__file__).read_text())
    calls = {node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {"now", "utcnow", "today", "execute", "messages", "create"}, calls
