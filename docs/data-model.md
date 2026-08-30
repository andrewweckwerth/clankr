# Data model and pipeline state

## Authentication and ownership

Better Auth is the application identity layer. The `users.auth_user_id` value
is the stable external identity; email addresses are profile data and are not
used as ownership keys.

Better Auth stores its identity records separately in `auth_users`,
`auth_sessions`, `auth_accounts`, and `auth_verifications`. A Better Auth
account can contain either the email/password credential or the linked Google
provider. The app's `users` row is created or refreshed when an
authenticated request reaches the orchestrator and maps the Better Auth user
ID to the numeric application user ID.

`jobs` stores one processing request and may be deleted by retention cleanup.
`jobs.user_id` scopes active job access to its owner, while `jobs.song_id` points
to the canonical song produced when processing completes.

`user_songs` is the durable user-library relationship. It records which
canonical songs a user has submitted, including the first and most recent
submission times and the number of submissions. This relationship survives
job cleanup. A canonical `songs` row may be shared by many users because
`fingerprint_hash` deduplicates recordings globally. The all-songs catalog reads
directly from `songs`; the user-specific catalog joins through `user_songs`.

`user_daily_usage` atomically tracks the number of processing submissions made
by each user on a UTC calendar date. The current limit is ten analyses per day;
searches and read-only polling do not consume this quota.

## `songs`

`songs` is the durable result table. It stores user-visible metadata and the
latest completed analysis for a fingerprinted recording. “Canonical” means
that this is the one shared record representing a recording, identified by its
fingerprint hash, rather than a separate copy for every user submission.

| Column group | Fields | Purpose |
| --- | --- | --- |
| Identity | `id`, `title`, `artist`, `fingerprint`, `fingerprint_hash` | Match and deduplicate recordings |
| Analysis | `lyrics`, `classification`, `accuracy`, `duration` | Store stage results |
| Storage | `file_path`, `audio_processed` | Point to the related MinIO object |
| Timestamps | `created_at`, `updated_at` | Record lifecycle times |

`fingerprint_hash` has a unique constraint and is an indexable natural key. The orchestrator computes it from the Chromaprint fingerprint string.

The orchestrator also maintains a best-effort Redis read-through cache using keys in the form `clankr:cache:song:fingerprint:<fingerprint_hash>`. The value is only the PostgreSQL `song_id`; PostgreSQL remains the source of truth. Cache misses, evictions, and Redis outages fall back to the fingerprint lookup in `songs`.

## `jobs`

`jobs` is the parent record for one analysis request. It contains the request's accumulated data, the overall lifecycle state, and the resulting `song_id` when processing finishes. It does not contain one column per processing stage.

`user_id` identifies the locally mapped authenticated user who submitted the request.
Job and song endpoints must filter by this value rather than trusting the
client-provided numeric ID.

## `job_steps`

`job_steps` contains one row for each requested stage in a job. Its `id` is the `job_step_id` used to correlate a queue task, worker execution, and result. `position` preserves the canonical pipeline order.

```text
id, job_id, stage, position, status, attempts,
result, error, queued_at, started_at, completed_at
```

The valid step states are `queued`, `processing`, `completed`, `failed`, and `cancelled`. The job's overall `status` uses the same vocabulary. `current_stage` is retained as a convenient summary for the UI; the step rows are the source of truth for per-stage state.

For example:

```text
jobs:      id=42, status=processing, current_stage=demucs
job_steps: id=101, job_id=42, stage=identify, status=completed
           id=102, job_id=42, stage=demucs,   status=processing
           id=103, job_id=42, stage=whisper,  status=queued
```

Completion checks only the requested stages, so a request can intentionally stop after identification, transcription, or classification.

## Object storage layout

The default MinIO bucket is `clankr-audio`.

| Prefix | Producer | Contents |
| --- | --- | --- |
| `raw/` | Orchestrator | Original uploaded object |
| `preprocessed/` | Acousti | WAV converted with FFmpeg |
| `stems/` | Demucs | Vocal stem WAV used by Whisper |

The database stores the object key in `file_path`. It does not store a public URL, so clients cannot fetch objects directly through the browser.

## Completion and reuse

When every `job_steps` row is complete, the orchestrator writes a song using the job's accumulated fields and sets `jobs.song_id`. Existing rows with the same fingerprint hash are updated rather than duplicated. Search uses PostgreSQL trigram similarity over title and artist and accepts the best match when its score is at least `0.3`.

## Schema limitations

- `updated_at` is declared but no trigger currently updates it.
- Status and stage values use database checks rather than PostgreSQL enums so the initialization schema stays easy to revise during prerelease.
- `jobs` duplicates many `songs` columns to make stage-by-stage updates simple.
- `jobs` is not the permanent user history; retention cleanup must preserve
  `user_songs` if the user's library is to remain intact.
- `job_steps.result` is flexible JSONB because stages produce different shapes of output.
- `database/init.sql` uses `CREATE TABLE IF NOT EXISTS`; changing an existing database requires an explicit migration or controlled rebuild.
- Deleting database rows does not automatically delete MinIO objects.
