"""L2 · Seven customer-support readings, all of them approximations over correspondence.

WHAT THIS TENANT ACTUALLY HAS. No helpdesk. No ticket table, no queue object, no assignee, no
SLA clock, no CSAT. `_schema/vocabulary.yaml` records the consequence in one line: of the shipped
Layer 2 situation types exactly five are domain-neutral and ZERO observation kinds are
support-native. Seven authored situations therefore sat in `pending_l2_situation_types` — routed
to nothing, counted by `backlog.py`, invisible in the product.

They are buildable because a company whose support runs over email is the real case here, and a
mailbox does carry the shape of a service desk: a request arrives, somebody replies or does not,
the same person comes back about the same thing, a customer asks for a manager, we hand out a
workaround and go quiet. Every one of the seven readings below is that shape and nothing more.

THE RULE THAT GOVERNS THE WHOLE FILE. Never assert that a ticket, a queue or an SLA exists. The
fact namespaces are deliberately NOT `ticket.*` / `sla.*` / `ticket.queue` even where a spec asked
for them: `response.*` is a clock we computed from message timestamps, `backlog.*` is an unmet ask
we extracted, `mailbox.*` is one connected mailbox and not a routing decision. Every situation
carries the specific things it cannot see in `missing`, and `coverage` is capped per reading so a
consumer can never read records-grade completeness into an inference. The failure this prevents is
concrete and was named by the corpus itself: minting a type labelled "SLA Breach Imminent" on an
org with no SLAs is worse than a gap, because it looks like coverage.

WHY ONE MODULE. The seven share one mechanism — a bounded snapshot of correspondence, read seven
ways — so they are seven `read_*` functions over one `Desk` snapshot rather than seven modules
that each re-derive who is internal, which thread is which node, and whose turn it is. Those
derivations are exactly where an inconsistency would be invisible: two modules disagreeing about
`ball_in_court` would produce a queue that is overloaded and an item that is not aging.

THE SHAPE IS `context/periodic.py`, deliberately copied rather than reinvented. Each reading mints
an anchor node the correlation engine cannot reach, writes its computed facts onto it as ordinary
facts, and upserts one situation anchored there — so `_load_context`, `_neighborhood`,
`build_context_slice` and the whole compile path need no new concept. The anchors are NOT in
`correlation.ANCHOR_PRIORITY` for the same reason the tenant node is not: `choose_anchors` returns
only the strongest tier present, so a reachable synthetic anchor would swallow every conversation
that touched it into one situation.

WHY EACH READING GETS ITS OWN ANCHOR NODE TYPE. `domain_spec.type_for` is a map from anchor node
type to situation type, and it is the only producer of the type string. Two readings sharing an
anchor could not both be named. So `first_response_overdue` anchors on the existing `thread` node
and the other six mint an anchor whose identity IS the finding — a `backlog_item` per unmet ask, a
`contact_intent` per person-and-topic, a `topic` per intent, a `mailbox` per connection. That is
also what the corpus asked for: `queue-overloaded.yaml` says per-item aging "needs the item to be
a first-class subject", and `repeat-contact.yaml` says the gap "belongs to an INTENT" and that
person-scope "finds the evidence; it does not describe the finding".

NO LLM ANYWHERE IN HERE. Intent, escalation, workaround and fix are read by closed deterministic
lexicons over the masked text L1 already persisted in `prepared_content`, not by asking a model.
That costs recall — see `_MISSING_*` — and buys replayability: the same mailbox re-swept tomorrow
by a different model version produces the same seven answers.
"""
from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.domain_spec import domains_declaring, spec_for
from genios_engine.context.periodic import WINDOW_DAYS
from genios_engine.context.situations import (
    COVERAGE_UNKNOWN,
    RESOLVED_BY_FACT,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
    coverage_score,
    evidence_score,
    freshness_score,
    identity_score,
)
from genios_engine.platform.ids import new_id

# ── anchors ──────────────────────────────────────────────────────────────────────────────────
#
# Node types, not situation types. A domain opts into a reading by declaring the anchor in its
# `DomainSpec.situation_types`; nothing here names a domain, which is what
# `test_domain_names_appear_in_exactly_one_file_in_the_context_layer` requires of every file in
# this layer except the registry itself.
ANCHOR_THREAD = "thread"              # the conversation a request arrived in
ANCHOR_BACKLOG_ITEM = "backlog_item"  # one unmet ask, as its own subject
ANCHOR_ESCALATION = "escalation"      # one raise, from the ask to the acceptance
ANCHOR_CONTACT_INTENT = "contact_intent"   # one person, one recurring topic
ANCHOR_TOPIC = "topic"                # one topic, across everybody who raised it
ANCHOR_MAILBOX = "mailbox"            # one connected mailbox — never called a queue
ANCHOR_WORKAROUND = "workaround"      # one customer living on a temporary measure

#: How far back the correspondence snapshot reaches. A thread that began before it is not a
#: candidate for the first-response clock at all, rather than being given a wrong `opened_at`:
#: the earliest message we can see is not necessarily the earliest message there was, and a
#: fabricated arrival time would put a fabricated deadline under it. Flow arithmetic reads
#: `open_loops` instead, which is small and needs no bound.
LOOKBACK_DAYS = 120

#: How much of a message the lexicons read. Quoted history accumulates DOWNWARD in a mail thread —
#: `capture/preprocess` masks but does not strip it — so a phrase matched 4KB into a long reply is
#: usually somebody else's older words. Bounding the scan to the head bounds the match to the text
#: the sender actually wrote this time.
SCAN_CHARS = 900

#: Below this a workaround is still live support rather than debt, and a repeat contact is a
#: conversation rather than a pattern. Both corpus files put the honest span at a fortnight.
QUIET_DAYS = 14

#: The floor under the aging band. Without it a tenant whose reply turnaround is measured in hours
#: would open an aging item on anything unanswered overnight, which is a first-response question
#: and already has its own reading.
AGING_FLOOR_DAYS = 3.0
AGING_BASELINE_MULT = 2.0
AGING_PERCENTILE_BP = 9000

#: Adaptive-window bounds for repeat contact. `contact_rate_per_account` is contacts/week, so
#: three of an account's own inter-contact gaps is 21/rate days — clamped, because a silent
#: account would otherwise get a window measured in years and a noisy one a window of hours.
REPEAT_WINDOW_MIN_DAYS = 14
REPEAT_WINDOW_MAX_DAYS = 90
REPEAT_GAPS = 3

#: A content gap needs more than one loud customer. Two accounts is the smallest number that can
#: distinguish "this account is struggling" (which is repeat_contact) from "this answer does not
#: exist" (which is this).
KGAP_MIN_ASKERS = 3
KGAP_MIN_ACCOUNTS = 2

#: An escalation with nobody on it for longer than this is stale — and stays ACTIVE. An
#: unaccepted escalation going quiet is the failure, not the resolution, which is why these rows
#: are written directly and never handed to `DORMANT_AFTER_DAYS`.
ESCALATION_STALE_DAYS = 5

# Coverage ceilings, one per reading, as an int PERCENT on the `situations.SCORE_MAX` scale that
# every score in `context_situations` uses. None of these is a percentage of a record; each is
# "how much of what this situation would need can be inferred from mail at all". They are ceilings
# rather than values: the registry's `expected_fields` still decides the number under them, so a
# reading that is missing its own inputs scores lower still.
#
# THEY WERE BASIS POINTS (4000, 2500 …), copied from `periodic.py`, and that made the cap
# decorative. `situation_bso._bp` converts a stored score to basis points by multiplying by 100
# and clamping at 10000, so the whole ladder collapsed on the way to Layer 3: 2500 -> 10000,
# 3000 -> 10000, 4000 -> 10000. Every one of these seven readings — whose only defence against
# being mistaken for a real helpdesk is that it never claims records-grade completeness — arrived
# at the compiler claiming exactly that, and confidence saturated the same way, so
# `expertise_builder`'s `min(situation.confidence_bp, expert.coverage_bp)` capped nothing.
_CAP_FIRST_RESPONSE = 40
_CAP_AGING = 35
_CAP_ESCALATION = 30
_CAP_REPEAT = 30
_CAP_KNOWLEDGE = 25
_CAP_MAILBOX = 35
_CAP_WORKAROUND = 30

# What each reading cannot see. Declared per reading rather than estimated, so every compiled card
# states on its face what the finding underneath it does not know. Same discipline as the period
# situations' ["targets", "per-owner load", "cost per contact"].
_MISSING_FIRST_RESPONSE = (
    "a per-customer entitlement — one stated policy applies to everybody",
    "public holidays and coverage handovers",
    "requests raised by phone, chat or portal",
    "whether a reply was substantive or an acknowledgement",
)
_MISSING_AGING = (
    "a queue and an owner for this item",
    "resolution state — an outbound reply closes the item, which is not the same as resolving it",
    "an SLA clock, so every number here is calendar days",
    "requests the extractor did not read as an ask",
)
_MISSING_ESCALATION = (
    "internally-triggered escalations, which are raised where mail cannot see them",
    "acceptance as a recorded act — a new internal sender on the thread is an inference",
    "any un-escalate event, so no de-escalation can be measured",
    "escalation to a rota or a channel rather than to a named person",
)
_MISSING_REPEAT = (
    "whether a published answer was surfaced and rejected",
    "contacts on channels other than email",
    "explicit resolution of the earlier contact",
    "the requester's own intent — this one is read from their wording",
)
_MISSING_KNOWLEDGE = (
    "a published-answer index, so findability cannot be told apart from absence",
    "self-service searches, including the ones that gave up before writing in",
    "a deflection denominator — every contact here arrived by mail by definition",
    "intents nobody was persistent enough to email about",
)
_MISSING_MAILBOX = (
    "a queue — this is one connected mailbox, not a routing decision",
    "an owner for the backlog, so nobody is named by this",
    "resolution as distinct from reply",
    "support-native arrivals — only extracted asks are counted",
)
_MISSING_WORKAROUND = (
    "an issue record, so many customers on one defect cannot be joined",
    "engineering fix state — nothing tells us whether the fault is fixed",
    "workarounds given on a call, in chat or on a screen-share",
    "resolution — the quiet here is inferred, not asserted",
)


# ── the first-response policy ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ResponsePolicy:
    """A DECLARATION the tenant makes, never captured data — which is why `source` rides in the
    situation and onto the node as `response.target_source`.

    It is never `entitlement`. There is no per-customer target anywhere in this system, so the
    card copy this feeds must say "your stated first-response policy" and not "SLA". The corpus
    is explicit that the mislabel, not the arithmetic, is the failure mode here.
    """

    hours: float = 8.0
    working_days: tuple[int, ...] = (0, 1, 2, 3, 4)   # datetime.weekday(): Monday is 0
    day_start_hour: int = 9
    day_end_hour: int = 18
    utc_offset_hours: float = 0.0
    source: str = "engine_default"

    def __post_init__(self) -> None:
        if not self.working_days:
            raise ValueError("a response policy with no working days has no clock to run")
        if not 0 <= self.day_start_hour < self.day_end_hour <= 24:
            raise ValueError("the working window must start before it ends, inside one day")


#: A policy longer than this many working days is a configuration mistake, not a deadline, and
#: the walk below must terminate on one rather than spin.
_MAX_WORKING_DAYS = 90


def advance_working_hours(start: datetime, policy: ResponsePolicy) -> datetime:
    """`start` advanced by the policy's hours across its working window. Pure arithmetic.

    Deliberately not wall-clock: a request that arrives at 17:55 on a Friday under an eight-hour
    policy is not late at 01:55 on Saturday, and reporting it as late is how a first-response
    number stops being believed. Holidays are NOT modelled — they cannot be known from mail and
    calendar — so a deadline crossing a public holiday still reads as due, which is stated in
    every situation's `missing` rather than left for someone to discover.
    """
    shift = timedelta(hours=policy.utc_offset_hours)
    cur = start + shift
    remaining = timedelta(hours=policy.hours)
    for _ in range(_MAX_WORKING_DAYS):
        opens = cur.replace(hour=policy.day_start_hour, minute=0, second=0, microsecond=0)
        closes = cur.replace(hour=policy.day_end_hour, minute=0, second=0, microsecond=0)
        if cur.weekday() not in policy.working_days or cur >= closes:
            cur = (cur + timedelta(days=1)).replace(
                hour=policy.day_start_hour, minute=0, second=0, microsecond=0)
            continue
        if cur < opens:
            cur = opens
        available = closes - cur
        if available >= remaining:
            return (cur + remaining) - shift
        remaining -= available
        cur = (cur + timedelta(days=1)).replace(
            hour=policy.day_start_hour, minute=0, second=0, microsecond=0)
    return cur - shift


# ── the deterministic lexicons ───────────────────────────────────────────────────────────────
#
# A closed vocabulary, not free text. `repeat-contact.yaml` is explicit about why: "how do I
# export this" and "where is the download button" are one gap in two phrasings, and anything that
# fragments them splits the evidence exactly where it needs to be joined. A closed set limits the
# fragmentation; it does not remove it, so every ordinal these produce is a FLOOR and the
# situations say so.

INTENT_LEXICON: dict[str, tuple[str, ...]] = {
    "access_login": ("log in", "login", "sign in", "signin", "password", "locked out",
                     "two-factor", "2fa", "mfa", "sso", "access denied"),
    "billing_invoice": ("invoice", "billing", "receipt", "vat", "gst", "was charged",
                        "payment failed", "card declined", "statement"),
    "refund": ("refund", "money back", "chargeback", "reimburse"),
    "cancellation": ("cancel my", "cancel our", "cancellation", "terminate the contract",
                     "not renew", "downgrade"),
    "export_download": ("export", "download", "csv", "extract the data", "backup"),
    "integration_setup": ("api key", "webhook", "integration", "oauth", "endpoint",
                          "connect our"),
    "bug_report": ("not working", "is broken", "error message", "keeps failing", "crash",
                   "a bug", "times out", "is stuck"),
    "how_to": ("how do i", "how can i", "how do we", "is it possible to", "where do i find",
               "best way to"),
    "data_request": ("gdpr", "delete my data", "data request", "subject access", "personal data"),
    "pricing": ("pricing", "how much does", "a quote", "per seat", "the plan costs"),
    "onboarding": ("onboarding", "get started", "set up our account", "kick off",
                   "training session"),
    "delivery_status": ("when will", "any eta", "status update", "any update", "timeline for"),
    "account_change": ("add a user", "remove a user", "change the email", "extra seat",
                       "transfer ownership"),
    "feature_request": ("feature request", "would be great if", "can you add", "roadmap",
                        "support for"),
}

#: Transfer-shaped, not anger-shaped. "Unacceptable" is a sentiment and belongs to
#: `derived.sentiment`; the corpus's escalation is defined by an unaccepted REQUEST for someone
#: else, and matching anger would fill the type with furious customers nobody was asked to hand
#: over — which is the compromise `escalation-requested.yaml` refuses in its own words.
ESCALATION_PHRASES: tuple[str, ...] = (
    "your manager", "a manager", "speak to a supervisor", "your supervisor", "escalate",
    "escalation", "someone more senior", "more senior", "head of support", "account manager",
    "take this further", "speak to someone else", "put me through to",
)

#: Said by US, outbound. The corpus's `workaround_provided`, in the only observable form an email
#: tenant has: we told them how to keep working while the fault remains.
WORKAROUND_PHRASES: tuple[str, ...] = (
    "as a workaround", "a workaround", "in the meantime", "temporary fix", "temporarily",
    "for now you can", "until we fix", "until this is fixed", "interim", "stopgap",
)

#: The closing edge. Wired now so the day a fix email lands the situation closes itself — and on
#: an email-only tenant it fires only if somebody happens to write, which is precisely the
#: behaviour the situation exists to prompt.
FIX_PHRASES: tuple[str, ...] = (
    "now fixed", "the fix is live", "deployed a fix", "released a fix", "issue is resolved",
    "permanently fixed", "rolled out the fix", "patch is live", "shipped the fix",
)

#: `workaround.cost` — the corpus's central demand, that "a one-time configuration change and a
#: manual step performed every morning" stop being recorded identically. Written ONLY when
#: exactly one family matches; an ambiguous quote leaves the field absent so `missing` reports it
#: rather than a guess being filed as a value.
_COST_MARKERS: dict[str, tuple[str, ...]] = {
    "recurring_manual": ("every time", "each time", "every morning", "each morning",
                         "every day", "manually", "by hand", "each week"),
    "one_time": ("one-off", "one off", "just once", "a one time", "single change"),
    "degraded_capability": ("without using", "turn off", "disable", "not able to use",
                            "limited to", "instead of the"),
}

_WORD = re.compile(r"[a-z0-9]+")


def classify_intent(head: str) -> str | None:
    """The topic a message is about, or None when the lexicon does not recognise it.

    None is NOT a bucket. An "unclassified" group would join a password reset to an invoice
    query because neither matched, which is the fragmentation failure running in reverse and far
    worse: it manufactures a repeat contact out of two unrelated messages. Unrecognised text
    simply does not participate, and the systematic undercount that causes is declared in
    `missing`.

    Ties break on declaration order so the same message classifies the same way on every worker —
    Atlas Rule 03's reason, applied to a lexicon rather than a float.
    """
    low = (head or "").lower()
    best, best_hits = None, 0
    for intent, phrases in INTENT_LEXICON.items():
        hits = sum(1 for p in phrases if p in low)
        if hits > best_hits:
            best, best_hits = intent, hits
    return best


def _matches(head: str, phrases: tuple[str, ...]) -> str | None:
    """The first phrase present, or None. Returned rather than a bool so the situation can carry
    WHICH words it read — a finding whose evidence is 'the lexicon fired' is not evidence."""
    low = (head or "").lower()
    for p in phrases:
        if p in low:
            return p
    return None


def reads_as_escalation(head: str) -> str | None:
    return _matches(head, ESCALATION_PHRASES)


def reads_as_workaround(head: str) -> str | None:
    return _matches(head, WORKAROUND_PHRASES)


def reads_as_fix(head: str) -> str | None:
    return _matches(head, FIX_PHRASES)


def clause_around(head: str, phrase: str, *, limit: int = 240) -> str:
    """The sentence a matched phrase sits in.

    Carrying the whole message head instead would put three paragraphs of unrelated mail into
    `escalation.ask_text` and `workaround.description`, where a reader is looking for the words
    that caused the finding. Carrying the bare phrase would be worse — "your manager" is not
    evidence, and a finding whose evidence is "the lexicon fired" cannot be checked by anybody.
    The text is already PII-masked by `capture/preprocess`, the same material every other
    `evidence.text` in the graph holds.
    """
    low = (head or "").lower()
    at = low.find((phrase or "").lower())
    if at < 0:
        return (head or "")[:limit].strip()
    start = max((low.rfind(c, 0, at) for c in ".!?\n"), default=-1) + 1
    ends = [e for e in (low.find(c, at) for c in ".!?\n") if e >= 0]
    return head[start:(min(ends) + 1 if ends else len(head))].strip()[:limit]


def workaround_cost(head: str) -> str | None:
    """one_time | recurring_manual | degraded_capability, or None when the text does not say."""
    low = (head or "").lower()
    hit = [cost for cost, markers in _COST_MARKERS.items() if any(m in low for m in markers)]
    return hit[0] if len(hit) == 1 else None


# ── small numeric helpers ────────────────────────────────────────────────────────────────────

def percentile_bp(population: list[float], value: float) -> int:
    """Where `value` sits in `population`, in basis points.

    Python rather than `percentile_cont`, which is Postgres-only — the same constraint
    `open_loops.py` records when it uses CASE instead of `greatest()`. Ties count as half so a
    population of identical ages reports the middle rather than everyone at the top.
    """
    if not population:
        return 0
    below = sum(1 for v in population if v < value)
    ties = sum(1 for v in population if v == value)
    return int(round(10000 * (below + ties / 2.0) / len(population)))


def _pct(population: list[float], q: float) -> float:
    """The q-th percentile by nearest rank. Distribution, never the average: the finding is in
    the tail and a mean is how a failing segment stays hidden (`queue-period-review.yaml`)."""
    if not population:
        return 0.0
    ordered = sorted(population)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return float(ordered[idx])


def _shingles(head: str, n: int = 3) -> set[str]:
    toks = _WORD.findall((head or "").lower())
    return {" ".join(toks[i:i + n]) for i in range(max(0, len(toks) - n + 1))}


#: Comparing every pair is quadratic and the answer stops moving long before the mailbox does.
_REUSE_SAMPLE = 12


def answer_reuse_bp(replies: list[str]) -> int:
    """How much our answers to one topic repeat themselves, 0–10000.

    HIGH means a settled answer exists and we retype it — publish it. LOW means every reply is
    improvised — the answer does not exist yet, so write it. This is a SURROGATE and not the
    corpus's discriminator, which is whether the customer found an article and rejected it. That
    needs a help-centre index nobody has connected, and the difference between the two is exactly
    the difference between "write the article" and "fix findability" — so the real discriminator
    stays visibly absent in `missing` instead of being faked by this number.

    Integer basis points per Atlas Rule 03: floats do not hash reproducibly across machines, so a
    threshold met on one worker would be missed on another.
    """
    sets = [s for s in (_shingles(r) for r in replies[:_REUSE_SAMPLE]) if s]
    if len(sets) < 2:
        return 0
    scores = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            union = sets[i] | sets[j]
            scores.append(len(sets[i] & sets[j]) / len(union) if union else 0.0)
    return int(round(10000 * (sum(scores) / len(scores))))


def _days(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return round((a - b).total_seconds() / 86400.0, 3)


def _parse_ts(value: str | None) -> datetime | None:
    """A `thread.last_inbound` fact back into a datetime. Facts are stored as ISO strings, and a
    silent None here would read as 'they have never written', which is the opposite of the truth
    for the one thread whose format we failed to parse."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().strip('"'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ── the snapshot every reading shares ────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Message:
    """One captured message, reduced to what the seven readings need."""

    event_id: str
    thread_id: str
    at: datetime
    sender: str
    internal: bool
    recipients: tuple[str, ...]
    head: str


@dataclass(frozen=True, slots=True)
class Loop:
    """One row of the open-loop ledger — an ask somebody made that we have not answered."""

    loop_id: str
    subject_node_id: str
    kind: str
    thread_id: str | None
    status: str
    opened_at: datetime
    closed_at: datetime | None
    ask_count: int


@dataclass(frozen=True, slots=True)
class Desk:
    """Everything gathered once, so seven readings cannot disagree about the same mailbox.

    `we_know_who_we_are` is not decoration. `runner._internal_emails` returns an EMPTY set on a
    self-serve tenant that never filled `org_seats`, and an empty "us" set does not fail loudly:
    `sender not in internal` passes for every message, so every thread reads as never answered and
    every colleague reads as an inbound stranger. Two of these readings — the first-response clock
    and the escalation acceptance — are direction-critical, and they refuse to run rather than
    mint a mailbox full of false findings.
    """

    org_id: str
    now: datetime
    internal: frozenset[str]
    internal_domains: frozenset[str]
    messages: tuple[Message, ...] = ()
    #: thread → its TRUE first message, read without the snapshot's date bound. A thread that
    #: began before the window is skipped by the first-response clock rather than dated from the
    #: earliest message we happen to hold, which would put a fabricated deadline under it.
    thread_first: dict[str, datetime] = field(default_factory=dict)
    thread_conn: dict[str, str] = field(default_factory=dict)
    thread_node: dict[str, str] = field(default_factory=dict)
    thread_facts: dict[str, dict[str, str]] = field(default_factory=dict)
    person_node: dict[str, str] = field(default_factory=dict)
    company_of: dict[str, str] = field(default_factory=dict)
    node_name: dict[str, str] = field(default_factory=dict)
    loops: tuple[Loop, ...] = ()
    mailboxes: dict[str, str] = field(default_factory=dict)
    account_rate: dict[str, float] = field(default_factory=dict)
    merge_pressure: dict[str, int] = field(default_factory=dict)
    policy: ResponsePolicy = ResponsePolicy()

    @property
    def we_know_who_we_are(self) -> bool:
        return bool(self.internal)

    def account_of(self, person_node: str) -> str:
        """The company this person works at, or the person themself. Rolling up matters: the
        second escalation from a different contact at one customer is the same event continuing,
        and an account-level repeat by two people is one finding."""
        return self.company_of.get(person_node, person_node)

    def thread_fact(self, thread_id: str, field_name: str) -> str | None:
        node = self.thread_node.get(thread_id)
        return self.thread_facts.get(node, {}).get(field_name) if node else None

    def ball(self, thread_id: str) -> str | None:
        return self.thread_fact(thread_id, "thread.ball_in_court")

    def by_thread(self) -> dict[str, list[Message]]:
        """Threads in first-message order, messages within a thread in `(at, event_id)` order.

        Both halves are load-bearing for the replayability this module claims. Insertion order
        decides the dict's key order, so it is only stable because `gather` orders its query; and
        the tie-break on `event_id` is what makes the per-thread sort total — two messages sharing
        a timestamp would otherwise keep whatever order the scan produced, and "the first internal
        sender on this thread" is the incumbent test the escalation reading depends on.
        """
        out: dict[str, list[Message]] = {}
        for m in self.messages:
            out.setdefault(m.thread_id, []).append(m)
        for msgs in out.values():
            msgs.sort(key=lambda m: (m.at, m.event_id))
        return out


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing worth opening a situation about, and everything needed to write it."""

    anchor: str
    canonical_key: str
    display_name: str
    correlation_id: str
    facts: tuple[tuple[str, object, str], ...]
    inputs: dict
    missing: tuple[str, ...]
    coverage_cap_pct: int
    event_count: int
    source_count: int
    last_seen_at: datetime | None
    first_seen_at: datetime | None
    identity_node: str | None = None
    concerns_node: str | None = None


# ── reading 1 · the first-response clock ─────────────────────────────────────────────────────

def read_first_response(desk: Desk) -> list[Finding]:
    """A request arrived and nobody has replied inside the stated policy.

    "Request" is a Gmail thread whose EARLIEST visible message is inbound, which is the honest
    floor: it merges two requests raised in one thread, splits one raised across two, and gives a
    reopened conversation no second clock. A thread that started before the snapshot is skipped
    entirely rather than dated from the first message we happen to hold.
    """
    if not desk.we_know_who_we_are:
        return []
    out: list[Finding] = []
    for thread_id, msgs in desk.by_thread().items():
        node = desk.thread_node.get(thread_id)
        if not node or msgs[0].internal:
            continue                      # we started it: nobody is waiting on a first reply
        if desk.thread_first.get(thread_id, msgs[0].at) < msgs[0].at:
            continue                      # it began before the snapshot: its arrival is unknown
        opened_at = msgs[0].at
        replies = [m for m in msgs if m.internal and m.at > opened_at]
        target_at = advance_working_hours(opened_at, desk.policy)
        if replies or desk.now <= target_at:
            continue
        overdue_h = round((desk.now - target_at).total_seconds() / 3600.0, 2)
        out.append(Finding(
            anchor=ANCHOR_THREAD, canonical_key=f"thread:{thread_id}",
            display_name=desk.node_name.get(node) or f"Thread {thread_id[:12]}",
            correlation_id=f"corr_firstreply_{desk.org_id}_{thread_id}",
            facts=(
                ("response.opened_at", opened_at.isoformat(), "timestamp"),
                ("response.target_at", target_at.isoformat(), "timestamp"),
                # NEVER 'entitlement'. There is no per-customer target anywhere in this system,
                # and the word is what would turn a stated policy into a contractual claim.
                ("response.target_source", desk.policy.source, "enum"),
                ("response.channel", "email", "enum"),
                ("response.overdue_hours", overdue_h, "number"),
            ),
            inputs={"opened_at": opened_at.isoformat(), "target_at": target_at.isoformat(),
                    "overdue_hours": overdue_h, "policy_hours": desk.policy.hours,
                    "policy_source": desk.policy.source, "messages_on_thread": len(msgs),
                    "requester": msgs[0].sender,
                    "clock": "calendar hours across the stated working window; holidays unknown"},
            missing=_MISSING_FIRST_RESPONSE, coverage_cap_pct=_CAP_FIRST_RESPONSE,
            event_count=len(msgs), source_count=1,
            last_seen_at=msgs[-1].at, first_seen_at=opened_at, identity_node=node))
    return out


# ── reading 2 · one unmet ask, aging ─────────────────────────────────────────────────────────

def read_backlog_items(desk: Desk) -> list[Finding]:
    """An individual open item that has waited materially longer than comparable work here.

    Two properties the corpus insisted on and both survive. It needs NO promise — that is the
    whole point, because the items that age are precisely the ones nobody committed to, which is
    why `commitment_overdue` can never see them. And time-since-the-customer-wrote is carried
    SEPARATELY from time-since-open, because an old item being actively worked and an old item
    nobody has touched are different findings that share an age.

    THE TRAP THIS FILTER EXISTS FOR. `ASK_KINDS` includes `proposal_sent` and `next_step_agreed`,
    and `pipeline.py` files an outbound ask against OUR OWN subject, while `close_loops_for_reply`
    closes on the recipient — so a self-opened loop never closes and would inflate this backlog's
    size and age forever. Requiring the ball to be in our court on the item's own thread drops
    them, because an outbound message puts it in theirs.
    """
    open_loops = [lp for lp in desk.loops if lp.status == "open"]
    qualifying = [lp for lp in open_loops
                  if lp.thread_id and desk.ball(lp.thread_id) == "us"]
    if not qualifying:
        return []
    ages = [round((desk.now - lp.opened_at).total_seconds() / 86400.0, 3) for lp in qualifying]
    band = max(AGING_FLOOR_DAYS, AGING_BASELINE_MULT * reply_turnaround_days(desk))
    asks_per_thread: dict[str, int] = {}
    for lp in qualifying:
        asks_per_thread[lp.thread_id] = asks_per_thread.get(lp.thread_id, 0) + 1

    out: list[Finding] = []
    for lp, age in zip(qualifying, ages):
        pctl = percentile_bp(ages, age)
        if age < band and pctl < AGING_PERCENTILE_BP:
            continue
        last_in = _parse_ts(desk.thread_fact(lp.thread_id, "thread.last_inbound"))
        last_out = _parse_ts(desk.thread_fact(lp.thread_id, "thread.last_outbound"))
        facts = [
            ("backlog.opened_at", lp.opened_at.isoformat(), "timestamp"),
            ("backlog.age_days", age, "number"),
            ("backlog.waiting_on", "us", "enum"),
            ("backlog.open_asks", asks_per_thread[lp.thread_id], "number"),
            ("backlog.ask_repeats", lp.ask_count, "number"),
            ("backlog.age_percentile_bp", pctl, "number"),
        ]
        since_customer = _days(desk.now, last_in)
        since_touched = _days(desk.now, last_out)
        if since_customer is not None:
            facts.append(("backlog.days_since_customer", since_customer, "number"))
        if since_touched is not None:
            facts.append(("backlog.days_since_we_touched", since_touched, "number"))
        out.append(Finding(
            anchor=ANCHOR_BACKLOG_ITEM, canonical_key=f"backlog:{desk.org_id}:{lp.loop_id}",
            display_name=f"{lp.kind.replace('_', ' ')} · "
                         f"{desk.node_name.get(lp.subject_node_id) or 'a counterparty'}"[:120],
            correlation_id=f"corr_aging_{desk.org_id}_{lp.loop_id}",
            facts=tuple(facts),
            inputs={"loop_id": lp.loop_id, "ask_kind": lp.kind, "thread_id": lp.thread_id,
                    "age_days": age, "band_days": round(band, 3),
                    "age_percentile_bp": pctl, "ask_repeats": lp.ask_count,
                    "days_since_customer": since_customer,
                    "days_since_we_touched": since_touched,
                    "comparable_population": len(ages),
                    "comparable_scope": "every open item in this org, not in its queue",
                    "closure_means": "we replied on the thread, not that it was resolved"},
            missing=_MISSING_AGING, coverage_cap_pct=_CAP_AGING,
            event_count=lp.ask_count, source_count=1,
            last_seen_at=last_in or lp.opened_at, first_seen_at=lp.opened_at,
            identity_node=lp.subject_node_id))
    return out


def reply_turnaround_days(desk: Desk) -> float:
    """This org's own norm for how long an ask stays open — median, over closed loops.

    Named for what it MEASURES. `close_loops_for_reply` closes every open loop on a thread the
    moment we send any outbound message on it, so a holding reply ("looking into it") closes the
    loop. This is therefore a time-to-REPLY distribution and calling it resolution time would put
    a wrong word under every band derived from it. Zero when there is no history: the caller's
    floor then decides, which is the honest cold start.
    """
    spans = [round((lp.closed_at - lp.opened_at).total_seconds() / 86400.0, 3)
             for lp in desk.loops
             if lp.status == "closed" and lp.closed_at and lp.closed_at >= lp.opened_at]
    return float(statistics.median(spans)) if spans else 0.0


# ── reading 3 · an escalation nobody has accepted ────────────────────────────────────────────

def read_escalations(desk: Desk) -> list[Finding]:
    """They asked for somebody else, and nobody has taken it.

    The defining property, which is why this cannot be `unanswered_email`: the interval stays
    open ACROSS replies. Answering faster from the same person does not close it; only a named
    person taking it over does. So it is deliberately kept out of `ASK_KINDS` — an outbound reply
    must not close it — and out of `DORMANT_AFTER_DAYS`, because an unaccepted escalation going
    quiet is the failure and not the resolution.

    ACCEPTANCE IS INFERRED, and the corpus rates it the one thing in this domain that should not
    be: a new internal sender appearing on the thread after the raise. It is wrong in both
    directions — a receiver who takes over internally while the original owner keeps writing
    scores as never having accepted, and a colleague chiming in scores as an acceptance — so
    `escalation.receiver_named` is reported and `time_to_accept` is carried as evidence, never as
    a rate.
    """
    if not desk.we_know_who_we_are:
        return []
    out: list[Finding] = []
    for thread_id, msgs in desk.by_thread().items():
        raise_msg = next(
            (m for m in msgs if not m.internal and reads_as_escalation(m.head)), None)
        if raise_msg is None:
            continue
        requester = desk.person_node.get(raise_msg.sender)
        if not requester:
            continue
        account = desk.account_of(requester)
        before = {m.sender for m in msgs if m.internal and m.at <= raise_msg.at}
        # THE INCUMBENT, and leaving it out was a real defect this module's tests caught. On a
        # thread the customer started, nobody internal has written before the raise — so "an
        # internal sender new to this thread" matched the ORIGINAL OWNER's first reply and scored
        # it as an acceptance. That is the precise inversion the corpus warns about: a reply from
        # the current owner is exactly what the customer has already rejected, and treating it as
        # a transfer would close every escalation with the answer that caused it.
        incumbent = next((m.sender for m in msgs if m.internal), None)
        receiver_msg = next((m for m in msgs if m.internal and m.at > raise_msg.at
                             and m.sender not in before and m.sender != incumbent), None)
        receiver_node = desk.person_node.get(receiver_msg.sender) if receiver_msg else None
        if receiver_msg is not None and receiver_node:
            continue                       # somebody new took it: this raise is over
        age_days = (desk.now - raise_msg.at).total_seconds() / 86400.0
        status = "stale" if age_days >= ESCALATION_STALE_DAYS else "requested"
        phrase = _matches(raise_msg.head, ESCALATION_PHRASES) or ""
        quote = clause_around(raise_msg.head, phrase)
        out.append(Finding(
            anchor=ANCHOR_ESCALATION,
            # THE THREAD IS PART OF THE IDENTITY, and leaving it out was a silent clobber.
            # `escalation:{org}:{account}:{date}` is not unique: two customers at one company
            # asking for a manager on the same day — or one customer raising on two threads —
            # produced two Findings sharing a canonical_key AND a correlation_id, so both wrote
            # the same node and the same situation row and whichever the scan yielded last
            # decided which `escalation.ask_text` and `escalation.thread_id` survived. One real
            # unaccepted escalation was overwritten by another, and nothing errored.
            #
            # This does NOT weaken the corpus's `scope: account`. The anchor's unit is one RAISE
            # ("from the ask to the acceptance") and a raise lives on a thread — acceptance is
            # read from who writes on THAT thread, so two raises cannot share one acceptance
            # state. The account roll-up the situation file asks for is carried where it belongs
            # and where order cannot affect it: `escalation.account_node_id`, the `concerns` edge
            # to the account, and the display name.
            canonical_key=f"escalation:{desk.org_id}:{account}:{thread_id}:"
                          f"{raise_msg.at.date().isoformat()}",
            display_name=f"Escalation · {desk.node_name.get(account) or 'a customer'}"[:120],
            correlation_id=f"corr_escalation_{desk.org_id}_{account}_{thread_id}_"
                           f"{raise_msg.at.date().isoformat()}",
            facts=(
                ("escalation.requested_at", raise_msg.at.isoformat(), "timestamp"),
                # Never defaulted to customer_initiated. Mail sees the customer's raise well and
                # an owner deciding "this is beyond me" not at all, so the share of the two is
                # uninterpretable and the KPI built on it must stay suppressed rather than
                # computed from a denominator that is missing.
                ("escalation.origin", "customer_initiated", "enum"),
                ("escalation.ask_text", quote, "string"),
                ("escalation.thread_id", thread_id, "string"),
                ("escalation.account_node_id", account, "string"),
                ("escalation.requester_node_id", requester, "string"),
                ("escalation.receiver_named", False, "boolean"),
                ("escalation.status", status, "enum"),
            ),
            inputs={"thread_id": thread_id, "requested_at": raise_msg.at.isoformat(),
                    "matched_phrase": phrase, "age_days": round(age_days, 3), "status": status,
                    "origin": "customer_initiated",
                    "acceptance": "no internal sender new to this thread has written since",
                    "internal_senders_before": sorted(before)},
            missing=_MISSING_ESCALATION, coverage_cap_pct=_CAP_ESCALATION,
            event_count=len([m for m in msgs if m.at >= raise_msg.at]), source_count=1,
            last_seen_at=msgs[-1].at, first_seen_at=raise_msg.at,
            identity_node=requester, concerns_node=account if account != requester else None))
    return out


# ── the intent lane, shared by readings 4 and 5 ──────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class _Ask:
    person: str
    account: str
    intent: str
    thread_id: str
    at: datetime


def _asks(desk: Desk) -> list[_Ask]:
    """Every inbound message the lexicon could name a topic for, at most one per thread per
    topic. Deduping by thread is what makes the ordinal count CONTACTS rather than messages — six
    emails in one conversation are one contact about one thing."""
    seen: set[tuple[str, str, str]] = set()
    out: list[_Ask] = []
    for m in sorted(desk.messages, key=lambda m: m.at):
        if m.internal:
            continue
        person = desk.person_node.get(m.sender)
        intent = classify_intent(m.head)
        if not person or not intent:
            continue
        key = (person, intent, m.thread_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(_Ask(person=person, account=desk.account_of(person), intent=intent,
                        thread_id=m.thread_id, at=m.at))
    return out


def repeat_window_days(desk: Desk, account_node: str) -> int:
    """Three of this account's own inter-contact gaps, clamped.

    The corpus's exact ask — "a weekly contact is normal for some accounts and alarming for
    others" — answered with the `contact_rate_per_account` baseline `reason/baselines.py` already
    writes. A cold or absent baseline falls back to the period window so the two window reads in
    Layer 2 agree with each other.
    """
    rate = desk.account_rate.get(account_node, 0.0)
    if rate <= 0:
        return WINDOW_DAYS
    span = int(round(REPEAT_GAPS * 7.0 / max(rate, 0.1)))
    return max(REPEAT_WINDOW_MIN_DAYS, min(REPEAT_WINDOW_MAX_DAYS, span))


def read_repeat_contacts(desk: Desk) -> list[Finding]:
    """The same person is back about the same thing, and the earlier one WAS answered.

    That gate is the whole situation. Repeat contact is the exact opposite of unanswered mail:
    every prior contact got a reply, which is what makes it interesting and why it is invisible on
    every dashboard a support team already owns. A group whose prior contact was never answered is
    left alone here — it is unanswered mail, and it belongs to that reading.

    The ordinal is a FLOOR, never an exact count. A lexicon that fails to recognise one of the
    phrasings splits the group and the situation quietly does not fire, so `inputs` says so rather
    than presenting "3rd contact" as a fact.
    """
    grouped: dict[tuple[str, str], list[_Ask]] = {}
    for ask in _asks(desk):
        grouped.setdefault((ask.person, ask.intent), []).append(ask)

    out: list[Finding] = []
    for (person, intent), asks in grouped.items():
        account = asks[0].account
        window = repeat_window_days(desk, account)
        recent = [a for a in asks if (desk.now - a.at).days <= window]
        if len(recent) < 2:
            continue
        prior, newest = recent[:-1], recent[-1]
        if not all(desk.ball(a.thread_id) == "them" for a in prior):
            continue                       # somebody is still owed a reply: not this reading
        gaps = [round((b.at - a.at).total_seconds() / 86400.0, 2)
                for a, b in zip(recent, recent[1:])]
        out.append(Finding(
            anchor=ANCHOR_CONTACT_INTENT,
            canonical_key=f"askrepeat:{desk.org_id}:{person}:{intent}",
            display_name=f"{desk.node_name.get(person) or 'A contact'} · "
                         f"{intent.replace('_', ' ')}"[:120],
            correlation_id=f"corr_repeat_{desk.org_id}_{person}_{intent}",
            facts=(
                ("repeat.intent", intent, "enum"),
                ("repeat.ordinal", len(recent), "number"),
                ("repeat.window_days", window, "number"),
                ("repeat.first_contact_at", recent[0].at.isoformat(), "timestamp"),
                ("repeat.latest_contact_at", newest.at.isoformat(), "timestamp"),
                ("repeat.prior_answered", True, "boolean"),
            ),
            inputs={"intent": intent, "ordinal": len(recent), "window_days": window,
                    "thread_ids": [a.thread_id for a in recent],
                    "gap_days_between_contacts": gaps,
                    "account_baseline_rate": desk.account_rate.get(account),
                    "prior_answered": True,
                    "ordinal_is": "a floor — an unrecognised phrasing splits the group and "
                                  "under-counts rather than over-counting",
                    "intent_source": "a closed lexicon over the customer's own wording, "
                                     "not a requester-supplied taxonomy"},
            missing=_MISSING_REPEAT, coverage_cap_pct=_CAP_REPEAT,
            event_count=len(recent), source_count=1,
            last_seen_at=newest.at, first_seen_at=recent[0].at, identity_node=person,
            concerns_node=account if account != person else None))
    return out


def read_knowledge_gaps(desk: Desk) -> list[Finding]:
    """Several different people, at several different accounts, all asking the same thing — and
    all of them answered.

    "All of them answered" is the corpus's whole point and the discriminator against unanswered
    mail: this is not a queue failure, it is content that does not exist or cannot be found. The
    part that CANNOT be recovered is which of those two it is, because that needs help-centre
    search telemetry nobody has connected, and commissioning a duplicate article is the specific
    harm the corpus warns about. `knowledge.published_answer_seen` is therefore never written —
    it is the honest placeholder that keeps the real discriminator visibly absent in `missing`
    instead of silently faked, and it flips only when such a source is connected.
    """
    window_start = desk.now - timedelta(days=WINDOW_DAYS)
    prev_start = window_start - timedelta(days=WINDOW_DAYS)
    replies_by_thread: dict[str, list[str]] = {}
    for m in desk.messages:
        if m.internal and m.head:
            replies_by_thread.setdefault(m.thread_id, []).append(m.head)

    grouped: dict[str, list[_Ask]] = {}
    for ask in _asks(desk):
        grouped.setdefault(ask.intent, []).append(ask)

    out: list[Finding] = []
    for intent, asks in grouped.items():
        this_window = [a for a in asks if a.at >= window_start]
        prev_window = [a for a in asks if prev_start <= a.at < window_start]
        askers = {a.person for a in this_window}
        accounts = {a.account for a in this_window}
        answered = sum(1 for a in this_window if desk.ball(a.thread_id) == "them")
        if (len(askers) < KGAP_MIN_ASKERS or len(accounts) < KGAP_MIN_ACCOUNTS
                or answered < len(askers) or len(this_window) < len(prev_window)):
            continue
        replies = [h for a in this_window for h in replies_by_thread.get(a.thread_id, [])]
        reuse = answer_reuse_bp(replies)
        out.append(Finding(
            anchor=ANCHOR_TOPIC, canonical_key=f"topic:{desk.org_id}:{intent}",
            display_name=intent.replace("_", " ").title()[:120],
            correlation_id=f"corr_kgap_{desk.org_id}_{intent}",
            facts=(
                ("knowledge.intent", intent, "enum"),
                ("knowledge.distinct_askers", len(askers), "number"),
                ("knowledge.distinct_accounts", len(accounts), "number"),
                ("knowledge.asks_this_window", len(this_window), "number"),
                ("knowledge.asks_prev_window", len(prev_window), "number"),
                ("knowledge.answered_count", answered, "number"),
                ("knowledge.answer_reuse_bp", reuse, "number"),
                ("knowledge.first_asked_at", min(a.at for a in asks).isoformat(), "timestamp"),
                ("knowledge.last_asked_at",
                 max(a.at for a in this_window).isoformat(), "timestamp"),
            ),
            inputs={"intent": intent, "window_days": WINDOW_DAYS,
                    "distinct_askers": len(askers), "distinct_accounts": len(accounts),
                    "asks_this_window": len(this_window), "asks_prev_window": len(prev_window),
                    "answered_count": answered, "answer_reuse_bp": reuse,
                    "answer_reuse_means": "how much OUR replies repeat themselves — high means a "
                                          "settled answer exists and should be published, low "
                                          "means none exists yet",
                    "published_answer_seen": None,
                    "deflection_rate": None,
                    "why_no_deflection_rate": "every contact here arrived by mail, so the "
                                              "denominator does not exist"},
            missing=_MISSING_KNOWLEDGE, coverage_cap_pct=_CAP_KNOWLEDGE,
            event_count=len(this_window), source_count=1,
            last_seen_at=max(a.at for a in this_window),
            first_seen_at=min(a.at for a in asks)))
    return out


# ── reading 6 · one mailbox taking in more than it clears ────────────────────────────────────

def read_mailbox_load(desk: Desk) -> list[Finding]:
    """Arrivals against closures, plus the shape of the wait. Per connected mailbox.

    The observable that matters is AGE, not SIZE — a count is the one measure that cherry-picking
    improves, because agents take the quick well-written items, the count falls, and the people
    who have waited longest keep waiting. So the oldest open item and the age distribution are the
    numbers carried, and the average is never reported.

    The second rule fires on the anti-pattern the corpus is actually about: a pile that is
    SHRINKING while getting OLDER, which every count-based signal reads as improvement and which
    is the precise opposite of it.

    WHAT THIS IS NOT. It is not a queue. There is no queue object, no assignee and no rota; the
    only honest partition on a mail tenant is one connected mailbox, and on a founder inbox that
    degenerates to the whole org. Every string this produces says "this mailbox".
    """
    window_start = desk.now - timedelta(days=WINDOW_DAYS)
    prev_start = window_start - timedelta(days=WINDOW_DAYS)
    out: list[Finding] = []
    for connection_id, address in sorted(desk.mailboxes.items()):
        mine = [lp for lp in desk.loops
                if lp.thread_id and desk.thread_conn.get(lp.thread_id) == connection_id]
        if not mine:
            continue
        opened = sum(1 for lp in mine if lp.opened_at >= window_start)
        opened_prev = sum(1 for lp in mine if prev_start <= lp.opened_at < window_start)
        closed = sum(1 for lp in mine if lp.closed_at and lp.closed_at >= window_start)
        closed_prev = sum(1 for lp in mine
                          if lp.closed_at and prev_start <= lp.closed_at < window_start)
        # `status='open'` with a `closed_at` already set is the ledger's own record of a reopen:
        # `record_ask` reopens a closed loop when the customer asks again. It is the counterweight
        # the corpus demands be read as a pair with closures — bulk closure of aged items is the
        # commonest cosmetic response to this situation and it returns as reopens.
        reopened = sum(1 for lp in mine if lp.status == "open" and lp.closed_at is not None)
        # Waiting-on-us only, for the same reason `read_backlog_items` filters: a self-opened
        # outbound ask never closes and would inflate this backlog's age forever.
        live = [lp for lp in mine if lp.status == "open" and desk.ball(lp.thread_id) == "us"]
        ages = [round((desk.now - lp.opened_at).total_seconds() / 86400.0, 3) for lp in live]
        open_now = len(live)
        open_prev = sum(1 for lp in mine
                        if lp.opened_at < window_start
                        and (lp.closed_at is None or lp.closed_at >= window_start))
        arrivals_before = _prior_window_arrivals(mine, window_start)
        baseline = float(statistics.median(arrivals_before)) if arrivals_before else 0.0

        # PRECOMPUTED, and forced rather than cosmetic: the predicate grammar compares a path to a
        # LITERAL and has no fact-to-fact form, so Layer 4 cannot divide two of these facts. If
        # Layer 2 does not materialise the ratio, no authored rule can ever express it.
        flow_ratio = round(opened / float(max(1, closed)), 3)
        vs_baseline = round(opened / float(max(1.0, baseline)), 3)
        delta = open_now - open_prev
        oldest = max(ages) if ages else 0.0
        p50, p90 = _pct(ages, 0.5), _pct(ages, 0.9)
        over_14 = sum(1 for a in ages if a > QUIET_DAYS)
        awaiting = [t for t, node in desk.thread_node.items()
                    if desk.thread_conn.get(t) == connection_id
                    and desk.thread_facts.get(node, {}).get("thread.ball_in_court") == "us"]
        awaiting_oldest = max(
            (d for d in (_days(desk.now, _parse_ts(desk.thread_fact(t, "thread.last_inbound")))
                         for t in awaiting) if d is not None), default=0.0)

        fired = _mailbox_rules(flow_ratio=flow_ratio, vs_baseline=vs_baseline, p50=p50, p90=p90,
                               oldest=oldest, delta=delta, reopened=reopened, closed=closed)
        facts = (
            ("mailbox.loops_opened", opened, "number"),
            ("mailbox.loops_opened_prev", opened_prev, "number"),
            ("mailbox.loops_closed", closed, "number"),
            ("mailbox.loops_closed_prev", closed_prev, "number"),
            ("mailbox.loops_open_now", open_now, "number"),
            ("mailbox.loops_open_prev", open_prev, "number"),
            ("mailbox.loops_reopened", reopened, "number"),
            ("mailbox.backlog_oldest_days", oldest, "number"),
            ("mailbox.backlog_age_p50_days", p50, "number"),
            ("mailbox.backlog_age_p90_days", p90, "number"),
            ("mailbox.backlog_over_14d", over_14, "number"),
            ("mailbox.threads_awaiting_us", len(awaiting), "number"),
            ("mailbox.threads_awaiting_us_oldest_days", awaiting_oldest, "number"),
            ("mailbox.loops_opened_baseline", round(baseline, 3), "number"),
            ("mailbox.flow_ratio", flow_ratio, "number"),
            ("mailbox.arrival_vs_baseline", vs_baseline, "number"),
            ("mailbox.backlog_delta", delta, "number"),
            ("mailbox.reply_turnaround_days", round(reply_turnaround_days(desk), 3), "number"),
        )
        if not fired:
            continue
        out.append(Finding(
            anchor=ANCHOR_MAILBOX, canonical_key=f"mailbox:{desk.org_id}:{connection_id}",
            display_name=f"Mailbox {address}"[:120] if address else "A connected mailbox",
            correlation_id=f"corr_mailbox_{desk.org_id}_{connection_id}",
            facts=facts,
            inputs={"window_days": WINDOW_DAYS, "rules_fired": fired,
                    "partition": "one connected mailbox — not a queue, and nobody owns it",
                    **{f: v for f, v, _ in facts}},
            missing=_MISSING_MAILBOX, coverage_cap_pct=_CAP_MAILBOX,
            event_count=opened + closed, source_count=1,
            last_seen_at=desk.now, first_seen_at=window_start))
    return out


def _prior_window_arrivals(loops: list[Loop], window_start: datetime,
                           windows: int = 6) -> list[int]:
    """Arrivals in each of the N windows BEFORE this one — this mailbox's own normal, from the
    same scan. A constant threshold would call a busy team overloaded and a quiet one healthy."""
    out = []
    for n in range(1, windows + 1):
        hi = window_start - timedelta(days=WINDOW_DAYS * (n - 1))
        lo = window_start - timedelta(days=WINDOW_DAYS * n)
        out.append(sum(1 for lp in loops if lo <= lp.opened_at < hi))
    return out


def _mailbox_rules(*, flow_ratio: float, vs_baseline: float, p50: float, p90: float,
                   oldest: float, delta: int, reopened: int, closed: int) -> list[str]:
    """Which of the three shapes is present. Named, so the situation carries WHY it opened."""
    fired = []
    if flow_ratio >= 1.2 and vs_baseline >= 1.2 and p90 >= 14 and oldest >= 21:
        fired.append("arrivals_outrunning_closures_with_a_calcified_tail")
    if delta <= 0 and oldest >= 21 and p50 >= 7:
        fired.append("shrinking_while_getting_older")
    if reopened >= 3 and closed >= 1:
        fired.append("closures_that_did_not_hold")
    return fired


# ── reading 7 · a customer living on a workaround ────────────────────────────────────────────

def read_workarounds(desk: Desk) -> list[Finding]:
    """We handed them a temporary way to keep working, the fault is still there, and it has gone
    quiet.

    The highest-value action the corpus names — "the thing you reported is fixed, you can stop
    doing the workaround" — CANNOT fire, because nothing tells us the fix shipped. The closing
    edge is wired anyway: the day somebody emails the customer about the fix, this closes itself.
    Until then the only card available is the second-best one, which is also the one the situation
    exists to prompt: this person has been on a workaround for N days and has heard nothing.

    "Resolved" here is inferred from SILENCE, and a thread that went quiet because the customer
    gave up is indistinguishable from one that closed on a workaround. That is declared, not
    hidden — the whole precision of this reading rests on one lexicon match with no corroborating
    system record.
    """
    out: list[Finding] = []
    threads = desk.by_thread()
    provided: dict[str, tuple[Message, str]] = {}
    fixed: dict[str, datetime] = {}
    touched: dict[str, datetime] = {}
    for thread_id, msgs in threads.items():
        counterparties = {m.sender for m in msgs if not m.internal}
        for m in msgs:
            # Everyone this message involved, so "the conversation has gone quiet" is measured
            # against the person rather than against one thread they happen to be on.
            for email in {m.sender} | set(m.recipients) | (
                    counterparties if m.internal and not m.recipients else set()):
                node = desk.person_node.get(email)
                if node:
                    touched[node] = max(touched.get(node, m.at), m.at)
            if not m.internal:
                continue
            work, fix = reads_as_workaround(m.head), reads_as_fix(m.head)
            if not work and not fix:
                continue
            # `recipients` is NULL on events captured before the column existed, so fall back to
            # whoever else is on the thread rather than dropping the finding entirely.
            for email in (set(m.recipients) or counterparties):
                node = desk.person_node.get(email)
                if not node:
                    continue
                if work:
                    held = provided.get(node)
                    if held is None or m.at > held[0].at:
                        provided[node] = (m, work)
                if fix:
                    fixed[node] = max(fixed.get(node, m.at), m.at)

    for node, (msg, phrase) in provided.items():
        if fixed.get(node) and fixed[node] > msg.at:
            continue                       # we told them it is fixed: this is over
        days_open = (desk.now - msg.at).total_seconds() / 86400.0
        if days_open < QUIET_DAYS:
            continue                       # still live support, not debt
        quiet_since = touched.get(node, msg.at)
        ball_thread = desk.ball(msg.thread_id)
        if (desk.now - quiet_since).total_seconds() / 86400.0 < QUIET_DAYS and ball_thread == "us":
            continue                       # the conversation is still moving
        facts = [
            ("workaround.provided_at", msg.at.isoformat(), "timestamp"),
            ("workaround.description", clause_around(msg.head, phrase), "string"),
            ("workaround.days_open", round(days_open, 3), "number"),
            ("workaround.quiet_since", quiet_since.isoformat(), "timestamp"),
        ]
        cost = workaround_cost(msg.head)
        if cost:
            facts.append(("workaround.cost", cost, "enum"))
        out.append(Finding(
            anchor=ANCHOR_WORKAROUND, canonical_key=f"workaround:{desk.org_id}:{node}",
            display_name=f"Workaround · {desk.node_name.get(node) or 'a customer'}"[:120],
            correlation_id=f"corr_workaround_{desk.org_id}_{node}",
            facts=tuple(facts),
            inputs={"workaround_provided_at": msg.at.isoformat(), "matched_phrase": phrase,
                    "workaround_cost": cost, "days_open": round(days_open, 3),
                    "quiet_since": quiet_since.isoformat(), "thread_id": msg.thread_id,
                    "fix_evidence": "none",
                    "resolution_is": "inferred from silence — a customer who gave up looks the "
                                     "same as one living happily on the workaround",
                    "blast_radius": None,
                    "why_no_blast_radius": "there is no issue record, so customers on the same "
                                           "defect cannot be joined"},
            missing=_MISSING_WORKAROUND, coverage_cap_pct=_CAP_WORKAROUND,
            event_count=1, source_count=1,
            last_seen_at=quiet_since, first_seen_at=msg.at, identity_node=node))
    return out


#: Anchor node type → the reading that fills it. The anchor is also the registry key a domain
#: declares to opt in, so this tuple is the complete list of what this module can mint.
READINGS: tuple[tuple[str, object], ...] = (
    (ANCHOR_THREAD, read_first_response),
    (ANCHOR_BACKLOG_ITEM, read_backlog_items),
    (ANCHOR_ESCALATION, read_escalations),
    (ANCHOR_CONTACT_INTENT, read_repeat_contacts),
    (ANCHOR_TOPIC, read_knowledge_gaps),
    (ANCHOR_MAILBOX, read_mailbox_load),
    (ANCHOR_WORKAROUND, read_workarounds),
)


def desk_domains() -> tuple[str, ...]:
    """Every domain that declares at least one of these anchors — asked of the registry rather
    than listed here, exactly as `periodic.period_domains` is. A domain named in Layer 2 would
    mean adding a domain requires editing Layer 2, and the registry exists precisely so it does
    not."""
    out: set[str] = set()
    for anchor, _ in READINGS:
        out.update(domains_declaring(anchor))
    return tuple(sorted(out))


# ── gather ───────────────────────────────────────────────────────────────────────────────────

def _internal(conn, org_id: str) -> tuple[frozenset[str], frozenset[str]]:
    """Who WE are — addresses and mail domains.

    `runner._internal_emails` answers the address half and is reused rather than restated. The
    DOMAIN half is added here because this module asks a question that one does not:
    `org_seats` is empty on a self-serve tenant, so a colleague replying on a customer's thread
    reads as an inbound stranger — which would make every escalation acceptance invisible and
    every answered thread read as unanswered.
    """
    from genios_engine.context.runner import _internal_emails

    class _Shim:                       # `_internal_emails` wants a store; it only uses .engine
        def __init__(self, engine):
            self.engine = engine

    emails = _internal_emails(_Shim(conn.engine), org_id)
    owner = conn.execute(text("select lower(email) from orgs where id=:o and email is not null"),
                         {"o": org_id}).scalar()
    domains = {owner.split("@", 1)[1]} if owner and "@" in owner else set()
    return frozenset(emails), frozenset(d for d in domains if d and "." in d)


def gather(store, org_id: str, *, now: datetime, policy: ResponsePolicy) -> Desk:
    """One bounded snapshot of the mailbox. One query per concept, never one per row — the same
    shape `refresh_situations` and `refresh_attention` already keep, for the same reason."""
    since = now - timedelta(days=LOOKBACK_DAYS)
    with store.engine.connect() as c:
        internal, internal_domains = _internal(c, org_id)
        addresses = sorted(internal)

        # The thread ENVELOPE, deliberately unbounded by date. Two columns per thread, so it is
        # cheap, and both answers are wrong if it is windowed: a backlog item older than the
        # snapshot would lose its mailbox and vanish from the load reading — which is precisely
        # the oldest end of the pile that reading exists to find — and a thread that began before
        # the window would be given the arrival time of the first message we happen to hold.
        thread_first, thread_conn = {}, {}
        for r in c.execute(text(
                "select parent_object_id as thread_id, min(occurred_at) as first_at, "
                "       min(connection_id) as connection_id from source_events "
                "where org_id=:o and parent_object_id is not null group by parent_object_id"),
                {"o": org_id}):
            thread_first[r.thread_id] = r.first_at
            if r.connection_id:
                thread_conn[r.thread_id] = r.connection_id

        # ORDER BY, and it is not cosmetic. Postgres returns an unordered set, so without this
        # `Desk.by_thread()` keys in whatever order the scan happened to produce and the seven
        # readings emit their findings in that order — which contradicts this module's own
        # docstring claim that "the same mailbox re-swept tomorrow produces the same seven
        # answers". `(occurred_at, event_id)` is TOTAL: the timestamp alone is not, because two
        # messages in one thread can share a second (a send and its own delivery receipt), and a
        # stable sort on a tied key preserves the arbitrary input order it was handed.
        rows = c.execute(text(
            "select se.event_id, se.parent_object_id as thread_id, se.occurred_at, "
            "       lower(coalesce(se.actor->>'email','')) as sender, "
            "       coalesce(se.recipients, cast('{}' as text[])) as recipients, "
            "       coalesce(substr(pc.clean_text, 1, :scan), '') as head "
            "from source_events se "
            "left join prepared_content pc "
            "  on pc.event_id = se.event_id and pc.org_id = se.org_id "
            "where se.org_id=:o and se.parent_object_id is not null "
            "  and se.occurred_at >= :since "
            "order by se.occurred_at, se.event_id"),
            {"o": org_id, "since": since, "scan": SCAN_CHARS}).fetchall()
        messages = []
        for r in rows:
            sender = (r.sender or "").strip()
            domain = sender.split("@", 1)[1] if "@" in sender else ""
            messages.append(Message(
                event_id=r.event_id, thread_id=r.thread_id, at=r.occurred_at, sender=sender,
                internal=bool(sender) and (sender in internal or domain in internal_domains),
                recipients=tuple(e.lower() for e in (r.recipients or []) if e),
                head=r.head or ""))

        nodes = c.execute(text(
            "select node_id, node_type, canonical_key, display_name from graph_nodes "
            "where org_id=:o and valid_to is null and node_type in ('thread','person','company')"),
            {"o": org_id}).fetchall()
        thread_node, person_node, node_name = {}, {}, {}
        for n in nodes:
            node_name[n.node_id] = n.display_name or ""
            if n.node_type == "thread" and (n.canonical_key or "").startswith("thread:"):
                thread_node[n.canonical_key.split("thread:", 1)[1]] = n.node_id
            elif n.node_type == "person" and n.canonical_key:
                person_node[n.canonical_key.lower()] = n.node_id

        thread_facts: dict[str, dict[str, str]] = {}
        for r in c.execute(text(
                "select subject_node_id, field, value #>> '{}' as v from graph_facts "
                "where org_id=:o and valid_to is null and status='active' "
                "  and field in ('thread.ball_in_court','thread.last_inbound',"
                "                'thread.last_outbound')"), {"o": org_id}):
            thread_facts.setdefault(r.subject_node_id, {})[r.field] = r.v

        company_of = {r.to_node_id: r.from_node_id for r in c.execute(text(
            "select from_node_id, to_node_id from graph_edges "
            "where org_id=:o and edge_type='works_at' and valid_to is null"), {"o": org_id})}
        # `works_at` is written person -> company by `pipeline.py`; the deal view walks it the
        # other way. Accept both rather than assume, or a whole tenant's roll-up is silently empty.
        company_of.update({r.from_node_id: r.to_node_id for r in c.execute(text(
            "select e.from_node_id, e.to_node_id from graph_edges e "
            "join graph_nodes n on n.org_id=e.org_id and n.node_id=e.to_node_id "
            "  and n.valid_to is null and n.node_type='company' "
            "where e.org_id=:o and e.edge_type='works_at' and e.valid_to is null"),
            {"o": org_id})})

        loops = tuple(Loop(loop_id=r.loop_id, subject_node_id=r.subject_node_id, kind=r.kind,
                           thread_id=r.thread_id, status=r.status, opened_at=r.opened_at,
                           closed_at=r.closed_at, ask_count=int(r.ask_count or 1))
                      for r in c.execute(text(
                          "select loop_id, subject_node_id, kind, thread_id, status, opened_at, "
                          "       closed_at, ask_count from open_loops where org_id=:o"),
                          {"o": org_id}))

        mailboxes = {r.connection_id: (r.external_account_id or "") for r in c.execute(text(
            "select connection_id, external_account_id from connections "
            "where org_id=:o and status='connected'"), {"o": org_id})}

        account_rate = {}
        for r in c.execute(text(
                "select key, value from baselines "
                "where org_id=:o and key like 'contact_rate_per_account:%' and not cold_start"),
                {"o": org_id}):
            account_rate[str(r.key).split(":", 1)[1]] = float(r.value)

        merge_pressure: dict[str, int] = {}
        for r in c.execute(text(
                "select left_node_id, right_node_id from merge_proposals "
                "where org_id=:o and status='open'"), {"o": org_id}):
            for node in (r.left_node_id, r.right_node_id):
                merge_pressure[node] = merge_pressure.get(node, 0) + 1

    return Desk(org_id=org_id, now=now, internal=frozenset(addresses),
                internal_domains=internal_domains, messages=tuple(messages),
                thread_first=thread_first, thread_conn=thread_conn,
                thread_node=thread_node, thread_facts=thread_facts,
                person_node=person_node, company_of=company_of,
                node_name=node_name, loops=loops, mailboxes=mailboxes,
                account_rate=account_rate, merge_pressure=merge_pressure, policy=policy)


# ── write ────────────────────────────────────────────────────────────────────────────────────

def _coverage(domain: str, stype: str, present: set[str], cap: int) -> tuple[int, list[str]]:
    """The registry decides what complete means; this decides how complete it can honestly be.

    `expected_fields` names what a reader of this situation type needs, and at least one entry per
    type is DELIBERATELY unwritable — the receiver of an escalation, whether a published answer
    exists, who owns the backlog. So `missing` keeps telling the truth on every row instead of
    going empty the moment the mechanical facts land, which is how 34 of one org's 73 situations
    came to report full coverage on the strength of knowing whose turn it was.
    """
    pct, gaps = coverage_score(present_fields=present,
                               expected=spec_for(domain).fields_for(stype))
    if pct == COVERAGE_UNKNOWN:
        return COVERAGE_UNKNOWN, list(gaps)
    return min(cap, pct), list(gaps)


def _write_fact(conn, *, org_id: str, node_id: str, field_name: str, value, value_type: str,
                now: datetime, key: str) -> None:
    conn.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
        "field, value, value_type, status, authority_rank, confidence, occurred_at, "
        "valid_from, visibility_scope) values "
        "(:vid, :fid, :o, :n, :f, cast(:v as jsonb), :vt, 'active', 100, 0.95, :now, :now, 'org') "
        # Same reasoning as `periodic.py` and `derived.py`: a recompute overwrites its own version
        # id rather than appending a row per sweep, or the table grows by a row per finding per
        # field forever.
        "on conflict (fact_version_id) do update set value = excluded.value, "
        "occurred_at = excluded.occurred_at, valid_from = excluded.valid_from"),
        {"vid": f"fv_desk_{key}", "fid": f"f_desk_{key}", "o": org_id, "n": node_id,
         "f": field_name, "v": json.dumps(value, default=str), "vt": value_type, "now": now})


def refresh_support_situations(store, org_id: str, *, now: datetime | None = None,
                               policy: ResponsePolicy | None = None) -> int:
    """Run all seven readings and open, refresh or close their situations. Returns rows written.

    Idempotent: every fact overwrites its own deterministic version id and every situation
    conflicts on `(org_id, correlation_id)`, so a sweep that runs six times a day produces one
    row per finding rather than six.

    SELF-CORRECTING, and it has to be here rather than in `refresh_situations`. These rows have
    synthetic correlation ids with no `context_correlations` row, so the generic refresh never
    sees them and `DORMANT_AFTER_DAYS` never touches them — which is exactly right for an
    unaccepted escalation and a customer on a workaround, where going quiet IS the situation. A
    finding that stops being true this sweep is instead resolved by FACT, so it re-opens by itself
    the moment it becomes true again.
    """
    now = now or datetime.now(timezone.utc)
    domains = desk_domains()
    if not domains:
        return 0
    desk = gather(store, org_id, now=now, policy=policy or ResponsePolicy())
    written = 0

    with store.engine.begin() as c:
        for anchor, reader in READINGS:
            claiming = domains_declaring(anchor)
            if not claiming:
                continue
            findings = reader(desk)
            minted: dict[str, set[str]] = {d: set() for d in claiming}
            for f in findings:
                node_id = store.find_or_create_node(
                    c, org_id=org_id, node_type=anchor, canonical_key=f.canonical_key,
                    display_name=f.display_name, event_id=None)
                for field_name, value, value_type in f.facts:
                    _write_fact(c, org_id=org_id, node_id=node_id, field_name=field_name,
                                value=value, value_type=value_type, now=now,
                                key=f"{org_id}_{node_id}_{field_name}")
                    written += 1
                if f.concerns_node:
                    # One hop, so `build_context_slice`/`_neighborhood` pull the account's facts
                    # in through the path they already walk. No new traversal concept.
                    store.write_edge(c, org_id=org_id, edge_type="concerns",
                                     from_node_id=node_id, to_node_id=f.concerns_node,
                                     confidence=0.9, occurred_at=now, event_id=f"desk:{org_id}",
                                     evidence={"derived": "support reading"}, source="engine",
                                     authority_rank=2)
                present = {name for name, _, _ in f.facts}
                for domain in claiming:
                    stype = spec_for(domain).type_for(anchor)
                    corr = f"{f.correlation_id}_{domain}"
                    minted[domain].add(corr)
                    coverage, gaps = _coverage(domain, stype, present, f.coverage_cap_pct)
                    fresh, fresh_known = freshness_score(last_seen_at=f.last_seen_at, now=now)
                    identity = identity_score(
                        open_merge_proposals=desk.merge_pressure.get(f.identity_node or "", 0))
                    evidence = evidence_score(event_count=f.event_count,
                                              source_count=f.source_count)
                    _upsert(c, org_id=org_id, corr=corr, node_id=node_id, stype=stype,
                            domain=domain, now=now, coverage=coverage,
                            missing=list(f.missing) + gaps,
                            inputs={**f.inputs, "reading": anchor,
                                    "approximated_from": "correspondence — no helpdesk is "
                                                         "connected, so no ticket, queue or SLA "
                                                         "object exists behind this",
                                    "coverage_cap_pct": f.coverage_cap_pct},
                            evidence=evidence,
                            freshness=fresh if fresh_known else None,
                            identity=identity,
                            first_seen=f.first_seen_at, last_seen=f.last_seen_at)
                    written += 1
            for domain, live in minted.items():
                written += _reconcile(c, org_id=org_id,
                                      stype=spec_for(domain).type_for(anchor),
                                      live=live, now=now)
    return written


def _upsert(conn, *, org_id: str, corr: str, node_id: str, stype: str, domain: str,
            now: datetime, coverage: int, missing: list[str], inputs: dict,
            evidence: int, freshness: int | None, identity: int,
            first_seen: datetime | None, last_seen: datetime | None) -> None:
    """One situation row. `overall` is the MINIMUM of the trust dimensions, never the average, and
    a dimension with no basis is LEFT OUT rather than scored zero — evidence with no timestamps
    tells us nothing about currency, and scoring that as stale would turn missing data into bad
    news. Consistency is a constant full 100 here because these findings are computed from one
    source and cannot contradict themselves; the single-source limit is priced in `evidence`.

    Every number here is an int PERCENT (`situations.SCORE_MAX`), the unit the column and every
    other writer use. They were basis points, and `situation_bso._bp` re-multiplied them into a
    saturated 10000 at the Layer 3 seam — the coverage cap above says why that matters."""
    trust = [evidence, 100, identity] + ([freshness] if freshness is not None else [])
    held = conn.execute(text(
        "select situation_id from context_situations where org_id=:o and correlation_id=:c"),
        {"o": org_id, "c": corr}).scalar()
    conn.execute(text(
        "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
        "  situation_type, domain, status, confidence_overall, confidence_evidence, "
        "  confidence_freshness, confidence_consistency, confidence_identity, coverage, missing, "
        "  inputs, first_seen_at, last_seen_at, computed_at) "
        "values (:sid, :o, :c, :n, :st, :d, 'active', :ov, :ev, :fr, 100, :id, :cov, "
        "  cast(:missing as jsonb), cast(:inputs as jsonb), :first, :last, :now) "
        "on conflict (org_id, correlation_id) do update set "
        "  status = 'active', resolved_by = null, resolved_at = null, "
        "  confidence_overall = excluded.confidence_overall, "
        "  confidence_evidence = excluded.confidence_evidence, "
        "  confidence_freshness = excluded.confidence_freshness, "
        "  confidence_identity = excluded.confidence_identity, "
        "  coverage = excluded.coverage, missing = excluded.missing, "
        "  inputs = excluded.inputs, last_seen_at = excluded.last_seen_at, "
        "  situation_type = excluded.situation_type, computed_at = excluded.computed_at"),
        {"sid": held or new_id("sit"), "o": org_id, "c": corr, "n": node_id, "st": stype,
         "d": domain, "ov": min(trust), "ev": evidence, "fr": freshness or 0, "id": identity,
         "cov": coverage, "missing": json.dumps(missing), "now": now,
         "inputs": json.dumps(inputs, default=str),
         "first": first_seen or now, "last": last_seen or now})


def _reconcile(conn, *, org_id: str, stype: str, live: set[str], now: datetime) -> int:
    """Close the rows this sweep no longer finds, as RESOLVED BY FACT.

    By fact rather than by a human, so it un-resolves by itself if the finding returns — the
    system should not need somebody to undo a conclusion it drew from data that has since
    changed. This is what closes an aging item when its loop closes, an escalation when a new
    name appears on the thread, and a workaround when a fix email lands.
    """
    rows = conn.execute(text(
        "select correlation_id from context_situations "
        "where org_id=:o and situation_type=:st and status=:active"),
        {"o": org_id, "st": stype, "active": STATUS_ACTIVE}).fetchall()
    stale = [r.correlation_id for r in rows if r.correlation_id not in live]
    if not stale:
        return 0
    return conn.execute(text(
        "update context_situations set status=:resolved, resolved_by=:by, resolved_at=:now, "
        "  computed_at=:now where org_id=:o and correlation_id = any(:ids)"),
        {"o": org_id, "ids": stale, "resolved": STATUS_RESOLVED, "by": RESOLVED_BY_FACT,
         "now": now}).rowcount


__all__ = [
    "ANCHOR_BACKLOG_ITEM", "ANCHOR_CONTACT_INTENT", "ANCHOR_ESCALATION", "ANCHOR_MAILBOX",
    "ANCHOR_THREAD", "ANCHOR_TOPIC", "ANCHOR_WORKAROUND", "Desk", "Finding", "INTENT_LEXICON",
    "Loop", "LOOKBACK_DAYS", "Message", "QUIET_DAYS", "READINGS", "ResponsePolicy",
    "advance_working_hours", "answer_reuse_bp", "classify_intent", "clause_around", "desk_domains", "gather",
    "percentile_bp", "read_backlog_items", "read_escalations", "read_first_response",
    "read_knowledge_gaps", "read_mailbox_load", "read_repeat_contacts", "read_workarounds",
    "reads_as_escalation", "reads_as_fix", "reads_as_workaround",
    "refresh_support_situations", "repeat_window_days", "reply_turnaround_days",
    "workaround_cost",
]
