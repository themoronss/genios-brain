"""STEP-12 · the expert pass — each file that changed, reviewed once, in the sweep, in shadow.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_the_expert_pass.py -q

`reason/expert/sweep.py` (tree `yc2_w27_s12` M32.C3.L-integration.V2.U04), at the end of
`reason/runner.run_all`. For a tenant with `expert_review` on: every file's fingerprint; a fingerprint a
standing review answers costs nothing (unchanged), and so does a file nothing touched (`05` §5); the rest
are reviewed once, nearest meeting or deadline first, at most `MAX_PER_PASS` a pass — the first refusal
for want of budget stops the pass and the rest are carried, counted (`06` D7). A tenant without the
feature, or without a model, costs no file read. The sweep runs it FIRST and hands the compiled lane
what its valid reviews cover (M33.C1.L-data.V0.U06, M33.C1.L-integration.V2.U07).
"""
from __future__ import annotations

import ast
import inspect
import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.llm.client import LLMResult
from genios_engine.reason import runner
from genios_engine.reason.expert import store as R
from genios_engine.reason.expert import sweep as P

pytestmark = pytest.mark.pg

ORG = "org_s12_expert_pass"
KUNAL, ASHA = "kunal@meridianvc.test", "asha@tamarindfund.test"


class _Expert:
    """A model that answers every review validly, citing the first event its dossier prints."""
    model = "claude-sonnet-5"

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400):
        self.prompts.append(prompt)
        evidence = re.search(r"\[(evt_[^\]\s]+)\]", prompt).group(1)
        return LLMResult(parsed={
            "facts": [{"claim": "they wrote to us", "evidence": [evidence]}],
            "frames": {"primary": "a fund getting to know us", "rivals": ["a cold intro"]},
            "expected_vs_actual": {"stage": None, "expected": "a reply", "actual": "a reply came"},
            "scenarios": {"do_nothing": "it cools", "act": "it moves", "best": "a meeting",
                          "worst": "silence", "signals_to_watch": ["a reply"]},
            "appraisal": {"stakes": "medium", "urgency": "low", "reversibility": "reversible",
                          "reasons": ["early"]},
            "mode": "wait", "wait_or_stop": "wait for their reply", "done_when": "they reply"},
            raw="{}", ok=True, model=self.model, input_tokens=9000, output_tokens=900)


def _files_of(pg_store):
    with pg_store.engine.connect() as c:
        return {r.event_id: r.anchor_node_id for r in c.execute(text(
            "select m.event_id, k.anchor_node_id from context_correlations k "
            "  join context_correlation_members m on m.org_id = k.org_id "
            "       and m.correlation_id = k.correlation_id where k.org_id = :o"), {"o": ORG})}


@pytest.fixture
def world(pg_store):
    from tests.context.workstream_world import FOUNDER, process, reset, tenant
    from tests.reason.expert.test_the_dossier import NOW
    tenant(pg_store, ORG)
    process(pg_store, ORG, event_id="evt_k_in", sender=KUNAL, thread="t_k",
            at=NOW - timedelta(days=12))
    process(pg_store, ORG, event_id="evt_k_out", sender=FOUNDER, recipients=(KUNAL,), thread="t_k",
            at=NOW - timedelta(days=10))
    process(pg_store, ORG, event_id="evt_a_in", sender=ASHA, thread="t_a",
            at=NOW - timedelta(days=20))
    with pg_store.engine.begin() as c:
        c.execute(text("insert into l4_activation (org_id, feature, enabled_by) "
                       "values (:o, 'expert_review', 'test')"), {"o": ORG})
    try:
        yield pg_store, NOW
    finally:
        reset(pg_store, ORG)


def _pass(store, now, **kw):
    kw.setdefault("llm", _Expert())
    return P.expert_pass(store=store, org_id=ORG, now=now, **kw), kw["llm"]


def _rows(store):
    with store.engine.connect() as c:
        return c.execute(text("select file_id, status, triggers from expert_reviews where org_id = :o "
                              "order by file_id"), {"o": ORG}).fetchall()


def test_every_changed_file_is_reviewed_once_and_kept(world):
    store, now = world
    receipt, expert = _pass(store, now)
    files = _files_of(store)
    assert receipt["files"] == 2 and receipt["reviewed"] == {R.VALID: 2} and len(expert.prompts) == 2
    rows = _rows(store)
    assert {r.file_id for r in rows} == {files["evt_k_in"], files["evt_a_in"]}
    assert all(r.status == R.VALID and r.triggers == [{"kind": "first_look", "says": "never judged"}]
               for r in rows)
    assert receipt["cost_micro_usd"] > 0


def test_an_unchanged_sweep_makes_no_expert_call(world):
    store, now = world
    _pass(store, now)
    receipt, expert = _pass(store, now + timedelta(minutes=15))
    assert expert.prompts == [] and receipt["unchanged"] == 2 and receipt["reviewed"] == {}


def test_a_new_mail_reviews_its_file_alone_and_says_why(world):
    from tests.context.workstream_world import process
    store, now = world
    _pass(store, now)
    process(store, ORG, event_id="evt_k_again", sender=KUNAL, thread="t_k", at=now - timedelta(hours=2))
    receipt, expert = _pass(store, now + timedelta(minutes=15))           # the next sweep
    assert receipt["reviewed"] == {R.VALID: 1} and receipt["unchanged"] == 1 and len(expert.prompts) == 1
    files = _files_of(store)
    with store.engine.connect() as c:
        latest = R.latest_standing(c, ORG, files["evt_k_in"])
    assert latest.triggers == (("new_evidence", "new since the last review: evt_k_again"),)


def test_a_file_nothing_touched_costs_no_call(world):
    """Eleven days on, both files crossed a quiet rung (10 → 21 days, 20 → 31) — their fingerprints
    moved — and nothing touched either: Kunal was already past his usual reply at the last review."""
    store, now = world
    _pass(store, now)
    receipt, expert = _pass(store, now + timedelta(days=11))
    assert expert.prompts == [] and receipt["untouched"] == 2 and receipt["unchanged"] == 0


def _meeting(store, now, *, after: str, event_id: str, days: float, who: str) -> None:
    """A meeting booked `days` from now, filed with the event `after` (its file)."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, parent_object_id, dedup_key, actor, recipients, occurred_at, "
            " captured_at, outcome) values (:e, :o, 'con_x', 'gcal', 'calendar_event', :e, null, "
            " :k, cast(:a as jsonb), :r, :at, :now, 'emitted')"),
            {"e": event_id, "o": ORG, "k": f"gcal:calendar_event:{event_id}",
             "a": f'{{"email": "{who}"}}', "r": [who], "at": now + timedelta(days=days), "now": now})
        c.execute(text(
            "insert into context_correlation_members (org_id, correlation_id, event_id) "
            "select org_id, correlation_id, :e from context_correlation_members "
            " where org_id = :o and event_id = :after"), {"o": ORG, "e": event_id, "after": after})


def test_nearest_meeting_first_and_at_most_so_many_a_pass(world):
    """Kunal's meeting is in ten days, Asha's in two: Kunal's file is the most recently touched (a
    booked meeting counts), so it comes first in the files' own order — and Asha's is reviewed first."""
    store, now = world
    _meeting(store, now, after="evt_k_in", event_id="evt_k_call", days=10, who=KUNAL)
    _meeting(store, now, after="evt_a_in", event_id="evt_a_call", days=2, who=ASHA)
    receipt, expert = _pass(store, now, max_per_pass=1)
    files = _files_of(store)
    assert receipt["reviewed"] == {R.VALID: 1} and receipt["carried"] == 1
    assert [r.file_id for r in _rows(store)] == [files["evt_a_in"]]


def _promise(store, now, *, hours: float) -> None:
    """We promised Asha the deck, due `hours` from now — written by her file's own mail."""
    with store.engine.begin() as c:
        node = store.find_or_create_node(c, org_id=ORG, node_type="commitment",
                                         canonical_key="commitment:asha_deck",
                                         display_name="send Asha the deck", event_id="evt_a_in")
        for fld, val, vt in (("commitment.text", "send Asha the deck", "string"),
                             ("commitment.status", "open", "enum"),
                             ("commitment.due_at", (now + timedelta(hours=hours)).isoformat(),
                              "timestamp")):
            store.write_fact(c, org_id=ORG, subject_node_id=node, field=fld, value=val, value_type=vt,
                             confidence=0.8, occurred_at=now - timedelta(days=20), event_id="evt_a_in",
                             evidence={"text": "I will send the deck by Monday"}, source="gmail",
                             authority_rank=2)


@pytest.mark.parametrize("kunal_meeting, asha_meeting, asha_promise", [
    (10, None, 30),            # a promised date closing in comes before a later meeting
    (10, 20, 30),              # a file's NEAREST date counts: her promise, not her later meeting
    (None, None, 500),         # any date before none — though Kunal's file is the more recent
])
def test_the_nearest_date_decides_the_order(world, kunal_meeting, asha_meeting, asha_promise):
    store, now = world
    if kunal_meeting:
        _meeting(store, now, after="evt_k_in", event_id="evt_k_call", days=kunal_meeting, who=KUNAL)
    if asha_meeting:
        _meeting(store, now, after="evt_a_in", event_id="evt_a_call", days=asha_meeting, who=ASHA)
    _promise(store, now, hours=asha_promise)
    receipt, expert = _pass(store, now, max_per_pass=1)
    assert [r.file_id for r in _rows(store)] == [_files_of(store)["evt_a_in"]]


def test_no_budget_left_stops_the_pass_and_carries_the_rest_said(world):
    from genios_engine.reason.bundle.budget import NarrativeBudget
    from genios_engine.reason.bundle.sites import SITE_EXPERT
    store, now = world
    budget = NarrativeBudget.for_site(SITE_EXPERT, org_id=ORG)
    budget.charge(2_000_000)
    receipt, expert = _pass(store, now, budget=budget)
    assert expert.prompts == [] and receipt["reviewed"] == {R.OVER_BUDGET: 1}
    assert receipt["carried"] == 1 and [r.status for r in _rows(store)] == [R.OVER_BUDGET]


def test_the_days_spend_carries_from_one_pass_to_the_next(world):
    """Every consult is on the R-site ledger, so the next pass's budget opens with today's spend — the
    $2 is a day's, not a pass's (`06` D7). ⛔ Found at the build of V3.U06: the gate had no ledger."""
    from genios_engine.reason.bundle.budget import NarrativeBudget
    from genios_engine.reason.bundle.sites import SITE_EXPERT
    store, now = world
    receipt, _expert = _pass(store, now)
    opened = NarrativeBudget.for_site(SITE_EXPERT, org_id=ORG, engine=store.engine, now=now)
    assert receipt["cost_micro_usd"] > 0 and opened.spent_micro_usd == receipt["cost_micro_usd"]
    with store.engine.connect() as c:
        sites = c.execute(text("select site, count(*) from l4_r_site_calls where org_id = :o "
                               "group by site"), {"o": ORG}).fetchall()
    assert [tuple(r) for r in sites] == [(SITE_EXPERT, 2)]


def test_a_file_that_is_us_is_never_reviewed(world):
    """We are never the subject (STEP-04). ⛔ Found by the golden probe: case F02's portal mail names the
    founder's own company, and Layer 3 anchors a file on it (`nimbuslabs.test`, the domain declared ours)."""
    store, now = world
    files = _files_of(store)
    with store.engine.begin() as c:                  # Asha's file, as if anchored on a domain we declared
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'domain', 'nimbus-studio.test', 'test')"), {"o": ORG})
        ours = store.find_or_create_node(c, org_id=ORG, node_type="company",
                                         canonical_key="nimbus-studio.test",
                                         display_name="Hollow Shell Studio", event_id="evt_a_in")
        c.execute(text("update context_correlations set anchor_node_id = :n "
                       " where org_id = :o and anchor_node_id = :a"),
                  {"n": ours, "o": ORG, "a": files["evt_a_in"]})
    receipt, expert = _pass(store, now)
    assert receipt["ours"] == 1 and receipt["reviewed"] == {R.VALID: 1} and len(expert.prompts) == 1
    assert [r.file_id for r in _rows(store)] == [files["evt_k_in"]]
    assert set(receipt["covered"]) == {files["evt_k_in"]}, "a file that is us is never covered"


def test_a_file_named_for_our_own_company_is_never_reviewed(world):
    """A domain is ours only when declared (STEP-04) — so a company node under another key, NAMED for the
    founder's company as the tenant records it, is us too: the served golden probe's F02."""
    store, now = world
    files = _files_of(store)
    with store.engine.begin() as c:
        c.execute(text("update orgs set company = 'Nimbus Labs', name = 'Arjun Rao' where id = :o"),
                  {"o": ORG})
        ours = store.find_or_create_node(c, org_id=ORG, node_type="company", canonical_key="nimbus.in",
                                         display_name="Nimbus Labs Private Limited", event_id="evt_a_in")
        c.execute(text("update context_correlations set anchor_node_id = :n "
                       " where org_id = :o and anchor_node_id = :a"),
                  {"n": ours, "o": ORG, "a": files["evt_a_in"]})
    receipt, expert = _pass(store, now)
    assert receipt["ours"] == 1 and len(expert.prompts) == 1
    assert [r.file_id for r in _rows(store)] == [files["evt_k_in"]]


def test_a_tenant_without_the_feature_or_a_model_reads_no_file(world, monkeypatch):
    store, now = world
    with store.engine.begin() as c:
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})
    receipt, expert = _pass(store, now)
    assert receipt == {"skipped": "expert_review_not_activated"} and expert.prompts == []
    with store.engine.begin() as c:
        c.execute(text("insert into l4_activation (org_id, feature, enabled_by) "
                       "values (:o, 'expert_review', 'test')"), {"o": ORG})
    from genios_engine.reason import llm_sites
    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: None)    # production's own door
    assert P.expert_pass(store=store, org_id=ORG, now=now) == {"skipped": "no_model_configured"}
    assert _rows(store) == []


def test_the_model_comes_through_the_r_sites_own_door(world, monkeypatch):
    """`llm_sites.make_site_client`, read when the pass runs — the door the golden runner opens
    (`tests/replays/engine_runner.py`). ⛔ Found at the build of M32.C5.L-data.V0.U01: a name bound
    at import never saw the door, and a golden run would have skipped the pass."""
    from genios_engine.reason import llm_sites
    store, now = world
    expert = _Expert()
    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: expert)
    receipt = P.expert_pass(store=store, org_id=ORG, now=now)
    assert receipt["reviewed"] == {R.VALID: 2} and len(expert.prompts) == 2


def test_a_failed_review_waits_before_it_is_tried_again(world):
    store, now = world

    class _Down(_Expert):
        def call(self, prompt, *, max_tokens=400):
            self.prompts.append(prompt)
            raise RuntimeError("connection reset")
    receipt, down = _pass(store, now, llm=_Down())
    assert receipt["reviewed"] == {R.FAILED: 2}
    soon, expert = _pass(store, now + timedelta(minutes=15))
    assert expert.prompts == [] and soon["waiting"] == {"failed_lately": 2}
    later, expert = _pass(store, now + P.RETRY_FAILED_AFTER)
    assert later["reviewed"] == {R.VALID: 2}


def test_a_kind_proposal_that_fails_is_no_failed_pass(world, monkeypatch):
    """The review is kept and the pass goes on; the proposal's failure is counted (`unreadable`)."""
    store, now = world

    class _Proposing(_Expert):
        def call(self, prompt, *, max_tokens=400):
            answer = super().call(prompt, max_tokens=max_tokens)
            evidence = answer.parsed["facts"][0]["evidence"]
            answer.parsed["proposed_kind"] = {"kind": "investor", "why": "a fund", "evidence": evidence}
            return answer

    def _broken(*_a, **_kw):
        raise RuntimeError("the brief store is down")
    monkeypatch.setattr(P, "propose_kind", _broken)
    receipt, expert = _pass(store, now, llm=_Proposing())
    assert receipt["reviewed"] == {R.VALID: 2} and receipt["unreadable"] == 2
    assert receipt["proposed_kinds"] == 0 and len(_rows(store)) == 2


def test_the_sweep_runs_the_pass_first_wrapped_and_hands_on_what_it_covers():
    """`runner.run_all` calls it once, inside a try — a failed pass is never a failed sweep — and
    BEFORE the compiled lane, which it hands the files its valid reviews cover (M33, `06` D1).
    ⛔ Moved deliberately by M33.C1.L-integration.V2.U07: it was pinned LAST while nothing read a
    review for a decision (M32, shadow)."""
    fn = ast.parse(inspect.getsource(runner.run_all)).body[0]

    def _calls(name):
        return [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", "")) == name]
    calls, compiled = _calls("expert_pass"), _calls("shadow_compile")
    assert len(calls) == 1 and len(compiled) == 1
    wrapped = [t for t in ast.walk(fn) if isinstance(t, ast.Try)
               and any(n is calls[0] for b in t.body for n in ast.walk(b))]
    assert wrapped, "the expert pass is not wrapped"
    assert calls[0].lineno < compiled[0].lineno, "the compiled lane runs before the review decides"
    handed = {k.arg: ast.unparse(k.value) for k in compiled[0].keywords}
    assert handed.get("covered") == "covered", handed
    assigned = [n for n in ast.walk(fn) if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "covered" for t in n.targets)]
    assert len(assigned) == 1 and "expert.get('covered')" in ast.unparse(assigned[0].value)
    returned = [n for n in ast.walk(fn) if isinstance(n, ast.Return)][-1]
    assert "expert" in [k.value for k in returned.value.keys]


# ── M33.C1.L-data.V0.U06 · which files a valid review now answers ──────────────────────────────────
def _valid(store, files):
    with store.engine.connect() as c:
        return {f: R.latest_valid(c, ORG, f).fingerprint for f in files}


def test_the_pass_says_which_files_its_valid_reviews_cover(world):
    """`covered`: file → the fingerprint of the VALID review that answers it now — the one written this
    pass, the fingerprint's own when unchanged, the last one when nothing has touched the file since."""
    store, now = world
    files = _files_of(store)
    first, _ = _pass(store, now)
    reviewed = _valid(store, (files["evt_k_in"], files["evt_a_in"]))
    assert first["covered"] == reviewed
    unchanged, _ = _pass(store, now + timedelta(minutes=15))
    assert unchanged["unchanged"] == 2 and unchanged["covered"] == reviewed
    untouched, _ = _pass(store, now + timedelta(days=11))
    assert untouched["untouched"] == 2 and untouched["covered"] == reviewed, \
        "nothing touched either file: the last valid review still answers it"


def test_a_file_whose_new_mail_is_reviewed_is_covered_by_the_new_review(world):
    from tests.context.workstream_world import process
    store, now = world
    files = _files_of(store)
    _pass(store, now)
    before = _valid(store, (files["evt_k_in"],))[files["evt_k_in"]]
    process(store, ORG, event_id="evt_k_again", sender=KUNAL, thread="t_k", at=now - timedelta(hours=2))
    receipt, _ = _pass(store, now + timedelta(minutes=15))
    after = _valid(store, (files["evt_k_in"],))[files["evt_k_in"]]
    assert after != before and receipt["covered"][files["evt_k_in"]] == after


def test_no_valid_review_covers_nothing_failed_refused_or_carried(world):
    """A failed review, one waiting to be retried, one refused on substance, a file carried for want of
    budget — each is decided as before, situation by situation: none of them is covered."""
    from genios_engine.reason.bundle.budget import NarrativeBudget
    from genios_engine.reason.bundle.sites import SITE_EXPERT
    store, now = world

    class _Down(_Expert):
        def call(self, prompt, *, max_tokens=400):
            self.prompts.append(prompt)
            raise RuntimeError("connection reset")
    failed, _ = _pass(store, now, llm=_Down())
    assert failed["reviewed"] == {R.FAILED: 2} and failed["covered"] == {}
    waiting, _ = _pass(store, now + timedelta(minutes=15))
    assert waiting["waiting"] == {"failed_lately": 2} and waiting["covered"] == {}

    class _Uncited(_Expert):
        def call(self, prompt, *, max_tokens=400):
            answer = super().call(prompt, max_tokens=max_tokens)
            answer.parsed["facts"] = [{"claim": "they wrote", "evidence": ["evt_never_shown"]}]
            return answer
    refused, _ = _pass(store, now + P.RETRY_FAILED_AFTER, llm=_Uncited())
    assert refused["reviewed"] == {R.REFUSED: 2} and refused["covered"] == {}
    standing, _ = _pass(store, now + P.RETRY_FAILED_AFTER + timedelta(minutes=15))
    assert standing["unchanged"] == 2 and standing["covered"] == {}, "a standing refusal answers nothing"
    quiet, _ = _pass(store, now + P.RETRY_FAILED_AFTER + timedelta(days=11))
    assert quiet["untouched"] == 2 and quiet["covered"] == {}, \
        "nothing touched since the refusal, and a refusal still answers nothing"


def test_a_file_carried_for_want_of_budget_is_not_covered(world):
    from genios_engine.reason.bundle.budget import NarrativeBudget
    from genios_engine.reason.bundle.sites import SITE_EXPERT
    store, now = world
    budget = NarrativeBudget.for_site(SITE_EXPERT, org_id=ORG)
    budget.charge(2_000_000)
    receipt, _ = _pass(store, now, budget=budget)
    assert receipt["carried"] == 1 and receipt["covered"] == {}
