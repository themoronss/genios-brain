import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/gmail/callback")
GOOGLE_CALENDAR_REDIRECT_URI = os.getenv("GOOGLE_CALENDAR_REDIRECT_URI", "http://localhost:8000/auth/calendar/callback")
GOOGLE_DRIVE_REDIRECT_URI = os.getenv("GOOGLE_DRIVE_REDIRECT_URI", "http://localhost:8000/auth/drive/callback")
GOOGLE_SHEETS_REDIRECT_URI = os.getenv("GOOGLE_SHEETS_REDIRECT_URI", "http://localhost:8000/auth/gsheets/callback")
GOOGLE_DOCS_REDIRECT_URI = os.getenv("GOOGLE_DOCS_REDIRECT_URI", "http://localhost:8000/auth/gdocs/callback")

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI", "http://localhost:8000/auth/slack/callback")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

JIRA_CLIENT_ID = os.getenv("JIRA_CLIENT_ID")
JIRA_CLIENT_SECRET = os.getenv("JIRA_CLIENT_SECRET")
JIRA_REDIRECT_URI = os.getenv("JIRA_REDIRECT_URI", "http://localhost:8000/auth/jira/callback")

NOTION_CLIENT_ID = os.getenv("NOTION_CLIENT_ID")
NOTION_CLIENT_SECRET = os.getenv("NOTION_CLIENT_SECRET")
NOTION_REDIRECT_URI = os.getenv("NOTION_REDIRECT_URI", "http://localhost:8000/auth/notion/callback")

HUBSPOT_CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
HUBSPOT_CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
HUBSPOT_REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI", "http://localhost:8000/auth/hubspot/callback")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Sync config — controls both normal (manual) and cron sync batch sizes
SYNC_MAX_EMAILS = int(os.getenv("SYNC_MAX_EMAILS", 15))
SYNC_MAX_EMAILS_CRON = int(os.getenv("SYNC_MAX_EMAILS_CRON", 100))
SYNC_MAX_CALENDAR_EVENTS = int(os.getenv("SYNC_MAX_CALENDAR_EVENTS", 250))
SYNC_MAX_CALENDAR_EVENTS_CRON = int(os.getenv("SYNC_MAX_CALENDAR_EVENTS_CRON", 250))
SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", 24))

# Bump this when extraction logic changes to trigger re-extraction of old interactions
PROCESSING_VERSION = 3

# ── Phase 1 — LLM foundation, Pull API deadline, webhook retry ──
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_HAIKU_MODEL = os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_SONNET_MODEL = os.getenv("ANTHROPIC_SONNET_MODEL", "claude-sonnet-4-6")
GENIOS_ANTHROPIC_ENABLED = os.getenv("GENIOS_ANTHROPIC_ENABLED", "false").lower() == "true"

GENIOS_LLM_DAILY_CAP_USD = float(os.getenv("GENIOS_LLM_DAILY_CAP_USD", "50.0"))
GENIOS_PULL_DEADLINE_MS = int(os.getenv("GENIOS_PULL_DEADLINE_MS", "400"))
GENIOS_WEBHOOK_RETRY_SCHEDULE = [
    int(s) for s in os.getenv(
        "GENIOS_WEBHOOK_RETRY_SCHEDULE", "30,120,600,3600,21600,86400"
    ).split(",") if s.strip()
]

# ── Phase 2 — reasoning loop (event bus, detectors, reasoner, gate) ──
GENIOS_REASONER_ENABLED = os.getenv("GENIOS_REASONER_ENABLED", "false").lower() == "true"
GENIOS_BATCH_WINDOW_SECONDS = int(os.getenv("GENIOS_BATCH_WINDOW_SECONDS", "30"))
GENIOS_MIN_PUSH_PRIORITY = float(os.getenv("GENIOS_MIN_PUSH_PRIORITY", "0.60"))
GENIOS_MIN_PUSH_CONFIDENCE = float(os.getenv("GENIOS_MIN_PUSH_CONFIDENCE", "0.50"))
GENIOS_WEBHOOK_DAILY_BUDGET = int(os.getenv("GENIOS_WEBHOOK_DAILY_BUDGET", "300"))
GENIOS_EVENT_STREAM = os.getenv("GENIOS_EVENT_STREAM", "genios:events:fact")
GENIOS_EVENT_GROUP = os.getenv("GENIOS_EVENT_GROUP", "brain_router")
GENIOS_EVENT_MAXLEN = int(os.getenv("GENIOS_EVENT_MAXLEN", "100000"))

# ── Phase 3 — learning loop (recommendations, cascade, narrative) ──
GENIOS_CASCADE_ENABLED = os.getenv("GENIOS_CASCADE_ENABLED", "false").lower() == "true"

# ── Phase 4 — correctness (calibration; observability deferred per deviations R) ──
GENIOS_CALIBRATION_ENABLED = os.getenv("GENIOS_CALIBRATION_ENABLED", "false").lower() == "true"
