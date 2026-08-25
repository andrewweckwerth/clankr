# AGENTS.md

## Scope

These instructions apply to the entire repository. More-specific `AGENTS.md` files may add service-level rules if introduced later.

## Project shape

Clankr is a Docker Compose application composed of a Next.js frontend, FastAPI orchestration and processing services, PostgreSQL, MinIO, and Ollama. Read [docs/architecture.md](docs/architecture.md) before changing pipeline behavior.

## Working rules

- Treat the current source and Compose files as the source of truth; do not assume old README or deployment prose is correct.
- Keep changes scoped to the requested behavior and avoid unrelated formatting churn.
- Never commit credentials, private keys, audio files, model weights, generated datasets, `.env` files, or runtime state.
- Preserve object-key contracts (`raw/`, `preprocessed/`, `stems/`) unless the database and all consumers are updated together.
- When changing a stage, update its FastAPI endpoint, orchestrator call, database flags/state transitions, frontend controls, and documentation.
- When changing schema, update `database/init.sql`, database access code, and `docs/data-model.md`. Remember that `init.sql` is not a migration system.

## Validation

Use the smallest relevant checks first, then broaden them for cross-service changes:

```bash
docker compose config
docker compose build
docker compose run --rm frontend npm run lint
```

For runtime changes, start the stack and verify `/health` for the affected service. For pipeline changes, exercise both an audio request and a text-only request when possible. There is currently no automated repository-wide test suite.

## Documentation expectations

Keep the public overview in [`readme.md`](readme.md) concise and oriented toward readers evaluating the project. Put implementation, development, data-model, deployment, and known-risk details in `docs/`.

