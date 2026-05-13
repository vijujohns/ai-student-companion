# API Versioning Strategy

**Last Updated**: May 10, 2026  
**Status**: Implemented – Version 1.0

## Overview

This document defines the API versioning strategy for the Brain Teaser backend to enable controlled evolution while maintaining backward compatibility and clear migration paths for clients.

## Versioning Approach

### URL-Based Versioning

All API endpoints are available under both unversioned and versioned paths:

- **Unversioned (backward compat)**: `/login`, `/ask`, `/quiz/generate`, etc.
- **Versioned**: `/api/v1/login`, `/api/v1/ask`, `/api/v1/quiz/generate`, etc.

Both paths return **identical response schemas** and behavior.

### Version Lifecycle

| Phase | Version | Status | Support Duration |
|-------|---------|--------|------------------|
| Current | v1 | Stable | 12+ months from release |
| Future | v2+ | TBD | TBD |

### Breaking Change Policy

A breaking change is defined as:
- Removal or renaming of response fields
- Change in response structure or nesting
- Modification of authentication/authorization requirements
- Change in HTTP status code semantics
- Alteration of error response format (outside the envelope)

**When a breaking change is necessary**:
1. Introduce the change under a new major version (`/api/v2/`)
2. Maintain the prior version for a deprecation window (12 months minimum)
3. Communicate deprecation timeline to clients via:
   - Release notes
   - API documentation
   - Deprecation headers (optional in future)

### Non-Breaking Changes

The following do not require version increments:
- Addition of new optional response fields
- Addition of new endpoints
- Deprecation of unrelated endpoints
- Internal refactoring that preserves contracts
- Bug fixes that align behavior with documented contracts

## Router Structure

```
v3/backend/app/api/
├── routes.py              # Unversioned routes (backward compat)
├── v1/
│   ├── __init__.py        # Versioned router factory
│   └── routing.py         # v1-specific routing if needed
├── auth_session.py
├── knowledge.py
├── ask.py
├── quiz.py
├── lesson_plan.py
├── assessment.py
├── progress.py
├── collaboration.py
├── subscription.py
├── admin.py
├── health.py
└── websocket.py
```

## Implementation

### Backward Compatibility

The existing unversioned routes continue to function as before:

```python
# Old clients continue to work
GET /login
POST /ask
GET /quiz/generate
```

### Versioned Routes

New versioned routes are registered under `/api/v1`:

```python
# New clients can use versioned paths
GET /api/v1/login
POST /api/v1/ask
GET /api/v1/quiz/generate
```

### Response Format

Both versioned and unversioned endpoints return the same envelope structure:

```json
{
  "data": { ... },
  "message": {
    "id": "MSG-xxxx",
    "user_text": "...",
    "level": "info|warning|error|success"
  },
  "timestamp": "2026-05-10T21:00:00Z"
}
```

## Migration Guide for Clients

### Phase 1: Current (v1 Stable)

Clients can use either:
- Unversioned paths: `/login`, `/ask`, etc. (current default)
- Versioned paths: `/api/v1/login`, `/api/v1/ask` (future-proof)

### Phase 2: Future (v2 Released)

When `/api/v2/` becomes available, clients should:
1. Plan migration to v2 within 6 months
2. Use `/api/v1/` as intermediate step if needed
3. Test v2 contracts thoroughly before cutover

### Phase 3: Deprecation (v1 End-of-Life + 12 months)

v1 support ends; all clients must migrate to v2.

## API Gateway / Proxy Considerations

For deployments behind API gateways or proxies:
- Route `/api/v1/*` to the versioned router
- Route unversioned paths directly to `routes.py`
- Consider path rewriting if clients cannot modify URLs

## Testing

All versioned endpoints have corresponding tests that validate:
1. **Response schema** is correct
2. **Status codes** match expectations
3. **Error envelopes** follow the defined format
4. **Backward compatibility** with unversioned paths

See `v3/test_suite/backend/test_api_versioning.py` for details.

## Future Considerations

- **Deprecation headers**: May add `Deprecation` and `Sunset` headers in future versions
- **OpenAPI/Swagger**: Versioning separated in documentation
- **Rate limiting per version**: May vary limits based on client version
- **Metrics tracking**: Track adoption of v1 vs. future versions
- **Client libraries**: May publish versioned SDKs

## References

- [REST API Versioning Best Practices](https://restfulapi.net/versioning/)
- [Semantic Versioning](https://semver.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
