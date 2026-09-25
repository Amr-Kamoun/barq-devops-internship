# Security and production-readiness review

This review covers the current assessment solution. Implemented controls are separated
from production follow-up work. The environment is a local Docker Compose lab and is not
presented as a production-ready high-availability deployment.

## Finding 1 - Secrets must not be stored in tracked configuration

- Risk and evidence: The starter configuration contained credential-like values in
  configuration. The current solution removes the active database password from tracked
  Compose/application configuration and uses an ignored local `.env`. Safe placeholders
  are provided in `.env.example`.
- Impact: A committed credential can be recovered from source control, copied into
  images or logs, and reused by anyone with repository access.
- Implemented fix / commit: `4f4cc7c` stopped tracking local environment credentials;
  `990a8b9` further hardened the runtime configuration and added the safe root
  `.env.example`.
- Production follow-up: Treat any historically exposed credential as compromised and
  rotate it. Use a dedicated secrets manager or orchestrator secret mechanism instead
  of long-lived plaintext environment files.
- How to verify: Run `git status --ignored`, `git check-ignore .env config/app.env`,
  inspect `.env.example`, and confirm current tracked files contain only placeholders,
  not the local secret value.

## Finding 2 - Runtime environment variables still expose secrets to privileged operators

- Risk and evidence: `DATABASE_URL` is supplied to application containers through the
  runtime environment. Although the secret is not committed to source control, a user
  with Docker daemon access can inspect container environment values.
- Impact: Compromise of the Docker daemon or excessive local operator privileges can
  expose database credentials.
- Implemented fix / commit: Current source-controlled configuration references an
  external `POSTGRES_PASSWORD` instead of embedding the password directly. This is
  implemented in `990a8b9`.
- Production follow-up: Use a secrets manager, short-lived credentials, workload
  identity where possible, and restrict access to the container runtime API.
- How to verify: Inspect `docker-compose.yml` and confirm no literal production password
  is present. Confirm `.env` is ignored and has restrictive local permissions.

## Finding 3 - Only NGINX should publish a host port

- Risk and evidence: Publishing Flask, PostgreSQL or Redis directly to the host would
  bypass the intended proxy path and unnecessarily increase attack surface.
- Impact: Direct database/cache exposure can enable unauthorized access; direct app
  exposure can bypass NGINX routing and controls.
- Implemented fix / commit: `ee66b5f` removed prohibited host-port exposure and
  `5a7b54f` added validation that only NGINX publishes the expected loopback-bound port.
- Production follow-up: Use a controlled ingress/load balancer with TLS and host/network
  firewall policy. Stateful services should remain private.
- How to verify: Run `docker compose ps`, `docker inspect` on all five services, or
  `python3 validate.py`. Validation must fail if a non-NGINX service publishes a port.

## Finding 4 - Backend services require network isolation

- Risk and evidence: A single flat network would allow NGINX to reach PostgreSQL and
  Redis even though the proxy has no reason to communicate with either service.
- Impact: A compromised proxy would gain unnecessary network reachability to stateful
  services, increasing lateral-movement opportunities.
- Implemented fix / commit: `ee66b5f` created frontend/backend separation. NGINX is
  frontend-only, PostgreSQL and Redis are backend-only, and application containers
  bridge the two networks. The backend network is internal.
- Production follow-up: Add enforceable network policies, firewall rules, service
  identity and encrypted service-to-service communication.
- How to verify: Run `python3 validate.py` and inspect
  `docker network inspect barq-assessment_frontend` and
  `docker network inspect barq-assessment_backend`.

## Finding 5 - Application containers should not run as root

- Risk and evidence: Running the Flask application as root would increase the impact of
  an application or dependency compromise.
- Impact: A successful exploit could gain unnecessary privileges inside the container
  and make container breakout weaknesses more damaging.
- Implemented fix / commit: `990a8b9` creates a dedicated application UID/GID 10001 and
  sets `USER app` in the Dockerfile. Both application containers were runtime-verified
  as UID 10001.
- Production follow-up: Also use a read-only root filesystem where possible, drop Linux
  capabilities, apply `no-new-privileges`, and use seccomp/AppArmor or equivalent
  controls.
- How to verify: Run:
  `docker compose exec -T app-01 id -u`
  and
  `docker compose exec -T app-02 id -u`.
  Both should return `10001`.

## Finding 6 - Base/container images require controlled selection and updates

- Risk and evidence: Mutable image tags can silently change, while old pinned images can
  accumulate known vulnerabilities if never updated.
- Impact: Unreviewed image changes hurt reproducibility; stale images create supply-chain
  and vulnerability risk.
- Implemented fix / commit: `990a8b9` pins the Python base image by digest, and the
  Compose services use controlled image references rather than arbitrary latest images.
- Production follow-up: Generate SBOMs, scan images in CI, verify signatures/provenance,
  define an image-update process, and regularly refresh pinned digests after testing.
- How to verify: Inspect `Dockerfile` and `docker-compose.yml` and confirm controlled
  image references. Rebuild from a clean cache and run validation.

## Finding 7 - Persistent data needs explicit backup and restore procedures

- Risk and evidence: PostgreSQL and Redis state would be lost if it lived only in
  container writable layers. Persistence alone is also not a backup.
- Impact: Container recreation or storage loss could destroy application records and
  state.
- Implemented fix / commit: `ee66b5f` added named PostgreSQL and Redis volumes with Redis
  AOF persistence. `319726e` implemented PostgreSQL backup and restore scripts, and
  restore behavior was tested.
- Production follow-up: Store encrypted backups off-host, define retention and recovery
  objectives, monitor backup jobs, and perform scheduled restore drills.
- How to verify: Create a PostgreSQL record, recreate containers without deleting
  volumes, and confirm the record remains. Run `backup.sh` and `restore.sh` using a
  disposable test record to prove restore behavior.

## Finding 8 - Resource exhaustion needs containment and monitoring

- Risk and evidence: Containers without CPU, memory or PID constraints can consume
  excessive host resources and affect every service.
- Impact: A runaway process, traffic spike or fork/resource leak could cause broad
  availability failure.
- Implemented fix / commit: `990a8b9` applies memory, CPU and PID limits to NGINX,
  applications, PostgreSQL and Redis and configures `restart: unless-stopped`.
- Production follow-up: Size requests/limits from real usage, alert on OOM kills,
  throttling, PID exhaustion and restart loops, and use autoscaling where appropriate.
- How to verify: Inspect the running container HostConfig values and confirm the expected
  memory, CPU/PID limits and restart policy are present.

## Finding 9 - Application redundancy does not remove infrastructure single points of failure

- Risk and evidence: Two application instances provide app-tier redundancy, but NGINX,
  PostgreSQL, Redis and the single Docker host are still single points of failure.
- Impact: Failure of any of those shared components can make the whole service
  unavailable even if an application container remains healthy.
- Implemented fix / commit: `93c7ed9` adds bounded NGINX backend failover so an
  individual application-container outage is tolerated. `failure_test.py` proves
  availability and recovery for that scenario.
- Production follow-up: Run multiple ingress instances, PostgreSQL replication/failover,
  Redis high availability, multiple worker nodes and a production orchestrator/load
  balancer.
- How to verify: Run `python3 failure_test.py`; then compare that success with the
  architecture and note that stopping NGINX/PostgreSQL/Redis would still affect the
  service.

## Finding 10 - Logging, monitoring and CI provide evidence but not full production detection

- Risk and evidence: Container stdout/stderr and the assessment validation scripts are
  useful for diagnosis, but there is no centralized monitoring, retention, alerting or
  distributed tracing in this local solution. Green CI also tests a short-lived clean
  environment, not long-duration production behavior.
- Impact: Failures, latency growth, capacity problems or security events could go
  unnoticed or lack sufficient retained evidence for incident response.
- Implemented fix / commit: Gunicorn emits access/error logs to container output in
  `990a8b9`; `5a7b54f` strengthens runtime/network validation; `b2a92c8` adds GitHub
  Actions build/start/readiness/validation CI. Historical log correlation is documented
  in `a279e92`.
- Production follow-up: Add centralized structured logs, metrics, alerting, dashboards,
  tracing, audit retention, SLOs and alerts for availability, latency, dependency
  failures and resource pressure.
- How to verify: Run `docker compose logs`, `python3 validate.py`, and inspect a GitHub
  Actions run. Confirm CI fails when validation exits non-zero, while recognizing this
  does not prove long-term availability or performance.

## Additional supply-chain improvement - GitHub Actions pinning

The workflow currently uses major-version references such as `actions/checkout@v4` and
`actions/setup-python@v5`. These are common and convenient, but a stricter production
supply-chain policy would pin Actions to reviewed immutable commit SHAs and use an
automated dependency updater to propose controlled upgrades.

## Finding 11 - Vulnerability scanning identified known image CVEs

- Risk and evidence: An optional Docker Scout scan of both locally built Flask
  application images reported 17 High/Critical vulnerabilities across 5 packages:
  3 Critical and 14 High. The findings were primarily in operating-system packages
  inherited from the pinned Debian-based Python image.
- Impact: Known vulnerable packages can increase exploitability if an affected code
  path is reachable. Pinning an image improves reproducibility but does not mean that
  the pinned image remains secure indefinitely.
- Implemented fix / commit: Added `scripts/security_scan.sh` so the local application
  image can be scanned reproducibly with Docker Scout. The default mode reports
  findings; `SCOUT_STRICT=1` can enforce a non-zero exit when vulnerabilities are
  detected.
- Production follow-up: Review Scout base-image recommendations, update the pinned base
  digest after regression testing, generate an SBOM, distinguish reachable/applicable
  findings from inherited but unused packages, and automate regular rescanning.
- How to verify: Build the application image and run
  `./scripts/security_scan.sh`. Run
  `SCOUT_STRICT=1 ./scripts/security_scan.sh` to verify that a vulnerability policy can
  fail when High/Critical findings remain.

## Review summary

Implemented controls currently include secret removal from tracked active configuration,
loopback-only NGINX publication, network segmentation, non-root application execution,
controlled images, persistent storage and tested backup/restore, resource limits,
restart policies, health/readiness checks, bounded backend failover and automated
validation.

Remaining production risks include single-host architecture, single NGINX/PostgreSQL/
Redis instances, runtime environment-secret visibility to privileged Docker operators,
limited runtime hardening beyond the non-root application user, and the absence of
centralized monitoring, alerting and production-grade backup/replication.
