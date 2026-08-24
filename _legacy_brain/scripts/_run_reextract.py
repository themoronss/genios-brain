#!/usr/bin/env python3
"""
Direct invocation of run_reextract for Rohit's org.

Runs the same code path that the celery task would, but locally — full
visibility, no celery worker dependency. The 2s sleep between LLM calls
inside the task respects Groq's 30 RPM free-tier limit.

Output is line-buffered so a parallel `tail` works.
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ["PYTHONUNBUFFERED"] = "1"

# Ensure we test the new gated paths if scanner runs adjacent
os.environ.setdefault("GENIOS_CAMPAIGN_DETECTORS_ENABLED", "true")
os.environ.setdefault("GENIOS_RELATED_OUTBOUND_ENABLED", "true")

from app.tasks.reextract import run_reextract

ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"


if __name__ == "__main__":
    print(f"Starting reextract for org {ORG_ID}", flush=True)
    run_reextract(ORG_ID)
    print("Reextract finished.", flush=True)
