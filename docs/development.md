# Local development

## Prerequisites

- Docker Engine with Docker Compose v2
- Enough CPU, memory, and disk for Demucs, Whisper, PostgreSQL, Redis, MinIO, and a local Ollama model
- An AcoustID API key for fingerprint lookups

The repository does not define a host-native Python or Node startup workflow. Compose is the supported development entry point.

## Configuration

Create a private environment file and provide the values consumed by `docker-compose.dev.yml`. At minimum, configure PostgreSQL credentials, MinIO credentials, `FRONTEND_ORIGIN`, the AcoustID key, and classifier settings.

Use non-production credentials locally. The compose defaults are suitable only for a disposable development machine.

## Start the stack

```bash
docker compose -f docker-compose.dev.yml --env-file .env up --build
```

The development compose file exposes the frontend at `http://localhost:3000`, PostgreSQL on `127.0.0.1:5432`, Redis on `127.0.0.1:6379`, MinIO on `127.0.0.1:9000`, its console at `http://127.0.0.1:9001`, and Ollama on `127.0.0.1:11434`. Other services, including worker health endpoints, are reachable only inside the Compose network.

On first use, make sure the configured Ollama model is available:

```bash
docker compose -f docker-compose.dev.yml exec ollama ollama pull qwen2.5:3b-instruct
```

## Useful commands

```bash
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs -f orchestrator
docker compose -f docker-compose.dev.yml logs -f classifier
docker compose -f docker-compose.dev.yml exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose -f docker-compose.dev.yml down
```

`docker compose down` preserves named volumes unless `--volumes` is supplied. Use the latter only when intentionally deleting local database and object-store data.

## Checks before a pull request

```bash
docker compose -f docker-compose.dev.yml config
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml run --rm frontend npm run lint
```

There is no repository-wide automated test command today. Changes to Python services should at least be checked by rebuilding the affected image and calling its `/health` endpoint. Changes to the pipeline should be tested with a small audio fixture and a text-only request.

## Change guide

- Update a service and its `requirements.txt` together.
- Keep Redis task/result payloads and object-key conventions documented when changing a stage.
- If a database column changes, update `database/init.sql`, the orchestrator's insert/upsert code, and [data-model.md](data-model.md).
- If a stage or flag changes, update frontend controls, worker claim logic, completion logic, and [architecture.md](architecture.md).
- Do not add credentials, audio samples, model weights, or large datasets to the repository.
