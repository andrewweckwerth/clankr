# Architecture

Clankr is a Next.js frontend backed by a FastAPI orchestrator, PostgreSQL, Redis Streams, MinIO, specialist workers, and Ollama.

```text
Browser
        |
Next.js frontend (:3000) ---- Better Auth (PostgreSQL auth_* tables)
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

Authentication stays in Next.js. Better Auth sets the browser session cookie
and handles Google OAuth plus email/password sign-in. Requests to the
application API go through Next.js, which validates the session and signs a
short-lived internal identity assertion for the orchestrator. The orchestrator
verifies that assertion before mapping the Better Auth user ID to the local
numeric application user.

## Request flow

1. The frontend sends `POST /api/analyze` with either `mode=full` or
   `mode=standalone` plus one specialist service.
2. Audio uploads are stored under `raw/` in MinIO; audio bytes never pass through Redis.
3. The orchestrator creates a `jobs` row and one `job_steps` row per requested stage.
4. A Redis Stream task is published for the first stage. Workers consume tasks, read/write MinIO objects, and publish result events.
5. The orchestrator consumes result events, updates PostgreSQL transactionally, and queues the next requested stage.
6. After identification, full jobs check the global fingerprint cache. A hit
   links the existing song to the user and skips the remaining stages.
7. On a cache miss, only a successful full job is upserted into the canonical
   `songs` record. Standalone jobs complete without creating songs. A standalone
   Acousti cache hit may still link an existing song to the user's library.

Redis Streams use consumer groups and at-least-once delivery. Abandoned pending messages can be reclaimed after `REDIS_VISIBILITY_TIMEOUT_MS`.

## Pipeline stages

The fixed order is `identify → demucs → whisper → classify`.

| UI output | Job step | Redis queue | Main result |
| --- | --- | --- | --- |
| Song Info | `identify` | `clankr:queue:identify` | title, artist, fingerprint, duration |
| Stems | `demucs` | `clankr:queue:demucs` | `stems/<name>.wav` |
| Lyrics | `whisper` | `clankr:queue:whisper` | lyrics text |
| Classification | `classify` | `clankr:queue:classify` | `AI`/`Human`, accuracy |

The full-project workflow always requests all four stages with fixed settings.
Demucs writes the vocal stem used by Whisper, and Whisper's transcript feeds the
classifier. Standalone tools request exactly one stage: Acousti, Demucs, and
Whisper accept audio, while the classifier accepts text.

## Product surfaces

- **Full Project** creates a full job. Cache misses become canonical Songs only
  after every stage succeeds.
- **Tools** creates one-stage standalone jobs. These results remain Jobs rather
  than becoming new Songs.
- **My Jobs** lists all user-owned work, including running, completed, and
  failed jobs. Failed jobs can be rerun as new jobs using their original input.
- **Songs** contains the global canonical catalog and each user's library
  relationship. Removing a Song from a library does not delete the canonical
  cache entry.

## Service boundaries

Each specialist is a standalone FastAPI application with a Redis consumer in its lifespan. The orchestrator owns sequencing and PostgreSQL writes. The classifier calls Ollama over HTTP and returns the normalized classification result.

## Redis configuration

Development and production run Redis 7 on the internal Docker network. The application reads `REDIS_URL`, defaulting to `redis://redis:6379/0`. Redis is both the asynchronous transport and a best-effort fingerprint-to-song cache; PostgreSQL remains authoritative.

## Reliability and constraints

- PostgreSQL is the source of truth for jobs and songs.
- Duplicate result events are ignored after a step is complete.
- Failed stages mark both the step and parent job `failed`; automatic retries are not implemented.
- User-requested retries create a new job and rerun the selected fixed workflow.
- MinIO object-key contracts are `raw/`, `preprocessed/`, and `stems/`.
- `database/init.sql` is initialization-only, not a migration system.
- There is no external metrics backend, tracing system, or dead-letter workflow yet.
