# API Reference

## Python API

### `RAGApp(config: dict | None = None)`

Full RAG application with built-in FastAPI server.

```python
from ragcore import RAGApp
app = RAGApp()
app.serve()  # starts uvicorn server
```

### `RAGClient(pipeline: RAGPipeline | None = None)`

Lightweight client for embedding into existing apps.

```python
from ragcore import RAGClient
rag = RAGClient()
result = await rag.query("question")
```

Methods:
- `query(question, k, chat_history, use_cache)` → `dict` (async)
- `query_sync(question, k, chat_history, use_cache)` → `dict` (sync)
- `ingest_text(text, metadata)` → `list[str]`
- `ingest_file(path, metadata)` → `list[str]`

### `RAGPipeline(config: dict | None = None)`

Core pipeline orchestrator. Direct access to all components.

Methods:
- `ingest_text(text, metadata)`, `ingest_file(path, metadata)`, `ingest_directory(path)`
- `query(question, k, chat_history, use_cache)`
- `query_stream(question, k, chat_history)` → `AsyncIterator[str]`
- `retrieve_only(question, k)`
- `set_retrieval_strategy(strategy)`
- `save_index(name)`, `load_index(name)`
- `delete_documents(doc_ids)`
- `get_stats()`

## REST API Endpoints

### Health
`GET /health` → `{status, version, components}`

### Ingestion
`POST /ingest/text` — Body: `{text, metadata?}` → `{doc_ids, chunk_count}`

`POST /ingest/file` — Multipart file upload → `{doc_ids, chunk_count}`

`POST /ingest/directory?path=/docs&recursive=true` → `{doc_ids, chunk_count}`

`DELETE /ingest/{doc_id}` → `{deleted_count}`

### Query
`POST /query` — Body: `{question, k?, retrieval_strategy?, chat_history?, use_cache?}` → `{answer, sources, ...}`

`POST /query/stream` — Body: `{question, k?, retrieval_strategy?, chat_history?}` → SSE stream

`POST /query/retrieve` — Body: `{question, k?, retrieval_strategy?}` → `{results, total}`

### Management
`GET /manage/index/stats` → `{vectorstore, retrieval_strategy, active_index, available_indexes}`

`POST /manage/index/save` — Body: `{name?}` → `{status, message}`

`POST /manage/index/load` — Body: `{name}` → `{status, message}`

`POST /manage/index/clear` → `{status, message}`

`GET /manage/index/list` → `[{name, created_at, ...}]`

`POST /manage/retrieval/strategy?strategy=hybrid` → `{status, strategy}`

`GET /manage/config` → Current runtime configuration
