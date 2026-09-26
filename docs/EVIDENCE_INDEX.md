# Evidence and submission index

## Submission references

- Repository URL: https://github.com/Amr-Kamoun/barq-devops-internship
- Starting video commit: `389cb7521ce31cb73ea7594d0ec52e830e0c7786`
- Final functional commit recorded in the video: `86686ace594b2ad9c4c076c6dd7875f407869f58`
- Matching functional CI run: https://github.com/Amr-Kamoun/barq-devops-internship/actions/runs/36202944510
- Continuous video: https://drive.google.com/file/d/16GeA_U9jBhOFGIOosFZAC_OGKD-tnGXb/view?usp=sharing
- Video duration: `13:58`
- Challenge receipt ID: `73de40e9ee064990bc5d4447aea6207d`
- Challenge started UTC: `2026-09-25T23:49:34.225756+00:00`

The commit after `86686ac` is documentation/evidence-only finalization. It updates
README/reporting/evidence files and `architecture.png`; it does not change the runtime
configuration demonstrated in the recording. The repository HEAD submitted with the
assessment is the documentation-only final commit.

## Video evidence timeline

Timestamps are approximate navigation ranges within the continuous 13:58 recording.

| Requirement / evidence | Repository evidence | Commit | Video timestamp |
| --- | --- | --- | --- |
| Clean working tree and starting commit | `git status`, `git rev-parse HEAD` | `389cb75` | `00:00-00:40` |
| Start from stopped environment | `docker compose ps`, `docker compose up --build -d` | `389cb75` | `00:20-01:45` |
| Initial five-service healthy stack | `docker-compose.yml`, `docker compose ps` | `389cb75` | `00:40-01:45` |
| Required HTTP endpoints | `app/app.py` and live `curl` output | existing application/fix history | `01:45-02:45` |
| Both initial backends serve through NGINX | `/instance` output showing `app-01` and `app-02` | `389cb75` starting state | `02:00-02:45` |
| Backend outage availability and recovery | `failure_test.py`, NGINX logs | `93c7ed9`, `5a7b54f` | `02:45-04:00` |
| PostgreSQL persistence across container recreation | named volume in `docker-compose.yml` plus live record proof | `ee66b5f`, `990a8b9` | `04:00-05:30` |
| Automated validation of initial state | `validate.py` | `5a7b54f` | `05:30-06:05` |
| Historical log correlation | `log_analysis.md`, supplied logs | `a279e92` | `06:00-06:30` |
| One-time supplied challenge execution | `video_challenge.sh`, challenge receipt shown live | receipt `73de40e9ee064990bc5d4447aea6207d` | `06:25-06:45` |
| Challenge diagnosis | `docker inspect app-01 app-02 redis` | runtime evidence | `06:40-07:05` |
| Targeted challenge repair | reconnect `app-02` to frontend network | runtime evidence | `07:00-07:20` |
| Live public-port change `8080 -> 8090` | `.env.example`, `docker-compose.yml` | `86686ac` | `07:30-08:30` |
| Live addition of `app-03` | `docker-compose.yml` | `86686ac` | `08:30-10:00` |
| NGINX updated/reloaded with three upstreams | `nginx/nginx.conf`, live `nginx -T` | `86686ac` | `09:30-10:30` |
| All three application identities observed | live `/instance` requests | `86686ac` | `10:00-10:40` |
| Final three-instance validation | `validate.py`, final runtime output | `86686ac` | `10:40-11:35` |
| Review tracked final changes | `git status`, `git diff --check`, `git diff` | `86686ac` | `11:35-12:40` |
| Commit and push live final configuration | Git commit/push output | `86686ac` | `12:40-13:50` |
| Final clean Git state | `git status` | `86686ac` | `13:40-13:58` |

## Final runtime architecture

The final runtime state is:

- NGINX is the only host-facing service.
- Public endpoint: `127.0.0.1:8090`.
- Application backends: `app-01`, `app-02`, `app-03`.
- NGINX is attached only to the frontend network.
- All three Flask applications attach to frontend and internal backend networks.
- PostgreSQL and Redis are backend-only and expose no host ports.
- PostgreSQL and Redis use named persistent volumes.
- `/health` provides application liveness.
- `/ready` checks PostgreSQL and Redis dependency readiness.
- NGINX backend failover is bounded.
- Final automated validation passed with all three application identities observed.

See `architecture.png` and `docs/ARCHITECTURE.md`.

## Supporting repository evidence

- Investigation journal: `troubleshooting.md`
- Historical log analysis: `log_analysis.md`
- Engineering decisions: `decisions.md`
- Security and production-readiness review: `security_review.md`
- AI assistance disclosure: `AI_USAGE.md`
- Automated validator: `validate.py`
- Failure/recovery test: `failure_test.py`
- PostgreSQL backup: `backup.sh`
- PostgreSQL restore: `restore.sh`
- Optional image vulnerability scan: `scripts/security_scan.sh`
- CI workflow: `.github/workflows/ci.yml`
- Final architecture diagram: `architecture.png`

## CI evidence

The recorded live functional commit:

`86686ace594b2ad9c4c076c6dd7875f407869f58`

completed BARQ CI successfully in push run:

https://github.com/Amr-Kamoun/barq-devops-internship/actions/runs/36202944510

That run tested the final runtime configuration containing three application instances
and public port 8090.

The later documentation-only finalization commit should also receive its own CI run.
Its hash and matching CI run are supplied as the repository HEAD in the final
submission.

## Video challenge evidence

The challenge was executed once for the first time in the fresh video working copy.

Receipt:

`73de40e9ee064990bc5d4447aea6207d`

The injected fault removed `app-02` from the frontend network. Live inspection showed
that `app-02` remained running but lacked frontend membership. The repair reconnected
only that missing network.

No full-stack reset was used to repair the challenge.

## Documentation-only finalization

The recorded runtime commit is `86686ac`.

Subsequent changes are limited to:

- synchronizing README text with the recorded final state;
- updating the security and AI-use documentation;
- completing this evidence index;
- adding/updating architecture documentation;
- adding the required root `architecture.png`.

These changes do not alter the final three-instance / port-8090 runtime demonstrated in
the video.
