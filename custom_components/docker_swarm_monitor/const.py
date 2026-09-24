"""Constants for Docker Swarm Monitor."""

from typing import Final

DOMAIN: Final = "docker_swarm_monitor"

CONF_URL: Final = "url"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
REQUEST_TIMEOUT: Final = 10

PLATFORMS: Final = ["binary_sensor", "sensor"]
