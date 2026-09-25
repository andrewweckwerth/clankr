# Testing

Clankr uses pytest for the Python backend, Vitest with React Testing Library
for frontend components, and Playwright for browser flows. Tests run alongside
image builds in CI. The default backend and component suites need no running
application stack, model weights, GPU, API keys, or audio files.

## Coverage and boundaries

| Suite | What it checks | External dependencies |
| --- | --- | --- |
| Backend unit/API | Signed authentication, HTTP validation and quota responses, audio/text submissions, job access, health endpoints, classifier parsing/HTTP contract, Redis worker result/ack behavior for all four workers, storage cleanup and object keys | Mocked; network sockets disabled |
| Backend integration | Full stage sequencing, duplicate completion events, text-only completion, failures/retries, fingerprint cache hits, concurrent quotas, owner-only jobs/shared queue redaction, Redis delivery/reclaim/ack | Disposable PostgreSQL 18 and Redis 7; storage and worker outputs mocked |
| Frontend components | Required inputs, upload metadata, text submissions, navigation, pending/error/retry states, account controls, UTC timestamps | Mocked fetch and auth session |
| Browser | Signed-out tool access; text submission → job progress → completed classification | Production Next.js server and Chromium; all application API calls mocked |

The API tests use HTTPX's ASGI transport to exercise real FastAPI routing,
form parsing, dependency resolution, and response serialization. They do not
start service lifespans or background consumers. The orchestrator's import-time
MinIO bucket probe is stubbed in the fixture. ML imports/model constructors are
stubbed when loading Demucs and Whisper; worker loop and event code remain real.

The integration tests use the real `database/init.sql`, database access code,
orchestrator event handler, and Redis helpers. They feed deterministic worker
results into the orchestrator, rather than starting audio-processing workers.
Each test creates and drops its own PostgreSQL schema and uses a unique Redis
key prefix. No test flushes Redis or truncates a shared database. Use dedicated
test services anyway: the fixtures need schema/extension creation privileges.

Browser tests mock the session and API at the browser boundary. They verify
rendering, submission, navigation, and polling, but do not validate real sign-in,
the Next.js authentication proxy, storage, or inference. Real audio processing,
model quality, OAuth, and a complete deployed pipeline still need separate
manual smoke tests. Do not commit audio samples or model weights.

The browser progress test also protects against the elapsed-time clock resetting
the polling timer: a processing job must update to completed without a reload.

## Fast backend tests

From the repository root, using Python 3.12 (matching the orchestrator image):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r tests/backend/requirements.txt
.venv/bin/python -m pytest -m 'not integration' -q
```

`python -m pytest` also works inside the activated virtual environment. Without
`--integration`, integration tests are explicitly skipped. When `--integration`
is supplied, missing service URLs or unavailable services fail the run.
`pytest-socket` blocks network access in fast tests; only local sockets are
allowed in integration tests. A 30-second per-test timeout catches hung workers.

Run one area while developing:

```bash
.venv/bin/python -m pytest tests/backend/test_auth.py -q
.venv/bin/python -m pytest tests/backend/test_workers.py -q
```

## PostgreSQL and Redis integration tests

The small test Compose project is independent of the development/production
stack. PostgreSQL data is ephemeral, Redis persistence is disabled, and ports
are bound to loopback at 55432 and 56379.

```bash
docker compose -p clankr-tests -f tests/compose.yml up -d --wait
TEST_DATABASE_URL=postgresql://clankr_test:clankr_test@127.0.0.1:55432/clankr_test \
TEST_REDIS_URL=redis://127.0.0.1:56379/0 \
  .venv/bin/python -m pytest --integration -m integration -q
docker compose -p clankr-tests -f tests/compose.yml down -v
```

The credentials above belong only to the disposable test containers. The final
command removes that test project's containers, network, and any anonymous
volumes; it does not target the development or production projects. Stop the
test project even if a test fails. To run all backend tests together, omit
`-m integration` while retaining `--integration` and both environment variables.

## Frontend tests

Use Node.js 24, matching CI and the frontend image:

```bash
cd services/frontend
npm ci
npm test
npm run test:watch
```

`npm test` runs once and exits; `test:watch` is for interactive development.
Tests live in `services/frontend/tests/`. They assert user-visible behavior and
request payloads rather than CSS classes or snapshots of whole pages. Async
server component behavior should be covered through browser tests.

For browser tests, build the app first:

```bash
cd services/frontend
npx playwright install chromium
npm run build
npm run test:e2e
```

Playwright starts and stops `next start` itself on `127.0.0.1:3100`. It uses a
dedicated port and refuses to reuse another running server. Rebuild after
changing application code, since these tests use the production bundle. Linux
machines may need `npx playwright install --with-deps chromium`. Failed runs
retain screenshots and traces under `test-results/`; open the browser report
with `npx playwright show-report`. Generated reports are ignored by Git.

## CI and deployment

`.github/workflows/tests.yml` is a reusable workflow with three parallel jobs:

1. Backend unit/API tests, without service containers.
2. Backend integration tests with PostgreSQL and Redis service containers.
3. Frontend lint, component tests, production build, and Chromium browser tests.

The pull-request CI workflow calls it for PRs targeting `dev` or `main`, alongside
all six image builds. The production workflow calls
the same suite on pushes to `main` and manual runs. Its deployment job requires
both the image builds and the entire test workflow to succeed. Image building
and pushing (including the existing `latest` tag) still happen in parallel with
tests; a test failure prevents the SSH deployment, not image publication.

JUnit backend results and browser reports are uploaded as Actions artifacts for
seven days, including on failure. There are no test retries masking flaky tests.
Dependencies use the existing backend requirements plus lightweight test tools;
frontend dependencies remain locked and CI/Docker continue to use `npm ci`.

To prevent merging a failing PR, configure repository branch protection/rulesets
to require the test jobs as status checks. Workflow files alone do not configure
GitHub's merge rules. Keep real model/audio smoke testing separate so routine CI
does not download weights or call external model services.
