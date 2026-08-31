"""The records reading: one situation per CONTROL GAP, and never one per file.

`document-under-control.yaml` states the whole discipline in five words — "the headline is the gap,
not the document" — and it is the property most easily lost. A Drive of four hundred files that
mints four hundred cards saying a document exists is a file listing wearing a situation's clothes,
and the handful of artefacts that actually need attention become unfindable inside it. So candidacy
(would a records reading of this file mean anything) and the gap (is anything actually wrong) are
two separate gates and both must pass.

The second discipline is what the reading refuses to say. Two of the four failures this subdomain
exists to catch do not survive an approximation over a file store: missing approval and past its
retention date. Neither is inferred, both stay in `missing` on every row, and the tests below pin
that they cannot quietly acquire a value — because records coverage claimed and absent is worse
than absent, since it is what somebody relies on in an audit.

The gates run over a plain snapshot, so they are tested hermetically. The sweep's SQL — jsonb
casts, array parameters, `unnest` — needs a real Postgres and is tested there.
"""
from __future__ import annotations

import inspect
import pathlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.document_register import (
    ANCHOR_DOCUMENT,
    COVERAGE_CAP_PCT,
    GAP_LIVE_COPIES,
    GAP_NO_OWNER,
    GAP_ORPHAN,
    GAP_UNMAINTAINED,
    LIVE_COPY_DAYS,
    MISSING,
    UNMAINTAINED_DAYS,
    Artefact,
    Register,
    gaps_for,
    governance_term,
    is_document_mime,
    live_copies,
    read_register,
    refresh_document_situations,
    register_domains,
)
from genios_engine.context.documents import (register_document_node,
                                             resolve_owner_node)
from genios_engine.context.domain_spec import domains_declaring, spec_for

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def _artefact(node_id="d1", title="Information Security Policy", *, mime=DOCX, owner="ops@acme.io",
              modified_days=10.0, head="", internal_kind=None, attached=2,
              owner_seen_days=5.0, owner_is_us=False, version="47",
              content_hash="h1") -> Artefact:
    facts = {"document.id": node_id, "document.mime": mime, "document.title": title}
    if owner:
        facts["document.owner_email"] = owner
    if modified_days is not None:
        facts["document.modified_at"] = _ago(modified_days)
    if version:
        facts["document.version"] = version
    if content_hash:
        facts["document.content_hash"] = content_hash
    return Artefact(node_id=node_id, title=title, facts=facts, head=head,
                    internal_kind=internal_kind, attached_people=attached,
                    owner_seen_at=(None if owner_seen_days is None
                                   else NOW - timedelta(days=owner_seen_days)),
                    owner_is_us=owner_is_us)


def _register(*artefacts: Artefact) -> Register:
    return Register(org_id="o", now=NOW, artefacts=tuple(artefacts))


# ── gate A · is a records reading of this file worth anything ────────────────────────────────

def test_a_file_with_no_readable_text_is_not_a_controlled_document():
    """An image, a video, an archive or a binary has no version identity and no readable text, so
    a records reading of one would rest entirely on its filename — which is exactly the "resolve
    against a filename" failure the situation file refused when it refused `admin_contact`."""
    assert is_document_mime(DOCX) and is_document_mime("application/pdf")
    assert is_document_mime("application/vnd.google-apps.document")
    assert not is_document_mime("image/png")
    assert not is_document_mime("application/zip")
    assert not is_document_mime("")


def test_a_scan_named_security_policy_is_still_not_a_candidate():
    """Both halves of candidacy have to hold. A JPEG called "Security Policy.jpg" trips the
    lexicon and is still a picture, and reading it as a controlled document would put the whole
    subdomain's inference on a filename."""
    a = _artefact(mime="image/jpeg", owner=None)
    assert read_register(_register(a)) == []


def test_an_ordinary_business_document_is_not_a_governance_artefact():
    """A proposal, an invoice and a meeting note are documents and are not artefacts the
    organisation is accountable for. Without this gate the reading fires on the entire Drive and
    the four gaps below become noise attached to everything."""
    assert governance_term("Q3 Pricing Proposal for Acme", "") is None
    assert read_register(_register(_artefact(title="Q3 Pricing Proposal", owner=None))) == []


def test_the_governance_term_is_read_from_the_body_when_the_title_says_nothing():
    """Half the policies in any Drive are called "Doc 3" or "final v2". The opening lines say what
    they are — "This policy sets out…" — and the term found is CARRIED, because a finding whose
    evidence is "the lexicon fired" cannot be checked by anybody."""
    a = _artefact(title="Doc 3", owner=None,
                  head="This policy sets out how information is handled.")
    (found, inputs), = read_register(_register(a))
    assert found is a
    assert inputs["governance_term"] == "policy"


def test_a_tag_the_organisation_typed_beats_the_lexicon():
    """A declaration outranks a guess about one. Dormant on today's paths — the upload door files
    a tagged file as a CANON node, so `internal_kind` is null on every event that mints a document
    — and read anyway, so the day a file store is tagged, a tenant who has stated exactly what
    these files are is not then excluded by a keyword list."""
    a = _artefact(title="Doc 3", owner=None, internal_kind="sop")
    (_, inputs), = read_register(_register(a))
    assert inputs["declared_kind"] == "sop" and inputs["governance_term"] is None


# ── gate B · the four gaps, and the discipline of firing on none of them ─────────────────────

def test_a_controlled_document_with_nothing_wrong_mints_nothing():
    """THE RULE THE WHOLE FILE TURNS ON. An owner who is around, one live copy, edited this month,
    two people attached — nothing here needs a human, and a card saying so would be a row in a file
    listing. This is the test that fails first if candidacy and the gap are ever fused."""
    assert gaps_for(_artefact(), copies=1, now=NOW) == []
    assert read_register(_register(_artefact())) == []


def test_a_document_nobody_owns_is_the_finding():
    assert gaps_for(_artefact(owner=None), copies=1, now=NOW) == [GAP_NO_OWNER]


def test_an_owner_this_tenant_has_not_seen_in_four_months_is_unverified_not_gone():
    """The claim is "owner unverified", never "the owner has left". Nothing here can tell a
    departure from parental leave, and the two demand opposite responses — which is exactly why
    `doc.owner_left_the_organisation` asks for an HRIS end date and stays `needs_signal`."""
    assert gaps_for(_artefact(owner_seen_days=200), copies=1, now=NOW) == [GAP_NO_OWNER]
    assert gaps_for(_artefact(owner_seen_days=None), copies=1, now=NOW) == [GAP_NO_OWNER]
    assert gaps_for(_artefact(owner_seen_days=30), copies=1, now=NOW) == []


def test_one_of_our_own_addresses_needs_no_correspondence_to_count_as_present():
    """A seat, the account owner or a connected mailbox is a STATEMENT that this person is here.
    Requiring them to have emailed somebody as well would open a no-owner gap on every document
    owned by a colleague who works in the product rather than in the inbox."""
    assert gaps_for(_artefact(owner_seen_days=None, owner_is_us=True), copies=1, now=NOW) == []


def test_two_live_copies_fire_and_a_stale_one_does_not():
    """"Two live copies exist" is provable; "the wrong version is in circulation" is not, because
    supersession has no emitter. The LIVE half is what keeps even the weaker claim honest — a copy
    nobody has opened since last spring is not in circulation, it is the stale one, which is a
    different and much weaker finding."""
    fresh = _artefact("d1", "Security Policy v2", modified_days=5, content_hash="a")
    also_fresh = _artefact("d2", "Copy of Security Policy", modified_days=20, content_hash="b")
    stale = _artefact("d3", "Security Policy FINAL", modified_days=LIVE_COPY_DAYS + 40,
                      content_hash="c")
    assert live_copies([fresh, also_fresh, stale], NOW) == 2
    assert live_copies([fresh, stale], NOW) == 1
    assert GAP_LIVE_COPIES in gaps_for(fresh, copies=2, now=NOW)
    assert GAP_LIVE_COPIES not in gaps_for(fresh, copies=1, now=NOW)


def test_a_copy_with_no_modification_stamp_is_not_assumed_live():
    """"We do not know when this was last touched" is not evidence that it is in circulation.
    Counting it as live would put a version-conflict card under a pair of files nobody has opened
    in three years."""
    known = _artefact("d1", "Leave Policy", modified_days=3)
    undated = _artefact("d2", "Leave Policy v2", modified_days=None)
    assert live_copies([known, undated], NOW) == 1


def test_the_copies_are_counted_per_file_and_not_per_revision_number():
    """The obvious rule — the version strings must differ — is the wrong one, and wrong in the
    direction that misses the finding. Drive's `version` is a per-file revision counter: two
    independently created copies of the handbook are both revision 1 on the day they are made and
    both revision 40 after a year of equal editing."""
    a = _artefact("d1", "Employee Handbook", version="1", content_hash="a", modified_days=2)
    b = _artefact("d2", "Employee Handbook v2", version="1", content_hash="b", modified_days=2)
    found = read_register(_register(a, b))
    assert {f.node_id for f, _ in found} == {"d1", "d2"}
    assert all(GAP_LIVE_COPIES in i["gaps"] and i["live_copies"] == 2 for _, i in found)


def test_two_byte_identical_copies_are_reported_as_identical_rather_than_as_a_fork():
    """A mirrored file in two folders is a filing problem; two divergent drafts is a decision made
    on a superseded document. Both are "two live copies" and Layer 4 must be able to tell them
    apart, so the content comparison rides in the payload instead of being banded here."""
    a = _artefact("d1", "Data Retention Policy", content_hash="same", modified_days=1)
    b = _artefact("d2", "Data Retention Policy (1)", content_hash="same", modified_days=1)
    found = read_register(_register(a, b))
    assert all(i["identical_content"] is True for _, i in found)


def test_a_governance_artefact_nobody_has_edited_in_a_year_has_stopped_being_maintained():
    assert gaps_for(_artefact(modified_days=UNMAINTAINED_DAYS + 5), copies=1,
                    now=NOW) == [GAP_UNMAINTAINED]
    assert gaps_for(_artefact(modified_days=UNMAINTAINED_DAYS - 5), copies=1, now=NOW) == []
    # Unknown is not old. An absent stamp must not manufacture an age.
    assert gaps_for(_artefact(modified_days=None), copies=1, now=NOW) == []


def test_the_orphan_threshold_is_zero_because_our_document_can_only_reach_two_people():
    """`doc.orphaned_artefact` reads `edge_count <= 1`, and that number is calibrated for a graph
    where a controlled document also has an approver and a series. Here a document can only ever
    reach an owner and a last editor, so a degree of one is the ORDINARY state of a file whose
    owner also maintains it — the corpus threshold verbatim would mint a situation on nearly every
    governance file, which is the flood the render hint refuses."""
    assert gaps_for(_artefact(attached=1), copies=1, now=NOW) == []
    assert GAP_ORPHAN in gaps_for(_artefact(attached=0, owner=None), copies=1, now=NOW)


def test_a_file_whose_title_reduces_to_nothing_gets_its_own_cluster():
    """An "unknown" bucket would make every unnameable file a copy of every other unnameable file,
    which is how a folder of scans becomes one document with forty live versions."""
    a = _artefact("d1", "v2", head="This policy applies to everyone.", modified_days=1)
    b = _artefact("d2", "FINAL", head="This policy applies to everyone.", modified_days=1)
    assert len(_register(a, b).clusters()) == 2
    assert all(GAP_LIVE_COPIES not in i["gaps"] for _, i in read_register(_register(a, b)))


# ── what the payload may and may not claim ───────────────────────────────────────────────────

def test_the_revision_counter_is_never_presented_as_the_document_version():
    """v3 of the security policy is not `version: 3`; it is `version: 47` because somebody fixed
    forty-four typos. The key name is the only thing stopping a card from rendering "version 47"
    of a policy that has been revised three times."""
    (_, inputs), = read_register(_register(_artefact(owner=None, version="47")))
    assert inputs["drive_revision_count"] == "47"
    assert "version" not in inputs


def test_every_row_declares_that_approval_and_retention_cannot_be_seen():
    """The two failures that do not survive. An artefact must render as "approval state unknown"
    and never as "unapproved", which would be a finding the system invented — and
    `retention_and_archival` is routed and has nothing true to say, which has to be on the row
    rather than discovered during an audit."""
    text_of = " ".join(MISSING).lower()
    assert "approval" in text_of
    assert "retention" in text_of
    assert "classification" in text_of
    assert "supersession" in text_of
    assert "leave" in text_of          # unverified owner ≠ departed owner


def test_two_expected_fields_have_no_writer_so_coverage_can_never_reach_the_cap_dishonestly():
    """`expected_fields` is what decides `missing`, and at least one entry per situation type is
    deliberately unsatisfiable. Without that, `missing` empties the moment the mechanical facts
    land — which is how 34 of one org's 73 situations came to report full coverage on the strength
    of knowing whose turn it was."""
    expected = spec_for("admin").fields_for("document_under_control")
    assert set(expected) == {"document.owner_email", "document.version",
                             "document.approved_at", "document.retention_until"}
    from genios_engine.context.situations import coverage_score
    everything_we_can_write = {"document.owner_email", "document.version", "document.id",
                               "document.modified_at", "document.mime"}
    pct, gaps = coverage_score(present_fields=everything_we_can_write, expected=expected)
    assert pct == 50 and len(gaps) == 2
    assert min(COVERAGE_CAP_PCT, pct) <= COVERAGE_CAP_PCT


# ── registry + wiring ────────────────────────────────────────────────────────────────────────

def test_the_anchor_is_declared_in_the_registry_and_nowhere_else():
    """`type_for` is the only producer of the type string. A domain that mints documents without
    declaring the anchor falls to the generic `<domain>_<anchor>` default and becomes
    `admin_document` — a name no situation file claims and the registry cannot resolve, which is
    the exact fault that kept `admin_person` and `fundraising_deal` dark, and it fails silently."""
    assert register_domains() == domains_declaring(ANCHOR_DOCUMENT)
    assert register_domains(), "no domain declares the document anchor"
    for domain in register_domains():
        stype = spec_for(domain).type_for(ANCHOR_DOCUMENT)
        assert stype == "document_under_control", stype


def test_the_sync_path_refreshes_the_register():
    """A records reading refreshed only by a separate schedule is a records reading that is always
    stale, and five capabilities would be reachable in principle and empty in practice."""
    from genios_engine.context import runner
    assert "refresh_document_situations" in inspect.getsource(runner.process_pending)


def test_no_domain_is_named_inside_the_reading():
    """Layer 2 knows domains only through the registry. A domain named here would mean adding a
    domain requires editing Layer 2, which is the one thing `domain_spec` exists to prevent."""
    from genios_engine.context import document_register, documents
    for module in (document_register, documents):
        source = inspect.getsource(module)
        for name in ('"admin"', "'admin'", '"sales"', "'sales'", '"support"', "'support'"):
            assert name not in source, f"{module.__name__} names a domain: {name}"


# ── the sweep, against a real Postgres ───────────────────────────────────────────────────────

def _seed_org(store, org: str) -> None:
    """NOT-NULL columns are discovered rather than listed, so a later migration adding one does
    not turn this into a skip — same shape as `tests/test_period_situations.py`."""
    with store.engine.begin() as c:
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id", "email"], [":id", ":email"], {"id": org,
                                                              "email": f"founder@{org}.io"}
        for r in reqd:
            if r.column_name in vals:
                continue
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else False if dt == "boolean"
                                   else "{}" if dt in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                       "on conflict (id) do nothing"), vals)


def _reset(store, org: str) -> None:
    """Clear this org's graph and situations before seeding.

    The scratch database is session-scoped and outlives a run, so without this a second invocation
    reads facts an earlier phase wrote — and `write_fact` is authority-aware, so a stale
    `document.owner_email` from the END of the previous run would satisfy the no-owner gate at the
    START of this one. The test would keep passing and would have stopped testing the transition.
    """
    with store.engine.begin() as c:
        for table, column in (("context_situations", "org_id"), ("graph_source_refs", "org_id"),
                              ("graph_facts", "org_id"), ("graph_edges", "org_id"),
                              ("graph_aliases", "org_id"), ("graph_nodes", "org_id"),
                              ("prepared_content", "org_id"), ("source_events", "org_id"),
                              ("connections", "org_id")):
            c.execute(text(f"delete from {table} where {column}=:o"), {"o": org})


def _seed_file(store, org: str, *, file_id: str, name: str, owner: str | None,
               modified: datetime, body: str, version: str = "12") -> None:
    """A Drive file exactly as the pipeline lands one: the capture event, its masked text, the
    editor's person node (the event actor, which is `lastModifyingUser`), and the projection.

    The projection runs through `register_document_node` and the owner through
    `resolve_owner_node`, so this exercises the authority-aware `write_fact` path and the
    resolve-never-create rule the real pipeline uses. A hand-rolled insert would only prove the
    sweep can read rows the test wrote itself.
    """
    event_id = f"ev_{org}_{file_id}"
    editor = f"intern@{org}.io"
    with store.engine.begin() as c:
        # `connection_id` is NOT NULL and carries no foreign key, so a literal is enough — and a
        # real `connections` row would be actively harmful here. It is a global table, several
        # sweeps enumerate it across every org, and a half-populated row (no `composio_user_id`)
        # fails their pydantic model in whichever test happens to run next. "Who we are" comes from
        # `orgs.email` in these fixtures, which is the union member that always exists.
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "  source_object_id, dedup_key, actor, occurred_at) values "
            "(:e, :o, :cid, 'gdrive', 'file', :fid, :e, cast(:actor as jsonb), :at) "
            "on conflict do nothing"),
            {"e": event_id, "o": org, "cid": f"conn_{org}", "fid": file_id, "at": modified,
             "actor": '{"email": "' + editor + '"}'})
        c.execute(text(
            "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
            "values (:e, :o, :p, :t) on conflict (event_id) do nothing"),
            {"e": event_id, "o": org, "p": f"pc_{org}_{file_id}", "t": body})
        editor_node = store.find_or_create_node(
            c, org_id=org, node_type="person", canonical_key=editor, display_name=editor,
            event_id=event_id)
        if owner:
            # The owner is somebody this graph already knows — a colleague who corresponds. The
            # projection RESOLVES them and never creates them, which is what this seeds.
            store.find_or_create_node(c, org_id=org, node_type="person", canonical_key=owner,
                                      display_name=owner, event_id=event_id)
        register_document_node(
            c, store, org_id=org, source="gdrive", event_id=event_id, content=body,
            occurred_at=modified, editor_node=editor_node,
            owner_node=resolve_owner_node(c, org_id=org, email=owner),
            meta={"file_id": file_id, "name": name, "mime": DOCX, "version": version,
                  "modified_at": modified.isoformat(), "created_at": _ago(900),
                  "owner_email": owner, "last_modified_by": editor,
                  "web_link": f"https://docs.example/{file_id}", "parents": [], "shared": True})


def test_the_sweep_opens_a_situation_for_a_policy_with_no_owner(pg_store):
    org = "docreg_no_owner"
    _seed_org(pg_store, org)
    _reset(pg_store, org)
    _seed_file(pg_store, org, file_id="f1", name="Information Security Policy v2", owner=None,
               modified=NOW - timedelta(days=9),
               body="This policy sets out how information is handled.")
    assert refresh_document_situations(pg_store, org, now=NOW) > 0

    with pg_store.engine.connect() as c:
        rows = c.execute(text(
            "select situation_type, domain, status, coverage, missing, inputs, anchor_node_id "
            "from context_situations where org_id=:o"), {"o": org}).mappings().all()
        node_type = c.execute(text(
            "select node_type from graph_nodes where org_id=:o and canonical_key='gdrive:f1'"),
            {"o": org}).scalar()
    assert node_type == ANCHOR_DOCUMENT
    assert {r["situation_type"] for r in rows} == {
        spec_for(d).type_for(ANCHOR_DOCUMENT) for d in register_domains()}
    row = rows[0]
    assert row["status"] == "active"
    assert row["inputs"]["gaps"] == [GAP_NO_OWNER]
    # An inference over a file store, never a records claim: the ceiling is on the reading and the
    # row is under it because the owner it is missing is one of the fields coverage counts.
    assert 0 < row["coverage"] <= COVERAGE_CAP_PCT
    assert any("approval" in m for m in row["missing"]), row["missing"]
    assert any("retention" in m for m in row["missing"]), row["missing"]


def test_a_governance_document_under_control_produces_no_row_at_all(pg_store):
    """The end-to-end version of the rule: a file store full of healthy policies is silent. If
    this ever produces a row, the product ships a Drive listing labelled as findings."""
    org = "docreg_healthy"
    _seed_org(pg_store, org)
    _reset(pg_store, org)
    _seed_file(pg_store, org, file_id="g1", name="Expenses Policy",
               owner=f"founder@{org}.io", modified=NOW - timedelta(days=11),
               body="This policy sets out how expenses are claimed.")
    refresh_document_situations(pg_store, org, now=NOW)
    with pg_store.engine.connect() as c:
        assert c.execute(text("select count(*) from context_situations where org_id=:o"),
                         {"o": org}).scalar() == 0


def test_the_sweep_is_idempotent_and_closes_a_gap_that_stops_being_true(pg_store):
    """Idempotent because the derived facts overwrite their own deterministic version ids and the
    situations conflict on `(org_id, correlation_id)`. Self-closing BY FACT rather than by a human,
    so the row reopens by itself if the gap returns — the system must not need somebody to undo a
    conclusion it drew from data that has since changed."""
    org = "docreg_lifecycle"
    _seed_org(pg_store, org)
    _reset(pg_store, org)
    _seed_file(pg_store, org, file_id="h1", name="Data Retention Policy", owner=None,
               modified=NOW - timedelta(days=4),
               body="This policy sets out how long records are kept.")
    refresh_document_situations(pg_store, org, now=NOW)
    refresh_document_situations(pg_store, org, now=NOW)
    with pg_store.engine.connect() as c:
        assert c.execute(text("select count(*) from context_situations where org_id=:o"),
                         {"o": org}).scalar() == len(register_domains())
        assert c.execute(text(
            "select count(*) from graph_facts where org_id=:o "
            "and field like 'derived.document_%' and valid_to is null"),
            {"o": org}).scalar() == 2

    # The owner is named, and it is one of ours — the gap is gone.
    _seed_file(pg_store, org, file_id="h1", name="Data Retention Policy",
               owner=f"founder@{org}.io", modified=NOW - timedelta(days=3),
               body="This policy sets out how long records are kept.", version="13")
    refresh_document_situations(pg_store, org, now=NOW)
    with pg_store.engine.connect() as c:
        row = c.execute(text(
            "select status, resolved_by from context_situations where org_id=:o"),
            {"o": org}).mappings().first()
    assert row["status"] == "resolved" and row["resolved_by"] == "fact"


def test_two_copies_of_one_policy_are_clustered_across_the_file_store(pg_store):
    """The version question, which the situation file calls the only reason this is a capability
    rather than a filing metaphor. Two files, two ids, two revision counters, one document."""
    org = "docreg_copies"
    _seed_org(pg_store, org)
    _reset(pg_store, org)
    for fid, name, body in (("c1", "Security Policy v2", "This policy sets out access rules."),
                            ("c2", "Copy of Security Policy",
                             "This policy sets out access rules and more.")):
        _seed_file(pg_store, org, file_id=fid, name=name, owner=f"founder@{org}.io",
                   modified=NOW - timedelta(days=6), body=body)
    refresh_document_situations(pg_store, org, now=NOW)

    with pg_store.engine.connect() as c:
        keys = {r[0] for r in c.execute(text(
            "select value #>> '{}' from graph_facts where org_id=:o "
            "and field='derived.document_cluster_key' and valid_to is null"), {"o": org})}
        rows = c.execute(text(
            "select inputs from context_situations where org_id=:o and status='active'"),
            {"o": org}).mappings().all()
    assert len(keys) == 1, keys                       # both files, one document
    assert len(rows) == 2 * len(register_domains())   # a situation on each copy
    for r in rows:
        assert r["inputs"]["gaps"] == [GAP_LIVE_COPIES]
        assert r["inputs"]["live_copies"] == 2
        assert r["inputs"]["identical_content"] is False


def test_an_org_with_no_file_store_connected_costs_nothing(pg_store):
    """A tenant who has not authorised a file store mints zero of these, and must not pay for the
    sweep on every drain to find that out."""
    org = "docreg_empty"
    _seed_org(pg_store, org)
    _reset(pg_store, org)
    assert refresh_document_situations(pg_store, org, now=NOW) == 0


@pytest.mark.parametrize("field", ["document.approved_at", "document.retention_until"])
def test_the_two_unwritable_fields_stay_expected_and_stay_unsupplied(field):
    """The load-bearing absence, held from both ends.

    The registry EXPECTS both, so `missing` names them on every row. The corpus census places
    neither in `substrate.fact_paths`, so no authored pattern may be marked executable against
    one. If either ever moves up, the situation quietly becomes an assertion about approval or
    disposal that no file store can support — and the census is the only place that would record
    it.
    """
    import yaml
    assert field in spec_for("admin").fields_for("document_under_control")
    root = pathlib.Path(inspect.getfile(refresh_document_situations)).parents[2]
    vocab = yaml.safe_load((root / "Domain Expertise" / "_schema" / "vocabulary.yaml").read_text())
    assert field not in set(vocab["substrate"]["fact_paths"])
    assert field in set(vocab["planned_substrate"]["fact_paths"])
