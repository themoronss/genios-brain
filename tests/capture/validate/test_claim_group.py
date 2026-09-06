"""G5 · claim grouping (L1.5.0, ALG-22 + ALG-23) — the unit that makes conflict detection possible.

    pytest tests/capture/validate/test_claim_group.py -q

The headline is one fixture and it is the reason the component exists: a Gmail message lands as
an ``email_message`` **plus** an ``email_attachment`` (``connectors/composio.py:512`` and
``:559``) — two events — so the covering mail's \\$84,000 and the signed PDF's \\$74,000 are two
rows. Grouped by event they are never compared and both publish. This file proves they land in
ONE group, that the group holds exactly one contradictory pair of amounts, and that the same
join does not drag two unrelated deals in one thread together.

Three properties are asserted from outside the unit, because each has already been a defect
somewhere in this build:

* the **real entry point** runs it — ``run_sync``, the function every polling path goes through,
  with a real connector, a real gate and a real extractor over a scripted model. A unit with no
  production caller is not done;
* the key is **stable across processes** — asserted from a subprocess under a different
  ``PYTHONHASHSEED``, since a key that moves regroups claims and makes ALG-12's output
  nondeterministic;
* input **order does not matter** — a shuffled batch produces byte-identical groups.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture import pipeline as P
from genios_engine.capture.validate.claim_group import (
    MAX_CLAIMS_PER_GROUP,
    FieldFamily,
    SubjectTier,
    assemble_claim_groups,
    claims_from_extraction,
    document_identity,
    field_family_of,
    subject_key,
    thread_group_key,
)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (Commitment, DecisionState, Dependency,
                                                EntityMention, ExtractionResult,
                                                UnclassifiedObservation)
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.units import DateCertainty, Money, ResolvedDate

WAVE = "W5"
GATE = "G5"

NOW = datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)
ORG = "org_cg"
CONN = "con_cg"
OWNER = "founder@genios.ai"

THREAD = "thread_18c4a"
MESSAGE = "msg_18c4a9e2f7"
ATTACHMENT = f"{MESSAGE}::MSA_signed_v2.pdf"


# ----------------------------------------------------------------------------------------
# builders — every one of these produces a REAL contract object, never a stub
# ----------------------------------------------------------------------------------------
def _event(*, event_id: str, object_type: str = "email_message", source: str = "gmail",
           source_object_id: str = MESSAGE, parent: str | None = THREAD,
           source_family: str = "communication", occurred_at: datetime = NOW,
           internal_kind: str | None = None) -> SourceEvent:
    return SourceEvent(
        event_id=event_id, org_id=ORG, connection_id=CONN, source=source,
        source_family=source_family, object_type=object_type,
        source_object_id=source_object_id, parent_object_id=parent,
        dedup_key=f"{source}:{object_type}:{source_object_id}",
        actor=Actor(type="external_contact", email="buyer@acme.com"),
        occurred_at=occurred_at, captured_at=NOW, internal_kind=internal_kind)


def _span(quote: str, *, event_id: str = "evt_1") -> EvidenceSpan:
    return EvidenceSpan(source_ref=f"prepared_content:{event_id}", quote=quote,
                        start_offset=0, end_offset=len(quote))


def _money(minor_units: int, as_written: str) -> Money:
    return Money(minor_units=minor_units, currency="USD", as_written=as_written)


def _date(as_written: str) -> ResolvedDate:
    return ResolvedDate(as_written=as_written, earliest=NOW, latest=NOW,
                        certainty=DateCertainty.EXACT, resolved_against=NOW,
                        evidence=[_span(as_written)])


def _mention(surface: str, entity_type: str = "organization",
             hint: str | None = None) -> EntityMention:
    return EntityMention(surface_form=surface, entity_type=entity_type, canonical_hint=hint,
                         evidence=[_span(surface)], confidence_bp=9000)


def _extraction(*, mentions=(), amounts=(), dates=(), commitments=(), decisions=(),
                dependencies=(), observations=()) -> ExtractionResult:
    return ExtractionResult(
        intent="inform", stance="neutral", entity_mentions=list(mentions),
        amounts=list(amounts), dates_mentioned=list(dates), commitments=list(commitments),
        decision_states=list(decisions), dependencies=list(dependencies),
        unclassified_observations=list(observations),
        model_snapshot="fake-model-1", prompt_version="p1", schema_version="s1",
        extraction_profile="general", input_tokens=10, output_tokens=10)


def _lookup(*events: SourceEvent):
    index = {e.source_object_id: e for e in events}
    return index.get


def _group_holding(groups, claim) -> tuple:
    """The single group a given claim landed in — asserted to be exactly one."""
    found = [g for g in groups if any(c.claim is claim for c in g.claims)]
    assert len(found) == 1, f"claim appears in {len(found)} groups; a claim belongs to one"
    return found[0]


# ==========================================================================================
# L1.5.0-U1 · ALG-22 — the subject key cascade
# ==========================================================================================
CASCADE = [
    # (label, event kwargs, extraction, expected key, expected tier)
    ("structured id wins over everything else",
     dict(source="hubspot", object_type="deal", source_object_id="12345", parent=THREAD,
          source_family="enterprise_system"),
     _extraction(mentions=[_mention("Zenith")]),
     "hubspot:deal:12345:amount", SubjectTier.STRUCTURED),
    ("a file keys on its document identity",
     dict(object_type="email_attachment", source_object_id=ATTACHMENT, parent=MESSAGE),
     _extraction(), "document:msa-signed-v2-pdf:amount", SubjectTier.DOCUMENT),
    ("one named organisation anchors the claim, per field family",
     dict(), _extraction(mentions=[_mention("Acme Corp", hint="acme")]),
     "entity:acme:amount", SubjectTier.ENTITY),
    ("no entity, but a thread → the thread",
     dict(), _extraction(), f"thread:{THREAD}:amount", SubjectTier.THREAD),
    # Spelled out from the DOCUMENTED rule — blake2s over the dedup key — rather than by
    # calling the unit, which would assert the implementation against itself.
    ("nothing at all → the source OBJECT, which groups alone",
     dict(parent=None), _extraction(),
     f"event:{hashlib.blake2s(f'gmail:email_message:{MESSAGE}'.encode(), digest_size=8).hexdigest()}"
     ":amount", SubjectTier.EVENT),
]


@pytest.mark.gate
@pytest.mark.parametrize("label,over,extraction,expected,tier",
                         CASCADE, ids=[row[0] for row in CASCADE])
def test_the_alg22_cascade_answers_at_the_first_matching_rung(label, over, extraction,
                                                              expected, tier):
    event = _event(event_id="evt_alone", **over)
    amount = _money(8_400_000, "$84,000")
    thread = thread_group_key(event, _lookup(event))
    assert subject_key(amount, extraction, event, thread_key=thread) == expected
    claims = claims_from_extraction(event, _extraction(amounts=[amount], **(
        {"mentions": extraction.entity_mentions} if extraction.entity_mentions else {})),
        event_lookup=_lookup(event))
    assert claims[0].tier is tier


@pytest.mark.gate
def test_two_different_events_about_one_hubspot_deal_derive_an_identical_key():
    """HARD RULE 1: the key is derived, never minted. Different event ids, one subject."""
    monday = _event(event_id="evt_a", source="hubspot", object_type="deal",
                    source_object_id="12345", parent=None, source_family="enterprise_system")
    friday = _event(event_id="evt_b", source="hubspot", object_type="deal",
                    source_object_id="12345", parent=None, source_family="enterprise_system",
                    occurred_at=NOW + timedelta(days=4))
    amount = _money(8_400_000, "$84,000")
    assert (subject_key(amount, _extraction(), monday)
            == subject_key(amount, _extraction(), friday) == "hubspot:deal:12345:amount")


@pytest.mark.gate
def test_the_same_claim_reworded_keys_the_same_and_a_different_subject_does_not():
    """`$84,000` and `84K USD` are one claim written twice; Zenith's deal is a different one."""
    event = _event(event_id="evt_1")
    acme = _extraction(mentions=[_mention("Acme, Inc.")])
    acme_again = _extraction(mentions=[_mention("acme")])
    zenith = _extraction(mentions=[_mention("Zenith Logistics")])

    formal = subject_key(_money(8_400_000, "$84,000"), acme, event)
    casual = subject_key(_money(8_400_000, "84K USD"), acme_again, event)
    other = subject_key(_money(8_400_000, "$84,000"), zenith, event)

    assert formal == casual == "entity:acme:amount"
    assert other != formal


@pytest.mark.gate
def test_two_organisations_in_one_message_anchor_nothing():
    """Ambiguity is not a match — the law canonical.py states, obeyed here too."""
    event = _event(event_id="evt_intro")
    both = _extraction(mentions=[_mention("Acme"), _mention("Zenith")])
    assert subject_key(_money(1, "$1"), both, event, thread_key="thread:t") == "thread:t:amount"


@pytest.mark.gate
def test_a_person_never_anchors_a_deal_amount():
    """A person cc'd on a deal thread is a participant, not the subject."""
    event = _event(event_id="evt_p")
    people = _extraction(mentions=[_mention("Rohit", entity_type="person")])
    assert subject_key(_money(1, "$1"), people, event, thread_key="thread:t") == "thread:t:amount"


FAMILIES = [
    (_money(1, "$1"), FieldFamily.AMOUNT),
    (_date("March 4"), FieldFamily.DATE),
    (Commitment(actor="us", action="send the contract", is_conditional=False,
                evidence=[_span("send the contract")], confidence_bp=9000),
     FieldFamily.COMMITMENT),
    (DecisionState(subject="pricing", state="open", evidence=[_span("pricing")],
                   confidence_bp=9000), FieldFamily.DECISION),
    (Dependency(blocker="legal", blocked="signature", dependency_type="blocks",
                evidence=[_span("legal")], confidence_bp=9000), FieldFamily.DEPENDENCY),
    (_mention("Acme"), FieldFamily.ENTITY),
    (UnclassifiedObservation(proposed_kind="mood", description="tense",
                             evidence=[_span("tense")], confidence_bp=6000),
     FieldFamily.OBSERVATION),
]


@pytest.mark.gate
@pytest.mark.parametrize("claim,family", FAMILIES, ids=[f.value for _, f in FAMILIES])
def test_every_claim_type_maps_to_its_field_family(claim, family):
    assert field_family_of(claim) is family


@pytest.mark.gate
def test_an_unknown_claim_shape_is_refused_rather_than_filed_under_a_default():
    with pytest.raises(TypeError):
        field_family_of("84000")            # type: ignore[arg-type]


@pytest.mark.gate
def test_an_amount_and_a_date_about_one_company_are_different_subjects():
    """Without the family in the key, ALG-12 would compare a due date against a price."""
    event = _event(event_id="evt_1")
    acme = _extraction(mentions=[_mention("Acme", hint="acme")])
    assert subject_key(_money(1, "$1"), acme, event) == "entity:acme:amount"
    assert subject_key(_date("March 4"), acme, event) == "entity:acme:date"


# ==========================================================================================
# ALG-23 · the parent walk
# ==========================================================================================
@pytest.mark.gate
def test_the_parent_walk_reaches_the_thread_from_both_the_message_and_its_attachment():
    """attachment --parent--> email --parent--> thread. The two hops composio.py already writes."""
    email = _event(event_id="evt_mail")
    pdf = _event(event_id="evt_pdf", object_type="email_attachment",
                 source_object_id=ATTACHMENT, parent=MESSAGE)
    lookup = _lookup(email, pdf)
    assert thread_group_key(email, lookup) == f"thread:{THREAD}"
    assert thread_group_key(pdf, lookup) == f"thread:{THREAD}"


WALKS = [
    ("no parent at all", dict(parent=None), None),
    ("a self-referencing parent terminates", dict(parent=MESSAGE), f"thread:{MESSAGE}"),
]


@pytest.mark.gate
@pytest.mark.parametrize("label,over,expected", WALKS, ids=[w[0] for w in WALKS])
def test_the_walk_is_total(label, over, expected):
    event = _event(event_id="evt_1", **over)
    assert thread_group_key(event, _lookup(event)) == expected


@pytest.mark.gate
def test_a_lookup_that_raises_is_a_miss_and_not_a_crash():
    def _explodes(_: str):
        raise RuntimeError("the repository is down")

    email = _event(event_id="evt_mail")
    assert thread_group_key(email, _explodes) == f"thread:{THREAD}"


@pytest.mark.gate
def test_a_forwarded_attachment_with_a_broken_chain_falls_back_to_document_identity():
    """Doc 05's failure row: parent chain broken → fall back to ALG-22 rule 2, never orphaned."""
    orphan = _event(event_id="evt_fwd", object_type="email_attachment",
                    source_object_id=f"msg_forwarded::{'MSA_signed_v2.pdf'}",
                    parent="msg_forwarded")
    assert thread_group_key(orphan, _lookup(orphan)) is None, (
        "an unresolvable MESSAGE parent is not a thread; minting one orphans the file quietly")
    assert document_identity(orphan) == "document:msa-signed-v2-pdf"
    assert subject_key(_money(7_400_000, "$74,000"), _extraction(), orphan) == \
        "document:msa-signed-v2-pdf:amount"


@pytest.mark.gate
def test_the_same_file_forwarded_into_a_second_thread_groups_with_the_original():
    """Two copies, two threads, no parent events — the document identity is what joins them."""
    first = _event(event_id="evt_pdf_1", object_type="email_attachment",
                   source_object_id=f"msg_a::{'MSA_signed_v2.pdf'}", parent="msg_a")
    second = _event(event_id="evt_pdf_2", object_type="email_attachment",
                    source_object_id=f"msg_b::{'msa-signed-v2.PDF'}", parent="msg_b",
                    occurred_at=NOW + timedelta(days=30))
    claims = [*claims_from_extraction(first, _extraction(amounts=[_money(7_400_000, "$74,000")]),
                                      event_lookup=_lookup(first, second)),
              *claims_from_extraction(second, _extraction(amounts=[_money(7_400_000, "$74,000")]),
                                      event_lookup=_lookup(first, second))]
    groups = assemble_claim_groups(claims, [first, second])
    assert len(groups) == 1 and groups[0].group_key == "document:msa-signed-v2-pdf:amount"


# ==========================================================================================
# L1.5.0-U2 · ALG-23 — THE HEADLINE FIXTURE
# ==========================================================================================
def _founders_example() -> tuple[list, list]:
    """The covering email (\\$84,000) and its signed attachment (\\$74,000), as TWO events."""
    email = _event(event_id="evt_mail")
    pdf = _event(event_id="evt_pdf", object_type="email_attachment",
                 source_object_id=ATTACHMENT, parent=MESSAGE)
    lookup = _lookup(email, pdf)
    claims = [
        *claims_from_extraction(
            email, _extraction(mentions=[_mention("Acme Corp", hint="acme")],
                               amounts=[_money(8_400_000, "$84,000")]), event_lookup=lookup),
        *claims_from_extraction(
            pdf, _extraction(amounts=[_money(7_400_000, "$74,000")]), event_lookup=lookup),
    ]
    return claims, [email, pdf]


@pytest.mark.gate
def test_an_email_and_its_attachment_land_in_ONE_group_across_two_events():
    """THE acceptance test. Two events, one subject, one comparable pair — the defect fix."""
    claims, events = _founders_example()
    groups = assemble_claim_groups(claims, events)

    amounts = [g for g in groups if any(c.family is FieldFamily.AMOUNT for c in g.claims)]
    assert len(amounts) == 1, ("$84,000 and $74,000 were grouped separately — this is exactly "
                               "the across-events defect L1.5.0 exists to fix")
    values = sorted(c.claim.minor_units for c in amounts[0].claims
                    if c.family is FieldFamily.AMOUNT)
    assert values == [7_400_000, 8_400_000]
    assert len({c.event_id for c in amounts[0].claims}) == 2, "one group, two events"
    assert len(set(values)) == 2, "one conflict: two answers to one question about one amount"


@pytest.mark.gate
def test_two_unrelated_deals_in_one_thread_do_not_merge():
    """Doc 05's other failure row: subject_key must match, not merely the thread."""
    acme_mail = _event(event_id="evt_acme")
    zenith_mail = _event(event_id="evt_zen", source_object_id="msg_second")
    lookup = _lookup(acme_mail, zenith_mail)
    claims = [
        *claims_from_extraction(acme_mail,
                                _extraction(mentions=[_mention("Acme Corp", hint="acme")],
                                            amounts=[_money(8_400_000, "$84,000")]),
                                event_lookup=lookup),
        *claims_from_extraction(zenith_mail,
                                _extraction(mentions=[_mention("Zenith Ltd", hint="zenith")],
                                            amounts=[_money(5_000_000, "$50,000")]),
                                event_lookup=lookup),
    ]
    groups = assemble_claim_groups(claims, [acme_mail, zenith_mail])
    keys = {g.group_key for g in groups
            if any(c.family is FieldFamily.AMOUNT for c in g.claims)}
    assert keys == {"entity:acme:amount", "entity:zenith:amount"}


@pytest.mark.gate
def test_an_anchorless_claim_in_a_thread_holding_two_subjects_is_attributed_to_neither():
    """With two candidates and no evidence, attributing the attachment is a coin flip."""
    acme_mail = _event(event_id="evt_acme")
    zenith_mail = _event(event_id="evt_zen", source_object_id="msg_second")
    pdf = _event(event_id="evt_pdf", object_type="email_attachment",
                 source_object_id=ATTACHMENT, parent=MESSAGE)
    lookup = _lookup(acme_mail, zenith_mail, pdf)
    claims = [
        *claims_from_extraction(acme_mail,
                                _extraction(mentions=[_mention("Acme", hint="acme")],
                                            amounts=[_money(8_400_000, "$84,000")]),
                                event_lookup=lookup),
        *claims_from_extraction(zenith_mail,
                                _extraction(mentions=[_mention("Zenith", hint="zenith")],
                                            amounts=[_money(5_000_000, "$50,000")]),
                                event_lookup=lookup),
        *claims_from_extraction(pdf, _extraction(amounts=[_money(7_400_000, "$74,000")]),
                                event_lookup=lookup),
    ]
    groups = assemble_claim_groups(claims, [acme_mail, zenith_mail, pdf])
    pdf_group = _group_holding(groups, claims[-1].claim)
    assert pdf_group.group_key == "document:msa-signed-v2-pdf:amount"
    assert {c.event_id for c in pdf_group.claims} == {"evt_pdf"}


@pytest.mark.gate
def test_the_window_is_unbounded_in_time():
    """An amendment six months later must still conflict with the original."""
    original = _event(event_id="evt_orig")
    amendment = _event(event_id="evt_amend", source_object_id="msg_later",
                       occurred_at=NOW + timedelta(days=183))
    lookup = _lookup(original, amendment)
    claims = [
        *claims_from_extraction(original,
                                _extraction(mentions=[_mention("Acme", hint="acme")],
                                            amounts=[_money(8_400_000, "$84,000")]),
                                event_lookup=lookup),
        *claims_from_extraction(amendment,
                                _extraction(mentions=[_mention("Acme", hint="acme")],
                                            amounts=[_money(9_000_000, "$90,000")]),
                                event_lookup=lookup),
    ]
    groups = assemble_claim_groups(claims, [original, amendment])
    group = _group_holding(groups, claims[0].claim)
    assert len(group.claims) == 2 and group.group_key == "entity:acme:amount"


@pytest.mark.gate
def test_a_six_hundred_claim_thread_caps_at_five_hundred_by_authority_rank():
    """The cap, and WHICH five hundred: the signed attachment survives, chatter does not."""
    chatter = _event(event_id="evt_chat")
    signed = _event(event_id="evt_pdf", object_type="email_attachment",
                    source_object_id=ATTACHMENT, parent=MESSAGE)
    lookup = _lookup(chatter, signed)
    mentions = [_mention("Acme", hint="acme")]
    noise = _extraction(mentions=mentions,
                        amounts=[_money(1_000 + i, f"${i}") for i in range(599)])
    claims = [*claims_from_extraction(chatter, noise, event_lookup=lookup),
              *claims_from_extraction(signed,
                                      _extraction(mentions=mentions,
                                                  amounts=[_money(7_400_000, "$74,000")]),
                                      event_lookup=lookup)]
    assert len(claims) == 602                      # 599 + 1 amounts, plus 2 entity mentions

    groups = assemble_claim_groups(claims, [chatter, signed])
    amounts = _group_holding(groups, claims[0].claim)
    assert amounts.size == MAX_CLAIMS_PER_GROUP
    assert amounts.truncated == 100
    top = max(c.authority_rank for c in claims)
    assert amounts.claims[0].authority_rank == top, "the cap keeps the most authoritative first"
    assert any(c.event_id == "evt_pdf" for c in amounts.claims), (
        "the signed attachment was dropped in favour of chatter — the cap's ordering is wrong")
    assert all(c.family is FieldFamily.AMOUNT for c in amounts.claims), (
        "the cap kept claims from another field family; the group was already too wide")


@pytest.mark.gate
def test_a_group_that_did_not_overflow_reports_no_truncation():
    claims, events = _founders_example()
    assert all(g.truncated == 0 for g in assemble_claim_groups(claims, events))


@pytest.mark.gate
def test_a_claim_whose_event_is_missing_still_groups_by_its_own_subject():
    """Never raise: a batch that lost an event loses the thread clause, not the claim."""
    event = _event(event_id="evt_gone", source="hubspot", object_type="deal",
                   source_object_id="12345", parent=None, source_family="enterprise_system")
    claims = claims_from_extraction(event, _extraction(amounts=[_money(1, "$1")]))
    groups = assemble_claim_groups(claims, [])          # no events supplied at all
    assert len(groups) == 1 and groups[0].group_key == "hubspot:deal:12345:amount"


@pytest.mark.gate
def test_no_claims_is_no_groups_rather_than_an_empty_group():
    assert assemble_claim_groups([], []) == ()


# ==========================================================================================
# STABILITY — an unstable key makes ALG-12 nondeterministic
# ==========================================================================================
@pytest.mark.gate
def test_input_order_does_not_change_the_grouping():
    claims, events = _founders_example()
    forward = assemble_claim_groups(claims, events)
    backward = assemble_claim_groups(list(reversed(claims)), list(reversed(events)))
    assert [(g.group_key, g.size) for g in forward] == [(g.group_key, g.size) for g in backward]


_SUBPROCESS = r"""
import json
from datetime import datetime, timezone
from genios_engine.capture.validate.claim_group import (assemble_claim_groups,
                                                        claims_from_extraction, subject_key)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import EntityMention, ExtractionResult
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.units import Money

NOW = datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)


def event(event_id, object_type, source_object_id, parent):
    return SourceEvent(event_id=event_id, org_id="org_cg", connection_id="con_cg",
                       source="gmail", source_family="communication", object_type=object_type,
                       source_object_id=source_object_id, parent_object_id=parent,
                       dedup_key=event_id, actor=Actor(type="external_contact"),
                       occurred_at=NOW, captured_at=NOW)


def mention(surface):
    span = EvidenceSpan(source_ref="prepared_content:e", quote=surface, start_offset=0,
                        end_offset=len(surface))
    return EntityMention(surface_form=surface, entity_type="organization",
                         evidence=[span], confidence_bp=9000)


def extraction(mentions, amounts):
    return ExtractionResult(intent="inform", stance="neutral", entity_mentions=mentions,
                            amounts=amounts, model_snapshot="m", prompt_version="p",
                            schema_version="s", extraction_profile="general",
                            input_tokens=1, output_tokens=1)


mail = event("evt_mail", "email_message", "msg_18c4a9e2f7", "thread_18c4a")
pdf = event("evt_pdf", "email_attachment", "msg_18c4a9e2f7::MSA_signed_v2.pdf", "msg_18c4a9e2f7")
lookup = {e.source_object_id: e for e in (mail, pdf)}.get
claims = list(claims_from_extraction(
    mail, extraction([mention("Acme Corp"), mention("Acme, Inc.")],
                     [Money(minor_units=8400000, currency="USD", as_written="$84,000")]),
    event_lookup=lookup))
claims += list(claims_from_extraction(
    pdf, extraction([], [Money(minor_units=7400000, currency="USD", as_written="$74,000")]),
    event_lookup=lookup))
groups = assemble_claim_groups(claims, [mail, pdf])
print(json.dumps([[g.group_key, g.tier.value, sorted(c.subject for c in g.claims)]
                  for g in groups]))
"""


@pytest.mark.gate
@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_the_key_is_identical_in_a_subprocess_with_a_different_hash_seed(seed):
    """A key derived from set or dict iteration order would drift here and nowhere else.

    Run as a separate interpreter because `PYTHONHASHSEED` is fixed at startup: patching the
    environment inside this process would prove nothing at all.
    """
    import os
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(root)}
    out = subprocess.run([sys.executable, "-c", _SUBPROCESS], capture_output=True, text=True,
                         env=env, cwd=str(root), timeout=180)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [
        ["entity:acme:amount", 3,
         ["document:msa-signed-v2-pdf:amount", "entity:acme:amount"]],
        ["entity:acme:entity", 3, ["entity:acme:entity", "entity:acme:entity"]],
    ]


# ==========================================================================================
# WIRED — driven through run_sync, the function every polling path in the product calls
# ==========================================================================================
BODY = ("Attaching the signed MSA. As discussed the annual figure with Acme Corp "
        "is $84,000 for year one.")
PDF_TEXT = ("MASTER SERVICES AGREEMENT between Acme Corp and GeniOS. "
            "Total annual fee: $74,000, payable quarterly.")


def _cite(text: str, quote: str) -> list[dict]:
    start = text.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


class _ScriptedLLM:
    """A model that answers from the CONTENT it was shown, not from call order.

    Order-keyed canned answers cannot be used here: `run_sync` captures a page through a thread
    pool, so the mail and its attachment race, and a fixture that depended on which finished
    first would be flaky in exactly the way this unit must not be.
    """

    model = "fake-model-1"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def call(self, prompt: str, *, max_tokens: int = 4096):
        from dataclasses import dataclass

        @dataclass
        class _Result:
            parsed: dict
            raw: str
            input_tokens: int = 100
            output_tokens: int = 50
            model: str = "fake-model-1"
            cached: bool = False
            ok: bool = True
            error: str | None = None

        self.calls.append(prompt)
        if "74,000" in prompt:
            text, amount, written = PDF_TEXT, 7_400_000, "$74,000"
        else:
            text, amount, written = BODY, 8_400_000, "$84,000"
        payload = {
            "intent": "inform", "stance": "neutral",
            "entity_mentions": [{"surface_form": "Acme Corp", "entity_type": "organization",
                                 "evidence": _cite(text, "Acme Corp"), "confidence_bp": 9000}],
            "amounts": [{"minor_units": amount, "currency": "USD", "as_written": written}],
        }
        return _Result(parsed=payload, raw=json.dumps(payload, sort_keys=True))


class _MailboxWithAnAttachment:
    """One Gmail message → two RawObjects, exactly as composio.py:512/:559 emits them."""

    source = "gmail"

    def validate_connection(self) -> bool:
        return True

    def _objects(self) -> list[RawObject]:
        return [
            RawObject(source="gmail", object_type="email_message", source_object_id=MESSAGE,
                      occurred_at=NOW, actor_email="buyer@acme.com", recipients=(OWNER,),
                      parent_object_id=THREAD,
                      raw={"subject": "Signed MSA", "body": BODY}),
            RawObject(source="gmail", object_type="email_attachment",
                      source_object_id=ATTACHMENT, occurred_at=NOW,
                      actor_email="buyer@acme.com", recipients=(OWNER,),
                      parent_object_id=MESSAGE,
                      raw={"subject": "MSA_signed_v2.pdf", "body": PDF_TEXT,
                           "has_attachment": True}),
        ]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


@pytest.mark.gate
def test_run_sync_assembles_the_group_across_the_two_events_it_just_captured():
    """The production caller. Without this wiring the assembler is a library nothing reaches.

    Driven from the real entry point — a real connector page, the real gate, the real extractor
    over a scripted model — so what is asserted is the product's behaviour and not the unit's.
    """
    llm = _ScriptedLLM()
    summary = run_sync(_MailboxWithAnAttachment(), org_id=ORG, connection_id=CONN,
                       repo=InMemorySourceEventRepository(), mode="backfill",
                       mailbox_owner=OWNER, source="gmail",
                       semantic=P.SemanticLane(llm=llm, eval_time=NOW))

    assert summary.scanned == 2 and llm.calls, "the page did not reach the extractor"
    extracted = [r for r in summary.results if r.extraction is not None]
    assert len(extracted) == 2, f"both events must extract; got {len(extracted)}"

    amount_groups = [g for g in summary.claim_groups
                     if any(c.family is FieldFamily.AMOUNT for c in g.claims)]
    assert len(amount_groups) == 1, (
        "run_sync published two separate amount groups — the email's $84,000 and the signed "
        "PDF's $74,000 were never compared, which is the defect L1.5.0 fixes")
    values = sorted(c.claim.minor_units for c in amount_groups[0].claims
                    if c.family is FieldFamily.AMOUNT)
    assert values == [7_400_000, 8_400_000]
    assert len({c.event_id for c in amount_groups[0].claims}) == 2


@pytest.mark.gate
def test_a_sweep_that_extracted_nothing_carries_no_groups():
    """No semantic lane wired → no claims → an empty tuple, never a crash at the seam."""
    summary = run_sync(_MailboxWithAnAttachment(), org_id=ORG, connection_id=CONN,
                       repo=InMemorySourceEventRepository(), mode="backfill",
                       mailbox_owner=OWNER, source="gmail")
    assert summary.claim_groups == ()


# ==========================================================================================
# RUNG 5 · the key a re-ingestion must not move
# ==========================================================================================
LONE_BODY = "Confirming the number we discussed: $84,000, flat, no other terms."


class _AmountOnlyLLM:
    """Returns one amount and NOTHING else — no organisation, so rungs 1-4 have no answer and
    the cascade falls to rung 5. The shape of a real short reply from a personal address."""

    model = "fake-model-1"

    def call(self, prompt: str, *, max_tokens: int = 4096):     # noqa: ARG002
        from dataclasses import dataclass

        @dataclass
        class _Result:
            parsed: dict
            raw: str
            input_tokens: int = 10
            output_tokens: int = 10
            model: str = "fake-model-1"
            cached: bool = False
            ok: bool = True
            error: str | None = None

        payload = {"intent": "inform", "stance": "neutral", "entity_mentions": [],
                   "amounts": [{"minor_units": 8_400_000, "currency": "USD",
                                "as_written": "$84,000"}]}
        return _Result(parsed=payload, raw=json.dumps(payload, sort_keys=True))


class _LoneMessage:
    """One message, no thread and no attachment: nothing for rungs 1-4 to key on."""

    source = "gmail"

    def validate_connection(self) -> bool:
        return True

    def _objects(self) -> list[RawObject]:
        return [RawObject(source="gmail", object_type="email_message",
                          source_object_id=MESSAGE, occurred_at=NOW,
                          actor_email="buyer@personal.example", recipients=(OWNER,),
                          parent_object_id=None, raw={"subject": "re: number", "body": LONE_BODY})]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


def _lone_amount_subject() -> str:
    """One ingestion of the same message through the real path, and the key it derived."""
    summary = run_sync(_LoneMessage(), org_id=ORG, connection_id=CONN,
                       repo=InMemorySourceEventRepository(), mode="backfill",
                       mailbox_owner=OWNER, source="gmail",
                       semantic=P.SemanticLane(llm=_AmountOnlyLLM(), eval_time=NOW))
    amounts = [c for g in summary.claim_groups for c in g.claims
               if c.family is FieldFamily.AMOUNT]
    assert len(amounts) == 1, f"the lone message did not produce one amount claim: {amounts}"
    return amounts[0].subject


@pytest.mark.gate
def test_the_rung_five_key_survives_a_re_ingestion_of_the_same_message():
    """HARD RULE 1 at the rung it was broken at: the key is DERIVED, never minted.

    `capture/landing/normalize.py:33` mints `event_id` fresh on every ingestion, so a rung-5 key
    built from it moved every time the same message was captured again — a recovery re-scan, a
    reconnected mailbox, a replayed page. Supersession then failed silently in the worst
    possible way: the claim did not group with its own earlier self, so the correction and the
    thing it corrected both stood, and nothing raised.

    Two full ingestions of one message through `run_sync`, and the same key must come out.
    """
    first, second = _lone_amount_subject(), _lone_amount_subject()
    assert first == second, (
        "the same message re-ingested derived a different rung-5 subject key: "
        f"{first} != {second}")


@pytest.mark.gate
def test_the_rung_five_key_is_the_dedup_key_and_not_the_minted_event_id():
    """The property behind the test above, at the unit, so a regression names its cause.

    Two SourceEvents for one source object — different `event_id`, identical `dedup_key`, which
    is exactly what a re-ingestion produces — derive one key; and the minted id appears in it
    nowhere, because anything carrying that id moves on the next capture.
    """
    amount = _money(8_400_000, "$84,000")
    first = _event(event_id="evt_first", parent=None)
    again = _event(event_id="evt_second", parent=None)
    assert first.dedup_key == again.dedup_key and first.event_id != again.event_id

    key = subject_key(amount, _extraction(), first)
    assert key == subject_key(amount, _extraction(), again)
    assert key.startswith("event:") and key.endswith(":amount")
    assert "evt_first" not in key and "evt_second" not in key

    other_object = _event(event_id="evt_first", source_object_id="msg_other", parent=None)
    assert subject_key(amount, _extraction(), other_object) != key, \
        "two different source objects collapsed into one rung-5 group"
