"""Two names for one domain, and the product's own domain is nobody's counterparty.

Three of the design partner's sixty situations found no route because of a vocabulary gap
rather than a corpus gap, and a fourth was the product's own website filed as a counterparty.
"""
import inspect

from genios_engine.context.correlation import resolve_domain
from genios_engine.context.domain_spec import canonical_domain, spec_for, spec_version
from genios_engine.context.situations import situation_type


# ── an alias is not a mislabel ──────────────────────────────────────────────────
def test_investor_and_fundraising_are_one_domain():
    """`_RELATIONSHIP_NATURES` offers the model `investor`; the registry calls the same domain
    `fundraising`. Nothing was wrong with either name — they never met. An unregistered name
    gets the generic spec, which types a company-anchored situation `<domain>_<anchor>`, so a
    fund the model called `investor` became `investor_company` and the authored investor route
    could not see it."""
    assert canonical_domain("investor") == "fundraising"
    assert spec_for("investor") is spec_for("fundraising")
    assert situation_type("company", "investor") == "investor_relationship"
    assert situation_type("person", "investor") == "investor_contact"


def test_an_unregistered_domain_is_still_visibly_unmapped():
    """Aliasing must not become a habit of guessing. A domain nobody has described still gets
    `<domain>_<anchor>` — never quietly filed as something it is not."""
    assert canonical_domain("recruiting") == "recruiting"
    assert situation_type("company", "recruiting") == "recruiting_company"


def test_the_domain_is_canonicalised_where_a_hint_becomes_the_domain():
    """`resolve_domain`'s result is the correlation key, the stored situation domain AND the hint
    Layer 3 resolves a corpus folder from. Aliasing anywhere later would leave those disagreeing."""
    assert resolve_domain([{"domain": "investor", "source": "model"}]) == "fundraising"
    # Ranking is untouched: a prior still outranks the model, and the winner is canonicalised.
    assert resolve_domain([{"domain": "investor", "source": "model"},
                           {"domain": "sales", "source": "prior"}]) == "sales"


def test_the_alias_table_is_inside_the_registry_stamp():
    """`spec_version` is stamped into every situation's `inputs` so a re-typing is attributable.
    An alias decides which spec a domain resolves to, so it changes the derived situation_type
    exactly as a spec edit does — leaving it out would make the change unattributable."""
    from genios_engine.context import domain_spec
    before = spec_version()
    domain_spec._ALIASES["zzz_test_alias"] = "sales"
    try:
        assert spec_version() != before
    finally:
        domain_spec._ALIASES.pop("zzz_test_alias")
    assert spec_version() == before


def test_layer_three_resolves_the_older_name_too():
    """Situations already stored under `investor` are real. Re-typing history silently is worse
    than reading it, so the corpus-side alias table maps the old name to its corpus folder."""
    from genios_engine.packs.compiler.capability_resolver import DOMAIN_ALIASES
    assert DOMAIN_ALIASES["investor"] == "sales"
    assert DOMAIN_ALIASES["fundraising"] == "sales"


# ── the product's own domain is not a counterparty ──────────────────────────────
def test_a_platform_company_node_is_marked_internal():
    """`is_platform_sender` kept `invite@thegenios.com` out of the PERSON graph, and only the
    person was protected: `_works_at` still minted a `thegenios.com` company node and left it
    eligible to anchor. The design partner carries a `recruiting_company` situation on
    `thegenios.com` — a card about his relationship with his own vendor's website."""
    from genios_engine.context import pipeline
    src = inspect.getsource(pipeline.commit_event if hasattr(pipeline, "commit_event")
                            else pipeline)
    marker = "if (_norm_email(email) or \"\") in internal_set or is_platform_sender(email):"
    assert marker in src, "the company-side platform guard is missing from _works_at"


def test_the_two_self_questions_stay_distinct():
    """"Is this the customer?" and "is this us, the product?" are different questions with
    different answers, and either one being yes means this is not a counterparty."""
    from genios_engine.context.pipeline import is_platform_sender
    assert is_platform_sender("ceo@thegenios.com")
    assert not is_platform_sender("boardy@boardy.ai")


# ── Admin has a door ────────────────────────────────────────────────────────────
def test_admin_now_routes_account_admin():
    """Fifty-seven authored Admin capabilities and zero situation files: `routes` is built per
    L2 type FROM the situation files, so the domain was content with no door."""
    from genios_engine.reason.domain_shadow import expert_catalog
    admin = expert_catalog().domain("admin")
    route = admin.routes.get("account_admin")
    assert route, "admin declares no route for account_admin"
    assert "admin.sit.live_account_admin" in (route.get("situations") or ())
    assert "admin.executive_support.commitment_tracking" in (route.get("capabilities") or ())


def test_the_admin_situation_states_that_it_cannot_deliver_yet():
    """It routes and it cannot become a card: `persist_complete` refuses the write unless
    `config_pack == capability_pack`, and no `admin` pack module exists. A situation that says so
    is honest; one that stays silent looks like coverage."""
    from genios_engine.reason.domain_shadow import expert_catalog
    sit = expert_catalog().domain("admin").situations["admin.sit.live_account_admin"]
    notes = ((sit.content.get("metadata") or {}).get("notes") or "").lower()
    assert "cannot yet deliver" in notes and "config_pack" in notes


def test_a_capability_domain_the_tenant_has_no_pack_for_is_counted_not_guessed():
    """The structural finding behind that note, pinned so it cannot regress into a silent skip:
    the compile counts `no_tenant_pack` and emits nothing."""
    from genios_engine.reason import domain_shadow
    src = inspect.getsource(domain_shadow.shadow_compile)
    assert 'counts["no_tenant_pack"] += 1' in src
    assert "if pack is None:" in src
