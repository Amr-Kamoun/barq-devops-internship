# AI usage disclosure

AI was used during this assessment as an engineering assistant. I remained responsible
for executing commands, inspecting actual output, deciding whether suggested changes
were appropriate, correcting suggestions when evidence disagreed, and verifying the
final repository and runtime behavior.

## Use 1 - Investigation and troubleshooting guidance

- Tool/model: OpenAI ChatGPT (GPT-5.6 Sol).
- Purpose: Help structure the investigate -> hypothesize -> test -> fix -> retest
  workflow and suggest diagnostic commands for Docker, Compose, NGINX, Flask,
  PostgreSQL, Redis and networking.
- Files or decisions affected: `troubleshooting.md`, Docker/Compose/NGINX configuration,
  and the sequence of investigation commits.
- What you changed or rejected: Suggestions were not treated as evidence. Commands were
  run against the actual environment and changes were made only after observing their
  output. Failed approaches, including the initial backend-failover behavior, were kept
  in the troubleshooting record rather than hidden.
- How you independently verified it: Used `docker compose ps`, container logs,
  `curl`, Docker network/container inspection, endpoint checks, persistence tests,
  `validate.py`, `failure_test.py`, and Git diffs after each change.
- Related commit: Investigation/fix sequence including `fb571bf`, `0f93158`,
  `a6460ce`, `ee66b5f`, `93c7ed9`, and `5a7b54f`.

## Use 2 - Validation, failure-test and CI review

- Tool/model: OpenAI ChatGPT (GPT-5.6 Sol).
- Purpose: Review validation coverage, bounded-wait behavior, failure-test logic and the
  GitHub Actions integration workflow.
- Files or decisions affected: `validate.py`, `failure_test.py`,
  `.github/workflows/ci.yml`, and related documentation.
- What you changed or rejected: Validation was strengthened after runtime testing showed
  that a first version of the failure test could return success even when client
  requests failed during a backend outage. The test was changed to require both
  continued availability and proof that the recovered backend served traffic.
- How you independently verified it: Ran the scripts locally and checked their exit
  codes, stopped/restarted a real backend, inspected NGINX behavior, and verified the
  GitHub Actions run completed successfully with `VALIDATION PASSED`.
- Related commit: `9b58339`, `93c7ed9`, `5a7b54f`, `b2a92c8`.

## Use 3 - Historical log analysis

- Tool/model: OpenAI ChatGPT (GPT-5.6 Sol).
- Purpose: Help design read-only parsing/correlation scripts for the three supplied
  historical logs and organize the final report.
- Files or decisions affected: `log_analysis.md`.
- What you changed or rejected: An initial suggested regular expression incorrectly
  reported zero request IDs in `error.log`. I detected the contradiction against the
  source lines, corrected the parser, reran the analysis, and used only the corrected
  results. Temporary analysis scripts remained outside the repository.
- How you independently verified it: Recomputed counts from the original files,
  correlated exact request IDs across access/error/application logs, checked duplicate
  handling and percentile calculations, and re-ran SHA-256 hashes afterward to prove
  that the supplied logs were unchanged.
- Related commit: `a279e92`.

## Use 4 - Documentation drafting and review

- Tool/model: OpenAI ChatGPT (GPT-5.6 Sol).
- Purpose: Help organize technical decisions, security findings, README content and
  evidence-oriented explanations against the assessment requirements.
- Files or decisions affected: `decisions.md`, `security_review.md`, `AI_USAGE.md`, and
  later README/evidence documentation.
- What you changed or rejected: Draft text was checked against actual repository
  configuration, commit history and runtime evidence. Claims without observed evidence
  were not accepted as proof, and documentation was adjusted when shell formatting or
  repository state did not match the suggestion.
- How you independently verified it: Used `git diff --check`, inspected relevant files
  and commits, reran validation/runtime checks, verified GitHub Actions output, and
  compared documentation against `assessment/TASK.md` and
  `assessment/APPLICATION.md`.
- Related commit: Documentation commits including `e7e97fe`, `a279e92`, and the final
  documentation commit on this branch.

## Verification principle

AI-generated suggestions were treated as hypotheses or drafts, not as authoritative
evidence. Final conclusions were based on commands executed in the assessment
environment, source-controlled diffs, runtime behavior, original-log analysis and CI
results. The recorded video will independently demonstrate the final system and required
live changes.
