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


def fetch_emails(service, max_results=500):
    """
    Fetch emails from Gmail, supporting pagination for large mailboxes.

    Args:
        service: Gmail API service
        max_results: Maximum number of emails to fetch (default: 500)

    Returns:
        List of message IDs
    """
    messages = []
    page_token = None

    while len(messages) < max_results:
        batch_size = min(100, max_results - len(messages))

        request = (
            service.users()
            .messages()
            .list(userId="me", maxResults=batch_size, pageToken=page_token)
        )

        response = request.execute()

        batch_messages = response.get("messages", [])
        messages.extend(batch_messages)

        page_token = response.get("nextPageToken")

        # Stop if no more pages
        if not page_token:
            break

    return messages


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
