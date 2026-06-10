"""Shared pytest fixtures."""

from __future__ import annotations

import os

# Ensure tests don't accidentally hit production .env
os.environ.setdefault("GENIOS_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
# Test-only Fernet key (deterministic, generated via Fernet.generate_key()).
# NEVER use in production — committed to repo so all dev/CI runs reproduce.
os.environ.setdefault(
    "GENIOS_CRYPTO_MASTER_KEY",
    "r3EvaCrC0M31LVH4xDnfbJTxpgPEacVPJ7PM-7qFop8=",
)
