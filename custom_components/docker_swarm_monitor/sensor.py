"""Aggregate sensors for Docker Swarm Monitor."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DockerSwarmConfigEntry
from .coordinator import DockerSwarmCoordinator
from .entity import DockerSwarmEntity, DockerSwarmNodeEntity
from .models import NodeInfo, SwarmSummary


@dataclass(frozen=True, kw_only=True)
class DockerSwarmSensorDescription(SensorEntityDescription):
    """Describe an aggregate Swarm sensor."""

    value_fn: Callable[[SwarmSummary], int]


SENSORS = tuple(
    DockerSwarmSensorDescription(
        key=key,
        translation_key=key,
        icon=icon,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="entities",
        value_fn=lambda data, attribute=attribute: getattr(data, attribute),
    )
    for key, attribute, icon in (
        ("nodes_total", "nodes_total", "mdi:server-network"),
        ("nodes_ready", "nodes_ready", "mdi:server-network"),
        ("nodes_non_ready", "nodes_non_ready", "mdi:server-network-off"),
        ("managers_total", "managers_total", "mdi:server-security"),
        ("managers_reachable", "managers_reachable", "mdi:server-security"),
        ("services_total", "services_total", "mdi:docker"),
        ("services_healthy", "services_healthy", "mdi:check-circle-outline"),
        ("services_degraded", "services_degraded", "mdi:alert-circle-outline"),
        ("tasks_running", "tasks_running", "mdi:play-circle-outline"),
        ("tasks_transitional", "tasks_transitional", "mdi:progress-clock"),
        ("tasks_failed", "tasks_failed", "mdi:close-circle-outline"),
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockerSwarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up aggregate and per-node sensors."""
    async_add_entities(
        DockerSwarmSensor(entry.runtime_data, entry, description)
        for description in SENSORS
    )

    coordinator = entry.runtime_data
    known_node_ids: set[str] = set()

    @callback
    def _async_add_node_sensors() -> None:
        """Add a sensor for any node not yet seen in a previous poll."""
        new_nodes = [
            node for node in coordinator.data.nodes if node.id not in known_node_ids
        ]
        if not new_nodes:
            return
        known_node_ids.update(node.id for node in new_nodes)
        async_add_entities(
            DockerSwarmNodeTasksSensor(coordinator, entry, node) for node in new_nodes
        )

    _async_add_node_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_node_sensors))


class DockerSwarmSensor(DockerSwarmEntity, SensorEntity):
    """An aggregate Docker Swarm count sensor."""

    entity_description: DockerSwarmSensorDescription

    def __init__(
        self,
        coordinator,
        entry: DockerSwarmConfigEntry,
        description: DockerSwarmSensorDescription,
    ) -> None:
        """Initialize an aggregate sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> int:
        """Return the current aggregate count."""
        return self.entity_description.value_fn(self.coordinator.data)


class DockerSwarmNodeTasksSensor(DockerSwarmNodeEntity, SensorEntity):
    """The current running-task count for a single Swarm node."""

    _attr_translation_key = "node_tasks_running"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "entities"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(
        self,
        coordinator: DockerSwarmCoordinator,
        entry: DockerSwarmConfigEntry,
        node: NodeInfo,
    ) -> None:
        """Initialize a per-node running-task sensor."""
        super().__init__(coordinator, entry, node)
        self._attr_unique_id = f"{entry.entry_id}_node_{node.id}_tasks_running"

    @property
    def native_value(self) -> int | None:
        """Return the node's current running-task count."""
        node = self._node
        return node.tasks_running if node is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        """Return the node's other current task counts and status."""
        node = self._node
        if node is None:
            return {}
        return {
            "transitional": node.tasks_transitional,
            "failed": node.tasks_failed,
            "node_state": node.node_state,
            "availability": node.availability,
            "role": node.role,
        }
