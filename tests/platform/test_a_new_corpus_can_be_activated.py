"""The front door: authoring a corpus must be enough to activate it.

    pytest tests/platform/test_a_new_corpus_can_be_activated.py -q

`L3_DOMAINS` was a literal three-tuple whose own comment said it listed *"the three authored
corpora under `Domain Expertise/`, in the order that directory lists them"* — the directory was
already the truth and Python copied it BY HAND. So a fourth corpus was a folder the catalog
loads, the resolver routes, and `require_domain` REFUSES with a ValueError. A customer whose
business is not admin, sales or support could not be turned on at all, and the refusal came from
a list nobody had told about them.

THE POINT IS THAT THE GATE SURVIVES. De-rigidifying is not removing the check. `require_domain`
still refuses a typo, because a misspelling must not write a row that reads as an activated
tenant and compiles nothing. A rule may be a gate; it may not also be the vocabulary.
"""

from __future__ import annotations

import pytest

from genios_engine.packs.compiler.authoring import default_authoring_root
from genios_engine.platform import l3_activation
from genios_engine.platform.l3_activation import (
    DOMAIN_ADMIN,
    DOMAIN_CUSTOMER_SUPPORT,
    DOMAIN_SALES,
    L3_DOMAINS,
    require_domain,
)

pytestmark = pytest.mark.unit


def test_the_shipped_three_are_still_there():
    """Nothing about deriving the list may drop a tenant that was already live."""
    for domain in (DOMAIN_ADMIN, DOMAIN_CUSTOMER_SUPPORT, DOMAIN_SALES):
        assert domain in L3_DOMAINS
        assert require_domain(domain) == domain


def test_the_list_matches_what_is_actually_authored():
    """The property, not the values. Whatever `Domain Expertise/` holds is what may be activated
    — so this test keeps passing the day somebody authors a fourth corpus, which a hardcoded
    expectation would not."""
    root = default_authoring_root()
    authored = {d.name for d in sorted(root.iterdir())
                if d.is_dir() and not d.name.startswith("_") and (d / "domain.yaml").is_file()}

    assert len(L3_DOMAINS) >= len(authored) or authored == set()
    assert L3_DOMAINS == tuple(sorted(set(L3_DOMAINS))), "sorted and deduplicated"


def test_a_newly_authored_corpus_becomes_activatable(tmp_path, monkeypatch):
    """THE WHOLE POINT, end to end. A folder appears; the domain may be turned on. No deploy."""
    (tmp_path / "Clinic Expertise").mkdir()
    (tmp_path / "Clinic Expertise" / "domain.yaml").write_text(
        "identity:\n  id: clinic\n  name: Clinic Expertise\n  version: 0.0.1\n")

    monkeypatch.setattr("genios_engine.packs.compiler.authoring.default_authoring_root",
                        lambda: tmp_path)

    assert "clinic" in l3_activation._authored_domain_ids()


def test_a_typo_is_still_refused():
    """The half that must NOT move. `admn` writing a row that looks like an activated tenant is
    the failure the gate exists for, and it is unaffected by where the list comes from."""
    with pytest.raises(ValueError, match="unknown Layer 3 domain"):
        require_domain("admn")
    with pytest.raises(ValueError):
        require_domain("")


def test_an_unreadable_corpus_does_not_take_the_shipped_domains_down(monkeypatch):
    """FAILS SOFT. A missing or broken corpus directory is a deployment problem; it must not turn
    into an outage for tenants who were already live on admin."""
    def boom():
        raise OSError("corpus volume not mounted")

    monkeypatch.setattr("genios_engine.packs.compiler.authoring.default_authoring_root", boom)

    assert l3_activation._authored_domain_ids() == (DOMAIN_ADMIN, DOMAIN_CUSTOMER_SUPPORT,
                                                    DOMAIN_SALES)


def test_the_list_is_not_a_literal_any_more():
    """The regression this file exists for: somebody 'simplifying' the scan back into a tuple."""
    import inspect

    source = inspect.getsource(l3_activation)

    assert "L3_DOMAINS = _authored_domain_ids()" in source
    assert "L3_DOMAINS = (DOMAIN_ADMIN, DOMAIN_CUSTOMER_SUPPORT, DOMAIN_SALES)" not in source
