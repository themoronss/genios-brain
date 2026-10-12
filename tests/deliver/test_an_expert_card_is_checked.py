"""STEP-13 §5 · every sentence on an expert card carries its source or says it is the expert's reading.

    .venv/bin/python -m pytest -q tests/deliver/test_an_expert_card_is_checked.py

Tree `yc2_w27_s13` M35.C3.L-interface.V3.U03 (`reason/expert/decide.sources_of`, `deliver/card_builder.
_sentence_sources`). The decision carries, beside the card's checked words, where each came from; the card's
`why` leads with one entry per sentence: the headline with the mails and asks its move rests on and their
quotes, the situation labelled an inference, the draft with whom it goes to. A held file's headline is its
question, and says why it is asked. Any other card's `why` is what it always was — the negative control.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.deliver import card_builder as B
from genios_engine.reason.expert import decide as D

pytestmark = pytest.mark.unit

WORDS = C.CardWords(headline="Send Marco the short deck", situation="An introduced investor asked for a deck",
                    done_when="Marco has the deck", draft="Hi Marco, the deck is attached. Arjun",
                    to="Marco", evidence=("evt_marco_0811", "loop:ask_deck"),
                    quotes=("could you send a short deck",))


def _checked(fate=C.SHOWN, **over) -> C.CheckedReview:
    base = dict(verdicts=(), fate=fate, words=WORDS, cited=("evt_marco_0811",))
    base.update(over)
    return C.CheckedReview(**base)


def _signal(sources) -> dict:
    return {"capability_render": {"fallback": {"headline": "h", "situation": "s"}, "sources": sources}}


def test_each_sentence_says_where_it_came_from():
    why = B._sentence_sources(_signal(D.sources_of(_checked())))
    assert [w["sentence"] for w in why] == ["headline", "situation", "draft"]
    headline, situation, draft = why
    assert headline["evidence"] == ["evt_marco_0811", "loop:ask_deck"]
    assert headline["quotes"] == ["could you send a short deck"]
    assert situation["inference"] == D.SITUATION_IS and "inference" in situation["inference"]
    assert draft["to"] == "Marco"
    assert {w["source"] for w in why} == {"expert_check"}


def test_every_sentence_of_a_shown_card_carries_an_id_or_an_inference_label():
    """STEP-13 §5: 100% — for the card's every sentence there is an entry, and it cites or it labels."""
    why = B._sentence_sources(_signal(D.sources_of(_checked())))
    for entry in why:
        assert entry.get("evidence") or entry.get("inference") or entry.get("to"), entry


def test_a_held_files_headline_is_its_question_and_says_why():
    held = _checked(C.HELD, question="Is it so: “Marco asked for a deck”? It is not in what it cites.",
                    because="misquoted (fact 1)",
                    words=C.CardWords(None, WORDS.situation, WORDS.done_when, None, None))
    [headline, situation] = B._sentence_sources(_signal(D.sources_of(held)))
    assert headline == {"sentence": "headline", "question": held.question, "because": "misquoted (fact 1)",
                        "source": "expert_check"}
    assert situation["sentence"] == "situation"


def test_a_withheld_line_has_no_entry():
    bare = _checked(words=C.CardWords("Send Marco the short deck", None, None, None, None,
                                      evidence=("loop:ask_deck",)))
    assert [w["sentence"] for w in B._sentence_sources(_signal(D.sources_of(bare)))] == ["headline"]


@pytest.mark.parametrize("signal", [{}, {"capability_render": None}, {"capability_render": {"fallback": {}}},
                                    {"capability_render": {"sources": "not a mapping"}}])
def test_any_other_card_carries_no_sentence_sources(signal):
    """⛔ THE NEGATIVE CONTROL: a narrator's card, a legacy signal — its `why` is what it always was."""
    assert B._sentence_sources(signal) == []


def test_the_decision_carries_the_sources_on_its_render():
    """Wired: the audited capability's render block — what `deliver/pipeline` hands the card as
    `capability_render` — holds the sources of the checked words."""
    from datetime import datetime, timezone

    from tests.reason.expert import check_world as W
    from tests.reason.expert.checks import as_written
    review = W.review()
    checked = as_written(review)
    manifest = D.capability_for(review, checked, root_entity_type="company", domain="founder_office",
                                eval_time=datetime(2026, 8, 12, tzinfo=timezone.utc))
    def plain(value):                     # the manifest is frozen: mappings and tuples, compared as data
        if hasattr(value, "items"):
            return {k: plain(v) for k, v in value.items()}
        return [plain(v) for v in value] if isinstance(value, (list, tuple)) else value
    assert plain(manifest.metadata["render"]["sources"]) == plain(D.sources_of(checked))
    assert set(manifest.metadata["render"]["sources"]) == {"headline", "situation", "draft"}


def test_the_card_leads_its_why_with_them(monkeypatch):
    """Wired: `build_draft` puts the sentence sources first in the card's `why`, before its evidence."""
    from datetime import datetime, timezone
    monkeypatch.setattr(B, "load_node", lambda *_a, **_k: ("Altavia", "company", {}, {}))
    monkeypatch.setattr(B, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(B, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))
    signal = {"signal_id": "sig_1", "subject_node_id": "n1", "reason_code": "expert_review",
              "level": "observation", "score": 60, "play": "expert.move",
              "evidence": [{"field": "thread.ball_in_court", "value": "us"}],
              **_signal(D.sources_of(_checked()))}
    why = B.build_draft(object(), "org_1", signal, {"pack_id": "founder_office", "templates": {}},
                        datetime(2026, 8, 12, tzinfo=timezone.utc))["why"]
    assert [w.get("sentence") for w in why[:3]] == ["headline", "situation", "draft"]
    assert any(w.get("field") == "thread.ball_in_court" for w in why[3:]), "its evidence follows"
