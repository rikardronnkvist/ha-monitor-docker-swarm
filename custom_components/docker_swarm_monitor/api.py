"""Asynchronous client for a Docker Socket Proxy."""

import asyncio
import json
import ssl
from collections.abc import Mapping
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

import aiohttp

from .const import REQUEST_TIMEOUT
from .models import SwarmSummary, build_summary

MINIMUM_API_VERSION = (1, 25)


class DockerSwarmError(Exception):
    """Base exception for Docker Swarm client failures."""


class InvalidUrlError(DockerSwarmError):
    """The proxy URL is invalid or unsupported."""


class CannotConnectError(DockerSwarmError):
    """The proxy could not be reached before the timeout."""


class TlsError(DockerSwarmError):
    """TLS verification or negotiation failed."""


class ForbiddenError(DockerSwarmError):
    """The proxy denied a required endpoint."""


class InvalidResponseError(DockerSwarmError):
    """The proxy returned an invalid Docker API response."""


class UnsupportedApiVersionError(DockerSwarmError):
    """The Docker API is too old for Swarm monitoring."""


class NotManagerError(DockerSwarmError):
    """The endpoint does not expose a Swarm manager."""


def normalize_url(value: str) -> str:
    """Validate and normalize an HTTP proxy base URL."""
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as err:
        raise InvalidUrlError from err

    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise InvalidUrlError

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        hostname = f"{hostname}:{port}"

    path = parsed.path.rstrip("/")
    return urlunsplit(SplitResult(scheme, hostname, path, "", ""))


class DockerSwarmClient:
    """Read aggregate state from a Docker Socket Proxy."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        *,
        verify_ssl: bool,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self.base_url = normalize_url(base_url)
        self._ssl = verify_ssl

    async def async_get_summary(self) -> SwarmSummary:
        """Validate the proxy and return current aggregate Swarm state."""
        ping, version_data = await asyncio.gather(
            self._request_text("/_ping"), self._request_json("/version")
        )
        if ping.strip().upper() != "OK":
            raise InvalidResponseError("Docker ping did not return OK")

        api_version = version_data.get("ApiVersion")
        if not isinstance(api_version, str):
            raise InvalidResponseError("Docker version response has no ApiVersion")
        if _parse_api_version(api_version) < MINIMUM_API_VERSION:
            raise UnsupportedApiVersionError(api_version)

        prefix = f"/v{api_version}"
        nodes, services, tasks = await asyncio.gather(
            self._request_list(f"{prefix}/nodes"),
            self._request_list(f"{prefix}/services"),
            self._request_list(f"{prefix}/tasks"),
        )
        if not any(_nested(node, "Spec", "Role") == "manager" for node in nodes):
            raise NotManagerError

        return build_summary(api_version, nodes, services, tasks)

    async def _request_list(self, path: str) -> list[Mapping[str, Any]]:
        data = await self._request_json(path)
        if not isinstance(data, list) or not all(
            isinstance(item, Mapping) for item in data
        ):
            raise InvalidResponseError(f"Expected a list from {path}")
        return data

    async def _request_json(self, path: str) -> Any:
        response_text = await self._request_text(path)
        try:
            return json.loads(response_text)
        except (json.JSONDecodeError, TypeError) as err:
            raise InvalidResponseError(f"Invalid JSON from {path}") from err

    async def _request_text(self, path: str) -> str:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    f"{self.base_url}{path}", ssl=self._ssl
                ) as response:
                    body = await response.text()
                    if response.status in {401, 403}:
                        raise ForbiddenError(path)
                    if response.status in {400, 404, 406, 503} and path.endswith(
                        ("/nodes", "/services", "/tasks")
                    ):
                        raise NotManagerError(path)
                    if response.status < 200 or response.status >= 300:
                        raise InvalidResponseError(
                            f"Docker API returned HTTP {response.status} for {path}"
                        )
                    return body
        except TimeoutError as err:
            raise CannotConnectError("Request timed out") from err
        except (
            aiohttp.ClientConnectorCertificateError,
            aiohttp.ClientSSLError,
            ssl.SSLError,
        ) as err:
            raise TlsError from err
        except aiohttp.ClientError as err:
            raise CannotConnectError from err


def _parse_api_version(value: str) -> tuple[int, int]:
    try:
        major, minor = value.split(".", maxsplit=1)
        return int(major), int(minor)
    except (TypeError, ValueError) as err:
        raise InvalidResponseError("Invalid Docker API version") from err


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current
