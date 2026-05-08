from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, is_dataclass
from typing import Any

from fleet.core.models import AgentDeployment, AgentPackage, AgentReplica, utcnow


class StateStore:
    """Small in-memory store used by the demo server, CLI, and tests."""

    def __init__(self) -> None:
        self.packages: dict[str, dict[str, AgentPackage]] = defaultdict(dict)
        self.deployments: dict[str, AgentDeployment] = {}
        self.logs: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.discovery: dict[str, list[str]] = defaultdict(list)

    def add_package(self, package: AgentPackage) -> AgentPackage:
        self.packages[package.name][package.version] = package
        self.log(package.name, f"packaged {package.ref}", {"version": package.version})
        return package

    def get_package(self, name: str, version: str | None = None) -> AgentPackage:
        versions = self.packages.get(name)
        if not versions:
            raise KeyError(f"package {name!r} not found")
        if version is None:
            return versions[sorted(versions)[-1]]
        try:
            return versions[version]
        except KeyError as exc:
            raise KeyError(f"package {name}:{version} not found") from exc

    def list_packages(self) -> list[AgentPackage]:
        return [package for versions in self.packages.values() for package in versions.values()]

    def add_deployment(self, deployment: AgentDeployment) -> AgentDeployment:
        self.deployments[deployment.name] = deployment
        self.refresh_discovery(deployment)
        self.log(deployment.name, f"deployed {deployment.package.ref}")
        return deployment

    def get_deployment(self, name: str) -> AgentDeployment:
        try:
            return self.deployments[name]
        except KeyError as exc:
            raise KeyError(f"deployment {name!r} not found") from exc

    def list_deployments(self) -> list[AgentDeployment]:
        return list(self.deployments.values())

    def refresh_discovery(self, deployment: AgentDeployment) -> None:
        self.discovery[deployment.service_name or deployment.name] = [
            replica.id for replica in deployment.running_replicas
        ]

    def log(self, agent: str, message: str, fields: dict[str, Any] | None = None) -> None:
        record = {
            "ts": utcnow().isoformat(),
            "agent": agent,
            "message": message,
            "fields": fields or {},
        }
        self.logs[agent].append(record)

    def get_logs(self, agent: str | None = None) -> list[dict[str, Any]]:
        if agent is not None:
            return list(self.logs.get(agent, []))
        records: list[dict[str, Any]] = []
        for agent_logs in self.logs.values():
            records.extend(agent_logs)
        return sorted(records, key=lambda item: item["ts"])

    def snapshot(self) -> dict[str, Any]:
        def clean(value: Any) -> Any:
            if is_dataclass(value):
                return clean(asdict(value))
            if isinstance(value, dict):
                return {key: clean(inner) for key, inner in value.items()}
            if isinstance(value, list):
                return [clean(inner) for inner in value]
            if hasattr(value, "value"):
                return value.value
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return value

        return {
            "packages": clean(self.list_packages()),
            "deployments": [deployment.to_dict() for deployment in self.deployments.values()],
            "services": dict(self.discovery),
        }
