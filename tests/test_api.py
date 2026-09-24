"""Tests for the Docker Socket Proxy client."""

import json

import pytest

from custom_components.docker_swarm_monitor.api import (
    DockerSwarmClient,
    ForbiddenError,
    InvalidResponseError,
    InvalidUrlError,
    NotManagerError,
    normalize_url,
)


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def text(self) -> str:
        return self._body


class FakeSession:
    """Route requests to predefined responses."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, bool | None]] = []

    def get(self, url: str, *, ssl: bool | None):
        self.requests.append((url, ssl))
        return self.responses[url]


def _response(data, status: int = 200) -> FakeResponse:
    return FakeResponse(status, data if isinstance(data, str) else json.dumps(data))


def test_normalize_url() -> None:
    """URLs have stable duplicate-detection semantics."""
    assert (
        normalize_url(" HTTPS://Swarm.Example:443/proxy/ ")
        == "https://swarm.example/proxy"
    )
    assert normalize_url("http://[2001:db8::1]:2375/") == "http://[2001:db8::1]:2375"


@pytest.mark.parametrize(
    "url",
    [
        "swarm.example:2375",
        "ftp://swarm.example",
        "http://user:password@swarm.example",
        "http://swarm.example?token=value",
        "http://swarm.example#fragment",
        "http://swarm.example:invalid",
    ],
)
def test_normalize_url_rejects_unsafe_values(url: str) -> None:
    """Unsupported or credential-bearing URLs are rejected."""
    with pytest.raises(InvalidUrlError):
        normalize_url(url)


@pytest.mark.asyncio
async def test_get_summary_uses_negotiated_api_version() -> None:
    """The client validates and concurrently reads all required endpoints."""
    base_url = "https://swarm.example"
    session = FakeSession(
        {
            f"{base_url}/_ping": _response("OK"),
            f"{base_url}/version": _response({"ApiVersion": "1.47"}),
            f"{base_url}/v1.47/nodes": _response(
                [
                    {
                        "Spec": {"Role": "manager"},
                        "Status": {"State": "ready"},
                        "ManagerStatus": {"Reachability": "reachable", "Leader": True},
                    }
                ]
            ),
            f"{base_url}/v1.47/services": _response([]),
            f"{base_url}/v1.47/tasks": _response([]),
        }
    )

    summary = await DockerSwarmClient(
        session, base_url, verify_ssl=True
    ).async_get_summary()

    assert summary.api_version == "1.47"
    assert summary.healthy
    assert {url for url, _ in session.requests} == set(session.responses)
    assert all(verify_ssl is True for _, verify_ssl in session.requests)


@pytest.mark.asyncio
async def test_forbidden_required_endpoint() -> None:
    """A denied proxy route produces a specific configuration error."""
    base_url = "http://swarm.example"
    session = FakeSession(
        {
            f"{base_url}/_ping": _response("OK"),
            f"{base_url}/version": _response({"ApiVersion": "1.47"}),
            f"{base_url}/v1.47/nodes": _response("denied", 403),
            f"{base_url}/v1.47/services": _response([]),
            f"{base_url}/v1.47/tasks": _response([]),
        }
    )

    with pytest.raises(ForbiddenError):
        await DockerSwarmClient(session, base_url, verify_ssl=False).async_get_summary()


@pytest.mark.asyncio
async def test_invalid_json_response() -> None:
    """Malformed Docker JSON is not silently accepted."""
    base_url = "http://swarm.example"
    session = FakeSession(
        {
            f"{base_url}/_ping": _response("OK"),
            f"{base_url}/version": _response("not-json"),
        }
    )

    with pytest.raises(InvalidResponseError):
        await DockerSwarmClient(session, base_url, verify_ssl=False).async_get_summary()


@pytest.mark.asyncio
async def test_endpoint_must_be_a_manager() -> None:
    """A daemon returning no manager node cannot monitor the Swarm."""
    base_url = "http://swarm.example"
    session = FakeSession(
        {
            f"{base_url}/_ping": _response("OK"),
            f"{base_url}/version": _response({"ApiVersion": "1.47"}),
            f"{base_url}/v1.47/nodes": _response([]),
            f"{base_url}/v1.47/services": _response([]),
            f"{base_url}/v1.47/tasks": _response([]),
        }
    )

    with pytest.raises(NotManagerError):
        await DockerSwarmClient(session, base_url, verify_ssl=False).async_get_summary()
