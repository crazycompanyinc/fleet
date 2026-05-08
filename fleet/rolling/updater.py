from __future__ import annotations

from fleet.core.models import AgentPackage, AgentStatus
from fleet.core.store import StateStore


class RollingUpdater:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def update(self, deployment_name: str, package: AgentPackage) -> str:
        deployment = self.store.get_deployment(deployment_name)
        if deployment.package.version != package.version:
            deployment.previous_versions.append(deployment.package.version)
        deployment.package = package
        deployment.revision += 1
        for replica in deployment.replicas:
            replica.status = AgentStatus.UPDATING
            self.store.log(deployment.name, f"updating replica {replica.id}", {"to": package.version})
            replica.version = package.version
            replica.resources = package.resources
            replica.start()
            self.store.log(deployment.name, f"replica {replica.id} now on {package.version}")
        self.store.refresh_discovery(deployment)
        return package.version

    def rollback(self, deployment_name: str) -> str:
        deployment = self.store.get_deployment(deployment_name)
        if not deployment.previous_versions:
            raise RuntimeError(f"deployment {deployment_name!r} has no rollback target")
        previous = deployment.previous_versions.pop()
        package = self.store.get_package(deployment.package.name, previous)
        current = deployment.package.version
        deployment.package = package
        deployment.revision += 1
        for replica in deployment.replicas:
            replica.status = AgentStatus.UPDATING
            replica.version = previous
            replica.resources = package.resources
            replica.start()
        self.store.log(deployment.name, f"rolled back from {current} to {previous}")
        self.store.refresh_discovery(deployment)
        return previous
