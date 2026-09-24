"""Base entity for Docker Swarm Monitor."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DockerSwarmConfigEntry
from .const import DOMAIN
from .coordinator import DockerSwarmCoordinator


class DockerSwarmEntity(CoordinatorEntity[DockerSwarmCoordinator]):
    """Base class for coordinator-backed Swarm entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DockerSwarmCoordinator, entry: DockerSwarmConfigEntry
    ) -> None:
        """Initialize shared entity attributes."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Docker",
            model="Swarm",
        )
