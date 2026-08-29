"""The file's own metadata, from the Drive response to the graph node.

THE BUG THIS PINS, in one sentence: the connector fetched everything the records subdomain needed
and threw it away. `capture/connectors/drive.py` listed Drive, downloaded each file and extracted
its text, and then kept only the name and the body — so `document.id`, `document.version` and
`document.owner_email` had no writer while the data was arriving in the same HTTP response as the
body, and five authored records capabilities had no trigger at all.

The body went somewhere worse than nowhere. `pipeline.process_event` files extracted content on
`canon_node or sender_node`, and the SENDER of a Drive event is its `lastModifyingUser` — so every
clause of the security policy was recorded as a fact about the colleague who last fixed a typo in
it. That is the same fault `canon.py` was written to fix for uploaded policies, arriving through a
different door.

Two refusals are pinned as hard as the projection itself, because both would be silent:
`document` must never join `ANCHOR_PRIORITY`, and a document title must never become a canon
alias. Either one would let an email that merely mentions "Security Policy" anchor on the policy
instead of on the customer who wrote it.
"""
from __future__ import annotations

import inspect

from genios_engine.capture.connectors.drive import ComposioDriveConnector, file_metadata
from genios_engine.context.documents import (
    DOCUMENT_AUTHORITY_RANK,
    DOCUMENT_NODE_TYPE,
    cluster_key,
    content_fingerprint,
    document_key,
    strip_version_decoration,
)

FILE = {
    "id": "1AbCdEf", "name": "Information Security Policy v2.docx",
    "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "modifiedTime": "2026-07-30T09:00:00Z", "createdTime": "2024-01-04T11:00:00Z",
    "version": "47", "webViewLink": "https://docs.google.com/document/d/1AbCdEf",
    "parents": ["fld_policies"], "shared": True, "trashed": False,
    "owners": [{"emailAddress": "Ops@Acme.io", "displayName": "Ops"}],
    "lastModifyingUser": {"emailAddress": "intern@acme.io", "displayName": "Intern"},
}


class _FakeExec:
    """Stands in for ComposioExec — canned responses, no network, and a record of what was asked."""

    def __init__(self, responses: dict, *, reject: set[str] = frozenset()) -> None:
        self._r = responses
        self._reject = reject
        self.calls: list[tuple[str, dict]] = []

    def execute(self, action: str, args: dict | None = None) -> dict:
        self.calls.append((action, dict(args or {})))
        if action in self._reject and "fields" in (args or {}):
            raise RuntimeError("unknown argument 'fields'")
        return self._r.get(action, {})


# ── L1 · what the connector now carries ──────────────────────────────────────────────────────

def test_the_metadata_that_was_arriving_and_being_discarded_is_carried():
    """Every field here was in the Drive response before this change and reached nothing."""
    meta = file_metadata(FILE)
    assert meta["file_id"] == "1AbCdEf"
    assert meta["version"] == "47"
    assert meta["modified_at"] == "2026-07-30T09:00:00Z"
    assert meta["created_at"] == "2024-01-04T11:00:00Z"
    assert meta["owner_email"] == "ops@acme.io"                 # lowercased, like every other key
    assert meta["last_modified_by"] == "intern@acme.io"
    assert meta["web_link"].endswith("1AbCdEf")
    assert meta["shared"] is True


def test_the_owner_is_never_defaulted_to_whoever_last_edited_it():
    """The single failure this subdomain exists to catch is a controlled document with nobody
    accountable for it. Drive omits `owners[]` on a file whose owner is outside the requester's
    visibility, and falling back to `lastModifyingUser` there would make that document report an
    owner — the gap would read as healthy on exactly the files where it is true."""
    meta = file_metadata({**FILE, "owners": []})
    assert meta["owner_email"] is None
    assert meta["last_modified_by"] == "intern@acme.io"          # still known, still not the owner


def test_an_owner_with_no_address_is_unknown_rather_than_empty():
    """A shared drive returns the owner object without `emailAddress`. An empty string would land
    as a `document.owner_email` fact whose value is nothing, and the no-owner gate — which asks
    whether the fact exists — would read that as an owner."""
    assert file_metadata({**FILE, "owners": [{"displayName": "A Team"}]})["owner_email"] is None


def test_the_metadata_rides_beside_the_parse_provenance_without_disturbing_it(monkeypatch):
    """`gate/rules.py::content_integrity_rule` parks a file on `document.status`, and
    `PostgresDocumentJobStore` reads nine named keys out of the same dict. Adding the file's own
    metadata to it must leave both of those reading exactly what they read before."""
    import genios_engine.capture.connectors.drive as drive_mod

    class _R:
        text = "This policy sets out how we handle information security."
        native_parse_used, ocr_used, ocr_engine, ocr_pages = True, False, None, 0
        avg_confidence, status = 1.0, "accepted"

    monkeypatch.setattr(drive_mod, "process_document", lambda **kw: _R())
    conn = ComposioDriveConnector.__new__(ComposioDriveConnector)
    conn._x, conn._ocr = _FakeExec({"GOOGLEDRIVE_DOWNLOAD_FILE": {"text": "x"}}), None

    doc = conn._to_raw(FILE).raw["document"]
    assert doc["status"] == "accepted" and doc["native_parse_used"] is True
    assert doc["file_id"] == "1AbCdEf" and doc["owner_email"] == "ops@acme.io"


def test_the_field_mask_is_asked_for_and_never_costs_us_the_feed():
    """`fields` is a Drive API parameter, not a Composio one, and the version of the tool wrapper
    is not pinned (`dangerously_skip_version_check=True`). LIST is the connector's only call, so a
    rejected argument would stop the entire Drive feed — to buy metadata that is optional to every
    consumer. One retry without the mask makes the worst case the connector we already had."""
    conn = ComposioDriveConnector.__new__(ComposioDriveConnector)
    conn._x = _FakeExec({"GOOGLEDRIVE_LIST_FILES": {"files": []}})
    conn._ocr = None
    conn._list(limit=5, page_token=None)
    assert "fields" in conn._x.calls[0][1]

    strict = _FakeExec({"GOOGLEDRIVE_LIST_FILES": {"files": []}}, reject={"GOOGLEDRIVE_LIST_FILES"})
    conn._x = strict
    assert conn._list(limit=5, page_token=None) == {"files": []}
    assert len(strict.calls) == 2 and "fields" not in strict.calls[1][1]


# ── L2 · identity across copies ──────────────────────────────────────────────────────────────

def test_the_four_filenames_one_document_actually_reaches_one_key():
    """"Security Policy v2", "Security Policy_FINAL", "Copy of Security Policy (1)" and
    "security-policy-2026-08-29.docx" are four filenames for one document, and every one of them
    exists in every Drive that more than one person has used. If they do not collapse to one key,
    the version question — the thing the situation file calls the only reason this is a capability
    rather than a filing metaphor — cannot be asked at all."""
    keys = {cluster_key(t) for t in (
        "Security Policy v2", "Security Policy_FINAL", "Copy of Security Policy (1)",
        "security-policy-2026-08-29.docx", "Security Policy  V 3.1 - Copy")}
    assert len(keys) == 1, keys
    assert next(iter(keys))


def test_bare_digits_survive_because_two_quarters_are_two_documents():
    """The tempting rule — strip trailing numbers — merges "Q3 2026 Budget" into "Q4 2026 Budget"
    and then reports a version conflict between two documents that were never the same one. A
    fabricated finding is worst precisely here, so a version token is stripped only when it
    carries its own marker."""
    assert cluster_key("Q3 2026 Budget") != cluster_key("Q4 2026 Budget")
    assert strip_version_decoration("Policy 2026 Handbook") == "Policy 2026 Handbook"


def test_two_documents_one_word_apart_are_not_clustered():
    """`identity.py`'s law, applied to filenames: exact equality on a derived key, never a
    similarity score. "Travel Policy" and "Travel Policies" are one character apart and are
    routinely the same document; "Travel Policy" and "Trading Policy" are three and never are.
    Nothing here will guess, which is why the derivation is the only place fuzziness lives."""
    assert cluster_key("Travel Policy") != cluster_key("Trading Policy")


def test_an_unreadable_file_has_no_fingerprint_rather_than_a_shared_one():
    """A scanned policy with no text layer is "we could not read this". Hashing the empty string
    would make every unreadable PDF identical to every other one, which is how a folder of nine
    unrelated scans becomes one document with nine live copies."""
    assert content_fingerprint("") is None
    assert content_fingerprint("   ") is None
    assert content_fingerprint("a") != content_fingerprint("b")
    assert content_fingerprint("policy text") == content_fingerprint("policy text")


def test_the_node_key_is_the_id_the_store_issued():
    """The only identifier that survives a rename. Keying on the title instead would make every
    rename a new document and every version conflict invisible — which inverts the one thing
    version_control exists to do."""
    assert document_key("gdrive", "1AbCdEf") == "gdrive:1AbCdEf"


# ── the two refusals ─────────────────────────────────────────────────────────────────────────

def test_a_document_can_never_anchor_a_correlation():
    """`choose_anchors` returns only the strongest tier present. A document in `ANCHOR_PRIORITY`
    would take every email that mentions a policy and file it under the policy instead of under
    the customer who wrote it — the filing-cabinet flood, where the handful of situations that
    need attention are buried under everything the company has ever written down."""
    from genios_engine.context.correlation import ANCHOR_PRIORITY, choose_anchors
    assert DOCUMENT_NODE_TYPE not in ANCHOR_PRIORITY
    anchors = choose_anchors({"d1": DOCUMENT_NODE_TYPE, "p1": "person"}, "admin")
    assert [a.node_id for a in anchors] == ["p1"]
    assert choose_anchors({"d1": DOCUMENT_NODE_TYPE}, "admin") == []


def test_a_document_title_is_not_registered_as_a_canon_alias():
    """The other half of the same refusal. `resolve_canon_mention` matches a name in prose against
    the canon alias table, so registering titles there would make "as per the Security Policy" in
    an ordinary email attach its facts to the policy — every mention of a document would leave the
    conversation it was part of."""
    from genios_engine.context import documents
    source = inspect.getsource(documents)
    assert "ALIAS_CANON" not in source
    assert "record_alias" not in source


def test_the_pipeline_files_content_on_the_document_and_not_on_its_last_editor():
    """The seam, and the order in it. Canon still wins — a file the org tagged `policy` is a
    deliberate statement at rank 4 — and the document beats the sender for exactly the reason canon
    does: a Drive file's sender is whoever last fixed a typo in it."""
    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "content_subject = canon_node or document_node or sender_node" in source
    # Resolve, never create. A Drive owner is usually a colleague who has written to nobody, and
    # minting a node for them would add a person with no observations and no edges — which every
    # other Layer 2 reading treats as somebody who has gone quiet.
    assert "resolve_owner_node(conn" in source
    assert "_person(doc_meta" not in source


def test_the_file_is_a_system_of_record_for_itself_and_nothing_else():
    """Rank 3, the same rank the structured lane uses, and for the same reason: Drive is not
    inferring who owns this file, it is reporting it. The file's CONTENTS stay at the extraction
    rank, because a sentence inside a policy is a claim a model read."""
    from genios_engine.context.pipeline import FACT_CONF_BY_RANK
    assert DOCUMENT_AUTHORITY_RANK == 3
    assert FACT_CONF_BY_RANK[DOCUMENT_AUTHORITY_RANK] == 0.90
