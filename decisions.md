# Technical decisions

The final design choices below were made from observed failures, validation results and
the requirements of the assessment. Where a choice is suitable for this lab but would
need stronger controls in production, that limitation is stated explicitly.

## Decision 1 - Use a pinned slim Python image and non-root application user

- Choice: Build the Flask application from a pinned `python:3.12-slim-bookworm` image
  digest, run it with Gunicorn, and execute the application as UID/GID 10001 instead of
  root.
- Why: The image is small, reproducible at the selected digest, compatible with the
  Python/PostgreSQL dependencies, and the non-root user reduces the impact of an
  application compromise.
- Alternative: Use an unpinned Python tag, a larger Debian image, Alpine, or run the
  application as root.
- Trade-off: Digest pinning improves reproducibility but requires deliberate dependency
  updates. A slim image has fewer debugging utilities available inside the container.
- Evidence / commit: `990a8b9` (`fix: harden container runtime and persistence`).
  Runtime verification showed both application containers running as UID 10001.
- Production improvement: Generate an SBOM, scan the image in CI, automate digest
  updates, and use a registry with signed/provenance-verified images.

## Decision 2 - Separate liveness from dependency readiness

- Choice: `/health` is a liveness check that only proves the application process can
  respond. `/ready` verifies PostgreSQL and Redis and returns 503 when dependencies are
  unavailable.
- Why: A dependency outage should make the service not ready without incorrectly
  implying that the application process itself is dead. This matches the application
  contract and makes diagnosis clearer.
- Alternative: Use one endpoint that checks everything for both liveness and readiness.
- Trade-off: Two health concepts require more explicit monitoring and documentation, but
  avoid restart loops caused by treating dependency failure as process failure.
- Evidence / commit: Application/network repair in `0f93158`; runtime validation was
  strengthened in `5a7b54f`.
- Production improvement: Use distinct orchestrator liveness, readiness and startup
  probes with alerting on sustained readiness failures.

## Decision 3 - Use separate frontend and internal backend networks

- Choice: NGINX is attached only to the frontend network; PostgreSQL and Redis are
  attached only to the internal backend network; application containers join both.
- Why: NGINX needs to reach the applications but does not need direct database or Redis
  access. PostgreSQL and Redis also do not need direct host exposure.
- Alternative: Put every service on one shared Docker network.
- Trade-off: Segmentation is slightly more complex to configure and inspect, but reduces
  unnecessary service reachability and makes intended communication paths explicit.
- Evidence / commit: `ee66b5f` (`fix: enforce container network isolation and persistence`);
  `validate.py` later verifies exact network membership and that the backend network is
  internal.
- Production improvement: Add network policies/firewall controls, TLS between services,
  and service identities rather than relying only on Docker bridge isolation.

## Decision 4 - Publish only NGINX and bind it to loopback

- Choice: Publish only NGINX to the host and bind the published port to `127.0.0.1`.
  Application, PostgreSQL and Redis ports remain container-network-only.
- Why: NGINX is the intended public entry point. Directly publishing application or
  dependency ports would bypass proxy controls and unnecessarily expand the attack
  surface.
- Alternative: Publish every service to the host for convenience.
- Trade-off: Direct host debugging of application/database ports is less convenient;
  debugging instead uses `docker compose exec`, logs and network inspection.
- Evidence / commit: Network hardening in `ee66b5f`; stronger host-port validation in
  `5a7b54f`; hardening verification in `990a8b9`.
- Production improvement: Terminate TLS at a managed ingress/load balancer, enforce
  firewall rules, and keep stateful services on private networks.

## Decision 5 - Retry bounded NGINX upstream failures

- Choice: Configure bounded NGINX failover with short connect/read timeouts,
  `proxy_next_upstream` for connection/timeout/502/503/504 failures, and a limited retry
  count.
- Why: The failure test proved that without retry/failover, stopping one backend caused
  client-visible failures even while another healthy backend was available.
- Alternative: Disable retries and return the first upstream failure directly to the
  client.
- Trade-off: Retries improve availability for transient backend failures but can add
  latency and can amplify load if they are unbounded or used on unsafe operations.
- Evidence / commit: The failed behavior is documented in `e7e97fe`; the bounded
  failover fix is `93c7ed9`.
- Production improvement: Tune retry policy from real latency/error SLOs, use active
  health/load-balancer signals, and be conservative with retries for non-idempotent
  requests.

## Decision 6 - Persist PostgreSQL and Redis with named volumes

- Choice: Use named Docker volumes for PostgreSQL data and Redis data, with Redis AOF
  persistence enabled.
- Why: Container recreation must not imply data loss. PostgreSQL records and the Redis
  counter both need to survive container replacement for the assessment.
- Alternative: Store state only in container writable layers or use anonymous volumes.
- Trade-off: Persistent state requires explicit backup, restore and cleanup procedures;
  deleting containers no longer guarantees a clean data state.
- Evidence / commit: `ee66b5f` added persistence/network isolation; backup and restore
  workflow was added in `319726e`. Persistence was verified through container
  recreation.
- Production improvement: Use managed/stateful storage with scheduled encrypted
  backups, retention policies, restore drills and off-host replication.

## Decision 7 - Apply restart and resource limits to every service

- Choice: Configure `restart: unless-stopped` plus explicit memory, CPU and PID limits
  for NGINX, applications, PostgreSQL and Redis.
- Why: Restart policy improves recovery from process/container exits, while resource
  limits reduce the chance that one service can consume all host resources.
- Alternative: Leave restart and resource behavior at Docker defaults.
- Trade-off: Tight limits can cause throttling or OOM/process failures if chosen without
  workload measurements. Restart policy also does not repair dependency/configuration
  faults.
- Evidence / commit: Resource/restart hardening is in `990a8b9` and was verified against
  the running containers.
- Production improvement: Size resources from observed metrics, configure reservations
  and autoscaling where appropriate, and alert on throttling, OOM events and restart
  loops.

## Assumptions and limits

This is a single-host Docker Compose assessment environment, not a production
high-availability deployment. NGINX, PostgreSQL, Redis and the Docker host are still
single points of failure. The application tier can tolerate an individual backend
failure, but the stateful services and proxy would require replication/failover in a
production design.
