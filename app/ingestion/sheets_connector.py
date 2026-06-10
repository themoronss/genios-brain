import re
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

SHEETS_REDIRECT_URI = None  # Lazy-loaded

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# Confidence threshold before writing to Authority Graph (mandatory)
AUTHORITY_GRAPH_CONFIDENCE_THRESHOLD = 0.85

# Quality gate: max rows to index (raw operational logs above this have no org signal)
MAX_INDEXABLE_ROWS = 50000

# Column headers that indicate payroll/salary data — never index without explicit opt-in
SENSITIVE_HEADER_KEYWORDS = {
    "salary", "compensation", "pay rate", "base pay", "bonus", "equity",
    "stock options", "ssn", "social security", "tax id", "payroll",
}


def _get_redirect_uri():
    global SHEETS_REDIRECT_URI
    if SHEETS_REDIRECT_URI is None:
        import os
        SHEETS_REDIRECT_URI = os.getenv("GOOGLE_SHEETS_REDIRECT_URI", "")
    return SHEETS_REDIRECT_URI


def create_sheets_oauth_flow():
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
    flow.redirect_uri = _get_redirect_uri()
    return flow


def build_sheets_service(access_token, refresh_token=None):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    return build("sheets", "v4", credentials=creds)


def build_drive_service(access_token, refresh_token=None):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    return build("drive", "v3", credentials=creds)


def get_sheets_user_email(drive_service):
    """Get authenticated user's email."""
    about = drive_service.about().get(fields="user").execute()
    return about.get("user", {}).get("emailAddress")


def fetch_spreadsheet_metadata(sheets_service, spreadsheet_id):
    """Fetch spreadsheet title and all sheet (tab) metadata."""
    result = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="spreadsheetId,properties.title,sheets.properties",
    ).execute()
    return result


def fetch_tab_sample(sheets_service, spreadsheet_id, tab_name, max_rows=50):
    """
    Fetch the header row + first N rows of a tab for LLM classification.
    Uses display value rendering (never formula values).

    Signal taxonomy:
      - DROP if no header row detected
      - DROP if tab_type == 'unknown' after classification
      - DROP if row_count > MAX_INDEXABLE_ROWS
      - DROP if tab classified as chart or pivot
      - DROP if primarily IMPORTRANGE
      - DROP if payroll/salary keywords in headers
    """
    range_name = f"'{tab_name}'!A1:{chr(ord('A') + 25)}{max_rows + 1}"
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueRenderOption="FORMATTED_VALUE",  # Display values, not formulas
        dateTimeRenderOption="FORMATTED_STRING",
    ).execute()
    return result.get("values", [])


def check_for_importrange(sheets_service, spreadsheet_id, tab_name, max_cols=10):
    """
    Check if a tab is primarily IMPORTRANGE (derived data from another sheet).
    Returns True if tab should be dropped (index source instead).
    """
    range_name = f"'{tab_name}'!A1:{chr(ord('A') + max_cols - 1)}1"
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueRenderOption="FORMULA",
    ).execute()
    values = result.get("values", [[]])[0]
    importrange_count = sum(1 for v in values if str(v).upper().startswith("=IMPORTRANGE"))
    return importrange_count > len(values) * 0.5 if values else False


def classify_tab_type(headers, sample_rows):
    """
    LLM-assisted tab type classifier.
    Returns (tab_type, confidence) where tab_type is one of:
    budget_tracker, crm, approval_matrix, okr, hiring, unknown

    Heuristic pre-classifier (runs before LLM to reduce cost):
    """
    if not headers:
        return "unknown", 0.0

    headers_lower = [h.lower() for h in headers]

    # Detect payroll/salary (immediate skip — too sensitive)
    for header in headers_lower:
        for sensitive in SENSITIVE_HEADER_KEYWORDS:
            if sensitive in header:
                return "sensitive_payroll", 0.95

    # Budget tracker signals
    budget_signals = {"budget", "spend", "allocated", "consumed", "remaining", "department", "q1", "q2", "q3", "q4"}
    if sum(1 for h in headers_lower if any(s in h for s in budget_signals)) >= 2:
        return "budget_tracker", 0.75

    # Approval matrix signals
    approval_signals = {"approver", "approval", "limit", "threshold", "role", "max amount", "authorized"}
    if sum(1 for h in headers_lower if any(s in h for s in approval_signals)) >= 2:
        return "approval_matrix", 0.8

    # OKR signals
    okr_signals = {"metric", "target", "current", "owner", "period", "objective", "key result", "okr", "kpi"}
    if sum(1 for h in headers_lower if any(s in h for s in okr_signals)) >= 2:
        return "okr", 0.75

    # CRM signals
    crm_signals = {"name", "email", "company", "stage", "deal", "contact", "pipeline", "status", "owner"}
    if sum(1 for h in headers_lower if any(s in h for s in crm_signals)) >= 3:
        return "crm", 0.7

    # Hiring signals
    hiring_signals = {"candidate", "role", "stage", "interview", "offer", "rejected", "position", "recruiter"}
    if sum(1 for h in headers_lower if any(s in h for s in hiring_signals)) >= 2:
        return "hiring", 0.7

    return "unknown", 0.0


def normalize_number(raw_value):
    """
    Normalize currency/number strings to float.
    Handles: $180K, $180,000, (180,000), 180K, 1.2M, etc.
    Returns None if not parseable.
    """
    if raw_value is None:
        return None
    s = str(raw_value).strip().replace(",", "").replace("$", "").replace(" ", "")

    # Handle negative (accounting format)
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]

    # Handle K/M/B suffixes
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    if s and s[-1].lower() in multipliers:
        try:
            value = float(s[:-1]) * multipliers[s[-1].lower()]
            return -value if negative else value
        except ValueError:
            return None

    try:
        value = float(s)
        return -value if negative else value
    except ValueError:
        return None


def hash_row(row_values):
    """Generate a deterministic hash of a row for change detection."""
    import hashlib
    import json
    content = json.dumps(row_values, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()[:16]
