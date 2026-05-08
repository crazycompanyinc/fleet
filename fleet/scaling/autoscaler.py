from __future__ import annotations

from fleet.deployment.deployer import Deployer
from fleet.scaling.resource_monitor import ResourceMonitor


class AutoScaler:
    def __init__(
        self,
        deployer: Deployer,
        monitor: ResourceMonitor,
        *,
        min_replicas: int = 1,
        max_replicas: int = 10,
        target_load: float = 0.70,
    ) -> None:
        self.deployer = deployer
        self.monitor = monitor
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.target_load = target_load

    def reconcile(self, deployment_name: str) -> int:
        deployment = self.deployer.store.get_deployment(deployment_name)
        load = self.monitor.average_load(deployment_name)
        desired = deployment.desired_replicas
        if load > self.target_load and desired < self.max_replicas:
            desired += 1
        elif load < self.target_load / 2 and desired > self.min_replicas:
            desired -= 1
        if desired != deployment.desired_replicas:
            self.deployer.scale(deployment_name, desired)
        return desired
