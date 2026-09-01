-- Adds explicit full-project versus standalone-tool semantics while preserving
-- existing preproduction jobs as full-project jobs.
BEGIN;

ALTER TABLE songs
  ADD COLUMN IF NOT EXISTS pipeline_complete BOOLEAN NOT NULL DEFAULT FALSE;

-- Older finalization wrote the Song from a stale pre-event job snapshot. Repair
-- canonical candidates from the latest completed job that actually ran all
-- four stages before deciding which rows are cacheable.
WITH completed_full_jobs AS (
  SELECT DISTINCT ON (jobs.song_id) jobs.*
  FROM jobs
  WHERE jobs.song_id IS NOT NULL
    AND jobs.status = 'completed'
    AND 4 = (
      SELECT COUNT(*)
      FROM job_steps
      WHERE job_steps.job_id = jobs.id
        AND job_steps.status = 'completed'
    )
  ORDER BY jobs.song_id, jobs.completed_at DESC NULLS LAST, jobs.id DESC
)
UPDATE songs
SET title = COALESCE(completed_full_jobs.title, songs.title),
    artist = COALESCE(completed_full_jobs.artist, songs.artist),
    lyrics = COALESCE(completed_full_jobs.lyrics, songs.lyrics),
    classification = COALESCE(completed_full_jobs.classification, songs.classification),
    accuracy = COALESCE(completed_full_jobs.accuracy, songs.accuracy),
    file_path = COALESCE(completed_full_jobs.file_path, songs.file_path),
    duration = COALESCE(completed_full_jobs.duration, songs.duration),
    fingerprint = COALESCE(completed_full_jobs.fingerprint, songs.fingerprint),
    fingerprint_hash = COALESCE(completed_full_jobs.fingerprint_hash, songs.fingerprint_hash),
    audio_processed = completed_full_jobs.audio_processed OR songs.audio_processed,
    updated_at = CURRENT_TIMESTAMP
FROM completed_full_jobs
WHERE songs.id = completed_full_jobs.song_id;

UPDATE songs
SET pipeline_complete = TRUE
WHERE audio_processed IS TRUE
  AND fingerprint_hash IS NOT NULL
  AND lyrics IS NOT NULL
  AND classification IS NOT NULL
  AND accuracy IS NOT NULL
  AND file_path LIKE 'stems/%';

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS job_type TEXT;

UPDATE jobs
SET job_type = 'full'
WHERE job_type IS NULL;

UPDATE jobs
SET job_type = CASE (
  SELECT stage
  FROM job_steps
  WHERE job_steps.job_id = jobs.id
  LIMIT 1
)
  WHEN 'identify' THEN 'acousti'
  WHEN 'demucs' THEN 'demucs'
  WHEN 'whisper' THEN 'whisper'
  WHEN 'classify' THEN 'classifier'
  ELSE 'full'
END
WHERE 1 = (
  SELECT COUNT(*)
  FROM job_steps
  WHERE job_steps.job_id = jobs.id
);

ALTER TABLE jobs
  ALTER COLUMN job_type SET DEFAULT 'full',
  ALTER COLUMN job_type SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'jobs_job_type_check'
  ) THEN
    ALTER TABLE jobs
      ADD CONSTRAINT jobs_job_type_check
      CHECK (job_type IN ('full', 'acousti', 'demucs', 'whisper', 'classifier'));
  END IF;
END
$$;

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS source_file_path TEXT;

UPDATE jobs
SET source_file_path = file_path
WHERE source_file_path IS NULL
  AND input_type = 'audio'
  AND (
    status <> 'failed'
    OR current_stage IN ('identify', 'demucs')
  );

-- Older failures at Whisper or Classifier no longer retain enough information
-- to distinguish the raw upload from the mutable stage file. Leave those rows
-- without a retry source instead of rerunning identification on a vocal stem.

COMMIT;
