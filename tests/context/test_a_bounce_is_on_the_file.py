"""STEP-10 · a bounce is on the file — a delivery report that says FAILED is written on the address that
failed and on the original's thread.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_bounce_is_on_the_file.py -q

`context/delivery.record_delivery_failure`, called from `context/pipeline.process_event` (tree
`yc2_w27_s10 · M29.C3.L-logic.V1.U02`, `06` D38). The founder's pitch to a fund bounced (golden F16) and
memory filed what it learned on the SENDER — the mail daemon's `service` node, noise for the network —
so nothing on the fund's file said the mail never arrived, and the pitch still read "waiting". Now a
report `capture/delivery_status` reads as FAILED writes a `delivery_failure` observation on the address
that failed and on the original's thread, and `delivery.status = failed` on that address — the fact
`context/waiting` can retire their waiting by. The original is the latest mail WE sent in the same
Gmail thread with that address among its recipients; with none, the address still carries it. A delay,
an unclassified report, a report whose address cannot be read, a forward that only looks like one, and
an archive (whose words no reader reads) write nothing.
"""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import pipeline
from genios_engine.platform.self_identity import identity_for

from .workstream_world import FOUNDER, T0, extraction, facts, ledger, node, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_bounce"
FUND = "partners@lattice-capital.test"
DAEMON = "mailer-daemon@mailhost.test"
THREAD = "t-bounce"
SENT = T0
BOUNCED = T0 + timedelta(seconds=20)

#: Gmail's failure report, headline and all (`capture/delivery_status`'s fixtures).
FAILED = ("Delivery Status Notification (Failure)",
          "** Address not found **\n\nYour message wasn't delivered to " + FUND + " because the "
          "domain lattice-capital.test couldn't be found. Check for typos or unnecessary spaces "
          "and try again.")


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def report(store, *, event_id: str, subject: str, body: str, sender: str = DAEMON,
           thread: str | None = THREAD, at=BOUNCED, metadata_only: bool = False,
           text_field: str = "body"):
    """One report through the pipeline as `context/runner` hands a read mail: the ledger row Layer 1
    wrote, and its stored payload as `canon_meta` — the subject and body the parser reads (a mail
    settled from its list fields carries a `snippet` instead)."""
    us = identity_for(store, ORG)
    ledger(store, ORG, event_id=event_id, sender=sender, thread=thread, at=at,
           recipients=(FOUNDER,))
    return pipeline.process_event(
        org_id=ORG, event_id=event_id, source="gmail", content=f"{subject}\n\n{body}",
        sender_email=sender, sender_name="Mail Delivery Subsystem", recipient_emails=[FOUNDER],
        occurred_at=at, llm=None, store=store, is_inbound=True, internal_emails=us.addresses,
        self_identity=us, thread_id=thread,
        canon_meta={"subject": subject, text_field: body, "headers": {}},
        qualified_extraction=extraction(), metadata_only=metadata_only)


def pitch(store, event_id: str, *, at=SENT, thread: str | None = THREAD, to=(FUND,)):
    """The founder's own mail — an OUTBOUND event of the thread."""
    process(store, ORG, event_id=event_id, sender=FOUNDER, recipients=to, thread=thread, at=at,
            mentions=())


def row(store, event_id: str, *, parent: str, at, recipients, source: str = "gmail",
        object_type: str = "email_message") -> None:
    """`workstream_world.ledger`'s row, for a source or an object type it does not write: a file the
    founder attached (Gmail's first message id IS its thread id, so a file on the first mail carries
    the thread's id as its parent), or another source's event under the same id."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, parent_object_id, dedup_key, actor, recipients, occurred_at, "
            " captured_at, outcome) values (:e, :o, 'con_x', :s, :ot, :e, :t, :k, "
            " cast(:a as jsonb), :r, :at, :at, 'emitted')"),
            {"e": event_id, "o": ORG, "s": source, "ot": object_type, "t": parent,
             "k": f"{source}:{object_type}:{event_id}",
             "a": json.dumps({"type": "external_contact", "email": FOUNDER}),
             "r": list(recipients), "at": at})


def bounced_on(store, key: str) -> list[dict]:
    """The evidence of every `delivery_failure` observation on the node keyed `key`."""
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select r.evidence from graph_observations o "
            "  join graph_nodes n on n.org_id = o.org_id and n.node_id = o.subject_node_id "
            "       and n.valid_to is null "
            "  left join graph_source_refs r on r.org_id = o.org_id "
            "       and r.observation_id = o.observation_id "
            " where o.org_id = :o and n.canonical_key = :k and o.kind = 'delivery_failure'"),
            {"o": ORG, "k": key}).fetchall()
    return [r.evidence if isinstance(r.evidence, dict) else json.loads(r.evidence) for r in rows]


def anything_bounced(store) -> tuple[int, int]:
    """(`delivery_failure` observations, `delivery.status` facts) anywhere in the tenant."""
    with store.engine.connect() as c:
        return (c.execute(text("select count(*) from graph_observations where org_id = :o "
                               "and kind = 'delivery_failure'"), {"o": ORG}).scalar_one(),
                c.execute(text("select count(*) from graph_facts where org_id = :o "
                               "and field = 'delivery.status'"), {"o": ORG}).scalar_one())


def written_by(store, event_id: str) -> tuple[int, int]:
    """(observations, facts) the event created."""
    params = {"o": ORG, "e": event_id}
    with store.engine.connect() as c:
        return (c.execute(text("select count(*) from graph_observations where org_id = :o "
                               "and created_by_event_id = :e"), params).scalar_one(),
                c.execute(text("select count(*) from graph_facts where org_id = :o "
                               "and created_by_event_id = :e"), params).scalar_one())


def _evidence(original: str | None, *, thread: str | None = THREAD,
              reason: str | None = "Address not found") -> dict:
    return {"derived": "delivery status report", "report_event_id": "evt_bounce",
            "original_event_id": original, "recipient": FUND, "reason": reason,
            "thread": thread}


# ── a failure is on the file ─────────────────────────────────────────────────────────────────────

def test_a_failed_report_is_on_the_address_and_on_the_originals_thread(store):
    pitch(store, "evt_pitch")
    report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1])
    assert bounced_on(store, FUND) == [_evidence("evt_pitch")]
    assert bounced_on(store, f"thread:{THREAD}") == [_evidence("evt_pitch")]
    assert bounced_on(store, DAEMON) == [], "the daemon wrote the report; the bounce is not its"


def test_the_address_carries_delivery_status_failed(store):
    pitch(store, "evt_pitch")
    report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1])
    assert facts(store, ORG, FUND, "delivery.status") == [("failed", _evidence("evt_pitch"))]
    with store.engine.connect() as c:
        row = c.execute(text(
            "select f.value_type, f.authority_rank, f.occurred_at, f.created_by_event_id "
            "  from graph_facts f join graph_nodes n on n.org_id = f.org_id "
            "       and n.node_id = f.subject_node_id "
            " where f.org_id = :o and n.canonical_key = :k and f.field = 'delivery.status' "
            "   and f.valid_to is null"), {"o": ORG, "k": FUND}).one()
    assert (row.value_type, row.authority_rank) == ("enum", 2)
    assert (row.occurred_at, row.created_by_event_id) == (BOUNCED, "evt_bounce")


def test_the_original_is_the_latest_mail_we_sent_in_the_thread_to_that_address(store):
    pitch(store, "evt_first", at=SENT - timedelta(hours=2))
    pitch(store, "evt_second", at=SENT)                                    # ← the original
    row(store, "evt_deck", parent=THREAD, at=SENT + timedelta(seconds=1), recipients=(FUND,),
        object_type="email_attachment")                                  # a file, not a mail
    pitch(store, "evt_elsewhere", at=SENT + timedelta(seconds=2),
          to=("ops@nimbuslabs-partner.test",))                         # another address
    process(store, ORG, event_id="evt_theirs", sender="li@lattice-capital.test",
            recipients=(FOUNDER, FUND), thread=THREAD, at=SENT + timedelta(seconds=3))
    pitch(store, "evt_other_thread", at=SENT + timedelta(seconds=4), thread="t-other")
    row(store, "evt_other_source", parent=THREAD, at=SENT + timedelta(seconds=5),
        recipients=(FUND,), source="outlook")                            # not a Gmail thread
    pitch(store, "evt_after", at=BOUNCED + timedelta(hours=1))           # after the report
    report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1])
    assert [e["original_event_id"] for e in bounced_on(store, FUND)] == ["evt_second"]


def test_an_address_is_matched_as_an_address_not_as_spelled(store):
    """The report and the ledger each spell the address as their own header did."""
    pitch(store, "evt_pitch", to=("PARTNERS@lattice-capital.test",))
    report(store, event_id="evt_bounce", subject=FAILED[0],
           body=FAILED[1].replace(FUND, "Partners@Lattice-Capital.test"))
    assert [e["original_event_id"] for e in bounced_on(store, FUND)] == ["evt_pitch"]


def test_a_report_settled_from_its_list_fields_is_read_from_its_snippet(store):
    pitch(store, "evt_pitch")
    report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1], text_field="snippet")
    assert bounced_on(store, FUND) == [_evidence("evt_pitch")]


def test_with_no_original_the_address_still_carries_it(store):
    pitch(store, "evt_pitch", thread="t-other")
    report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1])
    assert bounced_on(store, FUND) == [_evidence(None)]
    assert node(store, ORG, f"thread:{THREAD}") is None, "no original, so no thread of it"
    assert [v for v, _ in facts(store, ORG, FUND, "delivery.status")] == ["failed"]


def test_a_report_outside_any_thread_is_still_on_the_address(store):
    pitch(store, "evt_pitch", thread=None)
    report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1], thread=None)
    assert bounced_on(store, FUND) == [_evidence(None, thread=None)]


def test_an_empty_thread_id_ties_the_report_to_nothing(store):
    """No thread, no tie — `pipeline._thread_node`'s own rule: an empty id is no thread, so other
    mail that carries none is never taken for the original."""
    pitch(store, "evt_pitch", thread="")
    report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1], thread="")
    assert bounced_on(store, FUND) == [_evidence(None, thread="")]


@pytest.mark.parametrize("address, node_type", [(FUND, "person"),
                                                ("support@vendor.test", "service")])
def test_an_address_never_seen_gets_the_node_the_pipeline_would_give_it(store, address, node_type):
    """Typed as `pipeline.process_event` types a recipient (`_person`), because a node is never
    re-typed: a support inbox that bounced is a service from its first sighting."""
    report(store, event_id="evt_bounce", subject=FAILED[0],
           body=f"Your message wasn't delivered to {address} because the address couldn't be "
                "found.")
    assert node(store, ORG, address).node_type == node_type
    assert len(bounced_on(store, address)) == 1


def test_an_address_of_ours_is_a_person_even_at_the_platforms_domain(store):
    """STEP-04's own case: the founder's second address on the product's domain is ours, and an
    exact address of ours is never a service (`_person`)."""
    ours = "ceo@thegenios.com"
    with store.engine.begin() as c:
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) "
                       "values (:o, 'address', :v, 'test')"), {"o": ORG, "v": ours})
    report(store, event_id="evt_bounce", subject=FAILED[0],
           body=f"Your message wasn't delivered to {ours} because the address couldn't be found.")
    assert node(store, ORG, ours).node_type == "person"


def test_the_writes_are_counted_on_the_event(store):
    """The event's own record (`graph_changes`, `L2Result`) counts every observation and fact the
    event left — the report's among them; and a second report of the same failure adds its
    observations and no new fact (the held `failed` is corroborated, not re-written)."""
    pitch(store, "evt_pitch")
    first = report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1])
    again = report(store, event_id="evt_bounce_again", subject=FAILED[0], body=FAILED[1],
                   at=BOUNCED + timedelta(minutes=1))
    assert (first.observations, first.facts) == written_by(store, "evt_bounce")
    assert (again.observations, again.facts) == written_by(store, "evt_bounce_again")
    assert (first.facts, again.facts) == (1, 0)


# ── nothing that is not a failure ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("subject, body", [
    ("Delivery Status Notification (Delay)",
     f"There was a temporary problem delivering your message to {FUND}. Gmail will retry for 47 "
     "more hours."),
    ("Delivery Status Notification", "Something happened with your message."),
])
def test_a_report_that_does_not_say_failure_writes_nothing(store, subject, body):
    pitch(store, "evt_pitch")
    report(store, event_id="evt_bounce", subject=subject, body=body)
    assert anything_bounced(store) == (0, 0)


def test_a_failure_whose_address_cannot_be_read_writes_nothing(store):
    """An address is never guessed — not even the original's only recipient."""
    pitch(store, "evt_pitch")
    report(store, event_id="evt_bounce", subject=FAILED[0],
           body="Your message was not delivered. 5.7.1 blocked by the receiving server.")
    assert anything_bounced(store) == (0, 0)


def test_a_forwarded_bounce_from_a_person_writes_nothing(store):
    pitch(store, "evt_pitch")
    report(store, event_id="evt_bounce", subject="Fwd: " + FAILED[0], body=FAILED[1],
           sender="priya@acme.test")
    assert anything_bounced(store) == (0, 0)


def test_an_archived_report_writes_nothing(store):
    """An archive's words stay unread (STEP-05, `metadata_only`) — even when a caller has them."""
    pitch(store, "evt_pitch")
    report(store, event_id="evt_bounce", subject=FAILED[0], body=FAILED[1], metadata_only=True)
    assert anything_bounced(store) == (0, 0)
