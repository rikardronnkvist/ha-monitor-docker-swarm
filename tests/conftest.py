"""Shared fixtures for Docker Swarm Monitor tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations,
) -> None:
    """Enable loading custom integrations in all tests."""
