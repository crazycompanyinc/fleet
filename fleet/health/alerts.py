from __future__ import annotations

from dataclasses import dataclass, field

from fleet.core.models import utcnow


@dataclass(slots=True)
class Alert:
    deployment: str
    message: str
    severity: str = "warning"
    ts: str = field(default_factory=lambda: utcnow().isoformat())


class AlertManager:
    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def emit(self, deployment: str, message: str, *, severity: str = "warning") -> Alert:
        alert = Alert(deployment=deployment, message=message, severity=severity)
        self.alerts.append(alert)
        return alert

    def list(self) -> list[Alert]:
        return list(self.alerts)
