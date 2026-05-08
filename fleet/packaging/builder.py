from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fleet.core.models import AgentPackage, ResourceLimits


class PackageBuilder:
    """Builds deployable agent packages from paths, manifests, or names."""

    manifest_names = ("fleet.json", "agent.json", "pyproject.toml")

    def build(
        self,
        source: str | Path,
        *,
        name: str | None = None,
        version: str = "1.0.0",
        entrypoint: str = "agent:run",
        resources: ResourceLimits | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentPackage:
        source_path = Path(source)
        manifest = self._read_manifest(source_path)
        package_name = name or manifest.get("name") or self._normalize_name(source_path)
        package_version = str(manifest.get("version") or version)
        package_entrypoint = str(manifest.get("entrypoint") or entrypoint)
        package_resources = resources or self._resources_from_manifest(manifest)
        package_metadata = {"source": str(source), **manifest.get("metadata", {}), **(metadata or {})}
        return AgentPackage(
            name=package_name,
            version=package_version,
            entrypoint=package_entrypoint,
            resources=package_resources,
            metadata=package_metadata,
        )

    def _read_manifest(self, source: Path) -> dict[str, Any]:
        if source.is_file() and source.suffix == ".json":
            return json.loads(source.read_text())
        if source.is_dir():
            for manifest_name in self.manifest_names[:2]:
                manifest_path = source / manifest_name
                if manifest_path.exists():
                    return json.loads(manifest_path.read_text())
        return {}

    def _resources_from_manifest(self, manifest: dict[str, Any]) -> ResourceLimits:
        data = manifest.get("resources") or {}
        return ResourceLimits(
            cpu=float(data.get("cpu", 1.0)),
            memory_mb=int(data.get("memory_mb", 512)),
            api_rpm=int(data.get("api_rpm", 60)),
        )

    def _normalize_name(self, source: Path) -> str:
        raw = source.stem if source.suffix else source.name
        return raw.strip().lower().replace("_", "-") or "agent"
