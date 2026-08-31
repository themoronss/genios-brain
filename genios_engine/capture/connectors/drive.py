from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from genios_engine.capture.documents.native import process_document

from .base import RawObject, SourceBatch
from .composio_base import ComposioExec

# Google Drive via Composio. Files are DOCUMENTS → download, extract text NATIVELY
# (HTML/docx/pdf/txt — no OCR), and hand the text to the gate/L2. Scanned images with
# no text layer would need OCR (Tesseract), wired separately. Paths finalized live.
#
# THE FILE'S OWN METADATA, which this connector fetched and then dropped on the floor.
#
# Drive answers `files.list` with an id, a version counter, a modification stamp, an owner and a
# last-modifying user. Until now `_to_raw` kept the name and the extracted body and discarded the
# rest, so `document.id`, `document.version` and `document.owner_email` had no writer despite the
# data arriving in the same response — which is why five authored records capabilities
# (document_control, filing_and_retrieval, version_control, retention_and_archival,
# knowledge_base_maintenance) had no trigger and the whole subdomain was dark.
#
# It rides in `raw["document"]` beside the parse provenance already there. Both consumers of that
# dict read named keys — `gate/rules.py::content_integrity_rule` reads `status`, and
# `PostgresDocumentJobStore.put` names its nine columns — so extra keys are inert to them and the
# L2 projection gets one object to read instead of two.


#: The Drive fields the projection needs, as the API's own mask. Asked for explicitly because the
#: `files.list` default is `id, name, mimeType, kind` — `modifiedTime` and `lastModifyingUser`
#: are already load-bearing here (the `since` filter, `occurred_at`, `content_version` and the
#: actor all read them), so the connector was already relying on the wrapper to widen the default
#: for it. Naming the set makes that dependency visible instead of ambient.
FILE_FIELDS = ("nextPageToken, files(id,name,mimeType,modifiedTime,createdTime,version,"
               "webViewLink,parents,shared,trashed,owners(emailAddress,displayName),"
               "lastModifyingUser(emailAddress,displayName))")

#: What a REJECTED ARGUMENT looks like, in the only form we can see it. The Composio SDK raises its
#: own exception types out of a version we deliberately do not pin, so there is no class to catch
#: — but a 400-class rejection of an unknown parameter says so in its message, and an auth, quota,
#: rate-limit or deadline failure never does. Positive evidence, so an unrecognised failure
#: surfaces on the first call instead of being paid for twice.
_FIELD_MASK_REJECTED = ("fields", "invalid_argument", "invalid argument", "unknown parameter",
                        "unrecognized", "unrecognised", "badrequest", "bad request",
                        "invalid parameter", "400", "422")

#: Checked FIRST, because these strings can co-occur with the ones above in a long provider
#: message (a 403 body that also lists the request's `fields`) and none of them is ever fixed by
#: dropping the mask. A retry here doubles the pressure at exactly the wrong moment: a second
#: identical call against a rate limit we are already hitting, or a second 60s wait on the
#: `composio_base.execute` deadline.
_NEVER_RETRY = ("401", "403", "429", "unauthor", "unauthenticated", "forbidden", "permission",
                "quota", "rate limit", "ratelimit", "expired", "timeout", "timed out")


def _rejects_the_field_mask(exc: BaseException) -> bool:
    """Whether this failure is plausibly the `fields` mask being rejected, and only then.

    A timeout is excluded by TYPE as well as by text: `composio_base.execute` bounds every call
    with `.result(timeout=...)`, so a hung Drive call raises TimeoutError — and retrying it means
    the connector waits the deadline twice before the sweep learns anything.
    """
    if isinstance(exc, TimeoutError):
        return False
    message = f"{type(exc).__name__}: {exc}".lower()
    if any(hint in message for hint in _NEVER_RETRY):
        return False
    return any(hint in message for hint in _FIELD_MASK_REJECTED)


def _parse_ts(s: str | None) -> datetime:
    if isinstance(s, str):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _email_of(party: Any) -> str | None:
    """An `owners[i]` / `lastModifyingUser` entry → its address, lowercased, or None.

    Drive omits the whole sub-object on a file whose owner is outside the requester's
    visibility, and omits `emailAddress` on a shared drive where the caller cannot see members.
    Both come back as "we do not know who owns this", which is a FINDING for the records
    reading — so it must arrive as None and never as an empty string, or `document.owner_email`
    lands as a fact whose value is nothing and the no-owner gate reads it as satisfied.
    """
    if not isinstance(party, dict):
        return None
    addr = party.get("emailAddress")
    return (addr.strip().lower() or None) if isinstance(addr, str) else None


def file_metadata(f: dict) -> dict[str, Any]:
    """The Drive file's own record of itself, carried through untouched.

    Nothing is defaulted and nothing is inferred. A missing `owners[]` stays missing rather than
    falling back to `lastModifyingUser`: the person who last edited a policy is very often not
    its owner, and quietly promoting one to the other would make the single failure this
    subdomain exists to catch — a controlled document with nobody accountable for it — report as
    healthy on exactly the files where it is true.

    `version` is Drive's REVISION COUNTER, not the document's version. v3 of the security policy
    is not `version: 3`; it is `version: 47` because somebody fixed a typo forty-four times. It
    is carried because it distinguishes two copies of one file, and it is named in the situation
    payload as a revision count so nobody reads a semantic version into it.
    """
    owner = _email_of((f.get("owners") or [None])[0])
    return {
        "file_id": str(f.get("id") or "") or None,
        "name": f.get("name") or "",
        "mime": f.get("mimeType") or "",
        "version": str(f.get("version")) if f.get("version") is not None else None,
        "modified_at": f.get("modifiedTime") or None,
        "created_at": f.get("createdTime") or None,
        "owner_email": owner,
        "last_modified_by": _email_of(f.get("lastModifyingUser")),
        "web_link": f.get("webViewLink") or None,
        "parents": list(f.get("parents") or ()),
        "shared": bool(f.get("shared")) if f.get("shared") is not None else None,
    }


def _raw_bytes(dl: dict) -> bytes | str:
    """Best-effort: pull file content out of the download response (text or base64)."""
    for k in ("content", "text", "data", "file", "body"):
        v = dl.get(k)
        if isinstance(v, str) and v:
            try:
                return base64.b64decode(v, validate=True)
            except Exception:
                return v
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
    return ""


class ComposioDriveConnector:
    source = "gdrive"

    def __init__(self, *, api_key: str, user_id: str, ocr=None) -> None:
        self._x = ComposioExec(api_key=api_key, user_id=user_id)
        self._ocr = ocr                  # OcrEngine | None — native-only if None

    def _list(self, *, limit: int, page_token: str | None) -> dict:
        args: dict[str, Any] = {"pageSize": limit,
                                "q": "trashed = false and mimeType != 'application/vnd.google-apps.folder'",
                                "fields": FILE_FIELDS}
        if page_token:
            args["pageToken"] = page_token
        try:
            return self._x.execute("GOOGLEDRIVE_LIST_FILES", args)
        except Exception as exc:     # noqa: BLE001 — the mask is an ENRICHMENT, never a dependency
            # `fields` is a Drive API parameter, not a Composio one, so whether it survives the
            # tool wrapper is a property of a version of Composio we do not pin
            # (`dangerously_skip_version_check=True` in composio_base). A rejected argument would
            # 400 the LIST call, and this is the only call the connector has: the whole Drive feed
            # would stop, and it would stop to buy metadata that is optional to every consumer.
            # One retry without the mask, so the worst case is the connector we already had.
            #
            # NARROWED, and the width was the defect. `except Exception` retried on EVERY failure
            # — an expired token, a 429, a quota exhaustion, the 60s deadline in
            # `composio_base.execute` — none of which has anything to do with the mask. Each one
            # bought a second identical call before surfacing: double the rate-limit pressure at
            # exactly the moment we are being rate-limited, and double the wall-clock on the
            # timeout path, on the connector's only call. The retry now needs POSITIVE evidence
            # that the argument itself was rejected, so anything unrecognised surfaces on the
            # first attempt.
            if not _rejects_the_field_mask(exc):
                raise
            args.pop("fields", None)
            return self._x.execute("GOOGLEDRIVE_LIST_FILES", args)

    def _to_batch(self, data: dict, since: datetime | None = None) -> SourceBatch:
        files = data.get("files") or data.get("items") or []
        if since is not None:
            # Filter on modifiedTime BEFORE _to_raw — _to_raw downloads + extracts each
            # file, so skipping here is what stops every 6-hourly sweep from re-downloading
            # the entire Drive (`since` was previously ignored). Metadata-only compare;
            # dedup_key/content_version untouched.
            files = [f for f in files if isinstance(f, dict)
                     and _parse_ts(f.get("modifiedTime")) > since]
        objs = [self._to_raw(f) for f in files if isinstance(f, dict)]
        return SourceBatch(objects=[o for o in objs if o], next_cursor=data.get("nextPageToken"))

    def _to_raw(self, f: dict) -> RawObject | None:
        fid = f.get("id")
        if not fid:
            return None
        mime, name = f.get("mimeType") or "", f.get("name") or ""
        dl = self._x.execute("GOOGLEDRIVE_DOWNLOAD_FILE", {"file_id": str(fid)})
        r = process_document(mime=mime, data=_raw_bytes(dl), filename=name, ocr=self._ocr)
        return RawObject(
            source="gdrive", object_type="file", source_object_id=str(fid),
            occurred_at=_parse_ts(f.get("modifiedTime")),
            actor_email=((f.get("lastModifyingUser") or {}).get("emailAddress")),
            actor_type="internal_user",
            # modifiedTime bumps on every edit → new content_version → an edited file re-lands
            # and its extracted text updates, instead of being deduped to the first version seen.
            content_version=str(f.get("modifiedTime")) if f.get("modifiedTime") else None,
            raw={"subject": name, "body": r.text, "mime": mime, "has_attachment": bool(r.text),
                 "document": {"native_parse_used": r.native_parse_used, "ocr_used": r.ocr_used,
                              "ocr_engine": r.ocr_engine, "ocr_pages": r.ocr_pages,
                              "avg_confidence": r.avg_confidence, "status": r.status,
                              **file_metadata(f)}},
        )

    def validate_connection(self) -> bool:
        self._list(limit=1, page_token=None)
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._list(limit=limit, page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        return self._to_batch(self._list(limit=limit, page_token=cursor), since=since)

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return self._x.execute("GOOGLEDRIVE_DOWNLOAD_FILE", {"file_id": object_ref})
