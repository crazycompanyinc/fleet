from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CRASHED = "crashed"
    RESTARTING = "restarting"
    STOPPED = "stopped"
    UPDATING = "updating"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class Environment(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    EDGE = "edge"


@dataclass(slots=True)
class ResourceLimits:
    cpu: float = 1.0
    memory_mb: int = 512
    api_rpm: int = 60

    def validate(self) -> None:
        if self.cpu <= 0:
            raise ValueError("cpu must be positive")
        if self.memory_mb <= 0:
            raise ValueError("memory_mb must be positive")
        if self.api_rpm <= 0:
            raise ValueError("api_rpm must be positive")


@dataclass(slots=True)
class AgentPackage:
    name: str
    version: str = "1.0.0"
    entrypoint: str = "agent:run"
    image: str | None = None
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("package name is required")
        if not self.version:
            raise ValueError("package version is required")
        self.resources.validate()

    @property
    def ref(self) -> str:
        return f"{self.name}:{self.version}"


@dataclass(slots=True)
class AgentReplica:
    package_name: str
    version: str
    deployment_name: str
    environment: Environment = Environment.LOCAL
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    id: str = field(default_factory=lambda: str(uuid4()))
    status: AgentStatus = AgentStatus.PENDING
    health: HealthState = HealthState.UNKNOWN
    restart_count: int = 0
    started_at: datetime | None = None
    updated_at: datetime = field(default_factory=utcnow)
    last_error: str | None = None
    load: float = 0.0

    def start(self) -> None:
        self.status = AgentStatus.RUNNING
        self.health = HealthState.HEALTHY
        self.started_at = utcnow()
        self.updated_at = self.started_at
        self.last_error = None

    def stop(self) -> None:
        self.status = AgentStatus.STOPPED
        self.health = HealthState.UNKNOWN
        self.updated_at = utcnow()

    def crash(self, reason: str = "simulated crash") -> None:
        self.status = AgentStatus.CRASHED
        self.health = HealthState.UNHEALTHY
        self.last_error = reason
        self.updated_at = utcnow()

    def restart(self) -> None:
        self.status = AgentStatus.RESTARTING
        self.restart_count += 1
        self.start()


@dataclass(slots=True)
class AgentDeployment:
    name: str
    package: AgentPackage
    environment: Environment = Environment.LOCAL
    desired_replicas: int = 1
    replicas: list[AgentReplica] = field(default_factory=list)
    revision: int = 1
    previous_versions: list[str] = field(default_factory=list)
    service_name: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.desired_replicas < 0:
            raise ValueError("desired_replicas cannot be negative")
        if self.service_name is None:
            self.service_name = f"{self.name}.fleet.local"

    @property
    def running_replicas(self) -> list[AgentReplica]:
        return [replica for replica in self.replicas if replica.status == AgentStatus.RUNNING]

    @property
    def health(self) -> HealthState:
        if not self.replicas:
            return HealthState.UNKNOWN
        unhealthy = sum(replica.health == HealthState.UNHEALTHY for replica in self.replicas)
        healthy = sum(replica.health == HealthState.HEALTHY for replica in self.replicas)
        if unhealthy:
            return HealthState.UNHEALTHY
        if healthy == len(self.replicas) and len(self.replicas) == self.desired_replicas:
            return HealthState.HEALTHY
        return HealthState.DEGRADED

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "package": self.package.ref,
            "environment": self.environment.value,
            "desired_replicas": self.desired_replicas,
            "running_replicas": len(self.running_replicas),
            "health": self.health.value,
            "revision": self.revision,
            "service_name": self.service_name,
        }
