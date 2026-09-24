"""Base entity for Docker Swarm Monitor."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DockerSwarmConfigEntry
from .const import DOMAIN
from .coordinator import DockerSwarmCoordinator
from .models import NodeInfo


def node_device_identifier(entry_id: str, node_id: str) -> str:
    """Build the device-registry identifier for a Swarm node device."""
    return f"{entry_id}_node_{node_id}"


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


class DockerSwarmNodeEntity(CoordinatorEntity[DockerSwarmCoordinator]):
    """Base class for coordinator-backed, per-Swarm-node entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DockerSwarmCoordinator,
        entry: DockerSwarmConfigEntry,
        node: NodeInfo,
    ) -> None:
        """Initialize shared per-node entity attributes."""
        super().__init__(coordinator)
        self._node_id = node.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node_device_identifier(entry.entry_id, node.id))},
            name=node.hostname,
            manufacturer="Docker",
            model="Swarm Node",
            sw_version=node.engine_version,
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def _node(self) -> NodeInfo | None:
        """Return the current NodeInfo for this entity, if the node still exists."""
        return next(
            (node for node in self.coordinator.data.nodes if node.id == self._node_id),
            None,
        )

    @property
    def available(self) -> bool:
        """Return whether the node is ready and the last poll succeeded."""
        node = self._node
        return super().available and node is not None and node.node_state == "ready"
