"""Tests for Docker Swarm Monitor config flows."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.docker_swarm_monitor.const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
)

URL = "https://swarm.example"


async def test_user_flow(hass: HomeAssistant) -> None:
    """A validated endpoint creates a uniquely identified config entry."""
    with patch(
        "custom_components.docker_swarm_monitor.config_flow._async_validate_input",
        AsyncMock(return_value=URL),
    ) as validate:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_URL: f"{URL}/", CONF_VERIFY_SSL: True},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "swarm.example"
    assert result["data"] == {CONF_URL: URL, CONF_VERIFY_SSL: True}
    assert result["result"].unique_id == URL
    validate.assert_awaited_once()


async def test_duplicate_endpoint_aborts(hass: HomeAssistant) -> None:
    """The normalized endpoint cannot be configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={CONF_URL: URL, CONF_VERIFY_SSL: True},
    ).add_to_hass(hass)

    with patch(
        "custom_components.docker_swarm_monitor.config_flow._async_validate_input",
        AsyncMock(return_value=URL),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_URL: URL, CONF_VERIFY_SSL: True},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_url_shows_error(hass: HomeAssistant) -> None:
    """Invalid endpoint input remains on the setup form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_URL: "not-a-url", CONF_VERIFY_SSL: True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Polling interval can be changed through the options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={CONF_URL: URL, CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 45}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SCAN_INTERVAL: 45}
