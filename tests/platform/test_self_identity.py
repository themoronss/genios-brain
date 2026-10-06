"""STEP-04 · who is us — the two questions every module asks, answered in one place.

    pytest tests/platform/test_self_identity.py -q

`platform/self_identity.SelfIdentity` (tree `yc2_w27_s04/M22.C1.L-contract.V0.U02`). Pure. An address is
ours when it is one of our addresses exactly, or when its domain is one we DECLARED. A public mail
domain is never ours as a domain — the support lane took the domain of a Gmail founder's address and
made every gmail.com sender one of us (`speedrun008/YC-II W27/` STEP-04 §8.2). A node is ours by its key:
a person or a service by its address, a company by its domain.
"""
from __future__ import annotations

import pytest

from genios_engine.platform.self_identity import PUBLIC_MAIL_DOMAINS, SelfIdentity

US = SelfIdentity.of(addresses=["MrRohitSwerashi@gmail.com", "ceo+cal@thegenios.com"],
                     domains=["TheGenios.com", "gmail.com"])


def test_addresses_are_normalised_like_person_keys():
    assert "mrrohitswerashi@gmail.com" in US.addresses
    assert "ceo@thegenios.com" in US.addresses            # +tag stripped, as node keys are


def test_a_public_mail_domain_is_never_ours_as_a_domain():
    assert "gmail.com" in PUBLIC_MAIL_DOMAINS
    assert US.domains == frozenset({"thegenios.com"})
    assert US.is_us("mrrohitswerashi@gmail.com")          # the exact address still is
    assert not US.is_us("investor@gmail.com")             # its domain never is


@pytest.mark.parametrize("email, ours", [
    ("CEO@thegenios.com", True), ("invite@thegenios.com", True), ("a@eng.thegenios.com", True),
    ("mrrohitswerashi+news@gmail.com", True), ("khushi@247vc.test", False),
    ("thegenios.com", False), ("", False), (None, False),
])
def test_is_us(email, ours):
    assert US.is_us(email) is ours


@pytest.mark.parametrize("node_type, key, ours", [
    ("person", "mrrohitswerashi@gmail.com", True),
    ("service", "ceo@thegenios.com", True),
    ("person", "manik@titan.test", False),
    ("company", "thegenios.com", True),
    ("company", "titan.test", False),
    ("company", "gmail.com", False),
    ("thread", "thread:abc", False),
    ("tenant", "tenant:org_x", True),
])
def test_is_us_node(node_type, key, ours):
    assert US.is_us_node(node_type, key) is ours


def test_an_empty_identity_claims_nothing():
    nobody = SelfIdentity.of()
    assert not nobody.is_us("anyone@anywhere.test") and not nobody.is_us_node("company", "x.test")
    assert not nobody
