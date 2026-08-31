"""L2 · The document register — a governance artefact whose control state has a GAP.

WHAT THIS READS. Five authored records capabilities — document_control, filing_and_retrieval,
version_control, retention_and_archival, knowledge_base_maintenance — were complete knowledge
with no surface, because `context_situations` anchors on a graph node and no node was a document.
`context/documents.py` gives a file that node; this opens one situation per file WITH A GAP.

WITH A GAP, and never one per file. The situation's own render hint says it in five words: "the
headline is the gap, not the document." A Drive of four hundred files would otherwise produce four
hundred cards saying a document exists, which is a file listing wearing a situation's clothes and
is how the handful that need attention become unfindable. So candidacy (is this a governance
artefact at all) and the gap (is anything actually wrong with it) are two separate gates, and both
must pass.

WHAT IT REFUSES TO SAY, on every row, because two of the four failures this subdomain exists to
catch do not survive the approximation:

  MISSING APPROVAL does not survive. `document.approved_at` is not a Drive concept and nothing
  writes it. Drive offers revision history, comments and suggestion-accepts; not one of them is an
  approval, and inferring one from a modification history is precisely the fabrication the corpus
  file forbids. So every artefact renders as "approval state unknown" and never as "unapproved",
  which would be a finding this system invented.

  RETAINED PAST ITS DATE does not survive either. `document.retention_until` needs a retention
  schedule the tenant has never stated anywhere. There is no clock and none can be derived, so
  `retention_and_archival` gets a route and an empty hand — which is why it is named in `missing`
  on every row rather than left for somebody to discover during an audit.

  NO OWNER survives, but weakly. Drive names an owner and the graph can say whether that person is
  anybody this tenant corresponds with. It cannot tell a leaver from somebody on parental leave,
  and those two demand opposite responses — so the claim carried is "owner unverified", never
  "the owner has left".

  A SUPERSEDED COPY survives as half of itself. Title-and-content clustering finds that two live
  copies of one document exist. Nothing can say whether that is a fork or an orderly lineage,
  because supersession has a timestamp in every document management system and no representation
  here: v2 published with v1 correctly withdrawn looks identical to two teams editing in parallel.
  The honest claim is "two live copies exist", not "the wrong version is in circulation".

THE SHAPE IS `context/periodic.py`, copied rather than reinvented: mint an anchor the correlation
engine cannot reach, write its computed facts onto it as ordinary facts, and upsert a situation
anchored there, so `_load_context`, `_neighborhood`, `build_context_slice` and the whole compile
path need no new concept. And the anchor stays out of `ANCHOR_PRIORITY` for the same reason the
tenant node does — see `documents.py` for why a document that could anchor would swallow every
email that mentions one.

NO LLM ANYWHERE. Candidacy is a closed lexicon over the title and the head of the text L1 already
persisted; every gate is arithmetic over facts. The same Drive re-swept tomorrow by a different
model version produces the same answers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.context.documents import DOCUMENT_NODE_TYPE, cluster_key, document_nodes
from genios_engine.context.domain_spec import domains_declaring, spec_for
from genios_engine.context.situations import (
    COVERAGE_UNKNOWN,
    RESOLVED_BY_FACT,
    STATUS_ACTIVE,
    STATUS_RESOLVED,
    coverage_score,
    evidence_score,
    freshness_score,
)
from genios_engine.platform.ids import new_id

#: The anchor. Declared by a domain in `DomainSpec.situation_types`, which is the whole opt-in —
#: nothing in this file names a domain, per the rule Layer 2 is held to.
ANCHOR_DOCUMENT = DOCUMENT_NODE_TYPE

#: How much of the extracted text the candidacy lexicon reads. A governance artefact says what it
#: is in its opening lines — "This policy sets out…", "Purpose and scope" — and a term found ten
#: pages in is usually a cross-reference to a different document. Bounding the scan is what stops
#: an invoice that cites a contract from being filed as one.
SCAN_CHARS = 2000

#: Both copies edited inside this many days is what makes a fork LIVE. Six months rather than a
#: year because the claim is "two copies are in use", and a file nobody has touched since last
#: spring is not in use — it is the stale one, which is a different and much weaker finding.
LIVE_COPY_DAYS = 180

#: A governance artefact nobody has touched in this long has stopped being maintained. A year,
#: because most review cycles are annual and anything shorter would fire on every policy that is
#: simply correct and did not need editing this quarter.
UNMAINTAINED_DAYS = 365

#: How recently the owner has to have been seen anywhere in this tenant's data for the ownership
#: to read as verified. Four months absorbs a sabbatical-shaped gap without absorbing a departure.
OWNER_SEEN_DAYS = 120

#: Coverage ceiling, an int PERCENT on the `situations.SCORE_MAX` scale every other score in
#: `context_situations` uses. Not a percentage of a record — "how much of what a records reading
#: needs can be known from a file store at all", which is under half: the approval state, the
#: retention clock, the classification and the review date are all outside Drive. A ceiling rather
#: than a value; `expected_fields` still decides the number under it, so a file with no owner
#: scores lower still.
#:
#: It was 4000 basis points, copied from `periodic.py`, and that silently voided the cap: the
#: Layer 2 -> Layer 3 seam (`situation_bso._bp`) multiplies the stored number by 100 and clamps at
#: 10000, so a document situation capped at "under half" reached the compiler as coverage_bp=10000
#: — indistinguishable from a fully-sourced recorded situation, which is the exact claim this
#: reading must never make about a file store.
COVERAGE_CAP_PCT = 40

#: What this reading cannot see, declared per row rather than estimated — the same discipline as
#: the period situations' ["targets", "per-owner load", "cost per contact"]. Every compiled card
#: then states on its face what the finding underneath it does not know, which is the difference
#: between a records gap and records coverage that was claimed and is not there.
MISSING = (
    "approval — a file store keeps revisions and comments, and neither of those is an approval",
    "a retention schedule, so nothing here knows when this must be destroyed",
    "a classification label, so whether it may be shared cannot be checked",
    "a review date — the self-imposed one, which nobody has set",
    "whether an unverified owner has left or is on leave, which demand opposite responses",
    "supersession, so two live copies cannot be told from an orderly lineage",
)

#: File types a controlled document can plausibly BE. An image, a video, an archive or a binary
#: has no version identity and no readable text, so a records reading of one would rest entirely
#: on its filename. Matched as substrings because one MIME family spans several spellings
#: (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`).
DOCUMENT_MIMES = (
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/pdf",
    "wordprocessingml",
    "spreadsheetml",
    "presentationml",
    "application/msword",
    "application/vnd.oasis.opendocument",
    "application/rtf",
    "text/plain",
    "text/markdown",
    "text/rtf",
)

#: What makes a file a GOVERNANCE artefact rather than a document. This is the whole of candidacy
#: and it is deliberately narrow: a records reading of a meeting note or a customer proposal is
#: noise, and the corpus is explicit that the failures here are about artefacts the organisation
#: is accountable for. Whole words are not required — "policies", "procedures" and "agreements"
#: must all match — so every term is chosen to be one that rarely appears inside another word.
GOVERNANCE_TERMS = (
    "policy", "policies", "sop", "standard operating", "procedure", "handbook", "charter",
    "register", "minutes", "standard", "manual", "agreement", "contract", "nda",
    "data processing", "dpa", "msa", "checklist", "terms of service", "code of conduct",
    "guideline", "bylaw", "constitution", "memorandum",
)

#: A canon tag the organisation typed itself. It outranks the lexicon because it is a DECLARATION
#: rather than a guess about one — the org saying "this file is our SOP" is stronger evidence than
#: the word appearing in its title.
#:
#: Dormant on today's paths, and named here anyway. The upload door files a tagged file as a CANON
#: node (`canon.py`), not a document node, so `internal_kind` is null on every event that mints a
#: document today. It is read because the day any path tags a file store — a Drive folder declared
#: `policy` — a tenant who has stated exactly what these files are must not then be excluded by a
#: keyword list.
CANON_GOVERNANCE_KINDS = frozenset({"policy", "sop", "wiki"})

# Gap codes, carried in `inputs` so a card can say WHICH control is missing rather than that one
# is. The corpus asks for the gap to be the headline; a situation that only says "unverified"
# makes the reader open the document to find out what for.
GAP_NO_OWNER = "owner_unverified"
GAP_LIVE_COPIES = "two_live_copies"
GAP_UNMAINTAINED = "unmaintained"
GAP_ORPHAN = "nobody_attached"


def register_domains() -> tuple[str, ...]:
    """Every domain that declares the `document` anchor, asked of the registry rather than listed.

    Same opt-in shape as `periodic.period_domains` and `support_situations.desk_domains`, and for
    the same reason: a domain named in Layer 2 would mean adding a domain requires editing Layer 2,
    and the registry exists precisely so it does not.
    """
    return domains_declaring(ANCHOR_DOCUMENT)


def _parse(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _days(since: datetime | None, now: datetime) -> float | None:
    return None if since is None else (now - since).total_seconds() / 86400.0


def is_document_mime(mime: str | None) -> bool:
    """Whether this file type could hold a controlled document at all."""
    low = (mime or "").strip().lower()
    return bool(low) and any(m in low for m in DOCUMENT_MIMES)


def governance_term(*texts: str | None) -> str | None:
    """The first governance term any of these texts carries, or None.

    The TERM is returned rather than a boolean so the situation can say which word made this a
    candidate. A finding whose evidence is "the lexicon fired" cannot be checked by anybody —
    the same rule `support_situations.clause_around` was written for.
    """
    for chunk in texts:
        low = (chunk or "").lower()
        for term in GOVERNANCE_TERMS:
            if term in low:
                return term
    return None


@dataclass(frozen=True, slots=True)
class Artefact:
    """One file, reduced to what the register needs to read it."""

    node_id: str
    title: str
    facts: dict[str, str]
    head: str                       # first SCAN_CHARS of the extracted text, PII-masked by L1
    internal_kind: str | None
    attached_people: int            # distinct persons on an edge to this document
    owner_seen_at: datetime | None  # last time the named owner appeared anywhere in this tenant
    owner_is_us: bool               # the owner is a seat, the account owner or a connected mailbox

    def fact(self, name: str) -> str | None:
        return self.facts.get(name)

    @property
    def modified_at(self) -> datetime | None:
        return _parse(self.fact("document.modified_at"))


@dataclass(frozen=True, slots=True)
class Register:
    """The org's documents plus the small amount of context the gates need, gathered once."""

    org_id: str
    now: datetime
    artefacts: tuple[Artefact, ...] = ()

    def clusters(self) -> dict[str, list[Artefact]]:
        """Artefacts grouped by the document they are copies OF.

        A file whose title reduces to nothing (an id for a name, a single stripped decoration)
        gets its OWN cluster keyed on its node id rather than joining an "unknown" bucket. The
        bucket would make every unnameable file a copy of every other unnameable file, which is
        how a folder of scans becomes one document with forty live versions.
        """
        out: dict[str, list[Artefact]] = {}
        for a in self.artefacts:
            out.setdefault(cluster_key(a.title) or f"node:{a.node_id}", []).append(a)
        return out


def live_copies(members: list[Artefact], now: datetime) -> int:
    """How many copies of one document have been edited recently enough to be in use.

    Counted per FILE, not per distinct `document.version`, and that is a correction to the
    obvious rule rather than a shortcut. Drive's `version` is a per-file revision counter: two
    independently created copies of the handbook are both `version: 1` on the day they are made
    and both `version: 40` after a year of equal editing, so requiring the counters to differ
    would miss the commonest fork there is and match on the pair least likely to be one.

    Copies with no modification stamp are excluded rather than assumed live. "We do not know when
    this was last touched" is not evidence that it is in circulation, and counting it as such
    would put a version-conflict card under a pair of files nobody has opened in three years.
    """
    cutoff = now - timedelta(days=LIVE_COPY_DAYS)
    return sum(1 for m in members if (m.modified_at or datetime.min.replace(
        tzinfo=timezone.utc)) >= cutoff)


def gaps_for(a: Artefact, *, copies: int, now: datetime) -> list[str]:
    """Every control gap this artefact has. Empty means it is under control as far as we can see.

    "As far as we can see" is the whole caveat and it is carried in `missing`, not here: the two
    gaps that would matter most — no approval on record and past its retention date — cannot be
    read from a file store at all, so an empty list here means "none of the four we CAN see",
    never "this document is controlled".
    """
    found: list[str] = []

    # (i) NO OWNER. Absent, or named but unverifiable — not one of our own addresses and not seen
    # anywhere in this tenant's data for four months. Deliberately phrased as unverified: this
    # cannot tell a leaver from somebody on parental leave, and the corpus's own
    # `doc.owner_left_the_organisation` needs an HRIS end date exactly because those two produce
    # identical silence and demand opposite responses.
    if not a.fact("document.owner_email"):
        found.append(GAP_NO_OWNER)
    elif not a.owner_is_us:
        seen = _days(a.owner_seen_at, now)
        if seen is None or seen >= OWNER_SEEN_DAYS:
            found.append(GAP_NO_OWNER)

    # (ii) TWO LIVE COPIES. Not "the wrong version is in circulation" — supersession has no
    # emitter here, so a correctly withdrawn v1 and two teams editing in parallel are the same
    # picture. The claim is only that both copies are in use.
    if copies >= 2:
        found.append(GAP_LIVE_COPIES)

    # (iii) UNMAINTAINED. A governance artefact nobody has edited in a year. Absent stamp is not
    # a gap: unknown is not old.
    age = _days(a.modified_at, now)
    if age is not None and age >= UNMAINTAINED_DAYS:
        found.append(GAP_UNMAINTAINED)

    # (iv) NOBODY ATTACHED. The corpus's `doc.orphaned_artefact` reads `edge_count <= 1`, which is
    # calibrated for a graph where a controlled document also has an approver and a series. Here a
    # document can only ever reach an owner and a last editor, so a degree of one is the ORDINARY
    # state of a file whose owner also maintains it — using the corpus threshold verbatim would
    # mint a situation on nearly every governance file, which is the one-card-per-file flood the
    # render hint refuses. Zero is the honest version of the same reading: neither the owner nor
    # the last editor is anybody this graph has ever seen.
    if a.attached_people == 0:
        found.append(GAP_ORPHAN)
    return found


def read_register(reg: Register) -> list[tuple[Artefact, dict]]:
    """Every artefact worth opening a situation about, with the numbers behind it.

    TWO GATES, and they answer different questions. Candidacy asks whether a records reading of
    this file would mean anything at all; the gap asks whether anything is actually wrong. Fusing
    them would mint one card per governance document, which is a filing cabinet rather than a
    finding.
    """
    out: list[tuple[Artefact, dict]] = []
    clusters = reg.clusters()
    for key, members in sorted(clusters.items()):
        copies = live_copies(members, reg.now)
        for a in members:
            if not is_document_mime(a.fact("document.mime")):
                continue
            declared = a.internal_kind in CANON_GOVERNANCE_KINDS
            term = governance_term(a.title, a.head[:SCAN_CHARS])
            if not declared and not term:
                continue
            found = gaps_for(a, copies=copies, now=reg.now)
            if not found:
                continue
            out.append((a, {
                "gaps": found,
                "cluster_key": key,
                "live_copies": copies,
                "copy_titles": sorted({m.title for m in members})[:8] if copies >= 2 else [],
                "identical_content": (copies >= 2 and len({
                    m.fact("document.content_hash") for m in members
                    if m.fact("document.content_hash")}) == 1),
                "governance_term": term,
                "declared_kind": a.internal_kind if declared else None,
                "days_since_modified": (
                    None if _days(a.modified_at, reg.now) is None
                    else round(_days(a.modified_at, reg.now), 1)),
                "owner_email": a.fact("document.owner_email"),
                "owner_is_one_of_ours": a.owner_is_us,
                "owner_last_seen_at": (a.owner_seen_at.isoformat()
                                       if a.owner_seen_at else None),
                "attached_people": a.attached_people,
                # Named a revision count, every time, so nothing downstream reads "version 47" as
                # the forty-seventh edition of the policy.
                "drive_revision_count": a.fact("document.version"),
                "location": a.fact("document.location"),
                "shared_outside_its_folder": a.fact("document.shared"),
                "approximated_from": "a file store — there is no document management system "
                                     "behind this, so no approval, retention schedule, "
                                     "classification or review date exists to check against",
            }))
    return out


# ── gather ───────────────────────────────────────────────────────────────────────────────────

def gather(store, org_id: str, *, now: datetime) -> Register:
    """One bounded snapshot of the org's documents. One query per concept, never one per file."""
    with store.engine.connect() as c:
        docs = document_nodes(c, org_id)
        if not docs:
            return Register(org_id=org_id, now=now)

        file_ids = [d["facts"].get("document.id") for d in docs if d["facts"].get("document.id")]
        # The event each file arrived on, for its extracted text and any canon tag the org typed.
        # Keyed on `source_object_id`, which IS the file id — the same identifier the node's
        # canonical key is built from, so the join cannot drift.
        heads: dict[str, tuple[str, str | None]] = {}
        if file_ids:
            for r in c.execute(text(
                    "select se.source_object_id as fid, se.internal_kind, se.occurred_at, "
                    "       coalesce(substr(pc.clean_text, 1, :scan), '') as head "
                    "from source_events se "
                    "left join prepared_content pc "
                    "  on pc.event_id = se.event_id and pc.org_id = se.org_id "
                    "where se.org_id=:o and se.source_object_id = any(:ids) "
                    "order by se.occurred_at asc"),
                    {"o": org_id, "ids": file_ids, "scan": SCAN_CHARS}):
                # Ascending, so the LAST row wins: the newest revision of a file is the one whose
                # text describes what it says today, and a policy that was rewritten should be
                # read as what it is now rather than as its first draft.
                heads[r.fid] = (r.head or "", r.internal_kind)

        node_ids = [d["node_id"] for d in docs]
        attached: dict[str, set[str]] = {}
        for r in c.execute(text(
                "select e.from_node_id as person, e.to_node_id as doc from graph_edges e "
                "where e.org_id=:o and e.valid_to is null and e.to_node_id = any(:ids) "
                "union "
                "select e.to_node_id as person, e.from_node_id as doc from graph_edges e "
                "where e.org_id=:o and e.valid_to is null and e.from_node_id = any(:ids)"),
                {"o": org_id, "ids": node_ids}):
            attached.setdefault(r.doc, set()).add(r.person)

        # WHO WE ARE, reused from the drain rather than restated. An owner who is one of our own
        # addresses needs no correspondence check: a seat is a statement that this person is here.
        internal = _internal_emails(c, org_id)

        owners = sorted({(d["facts"].get("document.owner_email") or "").lower()
                         for d in docs} - {""})
        # LAST SEEN ANYWHERE, not last corresponded. A colleague who edited a file this month is
        # plainly still around even if they have never emailed a counterparty, and this gate must
        # err towards NOT claiming an owner is missing — it is the one claim in this reading that
        # would send somebody to reassign a document away from a person on leave.
        seen: dict[str, datetime] = {}
        if owners:
            since = now - timedelta(days=OWNER_SEEN_DAYS * 2)
            for r in c.execute(text(
                    "select lower(actor->>'email') as e, max(occurred_at) as at "
                    "from source_events where org_id=:o and occurred_at >= :since "
                    "  and lower(actor->>'email') = any(:who) group by 1"),
                    {"o": org_id, "since": since, "who": owners}):
                if r.e and r.at:
                    seen[r.e] = r.at
            for r in c.execute(text(
                    "select lower(rcpt) as e, max(se.occurred_at) as at from source_events se, "
                    "  unnest(coalesce(se.recipients, cast('{}' as text[]))) as rcpt "
                    "where se.org_id=:o and se.occurred_at >= :since "
                    "  and lower(rcpt) = any(:who) group by 1"),
                    {"o": org_id, "since": since, "who": owners}):
                held = seen.get(r.e)
                if r.at and (held is None or r.at > held):
                    seen[r.e] = r.at

    artefacts = []
    for d in docs:
        fid = d["facts"].get("document.id") or ""
        head, kind = heads.get(fid, ("", None))
        owner = (d["facts"].get("document.owner_email") or "").lower()
        artefacts.append(Artefact(
            node_id=d["node_id"],
            title=d["facts"].get("document.title") or d["display_name"],
            facts=d["facts"], head=head, internal_kind=kind,
            attached_people=len(attached.get(d["node_id"], ())),
            owner_seen_at=seen.get(owner),
            owner_is_us=bool(owner) and owner in internal))
    return Register(org_id=org_id, now=now, artefacts=tuple(artefacts))


def _internal_emails(conn, org_id: str) -> frozenset[str]:
    """Every address that is US, reused from the drain rather than restated.

    `runner._internal_emails` already unions seats, the account owner and the connected mailboxes,
    and it is the answer to the same question this gate asks. A second copy here would be a second
    place for "who works here" to drift, and the two disagreeing would mean a document's owner is
    a colleague to one reading and a stranger to another.
    """
    from genios_engine.context.runner import _internal_emails as drain_internal

    class _Shim:                       # `_internal_emails` wants a store; it only uses .engine
        def __init__(self, engine):
            self.engine = engine

    return drain_internal(_Shim(conn.engine), org_id)


# ── write ────────────────────────────────────────────────────────────────────────────────────

def _write_fact(conn, *, org_id: str, node_id: str, field_name: str, value, value_type: str,
                now: datetime) -> None:
    conn.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
        "field, value, value_type, status, authority_rank, confidence, occurred_at, "
        "valid_from, visibility_scope) values "
        "(:vid, :fid, :o, :n, :f, cast(:v as jsonb), :vt, 'active', 100, 0.95, :now, :now, 'org') "
        # Same reasoning as `periodic.py` and `derived.py`: a recompute overwrites its own
        # deterministic version id rather than appending a row per sweep, or the table grows by two
        # rows per document forever and a reader picking "latest" is sifting duplicates.
        "on conflict (fact_version_id) do update set value = excluded.value, "
        "occurred_at = excluded.occurred_at, valid_from = excluded.valid_from"),
        {"vid": f"fv_doc_{org_id}_{node_id}_{field_name}",
         "fid": f"f_doc_{org_id}_{node_id}_{field_name}", "o": org_id, "n": node_id,
         "f": field_name, "v": json.dumps(value, default=str), "vt": value_type, "now": now})


def refresh_document_situations(store, org_id: str, *, now: datetime | None = None) -> int:
    """Cluster the org's documents, then open/refresh/close their situations. Rows written.

    Idempotent: the derived facts overwrite their own deterministic version ids and every
    situation conflicts on `(org_id, correlation_id)`, so a sweep that runs six times a day
    produces one row per finding rather than six.

    SELF-CORRECTING, and it has to live here rather than in `refresh_situations`. These rows carry
    a synthetic correlation id with no `context_correlations` row, so the generic refresh never
    sees them and `DORMANT_AFTER_DAYS` never touches them — which is right, because a governance
    document going quiet is the UNMAINTAINED gap itself and quieting the card would delete the
    finding. A gap that stops being true is instead resolved BY FACT, so it reopens by itself the
    moment the file is edited again or the second copy comes back.
    """
    now = now or datetime.now(timezone.utc)
    domains = register_domains()
    if not domains:
        return 0
    reg = gather(store, org_id, now=now)
    if not reg.artefacts:
        return 0
    findings = read_register(reg)
    clusters = reg.clusters()
    written = 0

    with store.engine.begin() as c:
        # The cluster is written onto EVERY document, not only onto the ones with a gap. Which
        # document a file is a copy of is true whether or not anything is wrong with it, and a
        # reader asking "what else is this" from a card about a different file needs it there.
        for key, members in clusters.items():
            copies = live_copies(members, now)
            for m in members:
                _write_fact(c, org_id=org_id, node_id=m.node_id,
                            field_name="derived.document_cluster_key", value=key,
                            value_type="string", now=now)
                _write_fact(c, org_id=org_id, node_id=m.node_id,
                            field_name="derived.document_live_copies", value=copies,
                            value_type="number", now=now)
                written += 2

        minted: dict[str, set[str]] = {d: set() for d in domains}
        for artefact, inputs in findings:
            present = set(artefact.facts)
            last_seen = artefact.modified_at
            for domain in domains:
                stype = spec_for(domain).type_for(ANCHOR_DOCUMENT)
                corr = f"corr_doc_{artefact.node_id}_{domain}"
                minted[domain].add(corr)
                pct, gaps = coverage_score(present_fields=present,
                                           expected=spec_for(domain).fields_for(stype))
                coverage = (COVERAGE_UNKNOWN if pct == COVERAGE_UNKNOWN
                            else min(COVERAGE_CAP_PCT, pct))
                fresh, fresh_known = freshness_score(last_seen_at=last_seen, now=now)
                # ONE source and ONE event, honestly. Everything in this reading came out of a
                # single file-store response; there is no second system agreeing with it, and
                # `evidence_score` prices that correctly rather than being talked up here.
                evidence = evidence_score(event_count=1, source_count=1)
                _upsert(c, org_id=org_id, corr=corr, node_id=artefact.node_id, stype=stype,
                        domain=domain, now=now, coverage=coverage,
                        missing=list(MISSING) + gaps,
                        inputs={**inputs, "reading": ANCHOR_DOCUMENT,
                                "coverage_cap_pct": COVERAGE_CAP_PCT},
                        evidence=evidence,
                        freshness=fresh if fresh_known else None,
                        last_seen=last_seen)
                written += 1

        for domain, live in minted.items():
            written += _reconcile(c, org_id=org_id,
                                  stype=spec_for(domain).type_for(ANCHOR_DOCUMENT),
                                  live=live, now=now)
    return written


def _upsert(conn, *, org_id: str, corr: str, node_id: str, stype: str, domain: str,
            now: datetime, coverage: int, missing: list[str], inputs: dict,
            evidence: int, freshness: int | None, last_seen: datetime | None) -> None:
    """One situation row. `overall` is the MINIMUM of the trust dimensions, never the average, and
    a dimension with no basis is LEFT OUT rather than scored zero — a file with no modification
    stamp tells us nothing about currency, and scoring that as stale would turn missing data into
    bad news.

    Identity is a full 100 and that is not a claim about the DOCUMENT. The anchor is one file,
    keyed on the id its store issued, and there is no question about which file it is. Whether it
    is the same document as the copy in the next folder is a different question entirely, and it
    is answered — honestly and partially — by `derived.document_live_copies` and by the
    supersession entry in `missing`, not by inflating this number.

    Every number here is a PERCENT (`situations.SCORE_MAX`). They were basis points, which the
    `situation_bso._bp` seam re-multiplied into a saturated 10000 on the way to Layer 3.
    """
    trust = [evidence, 100, 100] + ([freshness] if freshness is not None else [])
    held = conn.execute(text(
        "select situation_id from context_situations where org_id=:o and correlation_id=:c"),
        {"o": org_id, "c": corr}).scalar()
    conn.execute(text(
        "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
        "  situation_type, domain, status, confidence_overall, confidence_evidence, "
        "  confidence_freshness, confidence_consistency, confidence_identity, coverage, missing, "
        "  inputs, first_seen_at, last_seen_at, computed_at) "
        "values (:sid, :o, :c, :n, :st, :d, 'active', :ov, :ev, :fr, 100, 100, :cov, "
        "  cast(:missing as jsonb), cast(:inputs as jsonb), :last, :last, :now) "
        "on conflict (org_id, correlation_id) do update set "
        "  status = 'active', resolved_by = null, resolved_at = null, "
        "  confidence_overall = excluded.confidence_overall, "
        "  confidence_evidence = excluded.confidence_evidence, "
        "  confidence_freshness = excluded.confidence_freshness, "
        "  coverage = excluded.coverage, missing = excluded.missing, "
        "  inputs = excluded.inputs, last_seen_at = excluded.last_seen_at, "
        "  situation_type = excluded.situation_type, computed_at = excluded.computed_at"),
        {"sid": held or new_id("sit"), "o": org_id, "c": corr, "n": node_id, "st": stype,
         "d": domain, "ov": min(trust), "ev": evidence, "fr": freshness or 0,
         "cov": coverage, "missing": json.dumps(missing), "now": now,
         "inputs": json.dumps(inputs, default=str), "last": last_seen or now})


def _reconcile(conn, *, org_id: str, stype: str, live: set[str], now: datetime) -> int:
    """Close the rows this sweep no longer finds, as RESOLVED BY FACT.

    By fact rather than by a human, so it un-resolves by itself if the gap returns — the system
    must not need somebody to undo a conclusion it drew from data that has since changed. This is
    what closes a document when an owner is named, when the second copy stops being edited, and
    when a stale policy is finally updated.
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
    "ANCHOR_DOCUMENT", "Artefact", "COVERAGE_CAP_PCT", "CANON_GOVERNANCE_KINDS",
    "DOCUMENT_MIMES", "GAP_LIVE_COPIES", "GAP_NO_OWNER", "GAP_ORPHAN", "GAP_UNMAINTAINED",
    "GOVERNANCE_TERMS", "LIVE_COPY_DAYS", "MISSING", "OWNER_SEEN_DAYS", "Register",
    "SCAN_CHARS", "UNMAINTAINED_DAYS", "gaps_for", "gather", "governance_term",
    "is_document_mime", "live_copies", "read_register", "refresh_document_situations",
    "register_domains",
]
