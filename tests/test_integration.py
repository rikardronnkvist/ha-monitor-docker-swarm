"""Tests for Docker Swarm Monitor setup and entities."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.docker_swarm_monitor import async_remove_config_entry_device
from custom_components.docker_swarm_monitor.const import (
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.docker_swarm_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.docker_swarm_monitor.entity import node_device_identifier
from custom_components.docker_swarm_monitor.models import NodeInfo, SwarmSummary

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
    nodes=(),
)
NODE_MANAGER = NodeInfo(
    id="node-1",
    hostname="swarm-manager-1",
    role="manager",
    node_state="ready",
    availability="active",
    engine_version="24.0.0",
    tasks_running=3,
    tasks_transitional=0,
    tasks_failed=0,
)


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="swarm.example",
        unique_id=URL,
        data={CONF_URL: URL, CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)
    return entry


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


async def test_node_sensor_created_for_each_node(hass: HomeAssistant) -> None:
    """Setup creates a running-tasks sensor and linked device per node."""
    entry = _entry(hass)
    summary = replace(SUMMARY, nodes=(NODE_MANAGER,))

    with patch(
        "custom_components.docker_swarm_monitor.api.DockerSwarmClient.async_get_summary",
        AsyncMock(return_value=summary),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_node_{NODE_MANAGER.id}_tasks_running"
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state.state == "3"
    assert state.attributes["transitional"] == 0
    assert state.attributes["failed"] == 0
    assert state.attributes["node_state"] == "ready"
    assert state.attributes["availability"] == "active"
    assert state.attributes["role"] == "manager"

    device_registry = dr.async_get(hass)
    node_device = device_registry.async_get_device(
        identifiers={(DOMAIN, node_device_identifier(entry.entry_id, NODE_MANAGER.id))}
    )
    hub_device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert node_device is not None
    assert node_device.name == NODE_MANAGER.hostname
    assert node_device.sw_version == NODE_MANAGER.engine_version
    assert node_device.via_device_id == hub_device.id


async def test_new_node_gets_a_sensor_without_reload(hass: HomeAssistant) -> None:
    """A node that appears on a later poll gets a sensor without a reload."""
    entry = _entry(hass)
    mock_get_summary = AsyncMock(return_value=SUMMARY)

    with patch(
        "custom_components.docker_swarm_monitor.api.DockerSwarmClient.async_get_summary",
        mock_get_summary,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        unique_id = f"{entry.entry_id}_node_{NODE_MANAGER.id}_tasks_running"
        assert registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None

        mock_get_summary.return_value = replace(SUMMARY, nodes=(NODE_MANAGER,))
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        assert registry.async_get_entity_id("sensor", DOMAIN, unique_id) is not None


async def test_removed_node_sensor_stays_registered_but_unavailable(
    hass: HomeAssistant,
) -> None:
    """A node missing from a later poll keeps its entity, now unavailable."""
    entry = _entry(hass)
    mock_get_summary = AsyncMock(return_value=replace(SUMMARY, nodes=(NODE_MANAGER,)))

    with patch(
        "custom_components.docker_swarm_monitor.api.DockerSwarmClient.async_get_summary",
        mock_get_summary,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        unique_id = f"{entry.entry_id}_node_{NODE_MANAGER.id}_tasks_running"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert hass.states.get(entity_id).state == "3"

        mock_get_summary.return_value = replace(SUMMARY, nodes=())
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
        assert registry.async_get_entity_id("sensor", DOMAIN, unique_id) == entity_id


async def test_remove_config_entry_device_requires_node_to_be_gone(
    hass: HomeAssistant,
) -> None:
    """A node device can only be deleted once its node has left the Swarm."""
    entry = _entry(hass)
    summary_with_node = replace(SUMMARY, nodes=(NODE_MANAGER,))

    with patch(
        "custom_components.docker_swarm_monitor.api.DockerSwarmClient.async_get_summary",
        AsyncMock(return_value=summary_with_node),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    node_device = device_registry.async_get_device(
        identifiers={(DOMAIN, node_device_identifier(entry.entry_id, NODE_MANAGER.id))}
    )
    hub_device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert node_device is not None

    assert await async_remove_config_entry_device(hass, entry, node_device) is False
    assert await async_remove_config_entry_device(hass, entry, hub_device) is False

    entry.runtime_data.data = replace(summary_with_node, nodes=())
    assert await async_remove_config_entry_device(hass, entry, node_device) is True
