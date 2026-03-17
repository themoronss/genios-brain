import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/gmail/callback")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SYNC_MAX_EMAILS = int(os.getenv("SYNC_MAX_EMAILS", 10))  # Default 10 for testing to avoid Groq rate limits
