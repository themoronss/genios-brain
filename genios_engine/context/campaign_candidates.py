"""L2.3 · the sends that ALMOST formed a campaign — a refusal, published.

`correlation_conversation` groups outbound mail by the EXACT sentence, and says plainly why:

    *"Deliberately not stemmed, tokenised or fuzzy-matched. Two sends are one campaign when the
    founder sent the SAME SENTENCE, and a similarity threshold here would quietly merge two
    different pitches on a bad day — the failure the eight-correlator design calls a wrongful
    merge, and the one nobody can debug from a stored score."*

That is correct and this module does not overturn it. A founder who paraphrases sends the same
raise to eighteen people and the system sees eighteen unrelated threads; a founder who copies and
pastes gets one campaign. The difference is a typing habit, not a fact about the fundraise.

THIS PASS ASSERTS NOTHING. It mints no campaign, no group, no card. It publishes a CANDIDATE: a
set of sends, in one window, to enough distinct counterparties, that share wording this tenant
does not use everywhere — together with the words themselves. Whether they are one campaign is
`same_situation_two_threads`'s question (M-3), and the spec names that as one of correlation's two
model sites for exactly this reason. The deterministic half's job is to find the ambiguity and
refuse it; the model's job is to adjudicate one bounded instance of it.

THE EVIDENCE IS THE WORDS, NOT A SCORE, and that is the whole answer to the objection above. A
stored similarity of 0.72 is undebuggable: nobody can say why, and nobody can say what would change
it. A row saying *these six emails all contain "preseed", "traction", "genios"* can be read by a
human in one second and agreed with or dismissed. It is also what a model can be shown without
being handed the mailbox.

DISTINCTIVE MEANS RARE IN THIS TENANT'S OWN MAIL, measured rather than listed. A token is
distinctive when it appears in at most `MAX_DOC_FREQUENCY_BP` of the sends read. No stopword list,
no length heuristic — "looking", "forward", "meeting" and "thanks" disqualify themselves because
this founder writes them in nearly every message, and so does their signature, their company name
in the footer and their calendar link. A list would have to be maintained and would be wrong for
the next tenant; a frequency is computed from the same rows the pass already holds.

EXACT MATCHES ARE NOT CANDIDATES. A group whose sentences are all identical is one
`find_campaigns` already owns, and re-proposing it would spend a model call to rediscover
something the deterministic layer got right.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.context.correlation_conversation import (MIN_RECIPIENTS, MIN_SENTENCE_CHARS,
                                                            WINDOW_HOURS, first_quote,
                                                            normalise_sentence,
                                                            outbound_with_sentences, sender_email)

FACT_PREFIX = "derived.conversation"

#: THE QUEUE. One fact on the TENANT node whose value is `{"candidates": [ … ]}` — the subject is
#: the org's own outbound behaviour, not any one counterparty, and `periodic.py` already anchors
#: tenant-wide readings there. A list rather than one fact per candidate because a candidate is
#: identified by the SET of sends in it, which is not a node and cannot be a `subject_node_id`.
#: The angle reads it through `Angle.fan_out`, which exists precisely for list-valued queues.
FIELD_CANDIDATE = f"{FACT_PREFIX}.campaign_candidate"

#: How common a word may be in this tenant's own sends and still count as distinctive. 2,000bp =
#: one send in five. A founder's signature, their calendar link and their habitual courtesies all
#: sit far above it and disqualify themselves; a product name that appears in one campaign and
#: nowhere else sits far below.
MAX_DOC_FREQUENCY_BP = 2_000

#: HOW MUCH MAIL THIS PASS NEEDS BEFORE IT WILL SAY ANYTHING, and the reason is a real limit
#: rather than a safety margin. Distinctiveness is measured as "rare in this tenant's own sends",
#: so it can only separate a campaign from a habit when there is mail OUTSIDE the campaign to
#: compare against. Read twenty sends where four are one raise and "preseed" sits far under the
#: ceiling while the signature sits far over it. Read only those four and the two are
#: indistinguishable: every word appears in every send, and no frequency rule can tell a pitch
#: from a sign-off.
#:
#: FAILING CLOSED IS THE ONLY HONEST ANSWER THERE, and it needs to be a DECLARED bound and not an
#: emergent one. Left to the arithmetic alone the ceiling silently collapses to one on a small
#: mailbox and the pass quietly never fires — behaviour nobody chose, in a pass whose whole job is
#: to be inspectable. Twenty is `MIN_RECIPIENTS` over `MAX_DOC_FREQUENCY_BP`, rounded up: the
#: smallest corpus in which the smallest admissible group can still sit under the ceiling.
MIN_CORPUS_SENDS = 20

#: How many distinctive words a group must have IN COMMON — the intersection across every member,
#: not a pairwise overlap. Three is where "they both mention the round" stops being a coincidence
#: two business emails can reach by accident.
MIN_SHARED_TOKENS = 3

#: Below this a token is punctuation or an initial, and including them would let "i", "a" and "re"
#: carry a candidate. Deliberately small: the real filter is the frequency above, and a length
#: threshold doing the work is the heuristic this module exists to avoid.
MIN_TOKEN_CHARS = 3

#: Ceilings on one sweep, in the shape `correlation_dependency.MAX_CLAIMS_PER_SWEEP` already uses:
#: a cost ceiling, not a sample. A truncated pass reports that it truncated.
MAX_CANDIDATES = 40
MAX_SENDS_PER_CANDIDATE = 12
#: How many of a candidate's distinct sentences travel with it. The model needs enough to judge
#: whether they are one message reworded; it does not need the mailbox.
MAX_SENTENCES_PER_CANDIDATE = 6

_TOKEN = re.compile(r"[a-z0-9$][a-z0-9$'\-.]*")


def tokenise(sentence: str) -> frozenset[str]:
    """The distinct words of one sentence, lower-cased, with punctuation dropped.

    Kept crude on purpose. A stemmer would make "raise" and "raising" one token and would also
    make this pass impossible to explain to somebody reading a candidate row; the words that come
    out of here are the words that go into the published evidence, so what a reader sees is
    exactly what the pass matched on.
    """
    # TRAILING PUNCTUATION IS NOT PART OF A WORD, and leaving it on was a real defect: `.` has to
    # be INSIDE the character class so "3.5k" and "v2.1" survive, which also means a sentence
    # ending "…at 3k MRR." yields `mrr.` while one reading "MRR traction" yields `mrr`. Four
    # paraphrases of one raise then shared two words instead of three and fell under
    # `MIN_SHARED_TOKENS` — the pass would have found nothing on real mail and looked like a
    # tenant with no campaigns rather than a bug.
    return frozenset(
        stripped for token in _TOKEN.findall(normalise_sentence(sentence))
        if len(stripped := token.strip(".-'")) >= MIN_TOKEN_CHARS)


@dataclass(frozen=True, slots=True)
class Send:
    """One outbound message, reduced to what grouping needs."""

    node_id: str
    event_id: str
    sent_at: datetime
    sentence: str
    tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A set of sends that share distinctive wording and were NOT grouped into a campaign."""

    candidate_id: str
    #: The words every member has in common — the evidence, and what makes the row checkable.
    shared_tokens: tuple[str, ...]
    #: Distinct sentences, bounded. Two members that wrote the same thing appear once.
    sentences: tuple[str, ...]
    recipients: tuple[str, ...]
    event_ids: tuple[str, ...]
    first_sent: datetime
    last_sent: datetime

    def as_json(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id,
                "shared_tokens": list(self.shared_tokens),
                "sentences": list(self.sentences),
                "recipients": list(self.recipients),
                "event_ids": list(self.event_ids),
                "first_sent": self.first_sent.isoformat(),
                "last_sent": self.last_sent.isoformat()}


def candidate_id_for(event_ids: Sequence[str]) -> str:
    """Content-addressed on the SET of sends, so the same group is the same candidate across
    sweeps and a member joining or leaving makes it a different one — which it is."""
    payload = "\x1f".join(sorted(event_ids))
    return f"cand_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _sends(rows: Sequence[Mapping]) -> list[Send]:
    """Rows to sends, applying the same three exclusions `_rows_to_campaigns` applies.

    Identical on purpose: a candidate built from rows the campaign finder would have skipped is a
    candidate about mail that does not exist as far as the other pass is concerned.
    """
    out: list[Send] = []
    for row in rows:
        quote = first_quote(row["evidence_refs"])
        sentence = normalise_sentence(quote)
        if len(sentence) < MIN_SENTENCE_CHARS:
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
        out.append(Send(node_id=str(row["node_id"]), event_id=str(row["event_id"]),
                        sent_at=sent_at, sentence=quote.strip(), tokens=tokenise(quote)))
    out.sort(key=lambda send: (send.sent_at, send.event_id))
    return out


def distinctive_tokens(sends: Sequence[Send]) -> frozenset[str]:
    """The words rare enough in this tenant's own mail to mean something.

    MEASURED, NOT LISTED. Document frequency over the sends read: a token in more than
    `MAX_DOC_FREQUENCY_BP` of them is this founder's habit — a sign-off, a company name in the
    footer, a scheduling link — and carries no information about which mails belong together. The
    threshold adapts to each tenant because it is computed from that tenant's rows, which a
    stopword list cannot do.
    """
    if not sends:
        return frozenset()
    counts: dict[str, int] = {}
    for send in sends:
        for token in send.tokens:
            counts[token] = counts.get(token, 0) + 1
    ceiling = max(1, (len(sends) * MAX_DOC_FREQUENCY_BP) // 10_000)
    return frozenset(token for token, n in counts.items() if n <= ceiling)


def _windowed(sends: Sequence[Send], window_hours: int) -> list[list[Send]]:
    """Runs of sends no further from the run's FIRST send than the window.

    The same rule `_rows_to_campaigns` uses, and for the reason it records: a calendar-day bucket
    would split a send that crossed midnight while merging two attempts a fortnight apart that
    happened to share a weekday.
    """
    runs: list[list[Send]] = []
    run: list[Send] = []
    for send in sends:
        if run and send.sent_at - run[0].sent_at > timedelta(hours=window_hours):
            runs.append(run)
            run = []
        run.append(send)
    if run:
        runs.append(run)
    return runs


def find_candidates(rows: Sequence[Mapping], *, window_hours: int = WINDOW_HOURS,
                    min_recipients: int = MIN_RECIPIENTS,
                    limit: int = MAX_CANDIDATES) -> tuple[tuple[Candidate, ...], bool]:
    """Every near-miss in these rows, largest first, and whether the cap cut anything.

    PURE, so the grouping rule can be read and tested without a database — the property
    `_rows_to_campaigns` keeps next door and for the same reason.

    ANCHORED ON A TOKEN, NOT CHAINED. For each distinctive word, the sends containing it are a
    proposed group; the group survives only if the INTERSECTION of its members' distinctive tokens
    is still at least `MIN_SHARED_TOKENS`. Connected components over pairwise similarity were the
    obvious alternative and were rejected: chaining merges A with C because both resemble B, and
    the resulting group has nothing a reader can point at. Here the shared words are common to
    every member by construction, which is what makes the published row checkable.
    """
    all_sends = _sends(rows)
    if len(all_sends) < MIN_CORPUS_SENDS:
        # See MIN_CORPUS_SENDS. Not "no candidates" so much as "no basis to name one", and the
        # two are reported the same way on purpose: this pass proposes, and a proposal it cannot
        # justify is one it must not make.
        return (), False
    distinctive = distinctive_tokens(all_sends)
    found: dict[frozenset[str], Candidate] = {}

    for run in _windowed(all_sends, window_hours):
        by_token: dict[str, list[Send]] = {}
        for send in run:
            for token in send.tokens & distinctive:
                by_token.setdefault(token, []).append(send)

        for token in sorted(by_token):
            members = by_token[token][:MAX_SENDS_PER_CANDIDATE]
            if len({send.node_id for send in members}) < min_recipients:
                continue
            shared = frozenset.intersection(*(send.tokens & distinctive for send in members))
            if len(shared) < MIN_SHARED_TOKENS:
                continue
            sentences = sorted({send.sentence for send in members})
            # ALREADY OWNED. One sentence across every member is a campaign `find_campaigns`
            # found; proposing it would spend a call rediscovering a correct answer.
            if len(sentences) < 2:
                continue
            key = frozenset(send.event_id for send in members)
            if key in found:
                continue
            found[key] = Candidate(
                candidate_id=candidate_id_for(sorted(key)),
                shared_tokens=tuple(sorted(shared)),
                sentences=tuple(sentences[:MAX_SENTENCES_PER_CANDIDATE]),
                recipients=tuple(sorted({send.node_id for send in members})),
                event_ids=tuple(sorted(key)),
                first_sent=min(send.sent_at for send in members),
                last_sent=max(send.sent_at for send in members))

    ordered = sorted(found.values(),
                     key=lambda c: (-len(c.recipients), -len(c.shared_tokens), c.candidate_id))
    return tuple(ordered[:limit]), len(ordered) > limit


__all__ = ["FACT_PREFIX", "FIELD_CANDIDATE", "MAX_CANDIDATES", "MAX_DOC_FREQUENCY_BP",
           "MAX_SENDS_PER_CANDIDATE", "MAX_SENTENCES_PER_CANDIDATE", "MIN_CORPUS_SENDS",
           "MIN_SHARED_TOKENS",
           "MIN_TOKEN_CHARS", "Candidate", "Send", "candidate_id_for", "distinctive_tokens",
           "find_candidates", "tokenise"]


# =================================================================================================
# THE SWEEP HALF — read the same rows the campaign finder reads, publish what it declined to group
# =================================================================================================

VERSION_PREFIX = "fv_cand"
VALUE_TYPE = "campaign_candidate"

#: PARTICIPANTS, not `org`. A candidate carries the sentences of real messages and the counterparty
#: nodes they went to, so it is exactly as narrow as the mail it is built from — the same ceiling
#: `correlation_timeline` records for its own rows, and strictly more honest than `'org'`.
CANDIDATE_VISIBILITY_SCOPE = "participants"

#: How far back a sweep looks for near-misses. Shorter than the condition window and for the
#: opposite reason: a campaign is a morning's work, and proposing one from mail sent last spring
#: would ask a model to adjudicate an argument nobody is having any more.
CANDIDATE_WINDOW_DAYS = 120


@dataclass(frozen=True, slots=True)
class CandidateReport:
    candidates: int = 0
    truncated: bool = False
    written: int = 0
    unchanged: int = 0
    closed: int = 0

    def as_record(self) -> dict:
        return {"candidates": self.candidates, "truncated": self.truncated,
                "written": self.written, "unchanged": self.unchanged, "closed": self.closed}


def refresh_campaign_candidates(store, org_id: str, *, eval_time: datetime,
                                window_hours: int = WINDOW_HOURS,
                                min_recipients: int = MIN_RECIPIENTS) -> CandidateReport:
    """Publish this sweep's near-misses onto the tenant node, and close them when they stop.

    NO TENANT NODE, NO PASS. `periodic.tenant_node_id` returns None before the first sweep has
    minted one, and minting one here would make this pass the reason a tenant node exists — a
    dependency nobody declared and a node whose provenance would read as "the campaign candidate
    pass created it". The honest answer on a graph that has none is zero candidates.

    `eval_time` is a parameter all the way down: the clock is read at the call site, so two runs at
    one instant publish byte-identical rows and the second is an overwrite rather than a second
    opinion.
    """
    from genios_engine.context.analytic.publish import close_derived_facts, publish_derived_fact
    from genios_engine.context.periodic import tenant_node_id

    since = eval_time - timedelta(days=CANDIDATE_WINDOW_DAYS)
    prefix = f"{VERSION_PREFIX}:"
    with store.engine.begin() as conn:
        node_id = tenant_node_id(conn, org_id)
        if not node_id:
            return CandidateReport()

        rows = outbound_with_sentences(conn, org_id, since=since)
        candidates, truncated = find_candidates(rows, window_hours=window_hours,
                                                min_recipients=min_recipients)

        keep: list[str] = []
        written = unchanged = 0
        if candidates:
            published = publish_derived_fact(
                conn, org_id=org_id, subject_node_id=node_id, field=FIELD_CANDIDATE,
                value={"candidates": [c.as_json() for c in candidates]},
                eval_time=eval_time, value_type=VALUE_TYPE,
                visibility_scope=CANDIDATE_VISIBILITY_SCOPE, version_prefix=prefix,
                fact_id=f"f_cand:{FIELD_CANDIDATE}:{node_id}")
            keep.append(published.version_id)
            written, unchanged = (1, 0) if published.wrote else (0, 1)

        # NOTHING FOUND CLOSES THE ROW. A tenant whose near-misses were all resolved — merged by
        # hand, or simply not repeated — must stop carrying last month's candidates, and closing
        # with `valid_to` rather than deleting keeps an as-of read of last week answerable.
        closed = close_derived_facts(conn, org_id=org_id, version_prefix=prefix, keep=keep,
                                     eval_time=eval_time)

    return CandidateReport(candidates=len(candidates), truncated=truncated,
                           written=written, unchanged=unchanged, closed=closed)


def read_candidates(conn, org_id: str) -> tuple[Mapping, ...]:
    """The published candidates for one org, or nothing. Defensive about the driver's `jsonb`."""
    from genios_engine.context.periodic import tenant_node_id

    node_id = tenant_node_id(conn, org_id)
    if not node_id:
        return ()
    value = conn.execute(text(
        "select value from graph_facts where org_id = :o and subject_node_id = :n "
        "and field = :f and status = 'active' and valid_to is null"),
        {"o": org_id, "n": node_id, "f": FIELD_CANDIDATE}).scalar()
    if isinstance(value, (str, bytes)):
        try:
            value = json.loads(value)
        except ValueError:
            return ()
    if not isinstance(value, Mapping):
        return ()
    found = value.get("candidates")
    return tuple(c for c in found if isinstance(c, Mapping)) if isinstance(found, list) else ()


__all__ += ["CANDIDATE_VISIBILITY_SCOPE", "CANDIDATE_WINDOW_DAYS", "VALUE_TYPE", "VERSION_PREFIX",
            "CandidateReport", "read_candidates", "refresh_campaign_candidates"]
