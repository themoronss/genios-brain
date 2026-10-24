"""GeniOS-011 S27.U1 · the drafter sees what is in motion, and proposes a goal for it.

    pytest tests/reason/test_the_drafter_sees_what_is_in_motion.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_the_drafter_sees_what_is_in_motion.py -q

The founder's F2: an accelerator application he is pursuing never became a goal, and he had to type
his goals by hand. Three things kept it out (audit `goals-antler-cannot-appear-today`):

  * the weekly review drafted only for a tenant with at least one ACCEPTED line, so a tenant with an
    empty brief never got a first draft — and a week whose draft the model failed was lost;
  * the drafter read memory patterns only — correspondents, domains, waves, introducers, series,
    deadlines, thread objectives — never the founder's files, their open situations, or the brief's
    in-motion lines, so it never saw the work in motion;
  * nothing stopped it proposing the same work again in other words, week after week.

The synthetic analogue is F17's (`tests/replays/specs/founder/F17.json`): Gulf Launchpad, an
accelerator, moves the founder's application to interview. Real names never appear
(`tests/replays/founder_case.REAL_NAMES`).
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.llm.client import LLMResult
from genios_engine.platform import company_brief_store as store
from genios_engine.reason import brief_drafter as D
from genios_engine.reason import brief_patterns as P
from genios_engine.reason import brief_review as R
from tests.context.workstream_world import FOUNDER
from tests.context.workstream_world import later
from tests.context.workstream_world import mention
from tests.context.workstream_world import process
from tests.context.workstream_world import reset
from tests.context.workstream_world import tenant

ORG = "org_g011_s27u1_gulf"
GULF = "gulflaunchpad.test"
AMIRA = "amira@gulflaunchpad.test"
KESTREL = "rahul@kestrelcap.test"
NOW = later(29)                    # 2026-10-02 18:00 UTC, a Friday of ISO week 40


# ── a stand-in for the model ─────────────────────────────────────────────────────────────────

class _ChiefOfStaff:
    """Reads the patterns in its prompt, as the model is asked to, and proposes one goal for each
    programme in motion — an in-motion line of kind `program` that names a file — citing the file, its
    open situations and the line. Each call words the goal anew, as a model does."""

    model = "claude-sonnet-5"
    WORDS = ("Get into the {name} accelerator cohort", "Win a place in the {name} programme")

    def __init__(self, *, fail_first: bool = False):
        self.prompts: list[str] = []
        self.fail_first = fail_first

    def call(self, prompt, *, max_tokens=4096, **_kw):
        self.prompts.append(prompt)
        if self.fail_first and len(self.prompts) == 1:
            return LLMResult(parsed={}, raw="", model=self.model, input_tokens=900, output_tokens=0,
                             ok=False, error="overloaded")
        items = [json.loads(line) for line in prompt.split("PATTERNS:\n", 1)[1].splitlines()
                 if line.strip()]
        by_id = {i["id"]: i for i in items}
        words = self.WORDS[(len(self.prompts) - 1) % len(self.WORDS)]
        lines = []
        for item in items:
            if item["kind"] != "in_motion" or item.get("work_kind") != "program" or not item.get("file"):
                continue
            f = by_id[item["file"]]
            on_it = [s["id"] for s in items if s["kind"] == "situation" and s.get("file") == f["id"]]
            lines.append({"section": "goals", "text": words.format(name=f["name"]), "address": None,
                          "domain": None, "kind": None, "evidence": [f["id"], *on_it, item["id"]]})
        return LLMResult(parsed={"lines": lines}, raw="", model=self.model, input_tokens=1200,
                         output_tokens=90)


# ── hermetic: the prompt, and one goal per piece of work ──────────────────────────────────────

WORK = {
    "company": "Nimbus Labs", "founder": "Arjun Rao", "us": [FOUNDER], "window_days": 180,
    "items": [
        {"id": "p1", "kind": "correspondent", "address": AMIRA, "name": "Amira Saleh",
         "from_them": 1, "to_them": 1, "first": "2026-09-03", "last": "2026-10-01"},
        {"id": "p2", "kind": "file", "file_id": "node_gulf", "name": "Gulf Launchpad",
         "type": "company", "address": None, "domain": GULF, "role": None, "work_kind": None,
         "areas": ["general"], "events": 2, "first": "2026-09-03", "last": "2026-10-01",
         "whose_move": "ours", "asks_ours": 0, "asks_theirs": 0, "goal": None},
        {"id": "p3", "kind": "situation", "situation_id": "sit_gulf", "file": "p2",
         "file_id": "node_gulf", "name": "Gulf Launchpad", "type": "relationship",
         "area": "general", "status": "active", "first": "2026-09-03", "last": "2026-10-01"},
        {"id": "p4", "kind": "in_motion", "line_id": "cbl_gulf", "file": "p2", "file_id": "node_gulf",
         "text": "Program · Gulf Launchpad — proposed by the expert", "status": "proposed",
         "work_kind": "program", "proposed_by": "expert_review", "address": None, "domain": GULF,
         "goal": None},
    ],
}


def _goal(text, evidence):
    return {"section": "goals", "text": text, "address": None, "domain": None, "kind": None,
            "evidence": list(evidence)}


class _Engine:
    def connect(self):
        return _Ctx()

    def begin(self):
        return _Ctx()


class _Ctx:
    def __enter__(self):
        return object()

    def __exit__(self, *exc):
        return False


class _Says:
    model = "claude-sonnet-5"

    def __init__(self, lines):
        self.lines, self.prompts = lines, []

    def call(self, prompt, *, max_tokens=4096, **_kw):
        self.prompts.append(prompt)
        return LLMResult(parsed={"lines": self.lines}, raw="", model=self.model, input_tokens=900,
                         output_tokens=120)


@pytest.fixture
def seams(monkeypatch):
    from genios_engine.contracts.company_brief import CompanyBrief
    from genios_engine.platform import company_brief

    proposed: list[dict] = []
    patterns = {"value": WORK}
    monkeypatch.setattr(P, "patterns_for", lambda c, org, *, now: patterns["value"])
    monkeypatch.setattr(company_brief, "brief_for", lambda c, org: CompanyBrief(org_id=org))
    monkeypatch.setattr(store, "propose", lambda c, **kw: proposed.append(kw) or f"cbl_{len(proposed)}")
    return proposed, patterns


@pytest.mark.unit
def test_the_prompt_shows_the_work_in_motion_and_asks_a_goal_for_each_piece_of_it():
    prompt = D.build_prompt(WORK)
    rendered = prompt.split("PATTERNS:\n", 1)[1]
    for kind in ("file", "situation", "in_motion"):
        assert f'"kind": "{kind}"' in rendered, f"the prompt never shows a {kind} pattern"
    rules = prompt.split("Return JSON only")[0]
    assert "the work in motion" in rules.lower()
    assert "A goal is an END the company drives to" in rules and "cites EVERY file" in rules
    assert "already holds" not in prompt            # the base prompt holds no brief
    assert D.PROMPT_VERSION == "company-brief-draft.v5"


@pytest.mark.unit
def test_a_goal_resting_on_work_a_goal_already_rests_on_is_not_proposed_again(seams):
    proposed, patterns = seams
    patterns["value"] = {**WORK, "goal_work": ["file:node_gulf"]}
    model = _Says([_goal("Get into the Gulf Launchpad cohort", ("p3",))])
    out = D.draft_company_brief(_Engine(), ORG, model, now=NOW)
    assert proposed == [] and out.proposed == 0 and out.lines == ()
    assert len(out.refused) == 1 and "file:node_gulf" in out.refused[0], out.refused


@pytest.mark.unit
def test_two_goals_on_one_piece_of_work_keep_the_first_and_other_sections_are_untouched(seams):
    proposed, _ = seams
    model = _Says([_goal("Get into the Gulf Launchpad cohort", ("p2",)),
                   _goal("Win the Gulf Launchpad interview", ("p4",)),
                   _goal("Raise the pre-seed round", ("p1",)),
                   {"section": "in_motion", "text": "Program · Gulf Launchpad", "address": None,
                    "domain": GULF, "kind": "program", "evidence": ["p2"]}])
    out = D.draft_company_brief(_Engine(), ORG, model, now=NOW)
    assert [(p["section"], p["words"]) for p in proposed] == [
        ("goals", "Get into the Gulf Launchpad cohort"), ("goals", "Raise the pre-seed round"),
        ("in_motion", "Program · Gulf Launchpad")]
    assert len(out.refused) == 1 and "Win the Gulf Launchpad interview" in out.refused[0]


@pytest.mark.unit
def test_h22_a_company_goal_is_served_by_every_file_it_cites_and_holds_none_of_them(seams):
    """G012 H-22: "raise the pre-seed" cites two investors' files — they SERVE it; a piece among them may still have a
    goal of its own, and the same company goal in other words is refused."""
    from genios_engine.platform.company_brief_store import SERVES
    proposed, patterns = seams
    two_files = {**WORK, "items": [*WORK["items"], {"id": "p9", "kind": "file", "file_id": "node_kestrel",
                                                    "name": "Kestrel Capital"}],
                 "goal_work": ["file:node_kestrel"], "goal_texts": ["Hire a founding engineer"]}
    patterns["value"] = two_files
    model = _Says([_goal("Raise the pre-seed round", ("p2", "p9")),
                   _goal("Close the pre-seed round for the company", ("p2", "p9")),
                   _goal("Get into the Gulf Launchpad cohort", ("p2",))])
    out = D.draft_company_brief(_Engine(), ORG, model, now=NOW)
    assert [p["words"] for p in proposed] == ["Raise the pre-seed round", "Get into the Gulf Launchpad cohort"], \
        "the company goal is not held by a piece already served, and a piece's own goal still stands"
    company = proposed[0]["evidence"]
    assert {e.get(SERVES) for e in company if e.get(SERVES)} == {"file:node_gulf", "file:node_kestrel"}
    assert not any(e.get("file_id") for e in company), "a company goal is born from no one file"
    assert len(out.refused) == 1 and "the same goal in other words" in out.refused[0], out.refused


@pytest.mark.unit
def test_h22_a_company_goal_already_in_force_is_not_proposed_again_in_other_words(seams):
    proposed, patterns = seams
    patterns["value"] = {**WORK, "items": [*WORK["items"], {"id": "p9", "kind": "file", "file_id": "node_kestrel"}],
                         "goal_texts": ["Raise the pre-seed round"]}
    out = D.draft_company_brief(_Engine(), ORG, _Says([_goal("Close the pre-seed round for us", ("p2", "p9"))]),
                                now=NOW)
    assert proposed == [] and "the same goal in other words" in out.refused[0]


@pytest.mark.unit
def test_h23_the_people_a_goal_names_serve_it_through_their_files(seams):
    """G012 H-23: the drafter cited Boardy's introductions BY THEIR PEOPLE and the goal rested on no file — so no card
    carried it. Each person's file serves it; two people's files make it the company's; a pattern naming no one, no
    file."""
    from genios_engine.platform.company_brief_store import SERVES
    proposed, patterns = seams
    items = [*WORK["items"],
             {"id": "p20", "kind": "file", "file_id": "node_sanchit", "address": "sanchit@cortex.test"},
             {"id": "p21", "kind": "file", "file_id": "node_nick", "address": "nick@bean.test"},
             {"id": "p22", "kind": "correspondent", "address": "sanchit@cortex.test", "inbound": 3},
             {"id": "p23", "kind": "correspondent", "address": "nick@bean.test", "inbound": 2},
             {"id": "p24", "kind": "wave", "day": "2026-08-11", "count": 12}]
    patterns["value"] = {**WORK, "items": items}
    D.draft_company_brief(_Engine(), ORG, _Says([_goal("Turn the intros into partners", ("p22", "p23", "p24"))]),
                          now=NOW)
    [goal] = proposed
    assert {e[SERVES] for e in goal["evidence"] if e.get(SERVES)} == {"file:node_sanchit", "file:node_nick"}
    assert not any(e.get("file_id") for e in goal["evidence"])
    proposed.clear()
    patterns["value"] = {**WORK, "items": items, "goal_texts": ["Turn the introductions into partners"]}
    out = D.draft_company_brief(_Engine(), ORG, _Says([_goal("Turn the intros into partners", ("p22", "p23"))]),
                                now=NOW)
    assert proposed == [] and "the same goal in other words" in out.refused[0], \
        "two people's files make it the company's goal, ruled by its words"


@pytest.mark.unit
def test_a_pattern_stands_for_its_file_and_its_line():
    assert P.work_of(WORK["items"][1]) == frozenset({"file:node_gulf"})
    assert P.work_of(WORK["items"][2]) == frozenset({"file:node_gulf"})
    assert P.work_of(WORK["items"][3]) == frozenset({"file:node_gulf", "line:cbl_gulf"})
    assert P.work_of(WORK["items"][0]) == frozenset()
    # Stored evidence is the item itself under its pattern id — it stands for the same work.
    assert P.work_of({"pattern": "p4", **{k: v for k, v in WORK["items"][3].items() if k != "id"}}) \
        == frozenset({"file:node_gulf", "line:cbl_gulf"})


# ── Postgres: the synthetic F17 world ────────────────────────────────────────────────────────

@pytest.fixture
def world(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _f17(pg) -> str:
    """Gulf Launchpad moves the founder's application to interview (F17), and the expert, reading the
    file, proposed its kind of work — a pending in-motion line (`reason/expert/kind_proposal`). The
    founder has accepted no line of the brief."""
    from genios_engine.context.situations import refresh_situations

    process(pg, ORG, event_id="evt_s27u1_mine", sender=FOUNDER, recipients=(AMIRA,), thread="t-s27u1-gulf",
            mentions=(mention("Amira"),), at=later(0))
    process(pg, ORG, event_id="evt_s27u1_next", sender=AMIRA, sender_name="Amira Saleh",
            thread="t-s27u1-gulf", at=later(28),
            mentions=(mention("Amira Saleh"), mention("Gulf Launchpad", "organization")))
    refresh_situations(pg, ORG, eval_time=NOW)
    with pg.engine.begin() as c:
        return store.propose(c, org_id=ORG, section="in_motion", proposed_by="expert_review",
                             words="Program · Gulf Launchpad — proposed by the expert: the cohort 9 "
                                   "application moved to interview",
                             domain=GULF, kind="program", at=later(28.5))


def _gulf_node(pg) -> str:
    with pg.engine.connect() as c:
        return c.execute(text("select node_id from graph_nodes where org_id = :o and canonical_key = :k "
                              "and valid_to is null"), {"o": ORG, "k": GULF}).scalar_one()


def _patterns(pg) -> dict:
    with pg.engine.connect() as c:
        return P.patterns_for(c, ORG, now=NOW)


def _of(patterns, kind) -> list[dict]:
    return [i for i in patterns["items"] if i["kind"] == kind]


def _goals(pg) -> list:
    with pg.engine.connect() as c:
        return c.execute(text(
            "select line_id, status, text, proposed_by, evidence from company_brief_lines "
            " where org_id = :o and section = 'goals' order by proposed_at, line_id"),
            {"o": ORG}).fetchall()


@pytest.mark.pg
def test_the_patterns_show_the_file_its_open_situation_and_the_in_motion_line(world):
    line = _f17(world)
    node = _gulf_node(world)
    p = _patterns(world)
    files = [f for f in _of(p, "file") if f["file_id"] == node]
    assert len(files) == 1, _of(p, "file")
    gulf = files[0]
    assert (gulf["name"], gulf["domain"], gulf["type"], gulf["last"]) == (
        "Gulf Launchpad", GULF, "company", "2026-10-01")
    situations = [s for s in _of(p, "situation") if s["file_id"] == node]
    assert [(s["file"], s["status"]) for s in situations] == [(gulf["id"], "active")]
    assert situations[0]["situation_id"].startswith("sit_")
    moving = _of(p, "in_motion")
    assert [(m["line_id"], m["status"], m["work_kind"], m["domain"], m["file"], m["proposed_by"])
            for m in moving] == [(line, "proposed", "program", GULF, gulf["id"], "expert_review")]
    # Every item keeps its own pattern id, in order, and a counterparty it names may be proposed.
    assert [i["id"] for i in p["items"]] == [f"p{n}" for n in range(1, len(p["items"]) + 1)]
    assert GULF in P.domains_in(p)
    assert p["goal_work"] == []
    assert _patterns(world) == p                                    # the same memory, the same patterns


@pytest.mark.pg
def test_an_ended_situation_a_rejected_line_and_a_private_file_are_not_in_motion(world):
    _f17(world)
    process(world, ORG, event_id="evt_s27u1_kestrel", sender=KESTREL, thread="t-s27u1-kestrel",
            mentions=(mention("Kestrel Capital", "organization"),), at=later(20))
    process(world, ORG, event_id="evt_s27u1_hidden", sender="someone@hidden-s27u1.test",
            thread="t-s27u1-hidden", at=later(21))
    from genios_engine.context.situations import refresh_situations
    refresh_situations(world, ORG, eval_time=NOW)
    with world.engine.begin() as c:
        c.execute(text("update source_events set visibility_scope = 'private' "
                       " where org_id = :o and event_id = 'evt_s27u1_hidden'"), {"o": ORG})
        kestrel = c.execute(text("select node_id from graph_nodes where org_id = :o "
                                 "and canonical_key = 'kestrelcap.test' and valid_to is null"),
                            {"o": ORG}).scalar_one()
        c.execute(text("update context_situations set status = 'resolved', resolved_by = 'human', "
                       "resolved_at = :at where org_id = :o and anchor_node_id = :n"),
                  {"o": ORG, "n": kestrel, "at": later(25)})
        no = store.propose(c, org_id=ORG, section="in_motion", words="Investor · Kestrel Capital",
                           proposed_by="expert_review", domain="kestrelcap.test", kind="investor",
                           at=later(26))
        store.reject(c, org_id=ORG, line_id=no, decided_by="founder", at=later(27))
    p = _patterns(world)
    rendered = json.dumps(p)
    assert "hidden-s27u1.test" not in rendered                     # captured privately
    assert kestrel in {f["file_id"] for f in _of(p, "file")}        # its file is still in memory…
    assert kestrel not in {s["file_id"] for s in _of(p, "situation")}   # …its situation ended
    assert [m["work_kind"] for m in _of(p, "in_motion")] == ["program"]  # the rejected line is gone


@pytest.mark.pg
def test_a_tenant_with_no_accepted_line_is_reviewed(world):
    _f17(world)
    with world.engine.connect() as c:
        assert c.execute(text("select count(*) from company_brief_lines where org_id = :o "
                              "and status = 'accepted'"), {"o": ORG}).scalar() == 0
        assert ORG in R.tenants(c)


@pytest.mark.pg
def test_an_accelerator_application_in_motion_becomes_a_proposed_goal_naming_it(world):
    """The first weekly draft of a tenant whose brief holds no accepted line proposes the
    programme in motion as a goal — pending, for the founder to accept — with what it rests on."""
    line = _f17(world)
    node = _gulf_node(world)
    model = _ChiefOfStaff()
    out = R.run_company_brief_reviews(world.engine, now=NOW, llm=model, orgs=[ORG])
    assert (out["reviewed"], out["failed"], out["proposed"]) == (1, 0, 1), out
    goals = _goals(world)
    assert [(g.status, g.text, g.proposed_by) for g in goals] == [
        ("proposed", "Get into the Gulf Launchpad accelerator cohort", "weekly")]
    rests_on = {(e["kind"], e.get("file_id"), e.get("line_id")) for e in goals[0].evidence}
    assert ("file", node, None) in rests_on and ("in_motion", node, line) in rests_on
    assert any(e["kind"] == "situation" for e in goals[0].evidence)
    with world.engine.connect() as c:
        assert [(r.outcome, r.proposed) for r in c.execute(text(
            "select outcome, proposed from company_brief_reviews where org_id = :o"), {"o": ORG})] == [
            ("proposed", 1)]


@pytest.mark.pg
def test_the_second_run_proposes_nothing_new(world):
    """Reworded the next time, the same programme is the same work: a goal already rests on it."""
    _f17(world)
    model = _ChiefOfStaff()
    first = D.draft_company_brief(world.engine, ORG, model, now=NOW, proposed_by="weekly")
    assert first.proposed == 1
    assert _of(_patterns(world), "file")[0]["goal"] == "proposed"
    second = D.draft_company_brief(world.engine, ORG, model, now=NOW + timedelta(days=7),
                                   proposed_by="weekly")
    assert len(model.prompts) == 2 and "Win a place in the Gulf Launchpad programme" in json.dumps(
        [p for p in second.refused])
    assert second.proposed == 0 and second.lines == ()
    assert [g.text for g in _goals(world)] == ["Get into the Gulf Launchpad accelerator cohort"]


@pytest.mark.pg
def test_a_failed_week_is_retried_the_next_tick_and_a_reviewed_week_is_not(world):
    _f17(world)
    model = _ChiefOfStaff(fail_first=True)
    failed = R.run_company_brief_reviews(world.engine, now=NOW, llm=model, orgs=[ORG])
    assert (failed["failed"], failed["reviewed"]) == (1, 0), failed
    retried = R.run_company_brief_reviews(world.engine, now=NOW + timedelta(hours=6), llm=model,
                                          orgs=[ORG])
    assert (retried["failed"], retried["reviewed"], retried["proposed"]) == (0, 1, 1), retried
    again = R.run_company_brief_reviews(world.engine, now=NOW + timedelta(hours=12), llm=model,
                                        orgs=[ORG])
    assert again["already_this_week"] == 1 and len(model.prompts) == 2
    with world.engine.connect() as c:
        rows = c.execute(text("select week_key, outcome, proposed, started_at, finished_at "
                              "  from company_brief_reviews where org_id = :o"), {"o": ORG}).fetchall()
    assert [(r.week_key, r.outcome, r.proposed) for r in rows] == [("2026-W40", "proposed", 1)]
    assert rows[0].started_at == NOW + timedelta(hours=6) == rows[0].finished_at
