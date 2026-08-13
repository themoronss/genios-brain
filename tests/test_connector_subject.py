"""Update 4 — connector/bot subjects must fail closed, not become the person to reply to.

An introduction connector (Boardy) collects many unrelated intro threads. GeniOS must not render a
confident 'reply to the connector' card; it must point the user at the real contacts.
"""
from genios_engine.api.routes import _connector_gate, _is_connector

# Boardy's real observation signature in the design-partner org.
BOARDY = {"email_noise:automated": 19, "meeting_request": 11, "introduction": 6}
NORMAL = {"question": 3, "meeting_request": 3, "introduction": 2}


def test_known_bot_domain_is_a_connector():
    assert _is_connector("boardy@boardy.ai", {}) is True


def test_automated_aggregator_is_a_connector():
    assert _is_connector("x@random.com", BOARDY) is True


def test_a_normal_person_is_not_a_connector():
    assert _is_connector("nitesh.pant@devdashlabs.com", NORMAL) is False


def test_a_human_with_one_automated_flag_is_not_a_connector():
    # a single automated newsletter does not make a real counterparty a connector bucket
    assert _is_connector("sal@nexlayer.com", {"email_noise:automated": 1, "introduction": 1}) is False


def test_connector_gate_fails_closed_to_the_real_contacts():
    g = _connector_gate("boardy@boardy.ai")
    assert g["state"] == "context_incomplete"
    assert g["connector"] is True
    assert "connector" in g["message"].lower()
    assert "reply to each introduced contact" in g["recommended"].lower()
