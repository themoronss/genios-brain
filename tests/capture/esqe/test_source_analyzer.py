"""L1.6.4-U1 · Provenance and actor authority.

    pytest tests/capture/esqe/test_source_analyzer.py -q

Doc 06's acceptance, in its own words: *a CFO-sent message scores above an unknown external; a
`no-reply@` sender scores 1000; an uploaded policy document gets `internal_kind` authority.*
Each is a row below, plus the two properties the unit's design rests on — that the artifact half
is ALG-14's answer and not a second one, and that an actor we failed to identify lands in the
conservative middle rather than at the top.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.esqe.source_analyzer import (
    ROLE_AUTHORITY_BP,
    RUNG_AUTHORITY_BP,
    ActorBasis,
    analyze_source,
    role_authority_bp,
)
from genios_engine.capture.validate.authority import (
    Authority,
    AuthorityBasis,
    Provenance,
    rank_of,
    weigh_authority,
)
from genios_engine.contracts.source_event import Actor, SourceEvent

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
ORG_DOMAINS = ("acme-corp.com",)


def _event(*, source: str = "gmail", object_type: str = "email_message",
           actor_type: str = "external_contact", email: str | None = "buyer@vendor.com",
           internal_kind: str | None = None, event_id: str = "evt_sa") -> SourceEvent:
    return SourceEvent(
        event_id=event_id, org_id="org_sa", connection_id="con_sa", source=source,
        source_family="communication", object_type=object_type,
        source_object_id="msg-1", dedup_key=f"{source}:{object_type}:msg-1",
        actor=Actor(type=actor_type, email=email), occurred_at=NOW, captured_at=NOW,
        internal_kind=internal_kind)


# ==========================================================================================
# The artifact half — delegated to ALG-14, never re-implemented
# ==========================================================================================

@pytest.mark.parametrize("source, object_type, internal_kind, executed, expected", [
    ("gmail", "email_message", None, False, Authority.EMAIL_PROSE),
    ("gmail", "email_attachment", None, False, Authority.ATTACHMENT),
    ("gmail", "email_attachment", None, True, Authority.SIGNED_DOCUMENT),
    ("upload", "file", "pricing", False, Authority.COMPANY_CANON),
    ("hubspot", "deal", None, False, Authority.STRUCTURED_SOURCE),
    ("slack", "message", None, False, Authority.CHAT_ASIDE),
    ("genios", "action", None, False, Authority.INFERRED),
])
def test_evidence_authority_is_alg14s_answer(source, object_type, internal_kind, executed,
                                             expected):
    """One row per artifact class: the analyzer returns exactly what `weigh_authority` returns.

    Asserted against the FUNCTION, not against a copy of its table — a test that hardcoded the
    ranks would keep passing after ALG-14 was re-tuned and this unit had drifted away from it,
    which is the precise failure "delegate, do not reimplement" exists to prevent.
    """
    event = _event(source=source, object_type=object_type, internal_kind=internal_kind)
    attribution = analyze_source(event, executed=executed, source_ref="prepared_content:evt_sa")

    expected_weight = weigh_authority(Provenance(
        source_ref="prepared_content:evt_sa", source=source, object_type=object_type,
        internal_kind=internal_kind, executed=executed))
    assert attribution.evidence == expected_weight
    assert attribution.evidence.authority is expected
    assert attribution.evidence_authority_rank == rank_of(expected)
    assert attribution.evidence_authority_multiplier_bp == expected_weight.multiplier_bp


def test_uploaded_policy_document_gets_internal_kind_authority():
    """Doc 06's third acceptance line, on both halves at once.

    The upload is company canon as an ARTIFACT (rank 5, `COMPANY_CANON_KIND`) and its author is
    the company as an ACTOR (9000). One event, two answers, neither derived from the other.
    """
    attribution = analyze_source(_event(source="upload", object_type="file",
                                        internal_kind="pricing", email=None, actor_type="system"))

    assert attribution.evidence.authority is Authority.COMPANY_CANON
    assert attribution.evidence.basis is AuthorityBasis.COMPANY_CANON_KIND
    assert attribution.actor_basis is ActorBasis.INTERNAL_KIND
    assert attribution.actor_authority_bp == 9000


def test_unmapped_provenance_floors_instead_of_raising():
    """An unrecognised source is rank 0 with an UNMAPPED basis — never an exception inside a
    sweep, which is ALG-14's own totality rule inherited unchanged."""
    attribution = analyze_source(_event(source="some-new-crm", object_type="widget"),
                                 source_ref=None)
    assert attribution.evidence_authority_rank == 0
    assert attribution.evidence.recognised is False


# ==========================================================================================
# The actor half — the cascade
# ==========================================================================================

@pytest.mark.parametrize("kwargs, expected_basis, expected_bp", [
    # 1 — the graph knew the role.
    (dict(actor_role="CFO", email="v.rao@acme-corp.com"), ActorBasis.ROLE_LADDER, 9500),
    (dict(actor_role="Chief Financial Officer", email="v.rao@acme-corp.com"),
     ActorBasis.ROLE_LADDER, 9500),
    (dict(actor_role="co-founder", email="rohit@acme-corp.com"), ActorBasis.ROLE_LADDER, 10000),
    (dict(actor_role="VP, Sales", email="sales@acme-corp.com"), ActorBasis.ROLE_LADDER, 9000),
    (dict(actor_role="intern", email="new@acme-corp.com"), ActorBasis.ROLE_LADDER, 5000),
    # 2 — company canon, no role known.
    (dict(internal_kind="sop", email="ops@acme-corp.com"), ActorBasis.INTERNAL_KIND, 9000),
    # 3 — a machine, above the domain rungs (see the module docstring's divergence note).
    (dict(email="no-reply@acme-corp.com"), ActorBasis.AUTOMATED, 1000),
    (dict(email="notifications@vendor.com"), ActorBasis.AUTOMATED, 1000),
    (dict(email="ops@vendor.com", actor_type="agent"), ActorBasis.AUTOMATED, 1000),
    # 4 — the connected mailbox's owner.
    (dict(email="rohit@acme-corp.com", mailbox_owner="Rohit@Acme-Corp.com"),
     ActorBasis.CONNECTION_OWNER, 8000),
    # 5 / 6 — colleague and counterparty.
    (dict(email="deepthi@acme-corp.com"), ActorBasis.SAME_DOMAIN, 5000),
    (dict(email="buyer@vendor.com"), ActorBasis.EXTERNAL, 5000),
    # 7 — nothing rankable at all.
    (dict(email=None), ActorBasis.UNKNOWN, 3000),
    (dict(email="   "), ActorBasis.UNKNOWN, 3000),
])
def test_actor_cascade_one_row_per_rung(kwargs, expected_basis, expected_bp):
    """One row per rung of doc 06's lookup cascade, plus the title-normalisation variants."""
    actor_role = kwargs.pop("actor_role", None)
    mailbox_owner = kwargs.pop("mailbox_owner", None)
    attribution = analyze_source(_event(**kwargs), actor_role=actor_role,
                                 mailbox_owner=mailbox_owner, org_domains=ORG_DOMAINS)
    assert attribution.actor_basis is expected_basis
    assert attribution.actor_authority_bp == expected_bp


def test_cfo_outranks_unknown_external_and_a_robot():
    """Doc 06's first acceptance line, and the ordering the whole unit exists to produce."""
    cfo = analyze_source(_event(email="v.rao@vendor.com"), actor_role="CFO")
    external = analyze_source(_event(email="someone@vendor.com"))
    unknown = analyze_source(_event(email=None))
    robot = analyze_source(_event(email="no-reply@vendor.com"))

    assert (cfo.actor_authority_bp > external.actor_authority_bp
            > unknown.actor_authority_bp > robot.actor_authority_bp)


def test_no_reply_sender_scores_1000_even_on_the_org_domain():
    """Doc 06's second acceptance line, at the address that would break a literal reading of the
    cascade: `no-reply@` on the ORG's own domain matches the same-domain rung two steps earlier,
    and would score 5000 if the machine test were not lifted above it."""
    attribution = analyze_source(_event(email="no-reply@acme-corp.com"),
                                 mailbox_owner="rohit@acme-corp.com",
                                 org_domains=ORG_DOMAINS)
    assert attribution.actor_authority_bp == 1000
    assert attribution.actor_basis is ActorBasis.AUTOMATED


def test_unknown_actor_takes_the_conservative_rank_never_the_highest():
    """An actor we could not identify sits BELOW every identified human and ABOVE the robots.

    Both directions are the assertion. At the top, every unparsed sender would be a founder; at
    the floor, an address our parser merely did not recognise would be silently demoted to a
    machine and its mail would stop reaching a card.
    """
    unknown = analyze_source(_event(email=None)).actor_authority_bp

    assert unknown == RUNG_AUTHORITY_BP[ActorBasis.UNKNOWN] == 3000
    assert unknown < min(ROLE_AUTHORITY_BP.values())
    assert unknown < max(RUNG_AUTHORITY_BP.values())
    assert unknown > RUNG_AUTHORITY_BP[ActorBasis.AUTOMATED]
    assert unknown != max(RUNG_AUTHORITY_BP.values())


def test_an_unrecognised_title_falls_through_rather_than_being_guessed():
    """"Growth Ninja" is not a rung. The cascade continues to the domain rungs instead of
    handing 9000 basis points to a job title nobody in the ladder ever read."""
    attribution = analyze_source(_event(email="ninja@acme-corp.com"),
                                 actor_role="Growth Ninja", org_domains=ORG_DOMAINS)
    assert attribution.actor_basis is ActorBasis.SAME_DOMAIN
    assert role_authority_bp("Growth Ninja") is None


@pytest.mark.parametrize("title, expected", [
    ("ceo", 10000), ("CEO", 10000), (" Chief Executive Officer ", 10000),
    ("cfo", 9500), ("coo", 9500),
    ("Senior Director", 9000), ("head of sales", 9000),
    ("Account Manager", 8000), ("team lead", 8000),
    ("analyst", 6000), ("intern", 5000),
    ("", None), (None, None), ("!!!", None), ("wizard", None),
])
def test_role_ladder_normalisation(title, expected):
    """One row per shape a graph role arrives in — case, spacing, alias, compound, junk."""
    assert role_authority_bp(title) == expected


def test_role_ladder_is_ordered_and_never_below_the_unknown_rung():
    """A ladder, not a scatter: seniority orders, and identifying a person can never cost them
    authority relative to a person we failed to identify."""
    assert (role_authority_bp("ceo") > role_authority_bp("cfo") > role_authority_bp("director")
            > role_authority_bp("manager") > role_authority_bp("analyst")
            > role_authority_bp("intern"))
    assert min(ROLE_AUTHORITY_BP.values()) > RUNG_AUTHORITY_BP[ActorBasis.UNKNOWN]


def test_attribution_is_frozen_and_reproducible():
    """Two calls over one event are equal, and neither answer can be edited afterwards."""
    event = _event(email="v.rao@vendor.com")
    first = analyze_source(event, actor_role="cfo")
    second = analyze_source(event, actor_role="cfo")
    assert first == second
    with pytest.raises(Exception):
        first.actor_authority_bp = 10000            # type: ignore[misc]


def test_every_rung_and_role_is_integer_basis_points():
    """DOCTRINE — every number that feeds ranking is a deterministic integer in 0..10000. A
    float here would reproduce differently on two machines after one multiplication."""
    for value in (*RUNG_AUTHORITY_BP.values(), *ROLE_AUTHORITY_BP.values()):
        assert isinstance(value, int) and not isinstance(value, bool)
        assert 0 <= value <= 10000


# ==========================================================================================
# D11 · two behaviours the cascade promises in prose and no test had ever pinned.
# ==========================================================================================

def test_a_compound_title_resolves_through_its_LEADING_segment_only():
    """`_normalise_title`'s own rule, and the only thing standing between a VP and 5000 basis
    points: *"Only the LEADING segment, never the trailing one — 'vp_of_interns' must not
    resolve through 'interns'."* Nothing tested it. A future edit that scanned every segment
    of the title would keep `"VP, Sales"` green — the case that IS covered — while quietly
    ranking a VP as an intern, because "interns" is a real row and it is the one that would
    match.
    """
    assert role_authority_bp("VP of Interns") == ROLE_AUTHORITY_BP["vp"] == 9000
    assert role_authority_bp("Head of Contractors") == ROLE_AUTHORITY_BP["head"] == 9000
    # The other direction: a leading segment that is not a rung falls through to None rather
    # than reaching for a trailing one.
    assert role_authority_bp("Growth Lead Ninja") is None


def test_the_same_domain_rung_reads_the_owner_and_a_configured_at_prefixed_domain():
    """Two inputs to rung 5 that no test supplied, both of which decide `SAME_DOMAIN` vs
    `EXTERNAL` — the two rungs that share the number 5000 and differ only in the audit basis a
    reviewer reads back.

    * an org domain configured with its `@` (`"@acme-corp.com"`), which the cascade strips;
    * NO configured org domains at all, where the connected mailbox owner's own domain is the
      only thing that can say "this is a colleague". Every sweep that never configured
      `org_domains` — which is every sweep today, since `EsqeStage.org_domains` defaults to
      `()` — depends on exactly this line.
    """
    at_prefixed = analyze_source(_event(email="deepthi@acme-corp.com"),
                                 org_domains=("@Acme-Corp.COM ",))
    from_owner_alone = analyze_source(_event(email="deepthi@acme-corp.com"),
                                      mailbox_owner="Rohit@Acme-Corp.com")
    outsider = analyze_source(_event(email="buyer@vendor.com"),
                              mailbox_owner="rohit@acme-corp.com")

    assert at_prefixed.actor_basis is ActorBasis.SAME_DOMAIN
    assert from_owner_alone.actor_basis is ActorBasis.SAME_DOMAIN
    assert outsider.actor_basis is ActorBasis.EXTERNAL
