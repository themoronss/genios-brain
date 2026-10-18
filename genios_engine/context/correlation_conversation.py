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

**STEP-10 · A WAVE IS ONE OBJECT** (`yc2_w27_s10 · M29.C4.L-logic.V2.U01`). What was wrong, measured on
the golden set (`STEP-10` §8.1, F15): the founder sent one pitch to five funds, and memory held five
`awaiting_response` readings, five dormant fund situations, five open loops ~56 days old and ten
`analytic_movement` — and no campaign. `_OUTBOUND_WITH_SENTENCE` INNER-joins `qualified_signals`, and
the founder's own mail there published no qualified signal, so `find_campaigns` never saw the wave.

What is true now: `find_waves` returns every WAVE — one outreach that went to several outside people —
recognised two ways, in this order:
  (a) the same SENTENCE: `find_campaigns`' rule, unchanged, over what the caller's clock can see;
  (b) else, of the sends no sentence claimed, the same SUBJECT (case, whitespace and a leading
      `Re:`/`Fwd:` chain aside) sent by us within `WAVE_WINDOW_DAYS` of the wave's first send to
      `MIN_RECIPIENTS` or more OUTSIDE addresses — not us by `platform/self_identity`, never by a domain
      written here.
Each wave names who it went to, each once; who wrote to us after their send — the ledger's actor,
never the turn memory keeps, and never a responder, a mailing or spam (`workstreams.NEVER_A_FILE`, the
rule the connector's rate counts replies by); whose address carries `delivery.status = failed` from a
report at or after their send (`context/delivery`); whom we wrote to again after their first send; and
the days since its last send, on the caller's clock. The counts are `Measured` at basis "wave" and a
share is `rate_of` (`contracts/measured`). Nothing a seat captured privately, nothing after the clock.

WHERE THE SUBJECT COMES FROM, AND WHAT IT CANNOT SEE. No column holds a subject: the ledger keeps who
sent what to whom and when, the subject lives in the encrypted payload, and this module never decrypts
one. Layer 1 also writes it, masked, at the head of the prepared text — the subject, a blank line, then
the body (`capture/pipeline.capture_event`) — so the text before the first blank line IS the subject
whenever the mail had one, and only that text is used, never the body. Declared, not guessed: a mail
sent WITHOUT a subject reads its first paragraph as one (one paragraph alone reads none); an archived
mail keeps no prepared text (STEP-03), so it joins no subject wave; prepared text ages out at 180 days.
Exact for every case is Layer 1's to make: the subject (or its digest) kept on the ledger row, beside
`recipients`.

NOTHING READS A WAVE YET. `find_campaigns` and `Campaign` are byte-for-byte what they were, and so is
every card: a card for a wave is STEP-14's (`outreach_situations._gather` stamps campaigns only).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import bindparam, text

from genios_engine.context.delivery import FAILED as DELIVERY_FAILED
from genios_engine.context.delivery import FIELD as DELIVERY_FIELD
from genios_engine.context.workstreams import NEVER_A_FILE
from genios_engine.contracts.measured import Measured, count_of, rate_of
from genios_engine.platform.identity import norm_email
from genios_engine.platform.self_identity import SelfIdentity, identity_for

#: How many distinct counterparties make a campaign rather than a conversation. Three is the
#: smallest number where "how is this OUTREACH going" is a different question from "what about
#: this person" — the same floor `read_outreach_cohorts` uses, kept identical on purpose so the
#: two readings cannot disagree about what a group is.
MIN_RECIPIENTS = 3

#: How far apart two sends may be and still be one campaign. A raise goes out in a morning; a
#: template reused three months later is a different attempt with different traction behind it.
#:
#: A DEFAULT, NOT A LAW, and `find_campaigns` takes it as an argument for that reason. Thirty-six
#: hours is a founder's morning. A tenant whose outreach goes out over a working week would have
#: one campaign split into five here, each below `MIN_RECIPIENTS`, and would see nothing at all —
#: so the value has to be the caller's to choose. When a per-tenant source is needed,
#: `capture/esqe/qualification.org_qualification_floors` is the proven shape: a table, a
#: documented default for a tenant with no row, an owner, and an append-only change log.
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


def _rows_to_campaigns(rows: Sequence[Mapping], *, org_id: str,
                       window_hours: int = WINDOW_HOURS,
                       min_recipients: int = MIN_RECIPIENTS) -> tuple[Campaign, ...]:
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
            if run and entry[2] - run[0][2] > timedelta(hours=window_hours):
                out.extend(_finish(run, sentences[key], org_id=org_id,
                                   min_recipients=min_recipients))
                run = []
            run.append(entry)
        out.extend(_finish(run, sentences[key], org_id=org_id, min_recipients=min_recipients))
    return tuple(sorted(out, key=lambda c: (-c.size, c.campaign_id)))


def _finish(run: Sequence[tuple[str, str, datetime]], sentence: str, *,
            org_id: str, min_recipients: int = MIN_RECIPIENTS) -> tuple[Campaign, ...]:
    """One completed run → zero or one campaign. Zero when too few counterparties received it."""
    if not run:
        return ()
    recipients = {node for node, _event, _at in run}
    if len(recipients) < min_recipients:
        return ()
    return (Campaign(
        campaign_id=campaign_id_for(org_id=org_id, sentence=sentence, opened_at=run[0][2]),
        sentence=sentence,
        first_sent=run[0][2],
        last_sent=run[-1][2],
        recipients=tuple(sorted(recipients)),
        event_ids=tuple(sorted({event for _node, event, _at in run})),
    ),)


def outbound_with_sentences(conn, org_id: str, *, since: datetime) -> Sequence[Mapping]:
    """The raw outbound-with-sentence rows, for callers that group them differently.

    ONE SPELLING OF THE QUERY. `campaign_candidates` asks the same question of the same rows and
    reaches the opposite conclusion — it looks for sends this module DECLINED to group — so it
    must read exactly what this module read. A second copy of the join would drift, and the two
    passes would disagree about what the tenant even sent: this one carries the `corresponded_with`
    coalesce that stopped the 11 August raise reporting fourteen recipients for seven real people,
    the sender exclusion, and the no-JSON-operators rule that keeps it runnable on SQLite.
    """
    return conn.execute(text(_OUTBOUND_WITH_SENTENCE), {"o": org_id, "since": since}).mappings().all()


def find_campaigns(conn, org_id: str, *, since: datetime,
                   window_hours: int = WINDOW_HOURS,
                   min_recipients: int = MIN_RECIPIENTS) -> tuple[Campaign, ...]:
    """Every campaign this org sent after `since`, largest first.

    `since` is required and has no default: an unbounded read on a founder's mailbox is the query
    that makes a sweep unpredictable, and a caller choosing the window is a caller who knows which
    window their answer is about.
    """
    rows = outbound_with_sentences(conn, org_id, since=since)
    return _rows_to_campaigns(rows, org_id=org_id, window_hours=window_hours,
                              min_recipients=min_recipients)


# =================================================================================================
# STEP-10 · a wave is one object — with or without a qualified signal behind it.
# =================================================================================================

#: How far apart two sends of one SUBJECT may be and still be one wave, counted from the wave's FIRST
#: send, inclusive (`STEP-10` §8.4.5). Wider than `WINDOW_HOURS` because a founder's pitch goes out to
#: a list over days, not only in a morning; a fortnight on, the same subject is another attempt. A
#: DEFAULT, NOT A LAW, for the reason `WINDOW_HOURS` gives: `find_waves` takes it as an argument.
WAVE_WINDOW_DAYS = 7

#: The level a wave's numbers are measured at (`contracts/measured`).
WAVE_BASIS = "wave"

#: How a wave was recognised: by the sentence a qualified signal quoted, or by its subject.
BY_SENTENCE = "sentence"
BY_SUBJECT = "subject"

#: How much of the prepared text is read for the subject. A header line is at most 998 characters
#: (RFC 5322 §2.1.1), so the blank line after a subject falls inside this — a subject folded longer
#: than that reads as none. Only the text before that blank line is ever used.
_SUBJECT_HEAD_CHARS = 1000

#: A leading chain of reply and forward prefixes, however many and in any case: `Re:`, `Fwd:`, and
#: `Fw:`, which `capture/structural/threads` reads as a forward too.
_REPLY_CHAIN = re.compile(r"^(?:\s*(?:re|fwd?)\s*:)+", re.IGNORECASE)


def normalise_subject(subject: str | None) -> str:
    """The subject as a grouping key: whitespace-folded, lower-cased, a leading reply chain gone.

    Nothing more, for the reason `normalise_sentence` gives — a similarity threshold would merge two
    different pitches on a bad day. The chain goes because a follow-up under `Re:` is the same
    outreach, not a new subject.
    """
    folded = _WHITESPACE.sub(" ", (subject or "").strip())
    return _REPLY_CHAIN.sub("", folded).strip().lower()


def subject_of(prepared_head: str | None) -> str | None:
    """The subject Layer 1 wrote at the head of a mail's prepared text, whitespace-folded, or None.

    `capture/pipeline.capture_event` writes the subject, a blank line, then the body — the body alone
    when the mail had no subject — so the text before the first blank line is the subject, and with
    no blank line there is none to read. ⛔ A mail sent without a subject whose body has several
    paragraphs reads its first paragraph here: the prepared text does not say which it was (the
    module's note says what would make it exact).
    """
    head, blank, _body = str(prepared_head or "").partition("\n\n")
    subject = _WHITESPACE.sub(" ", head).strip()
    return subject if blank and subject else None


def wave_id_for(*, org_id: str, subject: str, opened_at: datetime) -> str:
    """A stable id for a wave recognised by its subject — `campaign_id_for`'s rule on the subject: a
    re-run finds the same wave, and the day it opened is part of the key. A wave recognised by its
    sentence keeps its campaign's id."""
    digest = hashlib.sha256(
        f"{org_id}|subject|{normalise_subject(subject)}|{opened_at.date().isoformat()}".encode()
    ).hexdigest()[:24]
    return f"wave_{digest}"


def _count(k: int) -> Measured:
    """How many — a count is what it counts, exact (`contracts/measured.count_of`)."""
    return count_of(k, basis=WAVE_BASIS)


@dataclass(frozen=True, slots=True)
class Wave:
    """One outreach that went to several outside people, and what came of it."""

    wave_id: str
    recognised_by: str                 # BY_SENTENCE | BY_SUBJECT
    #: What every send shared — the sentence, or the subject as first sent — whitespace-folded.
    line: str
    first_sent: datetime
    last_sent: datetime
    #: The outside addresses it went to, each once, sorted. Never one of us.
    recipients: tuple[str, ...]
    #: The sends, sorted — so a card can cite the messages.
    event_ids: tuple[str, ...]
    replied: tuple[str, ...]           # of them, who wrote to us after their send
    bounced: tuple[str, ...]           # whose address failed in a report at or after their send
    followed_up: tuple[str, ...]       # whom we wrote to again after their first send
    days_since_last_send: float        # on the caller's clock

    @property
    def sent(self) -> Measured:
        return _count(len(self.recipients))

    @property
    def reply_rate(self) -> Measured:
        return rate_of(len(self.replied), len(self.recipients), basis=WAVE_BASIS)

    @property
    def bounce_rate(self) -> Measured:
        return rate_of(len(self.bounced), len(self.recipients), basis=WAVE_BASIS)

    @property
    def follow_up_rate(self) -> Measured:
        return rate_of(len(self.followed_up), len(self.recipients), basis=WAVE_BASIS)


#: Every mail of the tenant from `since` to the caller's clock — who sent it, to whom, when — with the
#: head of its prepared text (the subject: `subject_of`) and whether memory filed it as a mailing, spam
#: or a responder. A wave's sends, the answers and the follow-ups are all in it; nothing a seat
#: captured privately is. NO JSON OPERATORS, for the reason `_OUTBOUND_WITH_SENTENCE` records: `actor`
#: and `recipients` come back raw and are read in Python.
_MAIL = (
    "select e.event_id as event_id, e.occurred_at as at, e.actor as actor, "
    "       e.recipients as recipients, substr(pc.clean_text, 1, :head) as head, "
    "       exists (select 1 from graph_observations ob "
    "                where ob.org_id = e.org_id and ob.created_by_event_id = e.event_id "
    "                  and ob.kind in :never) as noise "
    "from source_events e "
    "left join prepared_content pc on pc.org_id = e.org_id and pc.event_id = e.event_id "
    "where e.org_id = :o and e.object_type = 'email_message' "
    "  and e.occurred_at >= :since and e.occurred_at <= :now "
    "  and (e.visibility_scope is null or e.visibility_scope <> 'private') "
    "order by e.occurred_at, e.event_id"
)

#: Every report of a failed delivery, as the address it failed for and when the report came: the
#: `delivery.status = failed` fact `context/delivery` writes on the address, and EVERY report behind
#: it. A second report on an address writes the same value, which the store keeps as a corroborating
#: reference on the first one's fact (`graph_store.fact_write_action`: "noop") — so the fact's own
#: time is only the first report's, and a pitch that bounced after an older one did would read clean.
_FAILED_DELIVERIES = (
    "select n.canonical_key as address, f.value as value, e.occurred_at as at "
    "from graph_facts f "
    "join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
    "join graph_source_refs r on r.org_id = f.org_id and r.fact_version_id = f.fact_version_id "
    "join source_events e on e.org_id = r.org_id and e.event_id = r.event_id "
    "where f.org_id = :o and f.field = :field and f.status = 'active' and f.valid_to is null "
    "  and f.visibility_scope <> 'private' and e.occurred_at <= :now "
    "  and (e.visibility_scope is null or e.visibility_scope <> 'private')"
)


@dataclass(frozen=True, slots=True)
class _Mail:
    """One mail of the ledger, as the waves read it."""

    event_id: str
    at: datetime
    sender: str                        # the actor's address, normalised; "" when it has none
    to: tuple[str, ...]                # its outside recipients, normalised, each once
    subject: str | None                # Layer 1's subject (`subject_of`), or None
    noise: bool                        # memory filed it as a mailing, spam or a responder


def _aware(value) -> datetime | None:
    """A timestamp as an aware datetime — the coercion `_rows_to_campaigns` applies, for a driver
    that hands back text or a naive value."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _value(value) -> object:
    """A `jsonb` value: decoded by Postgres, JSON text from a driver that has not decoded it."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _read_mail(conn, org_id: str, *, since: datetime, now: datetime,
               us: SelfIdentity) -> list[_Mail]:
    statement = text(_MAIL).bindparams(bindparam("never", expanding=True))
    mail: list[_Mail] = []
    for row in conn.execute(statement, {"o": org_id, "since": since, "now": now,
                                        "head": _SUBJECT_HEAD_CHARS,
                                        "never": list(NEVER_A_FILE)}).mappings():
        at = _aware(row["at"])
        if at is None:
            continue
        listed = _decode(row["recipients"])
        to = {norm_email(a) for a in (listed if isinstance(listed, (list, tuple)) else ())}
        mail.append(_Mail(event_id=str(row["event_id"]), at=at,
                          sender=norm_email(sender_email(row["actor"])) or "",
                          to=tuple(sorted(a for a in to if a and not us.is_us(a))),
                          subject=subject_of(row["head"]), noise=bool(row["noise"])))
    return mail


def _read_failures(conn, org_id: str, *, now: datetime) -> dict[str, list[datetime]]:
    """address → when each report of a failed delivery to it came."""
    failed: dict[str, list[datetime]] = {}
    for row in conn.execute(text(_FAILED_DELIVERIES),
                            {"o": org_id, "field": DELIVERY_FIELD, "now": now}).mappings():
        address, at = norm_email(row["address"]), _aware(row["at"])
        if address and at is not None and _value(row["value"]) == DELIVERY_FAILED:
            failed.setdefault(address, []).append(at)
    return failed


def _first_sends(rows: Sequence[Mapping], campaign: Campaign,
                 us: SelfIdentity) -> dict[str, datetime]:
    """A campaign's outside recipients by ADDRESS, each with the first of its sends they received.
    A recipient node whose key is not an address — a thread the `corresponded_with` coalesce did not
    resolve to its person — is no address a wave went to."""
    events, nodes = set(campaign.event_ids), set(campaign.recipients)
    first: dict[str, datetime] = {}
    for row in rows:
        if str(row["event_id"]) not in events or str(row["node_id"]) not in nodes:
            continue
        address, at = norm_email(row["recipient_key"]), _aware(row["sent_at"])
        if address and at is not None and not us.is_us(address):
            if address not in first or at < first[address]:
                first[address] = at
    return first


def _waves(org_id: str, rows: Sequence[Mapping], campaigns: Sequence[Campaign],
           mail: Sequence[_Mail], failed: Mapping[str, Sequence[datetime]], *, us: SelfIdentity,
           now: datetime, window_days: int = WAVE_WINDOW_DAYS,
           min_recipients: int = MIN_RECIPIENTS) -> tuple[Wave, ...]:
    """Campaigns, the ledger's mail and the failed deliveries → every wave, largest first. Pure."""
    ours: list[_Mail] = []
    wrote: dict[str, list[datetime]] = {}          # whom we wrote to, when
    heard: dict[str, list[datetime]] = {}          # who wrote to us, when — themselves
    for m in mail:
        if us.is_us(m.sender):
            ours.append(m)
            for address in m.to:
                wrote.setdefault(address, []).append(m.at)
        elif m.sender and not m.noise:
            heard.setdefault(m.sender, []).append(m.at)

    def wave(wave_id: str, by: str, line: str, first: Mapping[str, datetime],
             event_ids: Sequence[str], first_sent: datetime, last_sent: datetime) -> Wave:
        recipients = tuple(sorted(first))
        return Wave(
            wave_id=wave_id, recognised_by=by, line=" ".join(line.split()),
            first_sent=first_sent, last_sent=last_sent, recipients=recipients,
            event_ids=tuple(sorted(set(event_ids))),
            replied=tuple(a for a in recipients if any(t > first[a] for t in heard.get(a, ()))),
            bounced=tuple(a for a in recipients if any(t >= first[a] for t in failed.get(a, ()))),
            followed_up=tuple(a for a in recipients
                              if any(t > first[a] for t in wrote.get(a, ()))),
            days_since_last_send=round((now - last_sent).total_seconds() / 86400, 1))

    found: list[Wave] = []
    # (a) THE SENTENCE FIRST — today's campaigns, each over its outside recipients. A campaign that
    # keeps fewer than the floor once our own addresses are set aside is no wave, and its sends are
    # left for the subject to recognise.
    claimed: set[str] = set()
    for campaign in campaigns:
        first = _first_sends(rows, campaign, us)
        if len(first) < min_recipients:
            continue
        claimed.update(campaign.event_ids)
        found.append(wave(campaign.campaign_id, BY_SENTENCE, campaign.sentence, first,
                          campaign.event_ids, campaign.first_sent, campaign.last_sent))

    # (b) ELSE THE SUBJECT — our sends no sentence claimed, grouped by subject, then windowed from
    # each run's FIRST send exactly as `_rows_to_campaigns` windows a sentence.
    by_subject: dict[str, list[_Mail]] = {}
    for m in ours:
        key = normalise_subject(m.subject)
        if key and m.to and m.event_id not in claimed:
            by_subject.setdefault(key, []).append(m)
    for sends in by_subject.values():
        sends.sort(key=lambda m: (m.at, m.event_id))
        runs: list[list[_Mail]] = [[]]
        for m in sends:
            if runs[-1] and m.at - runs[-1][0].at > timedelta(days=window_days):
                runs.append([])
            runs[-1].append(m)
        for run in runs:
            first = {}
            for m in run:                          # in time order: the first send is the earliest
                for address in m.to:
                    first.setdefault(address, m.at)
            if len(first) < min_recipients:
                continue
            opened = run[0]
            found.append(wave(wave_id_for(org_id=org_id, subject=opened.subject or "",
                                          opened_at=opened.at),
                              BY_SUBJECT, opened.subject or "", first,
                              [m.event_id for m in run], opened.at, run[-1].at))
    return tuple(sorted(found, key=lambda w: (-len(w.recipients), w.wave_id)))


def find_waves(conn, org_id: str, *, since: datetime, now: datetime,
               us: SelfIdentity | None = None, window_days: int = WAVE_WINDOW_DAYS,
               min_recipients: int = MIN_RECIPIENTS) -> tuple[Wave, ...]:
    """Every wave this org sent from `since`, as a sweep at `now` sees it, largest first.

    Both bounds are the caller's and have no default: `since` for the reason `find_campaigns` gives,
    and `now` because it is the SWEEP's clock — a replay sees what the sweep it replays could have
    seen, never what came after. `us` is who is us, read here unless the caller already holds it.
    """
    us = us if us is not None else identity_for(conn, org_id)
    rows = [row for row in outbound_with_sentences(conn, org_id, since=since)
            if (_aware(row["sent_at"]) or now) <= now]
    campaigns = _rows_to_campaigns(rows, org_id=org_id, min_recipients=min_recipients)
    return _waves(org_id, rows, campaigns, _read_mail(conn, org_id, since=since, now=now, us=us),
                  _read_failures(conn, org_id, now=now), us=us, now=now,
                  window_days=window_days, min_recipients=min_recipients)


__all__ = [
    "BY_SENTENCE",
    "BY_SUBJECT",
    "MIN_RECIPIENTS",
    "first_quote",
    "MIN_SENTENCE_CHARS",
    "WAVE_BASIS",
    "WAVE_WINDOW_DAYS",
    "WINDOW_HOURS",
    "Campaign",
    "Wave",
    "campaign_id_for",
    "find_campaigns",
    "find_waves",
    "normalise_sentence",
    "normalise_subject",
    "outbound_with_sentences",
    "sender_email",
    "subject_of",
    "wave_id_for",
]
