"""
Generic IMAP pull adapter — for self-hosted email servers without webhook
support. Customer provides host/port/username/password; Genios connects via
imaplib over TLS and returns canonical events.

Sync strategy: fetch the most-recent messages in INBOX — those `SINCE` the
caller's watermark date, else the most-recent `IMAP_MAX_PER_SYNC` overall —
regardless of read state, using `BODY.PEEK[]` so the server's \\Seen flags are
NOT mutated (the brain is a read-only observer). De-duplication is handled
downstream by the `(org_id, source, external_id)` unique index, so re-seeing
the same messages on every poll is a cheap no-op.

Use case: Inkbox-class customers who run their own SMTP/IMAP infra and
don't have an HTTP API. Standard IMAP-over-TLS works out of the box.
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
from datetime import datetime
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

from . import register

logger = logging.getLogger(__name__)
IMAP_TIMEOUT = 20
try:
    IMAP_MAX_PER_SYNC = max(1, int(os.getenv("IMAP_MAX_PER_SYNC", "100")))
except ValueError:
    IMAP_MAX_PER_SYNC = 100


def _decode(s) -> str:
    if not s:
        return ""
    if isinstance(s, bytes):
        try: return s.decode()
        except Exception: return s.decode("latin-1", errors="ignore")
    out = []
    for part, enc in decode_header(s):
        if isinstance(part, bytes):
            try: out.append(part.decode(enc or "utf-8", errors="ignore"))
            except Exception: out.append(part.decode("latin-1", errors="ignore"))
        else:
            out.append(part)
    return "".join(out)


def _body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
        return ""
    payload = msg.get_payload(decode=True)
    if not payload:
        return ""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")


def _imap_date(since_iso: Optional[str]) -> Optional[str]:
    """ISO timestamp -> IMAP SEARCH date literal (DD-Mon-YYYY), or None."""
    if not since_iso:
        return None
    try:
        dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
        return dt.strftime("%d-%b-%Y")
    except Exception:
        return None


def fetch_emails(credentials: dict, since_iso: Optional[str] = None) -> list[dict]:
    """credentials: {host, port, username, password, ssl=True}.
    Pulls the most-recent INBOX messages (SINCE the watermark, else overall),
    read or not, without touching \\Seen flags. Returns canonical events."""
    host = credentials.get("host")
    user = credentials.get("username")
    pwd = credentials.get("password")
    if not (host and user and pwd):
        raise ValueError("imap adapter: host/username/password required")

    port = int(credentials.get("port") or (993 if credentials.get("ssl", True) else 143))
    use_ssl = credentials.get("ssl", True)

    try:
        if use_ssl:
            M = imaplib.IMAP4_SSL(host, port, timeout=IMAP_TIMEOUT)
        else:
            M = imaplib.IMAP4(host, port, timeout=IMAP_TIMEOUT)
        M.login(user, pwd)
    except imaplib.IMAP4.error as e:
        raise PermissionError(f"imap login failed: {e}")
    except Exception as e:
        logger.warning(f"imap connect failed: {e}")
        return []

    try:
        M.select("INBOX")
        since_date = _imap_date(since_iso)
        if since_date:
            typ, data = M.search(None, "SINCE", since_date)
        else:
            typ, data = M.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            return []
        # Highest sequence numbers = most recent; take the tail, capped.
        ids = data[0].split()[-IMAP_MAX_PER_SYNC:]
        results = []
        for mid in ids:
            try:
                # BODY.PEEK[] = fetch the full message WITHOUT setting \Seen.
                typ, msg_data = M.fetch(mid, "(BODY.PEEK[])")
                if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                    continue
                msg = email.message_from_bytes(msg_data[0][1])

                from_name, from_addr = parseaddr(msg.get("From", ""))
                to_addrs = [parseaddr(a)[1] for a in (msg.get_all("To") or [])]
                sent_at = None
                try:
                    if msg.get("Date"):
                        sent_at = parsedate_to_datetime(msg.get("Date")).isoformat()
                except Exception:
                    pass

                results.append({
                    "external_id":  msg.get("Message-ID") or f"imap_{mid.decode()}",
                    "from_address": from_addr,
                    "to":           to_addrs,
                    "subject":      _decode(msg.get("Subject")),
                    "body_text":    _body_text(msg),
                    "sent_at":      sent_at or "",
                    "direction":    "inbound",
                    "in_reply_to_external_id": msg.get("In-Reply-To"),
                    "thread_external_id":      msg.get("References", "").split()[0] if msg.get("References") else None,
                })
            except Exception as e:
                logger.warning(f"imap: skipping message {mid!r}: {e}")
                continue
        return results
    finally:
        try: M.logout()
        except Exception: pass


def verify_credentials(credentials: dict) -> tuple[bool, str]:
    """Connect-time validation: try LOGIN + SELECT INBOX. Disconnect immediately."""
    host = credentials.get("host")
    user = credentials.get("username")
    pwd = credentials.get("password")
    port = int(credentials.get("port") or 993)
    use_ssl = credentials.get("ssl", True)
    if not (host and user and pwd):
        return False, "Host, username, and password are required"
    try:
        if use_ssl:
            M = imaplib.IMAP4_SSL(host, port, timeout=IMAP_TIMEOUT)
        else:
            M = imaplib.IMAP4(host, port, timeout=IMAP_TIMEOUT)
        try:
            M.login(user, pwd)
        except imaplib.IMAP4.error as e:
            return False, f"IMAP login failed: {str(e)[:100]}"
        typ, _ = M.select("INBOX")
        if typ != "OK":
            return False, "Could not access INBOX folder"
        try: M.logout()
        except Exception: pass
        return True, f"{user}@{host}"
    except Exception as e:
        return False, f"IMAP connection failed: {str(e)[:100]}"


def _register():
    # No `mark_read`: we read with BODY.PEEK[] so \Seen is never touched —
    # the brain doesn't mutate the customer's mailbox. Dedup via external_id.
    register("imap", {
        "fetch_email": fetch_emails,
        "verify":      verify_credentials,
    })
    register("custom", {  # alias — generic "custom" provider defaults to IMAP
        "fetch_email": fetch_emails,
        "verify":      verify_credentials,
    })


_register()
