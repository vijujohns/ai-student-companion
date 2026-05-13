# Operations Runbooks

## Overview

This document provides operational procedures for running and maintaining the AI Student Companion in production environments. It covers backup/restore, reindexing, production hardening, monitoring, and recovery procedures.

## Backup Procedures

### Database Backup

1. **SQLite Backup** (Current):
   - Stop the application to ensure consistency.
   - Copy `v3/data/app.db` and `v3/data/app.db-journal` to backup location.
   - Restart the application.

2. **Future PostgreSQL Backup**:
   - Use `pg_dump` for logical backups.
   - Schedule automated backups via cron or backup service.
   - Store backups encrypted in cloud storage.

### Knowledge Base Backup

1. **FAISS Index**:
   - Copy `v3/data/faiss.index` file.
   - Backup associated metadata files: `logical_indexes.json`, `metadata.json`, `pdf_summaries.json`.

2. **Uploaded Documents**:
   - Backup entire `v3/app/uploads/` directory.
   - Maintain file permissions and ownership.

### Configuration Backup

- Backup `v3/configs/settings.json`.
- Backup environment variables and secrets securely.

## Restore Procedures

### Database Restore

1. **SQLite Restore**:
   - Stop the application.
   - Replace `v3/data/app.db` with backup copy.
   - Remove any existing journal file.
   - Start the application.

2. **PostgreSQL Restore**:
   - Use `pg_restore` from backup dump.
   - Verify data integrity with test queries.

### Knowledge Base Restore

1. **FAISS Index**:
   - Replace `v3/data/faiss.index` and metadata files.
   - Restart application to reload index.

2. **Documents**:
   - Restore `v3/app/uploads/` directory.
   - Run reindexing procedure if needed.

## Reindexing Procedures

### Full Knowledge Base Reindex

1. **Via Admin API**:
   - POST `/admin/reindex` with `{"full": true}`.
   - Monitor progress via `/admin/indexing-jobs/{job_id}`.

2. **Manual Reindex**:
   - Stop application.
   - Delete `v3/data/faiss.index` and metadata files.
   - Start application (will auto-reindex on startup).
   - Monitor logs for completion.

### Partial Reindex

1. **Single Document**:
   - Delete document from uploads.
   - Re-upload document (triggers reindex).

2. **Class-Specific**:
   - Use admin API to reindex specific class directories.

## Production Hardening

### Security Measures

1. **Network Security**:
   - Run behind reverse proxy (nginx/Caddy).
   - Enable HTTPS with valid certificates.
   - Configure firewall rules.

2. **Application Security**:
   - Use strong secrets for JWT and encryption.
   - Enable CORS only for trusted domains.
   - Regular dependency updates.

3. **Data Protection**:
   - Encrypt sensitive data at rest.
   - Implement rate limiting.
   - Use secure file permissions.

### Performance Optimization

1. **Database**:
   - Enable WAL mode for SQLite.
   - Configure connection pooling for PostgreSQL.
   - Regular VACUUM operations.

2. **Application**:
   - Configure appropriate worker processes.
   - Set memory limits.
   - Enable compression.

3. **Caching**:
   - Implement Redis for session caching.
   - Cache frequent queries.

## Monitoring Setup

### Application Metrics

1. **Request Metrics**:
   - Track request count, latency, error rates.
   - Monitor by endpoint and method.

2. **Business Metrics**:
   - User registrations, active sessions.
   - Knowledge base size, indexing status.
   - AI model usage and performance.

3. **System Metrics**:
   - CPU, memory, disk usage.
   - Database connection counts.
   - External service health.

### Logging

1. **Log Levels**:
   - ERROR: Critical issues requiring immediate attention.
   - WARN: Potential issues or unusual conditions.
   - INFO: Normal operational events.
   - DEBUG: Detailed diagnostic information.

2. **Log Aggregation**:
   - Centralize logs using ELK stack or similar.
   - Set up alerts for error patterns.

3. **Request Correlation**:
   - Use X-Request-ID for tracing requests across services.

### Health Checks

1. **Application Health**:
   - `/health` endpoint for basic checks.
   - `/health/detailed` for comprehensive diagnostics.

2. **Dependency Checks**:
   - Database connectivity.
   - AI model availability.
   - External service status.

## Recovery Procedures

### Application Crashes

1. **Automatic Recovery**:
   - Configure process manager (systemd/pm2) for auto-restart.
   - Implement circuit breakers for external services.

2. **Manual Recovery**:
   - Check logs for crash cause.
   - Restart application.
   - Verify functionality with smoke tests.

### Data Corruption

1. **Detection**:
   - Monitor for database integrity errors.
   - Regular checksum validation of critical files.

2. **Recovery**:
   - Restore from last known good backup.
   - Run data validation scripts.
   - Reindex knowledge base if affected.

### Service Outages

1. **AI Model Failures**:
   - Fallback to cached responses if available.
   - Queue requests for retry.
   - Alert on extended outages.

2. **Database Issues**:
   - Implement read replicas for redundancy.
   - Use connection pooling with retry logic.

## Maintenance Windows

### Scheduled Maintenance

1. **Weekly Tasks**:
   - Database VACUUM and ANALYZE.
   - Log rotation and archival.
   - Security updates.

2. **Monthly Tasks**:
   - Full backup verification.
   - Performance benchmarking.
   - Dependency updates.

### Emergency Maintenance

1. **Planning**:
   - Document emergency procedures.
   - Maintain on-call rotation.
   - Test recovery procedures regularly.

2. **Communication**:
   - Notify users of scheduled downtime.
   - Provide status updates during outages.