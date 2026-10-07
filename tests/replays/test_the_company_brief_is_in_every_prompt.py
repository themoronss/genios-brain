"""STEP-07 · the acceptance: on every founder case, every prompt that judges or reads carries the
founder's company brief — and no prompt that writes does; the brief's senders are kept and read.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 \
        pytest tests/replays/test_the_company_brief_is_in_every_prompt.py -q

Tree `yc2_w27_s07 · M25.C7.L-integration.V6.U03`. Every founder case is replayed from its cassette
through the REAL chain (`engine_runner.run_case`, the recorded model — no spend), its golden founder
holding the brief STEP-07 §4 would draft (`specs/founder/brief/company_brief.json`), and every prompt
the chain sends is read:

  * every JUDGING or READING prompt — the junk filter, the relevance page, extraction, resolution,
    R-1, the decider — carries the brief's block exactly once, under the version the tenant's brief
    has;
  * no WRITING prompt — the card narrator, the bundle narrator — carries it: card copy is STEP-14's,
    and the re-record held every writing prompt of every case byte for byte (their cassette keys);
  * every mail from a sender the brief names — the connector's address, a watchlist domain — is
    KEPT and read: emitted, attention `deep`, for the reason `W-07` (*named in the company brief*).

The board the re-record produced is held by `test_the_gate_deletes_nothing` (the four cases the brief
moved from the gate into reasoning) and by `scripts/golden_score.py --assert-recorded`.
"""
from __future__ import annotations

import os

import pytest

from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.harness import RecordedLLM, identify_site

CASES = load_cases()

#: The sites a golden run reaches that judge or read — and the two that write.
JUDGE_OR_READ = frozenset({"junk_gate", "junk_gate_batch", "relevance", "extraction", "resolution",
                           "r1", "decider", "org_rule_extract"})
WRITE = frozenset({"narrator", "bundle_narrator"})


class _PromptSpy(RecordedLLM):
    """The recorded model, keeping every prompt it was asked."""

    def __init__(self, cassette) -> None:
        super().__init__(cassette)
        self.prompts: list[str] = []

    def call(self, prompt: str, **kw):
        self.prompts.append(prompt)
        return super().call(prompt, **kw)


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def test_the_sites_are_the_golden_chain_s():
    """Every site the golden chain can reach is placed on one side — the recorded sites of
    `model_sites.CHAIN_SITES`, held to the register by its own guard."""
    from tests.replays.model_sites import recorded_sites
    assert JUDGE_OR_READ | WRITE >= recorded_sites()
    assert not JUDGE_OR_READ & WRITE


@pytest.mark.pg
@pytest.mark.golden
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.case_id)
def test_every_judging_and_reading_prompt_carries_the_brief_and_no_writing_prompt_does(case):
    _scratch_db()
    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.platform.company_brief import brief_for
    from tests.replays.engine_runner import remove_tenant, run_case

    spy = _PromptSpy(cassettes.load(case))
    run = run_case(case, spy, keep=True)
    engine = routes._graph.engine
    try:
        with engine.connect() as c:
            brief = brief_for(c, run.org_id)
            mail = c.execute(text(
                "select source_object_id, outcome, attention, attention_reason, "
                "       lower(actor->>'email') as sender "
                "  from source_events where org_id = :o and source = 'gmail' "
                "   and object_type = 'email_message'"), {"o": run.org_id}).fetchall()
    finally:
        remove_tenant(engine, run.org_id)

    assert not run.misses, f"{case.case_id}: the replay missed its cassette at {run.misses[:3]}"
    assert brief and brief.version.startswith("cb-"), f"{case.case_id}: the founder has no brief"
    header = f"COMPANY BRIEF {brief.version}"
    sites = [(identify_site(p), p) for p in spy.prompts]
    unknown = sorted({s for s, _ in sites} - JUDGE_OR_READ - WRITE)
    assert not unknown, f"{case.case_id}: prompts from sites on neither side: {unknown}"
    without = [s for s, p in sites if s in JUDGE_OR_READ and p.count(header) != 1]
    assert not without, f"{case.case_id}: judging prompts without the brief once: {without}"
    written = [s for s, p in sites if s in WRITE and "COMPANY BRIEF" in p]
    assert not written, f"{case.case_id}: writing prompts that carry the brief: {written}"

    named = [r for r in mail if brief.named_sender(r.sender)]
    for r in named:
        assert (r.outcome, r.attention, r.attention_reason) == ("emitted", "deep", "W-07"), (
            f"{case.case_id}: {r.source_object_id} from {r.sender} — the brief names "
            f"{brief.named_sender(r.sender)} — landed {r.outcome}/{r.attention}/{r.attention_reason}")
