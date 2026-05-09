"""
Generic IMAP pull adapter — for self-hosted email servers without webhook
support. Customer provides host/port/username/password; Genios connects via
imaplib, fetches unread, marks read, returns canonical events.

Use case: Inkbox-class customers who run their own SMTP/IMAP infra and
don't have an HTTP API. Standard IMAP-over-TLS works out of the box.
"""

from __future__ import annotations

import email
import imaplib
import logging
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

from . import register

logger = logging.getLogger(__name__)
IMAP_TIMEOUT = 20


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


def fetch_emails(credentials: dict, since_iso: Optional[str] = None) -> list[dict]:
    """credentials: {host, port, username, password, ssl=True}.
    Pulls UNSEEN messages, returns canonical events. Caller marks read."""
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
        typ, data = M.search(None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            return []
        ids = data[0].split()[:50]  # cap per-sync to avoid floods
        results = []
        for mid in ids:
            typ, msg_data = M.fetch(mid, "(RFC822)")
            if typ != "OK" or not msg_data:
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
        return results
    finally:
        try: M.logout()
        except Exception: pass


def mark_read(credentials: dict, external_id: str) -> bool:
    """IMAP marks via SEEN flag — done implicitly when iter scan re-runs since
    the FETCH already touched the message. We could explicitly STORE +FLAGS but
    keep it noop for now (UNSEEN search will still skip them on next pass)."""
    return True


def _register():
    register("imap", {
        "fetch_email": fetch_emails,
        "mark_read":   mark_read,
    })
    register("custom", {  # alias — generic "custom" provider defaults to IMAP
        "fetch_email": fetch_emails,
        "mark_read":   mark_read,
    })


_register()
