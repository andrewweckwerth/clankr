# System architecture

## Context

Clankr turns audio or lyrics into persisted song-analysis results. The browser talks to the Next.js frontend, and the frontend proxies `/api/*` requests to the internal FastAPI orchestrator. The orchestrator owns job creation, pipeline sequencing, database writes, and calls to the specialist services.

```text
Browser
  │
  ▼
Next.js frontend (:3000)
  │  Next.js rewrite: /api/* → http://orchestrator:8000/api/*
  ▼
FastAPI orchestrator (:8000)
  ├── PostgreSQL (:5432)       jobs, songs, deduplication metadata
  ├── Redis (:6379)            fingerprint-to-song ID cache
  ├── MinIO (:9000)            raw audio, converted audio, vocal stems
  ├── Acousti (:8000)          FFmpeg + fpcalc + AcoustID lookup
  ├── Demucs (:8000)           vocal separation
  ├── Whisper (:8000)          speech-to-text transcription
  └── Classifier (:8000)       Ollama-backed AI/Human classification
                                  │
                                  ▼
                              Ollama (:11434)
```

In production, Traefik is the only public edge service. It terminates HTTPS and routes the configured hostname to the frontend. The specialist services, database, object store, orchestrator, and Ollama remain on Docker networks without public host ports.

## Request flow

1. The user selects an input mode and an output stage in the frontend.
2. `POST /api/analyze` reaches the orchestrator through the Next.js rewrite.
3. For audio input, the orchestrator stores the upload under `raw/` in MinIO.
4. The orchestrator creates a row in `jobs` and one `job_steps` row for each requested stage in a single transaction.
5. Three orchestrator worker tasks poll PostgreSQL and atomically claim queued `job_steps` with `FOR UPDATE SKIP LOCKED`.
6. During identification, the orchestrator checks Redis for a cached song ID using the fingerprint hash. A miss falls back to PostgreSQL and repopulates the cache when a song is found.
7. Each worker runs one pending stage, records its result and status on the step, and queues the next step.
8. When all requested steps are complete, the job data is upserted into `songs`, the job receives its `song_id`, and the job is marked `completed`.
9. The frontend polls the job endpoint while work is active and receives the ordered step list for detailed progress.

## Pipeline stages

The stage order is fixed by `get_and_claim_job`:

```text
identify → demucs → whisper → classify
```

| UI output | Job flag | Service call | Main result |
| --- | --- | --- | --- |
| Song Info | `job_steps(stage='identify')` | Acousti convert + identify | title, artist, fingerprint, duration |
| Stems | `job_steps(stage='demucs')` | Demucs separate | `stems/<name>.wav` |
| Lyrics | `job_steps(stage='whisper')` | Whisper transcribe | lyrics text |
| Classification | `job_steps(stage='classify')` | Classifier classify | `AI`/`Human`, accuracy |

Text input bypasses audio stages and supplies lyrics directly to the classifier. Search input performs a fuzzy PostgreSQL lookup and returns an existing song without creating a processing job when the similarity threshold is met.

## Service boundaries

Each Python service is a standalone FastAPI application in its own container. The orchestrator calls services over Docker DNS using environment-configurable URLs. Service calls use form fields rather than JSON for the main processing operations. Health checks are exposed at `GET /health`.

The frontend is deliberately not a direct client of the worker services. This keeps internal service names and credentials out of the browser and gives the orchestrator one place to handle sequencing, timeouts, and persistence.

## Reliability characteristics

- Job-step claiming is transaction-safe for multiple workers through row locking and `SKIP LOCKED`.
- Fingerprint hashes are used as a natural key for song upserts.
- Redis is a best-effort read-through cache only; PostgreSQL remains authoritative and cache loss is recoverable.
- A failed step marks both the step and its parent job `failed`; there is no automatic retry policy yet.
- Work is polled from PostgreSQL approximately every 0.5 seconds when idle.
- Long-running model calls have per-service HTTP timeouts.
- There is no external queue, distributed tracing, metrics backend, or dead-letter workflow in the current implementation.

## Design constraints

- MinIO object keys, not local filesystem paths, are passed between services.
- Temporary local files are created inside processing containers and removed after processing.
- PostgreSQL initialization is supplied by `database/init.sql`; it is not a versioned migration system.
- The classifier's output is a model judgment about surface cues in lyrics; it is not a provenance proof.
