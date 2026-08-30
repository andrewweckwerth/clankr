
-- Better Auth owns authentication identity, sessions, and linked providers.
-- These tables deliberately use a separate namespace from the app's local
-- users table, which maps auth_users.id to app-owned ownership records.
CREATE TABLE IF NOT EXISTS auth_users (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  email           TEXT NOT NULL UNIQUE,
  email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
  image           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_sessions (
  id          TEXT PRIMARY KEY,
  expires_at  TIMESTAMPTZ NOT NULL,
  token       TEXT NOT NULL UNIQUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ip_address  TEXT,
  user_agent  TEXT,
  user_id     TEXT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
  ON auth_sessions(user_id);

CREATE TABLE IF NOT EXISTS auth_accounts (
  id                     TEXT PRIMARY KEY,
  issuer                 TEXT NOT NULL,
  account_id             TEXT NOT NULL,
  provider_id            TEXT NOT NULL,
  user_id                TEXT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
  access_token           TEXT,
  refresh_token          TEXT,
  id_token               TEXT,
  access_token_expires_at TIMESTAMPTZ,
  refresh_token_expires_at TIMESTAMPTZ,
  scope                  TEXT,
  password               TEXT,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (issuer, account_id)
);

CREATE INDEX IF NOT EXISTS idx_auth_accounts_user_id
  ON auth_accounts(user_id);

CREATE TABLE IF NOT EXISTS auth_verifications (
  id           TEXT PRIMARY KEY,
  identifier   TEXT NOT NULL,
  value        TEXT NOT NULL,
  expires_at   TIMESTAMPTZ NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auth_verifications_identifier
  ON auth_verifications(identifier);

CREATE TABLE IF NOT EXISTS users (
  id              BIGSERIAL PRIMARY KEY,
  auth_user_id    TEXT NOT NULL UNIQUE,
  email           TEXT,
  display_name    TEXT,
  image_url       TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
  user_id          BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS user_songs (
  user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  song_id             INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
  first_submitted_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_submitted_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  submission_count    INTEGER NOT NULL DEFAULT 1 CHECK (submission_count > 0),
  PRIMARY KEY (user_id, song_id)
);

CREATE INDEX IF NOT EXISTS idx_user_songs_user_submitted
  ON user_songs(user_id, last_submitted_at DESC);

CREATE TABLE IF NOT EXISTS user_daily_usage (
  user_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  usage_date     DATE NOT NULL,
  analysis_count INTEGER NOT NULL DEFAULT 0 CHECK (analysis_count >= 0),
  PRIMARY KEY (user_id, usage_date)
);

CREATE INDEX IF NOT EXISTS idx_user_daily_usage_date
  ON user_daily_usage(usage_date);

CREATE INDEX IF NOT EXISTS idx_jobs_user_created
  ON jobs(user_id, created_at DESC);
