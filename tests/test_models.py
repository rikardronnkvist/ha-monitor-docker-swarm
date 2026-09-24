"""Tests for normalized Docker Swarm summaries."""

from custom_components.docker_swarm_monitor.models import build_summary


def _node(
    *,
    node_id: str = "node-1",
    hostname: str | None = None,
    role: str = "worker",
    state: str = "ready",
    availability: str = "active",
    engine_version: str | None = "24.0.0",
    reachable: bool = True,
    leader: bool = False,
) -> dict:
    node = {
        "ID": node_id,
        "Spec": {"Role": role, "Availability": availability},
        "Status": {"State": state},
        "Description": {
            "Hostname": hostname or node_id,
            "Engine": {"EngineVersion": engine_version},
        },
    }
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


def _task(
    service_id: str,
    state: str,
    desired_state: str = "running",
    node_id: str | None = None,
) -> dict:
    task = {
        "ServiceID": service_id,
        "DesiredState": desired_state,
        "Status": {"State": state},
    }
    if node_id is not None:
        task["NodeID"] = node_id
    return task


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


def test_node_without_tasks_has_zero_counts() -> None:
    """A node with no matching tasks reports zero for every task count."""
    summary = build_summary(
        "1.47",
        [_node(node_id="node-1", role="manager", leader=True)],
        [],
        [],
    )

    assert len(summary.nodes) == 1
    node = summary.nodes[0]
    assert node.tasks_running == 0
    assert node.tasks_transitional == 0
    assert node.tasks_failed == 0


def test_task_without_node_id_is_not_attributed_to_any_node() -> None:
    """A task with no NodeID still counts in the aggregate but joins no node."""
    summary = build_summary(
        "1.47",
        [_node(node_id="node-1", role="manager", leader=True)],
        [_service("service", "replicated")],
        [_task("service", "preparing", node_id=None)],
    )

    assert summary.tasks_transitional == 1
    assert summary.nodes[0].tasks_transitional == 0


def test_node_task_counts_ignore_historical_tasks() -> None:
    """A node's counts exclude tasks whose desired state is shutdown."""
    summary = build_summary(
        "1.47",
        [_node(node_id="node-1", role="manager", leader=True)],
        [_service("service", "replicated")],
        [
            _task("service", "preparing", node_id="node-1"),
            _task("service", "failed", node_id="node-1"),
            _task("service", "failed", desired_state="shutdown", node_id="node-1"),
        ],
    )

    node = summary.nodes[0]
    assert node.tasks_running == 0
    assert node.tasks_transitional == 1
    assert node.tasks_failed == 1


def test_node_down_is_reported() -> None:
    """A down node is reported with its raw node state."""
    summary = build_summary(
        "1.47",
        [
            _node(node_id="manager", role="manager", leader=True),
            _node(node_id="worker", state="down"),
        ],
        [],
        [],
    )

    nodes_by_id = {node.id: node for node in summary.nodes}
    assert nodes_by_id["worker"].node_state == "down"


def test_new_node_appears_in_summary() -> None:
    """A node present in the /nodes response produces a matching NodeInfo."""
    summary = build_summary(
        "1.47",
        [
            _node(node_id="manager", role="manager", leader=True),
            _node(node_id="worker-new"),
        ],
        [],
        [],
    )

    assert {node.id for node in summary.nodes} == {"manager", "worker-new"}


def test_removed_node_is_absent_from_summary() -> None:
    """build_summary is stateless: a node missing from /nodes is simply absent."""
    summary = build_summary(
        "1.47",
        [_node(node_id="manager", role="manager", leader=True)],
        [],
        [],
    )

    assert {node.id for node in summary.nodes} == {"manager"}


def test_running_tasks_sum_matches_aggregate() -> None:
    """The sum of each node's running tasks equals the aggregate count."""
    summary = build_summary(
        "1.47",
        [
            _node(node_id="manager", role="manager", leader=True),
            _node(node_id="worker"),
        ],
        [_service("service", "replicated", 3)],
        [
            _task("service", "running", node_id="manager"),
            _task("service", "running", node_id="worker"),
            _task("service", "running", node_id="worker"),
        ],
    )

    assert sum(node.tasks_running for node in summary.nodes) == summary.tasks_running
    assert summary.tasks_running == 3
