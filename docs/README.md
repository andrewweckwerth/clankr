# Clankr documentation

Clankr is a self-hosted audio analysis application. The web interface accepts an audio file, lyrics, or a title/artist lookup and can run metadata identification, vocal isolation, transcription, and lyrics classification.

This documentation describes the implementation currently present in the repository. It is separate from the public-facing overview in [`readme.md`](../readme.md).

## Documentation map

- [Handy commands](commands.md) — SSH, VM benchmark runs, audio uploads, result downloads, HTML reports, and disk cleanup.
- [Benchmarking](benchmarking.md) — isolated Demucs comparisons, structured logs, and collected measurements.
- [First benchmark results](first-benchmark-results.md) — initial 1x–5x Demucs comparison on the Linveo VM, interpretation, and raw timing data.
- [System architecture](architecture.md) — services, request flow, processing stages, networks, and storage boundaries.
- [Data model and pipeline](data-model.md) — PostgreSQL tables, object keys, job state, deduplication, and completion behavior.
- [Local development](development.md) — prerequisites, configuration, startup, useful commands, and verification.
- [Testing](testing.md) — backend, frontend, and browser test coverage, local commands, and CI gates.
- [Operations and deployment](operations.md) — production topology, CI/CD, secrets, backups, and troubleshooting.
- [Roadmap](roadmap.md) — prioritized product, frontend, authentication, reliability, queue, and scaling work.

## Repository map

```text
database/init.sql                  PostgreSQL schema
docker-compose.dev.yml             local development stack
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

The codebase is an active project rather than a finished platform. Automated tests
cover backend contracts, database/queue integration, and focused frontend flows.
Model inference and storage are mocked. There is no formal schema migration
mechanism; Redis Streams distribute work while PostgreSQL remains the source of
truth. See [Testing](testing.md) for the coverage boundaries.
