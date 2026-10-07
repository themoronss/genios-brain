"""STEP-07 · screen insight reads the company brief — in the per-screen task, never in the rulebook.

    .venv/bin/python -m pytest tests/reason/moments/test_screen_insight_reads_the_company_brief.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (adds the route, end to end)

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U08`. The one screen judge was asked about a chat with no idea
whose company it was: no prompt in the product named the company, its goals or its people
(`speedrun008/YC-II W27/` STEP-07 §1, §8.1). It now carries the tenant's brief as its own paragraph
of the per-screen half — after who the manager is and when, before anything about the screen — and
never in the rulebook, which is the prefix every seat reads from the cache for an hour (§8.3 rule 3).
The route reads the brief once per screen, and the screen's key carries the brief's version, so a
changed brief judges a screen once more. A tenant with no accepted line sees the prompt and the key
exactly as they were.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from genios_engine.api import moment_routes
from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose
from genios_engine.reason.moments import screen_insight as SI
from genios_engine.reason.moments import store as M
from tests.test_moments_pg import H, _enable_display, _engine, _workspace, client  # noqa: F401

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
ORG = "org_s07_screen_insight"
SCREEN = "Priya Shah: Can you send the revised pricing by Friday? We need it for the board."
BRIEF = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                us=("arjun@nimbuslabs.test",),
                lines=[CompanyBriefLine(line_id="l1", section="goals",
                                        text="raise the pre-seed round")])
BLOCK = BRIEF.prompt_block()
ARGS = dict(app="whatsapp", screen=SCREEN, facts=[], now_local="Wednesday 2026-10-07 09:00",
            me=["Arjun Rao", "arjun@nimbuslabs.test"])


def test_the_block_is_its_own_paragraph_of_the_per_screen_half():
    """(a) After who and when, before the chat, the facts and the screen — never in the rulebook."""
    p = SI.build_prompt(**ARGS, company_brief=BLOCK)
    at = p.index(BLOCK)
    assert p[:SI.RULEBOOK_CHARS] == SI._RULEBOOK, "the brief moved into the cached prefix"
    assert at > SI.RULEBOOK_CHARS
    assert p.index("For the manager it is now", SI.RULEBOOK_CHARS) < at
    assert at < p.index("This chat so far") < p.index("SCREEN TEXT (newest last):")
    assert at < p.index("<<<", SI.RULEBOOK_CHARS) < p.index(SCREEN, SI.RULEBOOK_CHARS), (
        "the brief must come before the screen and never inside its fence")
    assert "\n\n" + BLOCK.strip() + "\n\n" in p, "the brief is its own paragraph"
    assert "{company_brief}" not in SI._RULEBOOK and SI._TASK.count("{company_brief}") == 1


@pytest.mark.parametrize("extra", [
    {},
    {"summary": "Earlier: pricing", "profile": "Founder of Nimbus Labs",
     "open_items": [{"kind": "ask", "text": "send the deck", "who": "Priya Shah",
                     "thread_key": "wa:1"}],
     "dates": [{"text": "kal tak", "resolved": "2026-10-08", "time": "17:00"}],
     "not_useful": ["too obvious"], "useful": ["the one that helped"]},
])
def test_no_brief_leaves_the_prompt_byte_for_byte(extra):
    """(b) No accepted line: the prompt is the builder's own without the parameter."""
    plain = SI.build_prompt(**ARGS, **extra)
    assert SI.build_prompt(**ARGS, **extra, company_brief="") == plain
    assert SI.build_prompt(**ARGS, **extra,
                           company_brief=CompanyBrief(org_id=ORG).prompt_block()) == plain
    assert "COMPANY BRIEF" not in plain
    # The slot is the template's only change: emptied, the two lines it sits between touch again.
    assert ("For the manager it is now {now_local}.\nThis chat so far"
            in SI._TASK.replace("{company_brief}", ""))


def test_the_one_judge_hands_the_block_to_the_model(monkeypatch):
    """(c) `insight` → `_compute` → `llm_insight` → the prompt the model is sent."""
    seen: dict = {}

    class FakeClient:
        def call(self, prompt, **kw):
            seen.update(kw, prompt=prompt)
            return SimpleNamespace(ok=True, error=None, input_tokens=10, output_tokens=2,
                                   cache_read_tokens=0, cache_write_tokens=0,
                                   parsed={"work": True, "remember": True, "items": [],
                                           "adds": "none", "note": None})

    monkeypatch.setattr(SI, "_client", lambda *a: FakeClient())
    monkeypatch.setattr("genios_engine.platform.config.get_settings",
                        lambda: SimpleNamespace(use_real_llm=True, anthropic_api_key="sk-test"))
    out = SI.insight(None, org_id=ORG, email=None, app="whatsapp", participants=[], entities=[],
                     screen=SCREEN, timeout_s=3.0, now_local="Wednesday", me=["Arjun Rao"],
                     company_brief=BLOCK)
    assert out is not None and out["work"] is True
    prompt = seen["prompt"]
    assert seen["cache_prefix_chars"] == SI.RULEBOOK_CHARS == len(SI._RULEBOOK)
    assert prompt.index(BLOCK) > SI.RULEBOOK_CHARS
    assert prompt.index(BLOCK) < prompt.index(SCREEN, SI.RULEBOOK_CHARS)


def test_the_screen_key_moves_with_the_brief_version_and_not_without_one():
    """(d) "This exact screen was already judged" holds only under the brief it was judged with."""
    seat, digest = "seat_s07", SI.text_digest(SCREEN)
    before = M.cache_key(seat_id=seat, capability_id=SI.CAPABILITY_ID, subject_ids=[],
                         trigger=M.trigger_digest(SI.CAPABILITY_ID, digest),
                         subject_version="screen")        # the key as it was before STEP-07
    assert moment_routes._screen_key(seat, digest) == before
    assert moment_routes._screen_key(seat, digest, "") == before
    one = moment_routes._screen_key(seat, digest, BRIEF.version)
    other = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                    lines=[CompanyBriefLine(line_id="l2", section="goals",
                                            text="land three design partners")]).version
    assert one != before
    assert moment_routes._screen_key(seat, digest, other) not in (one, before)
    assert moment_routes._screen_key(seat, digest, BRIEF.version) == one


# ── the route, end to end, on real Postgres ──────────────────────────────────────────────────────
def _due_in_3h() -> str:
    return ((datetime.now(timezone.utc) + timedelta(hours=3)).astimezone(ZoneInfo("Asia/Kolkata"))
            .strftime("%Y-%m-%dT%H:%M"))


def _answer(note: str) -> dict:
    """A note `verify_adds` stands behind (something due within a day), so the moment — and the
    screen's key with it — is written."""
    return {"work": True, "remember": True, "adds": "urgent_risk", "note": note,
            "items": [{"kind": "ask", "text": "Priya is waiting on the revised pricing",
                       "who": "Priya Shah", "due": _due_in_3h(),
                       "quote": "send the revised pricing", "confidence": 0.9}]}


@pytest.mark.pg
@pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")
def test_the_route_reads_the_tenants_brief_and_the_judge_receives_it(client, monkeypatch):  # noqa: F811
    """(c) + (d) through `POST /v1/moments/evaluate`: the brief the founder accepted is the one the
    model reads, and the key the route wrote carries its version — while the same seat's screen
    before any line was accepted got the old prompt and the old key."""
    from genios_engine.platform import company_brief as CB
    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.config import get_settings

    ws = _workspace(client)
    _enable_display(client, ws)
    org, seat, dev = ws["org"], ws["member"]["seat_id"], ws["member_dev"]
    prompts: list[str] = []
    answers = [_answer("Priya asked for this pricing on Monday too"),
               _answer("The board pack needs this pricing today")]

    class FakeClient:
        def call(self, prompt, **kw):
            prompts.append(prompt)
            return SimpleNamespace(ok=True, error=None, input_tokens=10, output_tokens=2,
                                   cache_read_tokens=0, cache_write_tokens=0,
                                   parsed=answers[len(prompts) - 1])

    monkeypatch.setattr(SI, "_client", lambda *a: FakeClient())
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test-not-a-real-key")
    monkeypatch.setattr(moment_routes, "_ensure_profile", lambda *a, **k: None)
    monkeypatch.setattr(moment_routes, "_meetings_soon", lambda *a, **k: [])

    def look(thread: str):
        body = {"moment_request_id": uuid.uuid4().hex, "insight": True,
                "surface": {"app": "whatsapp", "thread_key": thread},
                "visible_messages": [SCREEN]}
        return client.post("/v1/moments/evaluate", json=body, headers=H(dev["access_token"]))

    def keys() -> set[str]:
        with _engine().connect() as c:
            return {r[0] for r in c.execute(text("select key from moment_cache where org_id = :o"),
                                            {"o": org})}

    digest = SI.text_digest(SI.visible_text([SCREEN]))
    assert look("wa:chat:before").status_code == 200
    assert "COMPANY BRIEF" not in prompts[0]
    assert moment_routes._screen_key(seat, digest) in keys()

    with _engine().begin() as c:
        store.add(c, org_id=org, section="goals", words="raise the pre-seed round",
                  decided_by="founder", at=datetime.now(timezone.utc))
    with _engine().connect() as c:
        brief = CB.brief_for(c, org)
    assert brief.version and "raise the pre-seed round" in brief.prompt_block()

    assert look("wa:chat:after").status_code == 200
    assert len(prompts) == 2
    prompt, block = prompts[1], brief.prompt_block()
    assert prompt.index(block) > SI.RULEBOOK_CHARS, "the brief reached the cached rulebook"
    assert prompt.index(block) < prompt.index(SCREEN, SI.RULEBOOK_CHARS)
    assert prompt[:SI.RULEBOOK_CHARS] == prompts[0][:SI.RULEBOOK_CHARS]
    assert moment_routes._screen_key(seat, digest, brief.version) in keys()
