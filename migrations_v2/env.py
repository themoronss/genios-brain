"""Alembic environment — sync, reads DATABASE_URL from core.foundations.config.settings.

Important: ConfigParser (alembic.ini) does %-interpolation, so a raw URL
containing `%` (e.g. URL-encoded `@` as `%40` in a Supabase password) raises
on set_main_option. We bypass interpolation by NOT going through the .ini —
the URL is fed straight to create_engine().
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from core.foundations.config import settings
from core.foundations.db import Base

config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata — Base is the single declarative base in core/foundations/db.py
target_metadata = Base.metadata

# DATABASE_URL may contain URL-encoded special chars (% in passwords). Escape
# for the offline path (which still goes through ConfigParser via context.url).
_RUNTIME_URL = settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in offline mode (emits SQL to stdout)."""
    context.configure(
        url=_RUNTIME_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB.

    create_engine() is called directly with the runtime URL so we never push
    the URL through ConfigParser interpolation (which chokes on `%`).
    """
    connectable = create_engine(_RUNTIME_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
