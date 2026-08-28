# System architecture

## Context

Clankr turns audio or lyrics into persisted song-analysis results. The browser talks to the Next.js frontend, and the frontend proxies `/api/*` requests to the internal FastAPI orchestrator. Redis Streams dispatch processing work to the specialist containers, while PostgreSQL remains the durable source of truth for jobs and songs.

```text
Browser
  │
  ▼
Next.js frontend (:3000)
  │ Next.js rewrite: /api/* → http://orchestrator:8000/api/*
  ▼
FastAPI orchestrator (:8000)
  ├── PostgreSQL (:5432)       jobs, songs, deduplication metadata
  ├── Redis (:6379)            stage queues and result events
  └── MinIO (:9000)            raw audio, converted audio, vocal stems

Redis Streams
  ├── identify queue  → Acousti
  ├── demucs queue    → Demucs
  ├── whisper queue   → Whisper
  └── classify queue  → Classifier → Ollama (:11434)
```

In production, Traefik is the only public edge service. It terminates HTTPS and routes the configured hostname to the frontend. The specialist services, database, Redis, object store, orchestrator, and Ollama remain on Docker networks without public host ports.

## Request flow

1. The user selects an input mode and an output stage in the frontend.
2. `POST /api/analyze` reaches the orchestrator through the Next.js rewrite.
3. For audio input, the orchestrator stores the upload under `raw/` in MinIO.
4. The orchestrator creates a `Queued` row in `jobs` with the requested stages.
5. The orchestrator publishes a small task to the Redis Stream for the first stage. Tasks contain the job ID, stage, MinIO object key, and any text input; audio bytes do not pass through Redis.
6. The stage container consumes the task, processes it, and publishes a result event to `clankr:events:results`.
7. The orchestrator consumes the result event, updates PostgreSQL in a transaction, and queues the next requested stage.
8. When all requested stages are complete, the job data is upserted into `songs` and the job is marked `Completed`.

Redis uses Streams consumer groups. A task is acknowledged after the specialist has published its result event. Abandoned pending tasks can be reclaimed after `REDIS_VISIBILITY_TIMEOUT_MS`.

## Pipeline stages

The stage order is fixed by the orchestrator:

```text
identify → demucs → whisper → classify
```

| UI output | Job flag | Redis queue | Main result |
| --- | --- | --- | --- |
| Song Info | `want_identify` | `clankr:queue:identify` | title, artist, fingerprint, duration |
| Stems | `want_demucs` | `clankr:queue:demucs` | `stems/<name>.wav` |
| Lyrics | `want_whisper` | `clankr:queue:whisper` | lyrics text |
| Classification | `want_classify` | `clankr:queue:classify` | `AI`/`Human`, accuracy |

Text input bypasses audio stages and sends lyrics directly to the classifier. Search input performs a fuzzy PostgreSQL lookup and returns an existing song without creating a processing job when the similarity threshold is met.

## Service boundaries

Each Python specialist is a standalone FastAPI application with a Redis consumer running in its lifespan. Its processing HTTP routes have been removed. The remaining `/health` endpoint reports process and Redis readiness and is used by Docker Compose healthchecks.

The orchestrator is the only service that owns job sequencing and PostgreSQL writes. Specialists read and write audio through MinIO and communicate task completion through Redis result events. This keeps database credentials and lifecycle rules out of the processing containers.

HTTP is still used for browser/API requests, healthchecks, and the classifier's connection to Ollama. Redis is used for asynchronous processing communication, not for transferring audio data or serving the browser.

## Redis configuration

Development and the included Compose production file run a local Redis 7 container on the internal Docker network. Development also binds it to `127.0.0.1:6379` for operator access.

The application reads `REDIS_URL`. The default is:

```text
redis://redis:6379/0
```

For a managed TLS Redis service, set the value to its TLS URL, for example `rediss://<username>:<password>@<host>:10000/0`. The application does not assume that port `10000` is HTTP; it is a Redis protocol endpoint protected by TLS.

## Reliability characteristics

- PostgreSQL remains authoritative for user-visible job state.
- Redis Streams provide consumer groups and at-least-once task delivery.
- Duplicate result events are ignored after the corresponding stage flag is complete.
- A failed stage marks the job `Failed`; automatic retry policy is not implemented yet.
- Abandoned queue messages are reclaimable after the visibility timeout.
- MinIO object keys, not local filesystem paths, are passed between services.
- Temporary local files are created inside processing containers and removed after processing.
- There is no external metrics backend or dead-letter workflow yet.

## Design constraints

- Preserve object-key contracts (`raw/`, `preprocessed/`, `stems/`) when changing pipeline behavior.
- Redis is a dispatch and event transport, not the authoritative job database.
- `database/init.sql` is initialization-only, not a versioned migration system.
- The classifier's output is a model judgment about surface cues in lyrics; it is not a provenance proof.
