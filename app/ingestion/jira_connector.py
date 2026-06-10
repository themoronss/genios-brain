import requests
import secrets
import hashlib
import base64

# Atlassian OAuth 3LO endpoints
ATLASSIAN_AUTH_URL = "https://auth.atlassian.com/authorize"
ATLASSIAN_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ATLASSIAN_API_BASE = "https://api.atlassian.com"

SCOPES = [
    "read:jira-work",
    "read:jira-user",
    "read:sprint:jira-software",
    "offline_access",  # Required for refresh tokens
]


def get_jira_authorize_url(state, redirect_uri, client_id):
    """
    Build Atlassian OAuth 3LO authorization URL with PKCE.
    Returns (url, code_verifier) — store code_verifier in Redis with state.
    """
    code_verifier = secrets.token_urlsafe(96)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    scope = " ".join(SCOPES)
    url = (
        f"{ATLASSIAN_AUTH_URL}"
        f"?audience=api.atlassian.com"
        f"&client_id={client_id}"
        f"&scope={scope}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
        f"&response_type=code"
        f"&prompt=consent"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    return url, code_verifier


def exchange_code_for_tokens(code, code_verifier, redirect_uri, client_id, client_secret):
    """Exchange authorization code for access + refresh tokens."""
    response = requests.post(
        ATLASSIAN_TOKEN_URL,
        json={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )
    data = response.json()
    if "access_token" not in data:
        raise ValueError(f"Jira token exchange failed: {data}")
    return data


def refresh_access_token(refresh_token, client_id, client_secret):
    """Refresh an expired access token."""
    response = requests.post(
        ATLASSIAN_TOKEN_URL,
        json={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
    )
    data = response.json()
    if "access_token" not in data:
        raise ValueError(f"Jira token refresh failed: {data}")
    return data


def get_accessible_resources(access_token):
    """
    Get list of Atlassian cloud sites the user has access to.
    Returns list of {id, name, url, scopes, avatarUrl}.
    """
    response = requests.get(
        f"{ATLASSIAN_API_BASE}/oauth/token/accessible-resources",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def fetch_projects(cloud_id, access_token):
    """Fetch all projects in a Jira cloud instance."""
    url = f"{ATLASSIAN_API_BASE}/ex/jira/{cloud_id}/rest/api/3/project/search"
    projects = []
    start_at = 0

    while True:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            params={"startAt": start_at, "maxResults": 50, "expand": "issueTypes,lead"},
        )
        response.raise_for_status()
        data = response.json()
        projects.extend(data.get("values", []))
        if data.get("isLast", True):
            break
        start_at += len(data.get("values", []))

    return projects


def fetch_project_statuses(cloud_id, project_key, access_token):
    """
    Fetch all statuses for a project, building terminal_statuses and active_statuses maps.
    CRITICAL: Never hardcode "Done" as terminal — use this per-project status map.

    Returns:
        {
            "terminal_statuses": ["Done", "Closed", "Resolved", ...],
            "active_statuses": ["To Do", "In Progress", "In Review", ...]
        }
    """
    url = f"{ATLASSIAN_API_BASE}/ex/jira/{cloud_id}/rest/api/3/project/{project_key}/statuses"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    response.raise_for_status()
    data = response.json()

    terminal_statuses = []
    active_statuses = []

    for issue_type in data:
        for status in issue_type.get("statuses", []):
            category = status.get("statusCategory", {}).get("key", "")
            name = status.get("name", "")
            if category == "done":
                if name not in terminal_statuses:
                    terminal_statuses.append(name)
            else:
                if name not in active_statuses:
                    active_statuses.append(name)

    return {"terminal_statuses": terminal_statuses, "active_statuses": active_statuses}


def search_issues_jql(cloud_id, access_token, jql, start_at=0, max_results=100):
    """
    Search Jira issues using JQL query.
    Used for backfill (window-based, 3 months at a time).

    Returns (issues, total, is_last_page)
    """
    url = f"{ATLASSIAN_API_BASE}/ex/jira/{cloud_id}/rest/api/3/search"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json",
                 "Content-Type": "application/json"},
        json={
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": [
                "summary", "status", "assignee", "reporter", "priority",
                "duedate", "created", "updated", "issuetype", "labels",
                "customfield_10016",  # story points (common field name)
                "customfield_10020",  # sprint field
                "parent", "subtasks", "issuelinks",
            ],
        },
    )
    response.raise_for_status()
    data = response.json()
    issues = data.get("issues", [])
    total = data.get("total", 0)
    is_last = start_at + len(issues) >= total
    return issues, total, is_last


def register_webhook(cloud_id, access_token, webhook_url):
    """
    Register a Jira webhook for issue events.
    IMPORTANT: Webhooks expire after 30 days — must renew at 25 days.

    Returns webhook registration dict including webhookId.
    """
    url = f"{ATLASSIAN_API_BASE}/ex/jira/{cloud_id}/rest/webhooks/1.0/webhook"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json",
                 "Content-Type": "application/json"},
        json={
            "name": "GeniOS Brain Webhook",
            "url": webhook_url,
            "events": [
                "jira:issue_created",
                "jira:issue_updated",
                "jira:issue_deleted",
            ],
            "filters": {},
            "excludeBody": False,
        },
    )
    response.raise_for_status()
    return response.json()


# ─── Changelog field filter ──────────────────────────────────────────────────
PROCESS_CHANGELOG_FIELDS = {"status", "assignee", "priority", "duedate", "summary", "labels", "Sprint"}


def filter_changelog_items(items):
    """
    First-pass changelog filter. Drop anything that isn't a meaningful state change.
    CRITICAL: If this returns empty list, the entire event must be dropped.

    Signal taxonomy drop rules:
      - Only process: status, assignee, priority, duedate, summary, labels, Sprint
      - Drop: description edits, comment body edits
      - Drop: watch/unwatch events
      - Drop: attachment uploads
      - Drop: subtask micro-events
      - Drop: sprint board reordering (rank changes)
    """
    filtered = []
    for item in items:
        field = item.get("field", "").lower()
        if field in PROCESS_CHANGELOG_FIELDS or item.get("fieldId") in PROCESS_CHANGELOG_FIELDS:
            filtered.append(item)
    return filtered


def is_bot_transition(changelog_author):
    """
    Detect Atlassian automation bot transitions — drop these entirely.
    Returns True if this is a bot (should be dropped).
    """
    if not changelog_author:
        return False
    account_type = changelog_author.get("accountType", "")
    display_name = changelog_author.get("displayName", "").lower()
    if account_type == "atlassian" and (
        "automation" in display_name
        or "bot" in display_name
        or "jira-software-robot" in display_name
    ):
        return True
    return False
