"""L2.3 · Cross Conversation — one authored message, many counterparties, one campaign.

**THE MISSING CORRELATOR.** The architecture names eight: Cross Tool, Cross Resource, Cross User,
Cross Timeline, Cross Conversation, Cross Domain, Cross Organization and Dependency. Four exist —
`correlation.py` carries the anchor/tool/user joins, and `correlation_resource`,
`correlation_timeline` and `correlation_dependency` are their own modules. Cross Conversation,
Cross Domain and Cross Organization have no code at all.

**WHY THIS ONE FIRST, measured rather than chosen.** On the pilot tenant, 11 August between 03:02
and 08:39, seventeen messages went to eighteen recipients — Peak XV (2), Afore (5), Titan, Neon,
Together, 3one4, Surge, Z Fellows, Antler, IIM-B — every one carrying the same sentence,
*"we can expect the numbers to hit nearly ~$2-3k MRR"*. That is one campaign. The system saw
eighteen unrelated threads.

`outreach_situations.read_outreach_cohorts` exists to answer *"of everyone I contacted about the
raise, who has gone quiet?"* and returned **zero findings** on that data, because it groups by
EMPLOYER: eleven investors at nine different firms never reach `_MIN_COHORT`. The grouping key was
the wrong one. A fundraise is not a company, it is a message.

**WHAT A CAMPAIGN IS HERE, and the definition is deliberately narrow.** One sentence we wrote,
sent to at least `MIN_RECIPIENTS` distinct counterparties, inside `WINDOW_HOURS`. All three
conditions, because each alone is wrong:

  * a shared sentence with no window merges this quarter's raise with last year's;
  * a window with no shared sentence merges a busy morning's unrelated mail;
  * a low recipient count makes every two-person thread a campaign.

**IT DOES NOT DEDUPLICATE THE SIGNALS.** Ten investors who each received the same pitch are ten
real conversations with ten real people, and `y-combinator-w27` retired a unit that would have
collapsed them — the recurrence was a campaign, not boilerplate, and deleting it would have
deleted the Peak XV, Titan and Afore intelligence. This module adds a GROUP over them; every
per-counterparty situation stays exactly as it was.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

#: How many distinct counterparties make a campaign rather than a conversation. Three is the
#: smallest number where "how is this OUTREACH going" is a different question from "what about
#: this person" — the same floor `read_outreach_cohorts` uses, kept identical on purpose so the
#: two readings cannot disagree about what a group is.
MIN_RECIPIENTS = 3

#: How far apart two sends may be and still be one campaign. A raise goes out in a morning; a
#: template reused three months later is a different attempt with different traction behind it.
WINDOW_HOURS = 36

#: Below this a "shared sentence" is a greeting, a signature or a subject fragment, and grouping on
#: it would merge everything the founder has ever written. The receipt floor in
#: `capture/semantic/evidence_binder` refuses those as evidence for the same reason.
MIN_SENTENCE_CHARS = 40

_WHITESPACE = re.compile(r"\s+")


def normalise_sentence(quote: str | None) -> str:
    """The grouping key. Whitespace-folded and lower-cased, nothing else.

    Deliberately not stemmed, tokenised or fuzzy-matched. Two sends are one campaign when the
    founder sent the SAME SENTENCE, and a similarity threshold here would quietly merge two
    different pitches on a bad day — the failure the eight-correlator design calls a wrongful
    merge, and the one nobody can debug from a stored score.
    """
    return _WHITESPACE.sub(" ", (quote or "").strip()).lower()


def campaign_id_for(*, org_id: str, sentence: str, opened_at: datetime) -> str:
    """A stable id for one campaign, so a re-run finds the same group rather than minting a new
    one. The day is part of the key, not the exact instant: a send at 08:39 and one at 03:02 on
    the same morning must land in one campaign, and two identical raises months apart must not."""
    digest = hashlib.sha256(
        f"{org_id}|{normalise_sentence(sentence)}|{opened_at.date().isoformat()}".encode()
    ).hexdigest()[:24]
    return f"campaign_{digest}"


@dataclass(frozen=True, slots=True)
class Campaign:
    """One authored message and everyone it went to."""

    campaign_id: str
    sentence: str
    first_sent: datetime
    last_sent: datetime
    #: Node ids, sorted. The counterparty nodes, never the events — a recipient who got two sends
    #: is one person in one campaign.
    recipients: tuple[str, ...]
    #: The events that carried it, sorted. Kept so a card can cite the actual messages.
    event_ids: tuple[str, ...]

    @property
    def size(self) -> int:
        return len(self.recipients)

    @property
    def span_hours(self) -> int:
        return max(0, int((self.last_sent - self.first_sent).total_seconds() // 3600))


#: Outbound events, the counterparty each went to, and the sentence each carried.
#:
#: `thread.last_outbound` is written onto the RECIPIENT's node every time we send, and
#: `graph_source_refs` maps that fact version back to the message — the same join the absence
#: receipt uses, and the one measured to resolve for every waiting counterparty on the pilot.
#: `qualified_signals.evidence_refs[0].quote` is the sentence L1 already extracted and verified;
#: this module never re-reads a body.
#: A THREAD RESOLVES TO THE PERSON ON IT. `waiting.py` writes `thread.last_outbound` onto BOTH the
#: thread node and the party who corresponded on it, so a naive read counts "Manik Pasricha" and
#: "Thread with manik@titancapital.vc" as two recipients. Run against the live tenant before this
#: coalesce existed, the 11 August raise reported FOURTEEN recipients for seven real people — a
#: campaign at twice its true size, which is worse than not finding it, because the number is what
#: the card would say. The same `corresponded_with` bridge `outreach_situations` uses.
#:
#: NO JSON OPERATORS. `evidence_refs` and `actor` come back RAW and are decoded in Python. `#>>`
#: is Postgres-only, and this module's first cut used it — every one of these tests failed on
#: SQLite with `unrecognized token: "#"`. The codebase already records the rule, in
#: `situation_bso._L1_BY_EVENT_SELECT`: *a query whose correctness can only be demonstrated
#: against production is a query nobody can hold to account.* Decoding in `_rows_to_campaigns`
#: also puts the sentence rule and the sender rule in the one pure function a reader can check.
_OUTBOUND_WITH_SENTENCE = (
    "select coalesce(party.from_node_id, f.subject_node_id) as node_id, "
    "       rn.canonical_key as recipient_key, "
    "       r.event_id as event_id, e.occurred_at as sent_at, "
    "       e.actor as actor, qs.evidence_refs as evidence_refs "
    "from graph_facts f "
    "join graph_source_refs r "
    "  on r.fact_version_id = f.fact_version_id and r.org_id = f.org_id "
    "join source_events e on e.event_id = r.event_id and e.org_id = r.org_id "
    "join qualified_signals qs on qs.event_id = r.event_id and qs.org_id = r.org_id "
    "left join graph_edges party "
    "  on party.org_id = f.org_id and party.to_node_id = f.subject_node_id "
    "  and party.edge_type = 'corresponded_with' and party.valid_to is null "
    "left join graph_nodes rn "
    "  on rn.org_id = f.org_id and rn.node_id = coalesce(party.from_node_id, f.subject_node_id) "
    "where f.org_id = :o and f.field = 'thread.last_outbound' and f.status = 'active' "
    "  and e.occurred_at >= :since "
    "order by e.occurred_at, node_id"
)


def _decode(value) -> object:
    """`jsonb` arrives decoded from Postgres and as text from a driver that has not decoded it."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def first_quote(evidence_refs) -> str:
    """The sentence L1 extracted and verified. This module never re-reads a message body."""
    refs = _decode(evidence_refs)
    if isinstance(refs, (list, tuple)):
        for ref in refs:
            if isinstance(ref, Mapping):
                quote = str(ref.get("quote") or "").strip()
                if quote:
                    return quote
    return ""


def sender_email(actor) -> str:
    """Who sent the message. A MESSAGE'S OWN SENDER IS NOT ONE OF ITS RECIPIENTS —
    `thread.last_outbound` is written on every participant node including ours, so the founder
    appeared inside his own campaign and inflated it by one on the live tenant. Compared against
    the EVENT's actor rather than a configured address, so it holds for a tenant with several
    sending seats and needs no caller to pass an identity it might get wrong."""
    decoded = _decode(actor)
    if isinstance(decoded, Mapping):
        return str(decoded.get("email") or "").strip().lower()
    return ""


def _rows_to_campaigns(rows: Sequence[Mapping], *, org_id: str) -> tuple[Campaign, ...]:
    """Group `(node, event, sent_at, quote)` rows into campaigns. Pure, so it is testable without
    a database and so the grouping rule can be read in one place."""
    buckets: dict[str, list[tuple[str, str, datetime]]] = {}
    sentences: dict[str, str] = {}
    for row in rows:
        quote = first_quote(row["evidence_refs"])
        key = normalise_sentence(quote)
        if len(key) < MIN_SENTENCE_CHARS:
            continue
        recipient = str(row["recipient_key"] or "").strip().lower()
        if recipient and recipient == sender_email(row["actor"]):
            continue
        sent_at = row["sent_at"]
        if sent_at is None:
            continue
        if isinstance(sent_at, str):
            try:
                sent_at = datetime.fromisoformat(sent_at)
            except ValueError:
                continue
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        buckets.setdefault(key, []).append(
            (str(row["node_id"]), str(row["event_id"]), sent_at))
        sentences.setdefault(key, quote.strip())

    out: list[Campaign] = []
    for key, entries in buckets.items():
        entries.sort(key=lambda item: item[2])
        # WINDOWED, NOT BUCKETED BY DAY. One sentence reused next quarter is a different campaign
        # with different traction behind it, and a calendar-day bucket would split a send that
        # crossed midnight while merging two attempts a fortnight apart that happened to share a
        # weekday. The run breaks when the gap from the run's FIRST send exceeds the window.
        run: list[tuple[str, str, datetime]] = []
        for entry in entries:
            if run and entry[2] - run[0][2] > timedelta(hours=WINDOW_HOURS):
                out.extend(_finish(run, sentences[key], org_id=org_id))
                run = []
            run.append(entry)
        out.extend(_finish(run, sentences[key], org_id=org_id))
    return tuple(sorted(out, key=lambda c: (-c.size, c.campaign_id)))


def _finish(run: Sequence[tuple[str, str, datetime]], sentence: str, *,
            org_id: str) -> tuple[Campaign, ...]:
    """One completed run → zero or one campaign. Zero when too few counterparties received it."""
    if not run:
        return ()
    recipients = {node for node, _event, _at in run}
    if len(recipients) < MIN_RECIPIENTS:
        return ()
    return (Campaign(
        campaign_id=campaign_id_for(org_id=org_id, sentence=sentence, opened_at=run[0][2]),
        sentence=sentence,
        first_sent=run[0][2],
        last_sent=run[-1][2],
        recipients=tuple(sorted(recipients)),
        event_ids=tuple(sorted({event for _node, event, _at in run})),
    ),)


def find_campaigns(conn, org_id: str, *, since: datetime) -> tuple[Campaign, ...]:
    """Every campaign this org sent after `since`, largest first.

    `since` is required and has no default: an unbounded read on a founder's mailbox is the query
    that makes a sweep unpredictable, and a caller choosing the window is a caller who knows which
    window their answer is about.
    """
    rows = conn.execute(text(_OUTBOUND_WITH_SENTENCE), {"o": org_id, "since": since}).mappings().all()
    return _rows_to_campaigns(rows, org_id=org_id)


__all__ = [
    "MIN_RECIPIENTS",
    "first_quote",
    "MIN_SENTENCE_CHARS",
    "WINDOW_HOURS",
    "Campaign",
    "campaign_id_for",
    "find_campaigns",
    "normalise_sentence",
]
