from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import bindparam, text
from types import SimpleNamespace

from genios_engine.contracts.abstention import Level as _ABSTENTION
from genios_engine.contracts.abstention import VALID_LEVELS as _ABSTENTION_LEVELS
from .bands import band
from .router import co_recipients_for, resolve_assignee
from .slots import _fval, compute_slots

# E0 · Card Builder (§5.10). Compose the card.v1 draft deterministically from a signal + play +
# template — NO LLM here (that is E1). Attaches band (E2), owner (E3), the evidence chain (≥2,
# Law 2), on-device context_tags, the four actions, and +7d expiry. Returns a draft the renderer
# fills and the store persists.

#: The composition identity of a built card. BUMP THIS whenever what a card can SAY changes —
#: the slot vocabulary, the render prompt, the evidence or clarity gates, the authored copy path.
#:
#: `cards_one_per_signal` means the first card built for a signal was, until now, the last. Every
#: improvement upstream of delivery landed on an empty set: the cards a tenant actually looks at
#: already existed and were never recomposed. Stamping the builder lets `CardStore.claim_build`
#: reclaim a stale-but-untouched card and rewrite it in place, so a fix is visible on the queue a
#: user is already looking at rather than only on signals nobody has seen yet.
#:
#: The value is a NAME, not a hash of this file: a comment edit must not invalidate every card in
#: production, and deciding that a change is user-visible is a judgment the author makes.
# Seven stored campaign recipients now render as 7/7 and keep their verified quote outside
# the prose budget. v4 cards otherwise block a build claim and retain the old copy forever.
BUILDER_VERSION = "card-builder.v5-evidence-backed-copy"

EXPIRY_DAYS = 3650      # effectively "never" — a card only leaves the queue via user action
                        # (do_it_myself/snooze/dismiss) or a genuine decision_expires_at deadline,
                        # never a fixed housekeeping timer

# field prefix → the surface that produced it (for the evidence chain's `source`)
_SOURCE = {"deal": "crm", "thread": "gmail", "commitment": "gmail", "meeting": "calendar"}
# real connector source (graph_source_refs.source) → app tag. NOT field-name-based: there is no
# "deal" entry here on purpose. A "deal.*" field is just a field name — the L2 extractor writes it
# from whatever it was reading (usually a Gmail email), and only source_refs.source knows the truth.
_SOURCE_APP = {"gmail": "app:gmail", "gcal": "app:googlecalendar", "calendar": "app:googlecalendar",
               "notion": "app:notion", "drive": "app:googledrive", "hubspot": "app:hubspot"}


#: A card's level is what it CLAIMS: an instruction, a warning, or an explicit refusal to advise.
#: Sourced from `contracts/abstention.py` so the vocabulary cannot fork — the reasoner, the card
#: and the delivery gate must agree on what "the system is not telling you what to do" looks like.
VALID_LEVELS = _ABSTENTION_LEVELS


#: Observation kinds that mean the counterparty asked for SOMETHING. Without one of these we know
#: they wrote and that the ball is on us — but not what response they need, which is the whole
#: content of the instruction "reply now".
_ASK_SIGNALS: frozenset[str] = frozenset({
    "question", "meeting_request", "proposal_sent", "demo_requested",
    "contract_requested", "objection", "next_step_agreed",
})

#: reason_code -> (the fact or observation that makes its imperative meaningful, what is missing,
#: what a human should do instead). A card may carry a confident imperative ONLY when the
#: decisive context for its own type is grounded.
_CLARITY_REQUIREMENT: dict[str, tuple[str, str, str]] = {
    "unanswered_email": (
        "obs:ask",
        "what response they need",
        "Open the email to see what they are actually asking before replying."),
    "commitment_overdue": (
        "fact:commitment.action",
        "the promised outcome",
        "Open the source thread to verify what you committed to before acting."),
    "meeting_no_followup": (
        "fact:meeting.description",
        "what to recap",
        "Open the calendar event to see what was discussed before sending a recap."),
}


#: Situations whose finding is that the counterparty said nothing, so OUR OWN last message is
#: what grounds the card. Keyed on reason code rather than inferred, for the same reason
#: `states_absence` is declared rather than sniffed from the prose: a card's authority must not
#: depend on how a sentence happened to come out.
#:
#: `states_absence` is deliberately NOT reused here — it means "a gap in OUR RECORDS", and a
#: 34-day silence is not a gap in our records. It is a fact about the world that we know exactly.
_GROUNDED_BY_OUR_OWN_WORDS: frozenset[str] = frozenset({
    "awaiting_response",        # admin, the compiled lane
    "first_touch_unanswered",   # sales, a first approach nobody answered
    "outbound_prospect",        # sales, a whole sequence that produced nothing
    "cohort_outreach_gap",      # the campaign reading over the same silence
})


def clarity_verdict(reason_code: str | None, obs_kinds: set[str],
                    fact_fields: set[str]) -> tuple[bool, str, str]:
    """Is this card's imperative grounded? Returns (ok, what_is_missing, what_to_do_instead).

    This logic already existed and was correct — and it ran in a read projection on a single
    endpoint, `GET /cards/{card_id}`, where it ADDED a sibling field rather than changing
    anything. The list view, which is the surface a user actually scans, applied no gate at all,
    so "Reply to boardy@boardy.ai now" was shown as a confident instruction while the detail view
    of the same card knew the ask was unknown.

    Deciding at BUILD time is what makes the verdict real: the card is written as an observation,
    with a non-imperative headline and no action button, so every reader sees the same thing.
    """
    requirement = _CLARITY_REQUIREMENT.get(str(reason_code or ""))
    if requirement is None:
        return True, "", ""
    needed, missing, recommended = requirement
    kind, _, name = needed.partition(":")
    grounded = bool(obs_kinds & _ASK_SIGNALS) if kind == "obs" else name in fact_fields
    return grounded, ("" if grounded else missing), ("" if grounded else recommended)


def _int_fact(facts: dict, field: str) -> int | None:
    """A count off the graph as a whole number, or None. `graph_facts` stores numbers as JSON, so
    the same count arrives as `3`, `3.0` or `"3"` depending on which writer produced it."""
    value = _fval(facts, field)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _why_now(reason_code: str | None, facts: dict, slots: dict, eval_time) -> str | None:
    """What CHANGED to make this actionable — never elapsed time on its own.

    "It has been 9 days" is not a reason; it is a measurement, and presenting it as a reason is
    what manufactured urgency on threads where nothing had happened. A real why-now names the
    event: they asked something, a promise came due, a meeting ended.
    """
    days = slots.get("days")
    if reason_code == "commitment_overdue":
        action = _fval(facts, "commitment.action")
        return f"A promise came due{f': {action}' if action else ''}"
    if reason_code == "meeting_no_followup":
        title = _fval(facts, "meeting.title")
        return f"A meeting ended with no follow-up{f': {title}' if title else ''}"
    if reason_code == "unanswered_email":
        # Only a real ask makes this a why-now. Without one the clarity gate has already
        # downgraded the card, and inventing a reason here would undo that.
        return ("They are waiting on a reply"
                if isinstance(days, int) else None)
    # THE STATE READINGS. Their reason_code is their situation type, and each has a genuine event
    # behind it — a chase that has already been tried and not worked, a date that passed, a
    # meeting that ended. Without an entry here the richest cards in the system carried a NULL
    # why_now while the weakest legacy ones carried a sentence.
    if reason_code == "awaiting_response":
        # The count is the event, not the wait: a thread nobody has chased and a thread chased
        # twice are the same elapsed time and opposite instructions. Silent on the count we could
        # not compute, rather than reaching for the duration as a stand-in.
        chased = slots.get("follow_ups")
        if not isinstance(chased, int):
            return None
        if chased == 0:
            return "They have not been chased once since we wrote"
        return (f"Already chased {chased} time{'s' if chased != 1 else ''} with no reply — "
                "another reminder is unlikely to be what changes this")
    if reason_code == "commitment_overdue":
        return None      # handled above; kept explicit so the two never diverge silently
    if reason_code == "cohort_outreach_gap":
        # THE UNTOUCHED GROUP IS THE EVENT. Not the size of the campaign and not how long it has
        # run — those are measurements, and this function exists to refuse measurements dressed as
        # reasons. People nobody has followed up is a thing that is true and can be changed today.
        never = _int_fact(facts, "cohort.never_chased")
        if never:
            return (f"{never} in this campaign have never been followed up")
        chased = _int_fact(facts, "cohort.chased_twice_plus")
        if chased:
            return (f"{chased} have been chased twice or more with no reply — "
                    "reminders have stopped working here")
        return None
    if reason_code == "meeting_follow_through":
        title = _fval(facts, "meeting.title")
        return (f"A meeting ended and no follow-through is visible"
                f"{f': {title}' if title else ''}")
    return None


def _play_window(effective: dict, play_id: str | None) -> int | None:
    play = (effective.get("plays") or {}).get(str(play_id or ""), {})
    window = play.get("window_days")
    return int(window) if isinstance(window, int) else None


def _play_success(effective: dict, play_id: str | None) -> str | None:
    play = (effective.get("plays") or {}).get(str(play_id or ""), {})
    return play.get("success_signal") or None


def _require_level(signal: dict) -> str:
    """The signal's own level, or refuse to build the card.

    Silently defaulting is how the level literal in ``deliver/pipeline.py`` survived: every card
    carried `prescriptive`, so `select count(distinct level) from cards` returned 1 and the
    hardcoding was invisible from the data. A missing level is a broken producer, not a card
    that should ship as a command — the default that "feels safe" is the one that instructs.
    """
    level = (signal.get("level") or "").strip()
    if level not in VALID_LEVELS:
        raise ValueError(
            f"signal {signal.get('signal_id')!r} carries level {level!r}; expected one of "
            f"{sorted(VALID_LEVELS)}. A card must not infer its own authority.")
    return level


def _group_memberships(store, org_id: str, node_id: str) -> dict[str, str]:
    """THE FIRM A PERSON BELONGS TO IS A SLICE OF THE BUSINESS TOO.

    A responsibility is declared over `client = Peak XV`; the situation anchors on the partner,
    and the fund is one `works_at` edge away — on the anchor's facts it is nowhere. Each
    declared grouping (`context/groupings/*.yaml`, the same files the organisation reading
    uses) contributes `{edge_type: group display name}`, which `scope_pairs` reads like any
    attribute. Fails to `{}`: a graph that cannot be read leaves routing exactly as it was.
    """
    try:
        from genios_engine.context.correlation_organization import load_groupings
        edge_types = sorted({g.edge_type for g in load_groupings()})
        if not edge_types:
            return {}
        with store.engine.connect() as c:
            rows = c.execute(text(
                "select e.edge_type, g.display_name from graph_edges e "
                "join graph_nodes g on g.org_id=e.org_id and g.node_id=e.to_node_id "
                "and g.valid_to is null "
                "where e.org_id=:o and e.from_node_id=:n and e.valid_to is null "
                "and e.edge_type = any(:types) order by e.edge_type, g.display_name"),
                {"o": org_id, "n": node_id, "types": edge_types}).all()
    except Exception:      # noqa: BLE001 — see the docstring
        return {}
    out: dict[str, str] = {}
    for r in rows:
        if r.display_name and r.edge_type not in out:
            out[str(r.edge_type)] = str(r.display_name)
    return out


def load_node(store, org_id: str, node_id: str) -> tuple[str, str, dict, dict]:
    """(display_name, node_type, attributes, facts{field:{value,confidence,authority_rank}})."""
    with store.engine.connect() as c:
        nd = c.execute(text("select node_type, display_name, attributes from graph_nodes "
                            "where org_id=:o and node_id=:n and valid_to is null limit 1"),
                       {"o": org_id, "n": node_id}).first()
        facts: dict = {}
        for r in c.execute(text(
                "select field, value, confidence, authority_rank from graph_facts "
                "where org_id=:o and subject_node_id=:n and valid_to is null and status='active'"),
                {"o": org_id, "n": node_id}):
            v = r.value
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except (ValueError, TypeError):
                    pass
            facts[r.field] = {"value": v, "confidence": float(r.confidence),
                              "authority_rank": r.authority_rank}
    if nd is None:
        return "this account", "unknown", {}, facts
    attrs = nd.attributes if isinstance(nd.attributes, dict) else json.loads(nd.attributes or "{}")
    return (nd.display_name or "this account"), nd.node_type, attrs, facts


#: Observation kinds that record only that a NAME occurred, not that anything was SAID. Measured
#: on the design partner's org: `mention:person` averages 31 characters ("Boardy Boardman"),
#: `mention:company` 36 ("pablo@yappjam.com"), `mention:entity` 37 — and `email_relevance` plus the
#: `email_noise:*` kinds carry no text at all (0 of 121 rows had one). A card whose only quote is
#: somebody's name still cannot say what that person asked, which is the whole point of holding a
#: quote. Keyed on the KIND, which the extractor types, rather than on how long the text is or what
#: it looks like — the same reason `states_absence` is declared rather than sniffed from the prose.
_NAMING_ONLY_KINDS: frozenset[str] = frozenset({
    "mention:person", "mention:company", "mention:entity", "email_relevance",
})


def quotable(quotes: list[dict]) -> list[dict]:
    """The quotes that let a card say WHAT WAS ASKED: the counterparty's own words, with content.

    Two filters, and both are about honesty rather than taste. `from_counterparty` because 161 of
    the 526 observations on the design partner's org were minted from the FOUNDER'S OWN outgoing
    mail — quoting those back as "what they asked" attributes our words to them. And
    `_NAMING_ONLY_KINDS` because an extracted name is not a statement.
    """
    return [q for q in (quotes or ())
            if q.get("from_counterparty") is True
            and str(q.get("kind") or "") not in _NAMING_ONLY_KINDS
            and str(q.get("quote") or "").strip()]


#: Every observation is minted onto a PERSON node — 512 of 526 on the design partner's org, the
#: other 14 onto a service, and NEVER onto a thread or a company. This loader asked for
#: `subject_node_id = <the card's own node>`; 38 of the 55 live cards are keyed on a company or a
#: thread, so for every one of them the join returned ZERO ROWS. Not evidence with empty text — no
#: rows at all. That is the whole reason 48 of 55 cards had nothing to quote, and it is why the
#: renderer wrote from about five typed scalars: there was no content in the prompt because the
#: query could not reach any.
#:
#: So the subject is resolved to its observations by NODE TYPE, along links the graph already
#: records, and each lane is scoped as tightly as the graph allows:
#:
#:   thread  → observations minted from events in THAT EXACT THREAD
#:             (`source_events.parent_object_id` is the Gmail thread id the node is keyed on).
#:             Not "the people on the thread", which would let a card about one conversation quote
#:             a sentence from a different one.
#:   company → observations of the people who `works_at` it. Broader by nature, and honest at that
#:             width: the card names the company, and these are its people.
#:   person  → its own, which is what already worked for 7 of 55.
#:   outreach/     → the counterparty they `concerns`. These anchors are MINTED by
#:   commitment/     `context/outreach_situations.py` — they are not people, they are readings
#:   cohort          about a person — so they carry no observations of their own and this query
#:                   returned zero rows for every one of them. On the design partner's org that
#:                   was 43 outreach anchors, and it is why 19 live cards abstained with
#:                   "nothing this account said is on record": the words existed, one edge away,
#:                   on the person the reading is about.
#:
#:                   Scoped through `concerns` specifically, which is the edge those readings
#:                   write and the same hop `build_context_slice` and the neighbourhood walk
#:                   already take. It widens nothing: a reading about one person quotes that one
#:                   person.
_QUOTES_SQL = """
with subject as (
    select node_id, node_type, canonical_key
      from graph_nodes
     where org_id = :o and node_id = :n and valid_to is null
), reachable as (
    select o.observation_id
      from graph_observations o join subject s on o.subject_node_id = s.node_id
     where o.org_id = :o
    union
    select o.observation_id
      from graph_observations o
      join source_events se on se.event_id = o.created_by_event_id
      join subject s on s.node_type = 'thread'
                    and ('thread:' || se.parent_object_id) = s.canonical_key
     where o.org_id = :o and se.org_id = :o
    union
    select o.observation_id
      from graph_observations o
      join graph_edges e on e.from_node_id = o.subject_node_id
      join subject s on s.node_type = 'company' and e.to_node_id = s.node_id
     where o.org_id = :o and e.org_id = :o
       and e.valid_to is null and e.edge_type = 'works_at'
    union
    select o.observation_id
      from graph_observations o
      join graph_edges e on e.to_node_id = o.subject_node_id
      join subject s on e.from_node_id = s.node_id
     where o.org_id = :o and e.org_id = :o
       and e.valid_to is null and e.edge_type = 'concerns'
)
select o.kind, o.occurred_at, sr.evidence, sr.event_id, se.actor ->> 'email' as author,
       se.visibility_scope, se.visibility_principals
  from graph_observations o
  join graph_source_refs sr on sr.observation_id = o.observation_id and sr.org_id=o.org_id
  left join source_events se on se.event_id = sr.event_id and se.org_id=sr.org_id
 where o.org_id = :o and o.status = 'active'
   and o.kind not like 'email_noise%'
   and o.kind != 'event_presence'
   and o.observation_id in (select observation_id from reachable)
 order by o.occurred_at desc nulls last
 limit :lim
"""


def _quote_source_texts(conn, org_id: str, event_ids) -> dict[str, str]:
    """Reverify retained bytes; unavailable retention never removes the old quote path."""
    try:
        with conn.begin_nested():
            rows = conn.execute(text(
                "select event_id,clean_text from prepared_content "
                "where org_id=:org and event_id in :events"
            ).bindparams(bindparam("events", expanding=True)),
                {"org": org_id, "events": sorted(set(event_ids))}).all()
        return {str(r.event_id): str(r.clean_text or "") for r in rows}
    except Exception:  # noqa: BLE001 — optional verification cannot erase existing evidence
        return {}


def _campaign_quote_rows(conn, org_id: str, node_id: str, limit: int):
    """A campaign's 12 measured facts had zero refs; now read their newly retained origins.

    Presence observations deliberately do not copy the sender's words. The campaign's exact
    authored quote therefore comes from its own fact, with the event ref supplying speaker/ACL.
    """
    try:
        with conn.begin_nested():
            # All member events support campaign counts, but only the event that actually
            # contains this quote supplies its speaker/ACL. Match BEFORE LIMIT: ten newer
            # nonmatching members otherwise hide the one genuine source (SQLite regression).
            literal = ("json_extract(f.value, '$')" if conn.dialect.name == "sqlite"
                       else "(f.value #>> '{}')")
            rows = conn.execute(text(
                "select f.value as quote, r.event_id, se.occurred_at, "
                "se.actor ->> 'email' as author, se.visibility_scope, se.visibility_principals "
                "from graph_facts f join graph_source_refs r "
                "on r.org_id=f.org_id and r.fact_version_id=f.fact_version_id "
                "join source_events se on se.org_id=r.org_id and se.event_id=r.event_id "
                "join prepared_content pc on pc.org_id=r.org_id and pc.event_id=r.event_id "
                "where f.org_id=:org and f.subject_node_id=:node and f.field='campaign.quote' "
                "and f.status='active' and f.valid_to is null "
                f"and length({literal})>0 and replace(pc.clean_text,{literal},'')!=pc.clean_text "
                "order by se.occurred_at desc, r.event_id limit :lim"),
                {"org": org_id, "node": node_id, "lim": limit}).mappings().all()
        out = []
        for row in rows:
            quote = row["quote"]
            if isinstance(quote, str):
                try:
                    quote = json.loads(quote)
                except ValueError:
                    pass
            if isinstance(quote, str) and quote.strip():
                out.append(SimpleNamespace(kind="campaign_message", evidence={"text": quote},
                    **{k: v for k, v in row.items() if k != "quote"}))
        return out
    except Exception:  # noqa: BLE001 — derived receipts supplement, never replace, legacy quotes
        return []


def load_evidence_quotes(store, org_id: str, node_id: str, limit: int = 8,
                         identities: tuple[str, ...] = ()) -> list[dict]:
    """The counterparty's OWN WORDS, the human name behind the address, and WHO SAID IT.

    The renderer's entire world was `graph_nodes` + `graph_facts` — two queries, about five typed
    key/value pairs — and it was then asked to write a thread-specific reply. The substance a
    person would use sits one join away: `graph_source_refs.evidence` holds the exact quoted
    sentence each observation was extracted from, and a `mention:person` observation holds the real
    name for an address the node is keyed on.

    `author` is the third thing, and it is what makes a quote safe to print. The evidence table
    says what was said and never who said it, so the founder's own outgoing sentences — 161 of 526
    here — were indistinguishable from the counterparty's. `source_events.actor` knows, and every
    one of the 526 observations joins to its event, so the attribution costs nothing.

    Newest first, and bounded — the point is a handful of load-bearing quotes, not the whole
    thread.
    """
    mine = {str(i).strip().lower() for i in identities if "@" in str(i)}
    try:
        with store.engine.connect() as c:
            rows = c.execute(text(_QUOTES_SQL),
                             {"o": org_id, "n": node_id, "lim": limit}).fetchall()
            rows = (_campaign_quote_rows(c, org_id, node_id, limit) + list(rows))[:limit]
            source_texts = _quote_source_texts(c, org_id,
                [r.event_id for r in rows if getattr(r, "event_id", None)])
    except Exception:      # noqa: BLE001 — richer context is an enrichment, never a hard failure
        return []
    out: list[dict] = []
    for r in rows:
        ev = r.evidence
        if isinstance(ev, str):
            try:
                ev = json.loads(ev)
            except ValueError:
                ev = {}
        ev = ev if isinstance(ev, dict) else {}
        quote = str(ev.get("text") or "")
        if not quote.strip():
            continue
        event_id = getattr(r, "event_id", None)
        verified = bool(event_id and quote in source_texts.get(event_id, ""))
        author = str(r.author or "").strip().lower() or None
        # THE EVIDENCE'S OWN AUDIENCE, carried with the quote.
        #
        # `capture/visibility_rules.py:78` gives EVERY communication source
        # `scope=PARTICIPANTS` with the real addresses on it, and `contracts/visibility.py`
        # exists to answer "may this viewer see anything derived from this evidence". This
        # query asked neither question: it lifted the verbatim sentence for anything reachable
        # from the anchor and handed it to whoever the card was routed to.
        #
        # `deliver/audience.resolve_recipient` was written for exactly this and has NO
        # production caller — its one caller is `outbox.shadow_resolve_v2`, which sends nothing
        # and stubs the predicate to `lambda _seat: True` with the comment "Org-scope default
        # until card rows carry the evidence ACL". This is the card row carrying it.
        #
        # A PRE-0067 ROW HAS NO SCOPE and reads as org-visible. That is deliberate: those events
        # were captured before the column existed, the tenant has been seeing them all along,
        # and retroactively hiding them would be a behaviour change dressed as a fix. New
        # capture always writes a scope.
        raw_principals = getattr(r, "visibility_principals", None) or ()
        if isinstance(raw_principals, str):
            try:
                raw_principals = json.loads(raw_principals)
            except ValueError:
                raw_principals = ()
        principals = tuple(str(x).strip().lower()
                           for x in raw_principals
                           if str(x).strip())
        # The old loader cut every quote at 300 bytes before the renderer could protect it.
        # Full source-verified text earns the evidence allowance; legacy unknowns keep the cap.
        out.append({"kind": r.kind, "quote": quote if verified else quote.strip()[:300],
                    "event_id": event_id, "source_verified": verified,
                    "visibility_scope": (str(getattr(r, "visibility_scope", "") or "").strip()
                                         .lower() or None),
                    "visibility_principals": principals,
                    "name": str(ev.get("name") or "").strip() or None,
                    "author": author,
                    # Tri-state on purpose. False = we know we wrote it; None = the event that
                    # minted it is gone, so nobody can say whose words these are, and a card must
                    # not claim them as the counterparty's on a guess.
                    "from_counterparty": (None if author is None else author not in mine),
                    "occurred_at": (r.occurred_at.isoformat() if hasattr(r.occurred_at, "isoformat")
                                    else str(r.occurred_at) if r.occurred_at else None)})
    return out


def _visible_quotes(quotes, seat_id, *, store, org_id: str) -> list[dict]:
    """Only the quotes this card's recipient is allowed to have derived from.

    THE LEAK THIS CLOSES. `capture/visibility_rules` marks every mail, chat, meeting and
    calendar event `PARTICIPANTS` with the real addresses on it. `_QUOTES_SQL` lifted the
    verbatim sentence with no filter, `enqueue_pending` wrote `seat = r.assignee`, and
    `resolve_owner` rule 3 makes that `admins[0]` for every unowned card — which is currently
    almost every card. So on a multi-seat tenant an admin who was never on the thread received,
    in the card body, sentences quoted out of it.

    ORG SCOPE STILL MEANS ORG. A source the tenant handed its own system deliberately — an
    upload, a CRM row — is `ORG`, and every seat may see it. Only PARTICIPANTS narrows, and it
    narrows to the addresses actually on the exchange.

    AN UNROUTED CARD KEEPS ITS QUOTES. `seat_id` is None when the card is going to the admin
    QUEUE rather than to a named person, and that queue is read by whoever runs the account.
    Dropping every participants-scoped quote there would silently gut the admin view; the honest
    boundary for a queue is the tenant, which `org_id` already enforces. What this stops is the
    narrower and worse case: a card ADDRESSED to a named seat who was not a participant.

    FAILS OPEN ON A LOOKUP ERROR, deliberately and narrowly: if the seat's address cannot be
    read, the quotes are kept. A card that silently loses its evidence looks identical to a
    situation with none, and this function must not be able to blank a card because a directory
    query timed out. The tenant boundary is not what is failing open here — `org_id` is enforced
    in the query itself.
    """
    rows = list(quotes or ())
    if not rows or not seat_id:
        return rows
    try:
        from sqlalchemy import text as _text

        with store.engine.connect() as c:
            email = c.execute(_text(
                "select email from org_seats where org_id = :o and seat_id = :s"),
                {"o": org_id, "s": seat_id}).scalar()
    except Exception:      # noqa: BLE001 — see FAILS OPEN above
        return rows
    viewer = str(email or "").strip().lower() or None

    kept: list[dict] = []
    for quote in rows:
        scope = quote.get("visibility_scope")
        if scope != "participants":
            kept.append(quote)                      # org, public, or pre-0067
            continue
        # NORMALISED AT THE COMPARISON, not only at the loader. `load_evidence_quotes` already
        # lowercases and strips, and relying on that would make this check depend on every
        # future producer of a quote dict remembering to. A comparison that fails silently
        # because somebody upstream skipped a `.lower()` is a leak reopening with no test going
        # red — and on this predicate the cost of being wrong is somebody reading a thread they
        # were not on.
        allowed = {str(x).strip().lower()
                   for x in (quote.get("visibility_principals") or ()) if str(x).strip()}
        if viewer and viewer in allowed:
            kept.append(quote)
    return kept


def resolved_person_name(quotes: list[dict], fallback: str) -> str:
    """The human name for a node keyed on an email address.

    35 of 38 person cards named an address in the headline. The real name was already extracted —
    a `mention:person` observation carries `{"name": "Maria Exconde"}` — but the node's
    display_name stayed the address, so the headline spent its 60-character budget on
    "maria@alystventures.com" and the invention guard rejected any draft that wrote "Maria".
    """
    for q in quotes:
        if q.get("kind") == "mention:person" and q.get("name"):
            return q["name"]
    return fallback


def _real_sources(store, org_id: str, node_id: str) -> set[str]:
    """The TRUE app(s) behind this node's current facts, via graph_source_refs — never guessed from
    a field-name prefix. Fixes the bug where an LLM-extracted "deal.*" field from a Gmail email got
    tagged app:hubspot purely because its field name started with "deal.", regardless of the fact's
    actual (correctly-recorded) source."""
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select distinct sr.source from graph_facts f "
            "join graph_source_refs sr on sr.fact_version_id = f.fact_version_id "
            "where f.org_id=:o and f.subject_node_id=:n and f.valid_to is null and f.status='active'"),
            {"o": org_id, "n": node_id}).fetchall()
    return {r.source for r in rows if r.source}


#: Situations whose own status says the work is finished. Not a guess about relevance — the value
#: is written by the extractor from what the counterparty actually said.
_SETTLED_STATUSES = frozenset({"rejected", "lost", "won", "closed", "churned", "declined"})


def states_absence(template: dict | None) -> bool:
    """Does this situation's authored copy describe a GAP IN OUR RECORDS rather than a finding?

    Declared by the situation author in `render.fallback.states_absence` and carried on the
    audited capability snapshot, so the answer is pinned to the capability version that wrote the
    card and cannot drift under it. Read here rather than inferred from the prose, because
    inferring it means regex-matching a sentence the model may word any number of ways, and a
    card's authority must not depend on how a sentence happened to come out.
    """
    return bool(((template or {}).get("fallback") or {}).get("states_absence"))


def _surfaces(facts: dict, signal: dict, actions: list, *, has_finding: bool = True) -> list[str]:
    """Which surfaces this card is valid on.

    Four surfaces ask four different questions and were being served one answer. The app asks
    "what should I do right now"; the agent asks "what should I execute"; Ask and the API ask
    "tell me what you know". A rejected deal with zero momentum past its deadline answers the last
    two perfectly and the first two not at all — and it was appearing in the app's open-loop count,
    where the only honest measure is whether a person acts on every card he reads.

    So `ask` and `api` are unconditional: withholding a closed deal from someone who asked about it
    is that surface's failure mode. `app` and `agent` are earned. A card that reaches neither is
    not discarded — it is history, and history has two surfaces of its own.

    `has_finding` is false for two different failures and both end here: the situation is defined
    by a gap in OUR RECORDS (`states_absence`), or the card cannot quote one thing the counterparty
    said (`quotable`). Different causes, identical consequence — neither can answer "what should I
    do right now", and both answer "what is happening here" perfectly well.

    A card with NO FINDING fails that test on the same reasoning, one step earlier. "What is
    happening with errorcore.dev?" is answered perfectly well by "an open deal, and nothing on
    record says what problem it solves" — so it keeps `ask` and `api`. "What should I do right
    now?" is not answered by it at all. On the design partner's org, 16 of 47 cards were exactly
    that and every one of them sat in the app queue costing a reader the seconds to find out the
    system knew nothing.
    """
    surfaces = ["ask", "api"]
    if not has_finding:
        return surfaces
    def _val(field):
        v = facts.get(field)
        return v.get("value") if isinstance(v, dict) and "value" in v else v

    settled = str(_val("deal.status") or "").lower() in _SETTLED_STATUSES
    try:
        momentum = float(_val("derived.momentum") or 0)
    except (TypeError, ValueError):
        momentum = 0.0
    # Settled AND going nowhere. Either alone is not enough: a won deal still moving is an
    # expansion conversation, and a live deal at zero momentum is exactly what the app exists to
    # surface.
    if settled and momentum <= 0:
        return surfaces
    if actions:
        surfaces.insert(0, "app")
        # An agent can only act on a play it was handed. `run_play` is that handover; a card whose
        # only actions are human judgement calls has nothing to delegate.
        if any(str(a.get("action") or "") == "run_play" for a in actions if isinstance(a, dict)):
            surfaces.insert(1, "agent")
    return surfaces


def _plain_value(value):
    """Unwrap the canonical tag wrappers before a value is shown to a person.

    `canonicalize` encodes a Decimal as `{"$decimal": "0"}` so a hash is stable across float
    repr — correct for hashing, and a card rendered it verbatim: the live app showed
    "momentum: [object Object]" and "engagement: [object Object]" where a number belonged. The
    wrapper is a serialisation detail of the audit layer and has no business crossing into copy.
    """
    if isinstance(value, dict) and len(value) == 1:
        for tag in ("$decimal", "$datetime", "$date", "$uuid"):
            if tag in value:
                return value[tag]
    return value


#: How many authored claims a card may rest its `why` on. Two, not all of them: the block is read
#: by a person deciding in a few seconds, and a bibliography is not a reason. The decision's full
#: citation list stays on the signal row for anyone auditing it.
MAX_WHY_CITATIONS = 2


def _why(evidence: list, _facts: dict, citations: list | None = None) -> list[dict]:
    """Project the evidence the immutable reasoning context bound, then the doctrine it rested on.

    A short evidence chain must stay short and honest. Unrelated current graph facts cannot be
    promoted into post-hoc reasons merely to satisfy a presentation count.

    **THE CITATION HALF, AND WHY IT WAS MISSING.** CLG-08 attaches the authored heuristic to
    `ReasoningDecision.citations` byte-identical to the corpus, migration 0114 gave `signals` a
    column for it, and the trail stopped there: this function projected `field`/`value` pairs and
    nothing else, so `scripts/l3_pilot_report.py`'s stricter row —
    `cards_quoting_the_claim_in_their_own_copy` — read **0 on every card ever built**. The expert's
    sentence reached the row BEHIND the card and never the card. A reader of J5 could see a
    citation count and conclude the doctrine had reached a human when it had reached a table.

    **QUOTED VERBATIM, NEVER PARAPHRASED.** `statement_hash` pins the stored quote to the authored
    bytes precisely so a renderer cannot reword it and still claim the citation, and the pilot
    report's verbatim substring test is the check. The statement is passed through untouched and
    carries its own `artifact_id`, so a card's claim is traceable to the file it came from.
    """
    out = []
    for e in (evidence or []):
        if isinstance(e, str):
            out.append({"evidence_id": e, "source": "reasoning_trace"})
            continue
        if not isinstance(e, dict):
            continue
        field = e.get("field", "")
        out.append({"field": field, "value": _plain_value(e.get("value")),
                    "source": _SOURCE.get(field.split(".")[0], "graph")})
    for citation in (citations or [])[:MAX_WHY_CITATIONS]:
        if not isinstance(citation, dict):
            continue
        statement = str(citation.get("statement") or "").strip()
        if not statement:
            continue
        out.append({
            "statement": statement,
            "artifact_id": citation.get("artifact_id"),
            "artifact_class": citation.get("artifact_class"),
            "statement_hash": citation.get("statement_hash"),
            # `expertise`, not `graph`: this is authored doctrine, not a reading of the tenant's
            # data, and a surface that showed the two the same way would be claiming the corpus
            # observed something.
            "source": "expertise",
        })
    return out


def _context_tags(node_type: str, attrs: dict, facts: dict, sources: set[str]) -> list[str]:
    """On-device matcher whitelist (§5.14). App tags come from each fact's REAL source_ref.source
    (graph_source_refs) — never guessed from a field-name prefix — plus a work-tool url_domain/tool
    path when the fact set carries one."""
    tags: set[str] = {_SOURCE_APP[s] for s in sources if s in _SOURCE_APP}
    domain = (attrs or {}).get("company_domain") or \
        (facts.get("deal.company_domain") or {}).get("value") or \
        (facts.get("company.domain") or {}).get("value")
    if domain:
        tags.add(f"url_domain:{domain}")
    deal_key = (attrs or {}).get("crm_deal_id") or (facts.get("deal.id") or {}).get("value")
    if deal_key:
        tags.add(f"hs:deal:{deal_key}")
    return sorted(tags)


def build_draft(store, org_id: str, signal: dict, effective: dict, eval_time,
                quotes: list[dict] | None = None) -> dict:
    """E0 output — a complete card.v1 minus the rendered copy (E1) and persisted state."""
    node_id = signal["subject_node_id"]
    name, node_type, attrs, facts = load_node(store, org_id, node_id)
    # A SYNTHETIC ANCHOR'S DISPLAY NAME IS NOT THE CARD'S SUBJECT.
    #
    # `context/outreach_situations.py` names its nodes "Investor A — awaiting reply" so a person
    # reading the graph can tell an outreach anchor from the person it concerns. A card writes its
    # own framing, so using that as `{entity}` produced "Investor A — awaiting reply — waiting 4d
    # on a reply": the situation said twice, once in the node's name and once in the copy.
    #
    # The plain counterparty travels as a FACT on the anchor for exactly this reason, so the card
    # reads the name from the data rather than from a label meant for a different reader.
    name = _fval(facts, "outreach.counterparty") or _fval(facts, "commitment.owed_to") or name
    sources = _real_sources(store, org_id, node_id)
    reason_code = signal["reason_code"]

    scoring = effective.get("scoring", {})
    urgency_band = band(int(signal["score"]), scoring.get("bands"))
    # THE FIRM A PERSON BELONGS TO IS PART OF WHAT THIS SITUATION IS ABOUT, so a responsibility
    # declared over `client = Peak XV` can match a card anchored on a partner there.
    scoped_attrs = {**(attrs or {}), **_group_memberships(store, org_id, node_id)}
    assignee, rule = resolve_assignee(store, org_id, facts, scoped_attrs)
    # ONE CARD, EVERYONE WHO ANSWERS FOR IT. The row stays keyed on the signal — three writers
    # upsert on `cards_one_per_signal` and every count in the product reads rows — so the people
    # it reaches ride BESIDE it in `card_recipients`, each told which slice made it theirs.
    co_recipients = list(co_recipients_for(store, org_id, facts, scoped_attrs, owner=assignee))
    # The rule's own declared clock, not a hand-written lookup. Each pack rule states the field
    # its urgency is timed from; the renderer used a 6-entry map and printed "severald" for the
    # other 19.
    clock_path = None
    for r in (effective.get("rules") or ()):
        if isinstance(r, dict) and r.get("reason_code") == reason_code:
            clock_path = (r.get("urgency") or {}).get("path")
            break
    slots = compute_slots(reason_code, name, facts, eval_time, clock_path)

    # Composite deal-health (C3): member concerns come from the immutable context payload bound to
    # the selected run, never from the mutable signal projection. Surface them as a `concerns` slot
    # and grounded fact so the renderer can compose the audited verdict.
    if reason_code == "deal_health":
        codes = [member.get("reason_code") for member in
                 (signal.get("composite_members") or ()) if isinstance(member, dict)]
        codes = list(dict.fromkeys(code for code in codes if code))
        if codes:
            concerns = ", ".join(str(c).replace("_", " ") for c in codes)
            slots["concerns"] = concerns
            facts = {**facts, "deal.concerns": {"value": concerns, "confidence": 1.0,
                                                "authority_rank": 3}}
    # THE COMPILED BRAIN'S OWN COPY FIRST. `effective["templates"]` is the TENANT PACK's, keyed
    # by the pack's own reason codes; a compiled signal's reason_code is its situation type
    # (`opportunity`, `relationship`, `investor_relationship`) and no pack authors those. The
    # lookup therefore returned `{}` for every compiled card — an empty render_hint, so the
    # prompt carried no guidance and eighteen cards came back reading alike, and an empty
    # fallback, so a rejected line shipped as the default `{stage}` slot: the word "open".
    #
    # A legacy signal carries no `capability_render` and falls through to the pack exactly as
    # before. Neither lane can take the other's copy: the compiled block travels on the audited
    # capability snapshot, the pack block on the tenant's effective config.
    capability_render = signal.get("capability_render")
    template = (dict(capability_render) if isinstance(capability_render, dict)
                and capability_render else
                (effective.get("templates", {}) or {}).get(reason_code, {}))
    _play_id = (effective.get("plays", {}).get(signal.get("play") or "", {}) and signal.get("play"))

    actions = [
        {"type": "run_play", "play_id": signal.get("play"),
         "label": f"Draft {template.get('artifact_kind', 'response').replace('draft_', '')}",
         "artifact_ready": True},
        {"type": "do_it_myself"},
        {"type": "snooze", "options": ["4h", "tomorrow_09", "3d", "custom"]},
        {"type": "wrong", "reasons": ["not_relevant", "bad_timing", "wrong_facts"]},
    ]
    # CLARITY GATE, at build time. When the fact that gives this card's imperative its meaning is
    # absent, the card is WRITTEN as an observation: no run_play button, and a stated reason. The
    # same verdict used to be computed in a read projection on one endpoint and merely annotated
    # there, so the list view — the surface anyone actually scans — showed the imperative anyway.
    level = _require_level(signal)
    abstained = signal.get("abstained_because")
    grounded, missing, recommended = clarity_verdict(
        reason_code, {str(o.get("kind")) for o in (signal.get("observations") or ())},
        set(facts))
    if not grounded:
        level = str(_ABSTENTION.OBSERVATION)
        abstained = abstained or f"missing {missing} — {recommended}"
        # A card that cannot say what to do must not offer a button that claims to do it. `wrong`
        # and `snooze` remain: the user must still be able to dismiss or defer it.
        actions = [a for a in actions if a.get("type") in ("wrong", "snooze")]

    # NOTHING-TO-SAY GATE. `clarity_verdict` above asks the same question and answers it from a
    # three-entry map of LEGACY pack reason codes; the compiled lane's codes are `opportunity`,
    # `first_response_overdue`, `investor_relationship`, `investor_contact`, so on the design
    # partner's org it matched 0 of 47 cards. Meanwhile `_apply_abstention` passed all 47 because
    # the tenant's pack is promoted, which is a statement about AUTHORITY and not about whether
    # this particular card found anything. Nothing else asked, so every card shipped
    # `prescriptive` — including 25 whose entire content was that something was missing:
    # "errorcore.dev: no problem documented yet", "boardy.ai: no concerns logged yet".
    #
    # The situation AUTHOR answers it here instead, once, for every card the situation will ever
    # produce. That is the right place: whether a situation is defined by an absence is a fact
    # about the expertise (`matches.when: [{absent: business_need}]`), not about one render's
    # luck, and it is reviewed and version-hashed with the rest of the file.
    #
    # `review`, not `observation`: the vocabulary reserves review for "something is missing and a
    # human must look", which names what this card is. Downgrading is not hiding — the card still
    # answers Ask and the API, it just stops claiming the authority to give an order it cannot
    # phrase.
    has_finding = not states_absence(template)
    if not has_finding:
        level = str(_ABSTENTION.REVIEW)
        abstained = abstained or (
            "this situation is defined by what is missing from the record, so there is no "
            "instruction to give — a human has to establish the fact first")
        actions = [a for a in actions if a.get("type") in ("wrong", "snooze")]

    # NO-EVIDENCE GATE. The gate above asks whether the SITUATION is defined by an absence. This
    # one asks a narrower and more damning question: can this card quote anything anybody actually
    # said? Measured on the design partner's org on 2026-08-31, 48 of the 55 live cards could not.
    #
    # That is what the reader was seeing. A card written from five typed scalars can say THAT
    # somebody wrote — "Thread with nikhil@addis.im is owed a reply. They wrote several days ago
    # and no reply has gone back." — and cannot say WHAT they wrote, why it matters, or what the
    # reply should contain. Its Run Play button offers to draft a response to a message whose
    # contents are not in the process. Forty-eight of those are not forty-eight cards; they are
    # noise with a headline, and each one costs a reader the seconds to discover the system has
    # nothing.
    #
    # `review` is the honest level and the vocabulary already names it: "something is missing and
    # a human must look". The missing thing is the message itself, and the exact question is "open
    # the thread". `ask` and `api` are kept for the same reason `states_absence` keeps them —
    # "what is happening with this account" is still answerable from the typed facts; only "what
    # should I do right now" stops pretending.
    #
    # The bar is deliberately low: ONE sentence from the counterparty is enough. This is not a
    # quality filter and must never become one — a terse card with a real finding passes. It only
    # rejects the case where there is no finding to be terse about. `quotable` sets the bar, and
    # only two things fail it: our own outgoing words (which cannot evidence what THEY asked) and
    # a bare extracted name (which is not something anybody said).
    # WHOSE WORDS GROUND *THIS* CARD.
    #
    # The gate below asks for one sentence from the COUNTERPARTY, and for a reply-shaped card
    # that is exactly right: you cannot draft an answer to a message whose contents are not in
    # the process, and quoting our own outgoing words back as "what they asked" is the
    # misattribution `quotable` exists to prevent.
    #
    # It is the wrong question for a card whose entire finding is that they said NOTHING. An
    # unanswered approach is grounded by OUR OWN last message — that is the thing being followed
    # up, and knowing what we asked is what separates "send a reminder" from a follow-up worth
    # reading. Requiring their words there is requiring the silence to speak, and it abstained 19
    # live cards on the design partner's org for the crime of being about a silence.
    #
    # Attribution stays safe without the filter: `render._prompt` labels every quote with its
    # speaker and instructs the model never to present something the account holder wrote as
    # something the other side asked. The gate is what changes, not the honesty rule.
    # WHOSE EVIDENCE THIS RECIPIENT MAY SEE. Filtered HERE and not in the query, because the
    # quotes are read at `load_evidence_quotes` before `resolve_assignee` has run — the recipient
    # is not known yet at the point the SQL executes, which is the structural reason this check
    # never existed.
    quotes = _visible_quotes(quotes, assignee, store=store, org_id=org_id)
    grounding = quotable(quotes)
    if not grounding and reason_code in _GROUNDED_BY_OUR_OWN_WORDS:
        grounding = [q for q in (quotes or ())
                     if str(q.get("kind") or "") not in _NAMING_ONLY_KINDS
                     and str(q.get("quote") or "").strip()]
    has_quote = bool(grounding)
    if not has_quote:
        level = str(_ABSTENTION.REVIEW)
        abstained = abstained or (
            "nothing this account said is on record, so there is no way to say what they asked "
            "for or draft a reply to it — open the thread")
        actions = [a for a in actions if a.get("type") in ("wrong", "snooze")]

    score_inputs = signal.get("score_inputs") or {}
    card_expires_at = eval_time + timedelta(days=EXPIRY_DAYS)
    decision_expires_at = signal.get("decision_expires_at")
    if isinstance(decision_expires_at, str):
        try:
            decision_expires_at = datetime.fromisoformat(
                decision_expires_at.replace("Z", "+00:00"))
        except ValueError:
            decision_expires_at = None
    if isinstance(decision_expires_at, datetime):
        if decision_expires_at.tzinfo is None or decision_expires_at.utcoffset() is None:
            raise ValueError("decision_expires_at must be timezone-aware")
        card_expires_at = min(card_expires_at,
                              decision_expires_at.astimezone(timezone.utc))

    return {
        "signal_id": signal["signal_id"], "org_id": org_id, "subject_node_id": node_id,
        # Fail closed on level: defaulting to "prescriptive" is what let the pipeline's hardcoded
        # literal go unnoticed, turning every predictive risk warning into a direct order.
        "domain": effective.get("pack_id", "sales"), "level": level,
        # A card that declines to instruct without saying why is indistinguishable from one that
        # broke — the user cannot tell "we do not know enough" from "something failed".
        "abstained_because": abstained,
        "urgency_band": urgency_band, "assignee": assignee, "resolved_rule": rule,
        "co_recipients": co_recipients,
        "score": int(signal["score"]),
        "score_block": {"S": int(signal["score"]), **{k: score_inputs.get(k) for k in
                        ("U", "I", "R", "C")}, "inputs": score_inputs},
        # ── The Customer Intelligence Contract ────────────────────────────────────────────
        # Six of the twelve answers a promoted item must give had no column at all, and two of
        # them (`stakes`, `completion`) were the literal string "missing", written into the read
        # projection at request time. Producing them HERE makes card_builder the single producer
        # of the contract instead of a request-time projection inventing what it can.
        #
        # Every one of these is populated from something the engine already computed. None is
        # inferred: a NULL means this card genuinely never carried that answer, which is the
        # measurement the scorecard needs.
        "business_subject": name,                      # the counterparty, not the GeniOS seat
        "relationship_role": _fval(facts, "party.role"),
        # NEVER the slot, and never the objective. `compute_slots` fills an absent
        # `commitment.action` with the sentinel "the commitment", so this contract field — which
        # is supposed to say what is actually OPEN — reported the words "the commitment" on every
        # card that had no commitment. The objective is not a substitute either: "fundraising" is
        # what the thread is FOR, not what is outstanding in it, and putting it here would answer
        # a different question in the field's own name. A NULL is the measurement the intelligence
        # contract asks for.
        "unresolved_item": _fval(facts, "commitment.action"),
        "why_now": _why_now(reason_code, facts, slots, eval_time),
        "capability_key": signal.get("capability_id"),
        "capability_version": signal.get("capability_version"),
        # Unreviewed expertise must not instruct — the same state the abstention gate reads.
        # The SIGNAL's own value first: it records the review state of the exact package that
        # authored this decision, while `effective` describes the tenant's config as a whole. A
        # legacy signal carries none and falls through to the config, exactly as before.
        "capability_review_state": str(
            signal.get("capability_review_state")
            or (effective.get("expertise") or {}).get("review_state") or "unreviewed"),
        # The DECISION's own values first; the pack template only fills a pre-0070 signal.
        # These came from ReasoningDecision at emit time — the pack fallback is a config author's
        # generic estimate, not this decision's judgment.
        "outcome_window_days": (signal.get("decision_window")
                                or _play_window(effective, signal.get("play"))),
        "success_signal": _play_success(effective, signal.get("play")),
        "do_nothing_consequence": signal.get("do_nothing_consequence"),
        "candidate_steps": signal.get("candidate_steps") or [],
        "rejected_candidates": signal.get("rejected_candidates") or [],
        "uncertainty": signal.get("uncertainty") or [],
        # Decomposed, not a scalar: "unsure about the evidence" and "unsure about the timing"
        # call for different user actions and a single number cannot tell them apart.
        "confidence_vector": {k: score_inputs.get(k) for k in ("C", "U", "I", "R")},
        "actions": actions,
        "why": _why(signal.get("evidence"), facts, signal.get("citations")),
        "surfaces": _surfaces(facts, signal, actions,
                              has_finding=has_finding and has_quote),
        "context_tags": _context_tags(node_type, attrs, facts, sources),
        "config_snapshot_id": signal.get("config_snapshot_id"),
        "template_version": (effective.get("templates", {}) or {}).get("_version"),
        "builder_version": BUILDER_VERSION,
        "expires_at": card_expires_at,
        # carried forward to E1 (not persisted as-is)
        "_reason_code": reason_code, "_template": template, "_facts": facts, "_slots": slots,
    }
