import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tasks.gmail_sync import run_gmail_sync

run_gmail_sync("87b0235e-e29d-468a-b841-522c13546515")
