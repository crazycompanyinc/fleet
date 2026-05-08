from __future__ import annotations

from dataclasses import dataclass, field

from fleet.core.models import Environment, ResourceLimits


@dataclass(slots=True)
class DeploymentConfig:
    environment: Environment = Environment.LOCAL
    replicas: int = 1
    resources: ResourceLimits = field(default_factory=ResourceLimits)


class ConfigManager:
    def create(
        self,
        *,
        environment: Environment | str = Environment.LOCAL,
        replicas: int = 1,
        resources: ResourceLimits | None = None,
    ) -> DeploymentConfig:
        if replicas < 0:
            raise ValueError("replicas cannot be negative")
        env = environment if isinstance(environment, Environment) else Environment(environment)
        return DeploymentConfig(environment=env, replicas=replicas, resources=resources or ResourceLimits())
