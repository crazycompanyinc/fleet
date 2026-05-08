from __future__ import annotations

import json
from typing import Any

import click

from fleet.core.engine import FleetEngine


engine = FleetEngine()


def emit(data: Any) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


@click.group()
def cli() -> None:
    """Fleet agent orchestration CLI."""


@cli.command("init")
def init_command() -> None:
    """Initialize Fleet."""
    emit(engine.init())


@cli.command("build")
@click.argument("agent")
@click.option("--name", default=None, help="Package name.")
@click.option("--version", default="1.0.0", help="Package version.")
@click.option("--entrypoint", default="agent:run", help="Agent entrypoint.")
def build_command(agent: str, name: str | None, version: str, entrypoint: str) -> None:
    """Package an agent as a deployable unit."""
    package = engine.build(agent, name=name, version=version, entrypoint=entrypoint)
    emit({"package": package.ref, "entrypoint": package.entrypoint})


@cli.command("deploy")
@click.argument("agent")
@click.option("--version", default=None, help="Package version.")
@click.option("--replicas", default=1, type=int, help="Replica count.")
@click.option("--environment", default="local", type=click.Choice(["local", "cloud", "edge"]))
def deploy_command(agent: str, version: str | None, replicas: int, environment: str) -> None:
    """Deploy an agent package."""
    deployment = engine.deploy(agent, version=version, replicas=replicas, environment=environment)
    emit(deployment.to_dict())


@cli.command("scale")
@click.argument("agent")
@click.option("--replicas", required=True, type=int, help="Replica count.")
def scale_command(agent: str, replicas: int) -> None:
    """Scale an agent deployment."""
    emit(engine.scale(agent, replicas).to_dict())


@cli.command("status")
def status_command() -> None:
    """Show deployment status."""
    emit(engine.status())


@cli.command("logs")
@click.argument("agent", required=False)
def logs_command(agent: str | None) -> None:
    """Show centralized logs."""
    emit(engine.logs(agent))


@cli.command("rollback")
@click.argument("agent")
def rollback_command(agent: str) -> None:
    """Roll back to the previous deployed version."""
    emit({"agent": agent, "version": engine.rollback(agent)})


@cli.command("health")
@click.argument("agent", required=False)
def health_command(agent: str | None) -> None:
    """Run health checks."""
    emit(engine.health(agent))


@cli.command("crash")
@click.argument("agent")
def crash_command(agent: str) -> None:
    """Simulate a replica crash."""
    emit({"agent": agent, "replica": engine.crash(agent)})


@cli.command("demo")
def demo_command() -> None:
    """Run the Felix-CTO orchestration demo."""
    emit(engine.demo())


if __name__ == "__main__":
    cli()
