-- Phase 1 schema rollback (down)
-- Intended for controlled staging rollback only.
-- Take a DB backup before applying this script.

BEGIN TRANSACTION;

DROP TABLE IF EXISTS profile_audit_log;
DROP TABLE IF EXISTS learning_artifacts;
DROP TABLE IF EXISTS lesson_card_progress;
DROP TABLE IF EXISTS lesson_cards;
DROP TABLE IF EXISTS file_index_status;
DROP TABLE IF EXISTS indexing_jobs;
DROP TABLE IF EXISTS uploaded_files;
DROP TABLE IF EXISTS user_storage_roots;
DROP TABLE IF EXISTS message_catalog;
DROP TABLE IF EXISTS usage_counters;

COMMIT;
