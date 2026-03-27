import uuid
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

DRIVE_REDIRECT_URI = None  # Lazy-loaded

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.activity.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# Max folder nesting depth to index (deeper folders have diminishing signal)
MAX_FOLDER_DEPTH = 3

# mimeType routing: where each file type should go
MIME_ROUTING = {
    "application/vnd.google-apps.document": "docs_pipeline",
    "application/vnd.google-apps.spreadsheet": "sheets_pipeline",
    "application/vnd.google-apps.presentation": "slides_title_only",
    "application/vnd.google-apps.folder": "folder_structure",
    "application/pdf": "metadata_only",
    "application/vnd.google-apps.form": "drop",  # auto-generated responses
    "application/vnd.google-apps.shortcut": "resolve_target",
}


def _get_redirect_uri():
    global DRIVE_REDIRECT_URI
    if DRIVE_REDIRECT_URI is None:
        from app.config import GOOGLE_DRIVE_REDIRECT_URI
        DRIVE_REDIRECT_URI = GOOGLE_DRIVE_REDIRECT_URI
    return DRIVE_REDIRECT_URI


def create_drive_oauth_flow():
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


def build_drive_service(access_token, refresh_token=None):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    return build("drive", "v3", credentials=creds)


def build_activity_service(access_token, refresh_token=None):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    return build("driveactivity", "v2", credentials=creds)


def get_drive_user_email(drive_service):
    about = drive_service.about().get(fields="user").execute()
    return about.get("user", {}).get("emailAddress")


def get_start_page_token(drive_service):
    """
    Get the initial page token for the Changes API.
    CRITICAL: Store this in gdrive_connections.changes_page_token immediately.
    The token must never go 30 days without a call to fetch_changes().
    """
    result = drive_service.changes().getStartPageToken().execute()
    return result.get("startPageToken")


def fetch_changes(drive_service, page_token, page_size=100):
    """
    Fetch Drive changes since page_token using two-phase processing:
      Phase 1: Receive changes + write to gdrive_change_log as 'pending' (DO NOT advance token yet)
      Phase 2: Process each change log entry → advance token ONLY after full batch processed

    NEVER call this and advance the token in the same step.
    Callers must:
      1. Write all changes to gdrive_change_log with status='pending'
      2. Process each change
      3. Update page_token in gdrive_connections ONLY after full batch

    Returns (changes, new_page_token, has_more)

    Signal taxonomy:
      - DROP trashed: true files
      - DROP shortcut files (resolve to target)
      - DROP system/automated files (Google Forms responses, auto-backups)
      - DROP binary file body content (PDFs, images, videos — metadata + permissions only)
      - DROP internal-only activity with no external signal
      - Route by mimeType using MIME_ROUTING map
    """
    result = drive_service.changes().list(
        pageToken=page_token,
        pageSize=min(page_size, 100),
        includeRemoved=True,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields=(
            "nextPageToken,newStartPageToken,"
            "changes(changeType,removed,fileId,"
            "file(id,name,mimeType,trashed,parents,owners,driveId,"
            "modifiedTime,createdTime,sharingUser,shared,viewedByMe))"
        ),
    ).execute()

    changes = result.get("changes", [])
    new_page_token = result.get("newStartPageToken") or result.get("nextPageToken", page_token)
    has_more = "nextPageToken" in result
    return changes, new_page_token, has_more


def classify_file_change(change):
    """
    First-pass signal filter for a Drive change event.
    Returns (action, mime_route) or None if should be dropped.

    Signal taxonomy drop rules:
      - DROP trashed: true files
      - DROP shortcut files (type==shortcut — resolve to target instead)
      - DROP Google Forms files (auto-generated)
      - DROP deeply nested files (folder_depth > 3)
      - DROP binary files for content extraction
      - DROP revision history body content
    """
    if change.get("removed"):
        return "removed", None

    file = change.get("file", {})
    if not file:
        return None, None

    # DROP trashed
    if file.get("trashed"):
        return None, None

    mime_type = file.get("mimeType", "")

    # DROP Google Forms
    if mime_type == "application/vnd.google-apps.form":
        return None, None

    route = MIME_ROUTING.get(mime_type, "metadata_only")

    # Shortcut: resolve to target, don't index shortcut itself
    if route == "resolve_target":
        return None, None  # Caller should resolve target file_id

    return "upsert", route


def fetch_shared_drives(drive_service):
    """List all Shared Drives the user has access to."""
    drives = []
    page_token = None

    while True:
        result = drive_service.drives().list(
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken,drives(id,name,createdTime)",
        ).execute()

        drives.extend(result.get("drives", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return drives


def fetch_shared_drive_members(drive_service, drive_id):
    """Fetch all members of a Shared Drive."""
    result = drive_service.permissions().list(
        fileId=drive_id,
        supportsAllDrives=True,
        useDomainAdminAccess=False,
        fields="permissions(id,emailAddress,role,type,displayName)",
    ).execute()
    return result.get("permissions", [])


def fetch_file_permissions(drive_service, file_id):
    """
    Fetch permissions for a file.
    Note: Never batch-fetch permissions for large file sets in one call.
    This is called per-file only when change log indicates a permission change.
    """
    result = drive_service.permissions().list(
        fileId=file_id,
        supportsAllDrives=True,
        fields="permissions(id,emailAddress,role,type,expirationTime,allowFileDiscovery,displayName)",
    ).execute()
    return result.get("permissions", [])


def setup_drive_watch_channel(drive_service, webhook_url):
    """
    Set up push notifications for Drive changes.
    CRITICAL: Renew at 6.5 days (NOT 7).

    Returns channel dict with id, resourceId, expiration.
    """
    from datetime import datetime, timedelta, timezone

    expiry_ms = int(
        (datetime.now(timezone.utc) + timedelta(days=6, hours=12)).timestamp() * 1000
    )
    channel_id = str(uuid.uuid4())
    start_token = get_start_page_token(drive_service)

    body = {
        "id": channel_id,
        "type": "web_hook",
        "address": webhook_url,
        "expiration": expiry_ms,
    }
    result = drive_service.changes().watch(
        pageToken=start_token,
        body=body,
        supportsAllDrives=True,
    ).execute()
    return result


def fetch_folder_structure(drive_service, max_depth=MAX_FOLDER_DEPTH):
    """
    Fetch top-level folder structure up to max_depth levels.
    Returns flat list of folder dicts for gdrive_folder_structure table.

    Signal taxonomy: only index top 3 levels — deeper folders have diminishing signal.
    """
    folders = []
    queue = [("root", None, 0)]
    seen = set()

    while queue:
        parent_id, parent_folder_id, depth = queue.pop(0)
        if depth > max_depth:
            continue

        result = drive_service.files().list(
            q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            pageSize=50,
            fields="files(id,name,owners,createdTime,modifiedTime)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        for folder in result.get("files", []):
            if folder["id"] in seen:
                continue
            seen.add(folder["id"])
            folders.append({
                "folder_id": folder["id"],
                "folder_name": folder.get("name"),
                "parent_folder_id": parent_folder_id,
                "folder_level": depth,
                "owner_email": folder.get("owners", [{}])[0].get("emailAddress"),
            })
            if depth < max_depth:
                queue.append((folder["id"], folder["id"], depth + 1))

    return folders
