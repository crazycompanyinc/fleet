from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from fleet.core.engine import FleetEngine


app = FastAPI(title="Fleet", version="0.1.0", description="Kubernetes for AI agents")
engine = FleetEngine()


class BuildRequest(BaseModel):
    source: str
    name: str | None = None
    version: str = "1.0.0"
    entrypoint: str = "agent:run"


class DeployRequest(BaseModel):
    agent: str
    version: str | None = None
    replicas: int = Field(default=1, ge=0)
    environment: str = "local"


class ScaleRequest(BaseModel):
    replicas: int = Field(ge=0)


class LoadRequest(BaseModel):
    load: float = Field(ge=0.0, le=1.0)


def handle_errors(fn: Any) -> Any:
    try:
        return fn()
    except (KeyError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Fleet", "description": "Kubernetes for AI agents"}


@app.post("/init")
def init() -> dict[str, str]:
    return engine.init()


@app.post("/packages")
def build(request: BuildRequest) -> dict[str, str]:
    def run() -> dict[str, str]:
        package = engine.build(
            request.source,
            name=request.name,
            version=request.version,
            entrypoint=request.entrypoint,
        )
        return {"package": package.ref}

    return handle_errors(run)


@app.post("/deployments")
def deploy(request: DeployRequest) -> dict[str, Any]:
    return handle_errors(
        lambda: engine.deploy(
            request.agent,
            version=request.version,
            replicas=request.replicas,
            environment=request.environment,
        ).to_dict()
    )


@app.get("/deployments")
def deployments() -> list[dict[str, Any]]:
    return engine.status()


@app.post("/deployments/{agent}/scale")
def scale(agent: str, request: ScaleRequest) -> dict[str, Any]:
    return handle_errors(lambda: engine.scale(agent, request.replicas).to_dict())


@app.get("/deployments/{agent}/health")
def health(agent: str) -> dict[str, str]:
    return handle_errors(lambda: engine.health(agent))


@app.post("/deployments/{agent}/crash")
def crash(agent: str) -> dict[str, str]:
    return handle_errors(lambda: {"replica": engine.crash(agent)})


@app.post("/deployments/{agent}/rollback")
def rollback(agent: str) -> dict[str, str]:
    return handle_errors(lambda: {"version": engine.rollback(agent)})


@app.post("/deployments/{agent}/load")
def load(agent: str, request: LoadRequest) -> dict[str, float | int]:
    def run() -> dict[str, float | int]:
        engine.record_load(agent, request.load)
        return {"load": request.load, "replicas": engine.autoscale(agent)}

    return handle_errors(run)


@app.get("/logs")
def logs(agent: str | None = None) -> list[dict[str, Any]]:
    return engine.logs(agent)


@app.post("/demo")
def demo() -> dict[str, Any]:
    return engine.demo()
