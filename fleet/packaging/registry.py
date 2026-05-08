from __future__ import annotations

from fleet.core.models import AgentPackage
from fleet.core.store import StateStore


class Registry:
    def __init__(self, store: StateStore) -> None:
        self.store = store

    def push(self, package: AgentPackage) -> AgentPackage:
        return self.store.add_package(package)

    def pull(self, name: str, version: str | None = None) -> AgentPackage:
        return self.store.get_package(name, version)

    def list(self) -> list[AgentPackage]:
        return self.store.list_packages()
