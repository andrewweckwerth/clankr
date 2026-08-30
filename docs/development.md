# Local development

## Prerequisites

- Docker Engine with Docker Compose v2
- Enough CPU, memory, and disk for Demucs, Whisper, PostgreSQL, Redis, MinIO, and a local Ollama model
- An AcoustID API key for fingerprint lookups

The repository does not define a host-native Python or Node startup workflow. Compose is the supported development entry point.

## Configuration

Create a private environment file and provide the values consumed by `docker-compose.dev.yml`. At minimum, configure PostgreSQL credentials, MinIO credentials, `FRONTEND_ORIGIN`, the AcoustID key, classifier settings, and Better Auth:

```dotenv
BETTER_AUTH_URL=http://localhost:3000
BETTER_AUTH_SECRET=replace-with-a-long-random-secret
INTERNAL_AUTH_SECRET=replace-with-a-different-long-random-secret
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

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

## Google sign-in setup

1. Create a Google OAuth web client in Google Cloud.
2. Add `http://localhost:3000/api/auth/callback/google` as a development
   redirect URI.
3. Put the client ID and secret in `GOOGLE_CLIENT_ID` and
   `GOOGLE_CLIENT_SECRET`.
4. Run the stack and use **Continue with Google** at `http://localhost:3000/sign-in`.
5. Add the production callback URI for `https://clankr.app` before deployment.

Email/password accounts do not require an email service for sign-up or login.
Password recovery and email verification are intentionally not enabled yet, so
a user who loses their password must already have linked Google or be reset
manually during this preproduction phase. Passwords are stored by Better Auth,
not in application tables.

`INTERNAL_AUTH_SECRET` must be the same long random value in the frontend and
orchestrator environments. Next.js validates the Better Auth session and uses
this secret to sign a short-lived identity assertion for the internal API
request. The orchestrator rejects requests without a valid assertion.

The prerelease database is expected to be rebuilt when the authentication
schema changes. The initialization SQL is not a migration runner. Better Auth
uses the `auth_users`, `auth_sessions`, `auth_accounts`, and
`auth_verifications` tables; the application `users` table remains the local
ownership mapping used by jobs and songs.

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
