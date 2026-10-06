"""STEP-04 · we are never a card's subject.

    pytest tests/deliver/test_we_are_never_a_cards_subject.py -q

Tree `yc2_w27_s04 · M22.C3.L-logic.V3.U01`. Production carried *"Send Mr Rohit Swerashi your traction
metrics"*: an investor's ask, carded with the founder as its subject (`speedrun008/YC-II W27/`
STEP-04 §8.2). `build_draft`'s subject chain ends in `resolved_person_name`, which took the FIRST
`mention:person` in the node's quotes — and a mention lands on the SENDER for every person named in
their mail, so the investor's "Rohit, can you send…" named the card after Rohit.

Now the chain skips a name that is one of us (`platform/self_identity.names_us`), and a card whose
subject is still one of us — by any road — is refused: `SubjectIsUs`, counted by the pass as
`refused_subject_is_us`, logged with its reason, and never the end of the pass. `7075014c` stands:
our own words may ground a `dependency_stated` card; we are never the one it is about.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.deliver import card_builder, pipeline
from genios_engine.deliver.card_builder import SubjectIsUs, resolved_person_name
from genios_engine.platform.self_identity import SelfIdentity, names_us

EVAL = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
US = SelfIdentity.of(addresses=["founder.kite@gmail.com", "ceo@kitebird.test"],
                     domains=["kitebird.test"])
OUR_NAMES = ("Meera Iyer", "Kitebird")
INVESTOR = "ira@northwind.test"

TEMPLATE = {"artifact_kind": "draft_reply", "render_hint": "name the person who asked",
            "fallback": {"headline": "{who} is owed a reply",
                         "situation": "They wrote {days} days ago and no reply has gone back."}}


def _quote(name: str, *, author: str = INVESTOR, kind: str = "mention:person") -> dict:
    return {"kind": kind, "name": name, "quote": "can you send your traction metrics?",
            "author": author, "from_counterparty": author == INVESTOR}


@pytest.fixture()
def draft(monkeypatch):
    """`build_draft` with the graph reads stubbed — the harness of
    `tests/deliver/test_a_person_card_names_a_person.py`."""
    monkeypatch.setattr(card_builder, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(card_builder, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))
    monkeypatch.setattr(card_builder, "_group_memberships", lambda *_a, **_k: {})
    monkeypatch.setattr(card_builder, "co_recipients_for", lambda *_a, **_k: ())

    def _build(*, node=(INVESTOR, "person", {}, {}), quotes=(), reason="first_response_overdue",
               us=US, our_names=OUR_NAMES):
        monkeypatch.setattr(card_builder, "load_node", lambda *_a, **_k: node)
        signal = {"signal_id": "sig_1", "subject_node_id": "n1", "reason_code": reason,
                  "level": "prescriptive", "score": 70, "capability_render": TEMPLATE}
        return card_builder.build_draft(object(), "org_1", signal, {"pack_id": "admin"}, EVAL,
                                        quotes=list(quotes), us=us, our_names=our_names)
    return _build


def test_a_mention_of_us_never_names_the_card(draft):
    """The production defect: the founder is named first in the investor's quotes."""
    card = draft(quotes=[_quote("Meera Iyer"), _quote("Ira Shah")])
    assert card["business_subject"] == "Ira Shah"


def test_with_only_us_mentioned_the_card_keeps_the_node_s_own_name(draft):
    card = draft(quotes=[_quote("Meera Iyer")])
    assert card["business_subject"] == INVESTOR


@pytest.mark.parametrize("node", [
    ("ceo@kitebird.test", "person", {}, {}),                       # our declared address
    ("ops@kitebird.test", "person", {}, {}),                       # an address at our domain
    ("kitebird.test", "company", {}, {}),                          # our company
    (INVESTOR, "person", {}, {"outreach.counterparty": {"value": "Ms Meera Iyer"}}),  # a fact naming us
])
def test_a_card_about_us_is_refused_with_its_reason(draft, node):
    with pytest.raises(SubjectIsUs, match="one of us"):
        draft(node=node)


def test_without_the_identity_nothing_is_refused(draft):
    """The one caller, the pipeline, always hands both in; a direct call without them is today's
    behaviour, so no existing caller changes meaning."""
    card = draft(node=("ceo@kitebird.test", "person", {}, {}), us=None, our_names=())
    assert card["business_subject"] == "ceo@kitebird.test"


def test_our_own_words_may_still_ground_a_dependency_card(draft):
    """`7075014c`: a dependency we stated is grounded by our own sentence — the card is about the
    counterparty we depend on, and it is built."""
    ours = {**_quote("Ira Shah", author="founder.kite@gmail.com", kind="dependency_stated"),
            "from_counterparty": False}
    card = draft(quotes=[ours], reason="dependency_stated")
    assert card["business_subject"] == INVESTOR


def test_a_first_name_alone_claims_nobody():
    """"Meera" is not a name of ours on its own — another Meera is somebody else."""
    assert not names_us("Meera Kapoor", US, OUR_NAMES)
    assert resolved_person_name([_quote("Meera Kapoor")], INVESTOR,
                                lambda t: names_us(t, US, OUR_NAMES)) == "Meera Kapoor"


def test_the_pass_counts_a_refusal_and_goes_on(monkeypatch):
    """Refused, counted, the build lease released — and the pass reaches its own end."""
    signals = [{"signal_id": f"sig_{i}", "subject_node_id": f"n{i}", "effective_config": {}}
               for i in (1, 2)]
    released: list[str] = []
    monkeypatch.setattr(pipeline, "ensure_default", lambda *_a: None)
    monkeypatch.setattr(pipeline, "_open_signals_without_cards", lambda *_a: signals)
    monkeypatch.setattr(pipeline, "load_evidence_quotes", lambda *_a, **_k: [])

    def _refuse(*_a, **_k):
        raise SubjectIsUs("signal sig_x: the subject 'Meera Iyer' is one of us")

    monkeypatch.setattr(pipeline, "build_draft", _refuse)
    store = SimpleNamespace(claim_build=lambda *_a, **_k: "tok",
                            release_build=lambda _o, sid, _t: released.append(sid))
    out = pipeline.build_cards_for_org(graph=object(), card_store=store, org_id="org_1",
                                       registry=object(), eval_time=EVAL)
    assert out["refused_subject_is_us"] == 2
    assert out["built"] == 0
    assert released == ["sig_1", "sig_2"], "a refused build kept its lease"
    assert "lane_recall" in out, "the refusal ended the pass"
