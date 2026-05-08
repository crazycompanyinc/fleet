from __future__ import annotations

from fleet.core.store import StateStore


class ResourceMonitor:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def record_load(self, deployment_name: str, load: float) -> float:
        deployment = self.store.get_deployment(deployment_name)
        load = max(0.0, min(1.0, load))
        for replica in deployment.running_replicas:
            replica.load = load
        self.store.log(deployment_name, "recorded load", {"load": load})
        return load

    def average_load(self, deployment_name: str) -> float:
        deployment = self.store.get_deployment(deployment_name)
        replicas = deployment.running_replicas
        if not replicas:
            return 0.0
        return sum(replica.load for replica in replicas) / len(replicas)
