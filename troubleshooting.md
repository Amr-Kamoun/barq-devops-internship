# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.


## Entry 1 - Initial runtime investigation - 2026-09-23T08:27:40+03:00

- Symptom:
  The Compose stack built and all five containers started, but requests to
  http://127.0.0.1:8080 failed with "Recv failure: Connection reset by peer".
  app-01 and app-02 later became unhealthy.

- Hypothesis:
  The public NGINX port mapping may not match the port NGINX actually listens on.
  Separately, the application health check and inter-container Flask binding may
  also be misconfigured.

- Command or test:
  `docker port nginx`
  `docker exec nginx nginx -T`
  `docker exec nginx wget -S -O- http://127.0.0.1:80/`
  `docker exec app-01 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).status)"`
  `docker exec app-02 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).status)"`
  `docker exec nginx sh -c 'wget -S -O- http://app-01:8081/ 2>&1 || true'`
  `docker exec nginx sh -c 'wget -S -O- http://app-01:8080/ 2>&1 || true'`
  `docker exec nginx sh -c 'wget -S -O- http://app-02:8080/ 2>&1 || true'`
  `docker compose -p barq-assessment ps -a`

- Actual output:
  Docker publishes nginx container port 81 to host 127.0.0.1:8080.
  The loaded NGINX configuration listens on port 80.
  Direct access to NGINX port 80 from inside its container returns HTTP 502.
  Both Flask containers return HTTP 200 for /health through their own
  127.0.0.1:8080 interface.
  From the NGINX container, app-01:8081, app-01:8080 and app-02:8080 all
  refuse connections.
  Both application containers are reported unhealthy.

- Failed attempt and what changed your thinking:
  Bypassing the host port mapping and calling NGINX directly on port 80 changed
  the symptom from a connection reset to HTTP 502. This showed that NGINX itself
  was running and exposed a separate upstream connectivity problem.

- Root cause:
  Multiple independent configuration problems are present:
  1. Docker publishes host port 8080 to NGINX container port 81 while NGINX listens on 80.
  2. The application health check requests /healthz, but the application provides /health.
  3. Flask binds to 127.0.0.1:8080, so it works inside its own container but is unavailable over the Docker network.
  4. NGINX configures app-01 on port 8081 although the application runs on 8080.

- Fix:
  Not applied yet. Issues will be repaired and retested individually.

- Retest evidence:
  Pending.

- Related commit:
  Pending.

- Remaining uncertainty:
  PostgreSQL and Redis connectivity through /ready has not yet been tested successfully
  because the public proxy path and application network reachability fail first.
