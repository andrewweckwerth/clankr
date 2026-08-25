# Data model and pipeline state

## `songs`

`songs` is the durable result table. It stores user-visible metadata and the latest completed analysis for a fingerprinted recording.

| Column group | Fields | Purpose |
| --- | --- | --- |
| Identity | `id`, `title`, `artist`, `fingerprint`, `fingerprint_hash` | Match and deduplicate recordings |
| Analysis | `lyrics`, `classification`, `accuracy`, `duration` | Store stage results |
| Storage | `file_path`, `audio_processed` | Point to the related MinIO object |
| Timestamps | `created_at`, `updated_at` | Record lifecycle times |

`fingerprint_hash` has a unique constraint and is an indexable natural key. The orchestrator computes it from the Chromaprint fingerprint string.

## `jobs`

`jobs` is the work and progress table. It contains a copy of the fields needed to carry an in-flight request plus four pairs of flags:

```text
want_identify / done_identify
want_demucs   / done_demucs
want_whisper  / done_whisper
want_classify / done_classify
```

The `status` column is used by the worker claim query. Typical values are `Not Started`, `Claimed`, `In Progress`, `Completed`, and `Failed`. `current_stage` records the stage currently being attempted.

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

When the requested flags are all complete, the orchestrator writes a song using the job's accumulated fields. Existing rows with the same fingerprint hash are updated rather than duplicated. Search uses PostgreSQL trigram similarity over title and artist and accepts the best match when its score is at least `0.3`.

## Schema limitations

- `updated_at` is declared but no trigger currently updates it.
- Status and stage values are free-form text rather than database enums.
- `jobs` duplicates many `songs` columns to make stage-by-stage updates simple.
- `database/init.sql` uses `CREATE TABLE IF NOT EXISTS`; changing an existing database requires an explicit migration or controlled rebuild.
- Deleting database rows does not automatically delete MinIO objects.

