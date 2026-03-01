"""
Google Auth Helper

Manages OAuth2 credentials for Gmail and Calendar API access.
Stores tokens in credentials/token.json after first-time authorization.
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Read-only scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# Paths
_PROJECT_ROOT = Path(__file__).parent.parent.parent
CREDENTIALS_DIR = _PROJECT_ROOT / "credentials"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "client_secret.json"


def get_google_credentials() -> Credentials:
    """
    Get valid Google OAuth2 credentials.

    On first run:
        Opens browser for OAuth consent flow.
        Saves token to credentials/token.json.

    On subsequent runs:
        Loads and refreshes saved token.

    Returns:
        Authenticated Credentials object.

    Raises:
        FileNotFoundError: If client_secret.json is missing.
    """
    creds = None

    # Load existing token
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or re-authorize
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"Missing {CLIENT_SECRET_PATH}.\n"
                    "Download OAuth2 client credentials from Google Cloud Console:\n"
                    "  1. Go to https://console.cloud.google.com/apis/credentials\n"
                    "  2. Create OAuth 2.0 Client ID (Desktop app)\n"
                    "  3. Download JSON and save as credentials/client_secret.json"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save for next run
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds
