from __future__ import annotations

from fleet.core.models import AgentPackage
from fleet.core.store import StateStore


class VersionManager:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def latest(self, name: str) -> AgentPackage:
        return self.store.get_package(name)

    def previous(self, deployment_name: str) -> AgentPackage:
        deployment = self.store.get_deployment(deployment_name)
        if not deployment.previous_versions:
            raise RuntimeError(f"deployment {deployment_name!r} has no previous version")
        return self.store.get_package(deployment.package.name, deployment.previous_versions[-1])
