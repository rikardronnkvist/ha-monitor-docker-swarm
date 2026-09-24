"""Cluster health binary sensor for Docker Swarm Monitor."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DockerSwarmConfigEntry
from .entity import DockerSwarmEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DockerSwarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the cluster health sensor."""
    async_add_entities([DockerSwarmHealthBinarySensor(entry.runtime_data, entry)])


class DockerSwarmHealthBinarySensor(DockerSwarmEntity, BinarySensorEntity):
    """Represent aggregate Swarm health."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "swarm_health"

    def __init__(self, coordinator, entry: DockerSwarmConfigEntry) -> None:
        """Initialize the health sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_swarm_health"

    @property
    def is_on(self) -> bool:
        """Return whether the Swarm is healthy."""
        return self.coordinator.data.healthy
