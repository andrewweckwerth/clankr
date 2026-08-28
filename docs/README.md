# Clankr documentation

Clankr is a self-hosted audio analysis application. The web interface accepts an audio file, lyrics, or a title/artist lookup and can run metadata identification, vocal isolation, transcription, and lyrics classification.

This documentation describes the implementation currently present in the repository. It is separate from the public-facing overview in [`readme.md`](../readme.md).

## Documentation map

- [System architecture](architecture.md) — services, request flow, processing stages, networks, and storage boundaries.
- [Data model and pipeline](data-model.md) — PostgreSQL tables, object keys, job state, deduplication, and completion behavior.
- [Local development](development.md) — prerequisites, configuration, startup, useful commands, and verification.
- [Operations and deployment](operations.md) — production topology, CI/CD, secrets, backups, and troubleshooting.
- [Roadmap](roadmap.md) — prioritized product, frontend, authentication, reliability, queue, and scaling work.

## Repository map

```text
database/init.sql                  PostgreSQL schema
docker-compose.yml                 local development stack
docker-compose.prod.yml            production stack
services/frontend/                 Next.js web application
services/orchestrator/             FastAPI API, Redis queue coordinator, and persistence
services/acousti/                  FFmpeg + Chromaprint + AcoustID service
services/demucs/                   vocal-separation service
services/whisper/                  transcription service
services/classifier/               LLM-backed lyrics classifier
.github/workflows/                 image build and deployment automation
```

## Implementation status

The codebase is an active project rather than a finished platform. The current system has no automated test suite, no formal schema migration mechanism, and uses Redis Streams for work distribution while PostgreSQL remains the source of truth. Those constraints are documented so future changes do not mistake planned behavior for implemented behavior.
