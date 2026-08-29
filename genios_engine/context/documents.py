"""L2 · Documents — the file as a subject, and its identity across copies.

THE GAP THIS CLOSES, and it is a projection rather than a connector.

`capture/connectors/drive.py` has always listed Drive, downloaded every file and extracted its
text. What it never did was project the file's own record of itself — id, revision counter,
modification stamp, owner, last-modifying user — into facts, so `document.id`,
`document.version` and `document.owner_email` had no writer despite arriving in the same HTTP
response as the body. `select distinct field from graph_facts` on the design partner's org
returned eleven prefixes and none of them was `document`, which is why five authored records
capabilities had no trigger at all.

The body went somewhere worse than nowhere. `pipeline.process_event` files extracted content on
`canon_node or sender_node`, and a Drive file has no canon kind, so the sender wins — and the
sender of a Drive file is `lastModifyingUser`. Every clause of the security policy was therefore
recorded as a fact about the colleague who last fixed a typo in it. This module gives the file a
node of its own so its contents are facts about the DOCUMENT, which is the same correction
`canon.py` made for written policies.

WHY `document` IS NOT IN `ANCHOR_PRIORITY`, and why its title is not a canon alias.

Both were deliberate and both are the same refusal. `choose_anchors` returns only the strongest
tier present, so a document reachable from correspondence would take an email that merely
mentions "Security Policy" and anchor it on the policy instead of on the customer who wrote it —
the filing-cabinet flood `canon.py` already warns about, where the handful of situations that
need attention are buried under everything the company has ever written down. `correlation.py`
says the same thing in its own words: "anything else (meeting, document, commitment) describes a
situation rather than anchoring one." Documents get their situations from the sweep in
`context/document_register.py`, which mints them directly and never through correlation.

WHAT IS DELIBERATELY NOT WRITTEN HERE. `document.approved_at` and `document.retention_until`.
Neither is a Drive concept. Drive offers revision history, comments and suggestion-accepts, and
not one of them is an approval; a retention date needs a schedule this tenant has never stated
anywhere, so there is no clock and none can be derived. They stay absent so every situation's
`missing` says so on its face — because a records system that reports coverage it does not have
is worse than one that reports a gap, and an audit is exactly where somebody finds out.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.context.canon import canon_title_key
from genios_engine.context.identity import ALIAS_EMAIL, resolve_alias
from genios_engine.platform.identity import norm_email

#: The graph node type a file becomes. Named in `domain_spec.situation_types` by any domain that
#: wants the reading, which is the whole opt-in — nothing here knows a domain by name.
DOCUMENT_NODE_TYPE = "document"

#: System of record for the file's OWN metadata, and only for that. Rank 3 is what the structured
#: lane uses, and it is the right rank for the same reason: Drive is not inferring who owns this
#: file or when it was last touched, it is reporting it. The file's CONTENTS still land at the
#: extraction rank, because a sentence inside a policy is a claim the model read, not a record
#: Drive keeps.
DOCUMENT_AUTHORITY_RANK = 3

#: person → document edges. Two verbs rather than one, because they are two different claims and
#: the difference is the whole subdomain: the person who last edited a policy is very often not
#: the person accountable for it, and a records system that conflates them reports an owner for
#: every document that anyone has ever opened.
EDGE_OWNS = "owns"
EDGE_EDITED = "edited"


def _fact_confidence() -> float:
    """Rank 3's deterministic confidence, read from the one table that owns it.

    Imported inside the function because `pipeline.py` imports this module — restating the number
    here would be a second copy of a table whose whole point is that there is one.
    """
    from genios_engine.context.pipeline import FACT_CONF_BY_RANK
    return FACT_CONF_BY_RANK[DOCUMENT_AUTHORITY_RANK]


def document_key(source: str, file_id: str) -> str:
    """The canonical key a file is found by.

    Shaped `<source>:<object id>` like the structured lane and like `canon.py`, so a Drive file
    reads the same as a CRM deal or a calendar event: the file store IS the system of record for
    the file, and the id it issues is the only identifier that survives a rename.
    """
    return f"{(source or 'file').strip().lower()}:{file_id}"


def _parse_ts(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def content_fingerprint(text_content: str | None) -> str | None:
    """SHA-256 of the extracted text, or None when there was no text to read.

    Taken over the PII-MASKED text the pipeline already holds, not the original bytes, because
    that is the only form of the document Layer 2 ever sees. The cost is precise and small: two
    files differing only inside a masked span hash identically and read as one copy. The
    alternative — hashing raw bytes — would mean two exports of one document in two formats never
    matching, which is the commoner case by a wide margin.

    None rather than the hash of an empty string. A scanned policy with no text layer is "we
    could not read this", and hashing nothing would make every unreadable file identical to every
    other unreadable file, which is how a cluster of nine unrelated PDFs becomes one document with
    nine live copies.
    """
    body = (text_content or "").strip()
    return hashlib.sha256(body.encode("utf-8", "replace")).hexdigest() if body else None


#: Word boundaries that treat `_`, `.` and `-` as separators. `\b` does NOT: an underscore is a
#: word character to the regex engine, so `\bfinal\b` never matches inside `Policy_FINAL` — which
#: is the single commonest decorated filename there is, and the miss is silent. Every rule below
#: uses these instead, which is why they are named rather than inlined.
_L = r"(?<![A-Za-z0-9])"
_R = r"(?![A-Za-z0-9])"

#: Decoration a human adds to a filename that does not change which document it is.
_DECORATION = (
    re.compile(r"^\s*(copy\s+of\s+)+", re.I),                       # "Copy of Copy of Handbook"
    re.compile(r"\.(pdf|docx?|txt|md|rtf|odt|pptx?|xlsx?|csv)\s*$", re.I),
    re.compile(r"[\s._-]*\(\s*\d+\s*\)\s*$"),                       # "Handbook (1)"
    re.compile(r"[\s._-]*-?\s*copy\s*$", re.I),                     # "Handbook - Copy"
    re.compile(rf"[\s._-]*{_L}v\.?\s?\d+(\.\d+)*{_R}", re.I),       # v2, V 3.1, v.4, _v2
    re.compile(rf"[\s._-]*{_L}(final|draft|latest|current|clean|updated){_R}", re.I),
    re.compile(rf"[\s._-]*{_L}\d{{4}}[-_./]\d{{1,2}}[-_./]\d{{1,2}}{_R}"),    # 2026-08-29
    re.compile(rf"[\s._-]*{_L}\d{{1,2}}[-_./]\d{{1,2}}[-_./]\d{{2,4}}{_R}"),  # 29-08-2026
)


def strip_version_decoration(title: str | None) -> str:
    """A filename reduced to the document it names.

    "Security Policy v2", "Security Policy_FINAL", "Copy of Security Policy (1)" and
    "security-policy-2026-08-29.docx" are four filenames for one document, and every one of them
    exists in every Drive that has ever been used by more than one person.

    Bare digits are NOT stripped. "Q3 2026 Budget" and "Q4 2026 Budget" are two different
    documents, and a rule aggressive enough to remove "v2" from the first list would merge those
    two into one and then report a version conflict between them — a fabricated finding about the
    one artefact class where a fabricated finding is most expensive. So a version token is
    stripped only when it carries its own marker (`v`), and a date only in a full date shape.
    """
    out = title or ""
    for _ in range(3):                 # decorations stack: "Copy of Handbook v2 FINAL (1).docx"
        before = out
        for rule in _DECORATION:
            out = rule.sub(" ", out)
        if out == before:
            break
    return out.strip()


def cluster_key(title: str | None) -> str | None:
    """The key two copies of one document share, or None when the title says nothing.

    EXACT EQUALITY ON A DERIVED KEY, which is `identity.py`'s law applied to filenames: fuzziness
    lives in how the key is derived and never in how two keys are compared. There is no edit
    distance here and there will not be one — "Security Policy" and "Security Policies" are 1
    character apart and are routinely two different documents, and a 0.94 match that silently
    merges them is a permanent, invisible join of exactly the kind `identity.py` refuses.

    Clustering is NOT merging. Nothing here proposes a merge or moves a fact: the members stay
    separate nodes, and the only thing written is how many live copies each one is part of. Two
    Drive files ARE two files even when they hold one document, and a records reading that fused
    them would destroy the very evidence it exists to report.
    """
    return canon_title_key(strip_version_decoration(title)) or None


def register_document_node(conn, store, *, org_id: str, source: str, meta: dict,
                           content: str | None, event_id: str,
                           owner_node: str | None = None,
                           editor_node: str | None = None,
                           occurred_at: datetime | None = None) -> str | None:
    """Project one file's metadata onto a `document` node. Returns the node id, or None.

    None when the source gave no file id — the only identifier that survives a rename, so without
    it there is nothing to key identity on and inventing one from the title would make every
    rename a new document and every version conflict invisible.

    Facts land at rank 3 and are written through `store.write_fact` rather than a raw upsert, so
    a re-sync of an unchanged file is a no-op instead of a new version row, and a stale Drive read
    arriving after a fresher one lands as `historical` rather than overwriting it. That is the
    same treatment a CRM row gets, and for the same reason.
    """
    file_id = str(meta.get("file_id") or "").strip()
    if not file_id:
        return None

    title = (meta.get("name") or "").strip()
    node_id = store.find_or_create_node(
        conn, org_id=org_id, node_type=DOCUMENT_NODE_TYPE,
        canonical_key=document_key(source, file_id),
        display_name=title or file_id, event_id=event_id)

    # THE TITLE IS NOT CLAIMED AS AN ALIAS, and this is the same refusal as staying out of
    # `ANCHOR_PRIORITY`. `resolve_canon_mention` matches a name in prose against the canon alias
    # table; registering document titles there would make an email that merely says "as per the
    # Security Policy" attach its facts to the policy instead of to the customer who wrote it.
    # Every mention of a document would leave the conversation it was part of.

    modified_at = _parse_ts(meta.get("modified_at"))
    at = modified_at or occurred_at or datetime.now(timezone.utc)
    conf = _fact_confidence()

    pairs: list[tuple[str, object, str]] = [
        ("document.id", file_id, "string"),
        ("document.mime", meta.get("mime") or "", "string"),
    ]
    if title:
        pairs.append(("document.title", title, "string"))
    if meta.get("version") is not None:
        # Drive's REVISION COUNTER, not the document's version. v3 of the security policy is not
        # `version: 3`; it is `version: 47` because somebody fixed forty-four typos. It is written
        # because it tells two copies of one file apart, and the situation payload names it a
        # revision count so nothing downstream reads a semantic version into it.
        pairs.append(("document.version", str(meta["version"]), "string"))
    if modified_at is not None:
        pairs.append(("document.modified_at", modified_at.isoformat(), "timestamp"))
    created_at = _parse_ts(meta.get("created_at"))
    if created_at is not None:
        pairs.append(("document.created_at", created_at.isoformat(), "timestamp"))
    # Through `norm_email` and ONLY through it, with no raw fallback. It is the function every
    # layer that mints a person key already uses, so an owner written any other way would not join
    # to the person node the address belongs to — the ownership check would then find nobody and
    # report a gap on a document whose owner is sitting in the graph. A value it cannot parse is
    # not an address (a shared-drive group name, an empty object) and stays absent, which the
    # no-owner gate reads correctly as "we do not know who owns this".
    owner_email = norm_email(meta.get("owner_email"))
    if owner_email:
        pairs.append(("document.owner_email", owner_email, "string"))
    editor_email = norm_email(meta.get("last_modified_by"))
    if editor_email:
        pairs.append(("document.last_modified_by", editor_email, "string"))
    if meta.get("web_link"):
        pairs.append(("document.location", str(meta["web_link"]), "string"))
    if meta.get("shared") is not None:
        pairs.append(("document.shared", bool(meta["shared"]), "boolean"))
    fingerprint = content_fingerprint(content)
    if fingerprint:
        pairs.append(("document.content_hash", fingerprint, "string"))

    for field, value, value_type in pairs:
        store.write_fact(conn, org_id=org_id, subject_node_id=node_id, field=field,
                         value=value, value_type=value_type, confidence=conf,
                         occurred_at=at, event_id=event_id,
                         evidence={"derived": "file metadata", "file_id": file_id},
                         source=source, authority_rank=DOCUMENT_AUTHORITY_RANK)

    for person_node, edge_type in ((owner_node, EDGE_OWNS), (editor_node, EDGE_EDITED)):
        if person_node:
            store.write_edge(conn, org_id=org_id, edge_type=edge_type,
                             from_node_id=person_node, to_node_id=node_id, confidence=0.9,
                             occurred_at=at, event_id=event_id,
                             evidence={"derived": "file metadata"}, source=source,
                             authority_rank=DOCUMENT_AUTHORITY_RANK)
    return node_id


def resolve_owner_node(conn, *, org_id: str, email: str | None) -> str | None:
    """An owner address → the person node already in this graph, or None.

    RESOLVE, NEVER CREATE, and the asymmetry with the pipeline's own `_person` is deliberate. A
    Drive owner is usually a colleague who has never written to anybody the tenant corresponds
    with, so minting a node for them would add a person with zero observations, zero edges and no
    correspondence — which every other reading in Layer 2 reads as somebody who has gone quiet.
    One projection would be filling the relationship graph with people who are not in a
    relationship with anyone.

    None is a real answer and the interesting one: an owner this graph has never seen is exactly
    the state the no-owner gate is looking for.
    """
    key = norm_email(email)
    return resolve_alias(conn, org_id=org_id, alias_type=ALIAS_EMAIL,
                         alias_key=key) if key else None


def document_nodes(conn, org_id: str) -> list[dict]:
    """Every live document node with its `document.*` facts, in two queries.

    One query per concept rather than one per node — the shape `refresh_situations`,
    `refresh_attention` and `support_situations.gather` already keep, because the alternative on a
    pooled remote Postgres is a network turn per file and a Drive of any size makes the sweep the
    slowest thing in the drain.
    """
    rows = conn.execute(text(
        "select node_id, display_name from graph_nodes "
        "where org_id=:o and node_type=:t and valid_to is null"),
        {"o": org_id, "t": DOCUMENT_NODE_TYPE}).fetchall()
    if not rows:
        return []
    facts: dict[str, dict[str, str]] = {}
    for r in conn.execute(text(
            "select subject_node_id, field, value #>> '{}' as v from graph_facts "
            "where org_id=:o and valid_to is null and status='active' "
            "  and field like 'document.%'"), {"o": org_id}):
        facts.setdefault(r.subject_node_id, {})[r.field] = r.v
    return [{"node_id": r.node_id, "display_name": r.display_name or "",
             "facts": facts.get(r.node_id, {})} for r in rows]


__all__ = [
    "DOCUMENT_AUTHORITY_RANK", "DOCUMENT_NODE_TYPE", "EDGE_EDITED", "EDGE_OWNS",
    "cluster_key", "content_fingerprint", "document_key", "document_nodes",
    "register_document_node", "resolve_owner_node", "strip_version_decoration",
]
