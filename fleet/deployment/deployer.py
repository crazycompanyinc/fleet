from __future__ import annotations

from fleet.core.models import AgentDeployment, AgentPackage, AgentReplica, Environment
from fleet.core.store import StateStore


class Deployer:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def deploy(
        self,
        package: AgentPackage,
        *,
        name: str | None = None,
        replicas: int = 1,
        environment: Environment = Environment.LOCAL,
    ) -> AgentDeployment:
        deployment = AgentDeployment(
            name=name or package.name,
            package=package,
            desired_replicas=replicas,
            environment=environment,
        )
        for _ in range(replicas):
            deployment.replicas.append(self._new_replica(deployment))
        self.store.add_deployment(deployment)
        for replica in deployment.replicas:
            self.store.log(deployment.name, f"replica {replica.id} started", {"version": replica.version})
        return deployment

    def scale(self, name: str, replicas: int) -> AgentDeployment:
        if replicas < 0:
            raise ValueError("replicas cannot be negative")
        deployment = self.store.get_deployment(name)
        current = len(deployment.replicas)
        if replicas > current:
            for _ in range(replicas - current):
                replica = self._new_replica(deployment)
                deployment.replicas.append(replica)
                self.store.log(name, f"replica {replica.id} started", {"version": replica.version})
        elif replicas < current:
            for replica in deployment.replicas[replicas:]:
                replica.stop()
                self.store.log(name, f"replica {replica.id} stopped")
            deployment.replicas = deployment.replicas[:replicas]
        deployment.desired_replicas = replicas
        self.store.refresh_discovery(deployment)
        self.store.log(name, f"scaled to {replicas} replicas")
        return deployment

    def _new_replica(self, deployment: AgentDeployment) -> AgentReplica:
        replica = AgentReplica(
            package_name=deployment.package.name,
            version=deployment.package.version,
            deployment_name=deployment.name,
            environment=deployment.environment,
            resources=deployment.package.resources,
        )
        replica.start()
        return replica
