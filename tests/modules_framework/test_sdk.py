"""Tests for core.modules_framework.sdk — SDK validation rejects engine-in-module + LoRA + bad scopes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.modules_framework.sdk import (
    ModuleValidationError,
    load_manifest,
    validate_module,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _minimal_manifest() -> dict:
    return {
        "id": "test_module",
        "version": "1.0.0",
        "requiredScopes": [],
        "engineVersion": ">=2.0",
        "provides": {
            "rules": [],
            "graphFragment": None,
            "simulationTemplates": [],
            "artifacts": [],
        },
        "goldenSet": "evaluator.py",
    }


def _setup_module(tmp_path: Path, manifest: dict | None = None) -> Path:
    root = tmp_path / "test_module"
    root.mkdir()
    m = manifest or _minimal_manifest()
    _write(root / "manifest.json", json.dumps(m))
    _write(root / "evaluator.py", "def evaluate(**kw): return {'score': 1.0}\n")
    return root


# ── manifest schema ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_missing_manifest_rejected(tmp_path: Path) -> None:
    root = tmp_path / "no_manifest"
    root.mkdir()
    with pytest.raises(ModuleValidationError):
        load_manifest(root)


@pytest.mark.unit
def test_bad_semver_rejected(tmp_path: Path) -> None:
    m = _minimal_manifest()
    m["version"] = "not-semver"
    root = _setup_module(tmp_path, m)
    with pytest.raises(ModuleValidationError):
        load_manifest(root)


@pytest.mark.unit
def test_unknown_top_level_field_rejected(tmp_path: Path) -> None:
    """Pydantic extra='forbid' catches typos at manifest level."""
    m = _minimal_manifest()
    m["unknown_field"] = "oops"
    root = _setup_module(tmp_path, m)
    with pytest.raises(ModuleValidationError):
        load_manifest(root)


# ── engine-in-module rejection ─────────────────────────────────────────────


@pytest.mark.unit
def test_rejects_engine_py_in_module(tmp_path: Path) -> None:
    root = _setup_module(tmp_path)
    _write(root / "engine.py", "# rogue engine code\n")
    result = validate_module(root, valid_scopes=[])
    assert result.ok is False
    assert any("engine" in e.lower() for e in result.errors)


@pytest.mark.unit
def test_rejects_reasoner_py_in_module(tmp_path: Path) -> None:
    root = _setup_module(tmp_path)
    _write(root / "reasoning" / "reasoner.py", "# rogue\n")
    result = validate_module(root, valid_scopes=[])
    assert result.ok is False


# ── LoRA / weights rejection ───────────────────────────────────────────────


@pytest.mark.unit
def test_rejects_lora_weights(tmp_path: Path) -> None:
    root = _setup_module(tmp_path)
    (root / "model.safetensors").write_bytes(b"\x00" * 8)
    result = validate_module(root, valid_scopes=[])
    assert result.ok is False
    assert any("weight" in e.lower() for e in result.errors)


@pytest.mark.unit
def test_rejects_pt_checkpoint(tmp_path: Path) -> None:
    root = _setup_module(tmp_path)
    (root / "checkpoint.pt").write_bytes(b"\x00" * 8)
    result = validate_module(root, valid_scopes=[])
    assert result.ok is False


# ── scope validation ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_unknown_scopes_rejected(tmp_path: Path) -> None:
    m = _minimal_manifest()
    m["requiredScopes"] = ["crm:read", "made_up:scope"]
    root = _setup_module(tmp_path, m)
    result = validate_module(root, valid_scopes=["crm:read"])
    assert result.ok is False
    assert any("unknown scopes" in e.lower() for e in result.errors)


# ── graph fragment must be asserted ────────────────────────────────────────


@pytest.mark.unit
def test_rejects_non_asserted_graph_edges(tmp_path: Path) -> None:
    m = _minimal_manifest()
    m["provides"]["graphFragment"] = "knowledge/graph.json"
    root = _setup_module(tmp_path, m)
    _write(
        root / "knowledge" / "graph.json",
        json.dumps(
            {
                "nodes": [],
                "edges": [{"from": "a", "to": "b", "type": "influence", "status": "candidate"}],
            }
        ),
    )
    result = validate_module(root, valid_scopes=[])
    assert result.ok is False
    assert any("non-asserted" in e.lower() for e in result.errors)


@pytest.mark.unit
def test_accepts_asserted_graph_edges(tmp_path: Path) -> None:
    m = _minimal_manifest()
    m["provides"]["graphFragment"] = "knowledge/graph.json"
    root = _setup_module(tmp_path, m)
    _write(
        root / "knowledge" / "graph.json",
        json.dumps(
            {
                "nodes": [],
                "edges": [{"from": "a", "to": "b", "type": "dependency", "status": "asserted"}],
            }
        ),
    )
    result = validate_module(root, valid_scopes=[])
    assert result.ok is True


# ── golden set required ────────────────────────────────────────────────────


@pytest.mark.unit
def test_missing_golden_set_rejected(tmp_path: Path) -> None:
    m = _minimal_manifest()
    m["goldenSet"] = "no_such_evaluator.py"
    root = _setup_module(tmp_path, m)
    # don't write the evaluator file
    (root / "evaluator.py").unlink()
    result = validate_module(root, valid_scopes=[])
    assert result.ok is False
    assert any("goldenset" in e.lower() or "evaluator" in e.lower() for e in result.errors)


# ── happy path ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_minimal_valid_module_passes(tmp_path: Path) -> None:
    root = _setup_module(tmp_path)
    result = validate_module(root, valid_scopes=[])
    assert result.ok is True
    assert result.errors == []
