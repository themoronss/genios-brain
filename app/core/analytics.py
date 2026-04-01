import os
import logging
import posthog as _posthog

logger = logging.getLogger(__name__)

_posthog.project_api_key = os.getenv("POSTHOG_API_KEY", "")
_posthog.host = "https://eu.i.posthog.com"


def capture(org_id: str, event: str, properties: dict = None):
    """Fire a PostHog event. Non-blocking — never raises."""
    try:
        if _posthog.project_api_key:
            _posthog.capture(org_id, event, properties or {})
    except Exception as e:
        logger.debug(f"Analytics capture failed (non-critical): {e}")
