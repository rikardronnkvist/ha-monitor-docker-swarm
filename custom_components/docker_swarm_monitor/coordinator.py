"""Data coordinator for Docker Swarm Monitor."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DockerSwarmClient, DockerSwarmError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .models import SwarmSummary

_LOGGER = logging.getLogger(__name__)


class DockerSwarmCoordinator(DataUpdateCoordinator[SwarmSummary]):
    """Poll and distribute normalized Docker Swarm state."""

    def __init__(
        self, hass: HomeAssistant, config_entry, client: DockerSwarmClient
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
            always_update=False,
        )

    async def _async_update_data(self) -> SwarmSummary:
        """Fetch the latest Swarm summary."""
        try:
            return await self.client.async_get_summary()
        except DockerSwarmError as err:
            raise UpdateFailed(str(err) or type(err).__name__) from err
