"""Config flow for Docker Swarm Monitor."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CannotConnectError,
    DockerSwarmClient,
    ForbiddenError,
    InvalidResponseError,
    InvalidUrlError,
    NotManagerError,
    TlsError,
    UnsupportedApiVersionError,
    normalize_url,
)
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=defaults.get(CONF_URL, "http://")): str,
            vol.Required(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, True)
            ): bool,
        }
    )


async def _async_validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> str:
    url = normalize_url(user_input[CONF_URL])
    client = DockerSwarmClient(
        async_get_clientsession(hass),
        url,
        verify_ssl=user_input[CONF_VERIFY_SSL],
    )
    await client.async_get_summary()
    return url


def _error_key(err: Exception) -> str:
    if isinstance(err, InvalidUrlError):
        return "invalid_url"
    if isinstance(err, TlsError):
        return "invalid_tls"
    if isinstance(err, ForbiddenError):
        return "forbidden"
    if isinstance(err, NotManagerError):
        return "not_manager"
    if isinstance(err, UnsupportedApiVersionError):
        return "unsupported_api_version"
    if isinstance(err, InvalidResponseError):
        return "invalid_response"
    return "cannot_connect"


class DockerSwarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure Docker Swarm Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url = await _async_validate_input(self.hass, user_input)
            except (
                CannotConnectError,
                ForbiddenError,
                InvalidResponseError,
                InvalidUrlError,
                NotManagerError,
                TlsError,
                UnsupportedApiVersionError,
            ) as err:
                errors["base"] = _error_key(err)
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=urlsplit_hostname(url),
                    data={CONF_URL: url, CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]},
                )

        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Change the endpoint settings for an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url = await _async_validate_input(self.hass, user_input)
            except (
                CannotConnectError,
                ForbiddenError,
                InvalidResponseError,
                InvalidUrlError,
                NotManagerError,
                TlsError,
                UnsupportedApiVersionError,
            ) as err:
                errors["base"] = _error_key(err)
            else:
                for existing_entry in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        existing_entry.entry_id != entry.entry_id
                        and existing_entry.unique_id == url
                    ):
                        return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=url,
                    title=urlsplit_hostname(url),
                    data_updates={
                        CONF_URL: url,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return DockerSwarmOptionsFlow()


class DockerSwarmOptionsFlow(config_entries.OptionsFlow):
    """Configure polling options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                }
            ),
        )


def urlsplit_hostname(url: str) -> str:
    """Return the normalized host for a config entry title."""
    from urllib.parse import urlsplit

    return urlsplit(url).hostname or url
