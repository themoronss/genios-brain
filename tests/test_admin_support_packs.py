"""Admin and Customer Support had no pack, so 106 authored capabilities emitted nothing.

WHAT WAS BROKEN

`ReasoningStore.persist_complete` (reason/store.py:928) refuses a write unless the config
snapshot's `pack_id` equals the capability's `domain`. `domain_shadow._tenant_pack` resolves that
snapshot from `tenant_packs`, and only `general_v1` and `sales_v1` existed as pack modules. So
every Admin capability (57) and every Customer Support capability (49) reached
`domain_shadow.py:387`, was counted under `no_tenant_pack`, and emitted nothing — regardless of
how well it was authored, and with no error anywhere that named the cause.

These tests are split deliberately. The hermetic half pins the pack DATA (a rule-free pack is a
design decision, not an unfinished one, and the declared fields have to be fields Layer 2 really
writes). The real-Postgres half runs the actual seam — extraction, node creation, correlation,
situation typing, tenant-pack resolution, compile and signal emission — because every unit here
was already correct and the joint between them was not.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import yaml
from sqlalchemy import text

from genios_engine.context import situations
from genios_engine.context.pipeline import process_event
from genios_engine.packs.admin_v1 import ADMIN_V1
from genios_engine.packs.general_v1 import GENERAL_V1
from genios_engine.packs.sales_v1 import SALES_V1
from genios_engine.packs.support_v1 import SUPPORT_V1
from genios_engine.packs.wiring import BUILTIN_PACKS, DEFAULT_PACKS

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)
NEW_PACKS = (ADMIN_V1, SUPPORT_V1)


# ── pack data ───────────────────────────────────────────────────────────────────

def test_the_pack_id_is_the_corpus_domain_id_not_the_domain_hint():
    """The comparison that was failing is `config_snapshots.pack_id == manifest.domain`, and
    `manifest.domain` comes from the CORPUS (`<Domain> Expertise/domain.yaml` identity.id) — not
    from the Layer 1 domain hint. Support is the case where the two differ: the hint is `support`,
    the corpus folder is `customer_support`. A pack named `support` would resolve nothing and
    reproduce the exact bug it exists to fix."""
    from genios_engine.reason.domain_shadow import expert_catalog

    catalog = expert_catalog()
    assert ADMIN_V1["id"] in catalog.domains
    assert SUPPORT_V1["id"] in catalog.domains
    assert SUPPORT_V1["id"] == "customer_support"


def test_both_new_packs_are_registered_and_defaulted():
    """A pack nobody applies is a pack nobody has. `ensure_defaults` reads DEFAULT_PACKS."""
    ids = {p["id"] for p in BUILTIN_PACKS}
    assert {"admin", "customer_support"} <= ids
    defaults = dict(DEFAULT_PACKS)
    assert defaults["admin"] == ADMIN_V1["version"]
    assert defaults["customer_support"] == SUPPORT_V1["version"]


def test_the_new_packs_carry_no_legacy_rules_and_that_is_deliberate():
    """Rule-free BY DESIGN, pinned here so it cannot be quietly "completed" later.

    Three reasons, all of them in `packs/admin_v1.py`'s docstring: the compiled Layer 3 brain is
    the lane (its rule ids are capability ids), the daily signal budget is shared org-wide so a
    restated `unanswered_email` would emit a duplicate card and spend the budget twice, and every
    genuinely admin/support-native trigger rests on facts Layer 2 does not write.
    """
    for pack in NEW_PACKS:
        assert pack["rules"] == [], f"{pack['id']} grew legacy rules — read the module docstring"
        assert pack["plays"] == {}


def test_scoring_stays_in_lockstep_with_the_packs_it_shares_a_budget_with():
    """One org's cards are ranked against each other inside ONE shared daily budget
    (`runner._budget_used` counts every signal regardless of pack). A different gate or band here
    would decide ties by scale rather than by merit."""
    for pack in NEW_PACKS:
        sc = pack["scoring_defaults"]
        for other in (SALES_V1, GENERAL_V1):
            osc = other["scoring_defaults"]
            for key in ("gate", "bands", "weights", "c_weights", "budget_per_user_day"):
                assert sc[key] == osc[key], f"{pack['id']}.{key} diverges from {other['id']}"
        assert sc["weights"]["u"] + sc["weights"]["i"] + sc["weights"]["r"] == 100


def test_every_declared_field_is_one_layer_two_actually_writes():
    """`context/extract/vocab.py::field_vocabulary` unions every pack's `schema.fields` into the
    L2 EXTRACTION PROMPT. A field named here is a field the model is told to go and find, so
    declaring `ticket.status` or `approval.state` — both of which these corpora would dearly like
    — invites a plausible invented value for a fact nobody stated.

    The authority is `_schema/vocabulary.yaml::substrate.fact_paths`, whose own provenance is the
    three real producers (ENGINE_FIELDS, the shipped packs' schemas, and the L2 pipeline's direct
    writes). `planned_substrate` is explicitly NOT allowed."""
    from genios_engine.packs.compiler.authoring import default_authoring_root

    vocab = yaml.safe_load(
        (default_authoring_root() / "_schema" / "vocabulary.yaml").read_text())
    allowed = set(vocab["substrate"]["fact_paths"])
    planned = set(vocab["planned_substrate"]["fact_paths"])
    for pack in NEW_PACKS:
        declared = set(pack["schema"]["fields"])
        assert not (declared & planned), (
            f"{pack['id']} declares planned-substrate fields {sorted(declared & planned)} — "
            "nothing writes them and the extractor would be asked to invent them")
        assert declared <= allowed, (
            f"{pack['id']} declares fields outside the substrate: {sorted(declared - allowed)}")


def test_the_new_packs_add_no_extraction_surface():
    """The corollary, stated as its own check: because every field is already declared by an
    existing pack or by ENGINE_FIELDS, the union the extractor sees is byte-identical before and
    after these packs ship. Shipping them cannot change what Layer 2 captures."""
    from genios_engine.context.extract.vocab import field_vocabulary

    old = {"sales": {"pack_id": "sales", **SALES_V1},
           "general": {"pack_id": "general", **GENERAL_V1}}
    new = dict(old, admin={"pack_id": "admin", **ADMIN_V1},
               customer_support={"pack_id": "customer_support", **SUPPORT_V1})
    assert set(field_vocabulary(new)) == set(field_vocabulary(old))


def test_signal_vocab_names_the_situation_types_the_lane_actually_emits():
    """For a compiled-brain pack the reason code is the L2 SITUATION TYPE, because
    `_emit_capability_signal` derives a signal's rule_id from the capability id's last segment
    (`expertise.account_admin` -> `account_admin`) and the delivery authority predicate
    re-derives it the same way. Anything else here would be decoration."""
    from genios_engine.context.situations import situation_type

    assert set(ADMIN_V1["schema"]["signal_vocab"]) == {
        situation_type("company", "admin"), situation_type("person", "admin")}
    assert set(SUPPORT_V1["schema"]["signal_vocab"]) == {
        situation_type("company", "support"), situation_type("person", "support")}


def test_no_rule_id_can_collide_with_a_compiled_capability():
    """`_emit_capability_signal` refuses to emit when a compiled capability's rule id matches a
    tenant pack rule id — the open-signal uniqueness key is (org, pack, version, rule_id, node),
    so the two brains would evict each other. Rule-free packs cannot collide; this checks the
    OTHER packs' rules against the new signal vocabularies too, because the pack lookup is keyed
    on the capability's domain and a future rename could cross the lanes."""
    vocab = set(ADMIN_V1["schema"]["signal_vocab"]) | set(SUPPORT_V1["schema"]["signal_vocab"])
    for pack in BUILTIN_PACKS:
        clash = {r["id"] for r in pack["rules"]} & vocab
        assert not clash, f"{pack['id']} rule ids collide with a compiled situation type: {clash}"


# ── the seam, against a real Postgres ───────────────────────────────────────────

def _seed_org(store, org: str) -> None:
    """The FK-parent org row, filling any NOT-NULL-no-default column so graph_nodes.org_id
    resolves. Columns are discovered rather than listed so the next migration does not break a
    test about something else."""
    with store.engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        parts, ph, vals = ["id"], [":id"], {"id": org}
        for r in reqd:
            parts.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else "o@x.test" if "email" in r.column_name else org)
        conn.execute(text(f"insert into orgs ({','.join(parts)}) values ({','.join(ph)}) "
                          "on conflict do nothing"), vals)


def _seed_event(conn, org: str, event_id: str, domain: str) -> None:
    reqd = conn.execute(text(
        "select column_name, data_type from information_schema.columns "
        "where table_name='source_events' and is_nullable='NO' and column_default is null")).all()
    vals = {"event_id": event_id, "org_id": org, "source": "gmail", "object_type": "email",
            "outcome": "emitted", "occurred_at": NOW,
            "domain_hints": json.dumps([{"domain": domain}])}
    for r in reqd:
        if r.column_name in vals:
            continue
        vals[r.column_name] = (NOW if ("time" in r.data_type or "date" in r.data_type)
                               else 0 if ("int" in r.data_type or "numeric" in r.data_type)
                               else "{}" if "json" in r.data_type
                               else f"{r.column_name}_{event_id}")
    cols = ",".join(vals)
    conn.execute(text(f"insert into source_events ({cols}) "
                      f"values ({','.join(':' + c for c in vals)}) on conflict do nothing"), vals)


class _FakeResult:
    ok, raw, input_tokens, output_tokens, error = True, "{}", 10, 20, None

    def __init__(self, parsed):
        self.parsed = parsed


class _FakeLLM:
    model = "fake-haiku"

    def __init__(self, parsed):
        self._parsed = parsed

    def call(self, prompt, *, max_tokens=4096):
        return _FakeResult(self._parsed)


# Every fact and observation below is substring-backed: the grounding guard silently discards
# anything it cannot find in the content, so a canned payload that ignores that tests nothing.
_ADMIN_CONTENT = (
    "Meera at Northwind Registry confirmed our filing was received and is under review. "
    "She asked us to send the signed authorisation form by 27 August. "
    "We said we would send it on Tuesday.")

_ADMIN_CANNED = {
    "relevance": 0.9, "noise_type": "none", "domains": ["admin"],
    "entity_mentions": [
        {"type": "person", "name": "Meera", "email": "meera@northwind-registry.test",
         "evidence_text": "Meera at Northwind Registry"},
        {"type": "company", "name": "Northwind Registry", "email": None,
         "evidence_text": "at Northwind Registry"}],
    "fact_candidates": [
        {"subject": "Meera", "field": "thread.ball_in_court", "value": "us",
         "evidence_text": "asked us to send the signed authorisation form"}],
    "commitments": [
        {"actor": "us", "action": "send the signed authorisation form",
         "due_at": "2026-08-27", "evidence_text": "send the signed authorisation form by 27 August"}],
    "questions": [],
    "observations": [{"kind": "next_step_agreed",
                      "evidence_text": "We said we would send it on Tuesday"}],
}


_SUPPORT_CONTENT = (
    "Dan at Harbourworks reports the export job has been failing since Monday and his team is "
    "blocked. He is waiting on us for a fix date. We promised an update by 22 August.")

_SUPPORT_CANNED = {
    "relevance": 0.9, "noise_type": "none", "domains": ["support"],
    "entity_mentions": [
        {"type": "person", "name": "Dan", "email": "dan@harbourworks.test",
         "evidence_text": "Dan at Harbourworks"},
        {"type": "company", "name": "Harbourworks", "email": None,
         "evidence_text": "at Harbourworks"}],
    "fact_candidates": [
        {"subject": "Dan", "field": "thread.ball_in_court", "value": "us",
         "evidence_text": "He is waiting on us for a fix date"}],
    "commitments": [
        {"actor": "us", "action": "send an update on the export job",
         "due_at": "2026-08-22", "evidence_text": "We promised an update by 22 August"}],
    "questions": [],
    "observations": [{"kind": "question", "evidence_text": "waiting on us for a fix date"}],
}


def _run_admin(store, org: str, event_id: str = "adm_evt") -> None:
    with store.engine.begin() as conn:
        _seed_event(conn, org, event_id, "admin")
    res = process_event(org_id=org, event_id=event_id, source="gmail", content=_ADMIN_CONTENT,
                        sender_email="meera@northwind-registry.test", occurred_at=NOW,
                        llm=_FakeLLM(_ADMIN_CANNED), store=store, is_inbound=True,
                        internal_emails=frozenset(), domain_hints=[{"domain": "admin"}])
    assert res.outcome == "committed"


def test_admin_correspondence_types_as_an_account_admin_situation(pg_store):
    """The door the corpus is waiting behind. `domain_spec` types a company-anchored admin
    situation `account_admin`, and `admin.sit.live_account_admin` claims exactly that type."""
    org = "pk_admin_type"
    _seed_org(pg_store, org)
    _run_admin(pg_store, org)
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    with pg_store.engine.begin() as conn:
        types = {s["situation_type"] for s in situations.active_situations(conn, org_id=org)}
    assert "account_admin" in types, f"expected account_admin, got {types}"


def test_the_tenant_resolves_an_admin_pack_lane_where_it_used_to_resolve_none(pg_store):
    """THE regression this whole change exists for, at the exact call site.

    `_tenant_pack(registry, store, org, 'admin')` returned None for every org that has ever
    existed, because no `admin` row could be in `tenant_packs` when no `admin` pack module was in
    `BUILTIN_PACKS`. `shadow_compile` counted that as `no_tenant_pack` and `continue`d — the one
    line standing between 106 authored capabilities and a card."""
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.domain_shadow import _tenant_pack

    org = "pk_admin_lane"
    _seed_org(pg_store, org)
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    with pg_store.engine.connect() as conn:
        rows = {r.pack_id: r for r in conn.execute(text(
            "select pack_id, version, state, authority_revision from tenant_packs "
            "where org_id=:o"), {"o": org})}
    assert set(rows) == {"sales", "general", "admin", "customer_support"}

    for pack_id in ("admin", "customer_support"):
        lane = _tenant_pack(registry, pg_store, org, pack_id)
        assert lane is not None, f"{pack_id} still resolves no tenant pack"
        # > 0 is not incidental: `_tenant_pack` rejects a zero authority_revision, and the
        # delivery authority predicate joins on the same number.
        assert lane["revision"] > 0
        assert lane["pack_id"] == pack_id and lane["snapshot_id"]
        # The equality `persist_complete` enforces, checked against the real persisted snapshot
        # rather than against the manifest we happen to hold in memory.
        with pg_store.engine.connect() as conn:
            stored = conn.execute(text(
                "select pack_id from config_snapshots where org_id=:o and snapshot_id=:s"),
                {"o": org, "s": lane["snapshot_id"]}).scalar()
        assert stored == pack_id


def test_an_admin_situation_now_compiles_instead_of_dying_on_no_tenant_pack(pg_store):
    """End to end on real SQL: correspondence -> facts -> nodes -> correlation -> situation ->
    route -> compile -> reason -> persisted signal.

    The assertion that matters is `no_tenant_pack == 0` together with a non-zero compile. Before
    this change the same run produced `compiled > 0` and `no_tenant_pack == compiled`: the corpus
    was resolved, the package was built, and then it was thrown away."""
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.domain_shadow import shadow_compile

    org = "pk_admin_compile"
    _seed_org(pg_store, org)
    _run_admin(pg_store, org)
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)

    counts = shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True,
                            registry=registry)
    assert counts.get("compiled", 0) > 0, f"nothing compiled at all: {dict(counts)}"
    assert counts.get("no_tenant_pack", 0) == 0, (
        f"admin capabilities are still dying on the missing pack lane: {dict(counts)}")
    # Not just "did not die" — reached the end. A compile that decides and emits nothing looks
    # identical to a compile that was refused, which is how this went unnoticed for months.
    assert counts.get("emitted", 0) > 0, f"compiled but emitted nothing: {dict(counts)}"

    with pg_store.engine.connect() as conn:
        sig = conn.execute(text(
            "select rule_id, reason_code, pack_id, capability_id, status from signals "
            "where org_id=:o"), {"o": org}).mappings().all()
        packages = conn.execute(text(
            "select count(*) from expertise_packages where org_id=:o"), {"o": org}).scalar()
    assert len(sig) == 1, sig
    # Every one of these is load-bearing for delivery. `AUTHORITATIVE_SIGNAL_PREDICATE` joins
    # signal -> config_snapshot -> tenant_packs and re-derives the rule id from the capability id
    # (`regexp_replace(rr.capability_id, '^.*\\.', '')`), so a signal that sits in the wrong pack
    # lane or names the wrong rule is dropped silently at the last step.
    assert sig[0]["pack_id"] == "admin"
    assert sig[0]["capability_id"] == "expertise.account_admin"
    assert sig[0]["rule_id"] == "account_admin" == sig[0]["reason_code"]
    assert sig[0]["status"] == "open"
    assert packages == 1, "the package was reasoned over and never published"


def test_a_support_situation_reaches_the_customer_support_lane(pg_store):
    """The same seam for Customer Support, which is the harder of the two: the Layer 1 domain hint
    is `support` and the corpus domain — and therefore the pack id — is `customer_support`. If the
    pack had been named after the hint, this test would count `no_tenant_pack` exactly as before.
    """
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.domain_shadow import _tenant_pack, shadow_compile

    org = "pk_support_compile"
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as conn:
        _seed_event(conn, org, "sup_evt", "support")
    res = process_event(org_id=org, event_id="sup_evt", source="gmail", content=_SUPPORT_CONTENT,
                        sender_email="dan@harbourworks.test", occurred_at=NOW,
                        llm=_FakeLLM(_SUPPORT_CANNED), store=pg_store, is_inbound=True,
                        internal_emails=frozenset(), domain_hints=[{"domain": "support"}])
    assert res.outcome == "committed"
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    with pg_store.engine.begin() as conn:
        types = {s["situation_type"] for s in situations.active_situations(conn, org_id=org)}
    assert types & {"support_case", "support_contact"}, types

    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    lane = _tenant_pack(registry, pg_store, org, "customer_support")
    assert lane is not None and lane["pack_id"] == "customer_support"
    counts = shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True,
                            registry=registry)
    assert counts.get("no_tenant_pack", 0) == 0, dict(counts)


def test_a_rule_free_pack_does_not_sweep_every_node_for_nothing(pg_store):
    """`run_all` calls `run()` once per tenant pack. A pack with no rules and no native
    capability has nothing to evaluate per node, so without the early return, adding these two
    packs would have doubled the cost of every reasoning sweep to compute an empty Counter
    twice."""
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.runner import run

    org = "pk_rule_free"
    _seed_org(pg_store, org)
    _run_admin(pg_store, org)
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    result = run(org_id=org, store=pg_store, eval_time=NOW, registry=registry, pack_id="admin")
    assert result["nodes"] == 0 and result["outcomes"] == {}
    # It still reports WHICH pack declined, so a silent zero and a rule-free zero read apart.
    assert result["pack"]["pack_id"] == "admin"


def test_run_all_compiles_the_corpus_once_not_once_per_pack(pg_store):
    """The compile is org-scoped and pack-agnostic — it resolves its own pack per capability
    domain inside `shadow_compile`. It used to sit at the top of `run()`, which `run_all` calls
    once per pack, so the whole corpus compiled, reasoned and emitted twice per sweep and would
    have done so four times once these two packs became defaults."""
    import inspect

    from genios_engine.reason import runner

    assert "shadow_compile" not in inspect.getsource(runner.run)
    assert "shadow_compile" in inspect.getsource(runner.run_all)
