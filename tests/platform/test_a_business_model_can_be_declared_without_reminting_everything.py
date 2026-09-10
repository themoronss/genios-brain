"""BM-1 — the variant lane was authored, compiled and never selected; selecting it safely.

    pytest tests/platform/test_a_business_model_can_be_declared_without_reminting_everything.py -q

127 variant documents, loaded and integrity-checked, chosen on metadata keys nothing wrote.
The measured plan's load-bearing rule: the key must be ABSENT when a tenant declares nothing,
because `contracts/situation.content_key()` hashes the whole metadata dict, and a key written
`[]` on every situation would re-mint an expertise package per situation — the 995 MB
incident's mechanism.
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.packs.compiler import expertise_builder, knowledge_retriever
from genios_engine.platform import l3_activation
from genios_engine.platform.l3_activation import _variant_tuple

pytestmark = pytest.mark.unit


def test_a_declaration_round_trips_and_is_deduplicated():
    assert _variant_tuple(["sales.model.b2b.saas", "sales.model.b2b.saas", " "]) == \
        ("sales.model.b2b.saas",)
    assert _variant_tuple('["a","b"]') == ("a", "b"), "a driver may hand jsonb back as text"


def test_an_unreadable_declaration_is_nothing_not_a_partial_list():
    assert _variant_tuple(object()) == ()
    assert _variant_tuple(None) == ()


def test_activate_fills_in_a_blank_declaration_and_never_overwrites_a_live_one():
    src = inspect.getsource(l3_activation.activate)

    assert "jsonb_array_length(" in src and "> 0" in src
    assert "then " in src and ".variant_ids else excluded.variant_ids end" in src


def test_declared_variants_fails_closed():
    class Boom:
        def connect(self):
            raise OSError("down")

    assert l3_activation.declared_variants(Boom(), "org", "sales") == ()


def test_the_situation_key_is_absent_when_nothing_is_declared():
    """THE LOAD-BEARING LINE."""
    from genios_engine.context import situation_bso

    src = inspect.getsource(situation_bso.build_business_situation)

    assert '**({"model_ids": list(variant_ids)} if variant_ids else {})' in src


def test_a_typo_no_longer_becomes_a_tenant_wide_error():
    src = inspect.getsource(knowledge_retriever.KnowledgeRetriever._resolve_variants) \
        if hasattr(knowledge_retriever, "KnowledgeRetriever") \
        else inspect.getsource(knowledge_retriever)

    assert "raise AuthoringIntegrityError" not in src
    assert "self._unresolved = tuple(sorted(missing))" in src


def test_the_package_names_what_it_could_not_resolve_only_when_there_is_something():
    src = inspect.getsource(expertise_builder)

    assert 'if unresolved:\n            metadata["unresolved_variant_ids"] = list(unresolved)' in src
