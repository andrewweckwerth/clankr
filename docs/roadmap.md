# Clankr roadmap

This roadmap is ordered around the current system: a Next.js UI, a FastAPI orchestrator, PostgreSQL-backed jobs, MinIO object storage, and specialist processing containers. It favors making the existing workflow understandable and reliable before adding infrastructure that increases operational complexity.

## Product direction

Clankr should feel like a small analysis workspace rather than a form that opens a progress modal. A user should be able to submit work, understand exactly what is happening, return later, inspect results and failures, and trust that the system is healthy and recoverable.

## Priority order

| Phase | Outcome | Priority |
| --- | --- | --- |
| 0 | Define contracts and design the future data model | Now |
| 1 | Implement schema migrations and ownership-ready storage | Next |
| 2 | Add accounts, authentication, and ownership | High |
| 3 | Rework orchestration for reliable processing | High |
| 4 | Add metrics, health, and operational visibility | High |
| 5 | Harden Redis queueing, caching, and events | High |
| 6 | Scale workers and control capacity | Later |
| 7 | Complete the frontend redesign | Last |
| 8 | Stress test, tune, and document results | Final |

## Phase 0 — Contracts and architecture

Before major feature work, establish a stable vocabulary and contract.

- Define canonical job states: `queued`, `running`, `retrying`, `completed`, `failed`, and `cancelled`.
- Replace the current mixture of free-form status strings and stage flags with an explicit state transition model. Keep the existing `raw/`, `preprocessed/`, and `stems/` object-key contracts.
- Add versioned database migrations; `database/init.sql` is currently initialization-only.
- Define an API error shape, request IDs, upload limits, supported file types, and retention rules.
- Add a small test harness for job transitions, stage selection, failed stages, text-only jobs, deduplication, and future authorization boundaries.

Definition of done: the API and UI use the same job vocabulary, state transitions are documented, and a clean install plus an upgrade of an existing database are both repeatable.

## Phase 1 — Schema and migration foundation

Accounts and ownership can remain a future product feature, but the database should not block them or force a second major redesign later.

- Add versioned database migrations and stop treating `database/init.sql` as the upgrade mechanism.
- Normalize job lifecycle data: canonical status/stage values, timestamps, attempt counts, lease/heartbeat fields, error details, and cancellation state.
- Add a future-ready `users`/identity shape and nullable ownership columns or a clear ownership join model for jobs, songs, and stored objects. Do not expose login yet unless it is part of the current product scope.
- Add stage-attempt/history records rather than overwriting all operational detail on the job row.
- Add indexes for queue claims, status, creation time, owner lookup, and deduplication.
- Decide how MinIO object ownership, retention, deletion, and orphan cleanup relate to database records.
- Preserve the existing `raw/`, `preprocessed/`, and `stems/` object-key contracts while the schema evolves.

Definition of done: existing data can be upgraded safely, new jobs have enough lifecycle detail to support retries and metrics, and future ownership can be added without another data-model rewrite.

## Phase 2 — Accounts, authentication, and ownership

Implement this immediately after the schema foundation so all subsequent jobs, metrics, queue entries, objects, and UI flows have an ownership and authorization model.

- Add users, sessions, password-hash storage, account recovery, optional email verification, and logout.
- Prefer a mature identity provider or OIDC integration for production rather than implementing cryptography and recovery flows from scratch.
- Support OAuth/OIDC providers using the provider-neutral identity shape established in Phase 1. “OAuth” is usually the sign-in mechanism; OIDC supplies the identity claims needed by the app.
- Enforce ownership on jobs, songs, and stored objects at the orchestrator boundary.
- Add rate limits, per-user upload/storage quotas, session expiration, CSRF protection where applicable, and audit logging for destructive actions.
- Keep internal service endpoints private; do not rely only on the fact that traffic came through Next.js.

Definition of done: an authenticated user sees only authorized data, can recover access, and cannot access another user’s job, song, or object by changing an ID.

## Phase 3 — Reliable orchestration

Rework the orchestrator before introducing more infrastructure. PostgreSQL-backed claiming is a useful starting point, but the current implementation lacks robust retry, lease, cancellation, and recovery behavior.

- Separate job creation, stage dispatch, stage execution, result persistence, and finalization into explicit transitions.
- Make each stage idempotent so retries or worker restarts cannot corrupt results or create duplicate side effects.
- Add leases/heartbeats and reclaim expired work after worker/container failure.
- Add bounded retries with exponential backoff, classified errors, and a terminal attention/dead-letter state.
- Add cancellation that is safe for queued and active work.
- Add startup reconciliation for jobs left in claimed/running states after an outage.
- Handle duplicate submissions with idempotency keys and fingerprint-aware deduplication.
- Define concurrency limits per stage and prevent expensive GPU/LLM work from starving lightweight jobs.
- Add integration tests for worker crashes, timeouts, duplicate delivery, partial completion, restart recovery, and text-only jobs.

Definition of done: a job either completes, is safely retried, or becomes an actionable failure; a worker can disappear without permanently stranding work.

## Phase 4 — Metrics, health, and operations

Add measurement before scaling so capacity decisions are based on observed behavior.

- Add structured logs with request ID, job ID, stage, attempt, worker identity, and model/version metadata.
- Track queue depth, oldest-job age, throughput, stage latency, total job latency, retry/failure rates, active workers, resource utilization, storage usage, and dependency latency.
- Add stage-level timestamps and attempt history to support accurate duration metrics.
- Separate liveness, readiness, dependency health, and end-to-end pipeline checks.
- Expose an internal health/metrics API for the eventual frontend and operators.
- Add alert thresholds for stuck jobs, queue age, repeated failures, low disk, database saturation, MinIO failures, and model unavailability.
- Add backup/restore verification for PostgreSQL and MinIO.

Definition of done: the team can establish a baseline for normal load and identify whether a problem is in the queue, a worker, a dependency, storage, or the model.

## Phase 5 — Redis-backed queue, cache, and events

The initial Redis Streams transport is now in place for stage dispatch and result events. Complete the reliability and observability work below without making Redis the authoritative record of job state.

- Choose Redis Streams or a maintained task-queue library based on acknowledgement, visibility timeout, retry, and consumer-group needs.
- Keep PostgreSQL as the source of truth; Redis contains dispatchable stage tasks, transient cache entries, and optionally live event streams.
- Publish one stage task at a time and acknowledge it only after the database result transition is committed.
- Add separate queues and concurrency limits for CPU, GPU, and LLM workloads.
- Cache safe, bounded data such as dependency health, queue summaries, and reusable metadata lookups; do not cache authorization-sensitive results without ownership-aware keys.
- Add delayed retries, dead-letter queues, graceful shutdown, and a reconciliation process that re-enqueues missing tasks from PostgreSQL.
- Ensure Redis loss or eviction is recoverable from PostgreSQL and does not lose user-visible jobs.
- Use SSE/WebSockets or Redis-backed events for updates only with a polling/reload fallback.

Definition of done: multiple worker replicas can process jobs with controlled concurrency and recover from duplicate delivery, Redis restart, and missed events.

## Phase 6 — Scaling and capacity management

Docker Compose remains useful for development and a small single-host deployment, but true autoscaling requires a scheduler such as Docker Swarm, Kubernetes, Nomad, or a managed worker platform.

- Measure CPU, memory, GPU, model-cache, and I/O profiles for every service.
- Scale stateless frontend/API replicas independently from stage workers.
- Scale worker pools by queue/resource class using queue age, depth, and utilization signals.
- Decide GPU placement, model warm-up, cache locality, maximum concurrency, and node affinity.
- Add graceful draining so workers finish or safely requeue active stages before termination.
- Add admission control and capacity budgets for uploads, disk, MinIO, database connections, GPU memory, and model calls.
- Maintain a simple Compose profile and a separate production scheduler definition.

Definition of done: scale-out, scale-in, and worker loss are safe, and queue latency remains within an agreed target under load.

## Phase 7 — Complete frontend redesign

Do this after the backend contracts, authentication, metrics, queue behavior, and capacity controls are stable. The frontend should be built against the real job, ownership, health, and event APIs.

- Create a clear shell with primary areas: **New analysis**, **Active jobs**, **History/library**, and **System status**.
- Replace the modal-only progress experience with a persistent jobs page or drawer. Closing the view must not stop or hide the job.
- Show each job’s input, requested outputs, current stage, progress, elapsed time, created time, retry count, and a human-readable failure reason.
- Add actions: view result, cancel, retry failed job, delete job/result, and copy a job link.
- Make the submission flow task-oriented: “What do you have?” → “What do you want to learn?” → review → submit. Explain that stages are sequential and that some outputs require earlier stages.
- Add empty, loading, validation, duplicate-match, failed, permission-denied, and offline states.
- Use SSE or WebSockets for job updates when practical, with polling as a fallback. Avoid one request per second per open modal.
- Add accessible labels, keyboard navigation, responsive layouts, account/session controls, and consistent terminology.
- Remove dead UI paths and unused state/components.

Definition of done: a user can submit multiple jobs, navigate away, return to see all jobs and their live state, recover from a failure, understand system status, and use the full analysis library without reading documentation.

## Phase 8 — Stress testing and tuning

Validate the system before using autoscaling or calling the platform production-ready.

- Build representative workloads: audio through all stages, text-only classification, duplicate uploads, failed dependencies, long audio, and concurrent batches.
- Establish targets for submission latency, time-to-first-progress, queue wait, per-stage latency, total completion time, error rate, and recovery time.
- Run baseline, sustained-load, burst-load, failure-injection, and scale-up/scale-down tests.
- Test database contention, Redis restart/eviction, MinIO latency, model cold starts, worker crashes, network failures, and disk pressure.
- Capture results in versioned reports with workload size, deployment shape, resource limits, queue configuration, and observed bottlenecks.
- Tune worker concurrency, queue priorities, database indexes/pool sizes, model settings, and autoscaling thresholds from the results.

Definition of done: a repeatable stress-test report shows capacity limits, failure behavior, and the next scaling bottleneck; changes are validated against the baseline.

## Future product expansion

- Analysis history with filtering, sorting, search, tags, and export.
- Compare multiple analyses and show stage provenance, model/version, confidence, and limitations.
- Audio preview and secure, time-limited downloads for authorized users.
- Batch uploads with a summary view and partial-failure handling.
- User-editable corrections for title, artist, and transcript, with clear distinction between generated and human-edited data.
- Classifier evaluation: labeled test set, calibration, threshold tuning, model comparison, and language limitations. Classification should remain a probabilistic signal, not proof of authorship.
- Optional sharing links or team workspaces, added only after ownership and revocation rules are solid.

## Suggested first milestone

The first implementation milestone should be **Data and orchestration foundation v1**:

1. Define canonical job/stage states and transition rules.
2. Add versioned migrations for lifecycle, attempt, and future ownership fields.
3. Rework worker claiming, leases, retries, cancellation, and restart recovery.
4. Add transition/API/integration tests.
5. Add structured metrics and dependency health endpoints.
6. Establish a repeatable baseline load test.

After that milestone, implement accounts and ownership, harden the Redis transport, scale the measured bottlenecks, complete the frontend against the stabilized contracts, and then run the full end-to-end stress-test plan.

## Decisions to make early

- Is Clankr single-user/self-hosted, multi-user, or both? This changes the auth and data model substantially.
- Are uploaded audio and generated stems retained indefinitely, retained for a period, or deleted after results are persisted?
- Is the target deployment one VM, several GPU machines, or a hosted service?
- Which workloads need GPU acceleration, and how many concurrent jobs can each model safely handle?
- Should users be able to share results, and if so, are shared links public, private-to-team, or expiring?
- What is the product promise of classification, and how will uncertainty and false positives be communicated?
