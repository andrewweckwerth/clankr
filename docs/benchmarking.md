# Benchmarking and structured logs

Clankr emits structured JSON logs to standard output from the orchestrator,
each Python worker, and the frontend's server-side API proxy. Docker's
`json-file` driver retains the normal production logs with a `10 MB × 5 files`
rotation policy. The application never writes a log row synchronously while
processing a job; that would add database work to the workload being measured.

Every application event has a stable core shape:

```json
{
  "schema_version": 1,
  "timestamp": "2026-09-04T20:00:00.000000+00:00",
  "level": "info",
  "event": "stage.completed",
  "service": "demucs",
  "container": "…",
  "environment": "production",
  "run_kind": "normal",
  "benchmark_run_id": null,
  "release_sha": "…",
  "job_id": "42",
  "task_id": "…",
  "stage": "demucs",
  "worker_id": "…",
  "attempt": "1",
  "duration_ms": 1234
}
```

Normal work has `run_kind=normal` and no benchmark run ID. The isolated
benchmark stack sets `environment=benchmark`, `run_kind=stress_test`, and a
unique `benchmark_run_id` through Compose. That value is set by the operator,
not accepted from a browser request.

The backend lifecycle events are `service.started`, `worker.started`,
`job.created`, `stage.enqueued`, `task.claimed`, `stage.started`,
`stage.completed`, `stage.failed`, and `job.completed`. The frontend records
the authenticated API proxy's accepted, rejected, and failed requests with
method, path, status, and duration. Neither layer records request bodies,
cookies, audio bytes, lyrics, or credentials. Error stack traces remain in
standard error for debugging, so treat exported logs as operational data rather
than public data.

## Inspecting ordinary production logs

Use the production project and environment file already used for deployment:

```bash
docker compose --project-name clankr-prod --env-file /path/to/.env \
  -f docker-compose.prod.yml logs --tail=200 --no-log-prefix orchestrator

docker compose --project-name clankr-prod --env-file /path/to/.env \
  -f docker-compose.prod.yml logs --tail=200 --no-log-prefix demucs
```

Each non-framework application line is JSON and can be sent later to a log
backend without changing the services. Docker's normal log rotation makes this
useful for troubleshooting but is not an archive.

## Isolated single-VM Demucs benchmark

`benchmarks/run_demucs_benchmark.sh` compares Demucs replica counts while using
the same built application images as production. It starts only an isolated
benchmark project containing PostgreSQL, Redis, MinIO, MinIO initialization,
the orchestrator, the requested number of Demucs workers, and a short-lived
benchmark runner. It does **not** start Traefik, the frontend, or unrelated
workers.

Compose project names make the database, Redis, and MinIO volumes distinct
from `clankr-prod`; benchmark jobs never enter the production database. Because
both projects run on the same VM, the benchmark can still consume CPU, RAM,
disk I/O, and network bandwidth that production needs. Run it in a maintenance
window or when production traffic is negligible, begin with a small batch, and
watch host disk space.

### One-time preparation on the VM

1. Deploy a version containing this benchmark harness and select the exact
   GHCR image tag to compare. Use the same tag in every trial.
2. Create a benchmark-only environment file; do not copy or point at the
   production `.env` file:

   ```bash
   cp benchmarks/.env.benchmark.example benchmarks/.env.benchmark
   chmod 600 benchmarks/.env.benchmark
   ```

   Replace every `replace-with-…` value. Keep the benchmark PostgreSQL,
   MinIO, and internal-auth values separate from production. Set `IMAGE_PREFIX`
   and `IMAGE_TAG` to the production image registry/tag being measured. The
   example uses Clankr's public GHCR `latest` images; the script pulls its
   orchestrator and Demucs images automatically when the prefix starts with
   `ghcr.io/`. Pin a commit-SHA tag rather than `latest` for a reproducible
   comparison. Retain `BENCHMARK_ENVIRONMENT=isolated`; the benchmark script
   refuses to run without that explicit safety marker.
3. Place one representative, legally usable audio fixture under
   `benchmarks/fixtures/`. Fixtures are ignored by Git. A valid WAV keeps the
   Demucs workload comparable across every trial.

### Run a comparison

Do one small smoke run first. It verifies the benchmark images, fresh database,
MinIO input copies, and report generation before consuming substantial VM time:

```bash
BENCHMARK_ENV_FILE=benchmarks/.env.benchmark \
  ./benchmarks/run_demucs_benchmark.sh \
  --audio benchmarks/fixtures/representative.wav \
  --jobs 10 --demucs-replicas 1
```

Then run the actual comparison. Keep the fixture, image tag, job count, VM, and
other running production workload as consistent as possible. Repeat each shape
at least three times; ignore a first run only if it is a documented model-cache
warm-up run.

```bash
BENCHMARK_ENV_FILE=benchmarks/.env.benchmark \
  ./benchmarks/run_demucs_benchmark.sh \
  --audio benchmarks/fixtures/representative.wav \
  --jobs 1000 --demucs-replicas 1

BENCHMARK_ENV_FILE=benchmarks/.env.benchmark \
  ./benchmarks/run_demucs_benchmark.sh \
  --audio benchmarks/fixtures/representative.wav \
  --jobs 1000 --demucs-replicas 2
```

The script uses `docker compose --scale demucs=N`, so `N=2` launches two
independent Demucs consumers. It deliberately submits standalone Demucs jobs:
fingerprint caching and LLM behavior cannot hide the worker-capacity difference.
The runner gives each job a unique `raw/benchmarks/<run>/…` key, preventing
Demucs output-object collisions while all inputs remain byte-identical.

### Apple Silicon development machines

The published production images currently target `linux/amd64`. On an Apple
Silicon Mac, the harness intentionally stops before pulling them unless you
explicitly enable emulation:

```bash
./benchmarks/run_demucs_benchmark.sh \
  --audio benchmarks/fixtures/representative.wav \
  --jobs 10 --demucs-replicas 1 \
  --enable-emulation
```

The flag passes `linux/amd64` to Docker Desktop, allowing it to pull and emulate
the production application and infrastructure images. Use this for a local smoke test only: emulation
substantially changes CPU and timing results. Run capacity comparisons intended
to represent production on the amd64 VM, or publish native multi-architecture
images first.

The script automatically removes the isolated project, containers, network, and
named volumes after either success or failure. It preserves the result directory
on the host. Add `--keep-project` only when you need to inspect the benchmark
database or containers before removing that specific project manually; it never
removes production volumes.

## Evidence collected per run

Each run creates an ignored directory at `benchmarks/results/<run-id>/`:

```text
manifest.json             workload, image/git context, and host identity
docker-stats.ndjson       one Docker stats sample per running container per interval
logs/                     raw stdout/stderr log export for every benchmark container
summary.json              aggregate timings and throughput
jobs.csv                  one row per job
report.md                 concise comparison-ready report
```

The benchmark runner imports structured application JSON lines from `logs/` into
the isolated benchmark database's `benchmark_events` table **after** the jobs
finish. Raw infrastructure logs stay as files because Redis, PostgreSQL, and
MinIO do not share Clankr's event schema. `benchmark_runs` and
`benchmark_jobs` link the workload to the normal `jobs` and `job_steps` rows in
that isolated database.

The report treats database timestamps as the source of timing truth:

- Queue wait: `job_steps.started_at - job_steps.queued_at`
- Demucs duration: `job_steps.completed_at - job_steps.started_at`
- End-to-end job duration: `jobs.completed_at - jobs.created_at`

It reports p50, p95, maxima, completed/failed counts, and throughput. Compare
the report with `docker-stats.ndjson`: if two workers improve queue wait but not
throughput while both saturate CPU or memory, the VM is the bottleneck rather
than a missing worker replica.

## Suggested stress-test sequence

1. Establish the 10-job smoke baseline with one Demucs worker.
2. Run a 100-job steady batch at one worker and repeat it three times.
3. Run the same 100-job batch at two workers and compare p50/p95 queue wait,
   stage duration, throughput, error count, CPU, memory, and disk pressure.
4. Only after the VM is stable, run the 1,000-job burst with one worker, then
   two workers. Stop if failures, swap pressure, low disk space, or production
   impact appears.
5. Record the exact image tag, fixture hash, replica count, job count, and
   whether models were warm. Keep the resulting directories as the comparison
   evidence.
6. Follow-up experiments should change one thing at a time: worker count,
   input length, job arrival rate, or resource limit. Run a new isolated
   project for every experiment.

This measures a single VM's real capacity; it is not autoscaling. A second
Demucs container may improve throughput, do nothing, or make it worse depending
on CPU, memory, disk, and model-cache contention. The artifacts make that
tradeoff visible before changing the production worker count.
