from __future__ import annotations

from collections import defaultdict

from fleet.core.models import AgentReplica
from fleet.core.store import StateStore


class LoadBalancer:
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self._cursors: dict[str, int] = defaultdict(int)

    def choose(self, deployment_name: str) -> AgentReplica:
        deployment = self.store.get_deployment(deployment_name)
        replicas = deployment.running_replicas
        if not replicas:
            raise RuntimeError(f"deployment {deployment_name!r} has no running replicas")
        cursor = self._cursors[deployment_name] % len(replicas)
        self._cursors[deployment_name] += 1
        replica = replicas[cursor]
        self.store.log(deployment_name, f"routed request to {replica.id}")
        return replica
