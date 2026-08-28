
CREATE TABLE IF NOT EXISTS songs (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  artist TEXT,
  lyrics TEXT,
  classification TEXT CHECK (classification IN ('AI','Human')),
  accuracy NUMERIC(5,4),
  file_path TEXT,                    -- MinIO object key, e.g. stems/<id>.wav
  duration INTEGER,
  fingerprint TEXT,
  fingerprint_hash TEXT UNIQUE,     -- natural key for dedupe/upsert
  audio_processed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_songs_hash ON songs(fingerprint_hash);


CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS jobs (
  id               BIGSERIAL PRIMARY KEY,
  song_id          INTEGER REFERENCES songs(id) ON DELETE SET NULL,
  current_stage    TEXT,
  status           TEXT NOT NULL DEFAULT 'queued'
                   CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')),
  input_type       TEXT,
  title            TEXT NOT NULL,
  artist           TEXT,
  lyrics           TEXT,
  classification   TEXT CHECK (classification IN ('AI','Human')),
  accuracy         NUMERIC(5,4),
  file_path       TEXT,              -- MinIO object key, e.g. raw/<id>.mp3
  duration         INTEGER,
  fingerprint      TEXT,
  fingerprint_hash TEXT,     -- natural key for dedupe/upsert
  audio_processed  BOOLEAN DEFAULT FALSE,
  error            TEXT,
  created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_steps (
  id            BIGSERIAL PRIMARY KEY,
  job_id        BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  stage         TEXT NOT NULL CHECK (stage IN ('identify', 'demucs', 'whisper', 'classify')),
  position      SMALLINT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')),
  attempts      INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  result        JSONB,
  error         TEXT,
  queued_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at    TIMESTAMP,
  completed_at  TIMESTAMP,
  UNIQUE (job_id, stage),
  UNIQUE (job_id, position)
);

CREATE INDEX IF NOT EXISTS idx_job_steps_queue
  ON job_steps(status, job_id, position);

CREATE INDEX IF NOT EXISTS idx_job_steps_job
  ON job_steps(job_id, position);
