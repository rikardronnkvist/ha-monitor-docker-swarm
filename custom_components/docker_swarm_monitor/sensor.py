"""Aggregate sensors for Docker Swarm Monitor."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DockerSwarmConfigEntry
from .entity import DockerSwarmEntity
from .models import SwarmSummary


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
    """Set up aggregate sensors."""
    async_add_entities(
        DockerSwarmSensor(entry.runtime_data, entry, description)
        for description in SENSORS
    )


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
