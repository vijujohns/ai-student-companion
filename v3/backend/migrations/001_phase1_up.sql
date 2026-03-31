-- Phase 1 schema migration (up)
-- Includes policy, indexing, lesson card, artifact, and profile audit primitives.

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS usage_counters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  uploads_count INTEGER DEFAULT 0,
  quiz_count INTEGER DEFAULT 0,
  flashcard_count INTEGER DEFAULT 0,
  lesson_count INTEGER DEFAULT 0,
  ask_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS message_catalog (
  message_id TEXT PRIMARY KEY,
  level TEXT NOT NULL,
  template TEXT NOT NULL,
  user_friendly_text TEXT NOT NULL,
  developer_notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_storage_roots (
  user_id TEXT PRIMARY KEY,
  email_hash_root TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS uploaded_files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  class_name TEXT NOT NULL,
  subject_name TEXT NOT NULL,
  folder_name TEXT NOT NULL,
  file_name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  file_sha256 TEXT,
  mime_type TEXT,
  size_bytes INTEGER,
  upload_status TEXT DEFAULT 'UPLOADED',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS indexing_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT,
  scope_type TEXT NOT NULL,
  scope_ref TEXT,
  status TEXT DEFAULT 'QUEUED',
  started_at TEXT,
  ended_at TEXT,
  error_code TEXT,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS file_index_status (
  file_id INTEGER PRIMARY KEY,
  indexed INTEGER DEFAULT 0,
  index_version TEXT,
  last_indexed_at TEXT,
  status_reason TEXT,
  message_id TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lesson_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lesson_plan_id INTEGER NOT NULL,
  card_order INTEGER NOT NULL,
  title TEXT NOT NULL,
  card_type TEXT,
  content_json TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lesson_card_progress (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  lesson_plan_id INTEGER NOT NULL,
  card_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  completed_at TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, lesson_plan_id, card_id)
);

CREATE TABLE IF NOT EXISTS learning_artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  session_id TEXT,
  lesson_plan_id INTEGER,
  card_id INTEGER,
  artifact_type TEXT NOT NULL,
  title TEXT,
  tags TEXT,
  payload_json TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profile_audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  action TEXT NOT NULL,
  changes_json TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email);

COMMIT;
