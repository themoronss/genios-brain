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
PROCESSING_VERSION = 2
