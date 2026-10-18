"""STEP-07 · resolution reads the company brief — before the situation and the fenced message.

    .venv/bin/python -m pytest tests/context/test_resolution_reads_the_company_brief.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (adds a real sweep and its audit rows)

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U03`. M-4 asks one narrow question — does THIS message say THIS
obligation is complete? — and asked it with no idea whose company the obligation belonged to
(`speedrun008/YC-II W27/` STEP-07 §1, §8.1). Its prompt now carries the tenant's brief as background:
its own paragraph after the instruction spine, before the situation, the obligations and the fenced
message. `detect_resolutions` reads the brief once per sweep, only when a model will be asked, and
every audit row names the brief it was read under (`prompt_version` = `m4…+cb-…`). A tenant with no
accepted line sends exactly the prompt it sent before and records `PROMPT_VERSION` as before.
"""
from __future__ import annotations

import re
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.context.lifecycle import resolution
from genios_engine.context.lifecycle import store as store_mod
from genios_engine.context.lifecycle.contract import PROMPT_VERSION, Message, Obligation
from genios_engine.context.lifecycle.prompt import build_prompt
from genios_engine.context.lifecycle.store import SituationRow
from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose

from .lifecycle.conftest import AT, ScriptedModel, answer_for
from .lifecycle.test_resolution import RESOLUTION_TEXT, _drop, _ids, _seed

ORG = "org_s07_resolution"
OBLIGATIONS = (Obligation("ob_msa", "countersign the MSA", "priya@acme.example"),)
MESSAGE = Message(event_id="evt_reply", text=RESOLUTION_TEXT, sender_email="priya@acme.example",
                  occurred_at=AT)
BRIEF = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                us=("arjun@nimbuslabs.test",),
                lines=[CompanyBriefLine(line_id="l1", section="goals",
                                        text="raise the pre-seed round")])
BLOCK = BRIEF.prompt_block()
NONCE = "0123456789abcdef"
_FENCE = re.compile(r"<<<(CONTENT|END)_[0-9a-f]{16}>>>")


def _same_fence(prompt: str) -> str:
    """The prompt with its fence nonce — 64 fresh bits per call, by design — made one constant."""
    return _FENCE.sub(r"<<<\1_" + NONCE + ">>>", prompt)


def test_the_block_is_its_own_paragraph_before_the_situation_and_the_message():
    """(a) After the instruction spine, before the subject, the obligations and the fence."""
    p = build_prompt(subject="countersign the MSA", obligations=OBLIGATIONS, message=MESSAGE,
                     prior=True, nonce=NONCE, company_brief=BLOCK)
    at = p.index(BLOCK)
    assert p.index("You read ONE message that landed on an open business situation") < at
    assert p.index('"speaker_role_said"') < at, "the brief must not split the instruction spine"
    assert at < p.index("SITUATION SUBJECT:") < p.index("OPEN OBLIGATIONS")
    assert at < p.index("LAYER 1 NOTE") < p.index(f"<<<CONTENT_{NONCE}>>>")
    # The message itself, after its fence (the spine's worked examples quote "we signed" too).
    assert at < p.index(f"<<<CONTENT_{NONCE}>>>") < p.index(RESOLUTION_TEXT), (
        "the brief comes before the message, outside its fence")
    assert "\n\n" + BLOCK.strip() + "\n\n" in p, "the brief is its own paragraph"


@pytest.mark.parametrize("prior", [False, True])
def test_no_brief_leaves_the_prompt_byte_for_byte(prior):
    """(b) No accepted line: the prompt is the builder's own without the parameter."""
    kw = dict(subject="countersign the MSA", obligations=OBLIGATIONS, message=MESSAGE,
              prior=prior, nonce=NONCE)
    plain = build_prompt(**kw)
    assert build_prompt(**kw, company_brief="") == plain
    assert build_prompt(**kw, company_brief=CompanyBrief(org_id=ORG).prompt_block()) == plain
    assert "COMPANY BRIEF" not in plain


# ── the sweep, with its database reads stood in ──────────────────────────────────────────────────
class _Engine:
    """Nothing may reach it: every read the sweep makes is stood in below."""

    def connect(self):
        return self

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def sweep(monkeypatch):
    """`detect_resolutions` over one situation with two unexamined messages, every gather stood
    in, the audit writer and the brief recorded. Returns `(run, seen)`."""
    seen: dict = {"asked": [], "runs": []}
    row = SituationRow(situation_id="sit_1", correlation_id="corr_1", anchor_node_id="node_acme",
                       status="active", resolved_by=None, resolved_at=None, last_seen_at=AT,
                       deal_stage=None)
    messages = [{"situation_id": "sit_1", "correlation_id": "corr_1", "event_id": eid,
                 "occurred_at": AT - timedelta(hours=n), "sender_email": "priya@acme.example",
                 "text": body}
                for n, (eid, body) in enumerate((("evt_reply", RESOLUTION_TEXT),
                                                 ("evt_ask", "Can you countersign the MSA?")))]
    monkeypatch.setattr(store_mod, "situations_to_examine", lambda c, o: [row])
    monkeypatch.setattr(store_mod, "obligations_for", lambda c, o, ids: {"corr_1": OBLIGATIONS})
    monkeypatch.setattr(store_mod, "unexamined_messages", lambda c, o, ids, **kw: messages)
    monkeypatch.setattr(store_mod, "extraction_outputs", lambda c, o, ids: {})
    monkeypatch.setattr(store_mod, "calls_today", lambda c, o, **kw: (0, {}))
    monkeypatch.setattr(store_mod, "claims_for", lambda c, o, ids: {})
    monkeypatch.setattr(resolution, "_attempts_by_subject", lambda c, o, **kw: {})
    monkeypatch.setattr(resolution, "record_model_run",
                        lambda engine, **kw: seen["runs"].append(kw) or "run_1")

    def run(brief: CompanyBrief, llm=None):
        def current(source, org_id):
            seen["asked"].append((source, org_id))
            return brief
        monkeypatch.setattr("genios_engine.platform.company_brief.current", current)
        store = SimpleNamespace(engine=_Engine())
        seen["store"] = store
        llm = llm if llm is not None else ScriptedModel()   # answers nothing: no claim is written
        return resolution.detect_resolutions(store, ORG, llm=llm, eval_time=AT,
                                             internal_emails=["arjun@nimbuslabs.test"]), llm
    return run, seen


def test_every_prompt_of_a_sweep_carries_the_brief_read_once(sweep):
    """(c) Two messages, two calls: both prompts carry the brief, read ONCE, from the store's
    engine — and both audit rows name the brief's version beside the prompt's."""
    run, seen = sweep
    out, llm = run(BRIEF)
    assert out.calls == 2 and len(llm.prompts) == 2
    assert seen["asked"] == [(seen["store"].engine, ORG)], "once per sweep, from store.engine"
    for prompt in llm.prompts:
        at = prompt.index(BLOCK)
        assert at < prompt.index("SITUATION SUBJECT:") < prompt.index("<<<CONTENT_")
    assert [r["prompt_version"] for r in seen["runs"]] == [f"{PROMPT_VERSION}+{BRIEF.version}"] * 2
    assert [r["prompt"] for r in seen["runs"]] == llm.prompts


def test_no_brief_is_the_old_prompt_and_the_old_prompt_version(sweep):
    """(b)/(d) A tenant with no accepted line: the prompt is what `build_prompt` makes without the
    parameter, and the audit row records `PROMPT_VERSION` alone."""
    run, seen = sweep
    out, llm = run(CompanyBrief(org_id=ORG))
    assert out.calls == 2
    expected = _same_fence(build_prompt(subject="countersign the MSA", obligations=OBLIGATIONS,
                                        message=MESSAGE, prior=False))
    assert _same_fence(llm.prompts[0]) == expected
    assert all("COMPANY BRIEF" not in p for p in llm.prompts)
    assert [r["prompt_version"] for r in seen["runs"]] == [PROMPT_VERSION] * 2


def test_the_recorded_prompt_version_moves_with_the_brief(sweep):
    """(d) Two briefs, two prompt versions; neither is `PROMPT_VERSION` alone."""
    run, seen = sweep
    other = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                    lines=[CompanyBriefLine(line_id="l2", section="goals",
                                            text="land three design partners")])
    run(BRIEF)
    run(other)
    versions = {r["prompt_version"] for r in seen["runs"]}
    assert versions == {f"{PROMPT_VERSION}+{BRIEF.version}", f"{PROMPT_VERSION}+{other.version}"}


def test_a_sweep_with_no_model_reads_no_brief(sweep, monkeypatch):
    """Nothing will be asked, so nothing is read: the fallback sweep costs what it cost."""
    run, seen = sweep
    monkeypatch.setattr("genios_engine.platform.company_brief.current",
                        lambda *a: pytest.fail("the brief was read for a sweep with no model"))
    out = resolution.detect_resolutions(SimpleNamespace(engine=_Engine()), ORG, llm=None,
                                        eval_time=AT, internal_emails=["arjun@nimbuslabs.test"])
    assert out.calls == 0 and out.fell_back_to_fact is True


# ── a real sweep, on real Postgres ───────────────────────────────────────────────────────────────
def _model_runs(store, org: str) -> list[str]:
    with store.engine.connect() as c:
        return [r[0] for r in c.execute(text(
            "select prompt_version from l2_model_runs where org_id = :o and site = 'resolution' "
            "order by called_at, run_id"), {"o": org})]


@pytest.mark.pg
def test_a_real_sweep_reads_the_tenants_brief_and_its_audit_rows_name_it(pg_store):
    """(c) + (d) on the M-4 suite's own world: the brief the founder accepted is in every prompt
    the sweep sends, read by the real `current`, and `l2_model_runs` names its version; the same
    world for a tenant with no brief sends no brief and records `PROMPT_VERSION`."""
    from genios_engine.context.lifecycle.resolution import detect_resolutions
    from genios_engine.platform import company_brief as CB
    from genios_engine.platform import company_brief_store as store

    with_brief, without = "org_s07_m4_brief", "org_s07_m4_plain"
    for org in (with_brief, without):
        _drop(pg_store, org)
        CB.invalidate(org)
    try:
        for org in (with_brief, without):
            _seed(pg_store, org, resolution_text=RESOLUTION_TEXT)
        with pg_store.engine.begin() as c:
            store.add(c, org_id=with_brief, section="goals", words="raise the pre-seed round",
                      decided_by="founder", at=AT)
        with pg_store.engine.connect() as c:
            brief = CB.brief_for(c, with_brief)
        assert brief.version and "raise the pre-seed round" in brief.prompt_block()

        llm = ScriptedModel(answers={_ids(with_brief)["reply"]: answer_for(
            RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
            scope=[_ids(with_brief)["commitment"]], quote="we signed yesterday")})
        out = detect_resolutions(pg_store, with_brief, llm=llm, eval_time=AT)
        assert out.calls == 2 and len(llm.prompts) == 2
        for prompt in llm.prompts:
            assert prompt.index(brief.prompt_block()) < prompt.index("SITUATION SUBJECT:")
            assert prompt.index(brief.prompt_block()) < prompt.index("<<<CONTENT_")
        assert _model_runs(pg_store, with_brief) == [f"{PROMPT_VERSION}+{brief.version}"] * 2

        plain = ScriptedModel()
        assert detect_resolutions(pg_store, without, llm=plain, eval_time=AT).calls == 2
        assert all("COMPANY BRIEF" not in p for p in plain.prompts)
        assert _model_runs(pg_store, without) == [PROMPT_VERSION] * 2
    finally:
        for org in (with_brief, without):
            _drop(pg_store, org)
            CB.invalidate(org)
