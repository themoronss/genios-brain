"""L1.4.9 · the extraction cache — key formula, read-through, storage, and the rename.

Doc 04's acceptance for this component is three lines:

    same content + same key components -> cache hit, zero LLM calls
    bump EXTRACTION_SCHEMA_VERSION    -> cache miss
    change profile_id                  -> cache miss

`test_spec_acceptance_*` are those three, and the zero-LLM one is mechanical rather than
asserted: the model client injected into the read-through raises on call, so a hit that touched
a model would be an error, not a number this file chose to trust.

Everything after them exists because a cache fails in exactly one direction — it answers when it
should not — and every one of those failures is silent. So the key tests are table-driven over
`KEY_COMPONENTS` itself: a component added to the formula and forgotten here fails the coverage
row rather than quietly going untested, which is the shape the 260-row incident took.

The last section is the RENAME (`l2_extraction_results` -> `l1_extraction_results`, migration
0080). `api/account_routes.py::_wipe` executes `delete from {tbl}` for every name in
`_ORG_SCOPED_TABLES` with no try/except, so a name left stale there does not leak rows — it makes
every account deletion and every /reset raise. That runs here against real PostgreSQL.
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text

from genios_engine.capture.semantic.cache import (
    CACHE_TABLE,
    KEY_COMPONENTS,
    CacheEntry,
    ExtractionCacheKey,
    InMemoryExtractionCache,
    PostgresExtractionCache,
    cache_key,
    cached_extraction,
)
from genios_engine.capture.semantic.profiles import TIERS
from genios_engine.capture.semantic.vocabulary import EXTRACTION_PROFILE, vocabulary_fingerprint
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment, EntityMention, ExtractionResult, Money

CONTENT = "Hi Dana — we can sign by Friday if Finance confirms the $12,000 line."
ENVELOPE = "direction=inbound from=dana@acme.example to=us@genios.example thread_position=3"

#: The key components as a caller supplies them. One dict so every test varies ONE thing.
BASE = {
    "org_id": "org_acme",
    "content": CONTENT,
    "profile_id": "email",
    "prompt_version": "l1.4.2:email:9f2c4d1a8b70",
    "schema_version": "3",
    "model_snapshot": "claude-haiku-4-5-20251001",
    "vocab_fingerprint": vocabulary_fingerprint(),
    "envelope": ENVELOPE,
}


def a_result(**over) -> ExtractionResult:
    """An ExtractionResult whose provenance matches `BASE` unless a test overrides it."""
    fields = {
        "intent": "commit", "stance": "cautious", "topics": ["renewal"],
        "model_snapshot": BASE["model_snapshot"], "prompt_version": BASE["prompt_version"],
        "schema_version": BASE["schema_version"], "extraction_profile": BASE["profile_id"],
        "input_tokens": 1840, "output_tokens": 260,
    }
    fields.update(over)
    return ExtractionResult(**fields)


class RaisingLLM:
    """A model client that cannot be called. Injected wherever a cache hit is asserted, so
    'zero LLM calls' is enforced by the runtime and not by a counter this file trusts."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> ExtractionResult:
        self.calls += 1
        raise AssertionError(
            "the model was called on a cache hit — the whole component failed")


class CountingLLM:
    """A model client that answers, and counts. For the miss paths."""

    def __init__(self, result: ExtractionResult | None = None) -> None:
        self.calls = 0
        self._result = result or a_result()

    def __call__(self) -> ExtractionResult:
        self.calls += 1
        return self._result


# ── doc-04 acceptance ─────────────────────────────────────────────────────────────────────────

def test_spec_acceptance_same_content_and_components_hits_with_zero_llm_calls():
    store = InMemoryExtractionCache()
    first_llm = CountingLLM()
    first = cached_extraction(store, cache_key(**BASE), event_id="evt_1", tier="T2",
                              extract=first_llm)
    assert (first.hit, first.stored, first.llm_calls, first_llm.calls) == (False, True, 1, 1)

    never = RaisingLLM()
    second = cached_extraction(store, cache_key(**BASE), event_id="evt_1", tier="T2",
                               extract=never)
    assert second.hit is True
    assert second.llm_calls == 0
    assert never.calls == 0
    assert second.result == first.result


def test_spec_acceptance_bumping_the_schema_version_misses():
    store = InMemoryExtractionCache()
    cached_extraction(store, cache_key(**BASE), event_id="evt_1", tier="T2",
                      extract=CountingLLM())

    bumped = {**BASE, "schema_version": "4"}
    llm = CountingLLM(a_result(schema_version="4"))
    outcome = cached_extraction(store, cache_key(**bumped), event_id="evt_1", tier="T2",
                                extract=llm)
    assert outcome.hit is False
    assert outcome.llm_calls == 1
    assert llm.calls == 1
    assert len(store) == 2          # the old row survives, it is simply unreachable


def test_spec_acceptance_changing_the_profile_misses():
    store = InMemoryExtractionCache()
    cached_extraction(store, cache_key(**BASE), event_id="evt_1", tier="T2",
                      extract=CountingLLM())

    as_document = {**BASE, "profile_id": "document"}
    llm = CountingLLM(a_result(extraction_profile="document"))
    outcome = cached_extraction(store, cache_key(**as_document), event_id="evt_1", tier="T3",
                                extract=llm)
    assert outcome.hit is False
    assert llm.calls == 1


# ── U1 · the key formula ──────────────────────────────────────────────────────────────────────

#: One row per key component: how to change it, and the matching provenance change the result
#: needs so the entry is still filable. A component in KEY_COMPONENTS with no row here fails
#: `test_every_key_component_is_covered`.
COMPONENT_CHANGES = [
    ("org_id",           {"org_id": "org_other"},                    {}),
    ("prompt_version",   {"prompt_version": "l1.4.2:email:000000000000"},
                         {"prompt_version": "l1.4.2:email:000000000000"}),
    ("schema_version",   {"schema_version": "4"},                    {"schema_version": "4"}),
    ("model_snapshot",   {"model_snapshot": "claude-opus-4-1-20250805"},
                         {"model_snapshot": "claude-opus-4-1-20250805"}),
    ("profile_id",       {"profile_id": "transcript"},
                         {"extraction_profile": "transcript"}),
    ("vocab_fingerprint", {"vocab_fingerprint": "0123456789ab"},     {}),
    ("envelope_hash",    {"envelope": ENVELOPE.replace("dana@acme.example",
                                                       "rival@other.example")}, {}),
    ("content_hash",     {"content": CONTENT + " Also: the number is 13,000."}, {}),
]


@pytest.mark.parametrize("component,change,_provenance",
                         COMPONENT_CHANGES, ids=[row[0] for row in COMPONENT_CHANGES])
def test_changing_any_key_component_changes_the_digest(component, change, _provenance):
    assert cache_key(**BASE).digest != cache_key(**{**BASE, **change}).digest, (
        f"{component} does not reach the digest: an extraction taken under the old value would "
        "answer for the new one")


def test_every_key_component_is_covered_by_a_change_row():
    """The coverage lock. Adding a component to the formula without a row above would leave it
    untested, and an untested component is one that can silently fall out of the digest."""
    assert {row[0] for row in COMPONENT_CHANGES} == set(KEY_COMPONENTS)


def test_identical_inputs_give_an_identical_digest():
    assert cache_key(**BASE).digest == cache_key(**BASE).digest


def test_the_key_format_is_pinned():
    """A golden digest. The formula's ORDER and framing are part of the stored format: change
    either and every row in `l1_extraction_results` becomes unreachable — the whole backlog
    re-extracts and re-bills. This test is the deliberate-change gate, not a tautology; it is
    computed from fixed literals, not from the implementation."""
    pinned = cache_key(org_id="org_acme", content="hello", profile_id="email",
                       prompt_version="p1", schema_version="3", model_snapshot="m1",
                       vocab_fingerprint="vf1", envelope="e1")
    assert pinned.digest == (
        "267b34934ec6678917ee8bb48472d3d9c49086c7200eb2af3d46475381074f81")


def test_components_cannot_run_together_across_the_separator():
    """`("acme:x", "y")` and `("acme", "x:y")` must not produce one cache slot. A plain `:` join
    makes them identical material; the framed join is what keeps them apart. Two of these fields
    are free text somebody types."""
    left = cache_key(**{**BASE, "org_id": "acme:x", "prompt_version": "y"})
    right = cache_key(**{**BASE, "org_id": "acme", "prompt_version": "x:y"})
    assert left.digest != right.digest


def test_the_key_carries_its_components_for_diagnosis():
    key = cache_key(**BASE)
    assert key.org_id == "org_acme"
    assert key.profile_id == "email"
    assert key.processing_key == key.digest
    assert len(key.digest) == 64
    described = key.describe()
    assert all(name in described for name in KEY_COMPONENTS)


BLANKABLE = ["org_id", "prompt_version", "schema_version", "model_snapshot", "vocab_fingerprint"]


@pytest.mark.parametrize("component", BLANKABLE)
def test_a_blank_component_is_refused_rather_than_hashed(component):
    with pytest.raises(ValueError, match=component):
        cache_key(**{**BASE, component: "   "})


@pytest.mark.parametrize("content", ["", "   \n\t "])
def test_empty_content_is_refused(content):
    with pytest.raises(ValueError, match="nothing to key"):
        cache_key(**{**BASE, "content": content})


@pytest.mark.parametrize("profile_id", ["", "  ", "e-mail", "pdf", "Email"])
def test_an_unregistered_profile_is_refused(profile_id):
    """`get_profile` falls back to email for an unknown id so a 3am sync survives; the KEY must
    not, or the fallback is filed as though it were the profile that ran."""
    with pytest.raises(ValueError, match="unknown extraction profile"):
        cache_key(**{**BASE, "profile_id": profile_id})


@pytest.mark.parametrize("profile_id", sorted(EXTRACTION_PROFILE))
def test_every_vocabulary_profile_is_keyable(profile_id):
    assert cache_key(**{**BASE, "profile_id": profile_id}).profile_id == profile_id


def test_an_absent_envelope_is_keyable():
    """An uploaded document has no sender. Demanding one would make the caller fabricate a
    header to get a key."""
    assert cache_key(**{k: v for k, v in BASE.items() if k != "envelope"}).digest


def test_an_absent_envelope_is_not_the_same_key_as_a_present_one():
    with_envelope = cache_key(**BASE)
    without = cache_key(**{k: v for k, v in BASE.items() if k != "envelope"})
    assert with_envelope.digest != without.digest


def test_the_envelope_is_what_the_l2_key_formula_omits():
    """The defect this unit refuses to inherit, stated as a property.

    Two messages with byte-identical bodies and opposite direction — the same quote, once
    received and once sent — are ONE cache slot under a key over content alone. The second is
    then answered with the first's direction, which is the exact 'an outbound offer reads as an
    inbound request' bug doc 04 says was already fixed once. `context/pipeline.py` keys over
    `org : prompt : schema : model : vocab : content` and has this collision today; this key
    does not.
    """
    inbound = cache_key(**{**BASE, "envelope": "direction=inbound from=dana@acme.example"})
    outbound = cache_key(**{**BASE, "envelope": "direction=outbound from=us@genios.example"})
    assert inbound.content_hash == outbound.content_hash      # same body, as in the real case
    assert inbound.digest != outbound.digest


# ── U2 · the entry guard ──────────────────────────────────────────────────────────────────────

PROVENANCE_MISMATCHES = [
    ("prompt_version", {"prompt_version": "l1.4.2:email:deadbeef0000"}),
    ("schema_version", {"schema_version": "9"}),
    ("model_snapshot", {"model_snapshot": "claude-opus-4-1-20250805"}),
    ("profile_id", {"extraction_profile": "chat"}),
]


@pytest.mark.parametrize("field,over", PROVENANCE_MISMATCHES,
                         ids=[row[0] for row in PROVENANCE_MISMATCHES])
def test_a_result_may_not_be_filed_under_a_key_that_misdescribes_it(field, over):
    with pytest.raises(ValueError, match="provenance does not match"):
        CacheEntry(key=cache_key(**BASE), event_id="evt_1", tier="T2", result=a_result(**over))


def test_a_matching_result_is_filable_and_reports_the_call_cost():
    entry = CacheEntry(key=cache_key(**BASE), event_id="evt_1", tier="T2", result=a_result())
    assert entry.input_tokens == 1840
    assert entry.output_tokens == 260


@pytest.mark.parametrize("tier", ["T4", "t2", "haiku", ""])
def test_an_unknown_tier_is_refused(tier):
    with pytest.raises(ValueError, match="unknown model tier"):
        CacheEntry(key=cache_key(**BASE), event_id="evt_1", tier=tier, result=a_result())


@pytest.mark.parametrize("tier", list(TIERS))
def test_every_router_tier_is_storable(tier):
    assert CacheEntry(key=cache_key(**BASE), event_id="e", tier=tier, result=a_result()).tier == tier


@pytest.mark.parametrize("event_id", ["", "   "])
def test_an_entry_without_an_event_is_refused(event_id):
    with pytest.raises(ValueError, match="event_id"):
        CacheEntry(key=cache_key(**BASE), event_id=event_id, tier="T2", result=a_result())


# ── U2 · the read-through ─────────────────────────────────────────────────────────────────────

def test_a_miss_calls_the_model_exactly_once_and_stores_the_result():
    store, llm = InMemoryExtractionCache(), CountingLLM()
    outcome = cached_extraction(store, cache_key(**BASE), event_id="evt_9", tier="T3",
                                extract=llm)
    assert (outcome.hit, outcome.stored, llm.calls, len(store)) == (False, True, 1, 1)
    assert outcome.entry.tier == "T3"
    assert outcome.entry.event_id == "evt_9"


def test_losing_a_race_to_a_concurrent_writer_is_reported_not_raised():
    """Two workers extracting the same content at the same moment wasted one call; failing the
    loser would additionally throw away an extraction that has already been paid for."""
    store = InMemoryExtractionCache()
    key = cache_key(**BASE)
    store.put(CacheEntry(key=key, event_id="evt_first", tier="T2", result=a_result()))

    class _RacyStore:
        def get(self, _key):
            return None                       # the racing worker's read, taken before the write
        def put(self, entry):
            return store.put(entry)

    outcome = cached_extraction(_RacyStore(), key, event_id="evt_second", tier="T2",
                                extract=CountingLLM())
    assert outcome.hit is False
    assert outcome.stored is False
    assert outcome.llm_calls == 1


def test_a_thunk_that_does_not_return_the_contract_type_is_refused():
    with pytest.raises(TypeError, match="ExtractionResult"):
        cached_extraction(InMemoryExtractionCache(), cache_key(**BASE), event_id="e", tier="T2",
                          extract=lambda: {"intent": "commit"})


def test_a_forged_key_from_another_tenant_cannot_read_a_row():
    """org_id is inside the digest, so this cannot happen by accident — the store checks anyway,
    because a future change to the key formula must not be the only thing standing between two
    tenants."""
    store = InMemoryExtractionCache()
    key = cache_key(**BASE)
    store.put(CacheEntry(key=key, event_id="evt_1", tier="T2", result=a_result()))
    forged = ExtractionCacheKey(**{**{name: getattr(key, name) for name in KEY_COMPONENTS},
                                   "org_id": "org_attacker", "digest": key.digest})
    assert store.get(forged) is None


# ── the real table ────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def pg_cache(live_db_url):
    """`PostgresExtractionCache` on the scratch database, plus the org its rows must reference
    (the org FK from 0033 is enforced for new rows even though it is NOT VALID). Rows written by
    a test are removed afterwards: this store commits, so there is no transaction to roll back."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres cache tests skipped")
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)
    with engine.connect() as conn:
        org = conn.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        pytest.skip("no org in the scratch database")
    marker = f"pytest_cache_{uuid.uuid4().hex[:8]}"
    try:
        yield PostgresExtractionCache(live_db_url), org, marker
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"delete from {CACHE_TABLE} where event_id like :m"),
                         {"m": f"{marker}%"})


def _rich_result() -> ExtractionResult:
    """Every claim kind that carries a span, so the JSON round trip is proven on the shape that
    actually gets stored — not on the empty one."""
    span = EvidenceSpan(source_ref="prepared_content:evt_1", quote="we can sign by Friday",
                        start_offset=14, end_offset=35, verified=True)
    return a_result(
        entity_mentions=[EntityMention(surface_form="Dana", entity_type="person",
                                       canonical_hint="dana@acme.example", evidence=[span],
                                       confidence_bp=9000)],
        amounts=[Money(minor_units=1200000, currency="USD", as_written="$12,000")],
        commitments=[Commitment(actor="us", action="sign the renewal", beneficiary="Acme",
                                is_conditional=True, condition_text="Finance confirms",
                                evidence=[span], confidence_bp=8500)],
        questions=["Can Finance confirm today?"],
        field_confidence={"intent": 9200},
        all_evidence=[span])


def test_a_stored_extraction_round_trips_through_postgres(pg_cache):
    store, org, marker = pg_cache
    key = cache_key(**{**BASE, "org_id": org})
    entry = CacheEntry(key=key, event_id=f"{marker}_a", tier="T3", result=_rich_result())

    assert store.get(key) is None                  # a miss before anything is written
    assert store.put(entry) is True
    read = store.get(key)
    assert read is not None
    assert read.result == entry.result             # every claim, every span, every bp
    assert read.event_id == f"{marker}_a"
    assert read.tier == "T3"


def test_a_second_put_of_the_same_key_does_not_write_again(pg_cache):
    store, org, marker = pg_cache
    key = cache_key(**{**BASE, "org_id": org})
    entry = CacheEntry(key=key, event_id=f"{marker}_b", tier="T2", result=a_result())
    assert store.put(entry) is True
    assert store.put(entry) is False


def test_the_row_records_the_profile_the_tier_and_the_cost(pg_cache, live_db_url):
    """The two columns migration 0080 adds. Without them, 'how much of this tenant's spend went
    on documents' has no answer, and a stored row cannot say which prompt produced it."""
    store, org, marker = pg_cache
    key = cache_key(**{**BASE, "org_id": org, "profile_id": "document"})
    store.put(CacheEntry(key=key, event_id=f"{marker}_c", tier="T3",
                         result=a_result(extraction_profile="document")))

    from genios_engine.platform.db import get_engine
    with get_engine(live_db_url).connect() as conn:
        row = conn.execute(text(
            f"select profile_id, tier, input_tokens, output_tokens, model_snapshot "
            f"from {CACHE_TABLE} where processing_key=:k"), {"k": key.processing_key}).one()
    assert row.profile_id == "document"
    assert row.tier == "T3"
    assert (row.input_tokens, row.output_tokens) == (1840, 260)
    assert row.model_snapshot == BASE["model_snapshot"]


def test_the_database_refuses_a_tier_outside_the_router_vocabulary(live_db_url):
    """The check constraint from 0080. `CacheEntry` refuses one too — this asserts the second
    lock, on the path a raw backfill or a psql session takes."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from sqlalchemy.exc import IntegrityError

    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)
    with engine.connect() as conn:
        org = conn.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        pytest.skip("no org in the scratch database")
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(
            f"insert into {CACHE_TABLE} (processing_key, org_id, event_id, output, tier) "
            "values (:k, :o, 'evt_bad', '{}'::jsonb, 'T4')"),
            {"k": f"pytest_bad_tier_{uuid.uuid4().hex}", "o": org})


def test_an_unreadable_row_is_a_miss_and_not_an_exception(pg_cache, live_db_url):
    """A cache is not a place to fail. `schema_version` is in the key so this should be
    unreachable; if it happens anyway it must cost one model call, not break every replay of
    that message."""
    store, org, marker = pg_cache
    key = cache_key(**{**BASE, "org_id": org})
    from genios_engine.platform.db import get_engine
    with get_engine(live_db_url).begin() as conn:
        conn.execute(text(
            f"insert into {CACHE_TABLE} (processing_key, org_id, event_id, output, tier) "
            "values (:k, :o, :e, cast(:out as jsonb), 'T2')"),
            {"k": key.processing_key, "o": org, "e": f"{marker}_d",
             "out": json.dumps({"intent": "commit"})})       # no provenance — cannot validate

    assert store.get(key) is None
    llm = CountingLLM()
    outcome = cached_extraction(store, key, event_id=f"{marker}_d", tier="T2", extract=llm)
    assert outcome.hit is False
    assert llm.calls == 1


def test_a_row_written_for_one_tenant_is_invisible_to_another(pg_cache):
    """The WHERE clause, against real SQL. The digest already differs per org; this proves the
    second lock is actually in the statement."""
    store, org, marker = pg_cache
    key = cache_key(**{**BASE, "org_id": org})
    store.put(CacheEntry(key=key, event_id=f"{marker}_e", tier="T2", result=a_result()))
    forged = ExtractionCacheKey(**{**{name: getattr(key, name) for name in KEY_COMPONENTS},
                                   "org_id": "org_not_this_one", "digest": key.digest})
    assert store.get(forged) is None


# ── the rename: l2_extraction_results -> l1_extraction_results ────────────────────────────────

@pytest.fixture()
def conn(live_db_url):
    """Real PostgreSQL in a transaction that is always rolled back — never the configured
    (production) database. See tests/conftest.py::live_test_database_url."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def test_the_old_table_name_is_gone_and_the_new_one_carries_the_rows(conn):
    c, _org = conn
    assert c.execute(text("select to_regclass('public.l2_extraction_results')")).scalar() is None
    assert c.execute(text(f"select to_regclass('public.{CACHE_TABLE}')")).scalar() is not None


def test_every_table_the_erasure_loop_names_exists(conn):
    """`_wipe` runs `delete from {tbl}` with no try/except by design, so ONE stale name in that
    list raises on every account deletion. This is the whole class, not just the renamed row."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    c, _org = conn
    missing = [tbl for tbl in _ORG_SCOPED_TABLES
               if c.execute(text("select to_regclass('public.' || :t)"), {"t": tbl}).scalar()
               is None]
    assert missing == []


def test_org_erasure_still_runs_and_deletes_cached_extractions(conn):
    """The trap in one test: seed a cached extraction, run the REAL erasure loop, and require
    both that it did not raise and that the row is gone."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES, _wipe
    c, org = conn
    key = f"pytest_erasure_{uuid.uuid4().hex}"
    c.execute(text(
        f"insert into {CACHE_TABLE} (processing_key, org_id, event_id, output, profile_id, tier) "
        "values (:k, :o, 'evt_erasure', '{}'::jsonb, 'email', 'T1')"), {"k": key, "o": org})
    assert c.execute(text(f"select count(*) from {CACHE_TABLE} where processing_key=:k"),
                     {"k": key}).scalar() == 1

    wiped = _wipe(c, org)

    assert CACHE_TABLE in wiped
    assert "l2_extraction_results" not in _ORG_SCOPED_TABLES
    assert wiped[CACHE_TABLE] >= 1
    assert c.execute(text(f"select count(*) from {CACHE_TABLE} where processing_key=:k"),
                     {"k": key}).scalar() == 0


def test_the_l2_store_seam_still_reads_and_writes_the_renamed_table(live_db_url):
    """`GraphStore.cache_get`/`cache_set` name the table in raw SQL. The L2 lane still runs
    (strangler fig — it is not deleted in this wave), so its two statements are executed here."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)
    with engine.connect() as c:
        org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        pytest.skip("no org")
    store = GraphStore(live_db_url)
    key = f"pytest_l2_seam_{uuid.uuid4().hex}"
    try:
        assert store.cache_get(key, org_id=org) is None
        store.cache_set(processing_key=key, org_id=org, event_id="evt_seam",
                        output={"relevance": 0.5}, input_tokens=1, output_tokens=2, model="m")
        assert store.cache_get(key, org_id=org) == {"relevance": 0.5}
    finally:
        with engine.begin() as c:
            c.execute(text(f"delete from {CACHE_TABLE} where processing_key=:k"), {"k": key})


def test_the_pending_count_query_still_resolves(live_db_url):
    """`api/routes.py::_pending_count` and `context/runner.py::_pull` both subselect the cache
    table. A stale name there does not show up until a sync runs, so both statements execute
    here against real PostgreSQL."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from genios_engine.api import routes
    from genios_engine.context import runner
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.db import get_engine
    with get_engine(live_db_url).connect() as c:
        org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        pytest.skip("no org")
    store = GraphStore(live_db_url)
    previous = routes._graph
    routes._graph = store
    try:
        assert isinstance(routes._pending_count(org), int)
        assert runner._pull(store, org, 5) == []
    finally:
        routes._graph = previous
