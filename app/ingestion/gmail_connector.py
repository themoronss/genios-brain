from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI

# Scopes for MVP - Gmail only (removed calendar to avoid OAuth scope mismatch)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def create_oauth_flow():

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )

    flow.redirect_uri = GOOGLE_REDIRECT_URI

    return flow


def build_gmail_service(access_token, refresh_token=None):
    """
    Build Gmail API service with credentials.

    Args:
        access_token: OAuth access token
        refresh_token: OAuth refresh token (optional, for token refresh)

    Returns:
        Gmail API service
    """
    # Build credentials with token refresh support
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )

    service = build("gmail", "v1", credentials=creds)

    return service


def fetch_emails(
    service,
    max_results=500,
    label_id=None,
    query: str = "(in:inbox OR in:sent) -label:promotions -label:social -from:noreply -from:no-reply",
    page_token: str = None,
):
    """
    Fetch emails from Gmail using a query string (q parameter) for server-side filtering.
    Returns a tuple of (messages, next_page_token) to support incremental pagination.

    Args:
        service: Gmail API service
        max_results: Maximum number of emails to return in this call (default: 500)
        label_id: DEPRECATED — kept for backwards compatibility; use `query` instead.
                  If provided, it's appended to the query string as an 'in:' clause.
        query: Gmail search query string (server-side filter — much more efficient
               than fetching then filtering in Python).
        page_token: Pagination token from a previous call, to fetch the next page.

    Returns:
        Tuple: (list of message dicts with 'id' and 'threadId', next_page_token or None)
    """
    # Backwards compat: if old-style label_id is passed and no custom query was given,
    # fold the label into the query rather than using the deprecated labelIds param.
    effective_query = query
    if label_id and label_id not in ("INBOX", "SENT"):
        # For non-standard labels just append
        effective_query = f"label:{label_id} {query}"

    request_kwargs = {
        "userId": "me",
        "maxResults": min(max_results, 500),
        "q": effective_query,
    }
    if page_token:
        request_kwargs["pageToken"] = page_token

    response = service.users().messages().list(**request_kwargs).execute()

    messages = response.get("messages", [])
    next_page_token = response.get("nextPageToken")

    return messages, next_page_token


def fetch_message_headers(service, message_id):
    """
    Fetch lightweight header-only metadata for a single message (no body download).
    Returns From, To, Cc, Date, Subject — used for cheap pre-filtering before
    deciding to fetch the full message body.

    Args:
        service: Gmail API service
        message_id: Gmail message ID

    Returns:
        dict with keys: id, threadId, internalDate, from_raw, to_raw, cc_raw,
                        subject, date_raw
    """
    msg = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "To", "Cc", "Date", "Subject"],
        )
        .execute()
    )

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    return {
        "id": msg["id"],
        "threadId": msg.get("threadId", msg["id"]),
        "internalDate": int(msg.get("internalDate", 0)),  # ms since epoch
        "from_raw": headers.get("From", ""),
        "to_raw": headers.get("To", ""),
        "cc_raw": headers.get("Cc", ""),
        "subject": headers.get("Subject", ""),
        "date_raw": headers.get("Date", ""),
    }


def fetch_message_metadata(service, message_id):
    """
    Fetch lightweight metadata for a single message (no body).
    Used to get internalDate for date-based sorting before fetching full content.

    Args:
        service: Gmail API service
        message_id: Gmail message ID

    Returns:
        dict with 'id' and 'internalDate' (ms since epoch as string)
    """
    msg = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["Date"],
        )
        .execute()
    )
    return {
        "id": msg["id"],
        "threadId": msg.get("threadId", msg["id"]),
        "internalDate": int(msg.get("internalDate", 0)),  # ms since epoch
    }


def fetch_full_message(service, message_id):

    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    return msg


def get_user_email(service):
    """
    Get the authenticated user's email address.

    Args:
        service: Gmail API service

    Returns:
        str: User's email address
    """
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress")


# ── Phase 1: Live Tool Dispatcher ──────────────────────────────────────────
# Real-time Gmail search invoked when graph data is missing/insufficient.
# Returns lightweight summaries (no full body fetch) so latency stays <2s.

def live_search(org_id: str, query: str, limit: int = 5) -> list:
    """
    Live Gmail search — invoked from /v1/context when graph misses.

    Loads OAuth token from oauth_tokens (no prefix = gmail), runs Gmail's
    server-side `q=` search, fetches metadata + 200-char snippet for each
    hit. NEVER raises — returns [] on any failure so caller can fall through.

    Args:
        org_id: org UUID (string)
        query: Gmail query (e.g. "razorpay invoice", "from:rohit subject:Q2")
        limit: max messages to return (default 5, hard cap 10 for latency)

    Returns:
        list of dicts: {id, thread_id, from, subject, snippet, date, source}
    """
    from sqlalchemy import text as sa_text
    from app.database import SessionLocal

    if not org_id or not query:
        return []
    limit = min(max(1, int(limit)), 10)

    db = SessionLocal()
    try:
        token_row = db.execute(
            sa_text(
                """
                SELECT access_token, refresh_token, account_email
                FROM oauth_tokens
                WHERE org_id = :oid
                  AND (account_email NOT LIKE '%:%' OR account_email IS NULL)
                  AND access_token IS NOT NULL
                LIMIT 1
                """
            ),
            {"oid": org_id},
        ).fetchone()
    finally:
        db.close()

    if not token_row:
        return []

    try:
        service = build_gmail_service(
            token_row.access_token, token_row.refresh_token
        )
        resp = service.users().messages().list(
            userId="me", q=query, maxResults=limit,
        ).execute()
        msg_refs = resp.get("messages", []) or []
    except Exception:
        return []

    results = []
    for ref in msg_refs[:limit]:
        try:
            msg = service.users().messages().get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            ).execute()
            headers = {
                h["name"]: h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }
            results.append({
                "id": msg["id"],
                "thread_id": msg.get("threadId"),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": (msg.get("snippet") or "")[:300],
                "source": "gmail_live",
            })
        except Exception:
            continue
    return results
