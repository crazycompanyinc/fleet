from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from fastapi import HTTPException

from fleet.cli import cli, engine as cli_engine
from fleet.core.engine import FleetEngine
from fleet.core.models import AgentStatus, Environment, ResourceLimits
from fleet.packaging.builder import PackageBuilder
from fleet.server import app as server


def test_builder_uses_source_name() -> None:
    package = PackageBuilder().build("Felix-CTO")
    assert package.name == "felix-cto"


def test_builder_accepts_explicit_name_and_version() -> None:
    package = PackageBuilder().build("x", name="felix", version="2.1.0")
    assert package.ref == "felix:2.1.0"


def test_builder_reads_json_manifest(tmp_path) -> None:
    manifest = tmp_path / "fleet.json"
    manifest.write_text(json.dumps({"name": "cto", "version": "3.0.0", "entrypoint": "main:run"}))
    package = PackageBuilder().build(tmp_path)
    assert package.ref == "cto:3.0.0"
    assert package.entrypoint == "main:run"


def test_builder_reads_resource_limits(tmp_path) -> None:
    manifest = tmp_path / "fleet.json"
    manifest.write_text(json.dumps({"name": "cto", "resources": {"cpu": 2, "memory_mb": 1024, "api_rpm": 90}}))
    package = PackageBuilder().build(tmp_path)
    assert package.resources.cpu == 2
    assert package.resources.memory_mb == 1024
    assert package.resources.api_rpm == 90


def test_resource_limits_validate_positive_values() -> None:
    with pytest.raises(ValueError):
        ResourceLimits(cpu=0).validate()


def test_engine_init_returns_status() -> None:
    assert FleetEngine().init()["status"] == "initialized"


def test_registry_stores_built_package() -> None:
    engine = FleetEngine()
    package = engine.build("Felix-CTO", name="felix")
    assert engine.registry.pull("felix") is package


def test_registry_latest_returns_highest_version() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix", version="1.0.0")
    engine.build("Felix-CTO", name="felix", version="2.0.0")
    assert engine.registry.pull("felix").version == "2.0.0"


def test_deploy_creates_running_replicas() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    deployment = engine.deploy("felix", replicas=3)
    assert len(deployment.replicas) == 3
    assert all(replica.status == AgentStatus.RUNNING for replica in deployment.replicas)


def test_deploy_supports_environment() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    deployment = engine.deploy("felix", environment="edge")
    assert deployment.environment == Environment.EDGE


def test_status_reports_desired_and_running_replicas() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=2)
    assert engine.status()[0]["running_replicas"] == 2


def test_scale_up_adds_replicas() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=1)
    deployment = engine.scale("felix", 4)
    assert len(deployment.replicas) == 4


def test_scale_down_removes_replicas() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=4)
    deployment = engine.scale("felix", 2)
    assert len(deployment.replicas) == 2


def test_scale_rejects_negative_replicas() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix")
    with pytest.raises(ValueError):
        engine.scale("felix", -1)


def test_service_discovery_lists_running_replica_ids() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    deployment = engine.deploy("felix", replicas=2)
    assert len(engine.discover(deployment.service_name or "")) == 2


def test_load_balancer_round_robins() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=2)
    first = engine.route("felix")
    second = engine.route("felix")
    third = engine.route("felix")
    assert first != second
    assert first == third


def test_load_balancer_rejects_no_running_replicas() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=0)
    with pytest.raises(RuntimeError):
        engine.route("felix")


def test_health_is_healthy_after_deploy() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=1)
    assert engine.health("felix") == {"felix": "healthy"}


def test_crash_marks_replica_unhealthy() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    deployment = engine.deploy("felix", replicas=1)
    crashed = engine.crash("felix")
    replica = deployment.replicas[0]
    assert crashed == replica.id
    assert replica.status == AgentStatus.CRASHED


def test_health_check_restarts_crashed_replica() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    deployment = engine.deploy("felix", replicas=1)
    engine.crash("felix")
    assert engine.health("felix") == {"felix": "healthy"}
    assert deployment.replicas[0].restart_count == 1


def test_restart_policy_stops_after_limit() -> None:
    engine = FleetEngine(max_restarts=0)
    engine.build("Felix-CTO", name="felix")
    deployment = engine.deploy("felix")
    engine.crash("felix")
    engine.health("felix")
    assert deployment.replicas[0].status == AgentStatus.CRASHED


def test_alert_manager_records_crashes() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix")
    engine.crash("felix")
    engine.health("felix")
    assert engine.alerts.list()[0].deployment == "felix"


def test_record_load_sets_average() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=2)
    engine.record_load("felix", 0.8)
    assert engine.monitor.average_load("felix") == 0.8


def test_record_load_clamps_values() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix")
    assert engine.record_load("felix", 2.0) == 1.0


def test_autoscaler_scales_up_on_high_load() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=1)
    engine.record_load("felix", 0.95)
    assert engine.autoscale("felix") == 2


def test_autoscaler_scales_down_on_low_load() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix", replicas=3)
    engine.record_load("felix", 0.1)
    assert engine.autoscale("felix") == 2


def test_rolling_update_changes_replica_versions() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix", version="1.0.0")
    engine.deploy("felix", replicas=2)
    engine.build("Felix-CTO", name="felix", version="2.0.0")
    assert engine.rolling_update("felix", "2.0.0") == "2.0.0"
    assert {replica.version for replica in engine.store.get_deployment("felix").replicas} == {"2.0.0"}


def test_rolling_update_increments_revision() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix", version="1.0.0")
    deployment = engine.deploy("felix")
    engine.build("Felix-CTO", name="felix", version="2.0.0")
    engine.rolling_update("felix", "2.0.0")
    assert deployment.revision == 2


def test_rollback_restores_previous_version() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix", version="1.0.0")
    engine.deploy("felix")
    engine.build("Felix-CTO", name="felix", version="2.0.0")
    engine.rolling_update("felix", "2.0.0")
    assert engine.rollback("felix") == "1.0.0"


def test_rollback_without_target_raises() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix")
    with pytest.raises(RuntimeError):
        engine.rollback("felix")


def test_logs_are_centralized() -> None:
    engine = FleetEngine()
    engine.build("Felix-CTO", name="felix")
    engine.deploy("felix")
    assert len(engine.logs("felix")) >= 2


def test_demo_runs_complete_lifecycle() -> None:
    result = FleetEngine().demo()
    assert result["deployed_replicas"] == 3
    assert result["rolled_to"] == "2.0.0"
    assert result["scaled_replicas"] == 5
    assert result["recovered_health"] == {"felix-cto": "healthy"}


def test_cli_init() -> None:
    result = CliRunner().invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "initialized" in result.output


def test_cli_build_deploy_status() -> None:
    cli_engine.store.packages.clear()
    cli_engine.store.deployments.clear()
    runner = CliRunner()
    assert runner.invoke(cli, ["build", "Felix-CTO", "--name", "felix"]).exit_code == 0
    assert runner.invoke(cli, ["deploy", "felix", "--replicas", "2"]).exit_code == 0
    status = runner.invoke(cli, ["status"])
    assert status.exit_code == 0
    assert '"running_replicas": 2' in status.output


def test_cli_demo() -> None:
    result = CliRunner().invoke(cli, ["demo"])
    assert result.exit_code == 0
    assert '"scaled_replicas": 5' in result.output


def test_api_root() -> None:
    assert server.root()["name"] == "Fleet"


def test_api_build_deploy_and_scale() -> None:
    server.engine.store.packages.clear()
    server.engine.store.deployments.clear()
    assert server.build(server.BuildRequest(source="Felix-CTO", name="felix")) == {"package": "felix:1.0.0"}
    assert server.deploy(server.DeployRequest(agent="felix", replicas=1))["running_replicas"] == 1
    assert server.scale("felix", server.ScaleRequest(replicas=3))["desired_replicas"] == 3


def test_api_health_and_crash() -> None:
    server.engine.store.packages.clear()
    server.engine.store.deployments.clear()
    server.build(server.BuildRequest(source="Felix-CTO", name="felix"))
    server.deploy(server.DeployRequest(agent="felix", replicas=1))
    assert "replica" in server.crash("felix")
    assert server.health("felix") == {"felix": "healthy"}


def test_api_load_autoscales() -> None:
    server.engine.store.packages.clear()
    server.engine.store.deployments.clear()
    server.build(server.BuildRequest(source="Felix-CTO", name="felix"))
    server.deploy(server.DeployRequest(agent="felix", replicas=1))
    assert server.load("felix", server.LoadRequest(load=0.9))["replicas"] == 2


def test_api_missing_agent_returns_400() -> None:
    with pytest.raises(HTTPException) as exc:
        server.deploy(server.DeployRequest(agent="missing"))
    assert exc.value.status_code == 400
