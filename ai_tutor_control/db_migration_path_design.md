# Job Queue Abstraction Design

## Overview

The current system runs indexing and long AI jobs in-process, which can block the main FastAPI event loop and cause timeouts or poor responsiveness. This design proposes an abstraction for moving these jobs to an external queue system.

## Current State

- Indexing jobs are started via `start_reindex_job()` in `kb_sync.py`, which runs in a background asyncio task.
- Long AI generation (chat, lessons, etc.) streams directly in the request handler.
- No persistent queue; jobs are lost on restart.
- `indexing_jobs` table tracks status but not queue state.

## Proposed Abstraction

### Interface

```python
class JobQueue(Protocol):
    def enqueue(self, job_type: str, payload: Dict[str, Any], priority: int = 0) -> str:
        """Enqueue a job, return job_id."""
        ...

    def dequeue(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Dequeue next job for worker."""
        ...

    def complete(self, job_id: str, result: Dict[str, Any]) -> None:
        """Mark job complete."""
        ...

    def fail(self, job_id: str, error: str) -> None:
        """Mark job failed."""
        ...

    def status(self, job_id: str) -> Dict[str, Any]:
        """Get job status."""
        ...
```

### Implementations

1. **In-Memory Queue**: For development, using asyncio.Queue.
2. **Redis Queue**: For production, using Redis lists or streams.
3. **Database Queue**: Fallback using the existing `indexing_jobs` table.

### Migration Plan

1. Add `JobQueue` interface to `interfaces/service_ports.py`.
2. Implement default service in `adapters/default_services.py`.
3. Update `kb_sync.py` to use queue for reindex jobs.
4. Add worker process/script for job execution.
5. Update API endpoints to query queue status.

### Benefits

- Non-blocking request handling.
- Persistent job state across restarts.
- Horizontal scaling of workers.
- Better monitoring and retry logic.

### Risks

- Added complexity for job coordination.
- Potential for job duplication or loss during migration.
- Worker process management overhead.</content>
<parameter name="filePath">d:\GPT\ai-student-companion\ai_tutor_control\job_queue_abstraction_design.md