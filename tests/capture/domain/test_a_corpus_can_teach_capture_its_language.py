"""L1-01 — L1 could name four businesses, and the list was a Python regex table.

    pytest tests/capture/domain/test_a_corpus_can_teach_capture_its_language.py -q

A footwear exporter's core domain is production-and-shipping. *"Container held at Nhava Sheva,
BIS certificate pending, L/C expires Friday"* matched none of the four patterns, so
`domain_hints` returned `[]` and the signal was tagged with nothing. For a law firm it was
worse than nothing: the one word that DID match — `legal` — typed every matter email as
back-office admin.

And the domain could not even be assessed. `compute_coverage` returns
`coverage_state='unknown_domain'` with every readiness predicate FALSE for a name not in
`PACK_REQUIREMENTS`, and `declaration.py` iterated that dict — so a tenant who authored a
corpus and connected exactly the right tools was told, forever, that nothing was ready.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.coverage.model import (
    PACK_REQUIREMENTS,
    _already_shipped,
    _authored_requirements,
    pack_requirements,
)
from genios_engine.capture.domain.hints import _ordered_keywords, domain_hints

pytestmark = pytest.mark.unit


def corpus(tmp_path, name, domain_id, extra=""):
    (tmp_path / name).mkdir(exist_ok=True)
    (tmp_path / name / "domain.yaml").write_text(
        f"identity:\n  id: {domain_id}\n  name: {name}\n  version: 0.1.0\n{extra}")


LOGISTICS = """hints:
  rank: 15
  keywords:
    - '\\b(container|bill of lading|L/?C|customs|Nhava Sheva|BIS certificate)\\b'
  source_priors: [cargowise]
coverage:
  required: [communication, document_store]
  recommended: [finance]
"""


@pytest.fixture
def authored(tmp_path, monkeypatch):
    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root",
                        lambda: tmp_path)
    return tmp_path


# =============================================================================================
# The exporter whose mail matched nothing.
# =============================================================================================
def test_an_authored_corpus_can_recognise_its_own_vocabulary(authored):
    corpus(authored, "Logistics Expertise", "logistics", LOGISTICS)

    hints = domain_hints("gmail", "Container held at Nhava Sheva, BIS certificate pending")

    assert [h.domain for h in hints] == ["logistics"]


def test_an_authored_corpus_can_claim_its_own_tool(authored):
    corpus(authored, "Logistics Expertise", "logistics", LOGISTICS)

    assert [h.domain for h in domain_hints("cargowise", None)] == ["logistics"]


def test_an_authored_source_prior_overrides_the_shipped_one(authored):
    """REVERSED DELIBERATELY, and the distinction is the point.

    A KEYWORD prior is a claim about LANGUAGE — "term sheet" means fundraising in every
    business — so the shipped table, calibrated against a live graph, beats an authored file.
    A SOURCE prior is a claim about WHOSE ACCOUNT THIS IS, and the engine cannot know that.
    `stripe -> admin` assumes the tenant is a BUYER; for a SaaS founder whose Stripe holds
    their CUSTOMERS' subscriptions it is exactly backwards, and it filed all of their revenue
    under back-office ahead of any pattern.
    """
    corpus(authored, "Revenue Expertise", "revenue",
           LOGISTICS.replace("[cargowise]", "[stripe]"))

    assert [h.domain for h in domain_hints("stripe", None)] == ["revenue"]


def test_the_shipped_prior_is_still_the_default(authored):
    """Every tenant that has said nothing — which is all of them today."""
    corpus(authored, "Logistics Expertise", "logistics", LOGISTICS)

    assert [h.domain for h in domain_hints("stripe", None)] == ["admin"]


def test_a_shipped_KEYWORD_is_still_never_overridden(authored):
    """The half that does NOT reverse: language is not the tenant's to redefine."""
    corpus(authored, "Sales Expertise", "sales", LOGISTICS)

    assert [h.domain for h in domain_hints("gmail", "container at Nhava Sheva")] == []


# =============================================================================================
# Rank is a number now, and it was dict insertion order.
# =============================================================================================
def test_the_ordering_that_matters_survives(authored):
    """`fundraising` before `sales` is the whole point: an investor thread says "deck" AND
    "budget", and letting the generic sales words claim it turned six VCs and three accelerator
    programmes into sales opportunities. Not one of that org's sixteen sales situations was a
    customer."""
    corpus(authored, "Logistics Expertise", "logistics", LOGISTICS)

    order = [name for name, _ in _ordered_keywords()]

    assert order.index("fundraising") < order.index("sales")
    assert order.index("logistics") < order.index("sales")     # rank 15 beats rank 20


def test_two_domains_at_one_rank_order_by_name_not_by_the_filesystem(authored):
    corpus(authored, "Bravo Expertise", "bravo", LOGISTICS.replace("rank: 15", "rank: 25"))
    corpus(authored, "Alpha Expertise", "alpha", LOGISTICS.replace("rank: 15", "rank: 25"))

    order = [name for name, _ in _ordered_keywords()]

    assert order.index("alpha") < order.index("bravo")


def test_a_shipped_domain_is_never_overwritten_by_a_corpus(authored):
    """Their patterns are calibrated against a live graph; an authored file has no evidence
    behind it."""
    corpus(authored, "Sales Expertise", "sales", LOGISTICS)

    assert [h.domain for h in domain_hints("gmail", "container at Nhava Sheva")] == []


# =============================================================================================
# It fails soft.
# =============================================================================================
def test_a_broken_regex_in_one_corpus_does_not_blind_capture(authored):
    corpus(authored, "Broken Expertise", "broken",
           "hints:\n  rank: 5\n  keywords: ['[unclosed']\n")
    corpus(authored, "Logistics Expertise", "logistics", LOGISTICS)

    assert [h.domain for h in domain_hints("gmail", "container at Nhava Sheva")] == ["logistics"]
    assert [h.domain for h in domain_hints("gmail", "the term sheet")] == ["fundraising"]


def test_an_unreadable_corpus_leaves_the_shipped_four(monkeypatch):
    def boom():
        raise OSError("corpus volume not mounted")

    monkeypatch.setattr("genios_engine.platform.corpus.corpus_root", boom)

    assert [name for name, _ in _ordered_keywords()] == ["fundraising", "sales",
                                                         "support", "admin"]


# =============================================================================================
# Coverage: the domain can now be assessed at all.
# =============================================================================================
def test_an_authored_domain_gets_assessed(authored):
    corpus(authored, "Logistics Expertise", "logistics", LOGISTICS)

    got = pack_requirements()

    assert got["logistics"]["required"] == ["communication", "document_store"]
    assert got["logistics"]["recommended"] == ["finance"]


def test_a_corpus_that_says_nothing_needs_only_mail(authored):
    """Requiring more of a corpus that has not said what it needs would report a correctly
    connected tenant as permanently incomplete — the same failure as reporting an unassessed
    one as ready, pointed the other way."""
    corpus(authored, "Clinic Expertise", "clinic")

    assert pack_requirements()["clinic"]["required"] == ["communication"]


# =============================================================================================
# The alias table is many-to-one, and reversing it broke sales.
# =============================================================================================
def test_a_shipped_requirement_set_is_never_replaced():
    """A BUG THIS FILE CAUGHT. `DOMAIN_ALIASES` maps `fundraising`->`sales` AND
    `investor`->`sales`, so inverting it is not a function: `reverse['sales']` gave `'investor'`,
    `sales` looked like a new authored domain, and its real requirements were overwritten with
    the bare default. A tenant with a connected CRM would have been told sales coverage was
    complete without one."""
    assert pack_requirements()["sales"]["required"] == PACK_REQUIREMENTS["sales"]["required"]
    assert "crm" in pack_requirements()["sales"]["required"]


@pytest.mark.parametrize("domain_id", ["sales", "admin", "customer_support", "support",
                                       "fundraising", "investor"])
def test_every_name_a_shipped_set_speaks_for_is_recognised(domain_id):
    assert _already_shipped(domain_id)


def test_todays_corpora_add_nothing():
    """A live statement: all three authored corpora are already shipped domains, so the merge
    is a no-op right now. When that stops being true this test says so."""
    assert _authored_requirements() == {}
