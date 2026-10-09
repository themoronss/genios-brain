"""STEP-11 · the acceptance — every founder file reads its playbook, and the decider reads the claims.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 \
        pytest tests/replays/test_every_founder_file_reads_its_playbook.py -q

Tree `yc2_w27_s11 · M30.C7.L-integration.V5.U04`. M30's promise, on the golden cases it is about, each
replayed from its cassette through the real chain with the Founder Office switched on (as the pilot
org will run it) and read before its tenant is removed:

  * every founder file the brief names with a kind of work answers `playbook_for(file.work_kind)`:
    investor and program files read their spine — stages with sourced priors, moves, claims — labelled
    "playbook not yet reviewed" (D3); compliance, hiring and intro files answer `capability_not_authored`
    (M31), a partner's `no_capability_for_kind` — a reason, never a borrowed playbook;
  * F17's file — Gulf Launchpad, an accelerator's interview, read as an investor until STEP-11 — reads
    the programmes playbook, and its stages include `interview`;
  * the decider's prompt carries the corpus's claims whole, by the contract's keys — `03` F121: no
    prompt anywhere shows `{"rule": null`, and every quoted claim is the authored statement verbatim;
  * no founder card carries the template consequence, the 7-day default or a NULL success signal.
    ⛔ Before the founder's review (D45) the Founder Office's capability is admitted nowhere, so the live
    compile refuses every fundraising situation as `unreviewed` and there is NO founder card to read:
    that clause is declared NOT EXERCISED (an xfail that names why), never counted as a pass. Its
    path is proven at the seams (M30.C2.L-logic.V1.U02, M30.C3.L-data.V1.U03, M30.C3.L-interface.V2.U04).
"""
from __future__ import annotations

import os
import re
from typing import Any

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases

pytestmark = pytest.mark.golden

CASES = {c.case_id: c for c in load_cases()}
#: The golden counterparty each case is about, and the kind of work its in-motion line gives it.
KINDS = {"F10": ("banyanseed.test", "investor"), "F17": ("gulflaunchpad.test", "program"),
         "F01": ("startupsetu.gov.test", "compliance"), "F26": ("orbitly.test", "partner")}


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _keeping():
    """The recorded model, keeping every prompt it answers — the decider's are what F121 is about."""
    from tests.replays.harness import RecordedLLM, identify_site

    class Keeping(RecordedLLM):
        def __init__(self, cassette):
            super().__init__(cassette)
            self.prompts: list[tuple[str, str]] = []

        def call(self, prompt: str, **kw: Any):
            self.prompts.append((identify_site(prompt), prompt))
            return super().call(prompt, **kw)

    return Keeping


def _read(case_id: str) -> dict[str, Any]:
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.context.workstreams import files_for
    from genios_engine.packs.compiler.playbook_reader import playbook_for
    from tests.replays.engine_runner import remove_tenant, run_case

    case = CASES[case_id]
    llm = _keeping()(cassettes.load(case))
    run = run_case(case, llm, keep=True)
    engine, org = routes._graph.engine, run.org_id
    try:
        with engine.connect() as c:
            files = {f.counterparty_key: f for f in files_for(c, org, now=case.sweeps[-1]).files}
            founder_cards = c.execute(text(
                "select k.card_id, k.do_nothing_consequence, k.outcome_window_days, k.success_signal "
                "  from cards k join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id "
                "  join reasoning_runs rr on rr.org_id = s.org_id and rr.run_id = s.reasoning_run_id "
                "  join reasoning_capability_snapshots rcap on rcap.org_id = rr.org_id "
                "   and rcap.capability_snapshot_id = rr.capability_snapshot_id "
                " where k.org_id = :o and rcap.manifest->>'domain' = 'founder_office'"),
                {"o": org}).mappings().all()
        return {"files": files, "answers": {key: playbook_for(f.work_kind)
                                            for key, f in files.items() if f.work_kind},
                "prompts": list(llm.prompts), "founder_cards": [dict(r) for r in founder_cards]}
    finally:
        remove_tenant(engine, org)


@pytest.fixture(scope="module")
def reads(pg_store):
    _scratch_db()
    from tests.replays.engine_runner import pin_scratch_database
    pin_scratch_database()
    return {case_id: _read(case_id) for case_id in (*KINDS, "F12")}


def test_every_founder_file_with_a_kind_reads_an_answer(reads):
    expected = {"investor": None, "program": None, "compliance": "capability_not_authored",
                "hiring": "capability_not_authored", "intro": "capability_not_authored",
                "partner": "no_capability_for_kind"}
    for case_id, (key, kind) in KINDS.items():
        file = reads[case_id]["files"].get(key)
        assert file is not None, f"{case_id}: no file for {key}"
        assert file.work_kind == kind, f"{case_id}: {key} is {file.work_kind!r}, not {kind!r}"
        answer = reads[case_id]["answers"][key]
        assert answer.reason == expected[kind], f"{case_id}: {answer.reason!r}"
        if expected[kind] is None:
            assert answer.playbook.stages and answer.playbook.moves and answer.playbook.claims
            assert answer.playbook.review_label == "playbook not yet reviewed"


def test_f17_s_file_reads_the_programmes_playbook(reads):
    answer = reads["F17"]["answers"]["gulflaunchpad.test"]
    assert answer.playbook.playbook_id == \
        "founder_office.pb.program_applications.follow_an_application"
    assert "interview" in {s.name for s in answer.playbook.stages}


def test_no_prompt_shows_a_claim_as_nulls(reads):
    for case_id, read in reads.items():
        for site, prompt in read["prompts"]:
            assert '"rule": null' not in prompt and '"quote": null' not in prompt, (case_id, site)


def test_the_decider_quotes_each_claim_whole(reads):
    """At least one decider prompt on these cases carries corpus claims — or the clause is not
    exercised and this fails rather than passing over nothing."""
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root

    catalog = ExpertBrainCatalog(default_authoring_root())
    statements = {}
    for record in catalog.domains.values():
        for aid, doc in record.artifacts.items():
            heuristic = doc.content.get("heuristic") or {}
            purpose = doc.content.get("purpose") or {}
            for text_ in (heuristic.get("statement"), purpose.get("statement")):
                if text_:
                    statements.setdefault(aid, set()).add(" ".join(str(text_).split()))
    quoted = 0
    for read in reads.values():
        for site, prompt in read["prompts"]:
            if site != "decider" or "WHAT AN EXPERT WOULD KNOW HERE" not in prompt:
                continue
            block = prompt.split("WHAT AN EXPERT WOULD KNOW HERE", 1)[1].split("\n\n", 1)[0]
            for aid, said in re.findall(r'^- ([a-z0-9_.]+): "(.*)"$', block, re.M):
                assert said in statements.get(aid, set()), f"{aid} was not quoted whole: {said[:80]}"
                quoted += 1
    assert quoted, "no decider prompt on these cases carried a corpus claim — F121 is not exercised"


def test_no_founder_card_carries_a_fallback(reads):
    cards = [card for read in reads.values() for card in read["founder_cards"]]
    if not cards:
        pytest.xfail("NOT EXERCISED: no founder card exists before the founder's review admits the "
                     "Founder Office's capability (06 D45) — the live compile refuses its situations "
                     "as `unreviewed`. The path is proven at the seams (C2.U02, C3.U03, C3.U04).")
    from genios_engine.reason.adapters.expertise import DEFAULT_WINDOW_DAYS
    for card in cards:
        assert "is left unaddressed while its evidence compounds" not in (
            card["do_nothing_consequence"] or ""), card
        assert card["outcome_window_days"] not in (None, DEFAULT_WINDOW_DAYS), card
        assert card["success_signal"], card
