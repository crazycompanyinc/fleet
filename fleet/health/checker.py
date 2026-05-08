from __future__ import annotations

from fleet.core.models import AgentStatus, HealthState
from fleet.core.store import StateStore
from fleet.health.alerts import AlertManager
from fleet.health.restart import RestartPolicy


class HealthChecker:
    def __init__(self, store: StateStore, restart_policy: RestartPolicy, alerts: AlertManager) -> None:
        self.store = store
        self.restart_policy = restart_policy
        self.alerts = alerts

    def check(self, deployment_name: str | None = None) -> dict[str, str]:
        deployments = (
            [self.store.get_deployment(deployment_name)]
            if deployment_name
            else self.store.list_deployments()
        )
        results: dict[str, str] = {}
        for deployment in deployments:
            for replica in deployment.replicas:
                if replica.status == AgentStatus.CRASHED:
                    replica.health = HealthState.UNHEALTHY
                    self.alerts.emit(deployment.name, f"replica {replica.id} crashed")
                    if self.restart_policy.should_restart(replica):
                        replica.restart()
                        self.store.log(
                            deployment.name,
                            f"replica {replica.id} restarted",
                            {"restart_count": replica.restart_count},
                        )
                elif replica.status == AgentStatus.RUNNING:
                    replica.health = HealthState.HEALTHY
            self.store.refresh_discovery(deployment)
            results[deployment.name] = deployment.health.value
        return results

    def crash(self, deployment_name: str, replica_id: str | None = None, reason: str = "simulated crash") -> str:
        deployment = self.store.get_deployment(deployment_name)
        candidates = deployment.running_replicas
        if not candidates:
            raise RuntimeError(f"deployment {deployment_name!r} has no running replicas")
        replica = next((item for item in candidates if item.id == replica_id), candidates[0])
        replica.crash(reason)
        self.store.log(deployment_name, f"replica {replica.id} crashed", {"reason": reason})
        self.store.refresh_discovery(deployment)
        return replica.id
