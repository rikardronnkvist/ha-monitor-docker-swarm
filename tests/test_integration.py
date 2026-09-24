"""Tests for Docker Swarm Monitor setup and entities."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.docker_swarm_monitor.const import (
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.docker_swarm_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.docker_swarm_monitor.models import SwarmSummary

URL = "https://swarm.example"
SUMMARY = SwarmSummary(
    api_version="1.47",
    nodes_total=4,
    nodes_ready=4,
    nodes_non_ready=0,
    managers_total=3,
    managers_reachable=3,
    managers_required_for_quorum=2,
    leaders=1,
    services_total=2,
    services_healthy=2,
    services_degraded=0,
    tasks_running=5,
    tasks_transitional=0,
    tasks_failed=0,
)


async def test_setup_entities_and_unload(hass: HomeAssistant) -> None:
    """Setup creates one health and eleven aggregate count entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="swarm.example",
        unique_id=URL,
        data={CONF_URL: URL, CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.docker_swarm_monitor.api.DockerSwarmClient.async_get_summary",
        AsyncMock(return_value=SUMMARY),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 12

    states_by_unique_id = {
        entity.unique_id: hass.states.get(entity.entity_id) for entity in entities
    }
    assert states_by_unique_id[f"{entry.entry_id}_swarm_health"].state == "on"
    assert states_by_unique_id[f"{entry.entry_id}_nodes_total"].state == "4"
    assert states_by_unique_id[f"{entry.entry_id}_tasks_running"].state == "5"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_diagnostics_redact_endpoint(hass: HomeAssistant) -> None:
    """Diagnostics expose aggregates without the endpoint or raw API data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="swarm.example",
        unique_id=URL,
        data={CONF_URL: URL, CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.docker_swarm_monitor.api.DockerSwarmClient.async_get_summary",
        AsyncMock(return_value=SUMMARY),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["config"]["url"] == "REDACTED"
    assert diagnostics["api_version"] == "1.47"
    assert diagnostics["summary"]["healthy"] is True
    assert URL not in str(diagnostics)
