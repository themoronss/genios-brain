"""A declaration that does not reach `variant_ids` is a form nobody's answer leaves.

    pytest tests/context/test_declaring_a_profile_points_layer_three_at_it.py -q

Step 1 gave a tenant a way to SAY what it is. This is the half that makes the saying matter:
the facts land on the tenant node, and the selection they imply reaches
`l3_activation.variant_ids`, which is the column the compiler already reads and which has held
`[]` on every row of every tenant since it existed.

TWO WRITERS, NOT ONE, AND THE SPLIT IS THE POINT. `l3_activation.activate` refuses to overwrite a
non-empty `variant_ids` — its own comment says changing which business model a tenant runs under
"is its own decision, not a side-effect of re-clicking activate". Correct, and it left no way to
correct a mistake: a tenant that declared `saas` on Monday could not become `ai_agency` on
Tuesday. `set_variants` is that deliberate decision, separate so it cannot happen by accident.

ORDER MATTERS: facts first, switch second. `variant_ids` is DERIVED from the facts. Writing the
switch first and failing on the facts would leave a tenant compiling against a branch with
nothing in the graph saying why — which is precisely the state every tenant is in today, a
configuration column with no stated reason behind it. Derived state must not outlive its source.
"""
from __future__ import annotations

import pytest

from genios_engine.context import tenant_profile as TP

pytestmark = pytest.mark.unit


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    for domain, axis, slug, ident, fname in (
            ("Admin Expertise", "verticals", "ai_agency", "admin.vertical.ai_agency", "vertical.yaml"),
            ("Admin Expertise", "roles", "cto", "admin.role.cto", "role.yaml")):
        d = tmp_path / domain / axis / slug
        d.mkdir(parents=True)
        (d / fname).write_text(f"identity:\n  id: {ident}\n")
    monkeypatch.setattr(TP, "corpus_root", lambda: tmp_path)
    TP._axis_entries.cache_clear()
    yield
    TP._axis_entries.cache_clear()


class _Store:
    """Records what the declaration asked the graph to do, without a database."""

    def __init__(self) -> None:
        self.node_calls: list[dict] = []
        self.facts: list[dict] = []

    def find_or_create_node(self, conn, **kw):
        self.node_calls.append(kw)
        return "node_tenant_1"

    def write_fact(self, conn, **kw):
        self.facts.append(kw)
        return "fv_1"


class _Engine:
    """`engine.begin()` as a no-op context manager. The order of calls is what is under test."""

    def begin(self):
        class _Ctx:
            def __enter__(self_inner):
                return object()

            def __exit__(self_inner, *exc):
                return False
        return _Ctx()


def _patch_activation(monkeypatch, *, domains=("admin",), live=("admin",), log=None):
    monkeypatch.setattr("genios_engine.platform.l3_activation.activated_domains",
                        lambda engine, org: frozenset(domains))

    def _set(engine, org_id, *, domain, variant_ids, by, at=None):
        if log is not None:
            log.append((domain, tuple(variant_ids), by))
        return object() if domain in live else None
    monkeypatch.setattr("genios_engine.platform.l3_activation.set_variants", _set)


def test_a_declaration_reaches_the_column_the_compiler_reads(corpus, monkeypatch) -> None:
    log: list = []
    _patch_activation(monkeypatch, log=log)
    store, engine = _Store(), _Engine()

    out = TP.declare(engine, store, "org_1", category="ai_agency", reader_role="cto", by="rohit")

    assert out["variant_ids"] == ("cto", "ai_agency"), "most specific first"
    assert log == [("admin", ("cto", "ai_agency"), "rohit")]
    assert out["domains_switched"] == ("admin",)


def test_the_facts_land_on_the_tenant_node(corpus, monkeypatch) -> None:
    _patch_activation(monkeypatch)
    store, engine = _Store(), _Engine()

    TP.declare(engine, store, "org_1", category="ai_agency", by="rohit")

    assert store.node_calls[0]["canonical_key"] == "tenant:org_1"
    fields = [f["field"] for f in store.facts]
    assert fields == [TP.CATEGORY_FIELD, TP.CATEGORY_BASIS_FIELD]
    assert all(f["authority_rank"] == 6 for f in store.facts), (
        "an account holder describing their own company outranks anything extracted from prose")
    assert all(f["source"] == "declaration" for f in store.facts)


def test_a_value_no_corpus_authors_is_refused_before_anything_is_written(corpus, monkeypatch) -> None:
    """THE SILENT-FALLBACK TRAP. A stored `law_firm` resolves to nothing: the package records
    `unresolved_variant_ids`, the console shows the tenant configured, and the cards stay
    canonical. Nothing must be written."""
    log: list = []
    _patch_activation(monkeypatch, log=log)
    store, engine = _Store(), _Engine()

    with pytest.raises(TP.UndeclaredProfileValue, match="law_firm"):
        TP.declare(engine, store, "org_1", category="law_firm", by="rohit")

    assert store.facts == [], "a refused declaration wrote a fact"
    assert log == [], "a refused declaration moved the switch"


def test_facts_are_written_before_the_switch_moves(corpus, monkeypatch) -> None:
    """Derived state must not outlive its source. If the switch went first and the fact write
    raised, the tenant would compile against a branch nothing in the graph explains."""
    order: list[str] = []
    monkeypatch.setattr("genios_engine.platform.l3_activation.activated_domains",
                        lambda engine, org: frozenset({"admin"}))
    monkeypatch.setattr("genios_engine.platform.l3_activation.set_variants",
                        lambda *a, **k: order.append("switch") or object())
    store, engine = _Store(), _Engine()
    real_write = store.write_fact

    def _spy(conn, **kw):
        order.append("fact")
        return real_write(conn, **kw)
    store.write_fact = _spy

    TP.declare(engine, store, "org_1", category="ai_agency", by="rohit")
    assert order.index("fact") < order.index("switch")


def test_every_activated_domain_gets_the_same_profile(corpus, monkeypatch) -> None:
    """A tenant is one company. It does not sell into one vertical for Admin and another for
    Sales — which corpus has AUTHORED that branch is the corpus's business, reported as
    `unresolved_variant_ids`, not a question the tenant answers three times."""
    log: list = []
    _patch_activation(monkeypatch, domains=("admin", "sales", "customer_support"),
                      live=("admin", "sales", "customer_support"), log=log)
    TP.declare(_Engine(), _Store(), "org_1", category="ai_agency", by="rohit")
    assert [d for d, _v, _b in log] == ["admin", "customer_support", "sales"]
    assert {v for _d, v, _b in log} == {("ai_agency",)}


def test_a_domain_switched_off_is_skipped_not_revived(corpus, monkeypatch) -> None:
    """Reviving a disabled pair is `activate`'s decision and starts a new pilot period. A profile
    declaration is not that decision."""
    _patch_activation(monkeypatch, domains=("admin", "sales"), live=("admin",))
    out = TP.declare(_Engine(), _Store(), "org_1", category="ai_agency", by="rohit")
    assert out["domains_switched"] == ("admin",)


def test_a_tenant_with_no_activated_domain_still_records_what_it_is(corpus, monkeypatch) -> None:
    """The honest half-state: we know what they are, Layer 3 is not on for them yet."""
    _patch_activation(monkeypatch, domains=(), live=())
    store = _Store()
    out = TP.declare(_Engine(), store, "org_1", category="ai_agency", by="rohit")
    assert out["domains_switched"] == ()
    assert [f["field"] for f in store.facts] == [TP.CATEGORY_FIELD, TP.CATEGORY_BASIS_FIELD]
