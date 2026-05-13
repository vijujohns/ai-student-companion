# Vector Store Abstraction Design

## Overview

The current system uses FAISS directly for vector storage and retrieval, which ties the application to a specific vector store implementation. This design proposes an abstraction layer to support multiple vector stores, including future external options like Pinecone or Weaviate.

## Current State

- FAISS index loaded in `faiss_store.py`.
- Direct calls to FAISS for add/search operations.
- No abstraction; FAISS-specific code throughout `retrieval_orchestrator.py` and `rag.py`.
- Index persistence via pickle files.

## Proposed Abstraction

### Interface

```python
class VectorStore(Protocol):
    def add_vectors(self, vectors: List[List[float]], metadata: List[Dict[str, Any]]) -> List[str]:
        """Add vectors, return ids."""
        ...

    def search(self, query_vector: List[float], top_k: int = 10) -> List[Tuple[str, float]]:
        """Search vectors, return (id, score) pairs."""
        ...

    def delete(self, ids: List[str]) -> None:
        """Delete vectors by ids."""
        ...

    def save(self) -> None:
        """Persist the index."""
        ...

    def load(self) -> None:
        """Load the index."""
        ...
```

### Implementations

1. **FAISS Store**: Wrap existing FAISS usage.
2. **In-Memory Store**: For testing, using dict or list.
3. **External Store**: For production, using Pinecone API.

### Migration Plan

1. Add `VectorStore` interface to `interfaces/service_ports.py`.
2. Implement FAISS wrapper in `adapters/default_services.py`.
3. Update `faiss_store.py` to use the abstraction.
4. Update `retrieval_orchestrator.py` and `rag.py` to use the interface.
5. Add configuration for vector store type.

### Benefits

- Pluggable vector stores.
- Easier testing and development.
- Future-proof for scaling to external vector databases.

### Risks

- Performance overhead from abstraction.
- Migration complexity for existing FAISS data.
- Configuration complexity for multiple store types.</content>
<parameter name="filePath">d:\GPT\ai-student-companion\ai_tutor_control\job_queue_abstraction_design.md