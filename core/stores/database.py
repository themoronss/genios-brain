import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def get_supabase_client() -> Client:
    """
    Create and return a Supabase client.
    Requires SUPABASE_URL and SUPABASE_KEY in environment / .env file.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set. "
            "Copy .env.example to .env and fill in your Supabase credentials."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)
