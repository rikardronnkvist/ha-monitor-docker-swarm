"""Diagnostics for Docker Swarm Monitor."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import DockerSwarmConfigEntry
from .const import CONF_SCAN_INTERVAL, CONF_VERIFY_SSL, DEFAULT_SCAN_INTERVAL


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DockerSwarmConfigEntry
) -> dict[str, Any]:
    """Return privacy-preserving diagnostics for a config entry."""
    coordinator = entry.runtime_data
    summary = coordinator.data
    return {
        "config": {
            "url": "REDACTED",
            "verify_ssl": entry.data[CONF_VERIFY_SSL],
            "scan_interval": entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        },
        "last_update_success": coordinator.last_update_success,
        "api_version": summary.api_version,
        "summary": {
            field: getattr(summary, field)
            for field in summary.__dataclass_fields__
            if field != "api_version"
        }
        | {"healthy": summary.healthy},
    }
