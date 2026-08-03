"""Unit tests for core.memory.secrets — encrypt/decrypt round-trip via in-memory SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.memory.secrets import delete_secret, get_secret, put_secret, rotate_secret
from core.memory.store import Connection


@pytest.fixture
def session() -> Session:
    """In-memory SQLite for fast unit isolation."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


@pytest.fixture
def connection_row(session: Session) -> Connection:
    conn = Connection(
        org_id="org_test",
        source_type="gmail",
        source_id="bob@acme.com",
        created_by="user_test",
    )
    session.add(conn)
    session.commit()
    return conn


@pytest.mark.unit
def test_put_and_get_round_trip(session: Session, connection_row: Connection) -> None:
    """Stored encrypted; retrieved decrypts to original."""
    ref_id = put_secret(
        session,
        org_id="org_test",
        connection_id=connection_row.id,
        secret_type="oauth_refresh",
        plaintext="ya29.real-token-value",
    )
    session.commit()

    decrypted = get_secret(session, ref_id)
    assert decrypted == "ya29.real-token-value"


@pytest.mark.unit
def test_stored_value_is_encrypted(session: Session, connection_row: Connection) -> None:
    """Direct DB inspection shows ciphertext, NOT plaintext."""
    from core.memory.store import SecretRef

    ref_id = put_secret(
        session,
        org_id="org_test",
        connection_id=connection_row.id,
        secret_type="api_key",
        plaintext="sk-secret-key",
    )
    session.commit()

    row = session.get(SecretRef, ref_id)
    assert row is not None
    assert "sk-secret-key" not in row.encrypted_value  # NEVER plaintext at rest


@pytest.mark.unit
def test_rotate_replaces_value(session: Session, connection_row: Connection) -> None:
    """Rotation re-encrypts new value; old plaintext gone."""
    ref_id = put_secret(
        session,
        org_id="org_test",
        connection_id=connection_row.id,
        secret_type="oauth_refresh",
        plaintext="old",
    )
    session.commit()

    rotate_secret(session, ref_id, "new")
    session.commit()

    assert get_secret(session, ref_id) == "new"


@pytest.mark.unit
def test_delete_removes_secret(session: Session, connection_row: Connection) -> None:
    """Delete removes the row entirely (on disconnect/revoke)."""
    ref_id = put_secret(
        session,
        org_id="org_test",
        connection_id=connection_row.id,
        secret_type="oauth_access",
        plaintext="token",
    )
    session.commit()

    delete_secret(session, ref_id)
    session.commit()

    with pytest.raises(KeyError):
        get_secret(session, ref_id)


@pytest.mark.unit
def test_get_missing_raises(session: Session) -> None:
    """Unknown secret_ref id -> clean error."""
    with pytest.raises(KeyError):
        get_secret(session, "does-not-exist")
