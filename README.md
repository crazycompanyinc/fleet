# Fleet

Fleet is an agent deployment and orchestration platform: Kubernetes-style packaging, deployment, scaling, health checks, rolling updates, rollback, service discovery, load balancing, and centralized logs for AI agent fleets.

## Quick Start

```bash
python -m pip install -e ".[dev]"
fleet demo
fleet init
fleet build ./agents/felix
fleet deploy felix-cto --replicas 3
fleet status
fleet health
fleet logs felix-cto
```

## API

```bash
uvicorn fleet.server.app:app --reload
```

## Project Layout

- `fleet/core/` - models and in-memory state store
- `fleet/packaging/` - agent packages, builder, and registry
- `fleet/deployment/` - deployment engine and configuration
- `fleet/scaling/` - autoscaling, load balancing, and resource monitoring
- `fleet/health/` - health checks, restart policy, alerting
- `fleet/rolling/` - rolling updates and rollback
- `fleet/server/` - FastAPI app
- `fleet/cli.py` - Click CLI
