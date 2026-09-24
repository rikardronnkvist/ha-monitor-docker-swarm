"""Tests for normalized Docker Swarm summaries."""

from custom_components.docker_swarm_monitor.models import build_summary


def _node(
    *,
    role: str = "worker",
    state: str = "ready",
    reachable: bool = True,
    leader: bool = False,
) -> dict:
    node = {"Spec": {"Role": role}, "Status": {"State": state}}
    if role == "manager":
        node["ManagerStatus"] = {
            "Reachability": "reachable" if reachable else "unreachable",
            "Leader": leader,
        }
    return node


def _service(service_id: str, mode: str, replicas: int = 1) -> dict:
    service_mode = (
        {"Replicated": {"Replicas": replicas}}
        if mode == "replicated"
        else {"Global": {}}
    )
    return {"ID": service_id, "Spec": {"Mode": service_mode}}


def _task(service_id: str, state: str, desired_state: str = "running") -> dict:
    return {
        "ServiceID": service_id,
        "DesiredState": desired_state,
        "Status": {"State": state},
    }


def test_healthy_swarm_summary() -> None:
    """A quorate cluster with fulfilled services is healthy."""
    summary = build_summary(
        "1.47",
        [
            _node(role="manager", leader=True),
            _node(role="manager"),
            _node(role="manager"),
            _node(),
        ],
        [_service("replicated", "replicated", 2), _service("global", "global")],
        [
            _task("replicated", "running"),
            _task("replicated", "running"),
            _task("global", "running"),
        ],
    )

    assert summary.healthy
    assert summary.managers_required_for_quorum == 2
    assert summary.services_healthy == 2
    assert summary.tasks_running == 3


def test_quorum_leader_nodes_and_services_affect_health() -> None:
    """Each required cluster-health condition can make the Swarm unhealthy."""
    base_services = [_service("service", "replicated")]
    running_tasks = [_task("service", "running")]

    no_quorum = build_summary(
        "1.47",
        [
            _node(role="manager", leader=True),
            _node(role="manager", reachable=False),
            _node(role="manager", reachable=False),
        ],
        base_services,
        running_tasks,
    )
    no_leader = build_summary(
        "1.47",
        [_node(role="manager"), _node(role="manager"), _node(role="manager")],
        base_services,
        running_tasks,
    )
    node_down = build_summary(
        "1.47",
        [_node(role="manager", leader=True), _node(state="down")],
        base_services,
        running_tasks,
    )
    service_shortfall = build_summary(
        "1.47",
        [_node(role="manager", leader=True)],
        [_service("service", "replicated", 2)],
        running_tasks,
    )

    assert not no_quorum.healthy
    assert not no_leader.healthy
    assert not node_down.healthy
    assert not service_shortfall.healthy


def test_task_categories_ignore_historical_tasks() -> None:
    """Only tasks currently desired to run contribute to status counts."""
    summary = build_summary(
        "1.47",
        [_node(role="manager", leader=True)],
        [_service("service", "replicated")],
        [
            _task("service", "preparing"),
            _task("service", "failed"),
            _task("service", "failed", desired_state="shutdown"),
        ],
    )

    assert summary.tasks_running == 0
    assert summary.tasks_transitional == 1
    assert summary.tasks_failed == 1
    assert summary.services_degraded == 1


def test_global_service_requires_current_running_tasks() -> None:
    """A global service is degraded with no tasks or a transitional task."""
    no_tasks = build_summary(
        "1.47",
        [_node(role="manager", leader=True)],
        [_service("global", "global")],
        [],
    )
    transitional = build_summary(
        "1.47",
        [_node(role="manager", leader=True)],
        [_service("global", "global")],
        [_task("global", "starting")],
    )

    assert no_tasks.services_degraded == 1
    assert transitional.services_degraded == 1


def test_scaled_to_zero_replicated_service_is_healthy() -> None:
    """A replicated service intentionally scaled to zero is fulfilled."""
    summary = build_summary(
        "1.47",
        [_node(role="manager", leader=True)],
        [_service("service", "replicated", 0)],
        [],
    )

    assert summary.services_healthy == 1
    assert summary.healthy
