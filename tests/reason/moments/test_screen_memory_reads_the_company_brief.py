"""STEP-07 · screen memory reads the company brief — beside "The manager", before the text.

    .venv/bin/python -m pytest tests/reason/moments/test_screen_memory_reads_the_company_brief.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (adds a real queue, submitted end to end)

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U09`. The hourly memory batch judged work against personal and
pulled out asks and promises knowing only "The manager: {seat}" and the time (`speedrun008/YC-II
W27/` STEP-07 §1). Each job's prompt now carries its own tenant's brief as a paragraph beside the
manager's lines, before the rules and the text. `submit` reads the brief once per tenant per batch,
through the engine rather than the claim's connection, so a brief that cannot be read costs the
brief and never the claim. A tenant with no accepted line sends exactly the prompt it sent before.

No key moves in this unit: a job's id names the thread event it reads, not an answer, and nothing
here serves what the model said under an older brief.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import encrypt
from genios_engine.reason.moments import screen_insight as SI
from genios_engine.reason.moments import screen_memory_batch as MB

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
ORG_A, ORG_B = "org_s07_memory_a", "org_s07_memory_b"
CREATED = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)
TEXT = "Priya Shah: Can you send the revised pricing by Friday?\nYou: will do"
BRIEF_A = compose(org_id=ORG_A, company="Nimbus Labs", founder="Arjun Rao",
                  us=("arjun@nimbuslabs.test",),
                  lines=[CompanyBriefLine(line_id="l1", section="goals",
                                          text="raise the pre-seed round")])
BLOCK_A = BRIEF_A.prompt_block()
ARGS = dict(app="whatsapp", me=["Arjun Rao"], now_local="Wednesday 2026-10-07 14:30", text=TEXT)


def test_the_block_is_its_own_paragraph_beside_the_manager_and_before_the_text():
    """(a) After who the manager is and when; before the rules, the text and its fence."""
    p = MB.build_prompt(**ARGS, company_brief=BLOCK_A)
    at = p.index(BLOCK_A)
    assert p.index("The manager: Arjun Rao.") < p.index("For the manager it was") < at
    assert at < p.index("Work = customers") < p.index("TEXT (newest last):")
    assert at < p.index("<<<") < p.index(TEXT), "the brief is never inside the text's fence"
    assert "\n\n" + BLOCK_A.strip() + "\n\n" in p, "the brief is its own paragraph"


def test_no_brief_leaves_the_prompt_byte_for_byte():
    """(b) No accepted line: the prompt is the builder's own without the parameter."""
    plain = MB.build_prompt(**ARGS)
    assert MB.build_prompt(**ARGS, company_brief="") == plain
    assert MB.build_prompt(**ARGS, company_brief=CompanyBrief(org_id=ORG_B).prompt_block()) == plain
    assert "COMPANY BRIEF" not in plain
    # The slot is the template's only change: emptied, the two lines it sits between touch again.
    assert ("For the manager it was {now_local}.\nWork = customers"
            in MB._PROMPT.replace("{company_brief}", ""))


class _Result:
    rowcount = 0

    def __init__(self, first=None, rows=()):
        self._first, self._rows = first, list(rows)

    def first(self):
        return self._first

    def fetchall(self):
        return list(self._rows)


class _Claim:
    """The claim's one connection: the head read, the claimed rows, and the writes after them."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, statement, params=None):
        sql = str(statement)
        if "min(created_at)" in sql:
            return _Result(first=SimpleNamespace(oldest=CREATED, n=len(self.rows)))
        if "for update skip locked" in sql:
            return _Result(rows=self.rows)
        return _Result()


class _Engine:
    def __init__(self, rows):
        self.claim = _Claim(rows)

    @contextmanager
    def begin(self):
        yield self.claim


def _client(created: list):
    def create(*, requests):
        created.append(list(requests))
        return SimpleNamespace(id=f"msgbatch_{len(created)}")
    return SimpleNamespace(messages=SimpleNamespace(batches=SimpleNamespace(create=create)))


def _prompts(created: list) -> dict[str, str]:
    (requests,) = created
    return {r["custom_id"]: r["params"]["messages"][0]["content"] for r in requests}


def test_submit_hands_each_job_its_own_tenants_brief(monkeypatch):
    """(c) Two jobs of a tenant with a brief and one of a tenant without, in one batch: each prompt
    is its own tenant's, and the brief is read once per tenant, through the engine."""
    key = get_settings().crypto_key
    rows = [SimpleNamespace(id=f"smj_{n}", org_id=org, seat_id="seat_1", app="whatsapp",
                            text_enc=encrypt(TEXT, key), created_at=CREATED)
            for n, org in enumerate((ORG_A, ORG_A, ORG_B))]
    engine = _Engine(rows)
    asked: list[tuple] = []

    def current(source, org_id):
        asked.append((source, org_id))
        return BRIEF_A if org_id == ORG_A else CompanyBrief(org_id=org_id)

    monkeypatch.setattr("genios_engine.platform.company_brief.current", current)
    monkeypatch.setattr(MB, "_Seats", lambda conn: SimpleNamespace(
        get=lambda org, seat: (None, ["Arjun Rao"], "Asia/Kolkata")))
    created: list = []
    assert MB.submit(engine, client=_client(created), now=CREATED + timedelta(hours=2),
                     crypto_key=key, wait_minutes=0, max_jobs=10) == 3

    prompts = _prompts(created)
    clock = SI.local_label(CREATED, "Asia/Kolkata")
    plain = MB.build_prompt(app="whatsapp", me=["Arjun Rao"], text=TEXT, now_local=clock)
    for job in ("smj_0", "smj_1"):
        assert prompts[job] == MB.build_prompt(app="whatsapp", me=["Arjun Rao"], text=TEXT,
                                               now_local=clock, company_brief=BLOCK_A)
        assert prompts[job].index(BLOCK_A) < prompts[job].index(TEXT)
    assert prompts["smj_2"] == plain and "COMPANY BRIEF" not in prompts["smj_2"]
    assert asked == [(engine, ORG_A), (engine, ORG_B)], "once per tenant, through the engine"


# ── a real queue, on real Postgres ──────────────────────────────────────────────────────────────
def _reset(engine) -> None:
    from genios_engine.platform import company_brief as CB
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = any(:o)"), {"o": [ORG_A, ORG_B]})
    CB.invalidate(ORG_A)
    CB.invalidate(ORG_B)


@pytest.mark.pg
@pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")
def test_a_real_queue_goes_out_with_each_tenants_brief():
    """(c) `enqueue` → `submit` on the real queue: the brief the founder accepted is in that
    tenant's prompt, read by the real `current`, and the other tenant's prompt is unchanged."""
    from genios_engine.platform import company_brief as CB
    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.db import get_engine

    engine = get_engine(URL)
    _reset(engine)
    key = get_settings().crypto_key
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:a, :a), (:b, :b)"),
                  {"a": ORG_A, "b": ORG_B})
        # The queue is global and `submit` claims all of it: park every other test's open jobs.
        c.execute(text("update screen_memory_jobs set status = 'failed', text_enc = null, "
                       "error = 'isolated by test' where status in ('queued', 'submitted')"))
        store.add(c, org_id=ORG_A, section="goals", words="raise the pre-seed round",
                  decided_by="founder", at=CREATED)
    try:
        for org in (ORG_A, ORG_B):
            assert MB.enqueue(engine, org_id=org, seat_id="seat_1", thread_key="wa:chat:priya",
                              app="whatsapp", event_id=f"evt_{org}", text=TEXT, crypto_key=key,
                              now=CREATED)
        with engine.connect() as c:
            brief = CB.brief_for(c, ORG_A)
            _email, me, tz = MB._Seats(c).get(ORG_B, "seat_1")
        created: list = []
        assert MB.submit(engine, client=_client(created), now=CREATED + timedelta(hours=2),
                         crypto_key=key, wait_minutes=0, max_jobs=10) == 2

        prompts = _prompts(created)
        a = prompts[MB.job_id(ORG_A, "seat_1", "wa:chat:priya", f"evt_{ORG_A}")]
        b = prompts[MB.job_id(ORG_B, "seat_1", "wa:chat:priya", f"evt_{ORG_B}")]
        block = brief.prompt_block()
        assert "raise the pre-seed round" in block
        assert a.index("For the manager it was") < a.index(block) < a.index(TEXT)
        assert b == MB.build_prompt(app="whatsapp", me=me, text=TEXT,
                                    now_local=SI.local_label(CREATED, tz))
        assert "COMPANY BRIEF" not in b
    finally:
        _reset(engine)
