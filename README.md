# Docker Swarm Monitor for Home Assistant

A read-only Home Assistant custom integration that reports aggregate health and
workload counts from Docker Swarm. Home Assistant connects to one load-balancer
address in front of Docker Socket Proxy instances running on every manager.

## Features

- Manager quorum and leader monitoring
- Node, service, and current task aggregate counts
- Configurable local polling through the Home Assistant UI
- HTTP and HTTPS endpoint support
- No Docker write operations

## Installation

In HACS, add this repository as a custom integration repository and install
**Docker Swarm Monitor**. For manual installation, copy
`custom_components/docker_swarm_monitor` into the Home Assistant
`custom_components` directory. Restart Home Assistant, then add the integration
under **Settings > Devices & services**.

## Deploy Docker Socket Proxy

Deploy this stack from a manager. It runs one proxy on every manager and enables
only the API groups required by the integration:

```yaml
version: "3.8"

services:
  docker_socket_proxy:
    image: tecnativa/docker-socket-proxy:latest
    environment:
      AUTH: 0
      CONTAINERS: 0
      EVENTS: 0
      EXEC: 0
      INFO: 0
      NODES: 1
      PING: 1
      POST: 0
      SECRETS: 0
      SERVICES: 1
      SWARM: 0
      TASKS: 1
      VERSION: 1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    ports:
      - target: 2375
        published: 2375
        protocol: tcp
        mode: host
    deploy:
      mode: global
      placement:
        constraints:
          - node.role == manager
```

```shell
docker stack deploy --compose-file docker-socket-proxy.yml docker_api
```

Put a load balancer or stable DNS endpoint in front of the manager addresses on
port 2375. It is responsible for manager health checks and failover. Configure
that single endpoint in Home Assistant.

## Security

Docker Socket Proxy serves plain HTTP and has no native TLS support. Keep port
2375 on a trusted, firewalled network. To use HTTPS, terminate TLS at the load
balancer or reverse proxy. Never expose the proxy directly to the internet.

The integration deliberately avoids `/swarm`, whose inspect response can expose
manager and worker join tokens. `POST`, `AUTH`, `SECRETS`, `EXEC`, and unused API
groups remain disabled.

## Configuration

Enter the HTTP or HTTPS load-balancer URL and choose whether Home Assistant
should verify its TLS certificate. The endpoint must provide `/_ping`,
`/version`, `/nodes`, `/services`, and `/tasks`. Docker API 1.25 or newer is
required.

Polling defaults to 30 seconds and can be changed in the integration options;
the minimum is 10 seconds. Use **Reconfigure** to change the endpoint or TLS
verification setting.

## Entities and Health

One Home Assistant device represents the Swarm. It contains a health binary
sensor and counts for:

- Nodes total, ready, and not ready
- Managers total and reachable
- Services total, healthy, and degraded
- Current tasks running, transitional, and failed

Health is on only when a manager majority is reachable, exactly one leader is
reported, every node is ready, and every service has fulfilled its observable
desired workload. On polling failure, entities become unavailable instead of
reporting an unhealthy Swarm.

Historical tasks whose desired state is `shutdown` are ignored. Replicated
services must meet their desired replica count without a failed current task.
All observable tasks for a global service must be running. Docker placement
constraints are not reproduced, so a global service with no task is degraded.

## Troubleshooting

- **Forbidden endpoint**: enable `NODES`, `SERVICES`, `TASKS`, `VERSION`, and
  `PING` on every proxy.
- **Not a manager**: target only manager nodes and mount each manager's local
  Docker socket.
- **TLS verification failed**: use a certificate trusted by Home Assistant.
- **Entities unavailable**: verify the load balancer has a healthy manager
  target.

The first three requests should return `200`; sensitive and write requests
should return `403`:

```shell
curl http://swarm.example:2375/_ping
curl http://swarm.example:2375/version
curl http://swarm.example:2375/nodes
curl -i http://swarm.example:2375/swarm
curl -i -X POST http://swarm.example:2375/services/create
```
