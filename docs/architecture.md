# Architecture

Clankr is a Next.js frontend backed by a FastAPI orchestrator, PostgreSQL, Redis Streams, MinIO, specialist workers, and Ollama.

```text
Next.js frontend (:3000)
        |
FastAPI orchestrator (:8000) ---- PostgreSQL (:5432)
        |                          jobs, songs, job_steps
        +---- Redis (:6379) -------- stage queues and result events
        +---- MinIO (:9000) -------- raw audio and derived objects
        |
        +---- Acousti / Demucs / Whisper / Classifier workers
                                      |
                                      +---- Ollama (:11434)
```

In production, Traefik is the only public edge service. It terminates HTTPS and routes the configured hostname to the frontend. Specialist services, PostgreSQL, Redis, MinIO, the orchestrator, and Ollama remain on internal Docker networks.

## Request flow

1. The frontend sends `POST /api/analyze` to the orchestrator.
2. Audio uploads are stored under `raw/` in MinIO; audio bytes never pass through Redis.
3. The orchestrator creates a `jobs` row and one `job_steps` row per requested stage.
4. A Redis Stream task is published for the first stage. Workers consume tasks, read/write MinIO objects, and publish result events.
5. The orchestrator consumes result events, updates PostgreSQL transactionally, and queues the next requested stage.
6. When all requested steps complete, the job is upserted into `songs` and marked `completed`.

Redis Streams use consumer groups and at-least-once delivery. Abandoned pending messages can be reclaimed after `REDIS_VISIBILITY_TIMEOUT_MS`.

## Pipeline stages

The fixed order is `identify → demucs → whisper → classify`.

| UI output | Job step | Redis queue | Main result |
| --- | --- | --- | --- |
| Song Info | `identify` | `clankr:queue:identify` | title, artist, fingerprint, duration |
| Stems | `demucs` | `clankr:queue:demucs` | `stems/<name>.wav` |
| Lyrics | `whisper` | `clankr:queue:whisper` | lyrics text |
| Classification | `classify` | `clankr:queue:classify` | `AI`/`Human`, accuracy |

Text input skips audio stages and sends lyrics directly to the classifier. Search input performs a fuzzy PostgreSQL lookup and does not create a processing job when a match is found.

## Service boundaries

Each specialist is a standalone FastAPI application with a Redis consumer in its lifespan. The orchestrator owns sequencing and PostgreSQL writes. The classifier calls Ollama over HTTP and returns the normalized classification result.

## Redis configuration

Development and production run Redis 7 on the internal Docker network. The application reads `REDIS_URL`, defaulting to `redis://redis:6379/0`. Redis is both the asynchronous transport and a best-effort fingerprint-to-song cache; PostgreSQL remains authoritative.

## Reliability and constraints

- PostgreSQL is the source of truth for jobs and songs.
- Duplicate result events are ignored after a step is complete.
- Failed stages mark both the step and parent job `failed`; automatic retries are not implemented.
- MinIO object-key contracts are `raw/`, `preprocessed/`, and `stems/`.
- `database/init.sql` is initialization-only, not a migration system.
- There is no external metrics backend, tracing system, or dead-letter workflow yet.
