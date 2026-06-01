# Caching Architecture

RAGCore implements a 3-tier caching system for optimal performance.

## Layer 1: In-Memory LRU (Embeddings)

Fastest tier — stores embedding vectors in memory using an LRU eviction policy.

- **Location**: `ragcore/embeddings/cache.py` — `LRUCache`
- **Max size**: Configurable via `RAGCORE_CACHE_LRU_MAXSIZE` (default: 4096)
- **Eviction**: Least Recently Used

## Layer 2: Disk Cache (Embeddings)

Persistent SQLite cache for embedding vectors. Survives restarts.

- **Location**: `ragcore/embeddings/cache.py` — `DiskCache`
- **DB file**: `{data_dir}/cache/embed_cache.db`
- **TTL**: Configurable via `RAGCORE_CACHE_EMBEDDING_TTL` (default: 86400s = 24h)
- **Key**: SHA-256 hash of `prefix:text:model_name`

## Layer 3: Semantic Cache (Responses)

Caches LLM responses by semantic similarity. When a new query arrives, it's embedded and compared against past query embeddings. If similarity exceeds the threshold, the cached response is returned.

- **Location**: `ragcore/cache/semantic_cache.py` — `SemanticCache`
- **DB file**: `{data_dir}/cache/semantic_cache.db`
- **Similarity threshold**: `RAGCORE_CACHE_SEMANTIC_THRESHOLD` (default: 0.92)
- **TTL**: `RAGCORE_CACHE_SEMANTIC_TTL` (default: 3600s = 1h)

### How it works:
1. Query arrives → compute embedding
2. Search top 50 cached queries sorted by access count
3. If any cached query has cosine similarity >= threshold → return cached response
4. Otherwise → run full RAG pipeline → cache the result

## Configuration

```env
RAGCORE_CACHE_ENABLED=true
RAGCORE_CACHE_EMBEDDING_TTL=86400
RAGCORE_CACHE_SEMANTIC_TTL=3600
RAGCORE_CACHE_SEMANTIC_THRESHOLD=0.92
RAGCORE_CACHE_LRU_MAXSIZE=4096
```

## Per-Request Cache Control

```python
# Disable cache for a specific query
result = pipeline.query("question", use_cache=False)

# Re-enable via API
POST /query { "question": "...", "use_cache": false }
```
