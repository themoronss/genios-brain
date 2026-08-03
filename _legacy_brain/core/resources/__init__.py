"""Resources tab — manual context entries + file uploads, v2-native.

All ingest funnels through the same emit() bus the OAuth adapters use.
This module is the dashboard-facing thin wrapper that:
  - persists the UI-only metadata (so cards render without a fact query)
  - emits a MemoryItem the worldmodel ingest subscriber picks up
  - exposes read/list helpers org-scoped + per-agent policy aware
"""

from core.resources.manual import (
    ManualEntryInput,
    create_manual_entry,
    delete_manual_entry,
    list_manual_entries,
    update_manual_entry,
)
from core.resources.uploads import (
    UploadInput,
    create_upload,
    delete_upload,
    list_uploads,
    retag_upload,
)

__all__ = [
    "ManualEntryInput",
    "create_manual_entry",
    "delete_manual_entry",
    "list_manual_entries",
    "update_manual_entry",
    "UploadInput",
    "create_upload",
    "delete_upload",
    "list_uploads",
    "retag_upload",
]
