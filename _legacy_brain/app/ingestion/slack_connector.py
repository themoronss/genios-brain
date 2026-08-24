import hmac
import hashlib
import time
import requests

from app.config import SLACK_CLIENT_ID, SLACK_CLIENT_SECRET, SLACK_REDIRECT_URI

SLACK_OAUTH_URL = "https://slack.com/api/oauth.v2.access"
SLACK_API_BASE = "https://slack.com/api"

# Scopes required for the bot token
BOT_SCOPES = [
    "channels:read",
    "channels:history",
    "users:read",
    "users:read.email",
    "im:history",
    "groups:read",
    "groups:history",
]


def get_slack_authorize_url(state):
    """
    Build the Slack OAuth authorization URL.
    Returns the URL to redirect the user to.
    """
    scope = ",".join(BOT_SCOPES)
    return (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={SLACK_CLIENT_ID}"
        f"&scope={scope}"
        f"&redirect_uri={SLACK_REDIRECT_URI}"
        f"&state={state}"
    )


def exchange_code_for_tokens(code):
    """
    Exchange OAuth authorization code for bot + user tokens.
    Returns the full Slack oauth.v2.access response dict.
    """
    response = requests.post(
        SLACK_OAUTH_URL,
        data={
            "code": code,
            "client_id": SLACK_CLIENT_ID,
            "client_secret": SLACK_CLIENT_SECRET,
            "redirect_uri": SLACK_REDIRECT_URI,
        },
    )
    data = response.json()
    if not data.get("ok"):
        raise ValueError(f"Slack OAuth failed: {data.get('error', 'unknown_error')}")
    return data


def fetch_channels(bot_token, types="public_channel"):
    """
    List all channels in the workspace for the channel selector UI.
    Returns list of channel dicts: {id, name, is_private, is_ext_shared, num_members}.

    Signal taxonomy note: channels starting with 'ext-' are Slack Connect (external).
    """
    channels = []
    cursor = None

    while True:
        params = {
            "token": bot_token,
            "types": types,
            "limit": 200,
            "exclude_archived": True,
        }
        if cursor:
            params["cursor"] = cursor

        response = requests.get(f"{SLACK_API_BASE}/conversations.list", params=params)
        data = response.json()

        if not data.get("ok"):
            raise ValueError(f"Slack channels list failed: {data.get('error')}")

        channels.extend(data.get("channels", []))
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return channels


def fetch_channel_history(bot_token, channel_id, oldest=None, latest=None, cursor=None, limit=200):
    """
    Fetch message history for a channel.
    Returns (messages, next_cursor).

    Signal taxonomy — callers must apply quality gates:
      - DROP subtype: "bot_message" or bot_id set
      - DROP len(text) < 15 or reaction-only messages
      - DROP deleted messages
      - DROP message_changed, channel_archive, file_shared events
    """
    params = {
        "token": bot_token,
        "channel": channel_id,
        "limit": min(limit, 200),
    }
    if oldest:
        params["oldest"] = oldest
    if latest:
        params["latest"] = latest
    if cursor:
        params["cursor"] = cursor

    response = requests.get(f"{SLACK_API_BASE}/conversations.history", params=params)
    data = response.json()

    if not data.get("ok"):
        raise ValueError(f"Slack history fetch failed: {data.get('error')}")

    messages = data.get("messages", [])
    next_cursor = data.get("response_metadata", {}).get("next_cursor")
    return messages, next_cursor


def fetch_user_info(bot_token, slack_user_id):
    """Fetch user profile including email for entity resolution."""
    response = requests.get(
        f"{SLACK_API_BASE}/users.info",
        params={"token": bot_token, "user": slack_user_id},
    )
    data = response.json()
    if not data.get("ok"):
        return None
    return data.get("user")


def validate_event_signature(body_bytes, timestamp_header, signature_header, signing_secret):
    """
    Validate Slack request signature to prevent spoofed webhook calls.
    MUST be called before processing any incoming event.

    Args:
        body_bytes: Raw request body as bytes
        timestamp_header: X-Slack-Request-Timestamp header value
        signature_header: X-Slack-Signature header value
        signing_secret: Slack signing secret from app config

    Returns:
        bool: True if valid, False if invalid or replay attack (>5min old)
    """
    # Reject replays older than 5 minutes
    if abs(time.time() - int(timestamp_header)) > 300:
        return False

    sig_basestring = f"v0:{timestamp_header}:{body_bytes.decode('utf-8')}"
    computed = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, signature_header)


def classify_message(message, channel_name=None, org_domain=None):
    """
    Three-tier quality gate for Slack messages.
    Returns (tier, reason) where tier is 1=full extract, 2=keyword-gated, 3=drop.

    Tier 1: DM with external guest — full extract, full NLP
    Tier 2: Channel on allow-list — keyword-gated (commitment/entity keywords only)
    Tier 3: #random/#general/bot/internal-only — DROP
    """
    # DROP: bot messages
    if message.get("subtype") == "bot_message" or message.get("bot_id"):
        return 3, "bot_message"

    # DROP: deleted messages
    if message.get("subtype") == "message_deleted":
        return 3, "deleted"

    # DROP: non-message subtypes
    drop_subtypes = {"channel_archive", "channel_unarchive", "file_shared", "message_changed"}
    if message.get("subtype") in drop_subtypes:
        return 3, "non_message_subtype"

    text = message.get("text", "")

    # DROP: too short (reaction-only, "ok", "sure", "lol", single emoji)
    cleaned = text.strip()
    if len(cleaned) < 15:
        return 3, "too_short"

    # DROP: water cooler channel names
    if channel_name:
        drop_channels = {"random", "general", "watercooler", "fun", "memes", "off-topic"}
        if any(channel_name.lower().startswith(d) or channel_name.lower() == d for d in drop_channels):
            return 3, "water_cooler_channel"

    # Tier 1: external DM (channel_name starts with "D" = DM)
    if channel_name and channel_name.startswith("D"):
        return 1, "external_dm"

    # Tier 2: everything else that passed drop gates
    return 2, "channel_message"
