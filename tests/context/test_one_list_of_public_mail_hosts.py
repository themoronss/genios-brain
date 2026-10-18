"""`03` F128 · one list says which hosts are public mail — a company is never minted from one.

    pytest tests/context/test_one_list_of_public_mail_hosts.py -q

`yc2_w27_s18` M49.C2.L-logic.V0.U05 (L1 Signals `capture/structured` → L3 Context Graph `context/`).

⛔ WHAT WAS WRONG. Two lists disagreed: `capture/structured/apply._PERSONAL_DOMAINS` held 8 hosts and
`platform/self_identity.PUBLIC_MAIL_DOMAINS` (= `capture/validate/canonical.CONSUMER_EMAIL_DOMAINS`)
24. `context/pipeline._company_domain` and `context/introductions._stem` read the 8, so the other 16 —
rediffmail.com, zoho.com, yahoo.co.in … — still minted a company node, and everyone writing from one
shared one company file. The 8 is now the 24: one list.
"""
from __future__ import annotations

import pytest

from genios_engine.capture.structured import apply
from genios_engine.capture.validate.canonical import CONSUMER_EMAIL_DOMAINS
from genios_engine.context import introductions
from genios_engine.context import pipeline
from genios_engine.platform.self_identity import PUBLIC_MAIL_DOMAINS

#: The hosts the 8 lacked, as `03` F128 names them, and the rest of the 24.
ONCE_A_COMPANY = sorted(CONSUMER_EMAIL_DOMAINS - {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com",
    "proton.me", "protonmail.com"})


def test_there_is_one_list():
    assert apply._PERSONAL_DOMAINS == CONSUMER_EMAIL_DOMAINS == PUBLIC_MAIL_DOMAINS
    assert len(ONCE_A_COMPANY) == 16


@pytest.mark.parametrize("host", ONCE_A_COMPANY)
def test_a_public_host_mints_no_company(host):
    assert pipeline._company_domain(f"ravi@{host}") is None
    assert introductions._stem(host) is None


def test_a_company_domain_is_still_a_company():
    """The negative half: a work domain still names its company."""
    assert pipeline._company_domain("Ravi@Acme-Logistics.test") == "acme-logistics.test"
    assert introductions._stem("rahul@kestrelcap.test") == "kestrelcap"
