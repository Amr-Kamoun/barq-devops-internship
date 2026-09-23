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


## Entry 2 - Correct NGINX public port mapping - 2026-09-23T08:48:41+03:00

- Symptom:
  Requests to http://127.0.0.1:8080 were reset before receiving an HTTP response.

- Hypothesis:
  Docker was forwarding host port 8080 to a container port where NGINX was not listening.

- Command or test:
  `docker port nginx`
  `docker exec nginx nginx -T`
  `curl -i --max-time 5 http://127.0.0.1:8080/`
  `docker compose -p barq-assessment logs nginx --no-color --tail=30`

- Actual output:
  Before the fix, `docker port nginx` showed
  `81/tcp -> 127.0.0.1:8080`.
  The loaded NGINX configuration showed `listen 80;`.
  After the fix, `docker port nginx` showed
  `80/tcp -> 127.0.0.1:8080`.
  Curl reached NGINX and returned HTTP 502 instead of a connection reset.
  NGINX logged a refused upstream connection to app-01:8081.

- Failed attempt and what changed your thinking:
  Calling NGINX directly inside its container on port 80 returned HTTP 502.
  This proved that NGINX itself was running and that the public port mapping
  was a separate problem from the upstream application connectivity problem.

- Root cause:
  Docker Compose forwarded host port 8080 to NGINX container port 81,
  while the running NGINX process listened on container port 80.

- Fix:
  Changed the NGINX Compose mapping from
  `127.0.0.1:${PUBLIC_PORT:-8080}:81`
  to
  `127.0.0.1:${PUBLIC_PORT:-8080}:80`.

- Retest evidence:
  `docker port nginx` now reports
  `80/tcp -> 127.0.0.1:8080`.
  `curl -i --max-time 5 http://127.0.0.1:8080/`
  now receives an HTTP 502 response from NGINX.
  This confirms that the host-to-NGINX path is repaired and exposes the
  next independent problem between NGINX and the Flask backends.

- Related commit:
  `fb571bf` - fix: publish nginx on its listening port

- Remaining uncertainty:
  NGINX still cannot reach the Flask backends. The application binding
  and NGINX upstream configuration require separate investigation.


## Entry 3 - Fix application networking and NGINX upstream - 2026-09-23T20:00:42+03:00

- Symptom:
  NGINX returned HTTP 502 even though the application containers were healthy.

- Hypothesis:
  NGINX could not reach the Flask containers because of incorrect container networking configuration.

- Command or test:
  `docker exec nginx wget -S -O- http://app-01:8080/`
  `docker exec nginx wget -S -O- http://app-02:8080/`
  `docker exec nginx nginx -T | grep -A5 upstream`

- Actual output:
  Both application containers responded with HTTP 200 when accessed from NGINX.
  The loaded NGINX configuration used app-01:8080 and app-02:8080.

- Root cause:
  Flask was previously bound to 127.0.0.1, preventing Docker network access.
  NGINX also contained an incorrect upstream port for app-01.

- Fix:
  Changed APP_HOST from 127.0.0.1 to 0.0.0.0.
  Changed NGINX upstream app-01 port from 8081 to 8080.
  Recreated the NGINX container to load the new configuration.

- Retest evidence:
  `curl -i http://127.0.0.1:8080/`
  returned HTTP 200 with the application JSON response.

- Related commit:
  Pending.

- Remaining uncertainty:
  Database and Redis dependent endpoints should be tested next.
