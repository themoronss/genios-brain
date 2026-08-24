"""Git-backed Expert Brain authoring catalog.

This is a build/compiler input, never a mutable runtime brain.  YAML is parsed with SafeLoader,
floats are promoted to Decimal before they can enter a semantic hash, every authored identity is
unique, and generated registries are treated as indexes rather than as a second source of truth.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from genios_engine.contracts.validators import freeze_mapping
from genios_engine.platform.canonical import semantic_hash

from .errors import AuthoringIntegrityError
from .models import DomainRecord, SourceDocument


class _DecimalSafeLoader(yaml.SafeLoader):
    pass


def _decimal(loader: yaml.SafeLoader, node: yaml.Node) -> Decimal:
    raw = loader.construct_scalar(node).replace("_", "")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise yaml.constructor.ConstructorError(None, None, "invalid finite decimal", node.start_mark) \
            from exc
    if not value.is_finite():
        raise yaml.constructor.ConstructorError(None, None, "non-finite decimal", node.start_mark)
    return value


_DecimalSafeLoader.add_constructor("tag:yaml.org,2002:float", _decimal)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(), Loader=_DecimalSafeLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise AuthoringIntegrityError(f"cannot load Expert Brain source {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuthoringIntegrityError(f"Expert Brain source must be a mapping: {path}")
    return value


def _identity(data: dict[str, Any], path: Path) -> tuple[str, str]:
    identity = data.get("identity")
    if not isinstance(identity, dict):
        raise AuthoringIntegrityError(f"identity is required: {path}")
    identifier = str(identity.get("id") or "").strip()
    version = str(identity.get("version") or "").strip()
    if not identifier or not version:
        raise AuthoringIntegrityError(f"identity.id and identity.version are required: {path}")
    return identifier, version


def _source(*, kind: str, path: Path, root: Path, domain_id: str,
            data: dict[str, Any], identifier: str | None = None,
            version: str | None = None) -> SourceDocument:
    if identifier is None or version is None:
        found_id, found_version = _identity(data, path)
        identifier = identifier or found_id
        version = version or found_version
    return SourceDocument(
        kind=kind,
        id=identifier,
        domain_id=domain_id,
        version=version,
        relative_path=path.relative_to(root).as_posix(),
        content=data,
        content_hash=semantic_hash(data),
    )


def _insert(target: dict[str, SourceDocument], document: SourceDocument) -> None:
    previous = target.get(document.id)
    if previous is not None:
        raise AuthoringIntegrityError(
            f"duplicate Expert Brain id {document.id!r}: "
            f"{previous.relative_path} and {document.relative_path}")
    target[document.id] = document


class ExpertBrainCatalog:
    """Immutable in-process index over the human-authored three-domain corpus."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise AuthoringIntegrityError(f"Expert Brain root does not exist: {self.root}")
        records: dict[str, DomainRecord] = {}
        for domain_root in sorted(self.root.iterdir()):
            if (not domain_root.is_dir() or domain_root.name.startswith("_")
                    or not (domain_root / "domain.yaml").is_file()):
                continue
            record = self._load_domain(domain_root.resolve())
            domain_id = record.domain.id
            if domain_id in records:
                raise AuthoringIntegrityError(f"duplicate domain id {domain_id!r}")
            records[domain_id] = record
        if not records:
            raise AuthoringIntegrityError(f"no authored domains found under {self.root}")
        self.domains = MappingProxyType(records)

    def _load_domain(self, domain_root: Path) -> DomainRecord:
        if self.root not in domain_root.parents:
            raise AuthoringIntegrityError(f"domain escapes Expert Brain root: {domain_root}")
        if domain_root.is_symlink():
            raise AuthoringIntegrityError(f"symlinked domain roots are not allowed: {domain_root}")

        domain_path = domain_root / "domain.yaml"
        domain_data = _load_yaml(domain_path)
        domain_id, _ = _identity(domain_data, domain_path)
        domain_doc = _source(kind="domain", path=domain_path, root=self.root,
                             domain_id=domain_id, data=domain_data)

        registry_path = domain_root / "registry" / "situation-capability-map.yaml"
        if not registry_path.is_file():
            raise AuthoringIntegrityError(f"generated situation registry is missing: {registry_path}")
        registry = _load_yaml(registry_path)
        routes = registry.get("map") or {}
        if not isinstance(routes, dict):
            raise AuthoringIntegrityError(f"registry.map must be a mapping: {registry_path}")

        capabilities: dict[str, SourceDocument] = {}
        situations: dict[str, SourceDocument] = {}
        objects: dict[str, SourceDocument] = {}
        artifacts: dict[str, SourceDocument] = {}
        variants: dict[str, SourceDocument] = {}
        object_manifests: dict[str, SourceDocument] = {}
        knowledge_manifests: dict[str, SourceDocument] = {}

        for path in sorted(domain_root.rglob("*.yaml")):
            if path == domain_path or "registry" in path.relative_to(domain_root).parts:
                continue
            if path.is_symlink():
                raise AuthoringIntegrityError(f"symlinked Expert Brain source is not allowed: {path}")
            rel = path.relative_to(domain_root).parts
            data = _load_yaml(path)
            kind: str | None = None
            target: dict[str, SourceDocument] | None = None
            identifier: str | None = None
            version: str | None = None

            if path.name == "capability.yaml":
                kind, target = "capability", capabilities
            elif path.name == "objects.yaml" and rel and rel[0] == "capabilities":
                kind, target = "object_manifest", object_manifests
                identifier = str(data.get("capability") or "").strip()
                version = "object-manifest.v1"
            elif path.name == "knowledge.yaml":
                kind, target = "knowledge_manifest", knowledge_manifests
                identifier = str(data.get("capability") or "").strip()
                version = "knowledge-manifest.v1"
            elif "situations" in rel:
                kind, target = "situation", situations
            elif rel and rel[0] == "objects":
                kind, target = "object", objects
            elif rel and rel[0] in {
                    "playbooks", "heuristics", "mental-models", "rules",
                    "decision-frameworks"}:
                kind, target = "artifact", artifacts
            elif path.name in {"model.yaml", "vertical.yaml", "offering.yaml"}:
                kind, target = "variant", variants
            else:
                continue

            if not identifier:
                identifier, version = _identity(data, path)
            document = _source(kind=kind, path=path, root=self.root, domain_id=domain_id,
                               data=data, identifier=identifier, version=version)
            _insert(target, document)

        for capability_id in capabilities:
            if capability_id not in object_manifests:
                raise AuthoringIntegrityError(
                    f"capability {capability_id!r} has no objects.yaml")
            if capability_id not in knowledge_manifests:
                raise AuthoringIntegrityError(
                    f"capability {capability_id!r} has no knowledge.yaml")
        for situation_type, route in routes.items():
            if not isinstance(route, dict):
                raise AuthoringIntegrityError(
                    f"registry route {domain_id}:{situation_type} must be a mapping")
            for situation_id in route.get("situations") or ():
                if situation_id not in situations:
                    raise AuthoringIntegrityError(
                        f"registry route {domain_id}:{situation_type} references missing "
                        f"situation {situation_id!r}")

        return DomainRecord(
            domain=domain_doc,
            routes=freeze_mapping(routes),
            capabilities=MappingProxyType(capabilities),
            situations=MappingProxyType(situations),
            objects=MappingProxyType(objects),
            artifacts=MappingProxyType(artifacts),
            variants=MappingProxyType(variants),
            object_manifests=MappingProxyType(object_manifests),
            knowledge_manifests=MappingProxyType(knowledge_manifests),
        )

    def domain(self, domain_id: str) -> DomainRecord:
        try:
            return self.domains[domain_id]
        except KeyError as exc:
            raise AuthoringIntegrityError(f"unknown authored domain {domain_id!r}") from exc


def default_authoring_root() -> Path:
    return Path(__file__).resolve().parents[3] / "Domain Expertise"


__all__ = ["ExpertBrainCatalog", "default_authoring_root"]
