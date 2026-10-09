"""STEP-11 · `03` F121 — the decider reads the corpus's claims whole, and each play's steps whole.

    .venv/bin/python -m pytest tests/reason/test_the_decider_reads_the_corpus_claims.py -q

Tree `yc2_w27_s11 · M30.C3.L-logic.V0.U01`, `06` D46. The decider's prompt rendered each heuristic
citation as `{"rule": null, "quote": null}`: it read `rule_id`/`claim_id` and `quote`/`text`, and the
weld's citations carry `artifact_id` and `statement` (`contracts/domain_expertise.require_citation`).
Every claim the corpus made reached the model as two nulls. Framing blocks (mental models, decision
frameworks) were never read at all, and each play's steps were a JSON list cut at 300 characters —
half a step and an ellipsis on the median playbook. Whatever STEP-11 writes would not have reached
the model. Hermetic: the prompt is built from a hand-made manifest; nothing connects anywhere.
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.contracts.domain_expertise import citation_statement_hash
from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
)
from genios_engine.reason import llm_decision_maker as llm_dm
from genios_engine.reason.decision_maker import ProposedCandidate

NOW = datetime(2026, 10, 9, 9, tzinfo=timezone.utc)
CLAIM = ("When the turn is ours, the clock is running against us and nobody will tell us. Age the "
         "oldest thread waiting on us before anything else, because an investor who is waiting "
         "simply stops appearing — the relationship decays without ever announcing that it has, and "
         "the founder learns it only when the next round's list is drawn up without that name on it. "
         "This sentence is long on purpose: it is longer than three hundred characters.")
LENS = ("Read a programme's silence by its stage: in review, a batch decides together and says "
        "nothing until it does; after an interview, silence past the promised date is the signal.")
STEPS = tuple(f"Step {n}: " + "write down what was agreed and by whom, then check it against the "
              "programme's own published dates before anything is sent " * 1 for n in range(1, 7))


def _citation(artifact_id: str, statement: str, klass: str = "heuristic") -> dict:
    return {"artifact_id": artifact_id, "artifact_class": klass, "statement": statement,
            "statement_hash": citation_statement_hash(statement),
            "source_ref": f"expert:{klass}:{artifact_id}", "tag_overlap": 1}


def _request(*, citations=(), framing=(), steps=STEPS, label="Follow an application through"):
    play = PlayDefinition(play_id="founder_office.pb.program_applications.follow", version="1",
                          label=label, steps=steps)
    capability = CapabilityManifest(
        capability_id="expertise.investor_relationship", version="1.0.0", domain="founder_office",
        root_entity_type="company", goal=Goal("expertise.investor_relationship", "Read the programme"),
        reasoners=(ReasonerSpec("core.confidence", "1"),), plays=(play,), policies=(),
        metadata={"situation_type": "investor_relationship",
                  "weld": {"citations": list(citations), "framing_blocks": list(framing)}})
    context = ContextSnapshot(org_id="org_1", graph_version=1, root_entity_id="company_1",
                              root_entity_type="company", evaluation_time=NOW,
                              selector_version="selector.v1", facts={})
    request = ReasoningRequest(org_id="org_1", capability=capability, context=context,
                               evaluation_time=NOW, trigger_kind="email.received",
                               config_snapshot_id="cfg_1")
    proposals = [ProposedCandidate(play=play, components={"impact": 5_000}, utility_bp=5_000)]
    return request, proposals


def _prompt(**kwargs) -> str:
    request, proposals = _request(**kwargs)
    return llm_dm.build_prompt(request, [], proposals, [], False, None)


def test_a_claim_reaches_the_model_by_its_id_and_whole():
    prompt = _prompt(citations=[_citation("founder_office.heu.investor_relations.investors_do_not_chase",
                                          CLAIM)])
    assert '"rule": null' not in prompt and '"quote": null' not in prompt
    assert f'- founder_office.heu.investor_relations.investors_do_not_chase: "{CLAIM}"' in prompt


def test_no_claim_is_shown_as_nulls_whatever_keys_it_carries():
    """A record with neither an id nor words is dropped, not rendered as two nulls."""
    prompt = _prompt(citations=[{"artifact_class": "heuristic"}])
    assert "null" not in prompt.split("PLAYS YOU CAN RECOMMEND")[0].split("FORMULA SCORED")[-1]
    assert "WHAT AN EXPERT WOULD KNOW HERE" not in prompt


def test_the_old_keys_still_read_for_a_hand_built_citation():
    prompt = _prompt(citations=[{"rule_id": "legacy.rule.x", "quote": "A quoted rule."}])
    assert '- legacy.rule.x: "A quoted rule."' in prompt


def test_a_framing_block_has_its_own_heading():
    prompt = _prompt(framing=[_citation("founder_office.mm.program_applications.stage_lens", LENS,
                                        klass="mental_model")])
    assert "HOW AN EXPERT READS THIS KIND OF SITUATION" in prompt
    assert f'- founder_office.mm.program_applications.stage_lens: "{LENS}"' in prompt


def test_without_claims_neither_heading_appears():
    prompt = _prompt()
    assert "WHAT AN EXPERT WOULD KNOW HERE" not in prompt
    assert "HOW AN EXPERT READS THIS KIND OF SITUATION" not in prompt


def test_every_step_is_shown_whole_and_numbered():
    prompt = _prompt()
    line = next(l for l in prompt.splitlines() if l.startswith("- play_id="))
    for number, step in enumerate(STEPS, 1):
        assert f"{number}. {' '.join(step.split())}" in line
    assert "…" not in line


def test_past_the_budget_steps_are_counted_never_cut():
    long_steps = tuple(f"Step {n}: " + "x" * 400 for n in range(1, 8))
    line = next(l for l in _prompt(steps=long_steps).splitlines() if l.startswith("- play_id="))
    shown = [n for n in range(1, 8) if f"{n}. Step {n}: " + "x" * 400 in line]
    assert shown == list(range(1, len(shown) + 1)) and 1 <= len(shown) < 7
    assert f"(+{7 - len(shown)} more steps)" in line
    assert "…" not in line


def test_one_step_longer_than_the_budget_is_still_shown_whole():
    giant = ("A single step that runs on " + "and on " * 400).strip()
    line = next(l for l in _prompt(steps=(giant, "second")).splitlines()
                if l.startswith("- play_id="))
    assert f"1. {giant}" in line
    assert "(+1 more step)" in line


def test_the_play_is_shown_by_its_name():
    prompt = _prompt(label="Follow an application through to a decision")
    assert "| Follow an application through to a decision |" in prompt


def test_the_prompt_version_moved_with_the_prompt():
    """The in-process cache keys on this string, not on the prompt (STEP-07 §8.2)."""
    assert llm_dm.PROMPT_VERSION == "l4-llm-decision.v6"
