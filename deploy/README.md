# Clankr deployment

This project uses Docker Compose on a Linode Ubuntu server.

## Branches

- `main` is production and should be protected in GitHub.
- `develop` is the integration branch for the development environment.
- Feature branches should be named `feature/<short-name>` and merged into `develop`.

The server should use two separate Compose projects and two separate environment
files:

```text
/opt/clankr/
  app/                 # checked-out repository
  env/production.env   # chmod 600, never committed
  env/development.env  # chmod 600, never committed
```

## First-time Linode setup

Use an Ubuntu 24.04 LTS x86_64 instance with enough disk for Docker images,
Whisper, Demucs, and the Ollama model. Install Docker Engine and Compose v2,
clone the repository into `/opt/clankr/app`, then create the two env files from
`.env.example`.

Generate strong independent passwords for the two databases. Set the production
origin to the production URL and use a separate development hostname, such as
`dev.clankr.app`, if development is exposed through Traefik.

The production stack expects DNS for the configured hostname to point at the
Linode before Traefik requests a Let's Encrypt certificate. Open only ports 22,
80, and 443 in the Linode firewall. Postgres and Ollama should not be exposed
publicly.

After the first startup, pull the classifier model once:

```bash
ENV_FILE=/opt/clankr/env/production.env docker compose --project-name clankr-prod --env-file /opt/clankr/env/production.env \
  -f docker-compose.prod.yml exec ollama ollama pull qwen2.5:3b-instruct
```

## Start production

```bash
cd /opt/clankr/app
docker compose --project-name clankr-prod --env-file /opt/clankr/env/production.env \
  -f docker-compose.prod.yml up -d --build
docker compose --project-name clankr-prod --env-file /opt/clankr/env/production.env \
  -f docker-compose.prod.yml ps
```

## Start development on the same host

```bash
cd /opt/clankr/app
docker compose --project-name clankr-dev --env-file /opt/clankr/env/development.env \
  -f docker-compose.yml up -d --build
docker compose --project-name clankr-dev --env-file /opt/clankr/env/development.env \
  -f docker-compose.yml ps
```

The development stack is intended for internal access or an SSH tunnel to port
3000. Do not publish its database, worker APIs, or Ollama port to the internet.

## Updating after a merge

Production:

```bash
cd /opt/clankr/app
git fetch origin
git checkout main
git pull --ff-only origin main
docker compose --project-name clankr-prod --env-file /opt/clankr/env/production.env \
  -f docker-compose.prod.yml up -d --build
```

Development uses the same commands with `develop`, `clankr-dev`, and
`development.env`.

## Backups

Back up Postgres before upgrades and store backups outside the Linode host:

```bash
ENV_FILE=/opt/clankr/env/production.env docker compose --project-name clankr-prod --env-file /opt/clankr/env/production.env \
  -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > /var/backups/clankr-$(date +%F).sql.gz
```

The `pgdata` Docker volume is not a backup. Set up an encrypted off-host backup
schedule before treating the deployment as durable.

## Credentials and secrets

Do not reuse credentials currently present in old infrastructure files. Rotate
any OCI keys, SSH keys, AcoustID keys, and database passwords before going live.
Keep env files at mode `600` and do not commit `letsencrypt/acme.json` or private
keys.
