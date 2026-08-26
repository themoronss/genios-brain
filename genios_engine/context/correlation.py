"""L2 · Correlation Engine — which events describe the SAME business situation.

This engine has exactly one job and refuses every other one. It does not prioritise, it
does not score risk, it does not recommend. It answers one question:

    "Do these signals belong to the same thing?"

Four systems report one reality. Slack says "need pricing approval", email says "customer
is waiting", the calendar holds "Pricing Review tomorrow", the CRM says the deal is
Enterprise. A retrieval system stores four documents. This stores ONE situation with four
pieces of evidence — which is the difference between recalling text and understanding a
company.

THE GOVERNING PRINCIPLE: under-correlate rather than over-correlate.

    Wrongly SPLITTING one situation costs you a duplicate card. Annoying.
    Wrongly MERGING two situations builds a chimera and reasons about it at full
    confidence — two customers' problems fused into one recommendation.

So every rule below fails towards "leave them apart". This is the same instinct as the
identity rule in platform.identity: when the evidence is not decisive, do nothing.

HOW A SITUATION IS ANCHORED
    (counterparty entity, domain)

Company beats person, because people change companies and a company outlives them.

Domain comes from ranked hints: a source prior first (a fact about the connector), then the
model's own reading of the message, then a keyword match. It used to be keyword-only, and
"never an LLM" sounded like determinism but bought none — the model's judgment was extracted,
written into an observation, and discarded, while a substring test with no idea where in the
document it landed made the call. A regex matching "error" four times inside a confidentiality
footer typed this org's most important fundraising thread as `support`.

Replay determinism is preserved by the extraction cache, not by refusing to read the answer.

THREAD IS A CONTINUITY CARRIER, NOT AN ANCHOR
An email thread id is a HARD join: an event sharing a thread with already-correlated
events joins those correlations whatever its own anchor says. A bare reply — "sounds
good, thanks" — names no company, contains no keyword and anchors nothing. Without
thread inheritance every reply in a conversation becomes its own island, which is the
failure mode that makes correlation look like it is working while it does nothing.

Thread is checked FIRST. The anchor key is only consulted when the thread is silent.

KNOWN LIMITATION, STATED RATHER THAN HIDDEN
Two independent deals with the same company, with no CRM connected, correlate into one
situation. Nothing deterministically available distinguishes them — same people, same
domain, same period. When a deal object IS known it becomes part of the key and they
separate. Guessing the split from wording would be exactly the over-correlation this
module refuses to do.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text

from genios_engine.context.domain_spec import canonical_domain

from genios_engine.platform.canonical import stable_id

# How long a weak (entity+domain) correlation stays open to new evidence. A conversation
# that has been silent this long and then restarts is a NEW situation, not a continuation
# — the renewal you lost in March is not the renewal you are working in September.
# Threads are exempt: a reply after six months is still that thread.
CORRELATION_WINDOW_DAYS = 45

# Domain bucket for an event whose text triggered no keyword. Most email lands here, and
# that is fine: threads keep real conversations together, so `general` is a resting place
# for the genuinely uncategorised rather than a dumping ground for everything.
DEFAULT_DOMAIN = "general"

# Node types that can anchor a situation, strongest first. A deal is strongest because it
# is the business object itself; a company outlives its people; a person is the last
# resort. Anything else (meeting, document, commitment) describes a situation rather than
# anchoring one.
# Canon kinds that describe work in flight (currently: project) sit just below a deal
# and above a company. A named project is more specific than the company it belongs to,
# so "the Phoenix migration" should not be filed under "Acme" alongside the renewal.
#
# Read from the Layer 1 vocabulary rather than restated here, so adding an anchoring kind
# is one edit in one file — importing L1 from L2 is the legal direction.
def _anchor_priority() -> tuple[str, ...]:
    from genios_engine.capture.internal_knowledge import ANCHORING_KINDS
    # subscription / product_account are system-of-record business objects (like a deal): a billing
    # or account situation is ABOUT them. Without them here, choose_anchors returns [] for every
    # Stripe/client-DB structured event → it reaches NO situation, and admin/account situations report
    # their fields (renewal date, plan) missing forever — the "built, green, does nothing" dead-end.
    return ("deal", *sorted(ANCHORING_KINDS), "subscription", "product_account",
            "company", "person")


ANCHOR_PRIORITY: tuple[str, ...] = _anchor_priority()

JOINED_VIA_THREAD = "thread"
JOINED_VIA_ANCHOR = "anchor"


@dataclass(frozen=True, slots=True)
class Anchor:
    """One thing a situation can be about."""

    node_id: str
    node_type: str
    domain: str

    @property
    def base_key(self) -> str:
        """Identity of the situation ACROSS generations. The generation number is added
        separately so a restarted conversation is a sibling of the old one, not a
        stranger — which is what lets the history stay findable."""
        return stable_id("corr", {"node": self.node_id, "domain": self.domain})


#: How much a hint's ORIGIN is worth, highest first.
#:
#: A source prior is a fact about the connector — mail arriving from a support desk IS support —
#: so nothing outranks it. The model comes next: it read the entire message and answered, and
#: its answer is a judgment about meaning. A keyword match is last because it is a substring
#: test with no idea where in the document it landed.
#:
#: That ordering is the whole fix. Taking the first hint made a keyword outrank the model, and a
#: regex matching "error" four times inside a confidentiality footer typed this org's most
#: important fundraising thread as `support` — while the model's own reading of the same message,
#: ["venture_capital", "startup_funding"], was written into an observation and discarded.
#: `scope` is what `capture/domain/hints.py` actually emits for a source prior. Guessing the
#: token would have silently demoted every prior below a keyword — the exact inversion this
#: ranking exists to prevent, reintroduced by a typo nobody could see in a passing test.
_HINT_RANK = {"scope": 0, "source": 0, "prior": 0, "model": 1, "keyword": 2}
#: An unrecognised origin sits between the model and a keyword: it came from somewhere
#: deliberate enough to be labelled, so it should not rank below a substring match — but it has
#: not earned a prior's authority either.
_UNRANKED = 2


def resolve_domain(domain_hints: list | None) -> str:
    """Hints → the one domain this event correlates under, strongest ORIGIN first.

    Ties inside a rank keep their arrival order, so two keywords firing at once still resolves
    deterministically rather than alphabetically.
    """
    ranked: list[tuple[int, int, str]] = []
    for i, hint in enumerate(domain_hints or []):
        if isinstance(hint, dict):
            domain, origin = hint.get("domain"), hint.get("source")
        else:
            domain, origin = getattr(hint, "domain", None), getattr(hint, "source", None)
        if domain:
            ranked.append((_HINT_RANK.get(str(origin or ""), _UNRANKED), i, str(domain)))
    if not ranked:
        return DEFAULT_DOMAIN
    ranked.sort()
    # CANONICALISE HERE, at the one point where a hint becomes THE domain. This value is the
    # correlation key, the stored `context_situations.domain` and the hint Layer 3 resolves a
    # corpus folder from, so an alias applied anywhere later would leave those three disagreeing.
    return canonical_domain(ranked[0][2])


#: Roles that make a party INFRASTRUCTURE for a conversation rather than a party to it.
#: An introduction bot appears in every introduction it brokers; a scheduling service appears in
#: every meeting it books. They are present, they are not what the conversation is about.
NON_ANCHORING_ROLES: frozenset[str] = frozenset({"introducer", "machine", "observer"})


def choose_anchors(node_types: dict[str, str], domain: str,
                   node_roles: dict[str, str] | None = None) -> list[Anchor]:
    """The nodes an event is ABOUT → the situations it belongs to.

    Only the strongest available tier anchors. An email to a person at a company yields
    ONE company-anchored situation, not a company one and a person one — otherwise every
    conversation would be duplicated at both levels and every count would be double.

    Several nodes at the SAME tier all anchor: an introduction email naming two companies
    genuinely belongs to two situations, and dropping one loses a real relationship.

    A CONNECTOR NEVER ANCHORS. An introduction bot is named in every introduction it brokers, so
    anchoring on it fuses every one of those conversations into a single situation: the design
    partner's graph has 68 unrelated members under one `boardy.ai` correlation, from 254 distinct
    threads. Nothing downstream can recover a business subject from that — and it is why a card
    could tell him to reply to the introducer rather than to the investor he was introduced to.
    Excluding them is not a filter on relevance; the connector's own mail is still captured. It
    is a statement that infrastructure is not a subject.
    """
    roles = node_roles or {}
    for node_type in ANCHOR_PRIORITY:
        at_tier = sorted(nid for nid, ntype in node_types.items() if ntype == node_type)
        subjects = [nid for nid in at_tier
                    if roles.get(nid, "") not in NON_ANCHORING_ROLES]
        # Fall back to the full tier when EVERY node at it is a connector: a message genuinely
        # only about infrastructure still deserves a situation, and silently anchoring nothing
        # would drop it.
        chosen = subjects or at_tier
        if chosen:
            return [Anchor(node_id=nid, node_type=node_type, domain=domain)
                    for nid in chosen]
    return []          # nothing anchored — the event stands alone, which is a real answer


def joins_window(*, group_first: datetime | None, group_last: datetime | None,
                 event_at: datetime | None, window_days: int = CORRELATION_WINDOW_DAYS) -> bool:
    """Does this event belong to an existing weak correlation, or start a new one?

    Tested against the group's SPAN, not just its latest event. A connector recovering
    from an outage delivers old events after new ones; measuring only from the latest
    would push those late arrivals into a fresh generation and split one situation in
    two — the bug that makes correlation quietly worse after every outage.
    """
    if event_at is None:
        return False                     # undated evidence never extends a window
    if group_first is None or group_last is None:
        return True                      # an empty group accepts its first event
    window = timedelta(days=window_days)
    return (group_first - window) <= event_at <= (group_last + window)


def merged_span(*, group_first: datetime | None, group_last: datetime | None,
                event_at: datetime | None) -> tuple[datetime | None, datetime | None]:
    """The group's span after admitting this event. Widens in BOTH directions, because a
    late-arriving old event legitimately moves the start of a situation backwards."""
    if event_at is None:
        return group_first, group_last
    first = event_at if group_first is None else min(group_first, event_at)
    last = event_at if group_last is None else max(group_last, event_at)
    return first, last


@dataclass(frozen=True, slots=True)
class CorrelationPlan:
    """What the SQL layer should do. Pure output — nothing here has touched a database.

    `via` records WHY these correlations were chosen. Without it, a wrong grouping is
    unexplainable after the fact: you can see that two events were joined but not whether
    a thread or an anchor did it.
    """

    anchors: tuple[Anchor, ...]
    via: str
    inherited_correlation_ids: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.anchors and not self.inherited_correlation_ids


def plan_correlation(*, thread_correlation_ids: list[str] | None,
                     node_types: dict[str, str], domain_hints: list | None,
                     node_roles: dict[str, str] | None = None) -> CorrelationPlan:
    """The whole decision, as a pure function.

    Order matters and is the heart of the engine:

      1. THREAD FIRST. If this event's thread already has correlations, it joins those.
         A reply carries the conversation's identity even when its own text carries
         nothing — and it must not ALSO open an anchor-based group, or one conversation
         would live in two places.

      2. ANCHOR otherwise. Strongest tier of entity, plus the deterministic domain.

      3. NOTHING is a valid outcome. An event that anchors nothing correlates to nothing.
         Inventing a group for it would fill the graph with situations about no one.
    """
    if thread_correlation_ids:
        return CorrelationPlan(anchors=(), via=JOINED_VIA_THREAD,
                               inherited_correlation_ids=tuple(dict.fromkeys(
                                   thread_correlation_ids)))
    domain = resolve_domain(domain_hints)
    return CorrelationPlan(anchors=tuple(choose_anchors(node_types, domain, node_roles)),
                           via=JOINED_VIA_ANCHOR)


# ═══════════════════════════════════════════════════════════════════════════════════
# Persistence. Everything above is pure and decides; everything below only writes down
# what was decided. Keeping the split sharp is what makes the rules testable without a
# database — the same shape `fact_write_action` already uses in graph_store.
# ═══════════════════════════════════════════════════════════════════════════════════

def thread_correlations(conn, *, org_id: str, thread_id: str | None,
                        exclude_event_id: str | None = None) -> list[str]:
    """Correlations already holding OTHER events from this thread.

    Excludes the event being processed so a re-run cannot inherit from itself and pin an
    event to a group it originally opened for a different reason.
    """
    if not thread_id:
        return []
    # The exclusion is composed in Python rather than passed as a nullable bind. A bare
    # `:param is null` gives Postgres no type to infer and raises "could not determine
    # data type of parameter" — a failure that would only appear against a real database,
    # long after the tests looked green.
    params: dict[str, str] = {"o": org_id, "thread": thread_id}
    exclusion = ""
    if exclude_event_id:
        exclusion = "and m.event_id <> :excl "
        params["excl"] = exclude_event_id
    rows = conn.execute(text(
        "select distinct m.correlation_id from context_correlation_members m "
        "join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
        "where m.org_id = :o and se.parent_object_id = :thread " + exclusion),
        params).fetchall()
    return sorted(r.correlation_id for r in rows)


def find_or_open(conn, *, org_id: str, anchor: Anchor, event_at: datetime | None) -> str:
    """The live correlation for this anchor, opening a new generation when the last one
    has gone cold.

    The insert is conflict-tolerant on purpose. L2 drains with several workers, so two
    events for the same customer can be processed at the same instant; both would compute
    the same "next generation" and one must lose the race and re-read rather than raise.
    """
    latest = conn.execute(text(
        "select correlation_id, generation, first_event_at, last_event_at "
        "from context_correlations where org_id=:o and anchor_node_id=:n and domain=:d "
        "order by generation desc limit 1"),
        {"o": org_id, "n": anchor.node_id, "d": anchor.domain}).first()

    if latest is not None and joins_window(group_first=latest.first_event_at,
                                           group_last=latest.last_event_at,
                                           event_at=event_at):
        return latest.correlation_id

    generation = (latest.generation + 1) if latest is not None else 1
    correlation_id = stable_id("corr", {"base": anchor.base_key, "gen": generation})
    conn.execute(text(
        "insert into context_correlations (correlation_id, org_id, anchor_node_id, "
        "anchor_type, domain, generation, first_event_at, last_event_at) "
        "values (:id, :o, :n, :t, :d, :g, :at, :at) "
        "on conflict (org_id, anchor_node_id, domain, generation) do nothing"),
        {"id": correlation_id, "o": org_id, "n": anchor.node_id, "t": anchor.node_type,
         "d": anchor.domain, "g": generation, "at": event_at})
    # Re-read rather than trusting the insert: another worker may have won the race, and
    # its row is the one every later event must join.
    return conn.execute(text(
        "select correlation_id from context_correlations where org_id=:o "
        "and anchor_node_id=:n and domain=:d and generation=:g"),
        {"o": org_id, "n": anchor.node_id, "d": anchor.domain, "g": generation}).scalar()


def _add_member(conn, *, org_id: str, correlation_id: str, event_id: str, via: str,
                event_at: datetime | None) -> bool:
    """Join one event to one correlation. Returns False if it was already a member.

    Membership is idempotent and the counters follow it: incrementing on a replayed event
    would inflate a situation's evidence count without adding any evidence.
    """
    inserted = conn.execute(text(
        "insert into context_correlation_members (org_id, correlation_id, event_id, "
        "joined_via) values (:o, :c, :e, :via) on conflict do nothing"),
        {"o": org_id, "c": correlation_id, "e": event_id, "via": via}).rowcount
    if not inserted:
        return False
    conn.execute(text(
        "update context_correlations set event_count = event_count + 1, "
        "  first_event_at = least(first_event_at, coalesce(:at, first_event_at)), "
        "  last_event_at  = greatest(last_event_at, coalesce(:at, last_event_at)), "
        "  status = 'open', updated_at = now() "
        "where org_id = :o and correlation_id = :c"),
        {"o": org_id, "c": correlation_id, "at": event_at})
    return True


def lift_people_to_their_companies(conn, *, org_id: str,
                                   node_types: dict[str, str]) -> dict[str, str]:
    """Add each person's company to the anchor pool, so both lanes land in one situation.

    Without this the two lanes anchor differently for the SAME human. The extraction lane
    builds a company node from the sender's email domain, so an email with john@acme.io
    anchors on Acme. The structured lane creates attendees as bare people with no
    employer edge, so a calendar invite with john@acme.io anchors on John. The email and
    the meeting about one deal then live in two situations that never meet — which is
    exactly the "four systems, one reality" failure this engine exists to end.

    Read-only by design. If no company node exists for that domain yet, the person stays
    the anchor: correlation merges reality, it does not invent entities to merge.
    """
    people = [nid for nid, ntype in node_types.items() if ntype == "person"]
    if not people:
        return node_types
    rows = conn.execute(text(
        "select c.node_id from graph_nodes p "
        "join graph_nodes c on c.org_id = p.org_id and c.node_type = 'company' "
        "  and c.canonical_key = split_part(p.canonical_key, '@', 2) "
        "  and c.valid_to is null "
        "where p.org_id = :o and p.node_id = any(:ids) and p.valid_to is null "
        "  and p.canonical_key like '%@%'"), {"o": org_id, "ids": people}).fetchall()
    if not rows:
        return node_types
    lifted = dict(node_types)
    for row in rows:
        lifted[row.node_id] = "company"
    return lifted


def _lift_roles(conn, *, org_id: str, node_roles: dict[str, str]) -> dict[str, str]:
    """Carry each person's role onto the company they work at.

    `lift_people_to_their_companies` promotes a person node to their employer before anchoring,
    so a role attached to the person would be dropped exactly where it matters — the anchor is
    the company. An introduction bot's company is the introduction service.
    """
    if not node_roles:
        return {}
    lifted = dict(node_roles)
    try:
        rows = conn.execute(text(
            "select from_node_id, to_node_id from graph_edges "
            "where org_id=:o and edge_type='works_at' and valid_to is null"),
            {"o": org_id}).fetchall()
    except Exception:      # noqa: BLE001 — a role hint is an enrichment, never a hard failure
        return lifted
    for r in rows:
        role = node_roles.get(r.from_node_id)
        if role and r.to_node_id not in lifted:
            lifted[r.to_node_id] = role
    return lifted


def correlate_event(conn, *, org_id: str, event_id: str, occurred_at: datetime | None,
                    thread_id: str | None, node_types: dict[str, str],
                    domain_hints: list | None,
                    node_roles: dict[str, str] | None = None) -> list[str]:
    """Place ONE event into the situations it belongs to. Returns their ids.

    An empty list is a normal, frequent outcome: an event that anchors nothing and
    continues nothing belongs to no situation, and saying so is more useful than
    inventing a group about no one.
    """
    plan = plan_correlation(
        thread_correlation_ids=thread_correlations(
            conn, org_id=org_id, thread_id=thread_id, exclude_event_id=event_id),
        node_types=lift_people_to_their_companies(conn, org_id=org_id,
                                                  node_types=node_types),
        # A person's role carries to the company they were lifted to: an introduction bot's
        # company is the introduction service, and it must not anchor either.
        node_roles=_lift_roles(conn, org_id=org_id, node_roles=node_roles or {}),
        domain_hints=domain_hints)
    if plan.is_empty:
        return []

    correlation_ids = list(plan.inherited_correlation_ids) or [
        find_or_open(conn, org_id=org_id, anchor=anchor, event_at=occurred_at)
        for anchor in plan.anchors]
    for correlation_id in correlation_ids:
        if correlation_id:
            _add_member(conn, org_id=org_id, correlation_id=correlation_id,
                        event_id=event_id, via=plan.via, event_at=occurred_at)
    return [cid for cid in correlation_ids if cid]
