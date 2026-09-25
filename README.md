<img src="assets/barq-logo.svg" alt="BARQ Systems" width="180">

# BARQ DevOps Internship Assessment

This repository contains my repaired and hardened BARQ assessment environment.

The stack consists of:

- NGINX as the only host-facing entry point
- Flask application instances behind NGINX
- PostgreSQL for persistent records
- Redis for the shared counter
- separate frontend and internal backend Docker networks
- named persistent volumes
- health/readiness checks
- bounded NGINX backend failover
- local validation, failure testing, backup/restore and GitHub Actions CI

The assessment history, investigation and original evidence are preserved rather than
replacing the supplied project.

## Requirements

Use Linux or WSL2 with:

- Git
- Python 3.12
- Docker
- Docker Compose
- `curl`

Docker Desktop on Windows must use Linux containers with WSL integration enabled.

## Configuration

Create the local environment file from the safe example:

    cp .env.example .env
    chmod 600 .env

Review it before starting:

    cat .env.example

Do not commit `.env`.

To load the configured public port into the current shell:

    set -a
    source .env
    set +a

The public service URL is then:

    http://127.0.0.1:${PUBLIC_PORT}

Only NGINX publishes a host port. Flask, PostgreSQL and Redis remain reachable only
through their Docker networks.

## Build

Validate the Compose configuration first:

    docker compose config -q

Build the application image:

    docker compose build

Or explicitly rebuild without using the application build cache:

    docker compose build --no-cache app-01 app-02

## Start

Start the complete environment:

    docker compose up -d

Inspect service state:

    docker compose ps

Follow logs if needed:

    docker compose logs -f

A healthy pre-recording stack contains:

    nginx
    app-01
    app-02
    postgres
    redis

The recorded challenge later requires adding the final third application instance and
changing the public port. Those required live changes are intentionally not performed
early.

## Stop

Stop containers while preserving named volumes:

    docker compose down

Do not add `--volumes` during persistence tests.

## Application endpoints

Load `.env` first:

    set -a
    source .env
    set +a

### Root

    curl -i "http://127.0.0.1:${PUBLIC_PORT}/"

Expected: HTTP 200 with the message and serving `instance_id`.

### Liveness

    curl -i "http://127.0.0.1:${PUBLIC_PORT}/health"

`/health` proves that the application process can respond. It does not check PostgreSQL
or Redis.

### Readiness

    curl -i "http://127.0.0.1:${PUBLIC_PORT}/ready"

`/ready` returns HTTP 200 only while both PostgreSQL and Redis respond. Dependency
failure returns HTTP 503.

### Instance identity

    curl -i "http://127.0.0.1:${PUBLIC_PORT}/instance"

Repeated requests should show traffic reaching the configured application instances:

    for i in $(seq 1 12); do
      curl -s "http://127.0.0.1:${PUBLIC_PORT}/instance"
      echo
    done

### PostgreSQL records

Create a record:

    curl -i \
      -H 'Content-Type: application/json' \
      -d '{"title":"Persistence proof"}' \
      "http://127.0.0.1:${PUBLIC_PORT}/records"

List persisted records:

    curl -s "http://127.0.0.1:${PUBLIC_PORT}/records"
    echo

### Redis counter

    curl -s "http://127.0.0.1:${PUBLIC_PORT}/counter"
    echo

Each request atomically increments the shared Redis counter.

## Validation

Run the complete environment validator:

    python3 validate.py

The validator uses bounded waits and exits non-zero on failure. It verifies:

- Compose/runtime health
- `/ready`
- required endpoints
- PostgreSQL create/list behavior
- all configured application backends observed through NGINX
- exact network membership
- internal backend network
- prohibited host-port exposure
- only NGINX publishing the configured loopback port

Success ends with:

    VALIDATION PASSED

## Backend failure test

Run:

    python3 failure_test.py

The test:

1. discovers the configured application services;
2. stops one backend;
3. sends repeated requests through NGINX;
4. requires continued client availability;
5. restarts the backend;
6. waits for recovery;
7. proves the recovered backend serves traffic again.

Success requires both availability and recovery and exits with status 0.

Do not confuse Docker restart policy with request-level failover. NGINX retry behavior
is what allows another healthy application backend to serve a request when one backend
is unavailable.

## Persistence test

Create a unique record first:

    set -a
    source .env
    set +a

    curl \
      -H 'Content-Type: application/json' \
      -d '{"title":"Container recreation proof"}' \
      "http://127.0.0.1:${PUBLIC_PORT}/records"

Recreate application and PostgreSQL containers without deleting volumes:

    docker compose up -d --force-recreate app-01 app-02 postgres

Wait for health and confirm the record still exists:

    python3 validate.py
    curl -s "http://127.0.0.1:${PUBLIC_PORT}/records"
    echo

The PostgreSQL named volume must preserve the record.

## PostgreSQL backup

Create a timestamped backup using the default `backups/` directory:

    ./backup.sh

The script prints the created backup path on its final line.

For an explicit, easy-to-reference backup filename:

    BACKUP_FILE="backups/barq_tasks_manual.dump"
    ./backup.sh "$BACKUP_FILE"

The script uses `pg_dump` against the running PostgreSQL service and creates a
PostgreSQL custom-format backup. It exits non-zero if the resulting file is empty.

Keep generated backups out of source control.

## PostgreSQL restore

`restore.sh` requires exactly one backup-file argument.

Using the explicit backup created above:

    ./restore.sh "$BACKUP_FILE"

Or with a known backup path:

    ./restore.sh backups/barq_tasks_manual.dump

The restore uses `pg_restore --clean --if-exists --no-owner --exit-on-error`.

The restore workflow was tested by creating data after a backup, restoring the earlier
backup, and confirming that the post-backup data disappeared while the backed-up record
remained.

For production, backups should be encrypted, stored off-host, monitored and restored
regularly in recovery drills.

## CI

GitHub Actions is defined in:

    .github/workflows/ci.yml

The workflow runs on both `push` and `pull_request` and performs:

- repository checkout
- Python/shell/Compose syntax validation
- image build
- stack startup
- bounded readiness wait
- `validate.py`
- diagnostic logs on failure
- cleanup

A green CI run proves that the tested commit built and passed the automated integration
checks in a clean GitHub-hosted runner. It does not prove long-term availability,
production security, capacity, disaster recovery or performance under sustained load.

A verified pre-recording push run completed successfully for commit `b2a92c8`:

    https://github.com/Amr-Kamoun/barq-devops-internship/actions/runs/36171059838

The final submission will reference the CI run matching the final post-video commit.

## Network and request flow

The intended request flow is:

    Client
      |
      | loopback host port from PUBLIC_PORT
      v
    NGINX
      |
      | frontend network
      v
    Flask application instances
      |
      | backend network
      +-----------> PostgreSQL
      |
      +-----------> Redis

NGINX is not attached to the backend network.

PostgreSQL and Redis do not publish host ports.

The application containers are the only services that bridge frontend request handling
to backend dependencies.

## Why the health model is split

`/health` is liveness: the Flask process can answer.

`/ready` is dependency readiness: PostgreSQL and Redis must both respond.

This distinction avoids treating a dependency outage as if the application process
itself had crashed. It also makes dependency failures visible as HTTP 503 while keeping
the liveness signal meaningful.

## Timeouts, retries, restart policy and resources

NGINX uses bounded upstream failover. This was added only after failure testing showed
that stopping one backend produced client-visible failures despite another healthy
backend being available.

Retries are deliberately bounded to avoid uncontrolled retry storms and extra latency.

Services use:

    restart: unless-stopped

Restart policy helps recover from process/container exits but does not repair bad
credentials, broken networking or unhealthy shared dependencies.

CPU, memory and PID limits are configured for all services to reduce the risk of one
container exhausting the host. These lab limits are not production sizing values;
production limits should be based on measured workload and monitoring.

## Investigation summary

The first observed runtime failure was that the expected public endpoint was not
working correctly. Investigation progressively exposed several independent
configuration/runtime problems rather than one fault.

The detailed evidence, hypotheses, failed attempts, fixes and retests are in:

    troubleshooting.md

One important failed attempt was the first backend outage test: stopping `app-01`
produced client failures even though `app-02` remained healthy. The first version of
the failure test also returned success because it checked recovery but did not strictly
require zero client failures during the outage.

That failure led to two improvements:

- bounded NGINX upstream retry/failover;
- a stricter failure test requiring both continued availability and proof of recovery.

## Historical log findings

The supplied historical logs were analyzed without modifying them.

The detailed report is:

    log_analysis.md

After deduplication there were 720 distinct client requests.

The logs reveal separate incident patterns:

- one application backend refused connections;
- Redis dependency timeouts affected both applications;
- PostgreSQL rejected application authentication;
- `/records` later exceeded the NGINX upstream response timeout.

Raw lines were not treated as request counts. Access-log duplicates, retries and
application dependency events sharing a request ID were explicitly accounted for to
avoid double-counting.

## Remaining single points of failure

Application instances provide app-tier redundancy, but this Docker Compose environment
still has several single points of failure:

- one NGINX instance;
- one PostgreSQL instance;
- one Redis instance;
- one Docker host.

A production design would use redundant ingress/load balancers, replicated/failover
PostgreSQL and Redis, multiple worker nodes, production secret management, monitoring
and tested off-host backups.

See `decisions.md` and `security_review.md` for detailed trade-offs and production
follow-ups.

## Optional container vulnerability scan

Docker Scout can be used to scan the locally built application image for known
High/Critical vulnerabilities.

Build the application image first if necessary:

    docker compose build

Run the report-only scan:

    ./scripts/security_scan.sh

Scan another application image explicitly:

    ./scripts/security_scan.sh barq-assessment-app-02:latest

For a policy/enforcement mode where detected vulnerabilities cause a non-zero exit:

    SCOUT_STRICT=1 ./scripts/security_scan.sh

The pre-video scan of both application images found 17 High/Critical vulnerabilities
in 5 packages: 3 Critical and 14 High. Some findings had fixed package versions
available while others were reported without an available fix.

This result is intentionally documented rather than treated as a clean-security result.
A production image-maintenance process should review Docker Scout recommendations,
update the pinned base-image digest after testing, generate an SBOM, and regularly
rescan rebuilt images.

## Security notes

Implemented controls include:

- ignored local secret files and safe examples;
- no literal active database password in tracked Compose/application configuration;
- loopback-only NGINX publication;
- no Flask/PostgreSQL/Redis host ports;
- frontend/backend network separation;
- internal backend network;
- non-root Flask containers;
- pinned/controlled container images;
- CPU, memory and PID limits;
- persistent PostgreSQL and Redis storage;
- tested PostgreSQL backup/restore;
- bounded application-backend failover;
- automated runtime/network validation.

The assessment repository history may contain starter-provided credential-like values.
Historical exposure should be treated as compromised and rotated rather than copied,
published or reused.

## Cleanup

Stop the environment but preserve data:

    docker compose down

To remove only this project's containers and networks while retaining volumes, the same
command is sufficient:

    docker compose down --remove-orphans

Only when persistent assessment data is intentionally no longer needed:

    docker compose down --volumes --remove-orphans

Do not use global commands such as:

    docker system prune -a
    docker volume prune

because they can remove unrelated Docker resources.

## Reports and evidence

- `troubleshooting.md` - investigation journal, failed attempts, fixes and retests
- `log_analysis.md` - three-log correlation and metrics
- `decisions.md` - engineering decisions and trade-offs
- `security_review.md` - security/production-readiness review
- `AI_USAGE.md` - AI assistance and independent verification
- `docs/EVIDENCE_INDEX.md` - final repository/CI/video/challenge evidence
- `docs/ARCHITECTURE.md` - requirements/notes for the final architecture diagram
- `docs/evidence/screenshots/` - supporting terminal evidence

## Final recorded challenge

The supplied `video_challenge.sh` must remain unchanged and must not be run before the
continuous recorded demonstration.

During the recording it will be run once for the first time in that working copy. The
runtime fault it creates must be diagnosed and repaired without using
`docker compose down` as a reset.

The same continuous recording also requires the live public-port change and addition of
a third application instance.

After those live changes, this README, the architecture diagram and evidence index will
be synchronized with the final three-instance / port-8090 repository state.

## AI-assisted work

AI assistance is disclosed in `AI_USAGE.md`.

AI suggestions were treated as hypotheses/drafts rather than evidence. Verification was
performed through actual terminal commands, Git diffs, runtime/container inspection,
endpoint requests, persistence and failure tests, original-log hashes/correlation and
GitHub Actions results.
