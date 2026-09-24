"""Docker Swarm Monitor integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import DockerSwarmClient
from .const import CONF_URL, CONF_VERIFY_SSL, DOMAIN, PLATFORMS
from .coordinator import DockerSwarmCoordinator

type DockerSwarmConfigEntry = ConfigEntry[DockerSwarmCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DockerSwarmConfigEntry) -> bool:
    """Set up Docker Swarm Monitor from a config entry."""
    client = DockerSwarmClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    coordinator = DockerSwarmCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DockerSwarmConfigEntry
) -> bool:
    """Unload a Docker Swarm Monitor config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: DockerSwarmConfigEntry
) -> None:
    """Reload an entry after its configuration changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: DockerSwarmConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow deleting a node device once its node has left the Swarm."""
    node_ids = {node.id for node in entry.runtime_data.data.nodes}
    prefix = f"{entry.entry_id}_node_"
    for domain, identifier in device_entry.identifiers:
        if domain == DOMAIN and identifier.startswith(prefix):
            return identifier.removeprefix(prefix) not in node_ids
    return False
