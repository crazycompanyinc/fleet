from __future__ import annotations

from fleet.core.models import AgentReplica, AgentStatus


class RestartPolicy:
    def __init__(self, max_restarts: int = 3) -> None:
        self.max_restarts = max_restarts

    def should_restart(self, replica: AgentReplica) -> bool:
        return replica.status == AgentStatus.CRASHED and replica.restart_count < self.max_restarts
