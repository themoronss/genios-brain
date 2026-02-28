"""
R0.4 — Budget & TTL Defaults

Hard limits to prevent retrieval from becoming expensive.
"""

# --- Retrieval Budget Defaults ---
MAX_TOOL_CALLS = 4
MAX_MEMORY_ITEMS = 20
MAX_TOKENS = 4000
MAX_PRECEDENTS = 5

# --- TTL Defaults (seconds) ---
DEFAULT_TOOL_TTL_SECONDS = 120   # 2 minutes
GMAIL_TTL_SECONDS = 60           # 1 minute
CALENDAR_TTL_SECONDS = 120       # 2 minutes
CRM_TTL_SECONDS = 300            # 5 minutes

# --- Tool TTL Map ---
TOOL_TTL_MAP = {
    "gmail": GMAIL_TTL_SECONDS,
    "calendar": CALENDAR_TTL_SECONDS,
    "crm": CRM_TTL_SECONDS,
}


def get_ttl_for_tool(tool_name: str) -> int:
    """Return TTL in seconds for a given tool (default if unknown)."""
    return TOOL_TTL_MAP.get(tool_name, DEFAULT_TOOL_TTL_SECONDS)
