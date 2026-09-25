# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts

I treated the supplied logs as immutable evidence. I recorded hashes and line counts,
then parsed the JSONL access/application logs and the plaintext NGINX error log.

Commands used included:

    sha256sum logs/access.log logs/error.log logs/application.log
    wc -l logs/access.log logs/error.log logs/application.log
    head -n 8 logs/access.log
    tail -n 8 logs/access.log
    head -n 8 logs/error.log
    tail -n 8 logs/error.log
    head -n 8 logs/application.log
    tail -n 8 logs/application.log

The analysis scripts parsed JSON without rewriting the source files, grouped access
records by request_id, counted exact duplicate raw lines, correlated request IDs across
all three logs, and calculated latency from deduplicated client-facing access records.

For p95 I used the nearest-rank method:

    rank = ceil(0.95 * N)
    p95 = sorted_samples[rank - 1]

With N=720, the p95 rank is 684.

## Results

### 1. UTC interval and file quality

Overall supplied-log interval:

    2026-08-20T11:00:00.015Z -> 2026-08-20T11:30:00Z

Per-file intervals:

    access:      2026-08-20T11:00:00.015Z -> 2026-08-20T11:29:57.578Z
    application: 2026-08-20T11:00:00.015Z -> 2026-08-20T11:29:57.578Z
    error:       2026-08-20T11:05:02Z     -> 2026-08-20T11:30:00Z

| File | Raw lines | Valid | Malformed | Exact duplicate extra lines |
|---|---:|---:|---:|---:|
| `access.log` | 726 | 725 | 1 | 5 |
| `application.log` | 730 | 729 | 1 | 2 |
| `error.log` | 68 | 68 | 0 | 0 |

The malformed records are truncated JSON: access line 311 and application line 401.
They were preserved and counted as malformed rather than repaired.

### 2. Distinct client requests and deduplication

There are 720 distinct client requests.

The valid access log contains 725 records but only 720 unique request IDs. Five request
IDs are duplicated exactly:

- `lab-000121`
- `lab-000241`
- `lab-000361`
- `lab-000481`
- `lab-000601`

I deduplicated client requests by `request_id` and used one final access record per
request ID for client-facing counts.

Retries were not counted as extra client requests. A retried access record can contain
multiple upstream attempts in the same record, for example:

    upstream=172.23.0.12:8080, 172.23.0.11:8080
    upstream_status=502, 200

That is one client request with two proxy upstream attempts, not two client requests.

The application log also contains multiple events for some request IDs. In particular,
a `dependency_error` event and its corresponding `http_request` event belong to the
same client request. These were correlated rather than counted as separate requests.

### 3. Final client status counts and error rate

Using 720 distinct client requests as the denominator:

| Final client status | Count |
|---|---:|
| 200 | 615 |
| 404 | 10 |
| 502 | 40 |
| 503 | 47 |
| 504 | 8 |
| **Total** | **720** |

All HTTP statuses >=400:

    105 / 720 = 14.58%

The 10 HTTP 404 responses are all deliberate requests to `/missing`.

Considering only incident-related 502/503/504 responses:

    95 / 720 = 13.19%

### 4. Failure paths, windows and backends

HTTP 502:

    window: 2026-08-20T11:05:02.503Z -> 2026-08-20T11:09:57.503Z
    backend: 172.23.0.12:8080 only
    count: 40
    paths:
      /         10
      /counter  10
      /health   10
      /records  10

HTTP 503:

    window: 2026-08-20T11:12:09.525Z -> 2026-08-20T11:21:45.041Z
    count: 47
    upstream distribution:
      172.23.0.11:8080  23
      172.23.0.12:8080  24
    paths:
      /counter  16
      /ready    23
      /records   8

These 47 responses divide exactly into:
- 31 Redis TimeoutError dependency failures
- 16 PostgreSQL InvalidPassword dependency failures

HTTP 504:

    window: 2026-08-20T11:25:14.501Z -> 2026-08-20T11:26:47.001Z
    count: 8
    path: /records only
    upstream distribution:
      172.23.0.11:8080  4
      172.23.0.12:8080  4

### 5. Median and p95 client latency

Latency was calculated from the 720 deduplicated access-log requests.

Units: milliseconds.

    median = 54.000 ms
    p95    = 2001.000 ms

The p95 uses nearest-rank:

    ceil(0.95 * 720) = 684

so p95 is the 684th value in the sorted latency sample.

### 6. Upstream retries

There were 19 retried client requests and all 19 ultimately succeeded.

Retry request IDs:

    lab-000124 lab-000130 lab-000136 lab-000142 lab-000148
    lab-000154 lab-000160 lab-000166 lab-000172 lab-000178
    lab-000184 lab-000190 lab-000196 lab-000202 lab-000208
    lab-000214 lab-000220 lab-000226 lab-000232

Each initially attempted `172.23.0.12:8080`, received a connection failure/502 upstream
result, retried `172.23.0.11:8080`, and ultimately returned HTTP 200 to the client.

## Timeline and correlated examples

### 7. Incident timeline

#### 11:05:02-11:09:57 UTC — one application backend unreachable

The NGINX error log contains 59 `connect() failed (111: Connection refused)` events.
All 59 target:

    172.23.0.12:8080

Cross-log correlation shows:

- 40 requests ended as client-visible HTTP 502.
- 19 were retried to `172.23.0.11:8080` and returned HTTP 200.
- The 40 failed request IDs are absent from the application log, consistent with the
  proxy being unable to establish a connection to that application backend.

This is a proxy/connectivity/backend-availability failure.

#### 11:12:09-11:15:52 UTC — Redis timeouts

The application log contains 31 dependency errors:

    dependency=redis
    error_type=TimeoutError

They affect both `app-01` and `app-02`.

The same 31 request IDs correlate to HTTP 503 responses:

- `/counter`: 16
- `/ready`: 15

This is an application dependency incident rather than a single application-backend
connectivity failure.

#### 11:20:07-11:21:45 UTC — PostgreSQL authentication failures

The application log contains 16 dependency errors:

    dependency=postgres
    error_type=InvalidPassword

They affect both application instances.

The same 16 request IDs correlate to HTTP 503 responses:

- `/ready`: 8
- `/records`: 8

This indicates a shared PostgreSQL credential/configuration problem.

#### 11:25:14-11:26:47 UTC — `/records` upstream timeouts

NGINX records eight:

    upstream timed out (110: Operation timed out)

All eight requests are for `/records`.

Four target each backend, so this incident is not isolated to one application instance.
All eight final client responses are HTTP 504 with access-log request times of about
2.001 seconds.

### 8. Correlated failed and successful requests

#### Failed request: `lab-000122`

Access log:

    timestamp=2026-08-20T11:05:02.503Z
    request_id=lab-000122
    GET /health
    status=502
    upstream=172.23.0.12:8080
    upstream_status=502
    request_time=0.003

NGINX error log at `2026/08/20 11:05:02`:

    connect() failed (111: Connection refused)
    request_id=lab-000122
    upstream=http://172.23.0.12:8080/health

There is no corresponding application request event, which is consistent with NGINX
failing before it could connect to the backend.

#### Successful request after retry: `lab-000124`

Access log:

    timestamp=2026-08-20T11:05:07.620Z
    request_id=lab-000124
    GET /ready
    status=200
    upstream=172.23.0.12:8080, 172.23.0.11:8080
    upstream_status=502, 200
    request_time=0.12

NGINX error log at `2026/08/20 11:05:07` first records:

    connect() failed (111: Connection refused)
    request_id=lab-000124
    upstream=http://172.23.0.12:8080/ready

Application log then records:

    timestamp=2026-08-20T11:05:07.620Z
    request_id=lab-000124
    instance_id=app-01
    path=/ready
    status=200
    duration_ms=120.0

This proves the first upstream attempt failed and the retry to the other application
instance succeeded.

A useful timeout example is `lab-000606`: the client received HTTP 504 after roughly
2.001 seconds, while the application later logged the same request as HTTP 200 after
2700 ms. This shows that eventual application completion does not change the response
already returned by the proxy to the client.

## Conclusions and limits

### 9. Proxy/connectivity versus dependency/application failures

The first incident is a proxy/connectivity or backend-availability problem.

Evidence:

- NGINX logs 59 `connect() failed (111: Connection refused)` events.
- Every refused connection targets `172.23.0.12:8080`.
- 40 affected requests return HTTP 502 to clients.
- 19 affected requests are retried to `172.23.0.11:8080` and return HTTP 200.
- The 40 client-visible 502 request IDs have no corresponding application request
  event, consistent with NGINX failing before reaching the application.

The Redis and PostgreSQL incidents are dependency/application failures.

Redis evidence:

    dependency=redis
    error_type=TimeoutError
    events=31
    correlated final client status=503

The same failures occur on both application instances, so they are not isolated to one
application backend.

PostgreSQL evidence:

    dependency=postgres
    error_type=InvalidPassword
    events=16
    correlated final client status=503

Again, both application instances are affected. This supports a shared dependency or
runtime configuration problem rather than loss of connectivity to one application
container.

The later HTTP 504 incident is different from both categories above. NGINX successfully
reaches both application backends but times out waiting for `/records` response headers.
All eight affected client requests return HTTP 504.

Request `lab-000606` illustrates this distinction: NGINX returns 504 after approximately
2.001 seconds, but the application later records the same request as status 200 after
2700 ms. The proxy timeout occurred before the application completed its work.

### 10. What the logs do not prove and what to check next

The supplied logs prove observed symptoms and cross-log correlations, but they do not
prove every underlying infrastructure cause.

For the connection-refused incident, the logs do not establish whether the affected
backend was stopped, crashed, restarting, unhealthy, listening on the wrong interface
or port, or unreachable because of networking.

For the Redis incident, the logs establish Redis `TimeoutError` dependency failures but
do not establish whether Redis itself was stopped, overloaded, network-isolated, or
suffering another resource problem.

For PostgreSQL, `InvalidPassword` proves authentication was rejected, but the logs do
not establish which configuration source supplied the incorrect credential or when it
changed.

For the `/records` timeouts, the logs prove that both application backends exceeded the
proxy response timeout, but they do not identify whether the delay originated in the
application, PostgreSQL queries or locks, resource exhaustion, connection saturation,
or another downstream operation.

In a running environment I would check:

- container state, health status, restart count and recent restarts;
- NGINX and application live logs around each incident;
- frontend/backend network membership and DNS resolution;
- application listening addresses and ports;
- connectivity to Redis and PostgreSQL from each application container;
- Redis latency and resource state;
- PostgreSQL authentication configuration and the runtime credential source;
- PostgreSQL query latency, locks, sessions and connection usage;
- application/DB/Redis CPU, memory, process and connection saturation;
- NGINX retry and timeout configuration.

### Integrity verification

After completing the analysis I re-ran:

    sha256sum logs/access.log logs/error.log logs/application.log
    git status --short

The hashes remained:

    f8562d6ee86b7e7aa67e8c3474ca16eca8a1e5f521f78f3808d784be62efa754  logs/access.log
    940588d00bafd6c5c7cad8a4d8a0c39b665d1fd64928d93a5d1f1810c3c6f175  logs/error.log
    483d06cf431faa1d04a7264b015798bcde4bed1ba618f87426e79fb0d5caea05  logs/application.log

The supplied logs were not modified.
