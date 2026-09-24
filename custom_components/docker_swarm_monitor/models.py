"""Normalized Docker Swarm monitoring data."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

TRANSITIONAL_TASK_STATES = frozenset(
    {"new", "pending", "assigned", "accepted", "preparing", "ready", "starting"}
)
FAILED_TASK_STATES = frozenset({"failed", "rejected", "orphaned", "remove"})


@dataclass(frozen=True, slots=True)
class SwarmSummary:
    """Aggregate state exposed to Home Assistant."""

    api_version: str
    nodes_total: int
    nodes_ready: int
    nodes_non_ready: int
    managers_total: int
    managers_reachable: int
    managers_required_for_quorum: int
    leaders: int
    services_total: int
    services_healthy: int
    services_degraded: int
    tasks_running: int
    tasks_transitional: int
    tasks_failed: int

    @property
    def healthy(self) -> bool:
        """Return whether the control plane and all workloads are healthy."""
        return (
            self.managers_total > 0
            and self.managers_reachable >= self.managers_required_for_quorum
            and self.leaders == 1
            and self.nodes_ready == self.nodes_total
            and self.services_healthy == self.services_total
        )


def build_summary(
    api_version: str,
    nodes: Sequence[Mapping[str, Any]],
    services: Sequence[Mapping[str, Any]],
    tasks: Sequence[Mapping[str, Any]],
) -> SwarmSummary:
    """Build an immutable summary from Docker Engine API responses."""
    managers = [node for node in nodes if _nested(node, "Spec", "Role") == "manager"]
    nodes_ready = sum(_nested(node, "Status", "State") == "ready" for node in nodes)
    managers_reachable = sum(
        _nested(node, "ManagerStatus", "Reachability") == "reachable"
        for node in managers
    )
    leaders = sum(_nested(node, "ManagerStatus", "Leader") is True for node in managers)

    current_tasks = [task for task in tasks if task.get("DesiredState") == "running"]
    task_states = Counter(_nested(task, "Status", "State") for task in current_tasks)
    tasks_by_service: dict[str, list[Mapping[str, Any]]] = {}
    for task in current_tasks:
        service_id = task.get("ServiceID")
        if isinstance(service_id, str):
            tasks_by_service.setdefault(service_id, []).append(task)

    healthy_services = sum(
        _service_is_healthy(service, tasks_by_service.get(str(service.get("ID")), []))
        for service in services
    )

    managers_total = len(managers)
    return SwarmSummary(
        api_version=api_version,
        nodes_total=len(nodes),
        nodes_ready=nodes_ready,
        nodes_non_ready=len(nodes) - nodes_ready,
        managers_total=managers_total,
        managers_reachable=managers_reachable,
        managers_required_for_quorum=managers_total // 2 + 1,
        leaders=leaders,
        services_total=len(services),
        services_healthy=healthy_services,
        services_degraded=len(services) - healthy_services,
        tasks_running=task_states["running"],
        tasks_transitional=sum(
            task_states[state] for state in TRANSITIONAL_TASK_STATES
        ),
        tasks_failed=sum(task_states[state] for state in FAILED_TASK_STATES),
    )


def _service_is_healthy(
    service: Mapping[str, Any], tasks: Sequence[Mapping[str, Any]]
) -> bool:
    """Return whether a service has fulfilled its observable desired workload."""
    states = [_nested(task, "Status", "State") for task in tasks]
    has_failed_task = any(state in FAILED_TASK_STATES for state in states)
    mode = _nested(service, "Spec", "Mode")
    if not isinstance(mode, Mapping):
        return False

    replicated = mode.get("Replicated")
    if isinstance(replicated, Mapping):
        replicas = replicated.get("Replicas", 1)
        if not isinstance(replicas, int) or isinstance(replicas, bool) or replicas < 0:
            return False
        return states.count("running") >= replicas and not has_failed_task

    if isinstance(mode.get("Global"), Mapping):
        return bool(states) and all(state == "running" for state in states)

    return False


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    """Read a nested mapping without retaining raw API data."""
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current
