"""STEP-12 M33 · a covered file's card speaks its review — no narrator is asked.

    .venv/bin/python -m pytest -q tests/deliver/test_an_expert_card_speaks_its_review.py

Tree `yc2_w27_s12` M33.C1.L-interface.V1.U08 (`deliver/pipeline.py`, `deliver/render.review_copy`). A
covered file's decision is the expert's review (`reason/expert/decide`), and the review already wrote the
card's words — the move, its reading of the file, the draft — validated against its dossier. So the card
is built from them (`decide._render`, carried on the audited capability as its render block), and the
narrator is never asked: it would write the same words again, paid for, from less. A signal of any other
capability is narrated as before — the negative control.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.deliver import pipeline
from genios_engine.deliver.render import review_copy

pytestmark = pytest.mark.unit

EVAL = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)
EXPERT_TEMPLATE = {"artifact_kind": "draft_message",
                   "fallback": {"headline": "Send Arjun the deck and the quarter's metrics",
                                "situation": "a fund preparing a partner meeting"},
                   "draft": "Hi Arjun, attached are the deck and last quarter's metrics."}
CORPUS_TEMPLATE = {"artifact_kind": "draft_reply", "render_hint": "Headline: a direct order.",
                   "fallback": {"headline": "Set a next date with {entity}", "situation": "{stage}"}}


class _Narrator:
    """The card narrator — every prompt it is shown, kept."""
    model = "claude-haiku-4-5"

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=600):
        self.prompts.append(prompt)
        return SimpleNamespace(ok=True, parsed={"headline": "Reply to Arjun today",
                                                "situation": "Arjun asked for the deck.",
                                                "artifact": "Hi Arjun, here it is."},
                               input_tokens=10, output_tokens=10, model=self.model)


def _pass(monkeypatch, signals):
    built: dict[str, dict] = {}
    templates = {"expert.file_review": EXPERT_TEMPLATE, "expertise.opportunity": CORPUS_TEMPLATE}
    monkeypatch.setattr(pipeline, "ensure_default", lambda *_a: None)
    monkeypatch.setattr(pipeline, "_open_signals_without_cards", lambda *_a: signals)
    monkeypatch.setattr(pipeline, "_open_situations_without_cards", lambda *_a: [])
    monkeypatch.setattr(pipeline, "_activated_features", lambda *_a: frozenset())
    monkeypatch.setattr(pipeline, "_cohort_absorbed", lambda *_a: set())
    monkeypatch.setattr(pipeline, "_tenant_identities", lambda *_a: ())
    monkeypatch.setattr(pipeline, "load_evidence_quotes", lambda *_a, **_k: [])
    monkeypatch.setattr(pipeline, "budget_full", lambda *_a: False)

    def _draft(_graph, _org, sig, *_a, **_k):
        return {"_reason_code": sig["reason_code"], "_template": templates[sig["capability_id"]],
                "_facts": {}, "_slots": {"entity": "Arjun", "stage": "open"}, "level": "prescriptive",
                "actions": [{"type": "run_play", "artifact_ready": True}], "assignee": None,
                "output_lane": "decision"}
    monkeypatch.setattr(pipeline, "build_draft", _draft)

    def _insert(draft, copy, *, build_claim_token):
        built[draft["_reason_code"]] = copy
        return f"card_{draft['_reason_code']}", True, False
    store = SimpleNamespace(claim_build=lambda *_a, **_k: "tok", release_build=lambda *_a: None,
                            insert_card=_insert, transition=lambda *_a, **_k: False)
    narrator = _Narrator()
    graph = SimpleNamespace(engine=None, record_cost=lambda **_k: None)
    pipeline.build_cards_for_org(graph=graph, card_store=store, org_id="org_m33", llm=narrator,
                                 registry=object(), eval_time=EVAL)
    return built, narrator


def _signal(signal_id: str, capability_id: str, reason_code: str) -> dict:
    return {"signal_id": signal_id, "subject_node_id": "node_fund", "effective_config": {},
            "capability_id": capability_id, "reason_code": reason_code, "score": 60,
            "reasoning_run_id": f"rrun_{signal_id}", "reasoning_candidate_id": f"cand_{signal_id}",
            "reasoning_decision_hash": "d" * 64, "config_snapshot_id": "cfg_1"}


def test_a_covered_files_card_is_its_reviews_words_and_no_narrator_is_asked(monkeypatch):
    built, narrator = _pass(monkeypatch, [_signal("sig_e", "expert.file_review", "file_review")])
    assert narrator.prompts == [], "the narrator was asked to write what the review already wrote"
    copy = built["file_review"]
    assert (copy["headline"], copy["situation"]) == ("Send Arjun the deck and the quarter's metrics",
                                                     "a fund preparing a partner meeting")
    assert copy["artifact"]["body"] == EXPERT_TEMPLATE["draft"] and copy["render_mode"] == "review"


def test_any_other_card_is_narrated_as_before(monkeypatch):
    """⛔ THE NEGATIVE CONTROL: a corpus capability's signal, the same pass — narrated, once."""
    built, narrator = _pass(monkeypatch, [_signal("sig_e", "expert.file_review", "file_review"),
                                          _signal("sig_c", "expertise.opportunity", "opportunity")])
    assert len(narrator.prompts) == 1 and "file_review" not in narrator.prompts[0]
    assert built["opportunity"]["render_mode"] != "review" and built["file_review"]["render_mode"] == "review"


def test_a_review_with_no_draft_keeps_an_empty_artifact():
    copy = review_copy({"headline": "h", "situation": "s",
                        "artifact": {"kind": "none", "body": "", "mode": "raw_slot"},
                        "render_mode": "raw_slot"}, {"draft": None})
    assert copy["artifact"] == {"kind": "none", "body": "", "mode": "raw_slot"}
    assert copy["render_mode"] == "review"
