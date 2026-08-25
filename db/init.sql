
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
  status           TEXT NOT NULL DEFAULT 'Not Started',
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
  want_identify    BOOLEAN NOT NULL DEFAULT FALSE,
  want_demucs      BOOLEAN NOT NULL DEFAULT FALSE,
  want_whisper     BOOLEAN NOT NULL DEFAULT FALSE,
  want_classify    BOOLEAN NOT NULL DEFAULT FALSE,
  done_identify    BOOLEAN NOT NULL DEFAULT FALSE,
  done_demucs      BOOLEAN NOT NULL DEFAULT FALSE,
  done_whisper     BOOLEAN NOT NULL DEFAULT FALSE,
  done_classify    BOOLEAN NOT NULL DEFAULT FALSE
);
