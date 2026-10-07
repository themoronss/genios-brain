"""STEP-10 · a bounce is on the file — a delivery report that says FAILED, written where it belongs.

Tree `yc2_w27_s10 · M29.C3.L-logic.V1.U02`, `06` D38.

WHAT WAS WRONG. A founder's pitch to a fund bounced (golden F16). Layer 1 can read the report —
`capture/delivery_status` names the address that failed, and whether delivery FAILED or is still
being tried — but memory files what a mail says on its SENDER, and the sender of a report is the
mail daemon: a `service` node, noise for the network, which no file is about. Nothing on the fund's
file said the mail never arrived, and the pitch still read "waiting" for a reply that could not
come (`speedrun008/YC-II W27/` STEP-10 §8.1).

WHAT IS TRUE NOW. When `pipeline.process_event` meets a report the parser reads as FAILED, this
writes, inside the event's own transaction:
  * a `delivery_failed` observation on the node of the address that failed, and on the original's
    thread node (`thread:<parent_object_id>`, made by `pipeline._thread_node`) when the original
    is found — evidence: the report's event id, the original's (None when not found), the
    address, the report's own reason;
  * `delivery.status = failed` (enum, authority rank 2) on that address's node — the fact a
    reader retires their waiting by (`context/waiting`).

THE ORIGINAL is the latest mail WE sent in the same Gmail thread, at or before the report, with
the failed address among its recipients: the ledger's `parent_object_id` and `recipients`, and
"we" by the pipeline's own `_ours`. Gmail files a report in the thread of the mail it reports on
(golden F16: one thread, 20 seconds apart), and that is the whole tie. A file attached to that
mail is not the mail — Gmail's first message id IS its thread id, so an attachment of it carries
the thread's id as its parent. With no such mail (the thread is older than the backfill window,
the report has no thread) the address still carries the bounce, with no original and no thread.

WHAT WRITES NOTHING, each for the reason its source gives:
  * a report the parser rejects — a person forwarding a bounce has its words and is not one
    (`capture/delivery_status`: "a fabricated delivery failure is worse than a missed one");
  * a delay or an unclassified report — still being delivered, or not known to have failed;
  * a failure whose address the report does not state — an address is never guessed, not even
    the original's only recipient;
  * an archive (`metadata_only`, STEP-05) — its words stay unread, whoever holds them.

The parser is handed the three inputs `capture/pipeline._delivery_status` hands it — the sender,
the subject, the body else the snippet, from the stored payload (`canon_meta`) — so Layer 1's
detector and this writer cannot disagree about whether a message bounced.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import text

from genios_engine.capture.delivery_status import read_delivery_status
from genios_engine.platform.identity import norm_email

#: The observation on the address and on the thread. Its meaning is that of L1's
#: `delivery_failure` kind (`observations/kinds.yaml`: neutral, not an ask, not progress), which
#: `qes_adapter` files on the report's SENDER; this is the same failure, on the file it is about.
KIND = "delivery_failed"
#: The fact on the address, and its one value.
FIELD = "delivery.status"
FAILED = "failed"
#: A fact of the mailbox's mechanics, as thread state is: rank 2, a grounded event.
RANK = 2

_SENT_IN_THREAD = text(
    "select event_id, actor->>'email' as sender, recipients from source_events "
    " where org_id = :o and source = :s and object_type = 'email_message' "
    "   and parent_object_id = :t and occurred_at <= :at "
    " order by occurred_at desc, event_id desc")


def record_delivery_failure(store, conn, *, org_id: str, event_id: str, source: str,
                            sender_email: str | None, canon_meta: dict | None,
                            thread_id: str | None, occurred_at: datetime | None,
                            ours: Callable[[str], bool], internal_emails: frozenset[str],
                            metadata_only: bool = False,
                            counted: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """Write a FAILED report on the file it belongs to. Returns `counted` — the event's running
    (observations, facts) — with this report's writes added, so the event's change record counts
    them.

    `ours` is the pipeline's answer to "did we send this" (`process_event._ours`);
    `internal_emails` its self set, which types a node the way `_person` does — an exact address
    of ours is never a service, and a node is never re-typed, so the first sighting decides.
    """
    observations, facts = counted
    if metadata_only:
        return counted
    raw = canon_meta if isinstance(canon_meta, dict) else {}
    status = read_delivery_status(sender=sender_email or "", subject=str(raw.get("subject") or ""),
                                  text=str(raw.get("body") or raw.get("snippet") or ""))
    address = norm_email(status.recipient) if status is not None and status.failed else None
    if not address:
        return counted

    # Imported here because `pipeline.py` imports this module — the same reason
    # `documents._fact_confidence` gives: one thread key, one typing rule, one confidence table.
    from genios_engine.context.pipeline import (FACT_CONF_BY_RANK, _is_automated_sender,
                                                _thread_node, is_platform_sender)

    original = _original(conn, org_id=org_id, source=source, thread_id=thread_id,
                         address=address, at=occurred_at, ours=ours)
    machine = address not in internal_emails and (_is_automated_sender(address)
                                                  or is_platform_sender(address))
    node = store.find_or_create_node(conn, org_id=org_id,
                                     node_type="service" if machine else "person",
                                     canonical_key=address, display_name=address,
                                     event_id=event_id)
    on = [node]
    if original is not None:
        on.append(_thread_node(store, conn, org_id=org_id, thread_id=thread_id,
                               event_id=event_id, counterparty=address))
    evidence = {"derived": "delivery status report", "report_event_id": event_id,
                "original_event_id": original, "recipient": address, "reason": status.reason,
                "thread": thread_id}
    for subject in on:
        store.write_observation(conn, org_id=org_id, subject_node_id=subject, kind=KIND,
                                confidence=FACT_CONF_BY_RANK[RANK], occurred_at=occurred_at,
                                event_id=event_id, evidence=evidence, source=source)
    written = store.write_fact(conn, org_id=org_id, subject_node_id=node, field=FIELD,
                               value=FAILED, value_type="enum",
                               confidence=FACT_CONF_BY_RANK[RANK], occurred_at=occurred_at,
                               event_id=event_id, evidence=evidence, source=source,
                               authority_rank=RANK)
    return observations + len(on), facts + (written is not None)


def _original(conn, *, org_id: str, source: str, thread_id: str | None, address: str,
              at: datetime | None, ours: Callable[[str], bool]) -> str | None:
    """The latest mail we sent in this thread, at or before the report, to `address` — or None."""
    if not thread_id:
        return None
    for row in conn.execute(_SENT_IN_THREAD, {"o": org_id, "s": source, "t": thread_id,
                                              "at": at}):
        if ours(row.sender or "") and address in {norm_email(r) for r in row.recipients or ()}:
            return row.event_id
    return None
