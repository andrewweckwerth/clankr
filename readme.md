# Clankr

Clankr is a self-hosted audio-analysis application that explores whether song lyrics appear AI-generated. It combines audio fingerprinting, vocal separation, speech-to-text, and an LLM-backed classifier behind a small Dockerized microservice system.

## Why this project is interesting

- A Next.js frontend exposes one workflow for audio uploads, pasted lyrics, and metadata search.
- A FastAPI orchestrator turns optional analysis stages into durable, database-backed jobs.
- PostgreSQL, MinIO, Docker Compose, GitHub Actions, and an internal Ollama model make the project deployable without a managed cloud dependency.
- The processing pipeline demonstrates service boundaries, asynchronous work, object storage, deduplication, health checks, and production deployment.

```text
Browser → Next.js → Orchestrator → Acousti → Demucs → Whisper → Classifier → Ollama
                              ├──────── PostgreSQL ────────┤
                              └──────── MinIO audio ───────┘
```

## Repository

- `services/frontend` — Next.js user interface
- `services/orchestrator` — API, queue coordination, and persistence
- `services/acousti` — FFmpeg, Chromaprint, and AcoustID integration
- `services/demucs` — vocal isolation
- `services/whisper` — transcription
- `services/classifier` — LLM classification
- `database/init.sql` — current PostgreSQL schema
- `docs/` — architecture, development, data model, and operations notes

## Run locally

The supported local workflow uses Docker Compose:

```bash
docker compose --env-file .env up --build
```

Then open [http://localhost:3000](http://localhost:3000). The classifier also requires the configured Ollama model to be available in the Ollama container.

See the [documentation index](docs/README.md) for the system design and local development details.

## Project status

This is an active engineering project. The current implementation uses Redis Streams for stage queues, has no automated test suite, and treats the classifier as a probabilistic signal rather than proof of authorship. Those tradeoffs are documented alongside the architecture.
