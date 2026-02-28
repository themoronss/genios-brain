"""
Tests for R1 — Scope Resolver sub-modules.
Tests workspace resolution, actor resolution, and scope guard.
"""

import pytest

from layers.layer1_retrieval.r1_scope_resolver.workspace_resolver import resolve_workspace
from layers.layer1_retrieval.r1_scope_resolver.actor_resolver import resolve_actor
from layers.layer1_retrieval.r1_scope_resolver.scope_guard import (
    resolve_scope,
    check_permission,
)


# --- Workspace Resolver ---

def test_resolve_valid_workspace():
    ws = resolve_workspace("w1")
    assert ws["workspace_id"] == "w1"
    assert "gmail" in ws["connected_tools"]


def test_resolve_invalid_workspace():
    with pytest.raises(ValueError, match="Unknown workspace"):
        resolve_workspace("nonexistent")


# --- Actor Resolver ---

def test_resolve_valid_actor():
    actor = resolve_actor("u1")
    assert actor["role"] == "founder"
    assert "send_email" in actor["permissions"]


def test_resolve_employee():
    actor = resolve_actor("u2")
    assert actor["role"] == "employee"
    assert "send_email" not in actor["permissions"]


def test_resolve_invalid_actor():
    with pytest.raises(ValueError, match="Unknown actor"):
        resolve_actor("nonexistent")


# --- Scope Guard ---

def test_resolve_scope_success():
    scope = resolve_scope("w1", "u1")
    assert scope.workspace_id == "w1"
    assert scope.actor_id == "u1"
    assert scope.role == "founder"
    assert "send_email" in scope.permissions


def test_resolve_scope_invalid_workspace():
    with pytest.raises(ValueError):
        resolve_scope("bad_ws", "u1")


def test_resolve_scope_invalid_actor():
    with pytest.raises(ValueError):
        resolve_scope("w1", "bad_actor")


def test_check_permission_granted():
    scope = resolve_scope("w1", "u1")
    assert check_permission(scope, "send_email") is True


def test_check_permission_denied():
    scope = resolve_scope("w1", "u2")
    assert check_permission(scope, "send_email") is False
