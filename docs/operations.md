# Operations and deployment

## Production topology

`docker-compose.prod.yml` runs the application from images pulled from GHCR. Traefik is the public edge and routes HTTPS traffic to the frontend. The frontend and Traefik join a `web` network; application services use the default internal network. PostgreSQL and MinIO data live in named Docker volumes.

The production VM needs Docker Compose v2, DNS pointing the application host at the VM, and private environment values supplied outside the repository. PostgreSQL, Redis, MinIO, Ollama, and worker health APIs should not be internet-facing. Redis state lives in a named Docker volume, while PostgreSQL remains authoritative for jobs.

## Deployment flow

The GitHub Actions workflow runs on pushes to `main` or manually:

1. Build six images: frontend, Demucs, Whisper, classifier, Acousti, and orchestrator.
2. Push the commit-SHA tag and `latest` to GHCR.
3. SSH to the VM using GitHub secrets.
4. Pull the commit-SHA images with the production Compose file.
5. Restart the production project and prune unused Docker images.

The deployment is image-based, but the VM also pulls the repository checkout before Compose runs. Keep the checkout and production environment file in the paths expected by the workflow, or update the workflow and this document together.

## Secrets

Keep database, MinIO, AcoustID, TLS, registry, and SSH credentials outside the repository. Use GitHub Actions secrets for CI values and a file with restrictive permissions on the VM for runtime values. Rotate credentials if they have ever been committed, shared in logs, or copied into an issue.

The checked-in `.env` file must be treated as sensitive configuration. Remove real credentials from version control, rotate any exposed values, and use a non-secret example file for onboarding.

## Backups

Back up logical PostgreSQL data, Redis configuration/state as appropriate, and MinIO objects. PostgreSQL remains the source of truth for jobs, so a PostgreSQL dump plus MinIO objects is the essential application backup; Redis streams are recoverable dispatch state. Store encrypted copies outside the VM and periodically test a restore.

Before schema changes, capture a database dump and record the exact application commit. Because the project currently uses an initialization SQL file rather than migrations, upgrades to existing databases require an explicit, reviewed SQL migration plan.

## Troubleshooting

```bash
docker compose --project-name clankr-prod --env-file /path/to/production.env \
  -f docker-compose.prod.yml ps

docker compose --project-name clankr-prod --env-file /path/to/production.env \
  -f docker-compose.prod.yml logs --tail=200 orchestrator

docker compose --project-name clankr-prod --env-file /path/to/production.env \
  -f docker-compose.prod.yml exec classifier wget -qO- http://localhost:8000/health/llm
```

If a job is stuck, inspect the job row, Redis stream/consumer state, and orchestrator logs first. A `Failed` job is not automatically retried. If model calls fail, check Ollama reachability from the classifier container and confirm the configured model exists. If audio processing fails, inspect MinIO availability and the object key recorded in the job.

## Current operational risks

- No automatic retries or alerting for failed jobs.
- No scheduled backup or restore automation in the repository.
- Model downloads are external runtime state.
- Health checks confirm process availability, not end-to-end pipeline health.
- Production uses floating third-party image tags for some infrastructure services; pin and review those tags when reproducibility matters.
