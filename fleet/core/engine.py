from __future__ import annotations

from pathlib import Path
from typing import Any

from fleet.core.models import AgentDeployment, AgentPackage, Environment, ResourceLimits
from fleet.core.store import StateStore
from fleet.deployment.deployer import Deployer
from fleet.health.alerts import AlertManager
from fleet.health.checker import HealthChecker
from fleet.health.restart import RestartPolicy
from fleet.packaging.builder import PackageBuilder
from fleet.packaging.registry import Registry
from fleet.rolling.updater import RollingUpdater
from fleet.scaling.autoscaler import AutoScaler
from fleet.scaling.load_balancer import LoadBalancer
from fleet.scaling.resource_monitor import ResourceMonitor


class FleetEngine:
    """High-level API for packaging, deploying, scaling, and managing agents."""

    def __init__(self, *, max_restarts: int = 3) -> None:
        self.store = StateStore()
        self.builder = PackageBuilder()
        self.registry = Registry(self.store)
        self.deployer = Deployer(self.store)
        self.alerts = AlertManager()
        self.health_checker = HealthChecker(self.store, RestartPolicy(max_restarts), self.alerts)
        self.monitor = ResourceMonitor(self.store)
        self.autoscaler = AutoScaler(self.deployer, self.monitor)
        self.load_balancer = LoadBalancer(self.store)
        self.updater = RollingUpdater(self.store)

    def init(self) -> dict[str, str]:
        return {"status": "initialized", "registry": "in-memory"}

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
        package = self.builder.build(
            source,
            name=name,
            version=version,
            entrypoint=entrypoint,
            resources=resources,
            metadata=metadata,
        )
        return self.registry.push(package)

    def deploy(
        self,
        agent: str,
        *,
        version: str | None = None,
        replicas: int = 1,
        environment: Environment | str = Environment.LOCAL,
    ) -> AgentDeployment:
        package = self.registry.pull(agent, version)
        env = environment if isinstance(environment, Environment) else Environment(environment)
        return self.deployer.deploy(package, replicas=replicas, environment=env)

    def scale(self, agent: str, replicas: int) -> AgentDeployment:
        return self.deployer.scale(agent, replicas)

    def status(self) -> list[dict[str, Any]]:
        return [deployment.to_dict() for deployment in self.store.list_deployments()]

    def logs(self, agent: str | None = None) -> list[dict[str, Any]]:
        return self.store.get_logs(agent)

    def health(self, agent: str | None = None) -> dict[str, str]:
        return self.health_checker.check(agent)

    def crash(self, agent: str, replica_id: str | None = None) -> str:
        return self.health_checker.crash(agent, replica_id)

    def rolling_update(self, agent: str, version: str) -> str:
        deployment = self.store.get_deployment(agent)
        package = self.registry.pull(deployment.package.name, version)
        return self.updater.update(agent, package)

    def rollback(self, agent: str) -> str:
        return self.updater.rollback(agent)

    def record_load(self, agent: str, load: float) -> float:
        return self.monitor.record_load(agent, load)

    def autoscale(self, agent: str) -> int:
        return self.autoscaler.reconcile(agent)

    def route(self, agent: str) -> str:
        return self.load_balancer.choose(agent).id

    def discover(self, service_name: str) -> list[str]:
        return list(self.store.discovery.get(service_name, []))

    def demo(self) -> dict[str, Any]:
        v1 = self.build("Felix-CTO", name="felix-cto", version="1.0.0")
        deployment = self.deploy(v1.name, replicas=3)
        initial_health = self.health(v1.name)
        crashed = self.crash(v1.name)
        recovered_health = self.health(v1.name)
        self.build("Felix-CTO", name="felix-cto", version="2.0.0")
        updated_to = self.rolling_update(v1.name, "2.0.0")
        scaled = self.scale(v1.name, 5)
        return {
            "package": v1.ref,
            "deployed_replicas": 3,
            "initial_health": initial_health,
            "crashed_replica": crashed,
            "recovered_health": recovered_health,
            "rolled_to": updated_to,
            "scaled_replicas": scaled.desired_replicas,
            "logs": self.logs(v1.name),
            "status": deployment.to_dict(),
        }
